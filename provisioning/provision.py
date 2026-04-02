"""
provision.py — Docker SDK provisioning logic for focuscall.ai
Manages ZeroClaw container lifecycle: create, start, health-check, deprovision.

SECURITY NOTE:
  Keys (llm_key, bot_token) are NEVER written to disk.
  They are passed exclusively as Docker ENV vars to the container.
  The config.toml written to workspace contains NO secrets.

Config env vars (injected by docker-compose.infra.yml):
  REGISTRY_PATH        — /opt/focuscall/registry.json
  WORKSPACE_BASE       — /opt/focuscall/workspaces
  CONFIG_TEMPLATE_PATH — /app/config.toml.tmpl (or /opt/focuscall/config.toml.tmpl)
"""

import json
import logging
import os
import pathlib
import shutil
import string
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

import docker
import fcntl

# ── Config ─────────────────────────────────────────────────────────────────────
REGISTRY_PATH: str = os.getenv("REGISTRY_PATH", "/opt/focuscall/registry.json")
WORKSPACE_BASE: str = os.getenv("WORKSPACE_BASE", "/opt/focuscall/workspaces")
CONFIG_TEMPLATE_PATH: str = os.getenv(
    "CONFIG_TEMPLATE_PATH",
    os.path.join(os.path.dirname(__file__), "config.toml.tmpl"),
)

ZEROCLAW_IMAGE: str = "zeroclaw:latest"
PORT_BASE: int = 42000
HEALTH_CHECK_ATTEMPTS: int = 10
HEALTH_CHECK_INTERVAL_SEC: float = 2.0

log = logging.getLogger("provision")


# ── Registry helpers (with file locking for concurrent access) ─────────────────

def _load_registry(lock_fd: int) -> dict:
    """Read and parse registry.json. Caller must hold lock_fd."""
    registry_path = pathlib.Path(REGISTRY_PATH)
    if not registry_path.exists():
        # Bootstrap empty registry
        default = {"next_port": PORT_BASE, "instances": {}}
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(registry_path.read_text())


def _save_registry(data: dict, lock_fd: int) -> None:
    """Atomically write registry via temp file. Caller must hold lock_fd."""
    registry_path = pathlib.Path(REGISTRY_PATH)
    tmp_path = registry_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(registry_path)


def _open_registry_lock():
    """Open and exclusively lock the registry lock file."""
    lock_path = REGISTRY_PATH + ".lock"
    pathlib.Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_registry_lock(fd) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()


# ── Core provisioning ──────────────────────────────────────────────────────────

def provision_container(
    user_id: str,
    agent_id: str,
    llm_key: str,      # NEVER written to disk — Docker ENV only
    bot_token: str,    # NEVER written to disk — Docker ENV only
    llm_provider: str,
) -> dict[str, Any]:
    """
    Provision a ZeroClaw container for a user/agent pair.

    Steps:
      1. Allocate port from registry (fcntl-locked)
      2. Create workspace directory
      3. Render config.toml from template (no secrets in template)
      4. Start Docker container with keys as ENV vars only
      5. Health-check loop (10x, 2s apart)
      6. Update registry with final status
      7. Return result dict
    """
    instance_key = f"{user_id}-{agent_id}"
    container_name = f"fc-{user_id}-{agent_id}"

    # ── Step 1: Allocate port ─────────────────────────────────────────────────
    lock_fd = _open_registry_lock()
    try:
        registry = _load_registry(lock_fd)

        # Check for existing instance
        if instance_key in registry.get("instances", {}):
            existing = registry["instances"][instance_key]
            if existing.get("status") in ("running", "starting"):
                log.warning("Instance %s already exists with status %s", instance_key, existing["status"])
                return {"status": existing["status"], "port": existing["port"], "container_id": existing.get("container_id")}

        port = registry["next_port"]
        registry["next_port"] = port + 1
        registry.setdefault("instances", {})[instance_key] = {
            "port": port,
            "status": "starting",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "container_name": container_name,
        }
        _save_registry(registry, lock_fd)
    finally:
        _release_registry_lock(lock_fd)

    log.info("Allocated port %d for %s", port, instance_key)

    # ── Step 2: Create workspace ──────────────────────────────────────────────
    workspace = pathlib.Path(WORKSPACE_BASE) / user_id / agent_id
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "db").mkdir(exist_ok=True)
        (workspace / "logs").mkdir(exist_ok=True)
        log.info("Workspace created: %s", workspace)
    except OSError as exc:
        _set_instance_status(instance_key, "error", error=str(exc))
        raise RuntimeError(f"Failed to create workspace {workspace}: {exc}") from exc

    # ── Step 3: Render config.toml (no secrets!) ──────────────────────────────
    config_path = workspace / "config.toml"
    try:
        tmpl_text = pathlib.Path(CONFIG_TEMPLATE_PATH).read_text()
        tmpl = string.Template(tmpl_text)
        rendered = tmpl.substitute(
            USER_ID=user_id,
            AGENT_ID=agent_id,
            PORT=str(port),
            LLM_PROVIDER=llm_provider,
        )
        config_path.write_text(rendered)
        log.info("Config rendered to %s (no keys in file)", config_path)
    except (OSError, KeyError, ValueError) as exc:
        _set_instance_status(instance_key, "error", error=str(exc))
        raise RuntimeError(f"Config template rendering failed: {exc}") from exc

    # ── Step 4: Start Docker container ────────────────────────────────────────
    client = docker.from_env()

    # Remove stale container if exists (e.g. after error recovery)
    try:
        old = client.containers.get(container_name)
        log.info("Removing stale container %s", container_name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    try:
        container = client.containers.run(
            image=ZEROCLAW_IMAGE,
            name=container_name,
            detach=True,
            environment={
                # Keys passed as ENV — never touch disk
                "ZEROCLAW_API_KEY": llm_key,
                "TELEGRAM_BOT_TOKEN": bot_token,
                "ZEROCLAW_CONFIG_DIR": "/workspace",
            },
            volumes={
                str(workspace): {"bind": "/workspace", "mode": "rw"},
            },
            # Security constraints
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
            read_only=True,
            mem_limit="128m",
            nano_cpus=500_000_000,  # 0.5 CPUs
            restart_policy={"Name": "unless-stopped"},
            # /tmp needed because root is read-only
            tmpfs={"/tmp": "size=10m,noexec,nosuid"},
            # Network mode: bridge (default) so we can reach container IP
            network_mode="bridge",
        )
        container_id = container.id[:12]
        log.info("Container started: %s (id=%s)", container_name, container_id)
    except docker.errors.ImageNotFound:
        _set_instance_status(instance_key, "error", error="zeroclaw:latest image not found — build first")
        raise RuntimeError("zeroclaw:latest image not found. Run: docker build -t zeroclaw:latest .") from None
    except docker.errors.APIError as exc:
        _set_instance_status(instance_key, "error", error=str(exc))
        raise RuntimeError(f"Docker API error starting container: {exc}") from exc

    # Record container ID in registry
    _update_instance_field(instance_key, "container_id", container_id)

    # ── Step 5: Health-check loop ─────────────────────────────────────────────
    # Reload container to get IP after it's running
    container.reload()
    try:
        container_ip = container.attrs["NetworkSettings"]["IPAddress"]
        if not container_ip:
            # Fallback: inspect bridge network
            networks = container.attrs["NetworkSettings"]["Networks"]
            container_ip = next(iter(networks.values()))["IPAddress"]
    except (KeyError, StopIteration):
        container_ip = "127.0.0.1"

    health_url = f"http://{container_ip}:{port}/health"
    log.info("Starting health checks at %s", health_url)

    healthy = False
    for attempt in range(1, HEALTH_CHECK_ATTEMPTS + 1):
        time.sleep(HEALTH_CHECK_INTERVAL_SEC)
        try:
            with urllib.request.urlopen(health_url, timeout=3) as resp:
                if resp.status == 200:
                    log.info("Health check passed on attempt %d/%d", attempt, HEALTH_CHECK_ATTEMPTS)
                    healthy = True
                    break
        except Exception as exc:
            log.debug("Health check attempt %d/%d failed: %s", attempt, HEALTH_CHECK_ATTEMPTS, exc)

    # ── Steps 6-7: Update registry and return ────────────────────────────────
    if healthy:
        _set_instance_status(instance_key, "running")
        log.info("Instance %s is running on port %d", instance_key, port)
        return {"status": "running", "port": port, "container_id": container_id}
    else:
        log.error(
            "Health check failed after %d attempts for %s — stopping container",
            HEALTH_CHECK_ATTEMPTS,
            instance_key,
        )
        try:
            container.stop(timeout=10)
            container.remove()
        except docker.errors.APIError as exc:
            log.warning("Error cleaning up failed container: %s", exc)

        _set_instance_status(
            instance_key,
            "error",
            error=f"health check timeout after {HEALTH_CHECK_ATTEMPTS * HEALTH_CHECK_INTERVAL_SEC}s",
        )
        return {"status": "error", "port": port, "container_id": container_id}


# ── Deprovisioning ─────────────────────────────────────────────────────────────

def deprovision_container(user_id: str, agent_id: str) -> dict[str, Any]:
    """
    Stop and remove a ZeroClaw container, delete its workspace, clean registry.

    Steps:
      1. Stop container (timeout=10s)
      2. Remove container
      3. Delete workspace directory (shutil.rmtree)
      4. Remove from registry
    """
    instance_key = f"{user_id}-{agent_id}"
    container_name = f"fc-{user_id}-{agent_id}"
    workspace = pathlib.Path(WORKSPACE_BASE) / user_id / agent_id

    log.info("Deprovisioning %s", instance_key)

    # ── Stop and remove container ─────────────────────────────────────────────
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        log.info("Stopping container %s", container_name)
        container.stop(timeout=10)
        container.remove()
        log.info("Container %s removed", container_name)
    except docker.errors.NotFound:
        log.warning("Container %s not found — may have been removed already", container_name)
    except docker.errors.APIError as exc:
        log.error("Error removing container %s: %s", container_name, exc)
        raise RuntimeError(f"Failed to remove container {container_name}: {exc}") from exc

    # ── Delete workspace ──────────────────────────────────────────────────────
    if workspace.exists():
        try:
            shutil.rmtree(workspace)
            log.info("Workspace deleted: %s", workspace)
        except OSError as exc:
            log.error("Failed to delete workspace %s: %s", workspace, exc)
            raise RuntimeError(f"Failed to delete workspace: {exc}") from exc
    else:
        log.warning("Workspace %s does not exist — skipping", workspace)

    # ── Remove from registry ──────────────────────────────────────────────────
    lock_fd = _open_registry_lock()
    try:
        registry = _load_registry(lock_fd)
        instances = registry.get("instances", {})
        if instance_key in instances:
            del instances[instance_key]
            registry["instances"] = instances
            _save_registry(registry, lock_fd)
            log.info("Registry entry removed for %s", instance_key)
        else:
            log.warning("Registry entry not found for %s", instance_key)
    finally:
        _release_registry_lock(lock_fd)

    return {"status": "removed", "user_id": user_id, "agent_id": agent_id}


# ── List containers ────────────────────────────────────────────────────────────

def list_containers() -> dict[str, Any]:
    """Return all instances from registry with their current status."""
    lock_fd = _open_registry_lock()
    try:
        registry = _load_registry(lock_fd)
    finally:
        _release_registry_lock(lock_fd)

    return {
        "next_port": registry.get("next_port", PORT_BASE),
        "instances": registry.get("instances", {}),
    }


# ── Internal helpers ───────────────────────────────────────────────────────────

def _set_instance_status(instance_key: str, status: str, error: str | None = None) -> None:
    """Update status (and optionally error) for an instance in the registry."""
    lock_fd = _open_registry_lock()
    try:
        registry = _load_registry(lock_fd)
        if instance_key in registry.get("instances", {}):
            registry["instances"][instance_key]["status"] = status
            if error:
                registry["instances"][instance_key]["error"] = error
            _save_registry(registry, lock_fd)
    except Exception as exc:
        log.error("Failed to update registry status for %s: %s", instance_key, exc)
    finally:
        _release_registry_lock(lock_fd)


def _update_instance_field(instance_key: str, field: str, value: Any) -> None:
    """Update a single field for an instance in the registry."""
    lock_fd = _open_registry_lock()
    try:
        registry = _load_registry(lock_fd)
        if instance_key in registry.get("instances", {}):
            registry["instances"][instance_key][field] = value
            _save_registry(registry, lock_fd)
    except Exception as exc:
        log.error("Failed to update registry field %s for %s: %s", field, instance_key, exc)
    finally:
        _release_registry_lock(lock_fd)

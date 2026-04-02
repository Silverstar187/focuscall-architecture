"""
webhook-receiver.py — FastAPI webhook receiver for focuscall.ai provisioning
Runs on VPS port 9000 (nginx proxied), validates HMAC-signed requests from
Supabase Edge Functions and dispatches container provisioning.

Required ENV vars:
  WEBHOOK_SECRET     — 32-byte hex string matching Supabase Edge Function secret
  REGISTRY_PATH      — path to registry.json (default: /opt/focuscall/registry.json)
  WORKSPACE_BASE     — base dir for workspaces (default: /opt/focuscall/workspaces)
  CONFIG_TEMPLATE_PATH — path to config.toml.tmpl (default: /app/config.toml.tmpl)
"""

import hashlib
import hmac
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from provision import deprovision_container, list_containers, provision_container

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("webhook-receiver")

# ── Config from ENV ────────────────────────────────────────────────────────────
WEBHOOK_SECRET: str = os.environ["WEBHOOK_SECRET"]  # Hard fail if missing
REGISTRY_PATH: str = os.getenv("REGISTRY_PATH", "/opt/focuscall/registry.json")
WORKSPACE_BASE: str = os.getenv("WORKSPACE_BASE", "/opt/focuscall/workspaces")
CONFIG_TEMPLATE_PATH: str = os.getenv("CONFIG_TEMPLATE_PATH", "/app/config.toml.tmpl")

# Replay protection: reject requests older than this many seconds
MAX_REQUEST_AGE_SECONDS: int = 300  # 5 minutes


# ── HMAC validation ────────────────────────────────────────────────────────────
def _verify_hmac(request_body: bytes, x_timestamp: str, x_signature: str, user_id: str, agent_id: str) -> bool:
    """
    Verify HMAC-SHA256 signature from Supabase Edge Function.

    Signature covers: "{user_id}:{agent_id}:{timestamp}"
    This matches the signing approach in edge-function.ts.
    """
    message = f"{user_id}:{agent_id}:{x_timestamp}"
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, x_signature)


def _check_timestamp(x_timestamp: str) -> bool:
    """Reject requests older than MAX_REQUEST_AGE_SECONDS (replay protection)."""
    try:
        ts = int(x_timestamp)
    except (ValueError, TypeError):
        return False
    age = time.time() - ts
    return 0 <= age <= MAX_REQUEST_AGE_SECONDS


# ── Request models ─────────────────────────────────────────────────────────────
class ProvisionRequest(BaseModel):
    user_id: str
    agent_id: str
    llm_key: str       # Passed directly to Docker ENV — never written to disk
    bot_token: str     # Passed directly to Docker ENV — never written to disk
    llm_provider: str
    llm_key_vault_id: str | None = None
    bot_token_vault_id: str | None = None


class ProvisionResponse(BaseModel):
    status: str
    user_id: str
    agent_id: str


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "Webhook receiver starting up",
        extra={
            "registry_path": REGISTRY_PATH,
            "workspace_base": WORKSPACE_BASE,
            "config_template": CONFIG_TEMPLATE_PATH,
        },
    )
    yield
    log.info("Webhook receiver shutting down")


app = FastAPI(
    title="focuscall.ai Webhook Receiver",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "webhook-receiver"}


# ── POST /provision ────────────────────────────────────────────────────────────
@app.post("/provision", status_code=202, response_model=ProvisionResponse)
async def provision_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
) -> ProvisionResponse:
    """
    Receive HMAC-signed provisioning request from Supabase Edge Function.
    Validates signature and timestamp, then triggers container provisioning
    asynchronously (returns 202 immediately).
    """
    # Read raw body (needed for future full-body HMAC variant)
    raw_body = await request.body()

    # Extract security headers
    x_timestamp = request.headers.get("X-Timestamp", "")
    x_signature = request.headers.get("X-Signature", "")

    if not x_timestamp or not x_signature:
        log.warning("Missing X-Timestamp or X-Signature headers")
        raise HTTPException(status_code=401, detail="Missing authentication headers")

    # Timestamp / replay check (before parsing body to fail fast)
    if not _check_timestamp(x_timestamp):
        log.warning("Request timestamp out of acceptable range: %s", x_timestamp)
        raise HTTPException(status_code=401, detail="Request timestamp invalid or expired")

    # Parse body
    try:
        import json as _json
        payload_dict = _json.loads(raw_body)
        payload = ProvisionRequest(**payload_dict)
    except Exception as exc:
        log.warning("Failed to parse request body: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid request body: {exc}") from exc

    # HMAC validation
    if not _verify_hmac(raw_body, x_timestamp, x_signature, payload.user_id, payload.agent_id):
        log.warning(
            "HMAC validation failed for user_id=%s agent_id=%s",
            payload.user_id,
            payload.agent_id,
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    log.info(
        "Provisioning request validated: user_id=%s agent_id=%s provider=%s",
        payload.user_id,
        payload.agent_id,
        payload.llm_provider,
    )

    # Dispatch provisioning in background — return 202 immediately
    background_tasks.add_task(
        _run_provision,
        payload.user_id,
        payload.agent_id,
        payload.llm_key,
        payload.bot_token,
        payload.llm_provider,
    )

    return ProvisionResponse(
        status="provisioning",
        user_id=payload.user_id,
        agent_id=payload.agent_id,
    )


async def _run_provision(
    user_id: str,
    agent_id: str,
    llm_key: str,
    bot_token: str,
    llm_provider: str,
) -> None:
    """Background task: delegates to provision.py, logs result."""
    try:
        result = provision_container(
            user_id=user_id,
            agent_id=agent_id,
            llm_key=llm_key,
            bot_token=bot_token,
            llm_provider=llm_provider,
        )
        log.info(
            "Provisioning complete: user_id=%s agent_id=%s result=%s",
            user_id,
            agent_id,
            result,
        )
    except Exception as exc:
        log.error(
            "Provisioning failed: user_id=%s agent_id=%s error=%s",
            user_id,
            agent_id,
            exc,
            exc_info=True,
        )


# ── DELETE /provision/{user_id}/{agent_id} ────────────────────────────────────
@app.delete("/provision/{user_id}/{agent_id}", status_code=200)
async def deprovision_endpoint(
    user_id: str,
    agent_id: str,
    request: Request,
) -> dict:
    """
    Deprovision a container. Requires same HMAC auth as the provision endpoint.
    Signs over: "{user_id}:{agent_id}:{timestamp}"
    """
    x_timestamp = request.headers.get("X-Timestamp", "")
    x_signature = request.headers.get("X-Signature", "")

    if not x_timestamp or not x_signature:
        raise HTTPException(status_code=401, detail="Missing authentication headers")

    if not _check_timestamp(x_timestamp):
        raise HTTPException(status_code=401, detail="Request timestamp invalid or expired")

    raw_body = await request.body()
    if not _verify_hmac(raw_body, x_timestamp, x_signature, user_id, agent_id):
        log.warning("HMAC validation failed for deprovision: user_id=%s agent_id=%s", user_id, agent_id)
        raise HTTPException(status_code=401, detail="Invalid signature")

    log.info("Deprovision request for user_id=%s agent_id=%s", user_id, agent_id)

    try:
        result = deprovision_container(user_id=user_id, agent_id=agent_id)
        return result
    except Exception as exc:
        log.error("Deprovision failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── GET /instances ─────────────────────────────────────────────────────────────
@app.get("/instances")
async def list_instances() -> dict:
    """List all provisioned containers and their status."""
    return list_containers()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "webhook-receiver:app",
        host="0.0.0.0",
        port=9000,
        log_level="info",
        access_log=True,
    )

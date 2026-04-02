# Phase 1: Infrastructure Baseline - Research

**Researched:** 2026-04-02
**Domain:** FastAPI testing, systemd service management, .env.local patching, Next.js/Supabase dashboard wiring
**Confidence:** HIGH (code read directly, no guessing)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-03 | User hat ein Profil mit Agentenliste im Dashboard | AgentList.tsx already fetches from `user_agents` table but does NOT filter by logged-in user — see gap below |
| INFRA-03 | Webhook Receiver überlebt Server-Neustart (systemctl enable) | One command: `systemctl enable focuscall-webhook` — service unit already exists and works |
| INFRA-04 | Backend hat Tests (provision.py, webhook-receiver.py) | No tests exist; pytest + httpx[asyncio] + pytest-asyncio stack required from scratch |

</phase_requirements>

---

## Summary

The phase has three distinct work streams that are largely independent and can proceed in parallel.

**Stream 1 — INFRA-03 (systemctl enable)** is a single-command fix already known. The `focuscall-webhook` systemd service unit exists and runs; it was never enabled. `systemctl enable focuscall-webhook` makes it start on boot. No code changes needed — only a remote SSH command on the VPS.

**Stream 2 — INFRA-04 (pytest tests)** requires building a test suite from scratch. The codebase has zero tests. `provision.py` uses the Docker SDK and file I/O heavily — all of which must be mocked. `webhook-receiver.py` is a standard FastAPI app — testable via `httpx.AsyncClient` with ASGI transport. The key insight: the health-check loop in `provision_container` uses `time.sleep` and `urllib.request.urlopen`, both of which must be patched to make tests fast and hermetic.

**Stream 3 — AUTH-03 (.env.local + agent list wiring)** has two sub-tasks: (a) patch two env var values in `.env.local`, and (b) verify that `AgentList.tsx` correctly scopes agent queries to the logged-in user. The component currently calls `supabase.from('user_agents').select(...)` without a `.eq('user_id', user.id)` filter — relying entirely on Supabase Row Level Security (RLS). The RLS policy on `user_agents` must be confirmed to exist and be correct for this to be safe.

**Primary recommendation:** Execute stream 1 (30 seconds, SSH command), stream 3a (env patch, 2 minutes), then build tests. Do not skip the RLS verification — a missing RLS policy would expose all users' agents to every logged-in user.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.x | Test runner | Industry standard Python testing |
| httpx | 0.27.x | Async HTTP client for FastAPI tests | Required by FastAPI docs for async test client |
| pytest-asyncio | 0.23.x | Async test support | Required for `async def` test functions |
| unittest.mock | stdlib | Mocking Docker SDK, file I/O, time | Built-in, no extra dep |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | 4.x | Coverage reporting | Optional — add if coverage gate is desired |
| freezegun | 1.x | Freeze `time.time()` in timestamp tests | Use for `_check_timestamp` edge-case tests |

**Installation (on VPS, in the provisioning virtualenv):**
```bash
pip install pytest httpx pytest-asyncio
# Optional:
pip install freezegun
```

**Version verification note:** These versions are based on stable releases as of early 2026. Confirm with `pip install pytest --dry-run` on the VPS before writing lockfile.

---

## Architecture Patterns

### FastAPI Testing Pattern (httpx ASGI transport)

The standard approach for testing FastAPI apps without starting a real server:

```python
# Source: FastAPI official docs — https://fastapi.tiangolo.com/tutorial/testing/
import pytest
from httpx import AsyncClient, ASGITransport

# webhook-receiver.py imports WEBHOOK_SECRET at module load time from os.environ
# So the secret must be set before importing the app module.
import os
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-64chars-placeholder")

from webhook_receiver import app  # import AFTER env is set

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Critical detail:** `webhook-receiver.py` reads `WEBHOOK_SECRET` at module load via `os.environ["WEBHOOK_SECRET"]` (hard fail if missing). The env var MUST be set before the module is imported. Use `os.environ.setdefault(...)` at the top of conftest.py or monkeypatch before import.

### HMAC Signature Construction for Tests

The signature covers `"{user_id}:{agent_id}:{timestamp}"` — confirmed by reading `_verify_hmac()` in the source. Test helpers must construct matching signatures:

```python
import hashlib
import hmac
import time

def make_signature(user_id: str, agent_id: str, secret: str = "test-secret") -> tuple[str, str]:
    ts = str(int(time.time()))
    message = f"{user_id}:{agent_id}:{ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return ts, sig
```

### Mocking Docker SDK in provision.py Tests

`provision_container()` calls `docker.from_env()` and then `.containers.run(...)`. The Docker daemon is not available in CI or during local unit tests. Mock pattern:

```python
from unittest.mock import MagicMock, patch

@patch("provision.docker.from_env")
def test_provision_allocates_port(mock_docker_env, tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("WORKSPACE_BASE", str(tmp_path / "workspaces"))
    monkeypatch.setenv("CONFIG_TEMPLATE_PATH", str(tmp_path / "config.toml.tmpl"))

    # Write a minimal template
    (tmp_path / "config.toml.tmpl").write_text("[agent]\nport = $PORT\n")

    # Mock Docker container object
    mock_container = MagicMock()
    mock_container.id = "abc123def456"
    mock_container.attrs = {
        "NetworkSettings": {"IPAddress": "172.17.0.2", "Networks": {}}
    }
    mock_docker_env.return_value.containers.get.side_effect = docker.errors.NotFound("x")
    mock_docker_env.return_value.containers.run.return_value = mock_container

    # Patch health check to return success immediately
    with patch("provision.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value.status = 200
        with patch("provision.time.sleep"):  # skip sleep
            result = provision_container("user1", "agent1", "llm_key", "bot_token", "openrouter")

    assert result["status"] == "running"
    assert "port" in result
```

### Mocking the Registry (File I/O)

`provision.py` uses `fcntl.flock` for file locking. In tests, use `tmp_path` (pytest fixture) for a real temp directory — this is safer than mocking fcntl itself. The `REGISTRY_PATH` and `WORKSPACE_BASE` env vars allow full redirection without mocking file I/O.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP testing | Custom WSGI test shim | `httpx.AsyncClient` with `ASGITransport` | Handles lifespan, async, streaming correctly |
| Time freezing for timestamp tests | Manual `time.time` monkey-patching | `freezegun.freeze_time` or monkeypatch | Cleaner, handles re-entrancy |
| HMAC construction in tests | Ad-hoc string concat | Reusable fixture function in conftest.py | Single source of truth for test auth |

---

## Common Pitfalls

### Pitfall 1: WEBHOOK_SECRET imported at module level
**What goes wrong:** `webhook-receiver.py` line 35 does `WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]` at module load. If the test file imports the app before setting the env var, the test process crashes with `KeyError`.
**How to avoid:** In `conftest.py`, set `os.environ["WEBHOOK_SECRET"] = "test-..."` before any import of the app. Or use a `pytest.ini` / `pyproject.toml` env setup.
**Warning signs:** `KeyError: 'WEBHOOK_SECRET'` during collection phase, before any test runs.

### Pitfall 2: health-check loop takes 20 seconds in tests
**What goes wrong:** `provision_container` sleeps 2 seconds × 10 attempts = 20 seconds if health checks all fail. Tests hang.
**How to avoid:** Always `patch("provision.time.sleep")` AND `patch("provision.urllib.request.urlopen")` together.

### Pitfall 3: fcntl.flock not available on macOS in certain environments
**What goes wrong:** If tests run locally on macOS developer machine (not on Linux VPS), fcntl works fine. On Windows CI it would fail, but the VPS is Linux — not an issue here. However, parallel test execution with the same registry path causes lock contention.
**How to avoid:** Each test gets its own `tmp_path` for REGISTRY_PATH — never share registry path across tests.

### Pitfall 4: AgentList does not filter by user_id in the query
**What goes wrong:** `AgentList.tsx` queries `user_agents` without `.eq('user_id', user.id)`. If Supabase RLS is not enabled or policy is wrong, every logged-in user sees all agents from all users.
**How to avoid:** Before marking AUTH-03 complete, verify the RLS policy on `user_agents` table in Supabase. The correct policy is: `auth.uid() = user_id`. If absent, add it.
**Warning signs:** After creating a test agent with user A, logging in as user B and seeing user A's agent in the list.

### Pitfall 5: .env.local VPS_WEBHOOK_URL points to non-existent DNS
**What goes wrong:** Current value is `https://vps.focuscall.ai/provision` — DNS does not exist. Any frontend action that calls this URL will fail silently (or with a DNS error) rather than hitting the real VPS.
**How to avoid:** Replace with `http://91.99.209.45:9000/provision`. Note: no HTTPS — the VPS has no TLS cert on port 9000. This is acceptable for local dev; production needs nginx + cert.

### Pitfall 6: systemctl enable must run as root
**What goes wrong:** If SSH session lacks root or sudo, `systemctl enable` fails silently or with permission error.
**How to avoid:** The SSH command is `ssh -i ~/.ssh/openclaw_nopass root@91.99.209.45` — already root. Confirm with `whoami` if unsure.

---

## AUTH-03 Gap Analysis

**Current state (read from code):**

- `dashboard/page.tsx`: Renders `<AgentList />` — already in the dashboard, already behind auth guard (`useAuth` hook redirects to `/login` if no user).
- `AgentList.tsx`: Fetches from `user_agents` table, orders by `created_at`, renders cards with status badges. Functionally complete visually.
- **Missing:** The query has no `user_id` filter. RLS is the only thing preventing cross-user data leakage.

**AUTH-03 is functionally complete IF Supabase RLS is correctly configured.** The "profile with agent list" requirement is met by the dashboard page — it shows the logged-in user's agents via Supabase RLS. No frontend code change is needed for AUTH-03 UNLESS RLS is missing.

**Action required before closing AUTH-03:**
1. Verify RLS is enabled on `user_agents` in Supabase dashboard
2. Verify policy: `FOR SELECT USING (auth.uid() = user_id)`
3. If policy is missing, add it (one SQL statement in Supabase SQL editor)

---

## .env.local Patch Plan

Two keys need updating. All other keys are confirmed correct.

| Key | Current Value | Correct Value | Risk |
|-----|--------------|---------------|------|
| `WEBHOOK_SECRET` | `` (empty) | `c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f` | None — was empty, not broken |
| `VPS_WEBHOOK_URL` | `https://vps.focuscall.ai/provision` | `http://91.99.209.45:9000/provision` | Low — only affects provisioning; that flow is Phase 4 anyway |

**All other keys** (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DEEPSEEK_API_KEY`, `DEEPGRAM_API_KEY`, `SUPABASE_PAT`) are present and correctly set. Do not touch them.

Safe edit approach: Use a targeted line replacement, not a full file rewrite.

---

## INFRA-03: systemctl enable — Exact Steps

```bash
# SSH to VPS
ssh -i ~/.ssh/openclaw_nopass root@91.99.209.45

# Enable the service (survives reboot)
systemctl enable focuscall-webhook

# Verify
systemctl is-enabled focuscall-webhook
# Expected output: "enabled"

# Also confirm current state is still running
systemctl status focuscall-webhook
```

No code changes. No service unit file modifications. The unit file already exists (service was running). `enable` just creates the symlink in `/etc/systemd/system/multi-user.target.wants/`.

---

## Recommended Test File Structure

```
/opt/focuscall/provisioning/
├── provision.py
├── webhook-receiver.py
├── config.toml.tmpl
├── conftest.py            # shared fixtures, env setup
├── test_provision.py      # unit tests for provision.py
└── test_webhook.py        # integration tests for FastAPI endpoints
```

Or locally (preferred for dev):
```
/Users/pwrunltd/ZeroClaw/provisioning/
├── provision.py
├── webhook-receiver.py
├── config.toml.tmpl
├── conftest.py
├── test_provision.py
└── test_webhook.py
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml` or `pytest.ini` — Wave 0 creates this |
| Quick run command | `pytest provisioning/ -x -q` |
| Full suite command | `pytest provisioning/ -v --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-03 | Service enabled after SSH command | manual verification | `ssh ... systemctl is-enabled focuscall-webhook` | N/A — manual |
| INFRA-04 | provision.py core paths green | unit | `pytest provisioning/test_provision.py -x` | Wave 0 |
| INFRA-04 | webhook-receiver.py core paths green | unit | `pytest provisioning/test_webhook.py -x` | Wave 0 |
| AUTH-03 | RLS policy exists on user_agents | manual verification | Supabase SQL editor check | N/A — manual |

### Minimum Test Coverage for INFRA-04

**test_provision.py** — must cover:
- `provision_container` happy path returns `{"status": "running", ...}`
- `provision_container` returns existing instance if already running (idempotency)
- `deprovision_container` removes container, workspace, registry entry
- `list_containers` returns registry contents
- Port allocation increments `next_port`
- Health check failure returns `{"status": "error", ...}`

**test_webhook.py** — must cover:
- `GET /health` returns 200
- `POST /provision` with valid HMAC + timestamp returns 202
- `POST /provision` with missing headers returns 401
- `POST /provision` with expired timestamp returns 401
- `POST /provision` with wrong signature returns 401
- `DELETE /provision/{uid}/{aid}` with valid HMAC returns 200

### Wave 0 Gaps

- [ ] `provisioning/conftest.py` — env setup, shared HMAC fixture, tmp_path registry redirect
- [ ] `provisioning/test_provision.py` — provision.py unit tests
- [ ] `provisioning/test_webhook.py` — FastAPI endpoint tests
- [ ] `provisioning/pyproject.toml` or `pytest.ini` — asyncio_mode = "auto"

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | pytest, provision.py | Assumed — VPS runs it already | Check on VPS | — |
| pytest | INFRA-04 | Not installed yet | — | Install via pip |
| httpx | INFRA-04 | Not installed yet | — | Install via pip |
| pytest-asyncio | INFRA-04 | Not installed yet | — | Install via pip |
| Docker daemon | provision.py integration tests | Available on VPS, mocked in unit tests | v29.3.1 | Mock via unittest.mock |
| systemd | INFRA-03 | Available on VPS (Linux) | — | — |

**Missing dependencies with no fallback:** None — all missing items are installable via pip.

---

## Open Questions

1. **Is RLS enabled on `user_agents` in Supabase?**
   - What we know: AgentList query has no user_id filter — relies entirely on RLS
   - What's unclear: Whether the policy was set up when the table was created
   - Recommendation: First task of execution — verify in Supabase SQL editor before anything else

2. **Does the provisioning virtualenv exist on the VPS?**
   - What we know: The service runs webhook-receiver.py, so a Python env with FastAPI/uvicorn exists
   - What's unclear: Whether it is a venv, system Python, or something else; whether pytest can be installed in it
   - Recommendation: SSH and run `which uvicorn && uvicorn --version` to find the Python env used by the service

3. **Is there a `pytest.ini` / `pyproject.toml` on the VPS or should tests run locally first?**
   - Recommendation: Write tests in the local `ZeroClaw/provisioning/` repo directory first, then sync to VPS with rsync or git push

---

## Sources

### Primary (HIGH confidence)
- Direct code read: `/Users/pwrunltd/ZeroClaw/provisioning/provision.py` — all mock targets identified from actual source
- Direct code read: `/Users/pwrunltd/ZeroClaw/provisioning/webhook-receiver.py` — HMAC logic, env var loading, endpoint structure confirmed
- Direct code read: `/Users/pwrunltd/focuscall-ai-frontend/src/components/dashboard/AgentList.tsx` — confirmed no user_id filter in query
- Direct code read: `/Users/pwrunltd/focuscall-ai-frontend/.env.local` — confirmed exact current state of env vars

### Secondary (MEDIUM confidence)
- FastAPI testing docs pattern (httpx + ASGITransport) — standard pattern confirmed in FastAPI documentation, widely verified
- systemctl enable behavior — standard systemd documented behavior, no ambiguity

### Tertiary (LOW confidence)
- None — all findings are based on direct code inspection

---

## Metadata

**Confidence breakdown:**
- INFRA-03 systemctl fix: HIGH — trivial, one command, confirmed service exists
- INFRA-04 test patterns: HIGH — derived directly from reading the source files being tested
- AUTH-03 gap analysis: HIGH — confirmed by reading AgentList.tsx source; RLS verification is a runtime check
- .env.local patch: HIGH — both current and correct values confirmed from multiple sources

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable stack — no fast-moving dependencies)

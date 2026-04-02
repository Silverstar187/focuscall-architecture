# Architecture

**Analysis Date:** 2026-04-02

## Pattern Overview

**Overall:** Multi-tenant, per-user container isolation architecture (focuscall.ai)

**Key Characteristics:**
- Every user gets a dedicated, isolated Docker container running a ZeroClaw AI daemon — no shared process, no shared state
- Provisioning is triggered by a Supabase Edge Function calling a HMAC-authenticated webhook on the VPS; all provisioning is asynchronous (202 Accepted pattern)
- Credentials (LLM API keys, Telegram bot tokens) are never written to disk — they travel encrypted in Supabase Vault and arrive at the container exclusively as Docker ENV variables
- The system is designed around user-supplied credentials: the platform bears zero LLM infrastructure cost
- A tmux-based multi-agent orchestration system (`_orchestrator/`) runs Claude Code workers for development-time automation (not runtime infrastructure)

---

## Layers

**Frontend (Next.js 15):**
- Purpose: User-facing web dashboard for account management and agent creation
- Location: `/Users/pwrunltd/focuscall-ai-frontend/` (separate repo, not in this directory)
- Contains: Login, dashboard, agent creation form, voice recorder, Supabase Auth integration
- Depends on: Supabase Auth, Supabase DB (`user_agents`, `voice_recordings` tables), DeepSeek API (agent generation), Deepgram API (voice transcription), VPS webhook
- Used by: End users via browser

**Supabase Edge Function (Deno/TypeScript):**
- Purpose: Secure gateway that stores credentials and dispatches provisioning
- Location: `provisioning/edge-function.ts`
- Contains: Vault key storage, HMAC-SHA256 signing, webhook dispatch
- Depends on: Supabase Vault (pgsodium AES-256-GCM), `WEBHOOK_SECRET`, `VPS_WEBHOOK_URL` env vars
- Used by: Frontend (via fetch) when user triggers agent deployment

**VPS Webhook Receiver (Python/FastAPI):**
- Purpose: HMAC-validated HTTP API that receives provisioning commands from Supabase and executes them asynchronously
- Location: `provisioning/webhook-receiver.py`
- Contains: `POST /provision`, `DELETE /provision/{user_id}/{agent_id}`, `GET /instances`, `GET /health` endpoints; timestamp-based replay protection (5-minute window)
- Depends on: `provision.py`, `WEBHOOK_SECRET` env var, Docker socket
- Used by: Supabase Edge Function exclusively
- Runs on: Hetzner CAX21 (`91.99.209.45`), port 9000, via systemd service `focuscall-webhook`

**Provisioner (Python/Docker SDK):**
- Purpose: Creates and destroys ZeroClaw containers; manages port registry and workspaces
- Location: `provisioning/provision.py`
- Contains: `provision_container()`, `deprovision_container()`, `list_containers()`; file-locked registry access via `fcntl`
- Depends on: Docker daemon (via `docker.from_env()`), `config.toml.tmpl`, `/opt/focuscall/registry.json`, `/opt/focuscall/workspaces/`
- Used by: `webhook-receiver.py` (direct Python import, called as BackgroundTask)

**ZeroClaw Container (Rust daemon):**
- Purpose: Per-user AI agent process; handles Telegram message routing, LLM calls, memory persistence
- Location: `provisioning/Dockerfile` (builds from `https://github.com/zeroclaw-labs/zeroclaw` v0.6.7)
- Contains: Telegram webhook listener, LLM API proxy, SQLite memory (`brain.db`), `/health` HTTP endpoint
- Depends on: `ZEROCLAW_API_KEY` and `TELEGRAM_BOT_TOKEN` ENV vars; `/workspace/config.toml` (no secrets); `/workspace/brain.db`
- Resource constraints: 128MB RAM, 0.5 CPU, read-only rootfs, no-new-privileges, cap-drop ALL, tmpfs `/tmp` (10MB)
- Naming: `fc-{user_id}-{agent_id}`

**Infrastructure / IaC:**
- Purpose: Reproducible server provisioning
- Location: `infra/main.tf`, `infra/cloud-init.yml`
- Contains: Terraform Hetzner provider config; firewall rules (SSH/80/443/9000); CAX21 server definition with cloud-init
- Depends on: `hcloud` Terraform provider v~1.49

**Orchestrator (Development tooling):**
- Purpose: Multi-worker Claude Code automation for development tasks
- Location: `_orchestrator/`
- Contains: `orch-bootstrap.sh` (entry point), `spawn-worker.sh` (creates tmux workers), `heartbeat.sh`, `rate-limit-watchdog.sh`, `config.json`
- Not part of runtime infrastructure; used during development for parallel agent-assisted coding

---

## Data Flow

**Provisioning Request Flow:**

1. User fills agent creation form in Next.js frontend at `/dashboard/agents/new`
2. Frontend sends `POST` to `/api/process-voice/route.ts` → DeepSeek generates agent config files (`AGENT_CONTEXT.md`, `SOUL.md`, `config.toml`, system prompt)
3. User confirms, frontend sends `POST` to `VPS_WEBHOOK_URL/provision` (currently direct, eventually via Supabase Edge Function)
4. Edge Function (`edge-function.ts`) stores `llm_key` and `bot_token` in Supabase Vault; signs `{user_id}:{agent_id}:{timestamp}` with HMAC-SHA256
5. Edge Function POSTs signed payload to `http://91.99.209.45:9000/provision` with `X-Timestamp` and `X-Signature` headers
6. Webhook receiver (`webhook-receiver.py`) validates timestamp (±5 min) and HMAC; returns `202 Accepted` immediately
7. Background task calls `provision_container()` in `provision.py`
8. Provisioner acquires `fcntl` lock on `registry.json`, allocates next port (42000+N), creates workspace at `/opt/focuscall/workspaces/{user_id}/{agent_id}/`
9. Renders `config.toml.tmpl` (no secrets) and writes to workspace
10. Calls `docker.containers.run()` with security constraints; keys injected as ENV only
11. Health-check loop: polls `http://{container_ip}:{port}/health` up to 10 times (2s apart)
12. Registry updated to `running` or `error`

**Telegram Message Flow (per running container):**

1. User sends message via Telegram to their bot
2. Telegram calls webhook → ZeroClaw daemon receives message
3. ZeroClaw loads conversation context from `/workspace/brain.db` (SQLite)
4. ZeroClaw calls LLM API (OpenRouter/OpenAI/Anthropic) using `ZEROCLAW_API_KEY`
5. Response sent back to Telegram
6. New context stored in `brain.db`

**Deprovisioning Flow:**

1. `DELETE /provision/{user_id}/{agent_id}` received (HMAC-authenticated)
2. Container `fc-{user_id}-{agent_id}` stopped (10s timeout) and removed
3. Workspace `{WORKSPACE_BASE}/{user_id}/{agent_id}/` deleted (`shutil.rmtree`)
4. Registry entry removed

---

## Key Abstractions

**ZeroClaw Container Instance:**
- Purpose: The unit of isolation — one AI agent persona per container
- Key files: `provisioning/Dockerfile`, `provisioning/config.toml.tmpl`
- Pattern: Container name `fc-{user_id}-{agent_id}`; workspace at `/opt/focuscall/workspaces/{user_id}/{agent_id}/`; port from registry starting at 42000

**Registry (`registry.json`):**
- Purpose: Port allocation ledger and instance state tracker
- Location: `/opt/focuscall/registry.json` on VPS
- Pattern: `{ "next_port": 42000, "instances": { "{user_id}-{agent_id}": { "port", "status", "container_id", "created_at", "container_name" } } }`
- Access: Always via `fcntl.LOCK_EX` file lock in `provisioning/provision.py`

**HMAC Authentication:**
- Purpose: Authenticates all webhook calls between Supabase Edge Function and VPS
- Signature covers: `"{user_id}:{agent_id}:{timestamp}"` (metadata only)
- Headers: `X-Timestamp` (Unix seconds), `X-Signature` (SHA-256 hex)
- Replay protection: Requests older than 300 seconds rejected in `webhook-receiver.py`

**Workspace:**
- Purpose: Per-agent filesystem mount inside the container
- Structure: `/workspace/config.toml` (no secrets), `/workspace/brain.db` (SQLite memory), `/workspace/db/` (SurrealDB, Phase 2), `/workspace/logs/`, `/workspace/files/`
- Access: Container has `rw` mount; rootfs is read-only; only `/workspace` and `/tmp` are writable

---

## Entry Points

**Supabase Edge Function:**
- Location: `provisioning/edge-function.ts`
- Triggers: HTTP POST from frontend (or Supabase DB webhook)
- Responsibilities: Vault storage, HMAC signing, webhook dispatch to VPS

**FastAPI Webhook Receiver:**
- Location: `provisioning/webhook-receiver.py`
- Triggers: HTTP POST/DELETE from Supabase Edge Function; runs as systemd service `focuscall-webhook`
- Responsibilities: HMAC validation, replay protection, async provisioning dispatch

**ZeroClaw Daemon:**
- Location: Container entrypoint `zeroclaw daemon` (from `provisioning/Dockerfile`)
- Triggers: Container start via `docker.containers.run()` in `provision.py`
- Responsibilities: Telegram polling, LLM calls, memory management, health endpoint

**Terraform / cloud-init:**
- Location: `infra/main.tf`, `infra/cloud-init.yml`
- Triggers: Manual `terraform apply`
- Responsibilities: Hetzner CAX21 server creation, firewall, initial server configuration

---

## Error Handling

**Strategy:** Fail fast at validation boundaries; async operations log errors without blocking callers.

**Patterns:**
- `webhook-receiver.py`: HTTP 401 for missing/invalid HMAC or expired timestamps; HTTP 400 for malformed JSON; HTTP 500 for internal errors. Provisioning errors are logged but do not bubble to the HTTP caller (202 already returned).
- `provision.py`: Container startup failure triggers cleanup (stop + remove container); registry status set to `"error"` with error message; `RuntimeError` raised for callers. File lock released in `finally` blocks.
- `edge-function.ts`: Vault errors return HTTP 500 before webhook is sent; webhook delivery failures return HTTP 502.
- ZeroClaw containers: Health check loop (10 attempts × 2s). If health check times out, container is stopped and removed and registry status is `"error"`.

---

## Cross-Cutting Concerns

**Logging:** Python `logging` module (standard library) in `provision.py` and `webhook-receiver.py`; structured ISO timestamp format. ZeroClaw writes to `/workspace/logs/zeroclaw.log`. Infrastructure logs via `docker logs fc-{user_id}-{agent_id}`.

**Validation:** Request validation via Pydantic `BaseModel` (`ProvisionRequest`, `ProvisionResponse`) in `webhook-receiver.py`. Config template variables validated at render time by `string.Template.substitute()`.

**Authentication:** All VPS endpoints require HMAC-SHA256 with shared `WEBHOOK_SECRET` and timestamp freshness check. Keys are injected into containers as Docker ENV vars only — never written to disk anywhere in the provisioning chain.

**Concurrency:** Registry writes are protected by POSIX file lock (`fcntl.LOCK_EX` on `registry.json.lock`). Atomic registry updates use write-to-temp-then-rename pattern.

**Secret Management:** `WEBHOOK_SECRET` in systemd service env; `ZEROCLAW_API_KEY` and `TELEGRAM_BOT_TOKEN` as Docker ENV vars per container; backup copies in Supabase Vault (pgsodium AES-256-GCM) keyed as `llm_key_{user_id}_{agent_id}` and `bot_token_{user_id}_{agent_id}`.

---

## Phase Roadmap (as of 2026-04-02)

| Phase | Status | Focus |
|-------|--------|-------|
| 0 | Done | Foundation & Design |
| 1 | Active | Provisioning Core |
| 2 | Planned | Security Hardening |
| 3 | Planned | Knowledge Graph (SurrealDB per tenant) |
| 4 | Planned | Multi-Agent A2A Communication |
| 5 | Planned | Scale & Monitoring |

---

*Architecture analysis: 2026-04-02*

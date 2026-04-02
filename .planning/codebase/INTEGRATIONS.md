# External Integrations

**Analysis Date:** 2026-04-02

## APIs & External Services

**Messaging:**
- Telegram Bot API — primary user-facing channel; each user supplies their own bot token
  - SDK/Client: ZeroClaw built-in channel adapter
  - Auth: `TELEGRAM_BOT_TOKEN` env var injected into each Docker container at provision time
  - Quota: none on platform side — users own their bot tokens
  - Future: WhatsApp Business API, Discord, Slack (ZeroClaw supports 17+ channel adapters)

**LLM Providers (user-supplied — platform bears no cost):**
- OpenRouter — default/primary LLM gateway; users supply their own API key
- OpenAI — direct provider option; `openai/gpt-4o-mini` default model in config template
- Anthropic — direct provider option
- Ollama — local LLM option
- Auth: `ZEROCLAW_API_KEY` env var injected into each Docker container
- Config: `default_provider` field in `provisioning/config.toml.tmpl`

**AI (platform-owned — frontend generation):**
- DeepSeek API — generates agent configuration files (AGENT_CONTEXT.md, SOUL.md, config.toml, system prompt) from user voice/text descriptions
  - SDK/Client: called from Next.js API route `src/app/api/process-voice/route.ts`
  - Auth: `DEEPSEEK_API_KEY` in `.env.local`

**Voice Processing:**
- Deepgram — speech-to-text transcription for the voice agent creation flow in the frontend
  - SDK/Client: called from Next.js API route `src/app/api/process-voice/route.ts`
  - Auth: `DEEPGRAM_API_KEY` in `.env.local`

## Data Storage

**Databases:**
- Supabase (PostgreSQL) — user authentication, user data, agent metadata
  - Hosted project ID: `ahdzxabztewqqdajjtsn`
  - Tables deployed: `user_agents`, `voice_recordings`
  - Client: `@supabase/supabase-js@2` (frontend + edge function)
  - Auth: `NEXT_PUBLIC_SUPABASE_ANON_KEY` (client-side), `SUPABASE_SERVICE_ROLE_KEY` (server-side)
  - Row-Level Security enabled

- SurrealDB (embedded, per-container) — per-user knowledge graph, conversation persistence, session state
  - Version: 3.0+
  - Mode: embedded within each ZeroClaw container (no separate server process)
  - Location: `/workspace/db/` inside each container (bind-mounted from `/opt/focuscall/workspaces/{user_id}/{agent_id}/db/`)
  - Not externally accessible

- SQLite (session cache) — in-memory session persistence within ZeroClaw daemon
  - Managed automatically by ZeroClaw; stored in `/workspace/db/`
  - Referenced in STATUS.md: "Gateway session persistence enabled (SQLite)"

**File Storage:**
- Host filesystem — workspace data at `/opt/focuscall/workspaces/{user_id}/{agent_id}/` on the Hetzner VPS
  - Contains: `config.toml`, `db/`, `logs/`
  - No external object storage currently; Hetzner Volume planned for Phase 2 (300+ users)

**Registry:**
- `/opt/focuscall/registry.json` — port allocation and instance state tracking (JSON flat file with fcntl locking)
  - Managed by `provisioning/provision.py`
  - Not a database — flat file with concurrent access protection via lock file

**Caching:**
- None — no Redis, Memcached, or other caching layer

## Authentication & Identity

**Auth Provider:**
- Supabase Auth — email/password + (planned) Google OAuth
  - Implementation: JWT-based, handled by Supabase Auth service
  - Supabase project: `ahdzxabztewqqdajjtsn`
  - Google OAuth client ID: configured in `.env.local` as `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (currently empty — not yet active)

**Webhook Auth:**
- HMAC-SHA256 — used to authenticate provisioning webhooks between Supabase Edge Function and VPS receiver
  - Signing message format: `{user_id}:{agent_id}:{unix_timestamp}`
  - Replay protection: 5-minute timestamp window
  - Shared secret: `WEBHOOK_SECRET` env var (32-byte hex string)
  - Implementation: `provisioning/edge-function.ts` (signing) and `provisioning/webhook-receiver.py` (verification)

**Supabase Vault:**
- pgsodium AES-256-GCM encrypted secret storage
  - Stores: `llm_key_{user_id}_{agent_id}` and `bot_token_{user_id}_{agent_id}` per agent
  - Access: via `vault_create_secret` RPC in `provisioning/edge-function.ts`
  - Note: Vault IDs are stored but keys are passed directly to Docker ENV in transit (not retrieved from Vault for provisioning)

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Bugsnag, or similar service

**Logs:**
- Python webhook receiver: JSON-formatted logs via Python `logging` module, output to systemd journal; docker-compose mode: `json-file` driver, 10 MB max, 5 files rotation
- ZeroClaw per-container: log files at `/workspace/logs/` (rotated, max 50 MB per `config.toml.tmpl`)
- nginx: standard access/error logs

**Metrics:**
- ZeroClaw exposes `GET /metrics` (Prometheus-compatible) on its gateway port — not currently scraped
- No Prometheus/Grafana stack deployed

## CI/CD & Deployment

**Hosting:**
- Hetzner Cloud CAX21 (ARM64, 4 vCPU, 8 GB RAM, 80 GB NVMe)
  - Region: fsn1 (Falkenstein, Germany)
  - IP: `91.99.209.45`
  - OS: Ubuntu 24.04 LTS
  - SSH alias: `ssh focuscall`

**IaC:**
- Terraform >= 1.5 with `hetznercloud/hcloud` provider `~> 1.49`
  - Resources: `hcloud_server` (cax21), `hcloud_firewall`, `hcloud_ssh_key`
  - Config: `infra/main.tf`, `infra/variables.tf`, `infra/terraform.tfvars.example`
  - Cloud-init bootstrap: `infra/cloud-init.yml`

**CI Pipeline:**
- None — no GitHub Actions, GitLab CI, or other pipeline configured

**Service Management (production):**
- systemd service: `focuscall-webhook.service` — runs webhook receiver
  - Status: running but not yet `systemctl enable`d (survives manual starts, not reboots)
  - Service file written by `infra/cloud-init.yml`

**Edge Function Deployment:**
- Supabase CLI: `supabase functions deploy provision-agent`
- Function source: `provisioning/edge-function.ts`
- Status: not yet deployed (as of 2026-04-02)

## Webhooks & Callbacks

**Incoming (VPS receives):**
- `POST /provision` — HMAC-signed provisioning request from Supabase Edge Function; creates ZeroClaw container
- `DELETE /provision/{user_id}/{agent_id}` — HMAC-signed deprovision request; stops and removes container
- `GET /instances` — internal: list all provisioned containers
- `GET /health` — health check
- All endpoints handled by `provisioning/webhook-receiver.py` on port 9000

**Outgoing (Supabase Edge Function sends):**
- `POST {VPS_WEBHOOK_URL}/provision` — triggered by frontend agent creation flow
  - Target: `http://91.99.209.45:9000/provision` (direct IP, no DNS yet)
  - Headers: `X-Timestamp`, `X-Signature` (HMAC-SHA256)

**Telegram webhooks:**
- ZeroClaw polls Telegram Bot API directly (long-polling mode, not webhook push)
  - No public webhook endpoint needed per container

## Environment Configuration

**Required env vars (VPS — `/opt/focuscall/provisioning/.env`):**
- `WEBHOOK_SECRET` — HMAC shared secret (32-byte hex)
- `REGISTRY_PATH` — default: `/opt/focuscall/registry.json`
- `WORKSPACE_BASE` — default: `/opt/focuscall/workspaces`
- `CONFIG_TEMPLATE_PATH` — default: `/opt/focuscall/provisioning/config.toml.tmpl`

**Required env vars (Supabase Edge Function — via `supabase secrets set`):**
- `VPS_WEBHOOK_URL` — VPS webhook receiver URL (e.g., `http://91.99.209.45:9000`)
- `WEBHOOK_SECRET` — must match VPS value
- `SUPABASE_URL` — auto-injected by Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — auto-injected by Supabase

**Required env vars (Frontend — `.env.local`):**
- `NEXT_PUBLIC_SUPABASE_URL` — Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key
- `DEEPSEEK_API_KEY` — DeepSeek API key for agent generation
- `DEEPGRAM_API_KEY` — Deepgram API key for voice transcription
- `WEBHOOK_SECRET` — for signing provision requests (currently empty — bug)
- `VPS_WEBHOOK_URL` — currently set to wrong value; correct: `http://91.99.209.45:9000`
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID` — Google OAuth (not yet configured)
- `SUPABASE_PAT` — Supabase personal access token

**Secrets location:**
- VPS: `/opt/focuscall/provisioning/.env` (chmod 600, written by cloud-init)
- Frontend: `/Users/pwrunltd/focuscall-ai-frontend/.env.local` (local dev only)
- Supabase Vault: encrypted storage for per-agent LLM keys and bot tokens (AES-256-GCM via pgsodium)
- Keys never written to disk on VPS — passed as Docker ENV vars only

---

*Integration audit: 2026-04-02*

# Technology Stack

**Analysis Date:** 2026-04-02

## Languages

**Primary:**
- Rust (stable, 1.88) — ZeroClaw AI agent runtime binary; compiled via multi-stage Docker build in `provisioning/Dockerfile`
- Python 3.11 — VPS webhook receiver and Docker provisioning logic; `provisioning/webhook-receiver.py`, `provisioning/provision.py`
- TypeScript (Deno) — Supabase Edge Function for provisioning triggers; `provisioning/edge-function.ts`

**Secondary:**
- TOML — ZeroClaw agent configuration format; `provisioning/config.toml.tmpl`
- Turtle/RDF (.ttl) — Ontology layer for domain knowledge models (productivity, health, finance concepts); referenced in `architecture/06-tech-stack-and-capacity.md`
- HCL (Terraform) — Infrastructure as code; `infra/main.tf`, `infra/variables.tf`
- YAML — cloud-init server bootstrap; `infra/cloud-init.yml`

## Runtime

**ZeroClaw (Rust binary):**
- Version: 0.6.7 (b0xtch fork)
- Source: `https://github.com/zeroclaw-labs/zeroclaw`
- Async runtime: Tokio
- Binary size: 8.8 MB (stripped)
- Memory at idle: ~3–5 MB per instance
- Memory under load: ~10–20 MB per instance

**Python (webhook receiver):**
- Version: 3.11
- Runtime environment: Python venv at `/opt/focuscall/provisioning/venv` (production) or `python:3.11-slim` Docker image (docker-compose mode)

**Deno (Edge Function):**
- Version: built-in Supabase runtime (targets Deno std@0.208.0)
- Hosts: Supabase Edge Functions platform (serverless, no self-hosted runtime)

**Node.js / Next.js (frontend):**
- Next.js 15 — Frontend at `/Users/pwrunltd/focuscall-ai-frontend/` (separate repo, not in this directory)

## Package Manager

**Python:**
- pip (via venv)
- Lockfile: not present in repo (deps installed at container startup via docker-compose command)
- Python deps: `fastapi`, `uvicorn[standard]`, `docker`, `filelock`, `pydantic`

**Rust:**
- Cargo (bundled with rust:1.88 toolchain)
- Lockfile: managed upstream in `zeroclaw-labs/zeroclaw` repo (cloned at build time)

**Deno (Edge Function):**
- No package.json — imports via URL (`https://deno.land/std@0.208.0/`, `https://esm.sh/@supabase/supabase-js@2`)

## Frameworks

**Core (VPS backend):**
- FastAPI — async HTTP framework for webhook receiver; `provisioning/webhook-receiver.py`
- Uvicorn — ASGI server running FastAPI on port 9000
- Pydantic v2 — request/response validation in `webhook-receiver.py`

**Container Management:**
- Docker SDK for Python (`docker` package) — used in `provisioning/provision.py` to create/stop/remove containers
- Docker Compose v2 (`docker-compose-v2`) — runs the webhook receiver infrastructure via `provisioning/docker-compose.infra.yml`

**Frontend (separate repo):**
- Next.js 15 + shadcn/ui + Tailwind CSS — at `/Users/pwrunltd/focuscall-ai-frontend/`

**Build/Dev:**
- Cargo — Rust build system for ZeroClaw (inside Docker builder stage)
- Docker multi-stage build — `rust:1.88-bookworm` builder → `debian:bookworm-slim` runtime
- Terraform >= 1.5 — infrastructure provisioning; `infra/main.tf`

## Key Dependencies

**Critical (Python):**
- `fastapi` — HTTP API framework for webhook receiver
- `uvicorn[standard]` — production ASGI server
- `docker` (Docker SDK for Python) — container lifecycle management in `provision.py`
- `pydantic` — request model validation

**Critical (Deno Edge Function):**
- `@supabase/supabase-js@2` — Supabase client for Vault RPC calls; imported via `https://esm.sh/`
- `deno.land/std@0.208.0/http/server.ts` — Deno HTTP server

**Infrastructure:**
- `hetznercloud/hcloud` Terraform provider `~> 1.49` — Hetzner Cloud resource management

## Configuration

**Environment (VPS):**
- Loaded from `/opt/focuscall/provisioning/.env` via systemd `EnvironmentFile`
- Key vars: `WEBHOOK_SECRET`, `REGISTRY_PATH`, `WORKSPACE_BASE`, `CONFIG_TEMPLATE_PATH`

**Environment (Edge Function):**
- Set via `supabase secrets set`
- Key vars: `SUPABASE_URL` (auto-injected), `SUPABASE_SERVICE_ROLE_KEY` (auto-injected), `VPS_WEBHOOK_URL`, `WEBHOOK_SECRET`

**Environment (Frontend):**
- `.env.local` at `/Users/pwrunltd/focuscall-ai-frontend/.env.local`
- Key vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DEEPSEEK_API_KEY`, `DEEPGRAM_API_KEY`, `WEBHOOK_SECRET`, `VPS_WEBHOOK_URL`

**ZeroClaw per-container:**
- Config rendered from template `provisioning/config.toml.tmpl` via Python string.Template substitution
- Written to `/opt/focuscall/workspaces/{user_id}/{agent_id}/config.toml` (no secrets)
- Secrets injected as Docker ENV vars: `ZEROCLAW_API_KEY`, `TELEGRAM_BOT_TOKEN`

**Build:**
- `provisioning/Dockerfile` — multi-stage Rust build
- `provisioning/docker-compose.infra.yml` — webhook receiver service
- `infra/main.tf` + `infra/variables.tf` + `infra/terraform.tfvars.example` — IaC

## Platform Requirements

**Development:**
- Docker with buildx (for ARM64 cross-compile if building on x86_64)
- Python 3.11+ with pip
- Supabase CLI (for Edge Function deployment: `supabase functions deploy`)
- Terraform >= 1.5 (for infra provisioning)

**Production:**
- Hetzner CAX21 (ARM64, 4 vCPU, 8 GB RAM, 80 GB NVMe, Ubuntu 24.04 LTS)
- Docker v29.3.1 (confirmed running on server)
- nginx 1.25+ (reverse proxy, TLS termination)
- systemd (service manager for `focuscall-webhook.service`)
- Supabase (hosted, project ID: `ahdzxabztewqqdajjtsn`)

---

*Stack analysis: 2026-04-02*

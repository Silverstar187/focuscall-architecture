# Codebase Concerns

**Analysis Date:** 2026-04-02

---

## Tech Debt

**Webhook receiver runs as a raw systemd service, not via docker-compose:**
- Issue: `focuscall-webhook` systemd service was manually configured on the server and is not yet enabled for auto-restart on reboot. `docker-compose.infra.yml` exists but is apparently not in use on the running server.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/docker-compose.infra.yml`, `RESUME.md` line 9
- Impact: After any server reboot the webhook receiver goes offline and provisioning stops entirely.
- Fix approach: Run `systemctl enable focuscall-webhook` immediately; long-term, migrate to `docker compose up -d` using `docker-compose.infra.yml` so the receiver is also containerized.

**pip install at container startup instead of a built image:**
- Issue: `docker-compose.infra.yml` installs FastAPI, uvicorn, docker, filelock, pydantic via `pip install` on every `docker compose up`. A comment in the file acknowledges this: "In production: build a Dockerfile.webhook instead for faster startup."
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/docker-compose.infra.yml` line 24
- Impact: Cold starts are slow; any PyPI outage breaks deployment; version pinning is absent.
- Fix approach: Create a `Dockerfile.webhook` that pre-installs dependencies and produces a pinned, reproducible image.

**Port registry is a flat JSON file with fcntl locking — no upper bound check:**
- Issue: `registry.json` increments `next_port` from 42000 with no ceiling. If many containers are provisioned and deprovisioned, ports are never recycled; the counter grows unbounded.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/provision.py` lines 118-119
- Impact: Eventually port exhaustion, or port numbers exceeding OS limits (65535).
- Fix approach: Add a port-reuse mechanism: collect freed ports on deprovision into a `free_ports` list and allocate from there before incrementing `next_port`.

**`read_only=True` flag conflicts with ZeroClaw's write requirements:**
- Issue: `provision.py` sets `read_only=True` on containers, but `STATUS.md` records that this was previously disabled because ZeroClaw needs write access. The current code re-enables it with a `/tmp` tmpfs mount, but the workspace chmod 777 workaround documented in `STATUS.md` may still be required.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/provision.py` line 188, `STATUS.md` lines 24-26
- Impact: Containers may fail silently if ZeroClaw attempts writes that are not covered by the `/workspace` volume or `/tmp` tmpfs.
- Fix approach: Validate that ZeroClaw only writes to `/workspace` and `/tmp`; if additional paths are needed, add targeted tmpfs mounts rather than dropping `read_only`.

**Terraform IaC exists but has never been applied:**
- Issue: `/Users/pwrunltd/ZeroClaw/infra/main.tf` is present but the server at `91.99.209.45` was provisioned manually. The Terraform state does not exist. `RESUME.md` and `STATUS.md` list Terraform as a future step.
- Files: `/Users/pwrunltd/ZeroClaw/infra/main.tf`, `/Users/pwrunltd/ZeroClaw/infra/cloud-init.yml`
- Impact: The server cannot be reproduced deterministically; manual drift is invisible to version control.
- Fix approach: Run `terraform import` against the existing Hetzner server or reprovision via `terraform apply` after verifying `terraform.tfvars`.

---

## Known Bugs / Broken State

**WEBHOOK_SECRET missing from frontend `.env.local`:**
- Symptoms: Any deploy action from the Next.js frontend that calls the webhook will fail with a 401 from the receiver (no secret header sent).
- Files: `RESUME.md` line 33 and lines 127-129 (`.env.local` section)
- Trigger: Clicking the Deploy button in `AgentConfigForm.tsx`
- Workaround: Manually add `WEBHOOK_SECRET=c9109218...` to `/Users/pwrunltd/focuscall-ai-frontend/.env.local`

**VPS_WEBHOOK_URL points to a non-existent DNS name:**
- Symptoms: Webhook calls from the frontend time out because `https://vps.focuscall.ai/provision` has no DNS record.
- Files: `RESUME.md` line 64
- Trigger: Any provisioning attempt from the frontend
- Workaround: Set `VPS_WEBHOOK_URL=http://91.99.209.45:9000` in `.env.local`

**Deploy button calls a Supabase Edge Function that is not deployed:**
- Symptoms: Clicking Deploy in `AgentConfigForm.tsx` returns a 404 or connection error from Supabase.
- Files: `RESUME.md` line 65; `/Users/pwrunltd/ZeroClaw/provisioning/edge-function.ts` (not yet deployed)
- Trigger: Deploy button click from `/dashboard/agents/new`
- Workaround: Reroute the button to call `VPS_WEBHOOK_URL` directly via a Next.js server-side API route, bypassing the Edge Function.

**OpenRouter warmup fails non-fatally on every container start:**
- Symptoms: Container logs show a warmup error on startup. The container continues, but if the user's OpenRouter key is expired the agent silently cannot process LLM requests.
- Files: `STATUS.md` line 31
- Trigger: Container starts with a stale or placeholder `ZEROCLAW_API_KEY`
- Workaround: User must supply a valid key at provision time.

---

## Security Considerations

**Port 9000 open to the entire internet in Terraform firewall:**
- Risk: Any actor can send raw HTTP requests to `http://91.99.209.45:9000/provision`. HMAC protects against unauthorized provisioning, but the surface is wider than necessary.
- Files: `/Users/pwrunltd/ZeroClaw/infra/main.tf` lines 49-55 — comment reads "später einschränken"
- Current mitigation: HMAC-SHA256 signature + 5-minute replay window.
- Recommendations: Restrict port 9000 to Supabase IP ranges (published in their docs) or route exclusively through nginx with IP allowlisting.

**WEBHOOK_SECRET value is hardcoded in plaintext in RESUME.md:**
- Risk: The full 64-character hex secret (`c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f`) appears verbatim in `RESUME.md` which is committed to the git repository.
- Files: `RESUME.md` line 12 and line 128
- Current mitigation: Repository is private.
- Recommendations: Rotate the secret immediately; never commit secrets to documentation files. Store the value only in `.env.local` and the server's systemd environment file.

**`hmac.new()` is not the correct Python API — should be `hmac.new()` → actually `hmac.new` does not exist; correct call is `hmac.new` from the `hmac` module:**
- Risk: The HMAC construction in `webhook-receiver.py` line 53 uses `hmac.new(...)`. Python's `hmac` module exposes `hmac.new()` which is valid, but the import at the top of the file is `import hmac` — this is correct and functional. However, if someone refactors imports this could silently break signature validation, leaving the endpoint unprotected.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/webhook-receiver.py` line 53
- Current mitigation: Constant-time `hmac.compare_digest` is used correctly.
- Recommendations: Add an integration test that verifies a bad signature returns 401.

**Docker socket mounted in webhook-receiver container:**
- Risk: `/var/run/docker.sock` is mounted into the webhook-receiver container (`docker-compose.infra.yml` line 34). Any code execution inside the receiver container has full Docker daemon access, which is equivalent to root on the host.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/docker-compose.infra.yml` line 34
- Current mitigation: The receiver container is not publicly reachable on its own; HMAC auth guards the API.
- Recommendations: Use Docker's socket proxy (e.g., `tecnativa/docker-socket-proxy`) to expose only the subset of Docker API calls required (`containers.create`, `containers.start`, etc.).

**Telegram Bot Tokens and LLM keys pass through the Edge Function payload in plaintext over HTTPS:**
- Risk: The Edge Function stores keys in Supabase Vault but also forwards them in plaintext in the webhook JSON body to the VPS. If TLS is terminated at the wrong layer or logging captures the request body, keys are exposed.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/edge-function.ts` lines 163-170
- Current mitigation: Comment acknowledges "secured in transit by HTTPS+HMAC"; keys are never written to disk on VPS.
- Recommendations: Long-term, retrieve keys from Vault on the VPS side using the vault IDs already passed in `llm_key_vault_id` / `bot_token_vault_id`, eliminating plaintext key transit entirely.

---

## Performance Bottlenecks

**Health-check loop blocks the entire provisioning request for up to 20 seconds:**
- Problem: `provision.py` polls `/health` with 10 attempts × 2s sleep = up to 20 seconds of synchronous blocking inside the background task.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/provision.py` lines 224-235
- Cause: `time.sleep()` inside a FastAPI `BackgroundTasks` coroutine runs on the main thread pool.
- Improvement path: Convert the health-check loop to `asyncio.sleep` with an `async` background task, or move provisioning to a worker process (Celery, RQ) so the event loop is not stalled.

**ZeroClaw Docker image is built from source on every fresh server:**
- Problem: `docker build` clones the repo and runs `cargo build --release`, which takes 5–15 minutes on a CAX21.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/Dockerfile`, `/Users/pwrunltd/ZeroClaw/infra/cloud-init.yml`
- Cause: No pre-built image is pushed to a registry.
- Improvement path: Push `zeroclaw:latest` to GitHub Container Registry (GHCR) or Docker Hub after a successful build; pull from registry instead of building on the server.

---

## Fragile Areas

**`registry.json` is the single source of truth for all container state:**
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/provision.py` lines 48-79
- Why fragile: The file lives at `/opt/focuscall/registry.json` on the host. If the file is deleted, corrupted, or the host disk fills up, all provisioned container metadata is lost — there is no reconciliation with actual running Docker containers.
- Safe modification: Always use `_open_registry_lock()` before reading or writing. After any manual edit, validate JSON syntax before saving.
- Test coverage: No automated tests for the registry lock/unlock cycle or concurrent access.

**Agent file generation is incomplete — only the system prompt is produced:**
- Files: Referenced in `RESUME.md` lines 52-58: `/Users/pwrunltd/focuscall-ai-frontend/src/app/api/process-voice/route.ts` and `AgentConfigForm.tsx`
- Why fragile: The provisioning flow expects each container workspace to contain `AGENT_CONTEXT.md`, `AGENT_QUICKREF.md`, `SOUL.md`, and `config.toml`, but the DeepSeek generation step currently only produces a system prompt. Containers start without these files.
- Safe modification: Expand the DeepSeek prompt in `route.ts` before touching the provisioning layer.
- Test coverage: None.

**`focuscall-webhook` systemd service survives no reboots:**
- Files: `RESUME.md` line 9 — service is `disabled`
- Why fragile: A kernel panic, OOM event, or routine maintenance reboot silently takes down the entire provisioning API with no alert.
- Safe modification: `systemctl enable focuscall-webhook` before any production traffic.
- Test coverage: None.

---

## Scaling Limits

**Single Hetzner CAX21 server with 8GB RAM:**
- Current capacity: 1 server, ~60 containers at 128MB RAM each (leaving headroom for the OS and receiver).
- Limit: ~60 concurrent agents before OOM; no horizontal scaling path defined.
- Scaling path: Phase 5 ("Scale & Monitoring") in `README.md` roadmap is listed as pending. Requires a multi-server registry or an orchestrator (Nomad, k3s) rather than a flat JSON registry.

**Port registry increments from 42000 with no recycling:**
- Current capacity: Up to 23535 unique ports (42000–65535) before exhaustion.
- Limit: Fragile if containers are frequently deprovisioned and reprovisioned without reuse.
- Scaling path: Implement a free-port pool in `provision.py` (see Tech Debt section above).

---

## Missing Critical Features

**No callback or status webhook after async provisioning completes:**
- Problem: `POST /provision` returns 202 immediately, but the frontend has no way to know when the container is actually running or if it failed.
- Blocks: The UI cannot show a real "Agent is live" status without polling `/status/{user_id}` or implementing a callback.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/webhook-receiver.py` lines 119-183

**No admin dashboard or monitoring:**
- Problem: The only way to inspect running containers is `GET /instances`, which returns raw JSON. There is no alerting for failed health checks, OOM kills, or unexpected container exits.
- Files: `AGENT_CONTEXT.md` line 178 — "Human Operator: Via Admin Dashboard (geplant)"
- Blocks: Operators cannot detect silent failures in production.

**A2A (Agent-to-Agent) communication not implemented:**
- Problem: Multi-agent context described in `architecture/04-multi-agent-personalities.md` and `AGENT_CONTEXT.md` requires an A2A protocol. No code exists for it.
- Blocks: Users with multiple agents (health + productivity + finance) cannot have those agents coordinate.
- Files: Referenced as "Phase 2+" throughout `AGENT_CONTEXT.md`.

**Google OAuth not configured:**
- Problem: `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is empty in `.env.local`. The login page has a Google OAuth button that will fail at runtime.
- Files: `RESUME.md` line 35

**Knowledge Graph (SurrealDB) not implemented:**
- Problem: `architecture/03-knowledge-graph.md` defines the schema; `AGENT_CONTEXT.md` lists SurrealDB as the Phase 2 knowledge store. No integration code exists.
- Blocks: Long-term memory beyond SQLite `brain.db`, cross-session entity relationships.

**Nginx not configured on the server:**
- Problem: Port 9000 is exposed directly; there is no TLS termination, domain routing, or rate limiting at the edge.
- Files: `STATUS.md` step 4 (Terraform), `RESUME.md` step 8 ("Nginx + Domain")
- Blocks: Production HTTPS for `vps.focuscall.ai`.

**Supabase Edge Function not deployed:**
- Problem: `provisioning/edge-function.ts` is written but not deployed. The intended flow (Frontend → Edge Function → VPS) is broken.
- Files: `/Users/pwrunltd/ZeroClaw/provisioning/edge-function.ts`
- Blocks: The secure Vault-based provisioning path; currently any provisioning must bypass the Edge Function.

---

## Test Coverage Gaps

**No tests of any kind exist in this repository:**
- What's not tested: HMAC validation logic, registry locking under concurrency, container lifecycle (provision/deprovision), config template rendering, timestamp replay rejection.
- Files: Entire `/Users/pwrunltd/ZeroClaw/provisioning/` directory
- Risk: Any refactor of `provision.py` or `webhook-receiver.py` can silently break security guarantees.
- Priority: High — the HMAC path is the only security boundary; a bug there means unauthenticated provisioning.

**Frontend has no tests:**
- What's not tested: `AgentConfigForm.tsx`, `VoiceRecorder.tsx`, `/api/process-voice/route.ts`
- Files: `/Users/pwrunltd/focuscall-ai-frontend/` (external to this repo)
- Risk: Mobile layout breakage (known issue, `RESUME.md` line 51) will not be caught before deploy.
- Priority: Medium.

---

*Concerns audit: 2026-04-02*

# Roadmap: focuscall.ai

## Overview

Brownfield MVP completion: the infrastructure and auth foundation already exist. What remains is fixing broken
pieces (ENV vars, DeepSeek 5-file output, missing Supabase saves), completing the agent configuration UI,
wiring credentials securely into Supabase Vault, hooking the deploy button to a real server-side VPS route,
and delivering a polished mobile-responsive dashboard. The milestone ends when a non-technical user can go
from login to a live, responding Telegram bot in under 5 minutes.

## Phases

- [ ] **Phase 1: Infrastructure Baseline** - Fix ENV vars, enable systemd persistence, backend tests, complete agent list profile
- [ ] **Phase 2: AI Generation Pipeline** - Fix DeepSeek 5-file output, save generated files to Supabase, complete voice flow
- [ ] **Phase 3: Credentials & Vault** - Telegram token + LLM key input, encrypted storage in Supabase Vault
- [ ] **Phase 4: Provisioning Integration** - Deploy button via Next.js server-side route, container starts, bot answers
- [ ] **Phase 5: Dashboard & Mobile Polish** - Agent status/start/stop, fully responsive layout on all screens

## Phase Details

### Phase 1: Infrastructure Baseline
**Goal**: Backend is stable, testable, and server-reboot-safe; agent list visible in dashboard
**Depends on**: Nothing (existing infrastructure is live)
**Requirements**: AUTH-03, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. Server reboot does not kill the webhook receiver — it restarts automatically via systemctl
  2. Running `pytest` against `provision.py` and `webhook-receiver.py` returns green (core paths covered)
  3. `.env.local` contains correct `WEBHOOK_SECRET` and `VPS_WEBHOOK_URL` values — no placeholder strings
  4. Logged-in user sees their agent list on the dashboard profile page
**Plans:** 2 plans
Plans:
- [ ] 01-01-PLAN.md — Fix .env.local, enable systemd persistence, verify Supabase RLS
- [x] 01-02-PLAN.md — Create pytest test suite for provision.py and webhook-receiver.py

### Phase 2: AI Generation Pipeline
**Goal**: User describes an agent (text or voice) and gets all 5 ZeroClaw config files generated and saved
**Depends on**: Phase 1
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04
**Success Criteria** (what must be TRUE):
  1. Submitting a text description produces all 5 files (AGENT_CONTEXT.md, AGENT_QUICKREF.md, SOUL.md, config.toml, System Prompt) — not just the system prompt
  2. Recording a voice input transcribes via Deepgram and produces the same 5 files
  3. All 5 generated files are persisted to the `user_agents` table in Supabase after generation
  4. User can view each of the 5 files in separate tabs and edit the content before proceeding
**Plans**: TBD
**UI hint**: yes

### Phase 3: Credentials & Vault
**Goal**: User can supply their Telegram token and LLM key, which are encrypted in Supabase Vault — never on disk
**Depends on**: Phase 2
**Requirements**: CRED-01, CRED-02, CRED-03
**Success Criteria** (what must be TRUE):
  1. User can type a Telegram Bot Token into the credential form and save it
  2. User can type an LLM API key (OpenRouter or other provider) and save it
  3. Both keys are stored encrypted in Supabase Vault and are never written to VPS disk or visible in plain text in any log
**Plans**: TBD
**UI hint**: yes

### Phase 4: Provisioning Integration
**Goal**: User can deploy their configured agent and have a live Telegram bot within 30 seconds
**Depends on**: Phase 3
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04
**Success Criteria** (what must be TRUE):
  1. Clicking Deploy sends a HMAC-signed request from a Next.js server-side route (not the browser) directly to `http://91.99.209.45:9000/provision` — no Edge Function required
  2. The VPS creates a Docker container named `fc-{user_id}-{agent_id}` with keys injected as ENV variables
  3. Generated config files from Phase 2 land in the container's `/workspace` directory
  4. The Telegram bot is reachable and replies to messages within 30 seconds of clicking Deploy
**Plans**: TBD

### Phase 5: Dashboard & Mobile Polish
**Goal**: User can monitor and control their agents and complete the full flow on a mobile device
**Depends on**: Phase 4
**Requirements**: DASH-02, DASH-03, CONF-05
**Success Criteria** (what must be TRUE):
  1. Dashboard shows current status (running / stopped / error) for each agent, reflecting live container state
  2. User can stop a running agent and start a stopped agent from the dashboard with a single button click
  3. The full agent creation flow (voice input, tabs, credentials, deploy button) is fully usable on a 375px mobile screen with no horizontal scroll or overlapping elements
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure Baseline | 0/2 | Planning complete | - |
| 2. AI Generation Pipeline | 0/TBD | Not started | - |
| 3. Credentials & Vault | 0/TBD | Not started | - |
| 4. Provisioning Integration | 0/TBD | Not started | - |
| 5. Dashboard & Mobile Polish | 0/TBD | Not started | - |

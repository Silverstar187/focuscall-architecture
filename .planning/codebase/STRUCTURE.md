# Codebase Structure

**Analysis Date:** 2026-04-02

## Directory Layout

```
ZeroClaw/                          # Project root (focuscall.ai infrastructure)
├── _orchestrator/                 # Development-time tmux multi-agent orchestration
│   ├── config.json                # Orchestrator timing/threshold config
│   ├── orch-bootstrap.sh          # Session setup entry point
│   ├── spawn-worker.sh            # Spawns Claude Code workers in tmux
│   ├── heartbeat.sh               # Keeps worker sessions alive
│   ├── rate-limit-watchdog.sh     # API rate-limit detection
│   ├── workers/                   # Worker status JSON files (runtime)
│   ├── results/                   # Worker output artifacts (runtime)
│   ├── inbox/                     # Worker escalation/blocker files (runtime)
│   └── channels/                  # Cross-worker messaging (runtime)
├── architecture/                  # System architecture design documents
│   ├── README.md
│   ├── 01-vision.md               # Product concept and differentiators
│   ├── 02-per-tenant-architecture.md  # Isolation model, directory layout on VPS
│   ├── 03-knowledge-graph.md      # SurrealDB knowledge graph design (Phase 3)
│   ├── 04-multi-agent-personalities.md  # Multi-agent "Hands" model
│   ├── 05-provisioning-flow.md    # Full provisioning sequence (ASCII + code)
│   ├── 06-tech-stack-and-capacity.md   # Stack table, capacity math
│   └── 07-zeroclaw-reference.md   # ZeroClaw daemon config reference
├── docs/                          # Additional documentation
│   └── kimi-cli.md                # Kimi Code CLI ACP/MCP integration guide
├── infra/                         # Infrastructure as Code (Terraform)
│   ├── main.tf                    # Hetzner CAX21 server + firewall definition
│   ├── variables.tf               # Input variable declarations
│   ├── terraform.tfvars.example   # Example variable values (no secrets)
│   └── cloud-init.yml             # Server bootstrap script (cloud-init)
├── planning/                      # Task plans and execution summaries
│   ├── 260401-92r-PLAN.md         # Current execution plan (provisioning system)
│   └── 260401-92r-CONTEXT.md      # Context file for current plan
├── provisioning/                  # Production deployment code
│   ├── edge-function.ts           # Supabase Edge Function (Deno/TypeScript)
│   ├── webhook-receiver.py        # FastAPI webhook receiver (Python)
│   ├── provision.py               # Docker SDK provisioning logic (Python)
│   ├── Dockerfile                 # ZeroClaw multi-stage ARM64 image build
│   ├── config.toml.tmpl           # ZeroClaw config template (no secrets)
│   └── docker-compose.infra.yml   # Infra compose for webhook receiver
├── .planning/                     # GSD planning workspace
│   └── codebase/                  # Codebase analysis documents
├── AGENT_CONTEXT.md               # Full context doc for AI agents running in containers
├── AGENT_QUICKREF.md              # Quick reference card for running AI agents
├── README.md                      # Project overview, architecture diagram, stack table
├── RESUME.md                      # Session handoff document (current state + TODOs)
├── STATUS.md                      # Current operational status
├── SUBAGENTS.md                   # Subagent coordination notes
├── focuscall-architecture.excalidraw   # Main architecture diagram (Excalidraw source)
├── focuscall-architecture.png          # Main architecture diagram (rendered)
├── focuscall-detailed.excalidraw       # Detailed system diagram (Excalidraw source)
├── focuscall-detailed.png              # Detailed system diagram (rendered)
├── provisioner-v1.excalidraw           # Provisioner flow diagram (Excalidraw source)
└── zeroclaw.excalidraw                 # ZeroClaw container diagram (Excalidraw source)
```

---

## Directory Purposes

**`provisioning/`:**
- Purpose: All production-deployable code for the agent provisioning system
- Contains: Edge Function (TypeScript/Deno), Webhook Receiver (Python/FastAPI), Provisioner (Python/Docker SDK), Dockerfile (ZeroClaw image), config template, Docker Compose
- Key files: `provision.py` (core logic), `webhook-receiver.py` (HTTP API), `edge-function.ts` (Supabase layer), `Dockerfile` (container image), `config.toml.tmpl` (agent config template)
- Deployed to: Hetzner CAX21 at `/opt/focuscall/provisioning/`; edge-function deployed via `supabase functions deploy provision-agent`

**`architecture/`:**
- Purpose: Canonical design documentation; source of truth for architectural decisions
- Contains: Seven numbered markdown documents covering vision, per-tenant design, knowledge graph, multi-agent personalities, provisioning flow, tech stack, ZeroClaw reference
- Read order: `01` → `07` for full system understanding; `05` for provisioning detail; `06` for capacity planning
- Not deployed; reference only

**`infra/`:**
- Purpose: Terraform IaC for reproducible Hetzner server provisioning
- Contains: `main.tf` (server + firewall), `variables.tf`, `terraform.tfvars.example`, `cloud-init.yml`
- Use: `terraform apply` to create the CAX21 server; cloud-init bootstraps Docker, Python, nginx

**`_orchestrator/`:**
- Purpose: Development-time multi-agent Claude Code automation (not runtime infrastructure)
- Contains: Shell scripts for tmux session management, worker spawning, heartbeat, rate-limit watchdog; JSON config
- Key files: `orch-bootstrap.sh` (run first), `spawn-worker.sh` (create workers), `config.json` (tune intervals/limits)
- Runtime directories: `workers/` (status JSON), `results/` (output artifacts), `inbox/` (escalations), `channels/` (messaging)
- Not committed runtime state: `workers/*.json`, `results/**`, `inbox/**`, `heartbeat.pid`, `watchdog.pid`

**`planning/`:**
- Purpose: GSD-format task plans and execution context for current work
- Contains: `260401-92r-PLAN.md` (7-file provisioning system build plan with YAML frontmatter, tasks, verification), `260401-92r-CONTEXT.md`
- Naming pattern: `{YYMMDD}-{id}-{description}.md`

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents consumed by `/gsd:plan-phase` and `/gsd:execute-phase`
- Generated: Yes (by `/gsd:map-codebase`)
- Committed: Yes

**`docs/`:**
- Purpose: Supplementary documentation for tools used in development
- Key files: `kimi-cli.md` (Kimi Code CLI ACP/MCP setup for IDE integration)

---

## Key File Locations

**Entry Points:**
- `provisioning/edge-function.ts`: Supabase Edge Function — receives provision requests from frontend
- `provisioning/webhook-receiver.py`: FastAPI app — receives HMAC-authenticated calls from Edge Function; `uvicorn.run()` at bottom
- `provisioning/provision.py`: Core provisioner — `provision_container()`, `deprovision_container()`, `list_containers()`

**Configuration:**
- `provisioning/config.toml.tmpl`: ZeroClaw config template; variables `$USER_ID`, `$AGENT_ID`, `$PORT`, `$LLM_PROVIDER`
- `provisioning/docker-compose.infra.yml`: Webhook receiver service definition
- `_orchestrator/config.json`: Orchestrator timing and threshold configuration
- `infra/variables.tf`: Terraform input variable declarations
- `infra/terraform.tfvars.example`: Example Terraform values (safe to share)

**Container Definition:**
- `provisioning/Dockerfile`: Multi-stage build; Stage 1 `rust:1.88-bookworm` builds ZeroClaw from source; Stage 2 `debian:bookworm-slim` runtime; non-root user `zeroclaw`

**Architecture Reference:**
- `architecture/05-provisioning-flow.md`: Complete provisioning sequence with ASCII diagram
- `architecture/02-per-tenant-architecture.md`: VPS directory layout and isolation model
- `architecture/06-tech-stack-and-capacity.md`: Full stack table and capacity math

**Agent Runtime Context:**
- `AGENT_CONTEXT.md`: Full context for AI agents running inside ZeroClaw containers
- `AGENT_QUICKREF.md`: Quick reference card for running agents

**Session State:**
- `RESUME.md`: Current session handoff — read this first when resuming work
- `STATUS.md`: Operational status of deployed components

**Diagrams:**
- `focuscall-architecture.excalidraw` / `focuscall-architecture.png`: Top-level system architecture
- `focuscall-detailed.excalidraw` / `focuscall-detailed.png`: Detailed component diagram
- `provisioner-v1.excalidraw`: Provisioner flow diagram
- `zeroclaw.excalidraw`: ZeroClaw container internals

---

## Naming Conventions

**Files:**
- Python modules: `kebab-case.py` (e.g., `webhook-receiver.py`, `provision.py`)
- TypeScript/Deno: `kebab-case.ts` (e.g., `edge-function.ts`)
- Templates: `{name}.tmpl` suffix (e.g., `config.toml.tmpl`)
- Planning docs: `{YYMMDD}-{id}-{SLUG}.md` (e.g., `260401-92r-PLAN.md`)
- Architecture docs: `{NN}-{slug}.md` numbered sequence
- Status/context docs: `SCREAMING_SNAKE_CASE.md` (e.g., `AGENT_CONTEXT.md`, `RESUME.md`)
- Diagrams: `{project}-{variant}.excalidraw` with companion `.png`

**Directories:**
- Lowercase kebab-case: `provisioning/`, `architecture/`, `_orchestrator/`
- GSD workspace: `.planning/` (dotfile prefix)

**Docker containers:**
- Pattern: `fc-{user_id}-{agent_id}` (e.g., `fc-oliver-health`, `fc-oliver-finance`)

**Workspaces on VPS:**
- Pattern: `/opt/focuscall/workspaces/{user_id}/{agent_id}/`

**Port allocation:**
- Base: 42000; auto-increment via `registry.json`; range 42000–43999 (2000 slots)

---

## VPS Directory Layout (Runtime, on Hetzner CAX21)

```
/opt/focuscall/
├── registry.json              # Port/instance state registry (fcntl-locked)
├── registry.json.lock         # Lock file for concurrent registry access
├── workspaces/                # Per-agent workspace directories
│   └── {user_id}/
│       └── {agent_id}/
│           ├── config.toml    # Rendered from config.toml.tmpl (no secrets)
│           ├── brain.db       # ZeroClaw SQLite memory (Phase 1)
│           ├── db/            # SurrealDB data (Phase 3)
│           └── logs/          # Agent logs
├── provisioning/              # Deployed source files
│   ├── provision.py
│   ├── webhook-receiver.py
│   └── config.toml.tmpl
└── logs/                      # System-level provisioning logs
```

---

## Where to Add New Code

**New provisioning endpoint:**
- Add route to `provisioning/webhook-receiver.py` (Pydantic model + FastAPI route)
- Add business logic function to `provisioning/provision.py`
- Always use `_open_registry_lock()` / `_release_registry_lock()` for registry access

**New ZeroClaw config option:**
- Edit `provisioning/config.toml.tmpl`
- Add `$VARIABLE` placeholder; pass value in `string.Template.substitute()` call in `provisioning/provision.py`
- Keep all secrets out of the template — use ZeroClaw ENV var conventions (`ZEROCLAW_*`, `TELEGRAM_*`)

**New architecture document:**
- Add to `architecture/` with next sequential number: `08-{topic}.md`

**New infrastructure resource:**
- Add to `infra/main.tf`; declare variables in `infra/variables.tf`; update `infra/terraform.tfvars.example`

**New planning task:**
- Create `planning/{YYMMDD}-{id}-PLAN.md` following the YAML frontmatter + `<tasks>` XML format used by `planning/260401-92r-PLAN.md`

**New orchestrator worker task:**
- Run `./_orchestrator/spawn-worker.sh {id} sonnet "{description}" [context files...]`
- Worker writes status to `_orchestrator/workers/{id}.json`; output to `_orchestrator/results/{id}/`

---

## Special Directories

**`_orchestrator/workers/`:**
- Purpose: Live worker status JSON files written by active Claude Code workers
- Generated: Yes (at runtime)
- Committed: No (ephemeral, gitignored or manually cleaned)

**`_orchestrator/results/`:**
- Purpose: Output artifacts from completed worker tasks
- Generated: Yes (at runtime)
- Committed: Selectively (promoted manually when useful)

**`.planning/`:**
- Purpose: GSD planning workspace (codebase analysis, phase plans, summaries)
- Generated: By GSD commands
- Committed: Yes

---

*Structure analysis: 2026-04-02*

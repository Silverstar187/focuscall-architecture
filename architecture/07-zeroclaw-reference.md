# ZeroClaw Technical Reference

> Related: [Per-Tenant Architecture](02-per-tenant-architecture.md) | [Multi-Agent Personalities](04-multi-agent-personalities.md) | [Tech Stack](06-tech-stack-and-capacity.md) | [Provisioning Flow](05-provisioning-flow.md) | [README](README.md)

---

## Overview

ZeroClaw is a Rust-based, multi-channel AI agent runtime distributed as a single binary. It handles channel adapters (Telegram, WhatsApp, etc.), LLM routing, tool execution, session management, and multi-agent personalities ("Hands") — all without requiring a container, a runtime, or a language interpreter.

**Source:** [zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) — original repository, open source (Rust). Built from source via Dockerfile.

---

## Runtime Statistics

| Metric | Value |
|--------|-------|
| Binary size | 8.8 MB (stripped Rust binary) |
| RAM at idle | < 5 MB per instance |
| RAM under active use | ~10–20 MB per instance |
| Cold start time | < 10 ms to first message readiness |
| Language | Rust (zero GC pauses, no JVM/V8 overhead) |
| Async runtime | Tokio |
| Deployment | Single binary, no dependencies |

---

## Supported Channels

ZeroClaw can receive and send messages across a broad range of communication platforms via its channel adapter system.

| # | Channel | Notes |
|---|---------|-------|
| 1 | Telegram | Primary supported channel; bot_token based |
| 2 | WhatsApp | Via WhatsApp Business API |
| 3 | Discord | Bot token, slash commands supported |
| 4 | Slack | Slack app + bot token |
| 5 | Signal | Via Signal API bridge |
| 6 | iMessage | Via Apple Business Chat / Beeper bridge |
| 7 | Matrix | Element/Matrix federation |
| 8 | Email | SMTP/IMAP integration |
| 9 | SMS | Via Twilio or similar gateway |
| 10 | WeChat | Via WeChat Official Account API |
| 11 | Line | Via Line Messaging API |
| 12 | Viber | Via Viber Bot API |
| 13 | Twitter/X DM | Via Twitter API v2 |
| 14 | Instagram DM | Via Meta Business API |
| 15 | Facebook Messenger | Via Meta Business API |
| 16 | Web Widget | Embeddable chat widget |
| 17+ | 15+ more | Additional adapters released in updates |

For focuscall.ai, the primary integration is **Telegram** (bot_token). Users supply their own bot token, so the platform is not responsible for any Telegram API quotas.

---

## Built-in Tools

ZeroClaw includes a native tool execution layer. Tools are enabled/disabled per instance in `config.toml`.

| Tool | Category | Description |
|------|----------|-------------|
| Google Workspace | Productivity | Gmail, Google Calendar, Google Drive, Google Docs |
| Microsoft 365 | Productivity | Outlook, Teams, SharePoint, OneDrive |
| CRON | Scheduling | Schedule recurring agent actions (daily check-ins, habit reminders) |
| Web Search | Information | Search the web and return summarized results |
| Memory | Persistence | Store and retrieve named memories outside the knowledge graph |
| MCP (Model Context Protocol) | Extensibility | Connect to any MCP-compatible tool server |
| Shell | System | Execute shell commands (for advanced automation; use with caution) |
| Jira | Project Management | Create/update Jira issues, comment, query |
| Notion | Notes/Docs | Read/write Notion pages and databases |
| HTTP | Integration | Make arbitrary HTTP requests to external APIs |
| File | Storage | Read/write files in the instance's `files/` directory |

For focuscall.ai, the primary tools enabled per-instance:
- **CRON** — proactive morning/evening check-ins, habit nudges
- **Google Workspace** (optional) — calendar integration for events
- **Memory** — lightweight key-value memory alongside the knowledge graph

---

## Multi-Agent via Hands Feature

ZeroClaw's **Hands** feature allows one instance to host multiple named agent personalities. Each Hand has:

- A unique name
- A system prompt or system prompt file path
- Optional trigger keywords or routing rules
- A default flag (one Hand is the catch-all default)

Configuration in `config.toml`:

```toml
[[hands.personalities]]
name = "ProductivityCoach"
default = true
system_prompt_file = "/opt/focuscall/ontologies/prompts/productivity_coach.md"

[[hands.personalities]]
name = "HealthCoach"
trigger_keywords = ["health", "energy", "medication", "sleep", "symptom"]
system_prompt_file = "/opt/focuscall/ontologies/prompts/health_coach.md"

[[hands.personalities]]
name = "FinanceAdvisor"
trigger_keywords = ["money", "budget", "expense", "savings", "debt"]
system_prompt_file = "/opt/focuscall/ontologies/prompts/finance_advisor.md"
```

Users can also invoke Hands directly with `/handname message`.

See [Multi-Agent Personalities](04-multi-agent-personalities.md) for full routing and prompt design documentation.

---

## Session Isolation via sender_session_id

ZeroClaw uses a `sender_session_id` field to maintain conversation state isolation. For focuscall.ai:

- Each ZeroClaw instance serves exactly one user — so `sender_session_id` maps to the single user
- Session context (recent message history for LLM context window) is stored in memory and optionally persisted to the SurrealDB knowledge graph
- Sessions can be reset by the user or automatically after a configurable idle timeout

```toml
[session]
idle_timeout_minutes = 30   # Reset context window after 30 min of inactivity
persist_to_db = true         # Write session summaries to SurrealDB
```

---

## Gateway Port and Routing

ZeroClaw's internal HTTP gateway (used by webhooks and health checks) runs on a configurable port.

**Default port:** 42617 (ZeroClaw internal default)
**focuscall.ai convention:** 42000 + N (overriding the default via config)

```toml
[gateway]
port = 42003         # Unique per instance
host = "127.0.0.1"  # Only accessible from localhost; nginx proxies externally
```

The gateway exposes:
- `GET /health` — health check (returns `{"status":"ok","uptime":N,"db":"connected"}`)
- `POST /webhook` — receives channel messages (Telegram, etc. webhooks point here via nginx)
- `GET /metrics` — Prometheus-compatible metrics (optional)

---

## Autonomy Levels

ZeroClaw supports three autonomy modes that control how proactively the agent acts without user prompting:

### ReadOnly

The agent only responds to direct user messages. It does not initiate conversations, does not schedule CRON actions, does not modify external tools without explicit user instruction.

**Use case:** New users, high-trust-sensitivity domains (finance, medical adjacent).

```toml
[agent]
autonomy = "readonly"
```

### Supervised

The agent can initiate conversations (e.g., morning check-ins via CRON) but will ask for confirmation before taking any action with external tools (creating calendar events, sending emails, etc.).

**Use case:** Default mode for most focuscall.ai users. Proactive coaching without unilateral action.

```toml
[agent]
autonomy = "supervised"
```

### Full

The agent can initiate conversations, execute CRON schedules, and interact with external tools without per-action confirmation. The user trusts the agent to act on their behalf.

**Use case:** Power users who have established high trust with the agent and want fully autonomous operation.

```toml
[agent]
autonomy = "full"
```

---

## Config Format: Key Fields

Full reference for `config.toml` fields relevant to focuscall.ai deployment:

```toml
# ── Gateway ────────────────────────────────────────────────────────────────
[gateway]
port = 42000          # Internal HTTP port (unique per instance)
host = "127.0.0.1"    # Bind to localhost only

# ── Bot / Channel ──────────────────────────────────────────────────────────
[bot]
token = "..."          # Channel-specific bot token (e.g., Telegram bot token)
channel = "telegram"   # Active channel adapter

# ── LLM ────────────────────────────────────────────────────────────────────
[llm]
provider = "openai"    # openai | anthropic | mistral | ollama | ...
api_key = "..."        # User-supplied LLM API key
model = "gpt-4o-mini"  # Model name (provider-specific)
temperature = 0.7
max_tokens = 2048
timeout_ms = 30000     # LLM call timeout

# ── Database ───────────────────────────────────────────────────────────────
[database]
path = "/opt/focuscall/users/{user_id}/db"
embedded = true        # Use embedded SurrealDB (no server)

# ── Ontologies ─────────────────────────────────────────────────────────────
[ontologies]
path = "/opt/focuscall/ontologies"
load = ["core.ttl", "productivity.ttl"]

# ── Session ────────────────────────────────────────────────────────────────
[session]
idle_timeout_minutes = 30
persist_to_db = true
context_window_messages = 20   # How many messages to keep in LLM context

# ── Agent Autonomy ─────────────────────────────────────────────────────────
[agent]
autonomy = "supervised"        # readonly | supervised | full

# ── Tools ──────────────────────────────────────────────────────────────────
[tools]
enabled = ["cron", "memory"]   # Tools active for this instance

# ── Hands (Multi-Agent) ────────────────────────────────────────────────────
[[hands.personalities]]
name = "ProductivityCoach"
default = true
system_prompt_file = "/opt/focuscall/ontologies/prompts/productivity_coach.md"

# ── Logging ────────────────────────────────────────────────────────────────
[logging]
path = "/opt/focuscall/users/{user_id}/logs/zeroclaw.log"
level = "info"                 # debug | info | warn | error
rotate = true
rotate_max_size_mb = 50
```

---

## Version Notes: 0.6.7

ZeroClaw 0.6.7 (b0xtch fork) is the version used in focuscall.ai. Key features present in this version:

- Hands multi-personality support (new in 0.6.x)
- SurrealDB v3 embedded mode integration
- CRON tool with persistent schedules
- MCP tool support
- `sender_session_id` isolation
- ARM64 binary distribution
- `trusted_proxy` auth mode (for nginx-fronted deployments)

For integration specifics, see [Per-Tenant Architecture](02-per-tenant-architecture.md) and [Provisioning Flow](05-provisioning-flow.md).

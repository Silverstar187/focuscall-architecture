# ZeroClaw Automatische Provisionierung - Vollständige Anleitung

> **Version:** ZeroClaw v0.6.7 (b0xtch fork) / v0.1.7 (crates.io)  
> **Letzte Aktualisierung:** 2026-04-02  
> **Zweck:** Automatische Provisionierung in Docker-Containern

---

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Standardkonfiguration](#standardkonfiguration)
3. [Alle Konfigurationsparameter](#alle-konfigurationsparameter)
4. [Umgebungsvariablen](#umgebungsvariablen)
5. [Provisionierungsmethoden](#provisionierungsmethoden)
6. [Docker-Deployment](#docker-deployment)
7. [Beispiel-Konfigurationen](#beispiel-konfigurationen)
8. [Sicherheitsaspekte](#sicherheitsaspekte)
9. [Fehlerbehebung](#fehlerbehebung)

---

## Überblick

ZeroClaw ist ein Rust-basierter KI-Agent-Runtime, der als einzelnes Binary (~8.8 MB) läuft. Für automatische Provisionierung in Docker-Containern gibt es mehrere Ansätze:

| Ansatz | Beschreibung | Use Case |
|--------|--------------|----------|
| **Pre-built Image** | Vorkompiliertes Docker-Image mit Konfiguration | Schneller Start |
| **Source Build** | Build aus GitHub-Source pro Deployment | Aktuellste Version |
| **Multi-Container** | 1 Container = 1 Agent-Instanz | Multi-Tenant |
| **Cloud-Init** | Automatische Server-Provisionierung | VPS/VM |

### Ressourcenanforderungen

| Ressource | Minimum | Empfohlen |
|-----------|---------|-----------|
| **RAM** | 5 MB | 128 MB (mit Limit) |
| **CPU** | 0.1 Cores | 0.5 Cores |
| **Disk** | 50 MB | 1 GB (Logs/Datenbank) |
| **Binary-Größe** | ~8.8 MB | ~8.8 MB |
| **Cold Start** | < 10 ms | < 10 ms |

---

## Standardkonfiguration

### Minimal Konfiguration (config.toml)

```toml
# Absolute Minimum - Provider + API Key
default_provider = "anthropic"
api_key = "sk-ant-..."
```

### Vollständige Standardkonfiguration

```toml
# ═══════════════════════════════════════════════════════════════════════════
# ZeroClaw Standardkonfiguration (v0.6.7)
# ═══════════════════════════════════════════════════════════════════════════

# ── Core ────────────────────────────────────────────────────────────────────
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4-6"
default_temperature = 0.7

# ── Gateway ─────────────────────────────────────────────────────────────────
[gateway]
host = "127.0.0.1"
port = 42617
require_pairing = true
allow_public_bind = false
session_persistence = true
path_prefix = ""  # z.B. "/zeroclaw" für Reverse Proxy

# ── Agent ───────────────────────────────────────────────────────────────────
[agent]
max_tool_iterations = 10
max_history_messages = 50
max_context_tokens = 32000
compact_context = true
parallel_tools = false
tool_dispatcher = "auto"

# ── Autonomy ────────────────────────────────────────────────────────────────
[autonomy]
level = "supervised"  # readonly | supervised | full
workspace_only = true
max_actions_per_hour = 20
max_cost_per_day_cents = 500
require_approval_for_medium_risk = true
block_high_risk_commands = true
allowed_commands = []
forbidden_paths = ["/etc", "/root", "/proc", "/sys", "~/.ssh", "~/.gnupg", "~/.aws"]
allowed_roots = []
auto_approve = []
always_ask = []

# ── Memory ──────────────────────────────────────────────────────────────────
[memory]
backend = "sqlite"
auto_save = true
embedding_provider = "none"
embedding_model = "text-embedding-3-small"
embedding_dimensions = 1536
vector_weight = 0.7
keyword_weight = 0.3

# ── Channels ────────────────────────────────────────────────────────────────
[channels_config]
message_timeout_secs = 300

[channels_config.telegram]
enabled = false
bot_token = ""
allowed_users = []
stream_mode = "multi_message"  # off | partial | multi_message
interrupt_on_new_message = false

# ── Security ────────────────────────────────────────────────────────────────
[security.otp]
enabled = false
method = "totp"
token_ttl_secs = 30
cache_valid_secs = 300
gated_actions = ["shell", "file_write", "browser_open", "browser", "memory_forget"]
gated_domains = []
gated_domain_categories = []

[security.estop]
enabled = false
state_file = "~/.zeroclaw/estop-state.json"
require_otp_to_resume = true

# ── Tools ───────────────────────────────────────────────────────────────────
[tools]
enabled = ["cron", "memory"]

# ── Logging ─────────────────────────────────────────────────────────────────
[logging]
level = "info"
rotate = true
rotate_max_size_mb = 50
path = "logs/zeroclaw.log"

# ── Observability ───────────────────────────────────────────────────────────
[observability]
backend = "none"
otel_endpoint = "http://localhost:4318"
otel_service_name = "zeroclaw"
runtime_trace_mode = "none"
runtime_trace_path = "state/runtime-trace.jsonl"
runtime_trace_max_entries = 200

# ── Cost Control ────────────────────────────────────────────────────────────
[cost]
enabled = false
daily_limit_usd = 10.00
monthly_limit_usd = 100.00
warn_at_percent = 80
allow_override = false

# ── Storage ─────────────────────────────────────────────────────────────────
[storage]
path = "data"

# ── Runtime ─────────────────────────────────────────────────────────────────
[runtime]
reasoning_enabled = null
```

---

## Alle Konfigurationsparameter

### Core Parameter

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `default_provider` | string | `openrouter` | LLM Provider (openai, anthropic, openrouter, ollama, groq, mistral, custom:url) |
| `default_model` | string | `anthropic/claude-sonnet-4-6` | Modell-Name im Provider-Format |
| `default_temperature` | float | `0.7` | Sampling-Temperatur (0.0 - 2.0) |
| `api_key` | string | - | API-Key für den Provider |
| `api_url` | string | - | Custom Endpoint URL |

### Gateway Section `[gateway]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `host` | string | `127.0.0.1` | Bind-Addresse |
| `port` | integer | `42617` | Gateway-Port |
| `require_pairing` | boolean | `true` | Pairing für Auth erforderlich |
| `allow_public_bind` | boolean | `false` | Öffentliche Bindung erlauben |
| `session_persistence` | boolean | `true` | Sessions persistieren |
| `path_prefix` | string | `""` | URL-Prefix für Reverse Proxy |
| `trust_forwarded_headers` | boolean | `false` | X-Forwarded-* Headers vertrauen |
| `paired_tokens` | array | `[]` | Gepairte Tokens (automatisch) |

### Agent Section `[agent]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `max_tool_iterations` | integer | `10` | Maximale Tool-Call-Schleifen |
| `max_history_messages` | integer | `50` | Maximale Chat-Historie |
| `max_context_tokens` | integer | `32000` | Context-Window-Größe |
| `compact_context` | boolean | `true` | Kontext für kleine Modelle komprimieren |
| `parallel_tools` | boolean | `false` | Parallele Tool-Ausführung |
| `tool_dispatcher` | string | `auto` | Tool-Dispatch-Strategie |
| `tool_call_dedup_exempt` | array | `[]` | Tools mit erlaubten Duplikaten |

### Tool Filter Groups `[agent.tool_filter_groups]`

```toml
[[agent.tool_filter_groups]]
mode = "always"  # always | dynamic
tools = ["mcp_vikunja_*"]
keywords = ["task", "todo"]  # nur für dynamic
```

### Autonomy Section `[autonomy]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `level` | string | `supervised` | Autonomie-Level: readonly, supervised, full |
| `workspace_only` | boolean | `true` | Nur Workspace-Zugriff |
| `allowed_commands` | array | `[]` | Erlaubte Shell-Befehle (* = alle) |
| `forbidden_paths` | array | `["..."]` | Verbotene Pfade |
| `allowed_roots` | array | `[]` | Zusätzlich erlaubte Wurzelverzeichnisse |
| `max_actions_per_hour` | integer | `20` | Aktionen pro Stunde |
| `max_cost_per_day_cents` | integer | `500` | Tageslimit in Cent |
| `require_approval_for_medium_risk` | boolean | `true` | Bestätigung für mittleres Risiko |
| `block_high_risk_commands` | boolean | `true` | Hohes Risiko blockieren |
| `auto_approve` | array | `[]` | Immer genehmigte Tools |
| `always_ask` | array | `[]` | Immer nachfragende Tools |

### Memory Section `[memory]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `backend` | string | `sqlite` | Backend: sqlite, lucid, markdown, none |
| `auto_save` | boolean | `true` | Automatisches Speichern |
| `embedding_provider` | string | `none` | Embedding-Provider |
| `embedding_model` | string | `text-embedding-3-small` | Embedding-Modell |
| `embedding_dimensions` | integer | `1536` | Vektor-Dimensionen |
| `vector_weight` | float | `0.7` | Vektor-Gewichtung |
| `keyword_weight` | float | `0.3` | Keyword-Gewichtung |

### Channel Configuration `[channels_config.*]`

#### Telegram `[channels_config.telegram]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Telegram aktivieren |
| `bot_token` | string | - | Bot-Token von @BotFather |
| `allowed_users` | array | `[]` | Erlaubte User-IDs (* = alle) |
| `stream_mode` | string | `multi_message` | Streaming-Modus |
| `interrupt_on_new_message` | boolean | `false` | Unterbrechung bei neuer Nachricht |

#### Discord `[channels_config.discord]`

| Parameter | Typ | Standard |
|-----------|-----|----------|
| `token` | string | - |
| `allowed_servers` | array | `[]` |

#### Slack `[channels_config.slack]`

| Parameter | Typ | Standard |
|-----------|-----|----------|
| `bot_token` | string | - |
| `app_token` | string | - |
| `allowed_workspaces` | array | `[]` |

#### WhatsApp `[channels_config.whatsapp]`

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `access_token` | string | Meta Cloud API Token |
| `phone_number_id` | string | Meta Phone Number ID |
| `verify_token` | string | Webhook Verify Token |
| `allowed_numbers` | array | Erlaubte Nummern |

#### Signal `[channels_config.signal]`

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `phone_number` | string | Bot-Telefonnummer |

#### Matrix `[channels_config.matrix]`

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `homeserver_url` | string | Matrix-Server URL |
| `username` | string | Bot-Username |
| `password` | string | Bot-Passwort |

#### Email `[channels_config.email]`

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `imap_server` | string | IMAP-Server |
| `smtp_server` | string | SMTP-Server |
| `username` | string | E-Mail-Adresse |
| `password` | string | Passwort |

### Reliability Section `[reliability]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `fallback_providers` | array | `[]` | Fallback-Provider-Liste |
| `model_fallbacks` | map | `{}` | Per-Model Fallbacks |
| `api_keys` | array | `[]` | Zusätzliche API-Keys für Rotation |
| `provider_retries` | integer | `2` | Retries pro Provider |
| `provider_backoff_ms` | integer | `500` | Backoff in ms |
| `channel_initial_backoff_secs` | integer | `1` | Initialer Channel-Backoff |
| `channel_max_backoff_secs` | integer | `60` | Maximaler Channel-Backoff |
| `scheduler_poll_secs` | integer | `5` | Scheduler-Polling-Intervall |
| `scheduler_retries` | integer | `3` | Scheduler-Retries |

### Pacing Section `[pacing]`

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `step_timeout_secs` | integer | Timeout pro LLM-Schritt |
| `loop_detection_min_elapsed_secs` | integer | Mindestzeit für Loop-Erkennung |
| `loop_ignore_tools` | array | Tools von Loop-Erkennung ausgeschlossen |
| `message_timeout_scale_max` | integer | Maximale Timeout-Skalierung |

### Observability Section `[observability]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `backend` | string | `none` | none, log, prometheus, otel |
| `otel_endpoint` | string | `http://localhost:4318` | OTLP Endpoint |
| `otel_service_name` | string | `zeroclaw` | Service-Name |
| `runtime_trace_mode` | string | `none` | none, rolling, full |
| `runtime_trace_path` | string | `state/runtime-trace.jsonl` | Trace-Dateipfad |
| `runtime_trace_max_entries` | integer | `200` | Maximale Trace-Einträge |

### Security OTP Section `[security.otp]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | OTP aktivieren |
| `method` | string | `totp` | totp, pairing, cli-prompt |
| `token_ttl_secs` | integer | `30` | Token-Gültigkeit |
| `cache_valid_secs` | integer | `300` | Cache-Gültigkeit |
| `gated_actions` | array | `["shell", ...]` | OTP-geschützte Aktionen |
| `gated_domains` | array | `[]` | OTP-geschützte Domains |
| `gated_domain_categories` | array | `[]` | Kategorien: banking, medical, government |

### Skills Section `[skills]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `open_skills_enabled` | boolean | `false` | Community Skills laden |
| `open_skills_dir` | string | - | Lokaler Skills-Pfad |
| `prompt_injection_mode` | string | `full` | full, compact |

### Cost Section `[cost]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Kosten-Tracking |
| `daily_limit_usd` | float | `10.00` | Tageslimit USD |
| `monthly_limit_usd` | float | `100.00` | Monatslimit USD |
| `warn_at_percent` | integer | `80` | Warnschwelle % |
| `allow_override` | boolean | `false` | Override erlauben |

### Hands (Multi-Agent) Section `[[hands.personalities]]`

```toml
[[hands.personalities]]
name = "ProductivityCoach"
default = true
system_prompt_file = "/opt/focuscall/prompts/productivity_coach.md"

[[hands.personalities]]
name = "HealthCoach"
trigger_keywords = ["health", "energy", "sleep"]
system_prompt_file = "/opt/focuscall/prompts/health_coach.md"
```

### Sub-Agents Section `[agents.<name>]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `provider` | string | required | Provider für Sub-Agent |
| `model` | string | required | Modell für Sub-Agent |
| `system_prompt` | string | - | System-Prompt |
| `api_key` | string | - | API-Key Override |
| `temperature` | float | - | Temperatur |
| `max_depth` | integer | `3` | Max Rekursionstiefe |
| `agentic` | boolean | `false` | Multi-Turn Mode |
| `allowed_tools` | array | `[]` | Erlaubte Tools |
| `max_iterations` | integer | `10` | Max Iterationen |
| `timeout_secs` | integer | `120` | Timeout |
| `agentic_timeout_secs` | integer | `300` | Agentic Timeout |
| `skills_directory` | string | - | Skills-Verzeichnis |

### Model Routes `[[model_routes]]` und `[[embedding_routes]]`

```toml
[[model_routes]]
hint = "reasoning"
provider = "openrouter"
model = "anthropic/claude-opus-4"

[[model_routes]]
hint = "fast"
provider = "groq"
model = "llama-3.1-70b"

[[embedding_routes]]
hint = "semantic"
provider = "openai"
model = "text-embedding-3-small"
dimensions = 1536
```

### Query Classification `[query_classification]`

```toml
[query_classification]
enabled = true

[[query_classification.rules]]
hint = "reasoning"
keywords = ["explain", "analyze"]
patterns = ["```"]
min_length = 200
priority = 10
```

### Browser Section `[browser]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Browser-Tool aktivieren |
| `allowed_domains` | array | `[]` | Erlaubte Domains (* = alle) |
| `session_name` | string | - | Browser-Session-Name |
| `backend` | string | `agent_browser` | agent_browser, rust_native, computer_use |
| `native_headless` | boolean | `true` | Headless-Modus |
| `native_webdriver_url` | string | `http://127.0.0.1:9515` | WebDriver URL |
| `native_chrome_path` | string | - | Chrome-Pfad |

### HTTP Request Section `[http_request]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | HTTP-Tool aktivieren |
| `allowed_domains` | array | `[]` | Erlaubte Domains |
| `max_response_size` | integer | `1000000` | Max Response-Größe |
| `timeout_secs` | integer | `30` | Timeout |

### Google Workspace Section `[google_workspace]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Google Workspace aktivieren |
| `credentials_path` | string | - | Credentials-JSON-Pfad |
| `default_account` | string | - | Standard-Account |
| `allowed_services` | array | `["drive", "gmail", ...]` | Erlaubte Services |
| `rate_limit_per_minute` | integer | `60` | Rate-Limit |
| `timeout_secs` | integer | `30` | Timeout |
| `audit_log` | boolean | `false` | Audit-Logging |

### Tunnel Section `[tunnel]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `kind` | string | - | cloudflare, tailscale, ngrok, openvpn, custom, none |

### Identity Section `[identity]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `format` | string | `openclaw` | openclaw, aieos |
| `aieos_path` | string | - | Pfad zu AIEOS JSON |
| `aieos_inline` | string | - | Inline AIEOS JSON |

### Multimodal Section `[multimodal]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `max_images` | integer | `4` | Maximale Bilder pro Request |
| `max_image_size_mb` | integer | `5` | Maximale Bildgröße |
| `allow_remote_fetch` | boolean | `false` | Remote-Bilder laden |

### Hardware Section `[hardware]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Hardware-Zugriff |
| `transport` | string | `none` | none, native, serial, probe |
| `serial_port` | string | - | Serial-Port |
| `baud_rate` | integer | `115200` | Baudrate |
| `probe_target` | string | - | Ziel-Chip |
| `workspace_datasheets` | boolean | `false` | Datasheet-RAG |

### Peripherals Section `[peripherals]`

```toml
[peripherals]
enabled = true
datasheet_dir = "docs/datasheets"

[[peripherals.boards]]
board = "nucleo-f401re"
transport = "serial"
path = "/dev/ttyACM0"
baud = 115200
```

### Composio Section `[composio]`

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|----------|--------------|
| `enabled` | boolean | `false` | Composio aktivieren |
| `api_key` | string | - | Composio API-Key |
| `entity_id` | string | `default` | Entity-ID |

---

## Umgebungsvariablen

### Konfigurations-Overrides

| Variable | Beschreibung | Priorität |
|----------|--------------|-----------|
| `ZEROCLAW_WORKSPACE` | Workspace-Verzeichnis | Höchste |
| `ZEROCLAW_CONFIG_DIR` | Config-Verzeichnis | Hoch |
| `ZEROCLAW_PROVIDER` | Provider-Override | Hoch |
| `PROVIDER` | Provider (Legacy) | Mittel |

### API Keys

| Variable | Beschreibung |
|----------|--------------|
| `ZEROCLAW_API_KEY` | Universeller API-Key (für custom Provider) |
| `OPENAI_API_KEY` | OpenAI API-Key |
| `ANTHROPIC_API_KEY` | Anthropic API-Key |
| `GOOGLE_API_KEY` | Google API-Key |
| `GROQ_API_KEY` | Groq API-Key |
| `MISTRAL_API_KEY` | Mistral API-Key |
| `OPENROUTER_API_KEY` | OpenRouter API-Key |

### Channel Secrets

| Variable | Beschreibung |
|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot-Token |
| `DISCORD_BOT_TOKEN` | Discord Bot-Token |
| `SLACK_BOT_TOKEN` | Slack Bot-Token |
| `SLACK_APP_TOKEN` | Slack App-Token |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp Access-Token |
| `SIGNAL_PHONE_NUMBER` | Signal Telefonnummer |
| `MATRIX_PASSWORD` | Matrix Passwort |
| `NOSTR_PRIVATE_KEY` | Nostr Private Key |

### Skills

| Variable | Beschreibung |
|----------|--------------|
| `ZEROCLAW_OPEN_SKILLS_ENABLED` | Open Skills aktivieren (1/0, true/false) |
| `ZEROCLAW_OPEN_SKILLS_DIR` | Open Skills Verzeichnis |
| `ZEROCLAW_SKILLS_PROMPT_MODE` | full oder compact |

### Observability

| Variable | Beschreibung |
|----------|--------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP Endpoint |
| `OTEL_SERVICE_NAME` | Service-Name |

---

## Provisionierungsmethoden

### Methode 1: Pre-built Docker Image

```dockerfile
# Dockerfile.zeroclaw-prebuilt
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*

RUN groupadd -r zeroclaw && useradd -r -g zeroclaw -d /home/zeroclaw -m zeroclaw

# Pre-built Binary von GitHub Releases
ADD https://github.com/zeroclaw-labs/zeroclaw/releases/latest/download/zeroclaw-linux-arm64 /usr/local/bin/zeroclaw
RUN chmod +x /usr/local/bin/zeroclaw

VOLUME /workspace
ENV ZEROCLAW_CONFIG_DIR=/workspace
USER zeroclaw

ENTRYPOINT ["zeroclaw", "daemon"]
```

### Methode 2: Build from Source (empfohlen für focuscall)

```dockerfile
# Multi-stage Build
FROM rust:1.88-bookworm AS builder

RUN apt-get update && apt-get install -y \
    git pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/zeroclaw-labs/zeroclaw.git /build
WORKDIR /build
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*

RUN groupadd -r zeroclaw && useradd -r -g zeroclaw -d /home/zeroclaw -m zeroclaw

COPY --from=builder /build/target/release/zeroclaw /usr/local/bin/zeroclaw
RUN chmod +x /usr/local/bin/zeroclaw

VOLUME /workspace
ENV ZEROCLAW_CONFIG_DIR=/workspace
USER zeroclaw

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-42000}/health" | grep -q '"status"' || exit 1

ENTRYPOINT ["zeroclaw", "daemon"]
```

### Methode 3: Multi-Container Provisioning (focuscall.ai)

```python
# provision.py (Auszug)
container = client.containers.run(
    image="zeroclaw:latest",
    name=f"fc-{user_id}-{agent_id}",
    detach=True,
    environment={
        "ZEROCLAW_API_KEY": llm_key,      # NUR ENV, nie Disk
        "TELEGRAM_BOT_TOKEN": bot_token,  # NUR ENV, nie Disk
        "ZEROCLAW_CONFIG_DIR": "/workspace",
    },
    volumes={
        str(workspace): {"bind": "/workspace", "mode": "rw"},
    },
    security_opt=["no-new-privileges"],
    cap_drop=["ALL"],
    read_only=True,
    mem_limit="128m",
    nano_cpus=500_000_000,  # 0.5 CPUs
    restart_policy={"Name": "unless-stopped"},
    tmpfs={"/tmp": "size=10m,noexec,nosuid"},
    network_mode="bridge",
)
```

### Methode 4: Cloud-Init (VPS Bootstrap)

```yaml
#cloud-config
package_update: true
packages:
  - docker.io
  - docker-compose-v2
  - python3-pip
  - nginx

runcmd:
  - systemctl enable docker
  - mkdir -p /opt/focuscall/{workspaces,provisioning}
  
  # Build ZeroClaw Image
  - |
    cat > /opt/focuscall/Dockerfile << 'EOF'
    FROM rust:1.88-bookworm AS builder
    RUN apt-get update && apt-get install -y git pkg-config libssl-dev
    RUN git clone --depth 1 https://github.com/zeroclaw-labs/zeroclaw.git /build
    WORKDIR /build
    RUN cargo build --release
    
    FROM debian:bookworm-slim
    RUN apt-get update && apt-get install -y ca-certificates curl
    RUN groupadd -r zeroclaw && useradd -r -g zeroclaw zeroclaw
    COPY --from=builder /build/target/release/zeroclaw /usr/local/bin/zeroclaw
    VOLUME /workspace
    ENV ZEROCLAW_CONFIG_DIR=/workspace
    USER zeroclaw
    ENTRYPOINT ["zeroclaw", "daemon"]
    EOF
  
  - docker build -t zeroclaw:latest /opt/focuscall/
  
  # Registry initialisieren
  - echo '{"next_port":42000,"instances":{}}' > /opt/focuscall/registry.json
```

### Methode 5: Docker Compose (Single Instance)

```yaml
# docker-compose.yml
version: "3.9"

services:
  zeroclaw:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: zeroclaw-instance
    restart: unless-stopped
    
    environment:
      ZEROCLAW_API_KEY: ${ZEROCLAW_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      ZEROCLAW_CONFIG_DIR: /workspace
    
    volumes:
      - ./workspace:/workspace:rw
    
    # Security
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    
    # Ressourcen
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: "0.5"
    
    # Netzwerk
    ports:
      - "127.0.0.1:42617:42617"
    
    tmpfs:
      - /tmp:size=10m,noexec,nosuid
    
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:42617/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

---

## Docker-Deployment

### Build

```bash
# Auf ARM64 Host (Hetzner CAX21)
docker build -t zeroclaw:latest .

# Cross-compile von x86_64 für ARM64
docker buildx build --platform linux/arm64 -t zeroclaw:latest .

# Für AMD64
docker buildx build --platform linux/amd64 -t zeroclaw:latest .
```

### Run

```bash
# Mit Env-Variablen
docker run -d \
  --name zeroclaw-001 \
  -e ZEROCLAW_API_KEY="sk-..." \
  -e TELEGRAM_BOT_TOKEN="749..." \
  -e ZEROCLAW_CONFIG_DIR="/workspace" \
  -v /opt/focuscall/workspaces/user-001/agent-001:/workspace \
  --read-only \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --memory=128m \
  --cpus=0.5 \
  --tmpfs /tmp:size=10m,noexec,nosuid \
  zeroclaw:latest
```

### Health Check

```bash
# Container-Health
docker exec zeroclaw-001 curl -fsS http://localhost:42617/health

# Logs
docker logs -f zeroclaw-001

# Status
zeroclaw status  # innerhalb Container
```

---

## Beispiel-Konfigurationen

### Beispiel 1: Minimal Telegram Bot

```toml
# config.toml
default_provider = "openrouter"
default_model = "openai/gpt-4o-mini"

[gateway]
port = 42001
host = "127.0.0.1"
require_pairing = false

[channels_config.telegram]
enabled = true
bot_token = "${TELEGRAM_BOT_TOKEN}"
allowed_users = []
stream_mode = "multi_message"

[autonomy]
level = "supervised"

[agent]
max_tool_iterations = 5
```

### Beispiel 2: Multi-Channel Setup

```toml
# config.toml
default_provider = "anthropic"
default_model = "claude-sonnet-4-6"

[gateway]
port = 42002
host = "127.0.0.1"

# Telegram
[channels_config.telegram]
enabled = true
bot_token = "${TELEGRAM_BOT_TOKEN}"

# Discord
[channels_config.discord]
enabled = true
token = "${DISCORD_TOKEN}"

# Slack
[channels_config.slack]
enabled = true
bot_token = "${SLACK_BOT_TOKEN}"
app_token = "${SLACK_APP_TOKEN}"

[autonomy]
level = "full"

[tools]
enabled = ["cron", "memory", "http_request"]

[cost]
enabled = true
daily_limit_usd = 5.00
```

### Beispiel 3: Enterprise mit Fallback

```toml
# config.toml
default_provider = "openai"
default_model = "gpt-4o"

[reliability]
fallback_providers = ["anthropic", "groq"]
provider_retries = 3
provider_backoff_ms = 1000

[reliability.model_fallbacks]
"gpt-4o" = ["claude-sonnet-4-6", "llama-3.1-70b"]

api_keys = [
    "${ZEROCLAW_API_KEY_PRIMARY}",
    "${ZEROCLAW_API_KEY_BACKUP}",
]

[security.otp]
enabled = true
method = "totp"
gated_actions = ["shell", "file_write", "memory_forget"]
gated_domain_categories = ["banking", "medical"]

[cost]
enabled = true
daily_limit_usd = 50.00
monthly_limit_usd = 500.00
warn_at_percent = 75

[observability]
backend = "otel"
otel_endpoint = "http://otel-collector:4318"
otel_service_name = "zeroclaw-production"
```

### Beispiel 4: Local/Ollama Setup

```toml
# config.toml
default_provider = "custom:http://localhost:11434/v1"
default_model = "llama3.2"
default_temperature = 0.8

[gateway]
port = 42617

[autonomy]
level = "full"

[memory]
backend = "sqlite"
auto_save = true

[pacing]
step_timeout_secs = 120
loop_detection_min_elapsed_secs = 60
message_timeout_scale_max = 8

[channels_config.telegram]
enabled = true
bot_token = "${TELEGRAM_BOT_TOKEN}"
```

### Beispiel 5: focuscall.ai Template

```toml
# focuscall.ai — ZeroClaw config template
# Variablen: $USER_ID $AGENT_ID $PORT $LLM_PROVIDER

default_provider = "$LLM_PROVIDER"
default_model = "openai/gpt-4o-mini"

[gateway]
host = "127.0.0.1"
port = $PORT
require_pairing = false
session_persistence = true

[channels_config.telegram]
bot_token = "${TELEGRAM_BOT_TOKEN}"
allowed_users = []
stream_mode = "multi_message"

[autonomy]
level = "supervised"

[agent]
max_history_messages = 50
max_context_tokens = 32000
max_tool_iterations = 10

# Cost Guard (optional)
# [cost]
# daily_limit_usd = 1.0
# per_message_limit_usd = 0.05
```

---

## Sicherheitsaspekte

### Docker Security Best Practices

```yaml
# docker-compose.yml mit maximaler Sicherheit
services:
  zeroclaw:
    image: zeroclaw:latest
    
    # Security Profile
    security_opt:
      - no-new-privileges:true
      - seccomp:./zeroclaw-seccomp.json  # Custom Seccomp
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Falls nötig
    
    # Filesystem
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=10m
      - /var/tmp:noexec,nosuid,size=10m
    
    # Ressourcen-Limits
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: "0.5"
        reservations:
          memory: 32M
          cpus: "0.1"
    
    # Network Isolation
    networks:
      - zeroclaw-isolated
    
    # User
    user: "zeroclaw:zeroclaw"
```

### Secrets-Management

| Methode | Sicherheit | Empfehlung |
|---------|------------|------------|
| Docker Secrets | Hoch | Swarm/Enterprise |
| Env-Variablen | Mittel | Standard |
| Mounted Files | Hoch | Kubernetes |
| Cloud KMS | Sehr Hoch | AWS/GCP/Azure |

### Env-Variablen vs Config-Datei

```toml
# SICHER: Keys in Env, Config ohne Secrets
# config.toml
default_provider = "openai"
# KEIN api_key hier!

[channels_config.telegram]
bot_token = "${TELEGRAM_BOT_TOKEN}"  # Von Env gelesen
```

```bash
# Container-Start mit Secrets
docker run \
  -e ZEROCLAW_API_KEY="$(cat /run/secrets/openai_key)" \
  -e TELEGRAM_BOT_TOKEN="$(cat /run/secrets/telegram_token)" \
  zeroclaw:latest
```

---

## Fehlerbehebung

### Container startet nicht

```bash
# Logs prüfen
docker logs fc-user-001-agent-001

# Config validieren
docker exec fc-user-001-agent-001 zeroclaw doctor

# Berechtigungen prüfen
ls -la /opt/focuscall/workspaces/user-001/agent-001/
```

### Health Check fehlschlägt

```bash
# Manuelle Prüfung
curl -v http://container-ip:port/health

# ZeroClaw Status
docker exec <container> zeroclaw status

# Config-Validierung
docker exec <container> zeroclaw doctor
```

### API-Verbindungsprobleme

```bash
# Provider-Test
docker exec <container> zeroclaw agent -m "test"

# Mit Verbose
docker exec <container> zeroclaw agent -m "test" --verbose
```

### OOM (Out of Memory)

```toml
# config.toml - Ressourcen reduzieren
[agent]
max_history_messages = 20
max_context_tokens = 8000
compact_context = true

[memory]
backend = "sqlite"  # statt lucid
```

### Registry-Probleme

```bash
# Lock-Datei entfernen
rm /opt/focuscall/registry.json.lock

# Registry zurücksetzen
echo '{"next_port":42000,"instances":{}}' > /opt/focuscall/registry.json
```

---

## CLI Referenz

### Grundlegende Befehle

```bash
# Status prüfen
zeroclaw status

# Diagnose
zeroclaw doctor
zeroclaw doctor traces --limit 20

# Gateway starten
zeroclaw gateway
zeroclaw gateway --port 42617

# Daemon (Gateway + Channels)
zeroclaw daemon

# Interaktiver Agent
zeroclaw agent
zeroclaw agent -m "Hello"

# Service Management
zeroclaw service install
zeroclaw service start|stop|restart|status

# Channels
zeroclaw channel list
zeroclaw channel doctor

# Cron
zeroclaw cron list
zeroclaw cron add "*/5 * * * *" --prompt "Check health"

# Memory
zeroclaw memory list
zeroclaw memory stats

# Config Schema
zeroclaw config schema
```

### Onboarding

```bash
# Interaktives Setup
zeroclaw onboard

# Automatisiert
zeroclaw onboard --api-key "sk-..." --provider openrouter

# Nur Channels
zeroclaw onboard --channels-only

# Force overwrite
zeroclaw onboard --force
```

---

## Referenzen

- **GitHub:** https://github.com/zeroclaw-labs/zeroclaw
- **Dokumentation:** https://zeroclawlabs.ai/docs
- **Install:** `curl -fsSL https://raw.githubusercontent.com/zeroclaw-labs/zeroclaw/master/install.sh | bash`
- **Discord:** https://discord.gg/zeroclaw
- **Crates.io:** https://crates.io/crates/zeroclaw

---

## Versions-Historie

| Version | Datum | Notizen |
|---------|-------|---------|
| 0.6.7 | 2026-02 | Hands Multi-Personality, SurrealDB v3 |
| 0.1.7 | 2026-03 | Crates.io Release |

---

*Diese Dokumentation wurde für focuscall.ai erstellt und deckt ZeroClaw v0.6.7 ab.*

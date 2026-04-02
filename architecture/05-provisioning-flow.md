# Provisioning Flow

> Related: [Per-Tenant Architecture](02-per-tenant-architecture.md) | [Tech Stack](06-tech-stack-and-capacity.md) | [ZeroClaw Reference](07-zeroclaw-reference.md) | [README](README.md)

---

## ASCII Flow Diagram

```
User Browser                Supabase                        VPS
     │                         │                             │
     │  Enter bot_token +       │                             │
     │  llm_api_key             │                             │
     │─────────────────────────>│                             │
     │                         │                             │
     │                    Store encrypted                     │
     │                    (row-level security)                │
     │                         │                             │
     │                    Trigger Edge Function               │
     │                         │                             │
     │                         │  POST /provision            │
     │                         │  {user_id, bot_token,       │
     │                         │   llm_key (encrypted)}      │
     │                         │────────────────────────────>│
     │                         │                             │
     │                         │                     webhook listener
     │                         │                     runs provision.sh
     │                         │                             │
     │                         │                     mkdir /opt/focuscall/users/{user_id}/
     │                         │                     write config.toml
     │                         │                     assign port (registry.json)
     │                         │                     systemctl start focuscall@{user_id}
     │                         │                             │
     │                         │                     health check /health
     │                         │                             │
     │                         │  {"status": "running",      │
     │                         │<─ "port": 42003}────────────│
     │                         │                             │
     │                    Update user record:                 │
     │                    provisioned = true                  │
     │                         │                             │
     │  Redirect to dashboard  │                             │
     │<─────────────────────── │                             │
```

---

## Step-by-Step Provisioning Flow

### Step 1: Landing Page Input

The user visits `focuscall.ai` and enters:
- **bot_token** — their Telegram Bot API token (from @BotFather)
- **llm_api_key** — their OpenAI/Anthropic/etc. API key
- Optional: preferred LLM model name

The frontend sends these directly over HTTPS to the Supabase backend. The credentials never pass through any intermediate server unencrypted.

### Step 2: Supabase Stores Credentials Encrypted

Supabase receives the credentials and:
1. Encrypts `bot_token` and `llm_api_key` using Supabase Vault (AES-256)
2. Stores the encrypted values in the `user_instances` table
3. Applies row-level security (RLS) — only the user's own Supabase JWT can read their row
4. Sets `provisioning_status = "pending"`

```sql
-- user_instances table
CREATE TABLE user_instances (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES auth.users(id) NOT NULL,
  bot_token     TEXT NOT NULL,  -- Supabase Vault encrypted
  llm_api_key   TEXT NOT NULL,  -- Supabase Vault encrypted
  llm_model     TEXT DEFAULT 'gpt-4o-mini',
  port          INT,
  status        TEXT DEFAULT 'pending',  -- pending | running | stopped | error
  provisioned_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- RLS: users can only read their own row
ALTER TABLE user_instances ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_instance" ON user_instances
  USING (auth.uid() = user_id);
```

### Step 3: Supabase Edge Function Triggers Webhook

After the insert, a Supabase Edge Function fires:

```typescript
// supabase/functions/provision-trigger/index.ts
import { serve } from "https://deno.land/std/http/server.ts"

serve(async (req) => {
  const { record } = await req.json()  // Postgres webhook payload
  const { user_id, bot_token, llm_api_key, llm_model } = record

  const response = await fetch(Deno.env.get("VPS_WEBHOOK_URL")!, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Provision-Secret": Deno.env.get("PROVISION_SECRET")!,
    },
    body: JSON.stringify({ user_id, bot_token, llm_api_key, llm_model }),
  })

  return new Response(JSON.stringify({ ok: response.ok }), { status: 200 })
})
```

### Step 4: VPS Webhook Listener Receives Call

A lightweight HTTP server (Node.js or Python) runs on the VPS listening on a private port (e.g., 9100, bound to localhost). nginx exposes it only to trusted sources.

```python
# webhook_listener.py (simplified)
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, subprocess, os

PROVISION_SECRET = os.environ["PROVISION_SECRET"]

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        secret = self.headers.get("X-Provision-Secret", "")
        if secret != PROVISION_SECRET:
            self.send_response(403)
            self.end_headers()
            return

        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))

        subprocess.Popen([
            "/opt/focuscall/provision.sh",
            body["user_id"],
            body["bot_token"],
            body["llm_api_key"],
            body.get("llm_model", "gpt-4o-mini"),
        ])

        self.send_response(202)
        self.end_headers()
        self.wfile.write(b'{"status":"provisioning"}')

HTTPServer(("127.0.0.1", 9100), Handler).serve_forever()
```

### Step 5: provision.sh Runs

```bash
#!/usr/bin/env bash
# provision.sh — create and start a focuscall.ai user instance
# Usage: provision.sh {user_id} {bot_token} {llm_api_key} {llm_model}

set -euo pipefail

USER_ID="$1"
BOT_TOKEN="$2"
LLM_API_KEY="$3"
LLM_MODEL="${4:-gpt-4o-mini}"

BASE_DIR="/opt/focuscall/users/${USER_ID}"
REGISTRY="/opt/focuscall/registry.json"

log() { echo "[$(date -u +%FT%TZ)] [provision] $*" | tee -a /opt/focuscall/logs/provision.log; }

# ── Step 5a: Create directory structure ────────────────────────────────────
log "Creating directories for user ${USER_ID}"
mkdir -p "${BASE_DIR}/db"
mkdir -p "${BASE_DIR}/files/uploads"
mkdir -p "${BASE_DIR}/logs"
chown -R focuscall:focuscall "${BASE_DIR}"

# ── Step 5b: Assign next port ───────────────────────────────────────────────
log "Assigning port"
NEXT_PORT=$(jq -r '.next_port' "${REGISTRY}")
jq --arg uid "${USER_ID}" \
   --argjson port "${NEXT_PORT}" \
   '.next_port += 1 | .instances[$uid] = {port: $port, status: "starting", created_at: now | todate}' \
   "${REGISTRY}" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "${REGISTRY}"

# ── Step 5c: Write config.toml ─────────────────────────────────────────────
log "Writing config.toml (port ${NEXT_PORT})"
cat > "${BASE_DIR}/config.toml" <<EOF
[gateway]
port = ${NEXT_PORT}
host = "127.0.0.1"

[bot]
token = "${BOT_TOKEN}"
channel = "telegram"

[llm]
provider = "openai"
api_key = "${LLM_API_KEY}"
model = "${LLM_MODEL}"

[database]
path = "${BASE_DIR}/db"

[ontologies]
path = "/opt/focuscall/ontologies"

[logging]
path = "${BASE_DIR}/logs/zeroclaw.log"
level = "info"
EOF

# ── Step 5d: Start systemd service ─────────────────────────────────────────
log "Starting systemd service focuscall@${USER_ID}"
systemctl enable --now "focuscall@${USER_ID}"

# ── Step 5e: Health check ───────────────────────────────────────────────────
log "Running health check on port ${NEXT_PORT}"
for i in $(seq 1 10); do
    sleep 2
    STATUS=$(curl -sf "http://127.0.0.1:${NEXT_PORT}/health" | jq -r '.status' 2>/dev/null || echo "")
    if [[ "${STATUS}" == "ok" ]]; then
        log "Instance for ${USER_ID} is healthy on port ${NEXT_PORT}"
        jq --arg uid "${USER_ID}" '.instances[$uid].status = "running"' \
           "${REGISTRY}" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "${REGISTRY}"
        exit 0
    fi
    log "Attempt ${i}/10: not yet ready"
done

log "ERROR: Instance for ${USER_ID} failed health check after 20s"
exit 1
```

### Step 6: Health Check Confirmation

ZeroClaw exposes `/health` on its assigned port. The provision script polls this endpoint up to 10 times (20 seconds total). On success, the registry is updated to `running` and Supabase is notified via a callback.

---

## config.toml Template

The full `config.toml` written per user:

```toml
[gateway]
port = 42003         # Unique port from registry (42000 + N)
host = "127.0.0.1"  # Never exposed directly; nginx proxies

[bot]
token = "7491234567:AAF..."  # Telegram bot token
channel = "telegram"          # Channel type

[llm]
provider = "openai"
api_key = "sk-proj-..."
model = "gpt-4o-mini"
temperature = 0.7
max_tokens = 2048

[database]
path = "/opt/focuscall/users/{user_id}/db"
embedded = true

[ontologies]
path = "/opt/focuscall/ontologies"
load = ["core.ttl", "productivity.ttl"]  # Default set; user can extend

[hands]
# Each Hand is a named agent personality
[[hands.personalities]]
name = "ProductivityCoach"
default = true
system_prompt_file = "/opt/focuscall/ontologies/prompts/productivity_coach.md"

[[hands.personalities]]
name = "HealthCoach"
trigger_keywords = ["health", "energy", "medication", "sleep"]
system_prompt_file = "/opt/focuscall/ontologies/prompts/health_coach.md"

[logging]
path = "/opt/focuscall/users/{user_id}/logs/zeroclaw.log"
level = "info"
```

---

## registry.json Structure

```json
{
  "next_port": 42005,
  "instances": {
    "usr_a1b2c3d4": {
      "port": 42000,
      "status": "running",
      "created_at": "2026-01-15T10:30:00Z",
      "systemd_unit": "focuscall@usr_a1b2c3d4.service"
    },
    "usr_e5f6g7h8": {
      "port": 42001,
      "status": "running",
      "created_at": "2026-01-16T14:22:00Z",
      "systemd_unit": "focuscall@usr_e5f6g7h8.service"
    },
    "usr_i9j0k1l2": {
      "port": 42002,
      "status": "stopped",
      "created_at": "2026-01-17T09:15:00Z",
      "systemd_unit": "focuscall@usr_i9j0k1l2.service"
    },
    "usr_m3n4o5p6": {
      "port": 42003,
      "status": "running",
      "created_at": "2026-02-01T08:00:00Z",
      "systemd_unit": "focuscall@usr_m3n4o5p6.service"
    },
    "usr_q7r8s9t0": {
      "port": 42004,
      "status": "error",
      "created_at": "2026-02-15T11:45:00Z",
      "systemd_unit": "focuscall@usr_q7r8s9t0.service",
      "error": "health check timeout after 20s"
    }
  }
}
```

Note: Ports from stopped/deprovisioned instances are **not reused** (to avoid routing confusion). The port range 42000–43999 gives 2000 slots per server.

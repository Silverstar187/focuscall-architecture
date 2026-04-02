# focuscall.ai Provisioning System

Vollstaendiges Provisioning-System fuer focuscall.ai auf Hetzner CAX21 (ARM64).
**Architektur: 1 Docker Container pro User-Agent-Paar** — vollstaendig isoliert, mit eigenem Port und Ressourcen-Limits.

Keys werden verschluesselt in Supabase Vault gespeichert und NUR als Docker ENV-Variablen
an ZeroClaw-Container uebergeben — nie auf VPS-Disk.

---

## Architektur-Ueberblick

### Multi-Container Design: 1 Container = 1 Agent

Anders als viele andere Systeme, die einen einzelnen Container mit mehreren Agent-Instanzen nutzen,
startet ZeroClaw für **jeden Agenten einen eigenen Docker Container**. Das bietet:

- **Vollständige Isolation**: Ein abstürzender Agent beeinflusst keine anderen
- **Ressourcen-Garantien**: Jeder Container hat fixe Limits (128MB RAM, 0.5 CPU)
- **Unabhängige Updates**: Einzelne Agenten können neu gestartet werden
- **Sicherheit**: API Keys existieren nur im jeweiligen Container Memory

### System-Flow

```
User Browser
    │
    │  POST {llm_key, bot_token, user_id, agent_id, llm_provider}
    ▼
Supabase Edge Function (provision-agent)
    │
    ├─► Supabase Vault: store encrypted(llm_key), encrypted(bot_token)
    │
    │  POST https://vps.focuscall.ai/provision
    │  Headers: X-Timestamp, X-Signature (HMAC-SHA256)
    │  Body: {user_id, agent_id, llm_key, bot_token, llm_provider}
    ▼
nginx (SSL termination)
    │
    │  proxy_pass http://127.0.0.1:9000
    ▼
FastAPI Webhook Receiver (webhook-receiver.py)
    │
    ├─► Validate X-Timestamp (replay protection: max 5 min)
    ├─► Validate X-Signature (HMAC-SHA256 over user_id:agent_id:timestamp)
    │
    │  BackgroundTasks.add_task(provision_container(...))
    │  Returns 202 Accepted immediately
    ▼
provision.py (Docker SDK)
    │
    ├─► Registry lock (fcntl) → allocate port (42000+N)
    ├─► mkdir /opt/focuscall/workspaces/{user_id}/{agent_id}/
    ├─► Render config.toml from template (NO keys in file)
    │
    │  docker.containers.run(
    │    image="zeroclaw:latest",
    │    name="fc-{user_id}-{agent_id}",
    │    environment={
    │      ZEROCLAW_API_KEY: llm_key,      ← key stays in memory only
    │      TELEGRAM_BOT_TOKEN: bot_token,  ← key stays in memory only
    │    },
    │    security_opt=["no-new-privileges"],
    │    cap_drop=["ALL"],
    │    read_only=True,
    │    mem_limit="128m",
    │    nano_cpus=500_000_000,
    │  )
    │
    ├─► Health check: GET http://{container_ip}:{port}/health (10x, 2s)
    └─► Registry update: status = "running" or "error"
```

---

## Voraussetzungen

- Hetzner CAX21 (ARM64, Ubuntu 24.04 LTS empfohlen)
- Docker Engine 24+ und Docker Compose v2
- Python 3.11 (fuer lokale Tests; im Container automatisch)
- nginx mit SSL-Zertifikat (Let's Encrypt)
- Supabase Projekt mit aktiviertem Vault und Edge Functions

---

## Schritt 1: ZeroClaw Image bauen

```bash
cd /opt/focuscall/provisioning

# Auf ARM64 Host direkt:
docker build -t zeroclaw:latest .

# Cross-compile von x86_64 fuer ARM64:
docker buildx build --platform linux/arm64 -t zeroclaw:latest .
```

Der Build-Prozess klont ZeroClaw von GitHub und kompiliert mit `cargo build --release`.
Dauer auf CAX21: ca. 3-5 Minuten (Rust-Kompilierung).

---

## Schritt 2: Verzeichnisse anlegen

```bash
# Workspace-Basis und Registry erstellen
sudo mkdir -p /opt/focuscall/workspaces
sudo chown -R $USER:$USER /opt/focuscall

# Registry initialisieren (leer)
echo '{"next_port": 42000, "instances": {}}' > /opt/focuscall/registry.json

# Provisioning-Dateien deployen
sudo mkdir -p /opt/focuscall/provisioning
sudo cp webhook-receiver.py provision.py config.toml.tmpl /opt/focuscall/provisioning/
```

---

## Schritt 3: WEBHOOK_SECRET generieren

```bash
# Zufaelliger 32-Byte Hex-String — muss auf VPS und in Supabase identisch sein
openssl rand -hex 32
# Beispiel-Output: a3f8e2d1b4c9087654321fedcba98765a3f8e2d1b4c9087654321fedcba98765

# Sicher speichern, z.B. in /etc/focuscall/.env
sudo mkdir -p /etc/focuscall
sudo chmod 700 /etc/focuscall
echo "WEBHOOK_SECRET=<generated-secret>" | sudo tee /etc/focuscall/.env
sudo chmod 600 /etc/focuscall/.env
```

---

## Schritt 4: Webhook Receiver starten

```bash
cd /opt/focuscall/provisioning

# Secret aus gesicherter Datei laden
source /etc/focuscall/.env

# Starten
WEBHOOK_SECRET=$WEBHOOK_SECRET docker compose -f docker-compose.infra.yml up -d

# Status pruefen
docker compose -f docker-compose.infra.yml ps
docker compose -f docker-compose.infra.yml logs -f webhook-receiver
```

---

## Schritt 5: nginx konfigurieren

```nginx
# /etc/nginx/sites-available/focuscall-provision

server {
    listen 443 ssl;
    server_name vps.focuscall.ai;

    ssl_certificate     /etc/letsencrypt/live/vps.focuscall.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vps.focuscall.ai/privkey.pem;

    # Provisioning endpoint — only accessible via HTTPS
    location /provision {
        proxy_pass         http://127.0.0.1:9000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }

    # Health check (optional — for monitoring)
    location /webhook-health {
        proxy_pass http://127.0.0.1:9000/health;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/focuscall-provision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Schritt 6: Supabase Edge Function deployen

```bash
# Supabase CLI installieren falls nicht vorhanden
npm install -g supabase

# Supabase Projekt verknuepfen
supabase link --project-ref <your-project-ref>

# Edge Function deployen
supabase functions deploy provision-agent \
  --project-ref <your-project-ref>
```

---

## Schritt 7: Supabase ENV setzen

Im Supabase Dashboard unter **Settings > Edge Functions > Secrets** oder via CLI:

```bash
supabase secrets set VPS_WEBHOOK_URL=https://vps.focuscall.ai \
  --project-ref <your-project-ref>

supabase secrets set WEBHOOK_SECRET=<generated-secret-from-step-3> \
  --project-ref <your-project-ref>
```

Folgende Secrets werden automatisch von Supabase injiziert (kein manuelles Setzen noetig):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

---

## Schritt 8: Testen

```bash
# Health check des Receivers
curl https://vps.focuscall.ai/webhook-health

# Provisioning ausfuehren (Beispiel — normalerweise von Edge Function ausgeloest)
TIMESTAMP=$(date +%s)
USER_ID="test-user-001"
AGENT_ID="agent-001"
WEBHOOK_SECRET="<your-secret>"

SIGNATURE=$(echo -n "${USER_ID}:${AGENT_ID}:${TIMESTAMP}" | \
  openssl dgst -sha256 -hmac "${WEBHOOK_SECRET}" -hex | awk '{print $2}')

curl -X POST https://vps.focuscall.ai/provision \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Signature: ${SIGNATURE}" \
  -d "{
    \"user_id\": \"${USER_ID}\",
    \"agent_id\": \"${AGENT_ID}\",
    \"llm_key\": \"sk-test-...\",
    \"bot_token\": \"7491234567:AAF...\",
    \"llm_provider\": \"openai\"
  }"

# Erwartete Antwort (202):
# {"status": "provisioning", "user_id": "test-user-001", "agent_id": "agent-001"}

# Alle Instanzen anzeigen
curl https://vps.focuscall.ai/instances
```

---

## Deprovision

```bash
TIMESTAMP=$(date +%s)
USER_ID="test-user-001"
AGENT_ID="agent-001"

SIGNATURE=$(echo -n "${USER_ID}:${AGENT_ID}:${TIMESTAMP}" | \
  openssl dgst -sha256 -hmac "${WEBHOOK_SECRET}" -hex | awk '{print $2}')

curl -X DELETE "https://vps.focuscall.ai/provision/${USER_ID}/${AGENT_ID}" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Signature: ${SIGNATURE}"

# Erwartete Antwort (200):
# {"status": "removed", "user_id": "test-user-001", "agent_id": "agent-001"}
```

---

## Security-Hinweise

**Keys bleiben sicher:**
- LLM API Keys und Bot Tokens werden in Supabase Vault (pgsodium AES-256-GCM) verschluesselt gespeichert
- Im Webhook-Payload: gesichert durch HTTPS + HMAC-SHA256 Signatur + Timestamp (Replay-Schutz 5 min)
- Auf dem VPS: werden NUR als Docker ENV-Variablen weitergereicht — nie auf Disk geschrieben
- Im Container: ZeroClaw liest Keys aus ENV — `config.toml` enthaelt keine Secrets

**Container Security:**
- `no-new-privileges` — verhindert Privilege Escalation
- `cap_drop: ALL` — keine Linux Capabilities
- `read_only: true` — Root-Filesystem read-only (`/tmp` als tmpfs)
- Memory limit: 128 MB, CPU limit: 0.5 Cores
- Nicht-root User (`zeroclaw`) im Container

**Webhook Security:**
- HMAC-SHA256 Signatur ueber `{user_id}:{agent_id}:{timestamp}`
- Timestamp-Validation: Requests aelter als 5 Minuten werden abgelehnt
- HTTPS-Only: nginx SSL termination, kein HTTP-Fallback

**Zugriffskontrolle:**
- Port 9000 nur auf localhost gebunden — kein direkter externer Zugriff
- nginx als einziger Einstiegspunkt mit SSL

---

## Dateistruktur

```
/opt/focuscall/
├── registry.json               — Port-Registry (next_port + instances)
├── workspaces/
│   └── {user_id}/
│       └── {agent_id}/
│           ├── config.toml     — ZeroClaw config (KEIN Secret-Inhalt)
│           ├── db/             — Embedded SurrealDB
│           └── logs/
│               └── zeroclaw.log
├── provisioning/
│   ├── webhook-receiver.py
│   ├── provision.py
│   ├── config.toml.tmpl
│   ├── docker-compose.infra.yml
│   └── Dockerfile
```

---

## Troubleshooting

**Container startet nicht:**
```bash
docker logs fc-{user_id}-{agent_id}
```

**HMAC-Validation schlaegt fehl:**
- Sicherstellen dass WEBHOOK_SECRET auf VPS und in Supabase identisch ist
- Timestamp des anfragenden Systems pruefen (NTP sync)

**Health Check schlaegt fehl:**
- ZeroClaw braucht ca. 5-10s zum Start
- Pruefen ob Port korrekt in config.toml gesetzt ist
- `docker exec fc-{user_id}-{agent_id} curl localhost:{port}/health`

**Registry gesperrt:**
- Lock-Datei entfernen falls Prozess abgebrochen: `rm /opt/focuscall/registry.json.lock`

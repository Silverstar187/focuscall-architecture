# ZeroClaw — Projektdokumentation

## Was ist ZeroClaw?

ZeroClaw ist ein KI-Agent-Framework in Rust von zeroclaw-labs. Es ist der Nachfolger von OpenClaw (NullClaw). Im Gegensatz zu OpenClaw (Node.js, ~180MB RAM) ist ZeroClaw:
- ~2.1 MB Binary
- 8–25 MB RAM im Idle
- 15 ms Cold Start
- ARM64/aarch64-kompatibel (läuft nativ auf Hetzner CAX-Servern)
- Konfiguration via TOML statt JSON

**Version:** 0.1.7 (Stand 2026-03-30)
**Crates.io:** https://crates.io/crates/zeroclaw

---

## Installation auf Hetzner

**Server:** 91.99.209.45 (Hetzner CAX21, ARM64, 8 GB RAM)
**SSH:** `ssh -i ~/.ssh/openclaw_nopass root@91.99.209.45`

Binary liegt unter: `~/.cargo/bin/zeroclaw`
Config liegt unter: `~/.zeroclaw/config.toml`

PATH dauerhaft setzen:
```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
zeroclaw --version  # zeroclaw 0.1.7
```

Für systemd-Service:
```bash
zeroclaw service install
systemctl status zeroclaw
```

---

## Konfiguration

**Datei:** `~/.zeroclaw/config.toml`

### Wichtige Abschnitte

```toml
# Provider & Modell
default_provider = "custom:https://api.moonshot.ai/v1"
default_model = "moonshot-v1-8k"
default_temperature = 1.0

# Gateway (WebSocket + Webhook)
[gateway]
port = 42617
host = "0.0.0.0"
require_pairing = true          # Auth via Pairing-Token
allow_public_bind = true
trust_forwarded_headers = true  # Für nginx trusted-proxy Setup
paired_tokens = []              # Tokens werden nach Pairing automatisch befüllt
```

### Unterstützte native Provider

| Provider-Key | Endpoint |
|---|---|
| `openai` | api.openai.com |
| `anthropic` | api.anthropic.com |
| `google` | generativelanguage.googleapis.com |
| `groq` | api.groq.com |
| `mistral` | api.mistral.ai |
| `moonshot` | api.moonshot.cn ⚠️ (China-Endpoint — passt nicht zu unserem Key) |
| `custom:<url>` | beliebiger OpenAI-kompatibler Endpoint |

**Env-Vars für Provider:**
- Native Provider: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, etc.
- Custom Provider: `ZEROCLAW_API_KEY` (universell für alle `custom:*` Provider)

---

## Aktueller Status: Moonshot-Connectivity-Problem

**Problem:** Der `custom:` Provider von ZeroClaw sendet Null-Felder in JSON-Requests (z.B. `"max_tokens": null`). Moonshot API lehnt diese mit `400 invalid scalar type [number null]` ab.

**API-Key:** `sk-uAQANa7OiL8FGcV4ct6ykbxixDrNnPEa9zeOhRvEDv6xOKPw` (direkt curl-verified)
**OpenRouter:** kein Guthaben — nicht verfügbar

### Lösung: Null-Strip-Proxy

Ein kleiner Python-Proxy auf dem Hetzner-Server filtert Null-Felder heraus, bevor die Anfrage an Moonshot geht. ZeroClaw wird auf diesen Proxy als Custom-Provider zeigen.

**Proxy-Script** `/root/moonshot-proxy/proxy.py`:
```python
#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

MOONSHOT_BASE = "https://api.moonshot.ai/v1"
API_KEY = os.environ["MOONSHOT_API_KEY"]

def strip_nulls(obj):
    if isinstance(obj, dict):
        return {k: strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_nulls(i) for i in obj]
    return obj

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            data = strip_nulls(json.loads(body))
        except Exception:
            data = body

        req = urllib.request.Request(
            MOONSHOT_BASE + self.path,
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                content = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            content = e.read()
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(content)

    def log_message(self, fmt, *args):
        pass  # silent

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9999), ProxyHandler).serve_forever()
```

**Starten:**
```bash
MOONSHOT_API_KEY=sk-uAQANa7OiL8FGcV4ct6ykbxixDrNnPEa9zeOhRvEDv6xOKPw python3 /root/moonshot-proxy/proxy.py &
```

**ZeroClaw Config anpassen:**
```toml
default_provider = "custom:http://localhost:9999"
default_model = "moonshot-v1-8k"
```
`ZEROCLAW_API_KEY` auf irgendeinen Dummy-Wert setzen (Proxy ignoriert es, Moonshot-Key ist im Proxy).

**Als systemd-Service:**
```ini
[Unit]
Description=Moonshot Null-Strip Proxy
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/moonshot-proxy/proxy.py
Environment=MOONSHOT_API_KEY=sk-uAQANa7OiL8FGcV4ct6ykbxixDrNnPEa9zeOhRvEDv6xOKPw
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Gateway starten

```bash
zeroclaw gateway
# Läuft auf Port 42617, gebunden an 0.0.0.0
```

Pairing-URL (für ersten Connect):
```
http://91.99.209.45:42617/pair
```

Danach erscheint ein Token in `~/.zeroclaw/config.toml` unter `[gateway] paired_tokens`.

---

## Multi-Tenant: Was ZeroClaw v0.1.7 NICHT kann

**ZeroClaw v0.1.7 ist kein Multi-Tenant-System.** Ein Prozess = eine Workspace = eine Memory-Datenbank für alle.

- `trust_forwarded_headers = true` betrifft nur Rate-Limiting (IP-Weitergabe durch Proxies) — keine Session-Isolation per User
- `brain.db` ist eine geteilte SQLite-Datenbank; `session_id`-Spalte existiert für Konversations-Fortsetzung, aber ohne Zugriffskontrolle zwischen Usern
- Multi-Tenancy (ein Prozess, N isolierte Workspaces) ist als Draft-Proposal (Issue #2765) geplant, aber in v0.1.7 nicht implementiert

### Was Multi-Tenant heute bedeuten würde

**Einzige funktionierende Option:** Ein ZeroClaw-Prozess pro User, mit separatem Workspace-Verzeichnis und Port.

```bash
# User A
ZEROCLAW_WORKSPACE=/data/users/uuid-a ~/.cargo/bin/zeroclaw gateway --port 42001

# User B
ZEROCLAW_WORKSPACE=/data/users/uuid-b ~/.cargo/bin/zeroclaw gateway --port 42002
```

nginx routet dann basierend auf JWT-Sub zum richtigen Port. Das ist technisch möglich, skaliert aber nicht für viele User.

### Fazit: ZeroClaw ist heute Single-Tenant

ZeroClaw macht Sinn für **einen Operator** (= dich persönlich auf dem Hetzner-Server) mit Telegram-Bots und direktem CLI-Zugang. Für **Web-Chat mit mehreren Usern** ist OpenClaw auf Hostinger weiterhin die richtige Wahl — der hat `trusted-proxy` Mode der genau für diesen Use Case gebaut ist.

---

## Telegram-Bots konfigurieren

In `~/.zeroclaw/config.toml`:

```toml
[channels_config.telegram]
enabled = true
bots = [
  { token = "BOT_TOKEN_1", allow_from = ["+4917664021045"] },
  { token = "BOT_TOKEN_2", allow_from = ["+4917132500033"] },
  { token = "BOT_TOKEN_3", allow_from = ["*"] },  # open bot
]
```

Oder via Umgebungsvariablen für Secrets.

---

## Deployment-Checkliste

- [x] ZeroClaw v0.1.7 installiert (`~/.cargo/bin/zeroclaw`)
- [x] Config generiert (`~/.zeroclaw/config.toml`)
- [ ] PATH-Fix dauerhaft in ~/.bashrc
- [ ] Moonshot-Proxy aufsetzen (`/root/moonshot-proxy/proxy.py`)
- [ ] ZeroClaw Config auf `custom:http://localhost:9999` umstellen
- [ ] Gateway starten + Pairing durchführen
- [ ] Gateway als systemd-Service einrichten (`zeroclaw service install`)
- [ ] Moonshot-Proxy als systemd-Service einrichten
- [ ] Firewall: Port 42617 für nginx-intern freigeben (NICHT public)
- [ ] nginx: `/zeroclaw/`-Block mit JWT-Validierung und X-Forwarded-User

---

## Migrationsstrategie: OpenClaw → ZeroClaw

| Kanal | Hostinger (jetzt) | Hetzner (Ziel) |
|---|---|---|
| Web-Chat | OpenClaw `trusted-proxy` Port 18789 | ZeroClaw Port 42617 |
| Telegram | 4 Bots via OpenClaw | 4 Bots via ZeroClaw |
| Voice | Twilio via OpenClaw Plugin | ZeroClaw Channels (TBD) |
| Supabase | Hostinger, bleibt dort | Hostinger, bleibt dort |

**Migration-Reihenfolge:**
1. ZeroClaw Gateway live + Pairing ✓ (sobald Moonshot-Proxy läuft)
2. Telegram-Bots auf ZeroClaw migrieren (ein Bot nach dem anderen)
3. Web-Chat umstellen (nginx auf Hetzner zeigen)
4. Voice: klären ob ZeroClaw Voice-Plugin hat

OpenClaw auf Hostinger bleibt als Fallback bis ZeroClaw stabil läuft.

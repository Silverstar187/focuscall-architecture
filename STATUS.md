# Status — Stand 2026-04-02

## Was funktioniert

- **ZeroClaw Docker Image** (`zeroclaw:latest`) gebaut auf Hetzner CAX21 (ARM64)
  - Rust 1.88, multi-stage build, 44MB Image
  - Source: https://github.com/zeroclaw-labs/zeroclaw v0.6.7

- **Container startet und läuft:**
  ```
  🧠 Starting ZeroClaw Daemon on 127.0.0.1:42001
  Telegram channel listening for messages...
  Gateway session persistence enabled (SQLite)
  ```

- **Webhook Receiver** läuft als systemd Service auf Port 9000
  - FastAPI, HMAC-SHA256 Signatur-Validierung
  - `curl http://localhost:9000/health` → `{"status":"ok"}`

- **Provisioning-Script** (`provision.py`) — Docker SDK, Port-Registry, Keys als ENV

## Bekannte Einschränkungen (TODO)

- `--read-only` Container-Flag deaktiviert — ZeroClaw braucht Schreibzugriff im Workspace.
  Workaround: Workspace-Verzeichnis mit `chmod 777` anlegen (läuft dann sauber).
  Fix: Dockerfile USER anpassen + Workspace-Init-Script.

- `TELEGRAM_BOT_TOKEN=KEIN_ECHTER_TOKEN` im Testcontainer — braucht echten Token für Produktivbetrieb.

- OpenRouter Warmup schlägt fehl (non-fatal) — OpenRouter Key aus alter Session, ggf. abgelaufen.
  Für Produktion: User gibt eigenen Key ein → wird via ENV injiziert.

## Server

- Hetzner CAX21: `91.99.209.45`
- SSH: `ssh -i ~/.ssh/openclaw_nopass root@91.99.209.45`
- Docker: v29.3.1
- ZeroClaw Image: `zeroclaw:latest` (44MB, ARM64)
- Webhook Receiver: `systemctl status focuscall-webhook`

## Nächste Schritte

1. Echten Telegram Bot Token einbinden → Produktionstest
2. Supabase Edge Function deployen
3. `chmod 777` durch sauberes User-Mapping ersetzen (Dockerfile: `USER` + Entrypoint-Script)
4. Terraform für reproduzierbares Server-Setup

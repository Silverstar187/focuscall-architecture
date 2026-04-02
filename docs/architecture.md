# ZeroClaw Multi-Container Architektur

## Überblick

ZeroClaw verwendet eine **1-Container-pro-Agent** Architektur. Jeder Agent läuft in einem isolierten Docker Container mit eigenen Ressourcen, eigenem Port und eigenem Datenspeicher.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Hetzner VPS (CAX21)                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Webhook Receiver (Port 9000)                     │   │
│  │  FastAPI + provision.py ─ empfängt Signale von Supabase             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│          ┌───────────────────────────┼───────────────────────────┐          │
│          │                           │                           │          │
│          ▼                           ▼                           ▼          │
│  ┌───────────────┐          ┌───────────────┐          ┌───────────────┐   │
│  │ Container 1   │          │ Container 2   │          │ Container N   │   │
│  │               │          │               │          │               │   │
│  │ fc-alice-     │          │ fc-bob-       │          │ fc-eve-       │   │
│  │ productivity  │          │ salescoach    │          │ supportbot    │   │
│  │               │          │               │          │               │   │
│  │ Port: 42000   │          │ Port: 42001   │          │ Port: 42xxx   │   │
│  │               │          │               │          │               │   │
│  │ Env:          │          │ Env:          │          │ Env:          │   │
│  │ • OPENAI_KEY  │          │ • ANTHROPIC   │          │ • OPENAI_KEY  │   │
│  │ • BOT_TOKEN   │          │ • BOT_TOKEN   │          │ • BOT_TOKEN   │   │
│  │               │          │               │          │               │   │
│  │ Volume:       │          │ Volume:       │          │ Volume:       │   │
│  │ /workspace    │          │ /workspace    │          │ /workspace    │   │
│  └───────────────┘          └───────────────┘          └───────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Warum 1 Container pro Agent?

| Vorteil | Beschreibung |
|---------|-------------|
| **Isolation** | Jeder Agent läuft komplett getrennt – ein Crash beeinflusst andere nicht |
| **Ressourcen-Limits** | Pro Container: 128MB RAM, 0.5 CPU – faire Verteilung |
| **Sicherheit** | Keys sind nur im Container Memory, nie auf Host-Disk |
| **Skalierbarkeit** | Horizontal skalierbar auf mehrere Server |
| **Updates** | Einzelne Agenten können neu gestartet werden |

## Container Lebenszyklus

```
User erstellt Agent in UI
        │
        ▼
┌───────────────────┐
│ Supabase Vault    │ ◄── Speichert verschlüsselte Keys
│ (LLM Key, Token)  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Edge Function     │ ──► Entschlüsselt Keys
│ provision-agent   │ ──► Sendet Webhook mit Keys
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ VPS:9000          │ ──► HMAC-Validierung
│ webhook-receiver  │ ──► Background Task startet
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ provision.py      │ ──► Port aus Registry allocieren
│                   │ ──► Workspace anlegen
│                   │ ──► Docker Container starten
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Docker Container  │ ◄── Container läuft!
│ fc-{user}-{agent} │ ◄── Health Check alle 2s
└───────────────────┘
```

## Registry & Port-Management

Die `registry.json` verwaltet alle laufenden Instanzen:

```json
{
  "next_port": 42002,
  "instances": {
    "alice-productivitycoach": {
      "port": 42000,
      "status": "running",
      "container_name": "fc-alice-productivitycoach",
      "container_id": "a1b2c3d4e5f6",
      "created_at": "2026-04-02T10:30:00Z"
    },
    "bob-salescoach": {
      "port": 42001,
      "status": "running",
      "container_name": "fc-bob-salescoach",
      "container_id": "b2c3d4e5f6a7",
      "created_at": "2026-04-02T11:00:00Z"
    }
  }
}
```

- **Port-Range**: 42000+ (jeder Container bekommt einen eindeutigen Port)
- **Thread-sicher**: `fcntl`-Locks verhindern Race Conditions
- **Persistenz**: Registry wird auf Disk gespeichert, überlebt Neustarts

## Workspace-Struktur

Jeder Container hat ein eigenes Verzeichnis:

```
/opt/focuscall/workspaces/
├── alice/
│   └── productivitycoach/
│       ├── config.toml      # ZeroClaw Config (KEINE Secrets!)
│       ├── db/
│       │   └── surreal.db   # Embedded Datenbank
│       └── logs/
│           └── zeroclaw.log # Container Logs
│
└── bob/
    └── salescoach/
        ├── config.toml
        ├── db/
        └── logs/
```

## Security Modell

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Supabase  │───▶│  HTTPS +    │───▶│   Docker    │───▶│  Container  │
│    Vault    │    │  HMAC-Sig   │    │    ENV      │    │   Memory    │
│  (AES-256)  │    │  (Replay)   │    │  (Runtime)  │    │  (Nur ENV)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
  Verschlüsselt      Signiert +         Niemals auf        Keys nur im
  gespeichert        Zeitstempel         Disk geschrieben   Container RAM
```

## Container Constraints

Jeder Agent-Container läuft mit folgenden Limits:

```python
{
    "mem_limit": "128m",           # Max 128 MB RAM
    "nano_cpus": 500_000_000,      # Max 0.5 CPU Cores
    "read_only": True,             # Root-Filesystem read-only
    "cap_drop": ["ALL"],           # Keine Linux Capabilities
    "security_opt": ["no-new-privileges"],  # Keine Privilege Escalation
    "restart_policy": {"Name": "unless-stopped"},  # Auto-restart
}
```

## Health Checks

Nach dem Start wird der Container überwacht:

```
Attempt 1/10: GET http://{container_ip}:{port}/health
    ↓ (2 Sekunden Pause)
Attempt 2/10: GET http://{container_ip}:{port}/health
    ↓ ...
Attempt 10/10: GET http://{container_ip}:{port}/health
    ↓
✅ Healthy → Status: "running"
❌ Failed → Container wird gestoppt & entfernt, Status: "error"
```

## API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/provision` | POST | Neuen Container starten |
| `/provision/{user}/{agent}` | DELETE | Container stoppen & entfernen |
| `/instances` | GET | Alle Container auflisten |
| `/health` | GET | Webhook Receiver Health |

## Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
docker logs fc-{user_id}-{agent_id}

# Health Check manuell testen
docker exec fc-{user_id}-{agent_id} curl localhost:{port}/health

# Registry prüfen
cat /opt/focuscall/registry.json | jq
```

### Port bereits belegt

```bash
# Registry zurücksetzen (nur wenn nötig!)
echo '{"next_port": 42000, "instances": {}}' > /opt/focuscall/registry.json

# Alle Container stoppen
docker stop $(docker ps -q --filter "name=fc-")
docker rm $(docker ps -aq --filter "name=fc-")
```

### Lock-Datei hängt

```bash
# Falls provision.py abgebrochen wurde:
rm /opt/focuscall/registry.json.lock
```

## Vergleich: Multi-Container vs Single Container

| Aspekt | Multi-Container (ZeroClaw) | Single Container |
|--------|---------------------------|------------------|
| **Isolation** | ✅ Vollständig | ❌ Shared Process |
| **Ressourcen** | ✅ Pro-Container Limits | ❌ Shared Limits |
| **Skalierung** | ✅ Horizontal (mehrere Server) | ⚠️ Vertikal (mehr RAM/CPU) |
| **Fehlertoleranz** | ✅ Ein Crash = Ein Agent down | ❌ Ein Crash = Alle Agenten down |
| **Memory Overhead** | ⚠️ ~10MB pro Container | ✅ Kein Overhead |
| **Startzeit** | ⚠️ ~5-10s | ✅ Sofort |

## Zukunft: Hyperscaling

Für sehr viele Agenten (>100) können mehrere VPS parallel betrieben werden:

```
┌─────────────────┐
│   Load Balancer │
│   (Round Robin) │
└────────┬────────┘
         │
    ┌────┼────┬────────┐
    ▼    ▼    ▼        ▼
┌─────┐┌─────┐┌─────┐ ┌─────┐
│VPS 1││VPS 2││VPS 3│...│VPS N│
│CAX21││CAX21││CAX21│ │CAX21│
│~50  ││~50  ││~50  │ │~50  │
│Agent││Agent││Agent│ │Agent│
└─────┘└─────┘└─────┘ └─────┘
```

Terraform unterstützt bereits das Deployen mehrerer Server via `count` Parameter.

# ZeroClaw / focuscall.ai

KI-Agent Infrastructure für Telegram-Bot Coaching auf Basis von [ZeroClaw](https://github.com/b0xtch/zeroclaw).

---

## 📁 Repository Struktur

```
~/ZeroClaw/
├── 📂 architecture/          # System-Architektur & Konzepte
├── 📂 provisioning/          # Produktions-Code für Deployment
├── 📂 docs/                  # Zusätzliche Dokumentation
└── 📂 planning/              # Planungs-Dokumente & Tasks
```

### architecture/
High-level Architektur-Dokumente für das focuscall.ai System:

| Datei | Beschreibung |
|-------|--------------|
| `01-vision.md` | Produktvision & Zielgruppe |
| `02-per-tenant-architecture.md` | Multi-Tenant Konzept |
| `03-knowledge-graph.md` | Knowledge Graph für persönlichen Kontext |
| `04-multi-agent-personalities.md` | Verschiedene Agent-Persönlichkeiten |
| `05-provisioning-flow.md` | Provisioning-Prozess (Legacy - systemd) |
| `06-tech-stack-and-capacity.md` | Tech Stack & Server-Kapazität |
| `07-zeroclaw-reference.md` | ZeroClaw Config & CLI Referenz |

### provisioning/
Produktionsreifer Code für Docker-basiertes Provisioning auf Hetzner CAX21 (ARM64):

| Datei | Zweck |
|-------|-------|
| `edge-function.ts` | Supabase Edge Function (Deno) - speichert Keys in Vault, sendet HMAC-Webhook |
| `webhook-receiver.py` | FastAPI Webhook Receiver - validiert HMAC, triggert Provisioning |
| `provision.py` | Docker SDK Logik - erstellt/entfernt Container mit Security-Constraints |
| `Dockerfile` | Multi-stage Build für ZeroClaw (ARM64-kompatibel) |
| `config.toml.tmpl` | ZeroClaw Config Template (Keys kommen aus ENV) |
| `docker-compose.infra.yml` | Infra-Compose für Webhook-Receiver |
| `README.md` | Deployment-Anleitung |

**Security-Prinzip:** Keys (LLM API Key, Bot Token) werden **niemals auf Disk** geschrieben – nur in Supabase Vault und als Docker ENV-Variablen.

### docs/
Zusätzliche Dokumentation:
- `zeroclaw.md` — ZeroClaw Grundlagen (aus OnlyPlans-Projekt)

### planning/
Planungs-Dokumente für Quick Tasks:
- `260401-92r-CONTEXT.md` — Task-Kontext & Entscheidungen
- `260401-92r-PLAN.md` — Ausführungsplan

---

## 🔗 Symlinks

Die alten Pfade sind als Symlinks erhalten:

```bash
~/focuscall-architecture          → ~/ZeroClaw/architecture
~/OnlyPlans/.planning/quick/...   → ~/ZeroClaw/planning
```

---

## 🚀 Quick Start

1. **ZeroClaw Image bauen:**
   ```bash
   cd ~/ZeroClaw/provisioning
   docker build -t zeroclaw:latest .
   ```

2. **Infra starten:**
   ```bash
   docker compose -f docker-compose.infra.yml up -d
   ```

3. **Edge Function deployen:**
   ```bash
   cd ~/ZeroClaw/provisioning
   supabase functions deploy provision-agent
   ```

Siehe `provisioning/README.md` für vollständige Anleitung.

---

## 🔐 Security Highlights

- ✅ Supabase Vault für Key-Storage (pgsodium-verschlüsselt)
- ✅ HMAC-SHA256 für Webhook-Authentifizierung
- ✅ Docker Container mit `no-new-privileges`, `cap-drop ALL`, `read-only`
- ✅ Resource-Limits: 128MB RAM, 0.5 CPU pro Container
- ✅ Keys nur als ENV-Variablen – nie auf VPS-Disk

---

## 📅 Letzte Aktualisierung

2026-04-01 — Quick Task 260401-92r: Vollständiges Provisioning-System erstellt

---

*ZeroClaw Version: 0.1.7 | Server: Hetzner CAX21 (ARM64, 8GB RAM)*

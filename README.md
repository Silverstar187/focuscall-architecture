# 🎯 focuscall.ai

> KI-Agent Infrastructure für Telegram-Bot Coaching auf Basis von [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw).

---

## 📁 Repository Struktur

```
~/ZeroClaw/
├── 📂 architecture/          # System-Architektur & Konzepte
├── 📂 provisioning/          # Produktions-Code für Deployment
│   ├── edge-function.ts      # Supabase Edge Function (Deno)
│   ├── webhook-receiver.py   # FastAPI Webhook Receiver
│   ├── provision.py          # Docker SDK Logik
│   ├── Dockerfile            # ZeroClaw Image Build
│   ├── config.toml.tmpl      # Config Template
│   └── docker-compose.infra.yml
├── 📂 docs/                  # Zusätzliche Dokumentation
│   └── kimi-cli.md           # 🤖 Kimi Code CLI (ACP/MCP)
├── 📂 planning/              # Planungs-Dokumente & Tasks
├── AGENT_CONTEXT.md          # 🤖 Für KI-Agenten (System-Context)
├── AGENT_QUICKREF.md         # 🚀 Kurzreferenz für Agenten
└── README.md                 # Diese Datei
```

---

## 🚀 Quick Start

### 1. ZeroClaw Image bauen
```bash
cd ~/ZeroClaw/provisioning
docker build -t zeroclaw:latest .
```

### 2. Infra starten
```bash
docker compose -f docker-compose.infra.yml up -d
```

### 3. Edge Function deployen
```bash
cd ~/ZeroClaw/provisioning
supabase functions deploy provision-agent
```

---

## 🤖 Für Agenten

Wenn du ein Agent bist, der auf diesem System läuft:

→ Lies [**AGENT_CONTEXT.md**](AGENT_CONTEXT.md) für den vollständigen System-Überblick

→ Oder die Kurzversion: [**AGENT_QUICKREF.md**](AGENT_QUICKREF.md)

**Wichtig:** Du läufst in einer isolierten Docker Sandbox mit 128MB RAM!

---

## 📚 Dokumentation

Vollständige Dokumentation im Obsidian Vault:
```
~/Documents/ObsidianVaults/FocuscallVault/focuscall.ai/
├── 00 - focuscall.ai Home.md
├── 01 - Architecture.md
├── 02 - Provisioning Flow.md
├── 03 - Security.md
├── 04 - Knowledge Graph.md
├── 05 - Deployment Guide.md
├── 06 - Troubleshooting.md
├── 07 - API Reference.md
├── 08 - Roadmap & TODOs.md
├── 09 - Agent Context.md      ← Diese Datei auch hier
└── Attachments/               # Excalidraw Diagramme
```

---

## 🔐 Security Highlights

- ✅ Supabase Vault für Key-Storage (pgsodium-verschlüsselt)
- ✅ HMAC-SHA256 für Webhook-Authentifizierung
- ✅ Docker Container mit `no-new-privileges`, `cap-drop ALL`, `read-only`
- ✅ Resource-Limits: 128MB RAM, 0.5 CPU pro Container
- ✅ Keys nur als ENV-Variablen – nie auf VPS-Disk
- ✅ Agent-Isolation: Jeder Agent eigener Container

---

## 📊 Architektur-Überblick

```
User (Landing Page)
    ↓
Supabase Edge Function → Vault (encrypted keys)
    ↓ (HMAC Webhook)
VPS Hetzner (FastAPI)
    ↓
provision.py (Docker SDK)
    ↓
Container 1    Container 2    Container N
oliver-health  oliver-prod    lisa-finance
    ↓              ↓               ↓
Telegram Bot API (alle)
```

**Merke:** 1 Container = 1 Agent = 1 Persönlichkeit

---

## 🛠️ Tech Stack

| Layer | Technologie |
|-------|-------------|
| Frontend | React + Vite |
| Backend | Supabase Edge Functions (Deno) |
| VPS | Hetzner CAX21 (ARM64, 8GB) |
| Container | Docker |
| AI Runtime | ZeroClaw (Rust) |
| Channels | Telegram Bot API (später WhatsApp) |
| Memory | SQLite (brain.db) |
| Knowledge Graph | SurrealDB (Phase 2) |
| Development | [Kimi Code CLI](docs/kimi-cli.md) (ACP/MCP) |

---

## 📅 Roadmap

| Phase | Status | Beschreibung |
|-------|--------|--------------|
| 0 | ✅ | Foundation & Design |
| 1 | 🔄 | Provisioning Core (Aktiv) |
| 2 | ⏳ | Security Hardening |
| 3 | ⏳ | Knowledge Graph |
| 4 | ⏳ | Multi-Agent (A2A) |
| 5 | ⏳ | Scale & Monitoring |

Siehe [planning/260401-92r-PLAN.md](planning/260401-92r-PLAN.md) für Details.

---

## 📞 Support

- **Menschliche Admins:** Obsidian Vault lesen
- **KI-Agenten:** AGENT_CONTEXT.md lesen
- **Technische Fragen:** Troubleshooting Guide im Vault

---

*ZeroClaw Version: 0.6.7 | Server: Hetzner CAX21 (ARM64) | Last updated: 2026-04-02*

# focuscall.ai

## What This Is

focuscall.ai ist eine SaaS-Plattform für non-technical User, auf der sie per Voice- oder Text-Input ihre eigenen persönlichen KI-Assistenten konfigurieren und als Telegram-Bot deployen können. Jeder Bot läuft in einem isolierten Docker-Container auf Basis von ZeroClaw (Rust-basierter AI-Agent-Runtime). User bringen ihre eigenen LLM-Keys und Telegram-Bot-Tokens mit — die Plattform orchestriert alles andere.

## Core Value

Ein nicht-technischer User kann in unter 5 Minuten einen laufenden, personalisierten Telegram-Bot erstellen — ohne eine einzige Zeile Code zu schreiben.

## Requirements

### Validated

- ✓ Docker-Container-Isolation pro Agent (1 Container = 1 Agent) — Phase 1
- ✓ ZeroClaw-Image gebaut (ARM64, 44MB, v0.6.7) — Phase 1
- ✓ Webhook Receiver läuft (FastAPI :9000, HMAC-Signatur) — Phase 1
- ✓ Provisioning-Script (provision.py, Docker SDK, Port-Registry) — Phase 1
- ✓ End-to-End Provisioning-Test erfolgreich — Phase 1
- ✓ Supabase Auth (Email/Password, User-Profile, AgentList) — Phase 1
- ✓ Voice-Input technisch funktional (Deepgram STT eingebunden) — Phase 1

### Active

- [ ] DeepSeek generiert alle 5 ZeroClaw-Dateien (AGENT_CONTEXT.md, AGENT_QUICKREF.md, SOUL.md, config.toml, System Prompt)
- [ ] Generierte Dateien werden in Supabase gespeichert und sind editierbar (Tabs)
- [ ] Deploy-Button ruft VPS-Webhook direkt auf → Container startet
- [ ] Vollständiger End-to-End Flow: Login → Agent konfigurieren → Deploy → Telegram Bot antwortet
- [ ] Mobile-responsives Layout (AgentConfigForm, VoiceRecorder)
- [ ] Backend-Tests für provision.py + webhook-receiver.py
- [ ] ENV-Variablen korrekt gesetzt (WEBHOOK_SECRET, VPS_WEBHOOK_URL)
- [ ] systemctl enable focuscall-webhook (Server-Reboot-Sicherheit)

### Out of Scope

- Stripe/Payment-Integration — nicht im ersten Milestone; erst nach MVP-Validierung
- Google OAuth — nice-to-have, nicht MVP-blockierend
- A2A Agent-Kommunikation — Phase 5+; erst wenn Multi-Agent-Basis steht
- Knowledge Graph (SurrealDB) — Phase 4+; aktuell nur SQLite Memory
- Layer Builder (Knowledge-Basis erweitern) — Phase 6+
- WhatsApp/Discord/andere Channels — Telegram first
- Admin Dashboard — nice-to-have, nach Launch
- Supabase Edge Function deployen — wird durch direkte VPS-Route ersetzt im v1

## Context

**Bestehendes Backend (läuft auf 91.99.209.45):**
- ZeroClaw Docker Image (`zeroclaw:latest`, 44MB ARM64)
- FastAPI Webhook Receiver auf Port 9000 (`focuscall-webhook` systemd service)
- provision.py mit Docker SDK, Port-Registry (registry.json), File-Locking
- WEBHOOK_SECRET: `c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f`

**Bestehendes Frontend (Next.js 15 + Supabase, lokal auf :3000):**
- Login, Dashboard, AgentList funktionieren
- `/dashboard/agents/new` existiert aber ist unvollständig
- DeepSeek gibt aktuell nur System Prompt zurück (nicht alle 5 Dateien)
- Deepgram ist eingebunden, Upload zu Supabase fehlt
- `.env.local` hat fehlende/falsche Werte für WEBHOOK_SECRET und VPS_WEBHOOK_URL

**ZeroClaw Workspace-Dateien pro Container:**
```
/workspace/
├── config.toml          # Provider, Model, Telegram-Channel, Memory, Tools — KEINE Keys
├── AGENT_CONTEXT.md     # Überblick: Umgebung, Ziele, Tools
├── AGENT_QUICKREF.md    # Kurzreferenz, Slash-Commands
└── SOUL.md              # Persönlichkeit, Werte, Charakter
```
Keys (TELEGRAM_BOT_TOKEN, ZEROCLAW_API_KEY) kommen ausschließlich als Docker ENV — nie in Dateien.

**Keine Tests:** Das Backend hat bisher 0 Tests. Jede Änderung ist ohne Netz.

## Constraints

- **Tech Stack:** Next.js 15, Supabase, shadcn/ui, Python FastAPI, Docker, ZeroClaw — kein Wechsel
- **Server:** Hetzner CAX21 ARM64 (91.99.209.45) — kein Kubernetes, kein Coolify
- **Security:** Keys niemals auf Disk — nur Supabase Vault + Docker ENV
- **ZeroClaw Version:** v0.6.7 (b0xtch fork) — API kann sich ändern, Image bereits gebaut
- **Kein Port-Mapping nötig:** ZeroClaw pollt Telegram (outbound only)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 1 Docker Container = 1 Agent | Isolation, Security, Resource-Limits | ✓ Gut |
| Python FastAPI statt Supabase Edge Function für v1 Deploy | Edge Function noch nicht deployed, VPS-Direktroute einfacher | — Pending |
| Docker SDK direkt (kein Coolify/Portainer) | Maximale Einfachheit, volle Kontrolle | ✓ Gut |
| Keys nur als Docker ENV | Security: Keys nie auf VPS-Disk | ✓ Gut |
| DeepSeek für 5-Datei-Generierung | Günstig, gut genug für strukturierte JSON-Ausgabe | — Pending |
| Deepgram für Voice-Transkription | STT-Qualität, bereits integriert | ✓ Gut |
| Supabase für Auth + Storage | Schnelles Setup, RLS, Vault | ✓ Gut |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after initial GSD initialization (brownfield)*

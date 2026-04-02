# Requirements: focuscall.ai

**Defined:** 2026-04-02
**Core Value:** Non-technical User erstellt in unter 5 Minuten einen laufenden, personalisierten Telegram-Bot — ohne Code.

## v1 Requirements (Milestone 1: MVP)

### Authentication

- [x] **AUTH-01**: User kann sich mit Email/Passwort registrieren und einloggen *(existiert)*
- [x] **AUTH-02**: User-Session bleibt über Browser-Refresh erhalten *(existiert)*
- [ ] **AUTH-03**: User hat ein Profil mit Agentenliste im Dashboard

### Agent Configuration

- [ ] **CONF-01**: User kann Agenten per Text-Beschreibung konfigurieren
- [ ] **CONF-02**: User kann Agenten per Voice-Input (Deepgram) konfigurieren
- [ ] **CONF-03**: DeepSeek generiert alle 5 ZeroClaw-Dateien aus der Beschreibung (AGENT_CONTEXT.md, AGENT_QUICKREF.md, SOUL.md, config.toml, System Prompt)
- [ ] **CONF-04**: User kann jeden der 5 generierten Texte vor dem Deploy einsehen und editieren (Tabs)
- [ ] **CONF-05**: UI ist auf Mobile vollständig benutzbar (responsive Layout)

### Credentials

- [ ] **CRED-01**: User kann Telegram Bot Token eingeben
- [ ] **CRED-02**: User kann LLM API Key eingeben (OpenRouter oder andere Provider)
- [ ] **CRED-03**: Keys werden verschlüsselt in Supabase Vault gespeichert — nie auf VPS-Disk

### Provisioning

- [ ] **PROV-01**: Deploy-Button sendet sicheren Webhook an VPS (HMAC-signiert, Server-Side)
- [ ] **PROV-02**: VPS erstellt Docker-Container (fc-{user_id}) mit Keys als ENV-Variablen
- [ ] **PROV-03**: Generierte Konfigurationsdateien landen im Container-Workspace (/workspace)
- [ ] **PROV-04**: Container startet ZeroClaw, der Telegram Bot ist innerhalb von 30 Sekunden erreichbar
- [x] **PROV-05**: Container läuft isoliert (128MB RAM, 0.5 CPU, read-only rootfs) *(existiert)*

### Dashboard

- [x] **DASH-01**: User sieht Liste seiner Agenten im Dashboard *(existiert)*
- [ ] **DASH-02**: User sieht Status seiner Agenten (running/stopped/error)
- [ ] **DASH-03**: User kann Agenten stoppen und starten

### Infrastructure

- [x] **INFRA-01**: ZeroClaw Docker Image gebaut (ARM64, v0.6.7) *(existiert)*
- [x] **INFRA-02**: Webhook Receiver läuft auf VPS (:9000, HMAC-Validierung) *(existiert)*
- [ ] **INFRA-03**: Webhook Receiver überlebt Server-Neustart (systemctl enable)
- [x] **INFRA-04**: Backend hat Tests (provision.py, webhook-receiver.py)

## v2 Requirements (Milestone 2+)

### Multi-Agent

- **MULTI-01**: User kann mehrere verschiedene Agenten erstellen und verwalten
- **MULTI-02**: Agenten können optional Daten untereinander austauschen (A2A)

### Knowledge Graph

- **KG-01**: Agent speichert Konversationskontext persistent (SQLite Memory)
- **KG-02**: User kann Knowledge-Basis für Agenten erweitern (Layer Builder)
- **KG-03**: Agent kann auf Knowledge Graph zugreifen (Graph Queries)

### Payments

- **PAY-01**: Stripe-Integration — User zahlt vor erstem Deploy
- **PAY-02**: Provisioning wird erst nach erfolgreicher Zahlung getriggert

### Scale

- **SCAL-01**: Nginx + Domain für VPS (nginx proxy, SSL)
- **SCAL-02**: Monitoring (Container Health, Uptime)

## Out of Scope (v1)

| Feature | Reason |
|---------|--------|
| Stripe Payment | Erst nach MVP-Validierung — kein Paid Gate im ersten Milestone |
| Google OAuth | Email/Passwort reicht für v1 |
| WhatsApp / Discord | Telegram first — andere Channels sind spätere Erweiterungen |
| Supabase Edge Function Deploy | Wird durch direkte Server-Side Next.js Route ersetzt |
| Admin Dashboard | Nach Launch |
| Kubernetes / Coolify | Hetzner CAX21 + Docker direkt ist ausreichend und einfacher |
| SurrealDB Knowledge Graph | Phase 4+ — aktuell SQLite Memory ausreichend |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | — | ✓ Complete |
| AUTH-02 | — | ✓ Complete |
| AUTH-03 | Phase 1 | Pending |
| CONF-01 | Phase 2 | Pending |
| CONF-02 | Phase 2 | Pending |
| CONF-03 | Phase 2 | Pending |
| CONF-04 | Phase 2 | Pending |
| CONF-05 | Phase 5 | Pending |
| CRED-01 | Phase 3 | Pending |
| CRED-02 | Phase 3 | Pending |
| CRED-03 | Phase 3 | Pending |
| PROV-01 | Phase 4 | Pending |
| PROV-02 | Phase 4 | Pending |
| PROV-03 | Phase 4 | Pending |
| PROV-04 | Phase 4 | Pending |
| PROV-05 | — | ✓ Complete |
| DASH-01 | — | ✓ Complete |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| INFRA-01 | — | ✓ Complete |
| INFRA-02 | — | ✓ Complete |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 20 total
- Bereits erledigt: 7
- Noch zu bauen: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 — traceability updated after roadmap creation*

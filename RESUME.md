# RESUME — Session Handoff 2026-04-02

## Aktueller Stand

### Server (91.99.209.45 — ssh focuscall)
- ✅ `zeroclaw:latest` Docker Image gebaut (44MB ARM64)
- ✅ `provision.py` neu geschrieben — Docker SDK, File-Locking, Registry, Network pro User
- ✅ `webhook-receiver.py` neu geschrieben — FastAPI :9000, alle Endpoints
- ✅ `focuscall-webhook` systemd Service läuft (aber noch `disabled` — überlebt keinen Reboot nicht!)
- ✅ End-to-End Test erfolgreich: POST /provision → Container läuft
- ⚠️ `systemctl enable focuscall-webhook` noch nicht gemacht
- ⚠️ WEBHOOK_SECRET in systemd gesetzt: `c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f`

### Webhook API (Port 9000)
```
POST /provision   {user_id, bot_token, openrouter_key}  Header: X-Webhook-Secret
POST /deprovision {user_id}
POST /start       {user_id}
POST /stop        {user_id}
GET  /status/{user_id}
GET  /instances
GET  /health
```

### Frontend (`/Users/pwrunltd/focuscall-ai-frontend/`)
- ✅ Next.js 15 + Supabase Auth + shadcn/ui
- ✅ Landing Page (bestehend)
- ✅ Login `/login` — Email/Password funktioniert, User angelegt
- ✅ Dashboard `/dashboard` — AgentList läuft, Supabase Schema deployed
- ✅ Neuer Agent `/dashboard/agents/new` — Voice + Text-Toggle
- ✅ Supabase Tabellen: `user_agents`, `voice_recordings` deployed
- ✅ Dev Server läuft auf `http://localhost:3000`
- ⚠️ WEBHOOK_SECRET fehlt in `.env.local` (leer)
- ⚠️ Google OAuth Client ID fehlt in `.env.local`

### Supabase
- Project: `ahdzxabztewqqdajjtsn`
- User angelegt: `oliver.spitzkat@gmail.com` (bestätigt)
- PAT: in `.env.local` als `SUPABASE_PAT`

### tmux Subagenten
- `agent-1` — Kimi, war Backend-Umbau, idle
- `agent-2` — Kimi, war Frontend-Test, idle
- `agent-3` — Kimi, hat Frontend gebaut, 38% Context

---

## Offene TODOs (Priorität)

### 🔴 Sofort
1. **`/dashboard/agents/new` nicht responsive** — Layout bricht auf Mobile. Tailwind-Klassen für sm/md Breakpoints fehlen in `AgentConfigForm.tsx` und `VoiceRecorder.tsx`
2. **Agent-Generierung produziert nur System Prompt** — DeepSeek gibt ein JSON zurück, aber die Config muss mehrere Dateien erzeugen:
   - `AGENT_CONTEXT.md` — Überblick, Umgebung, Ziele
   - `AGENT_QUICKREF.md` — Kurzreferenz, Slash-Commands
   - `SOUL.md` — Persönlichkeit, Werte, Charakter
   - `config.toml` — ZeroClaw Konfiguration
   - System Prompt (für ZeroClaw selbst)
   → DeepSeek-Prompt in `/src/app/api/process-voice/route.ts` anpassen: mehr Felder anfordern
   → `AgentConfigForm.tsx` — Tabs für jede Datei anzeigen + editierbar machen

### 🟡 Wichtig
3. **`systemctl enable focuscall-webhook`** auf dem Server ausführen
4. **WEBHOOK_SECRET** in `.env.local` eintragen: `c9109218...`
5. **VPS_WEBHOOK_URL** in `.env.local` auf echten Wert setzen (aktuell `https://vps.focuscall.ai/provision`, aber der DNS existiert noch nicht — erstmal `http://91.99.209.45:9000/provision`)
6. **Deploy-Button** in `AgentConfigForm.tsx` — ruft aktuell Supabase Edge Function auf, die noch nicht deployed ist. Stattdessen direkt `VPS_WEBHOOK_URL` aufrufen (oder Server-Side Route bauen)

### 🟢 Nice to Have
7. `registry.json` auf Server prüfen nach mehreren Provision-Aufrufen
8. Nginx + Domain für den Server
9. Supabase Edge Function deployen

---

## Wichtige Dateipfade

| Datei | Pfad |
|---|---|
| Frontend | `/Users/pwrunltd/focuscall-ai-frontend/` |
| Agent-Erstellung Page | `src/app/dashboard/agents/new/page.tsx` |
| Voice/Text API | `src/app/api/process-voice/route.ts` |
| AgentConfigForm | `src/components/dashboard/AgentConfigForm.tsx` |
| VoiceRecorder | `src/components/voice/VoiceRecorder.tsx` |
| Backend provision.py | `/opt/focuscall/provisioning/provision.py` (auf Server) |
| Backend webhook-receiver.py | `/opt/focuscall/provisioning/webhook-receiver.py` (auf Server) |
| .env.local | `/Users/pwrunltd/focuscall-ai-frontend/.env.local` |
| Obsidian Vault | `/Users/pwrunltd/Documents/ObsidianVaults/FocuscallVault/focuscall.ai/` |

---

## ZeroClaw Dateien pro Container (Ziel)

Jeder provisionierte Container bekommt diese Dateien im `/workspace`:
```
/workspace/
├── config.toml          # ZeroClaw Konfiguration (port, bot, llm, db)
├── AGENT_CONTEXT.md     # Umgebung, Ziele, Tools
├── AGENT_QUICKREF.md    # Kurzreferenz
├── SOUL.md              # Persönlichkeit, Charakter
└── db/                  # SurrealDB (auto-erstellt)
```

DeepSeek muss alle diese Inhalte aus der User-Beschreibung generieren.

---

## Architektur-Kurzfassung

```
User → /login → /dashboard → /agents/new
  → Text/Voice beschreibt Agent
  → DeepSeek generiert: AGENT_CONTEXT, QUICKREF, SOUL, config.toml, SystemPrompt
  → User fügt Telegram Token + OpenRouter Key ein
  → Deploy-Button → POST http://91.99.209.45:9000/provision
      {user_id, bot_token, openrouter_key}
  → Server erstellt Docker Container fc-{user_id}
  → ZeroClaw startet, pollt Telegram
```

---

## Keys (.env.local)
- `NEXT_PUBLIC_SUPABASE_URL` ✅
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` ✅
- `SUPABASE_SERVICE_ROLE_KEY` ✅
- `DEEPSEEK_API_KEY` ✅
- `DEEPGRAM_API_KEY` ✅
- `SUPABASE_PAT` ✅
- `WEBHOOK_SECRET` ❌ leer — Wert: `c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f`
- `VPS_WEBHOOK_URL` ❌ falscher Wert — korrekter Wert: `http://91.99.209.45:9000/provision`
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID` ❌ leer

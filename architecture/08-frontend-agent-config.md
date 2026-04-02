# Frontend: Agent Configuration Flow

> Related: [Provisioning Flow](05-provisioning-flow.md) | [ZeroClaw Reference](07-zeroclaw-reference.md) | [README](README.md)
> Last updated: 2026-04-02

---

## Übersicht

Der User erstellt einen neuen Agenten über das Next.js Frontend. Er beschreibt seinen Agenten per **Voice oder Text**. Daraus generiert DeepSeek automatisch alle nötigen ZeroClaw-Konfigurationsdateien. Danach gibt der User seine Keys ein und deployt den Container mit einem Klick.

---

## Vollständiger Flow

```
/dashboard/agents/new
        │
        ▼
┌───────────────────────────────┐
│ 1. Beschreibung               │
│    Voice (Deepgram)           │
│    oder Text-Input            │
└───────────────────────────────┘
        │
        ▼ DeepSeek API
┌───────────────────────────────┐
│ 2. KI-Generierung             │
│    → AGENT_CONTEXT.md         │
│    → AGENT_QUICKREF.md        │
│    → SOUL.md                  │
│    → config.toml              │
│    → System Prompt            │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 3. Review & Edit              │
│    Tabs für jede Datei        │
│    User kann alles anpassen   │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 4. Keys eintragen             │
│    Telegram Bot Token         │
│    LLM API Key (OpenRouter    │
│    oder andere Provider)      │
└───────────────────────────────┘
        │
        ▼ Supabase
┌───────────────────────────────┐
│ 5. Speichern in Supabase      │
│    Dateien in user_agents     │
│    Keys in Vault (encrypted)  │
└───────────────────────────────┘
        │
        ▼ Deploy-Button
┌───────────────────────────────┐
│ 6. Provisioning               │
│    Edge Function →            │
│    POST http://91.99.209.45   │
│         :9000/provision       │
│    {user_id, bot_token,       │
│     openrouter_key}           │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 7. Docker Container läuft    │
│    ZeroClaw pollt Telegram    │
│    Bot antwortet              │
└───────────────────────────────┘
```

---

## Voice-Input (Deepgram)

- **Status:** Technisch funktional (Deepgram SDK eingebunden)
- **Offen:** Upload der transkribierten/generierten Dateien zurück zu Supabase
- **Flow:** Audio → Deepgram STT → Text → DeepSeek → 5 Dateien

```typescript
// src/app/api/process-voice/route.ts
// 1. Audio per Deepgram transkribieren
// 2. Transkript an DeepSeek schicken
// 3. DeepSeek gibt strukturiertes JSON mit allen 5 Dateien zurück
// 4. Dateien in Supabase speichern (NOCH NICHT IMPLEMENTIERT)
```

---

## DeepSeek Prompt-Output (5 Dateien)

DeepSeek muss auf Basis der User-Beschreibung alle 5 Dateien generieren:

### 1. `AGENT_CONTEXT.md`
Überblick über den Agenten: Umgebung, Ziele, Tools, Limits.
```markdown
# Agent Context: [Name]
## Was bin ich?
## Meine Aufgaben
## Meine Tools
## Meine Grenzen
```

### 2. `AGENT_QUICKREF.md`
Kurzreferenz für den Agenten: Slash-Commands, wichtige Infos.
```markdown
# Quick Reference: [Name]
## Befehle
## Wichtige Dateipfade
## Kontakt
```

### 3. `SOUL.md`
Persönlichkeit, Werte, Charakter des Agenten.
```markdown
# Soul: [Name]
## Persönlichkeit
## Werte
## Kommunikationsstil
## Was ich niemals tue
```

### 4. `config.toml`
ZeroClaw Konfiguration. **Keine Keys** — kommen aus ENV.
```toml
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4-6"

[gateway]
host = "127.0.0.1"
port = 42000  # wird automatisch zugewiesen

[channels_config.telegram]
enabled = true
bot_token = "${TELEGRAM_BOT_TOKEN}"  # aus ENV

[autonomy]
level = "supervised"

[tools]
enabled = ["memory"]  # Basis: nur memory, keine Shell
```

### 5. System Prompt
Der eigentliche System-Prompt für das LLM.
```
Du bist [Name], ein persönlicher KI-Assistent...
```

---

## Supabase Schema

```sql
-- user_agents Tabelle
CREATE TABLE user_agents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES auth.users(id) NOT NULL,
  name            TEXT NOT NULL,
  agent_context   TEXT,  -- AGENT_CONTEXT.md Inhalt
  agent_quickref  TEXT,  -- AGENT_QUICKREF.md Inhalt
  soul            TEXT,  -- SOUL.md Inhalt
  config_toml     TEXT,  -- config.toml Inhalt
  system_prompt   TEXT,  -- System Prompt
  bot_token       TEXT,  -- Vault encrypted
  llm_key         TEXT,  -- Vault encrypted
  status          TEXT DEFAULT 'draft',  -- draft | provisioned | running | stopped
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Frontend-Dateien

| Datei | Pfad | Funktion |
|-------|------|----------|
| Neue Agent Page | `src/app/dashboard/agents/new/page.tsx` | Route |
| Voice Recorder | `src/components/voice/VoiceRecorder.tsx` | Audio-Aufnahme + Deepgram |
| Agent Config Form | `src/components/dashboard/AgentConfigForm.tsx` | Formular + Tabs + Deploy |
| Voice/Text API | `src/app/api/process-voice/route.ts` | DeepSeek Generierung |

---

## Offene Punkte (Stand 2026-04-02)

| Problem | Beschreibung | Priorität |
|---------|-------------|-----------|
| Supabase Upload | Generierte Dateien werden nicht gespeichert | 🔴 Kritisch |
| DeepSeek Prompt | Gibt nur System Prompt zurück, nicht alle 5 Dateien | 🔴 Kritisch |
| Mobile Layout | AgentConfigForm + VoiceRecorder nicht responsive | 🔴 Kritisch |
| Deploy-Button | Ruft noch Edge Function auf, nicht direkt VPS | 🟡 Wichtig |
| WEBHOOK_SECRET | Fehlt in .env.local | 🟡 Wichtig |
| VPS_WEBHOOK_URL | Falscher Wert in .env.local | 🟡 Wichtig |
| Keine Tests | Backend hat 0 Tests | 🟡 Wichtig |

---

## Wichtige ENV-Variablen (Frontend)

```bash
# .env.local (focuscall-ai-frontend)
NEXT_PUBLIC_SUPABASE_URL=https://ahdzxabztewqqdajjtsn.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...       # ✅
SUPABASE_SERVICE_ROLE_KEY=...           # ✅
DEEPSEEK_API_KEY=...                    # ✅
DEEPGRAM_API_KEY=...                    # ✅
WEBHOOK_SECRET=c9109218c9e92c1f09de3e695bc127b9cd83ab4372ee45d733570fc7b23fa52f  # ❌ leer
VPS_WEBHOOK_URL=http://91.99.209.45:9000/provision  # ❌ falscher Wert
```

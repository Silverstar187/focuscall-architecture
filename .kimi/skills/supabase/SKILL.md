# Supabase Skill

## Overview

Dieser Skill enthält alle wichtigen Informationen für die Supabase-Integration des focuscall.ai Projekts.

## Projekt-Details

| Eigenschaft | Wert |
|-------------|------|
| **Project URL** | `https://ahdzxabztewqqdajjtsn.supabase.co` |
| **Project ID** | `ahdzxabztewqqdajjtsn` |
| **Region** | eu-central-1 (Frankfurt) |
| **Frontend** | Next.js 15 + React 19 |
| **Auth** | Google OAuth + Email/Password |

## Datenbank-Schema

### Tabelle: `user_agents`

```sql
CREATE TABLE user_agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  agent_name TEXT NOT NULL,
  telegram_bot_token TEXT, -- Supabase Vault encrypted
  llm_api_key TEXT, -- Supabase Vault encrypted
  llm_provider TEXT DEFAULT 'openai',
  llm_model TEXT DEFAULT 'gpt-4o-mini',
  status TEXT DEFAULT 'pending', -- pending | configuring | ready | deploying | running | error
  config_markdown JSONB DEFAULT '{}', -- AGENT_CONTEXT, AGENT_QUICKREF, config.toml
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS Policies
ALTER TABLE user_agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only access their own agents"
  ON user_agents FOR ALL
  USING (auth.uid() = user_id);
```

### Tabelle: `voice_recordings`

```sql
CREATE TABLE voice_recordings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  agent_id UUID REFERENCES user_agents(id),
  audio_url TEXT,
  transcription TEXT,
  generated_markdown JSONB,
  status TEXT DEFAULT 'pending', -- pending | transcribed | processed | error
  created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS Policies
ALTER TABLE voice_recordings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only access their own recordings"
  ON voice_recordings FOR ALL
  USING (auth.uid() = user_id);
```

## Edge Functions

### 1. `provision-agent`

**Purpose:** Triggert VPS Webhook für Docker Container Deployment

**Location:** `supabase/functions/provision-agent/index.ts`

**Environment Variables:**
- `VPS_WEBHOOK_URL` - https://vps.focuscall.ai/provision
- `WEBHOOK_SECRET` - HMAC Secret

**Input:**
```json
{
  "user_id": "uuid",
  "agent_id": "uuid",
  "telegram_bot_token": "string",
  "llm_api_key": "string",
  "llm_provider": "string"
}
```

### 2. `process-voice`

**Purpose:** Transkribiert Audio und generiert Markdown mit DeepSeek

**Environment Variables:**
- `DEEPSEEK_API_KEY` - DeepSeek API Key

## Auth-Konfiguration

### Google OAuth

**Redirect URL:** `https://ahdzxabztewqqdajjtsn.supabase.co/auth/v1/callback`

**Sites:**
- `http://localhost:3000` (Dev)
- `https://focuscall.ai` (Prod)

### Email/Password

- Enabled: true
- Confirm email: false (für schnellen Onboarding)

## CLI Commands

```bash
# Login
supabase login

# Init (bereits gemacht)
supabase init

# Link zu Projekt
supabase link --project-ref ahdzxabztewqqdajjtsn

# Edge Function deploy
supabase functions deploy provision-agent
supabase functions deploy process-voice

# Secrets setzen
supabase secrets set VPS_WEBHOOK_URL=https://vps.focuscall.ai/provision
supabase secrets set WEBHOOK_SECRET=<dein-secret>
supabase secrets set DEEPSEEK_API_KEY=<dein-key>

# Database Types generieren
supabase gen types typescript --project-id ahdzxabztewqqdajjtsn > src/lib/database.types.ts
```

## Frontend Integration

### Supabase Client

```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)
```

### Auth Hook

```typescript
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { User } from '@supabase/supabase-js'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  return { user, loading }
}
```

## HMAC Webhook Security

```typescript
// HMAC-SHA256 Signatur für VPS Webhook
const crypto = require('crypto')

function generateSignature(userId: string, agentId: string, timestamp: string, secret: string): string {
  const payload = `${userId}:${agentId}:${timestamp}`
  return crypto.createHmac('sha256', secret).update(payload).digest('hex')
}
```

## Wichtige Links

- [Supabase Dashboard](https://supabase.com/dashboard/project/ahdzxabztewqqdajjtsn)
- [Auth Settings](https://supabase.com/dashboard/project/ahdzxabztewqqdajjtsn/auth/settings)
- [Edge Functions](https://supabase.com/dashboard/project/ahdzxabztewqqdajjtsn/functions)
- [Database](https://supabase.com/dashboard/project/ahdzxabztewqqdajjtsn/database/tables)

## Troubleshooting

**CORS Fehler:**
- Auth URLs in Supabase Dashboard unter Auth > URL Configuration hinzufügen

**RLS Policy Fehler:**
- Prüfen ob RLS Policies korrekt gesetzt sind
- `auth.uid()` muss mit `user_id` Spalte übereinstimmen

**Edge Function 500:**
- Logs checken: `supabase functions logs provision-agent`
- Secrets prüfen: `supabase secrets list`

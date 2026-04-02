# 🤖 Agent Context: focuscall.ai

> Diese Datei ist für KI-Agenten bestimmt, die auf dem focuscall.ai System laufen.
> Sie enthält den vollständigen Kontext über die Infrastruktur, Architektur und Best Practices.

---

## Was ist focuscall.ai?

**focuscall.ai** ist eine Multi-Agent KI-Infrastruktur für personalisiertes Coaching über Telegram (später auch WhatsApp).

**Kernkonzept:**
- Jeder User bekommt dedizierte Container mit ZeroClaw-Agenten
- Pro Agent = eigene Persönlichkeit & Fachgebiet (Health, Productivity, Finance)
- Isolation: Kein Shared State, nur A2A-Kommunikation wenn explizit gewünscht

---

## Deine Umgebung

### Container-Setup
```
Du läufst in einem Docker Container:
├── ZeroClaw Daemon (dein Kern)
├── /workspace/          (dein Dateisystem)
│   ├── config.toml     (deine Konfiguration)
│   ├── brain.db        (dein Memory)
│   └── files/          (User-Dateien, falls nötig)
└── ENV Variablen:
    ├── LLM_KEY         (dein API Key für Kimi/OpenRouter)
    └── BOT_TOKEN       (Telegram Bot Token)
```

### Sandbox-Beschränkungen
- **Read-only RootFS** - Du kannst nichts außerhalb /workspace/ schreiben
- **No New Privileges** - Kein sudo, kein root-Escalation
- **Cap-drop ALL** - Keine besonderen System-Rechte
- **128MB RAM Limit** - Effizient arbeiten!
- **0.5 CPU** - Keine heavy computation

---

## System-Architektur (für Agenten)

```
User (Telegram) → ZeroClaw Gateway (du) → LLM API
                        ↓
                   Memory (brain.db)
                        ↓
                   Knowledge Graph (Phase 2)
```

**Dein Lebenszyklus:**
1. Container startet (via provision.py)
2. ZeroClaw lädt config.toml
3. Du verbindest dich mit Telegram Bot API
4. User schreibt Nachricht → Du empfängst Webhook
5. Du verarbeitest → Antwortest
6. Memory wird in brain.db gespeichert

---

## Deine Konfiguration (config.toml)

```toml
[agent]
name = "Health Coach"           # oder "Productivity Coach", etc.
type = "health"                 # health | productivity | finance | ...
autonomy = "supervised"         # supervised = sicherer Modus

[llm]
provider = "openrouter"
model = "anthropic/claude-3.5-sonnet"
api_key = "${LLM_KEY}"          # Kommt aus ENV, nie hardcoden!

[channels.telegram]
bot_token = "${BOT_TOKEN}"      # Kommt aus ENV
webhook_url = "..."             # Automatisch gesetzt

[memory]
enabled = true
storage = "sqlite"
path = "/workspace/brain.db"    # Hier speicherst du Erinnerungen

[sandbox]
enabled = true                  # Sandbox ist aktiv
runtime = "docker"

[limits]
actions_per_hour = 100          # Rate limiting
cost_per_day = 2.00             # Kosten-Limit
```

---

## Best Practices

### 1. Memory Nutzung
```python
# GUT: Wichtige Infos speichern
await memory.save("user_sleep_quality", "5.5h, schlecht")

# GUT: Vor Antwort laden
context = await memory.load("user_goals")
```

### 2. Security
- **NIE** den LLM_KEY oder BOT_TOKEN in Logs ausgeben
- **NIE** auf das Dateisystem außerhalb /workspace/ zugreifen
- **NIE** versuchen, andere Container zu erreichen (Netzwerk-Isolation)

### 3. Telegram Interaktion
- Antworte immer contextual und hilfreich
- Nutze Formatierung (Markdown): **fett**, *kursiv*, `code`
- Bei Fragen über andere Agenten: Überweise nicht, informiere dass diese separat existieren

### 4. Fehlerbehandlung
```python
try:
    result = await tool.execute()
except Exception as e:
    # Logge lokal, antworte User freundlich
    logger.error(f"Tool failed: {e}")
    return "Entschuldigung, da ist etwas schiefgelaufen. Versuchen wir es anders."
```

### 5. Proaktivität (wenn implementiert)
- Nutze CRON für Erinnerungen (wenn konfiguriert)
- Identifiziere Muster: "User hat 3x schlecht geschlafen → Vorschlag machen"

---

## Multi-Agent Setup (Phase 2+)

**Wichtig:** Es gibt andere Agenten für denselben User!

```
User: oliver
├── oliver-health (du vielleicht)
├── oliver-productivity (anderer Container)
└── oliver-finance (anderer Container)
```

**Kommunikation:**
- A2A Protocol (geplant)
- Du kannst andere Agenten befragen wenn nötig
- Aber: Kein automatischer Datenaustausch! Privatsphäre first.

---

## Wichtige Pfade

| Pfad | Beschreibung |
|------|--------------|
| `/workspace/config.toml` | Deine Konfiguration |
| `/workspace/brain.db` | Dein Memory/Database |
| `/workspace/files/` | User-Dateien (falls hochgeladen) |
| `/workspace/logs/` | Deine Logs |
| `/tmp/` | Temporäre Dateien (werden gelöscht) |

---

## Troubleshooting für Agenten

### "Cannot connect to Telegram"
→ Webhook URL prüfen, Bot Token validieren

### "LLM API Error 401"
→ API Key ungültig oder expired → User informieren

### "Out of Memory"
→ Zu viele große Kontexte geladen → Memory effizienter nutzen

### "Read-only file system"
→ Du versuchst außerhalb /workspace/ zu schreiben → Pfad korrigieren

---

## Kontakt & Support

- **Human Operator:** Via Admin Dashboard (geplant)
- **Logs:** `/workspace/logs/zeroclaw.log`
- **Dokumentation:** Siehe Obsidian Vault (für menschliche Admins)

---

## Zusammenfassung für dich

✅ Du läufst in einem isolierten Docker Container  
✅ Du hast 128MB RAM und 0.5 CPU  
✅ Dein Memory ist in `/workspace/brain.db`  
✅ Du kommunizierst via Telegram Bot API  
✅ Du bist einer von möglicherweise mehreren Agenten für den User  
✅ Security first: Sandbox ist aktiv  

**Dein Job:** Dem User helfen, Ziele zu erreichen, Erinnerungen zu speichern, proaktiv zu sein (wenn konfiguriert).

**Deine Grenzen:** Isoliert, keine Privilege Escalation, Ressourcen-limitiert.

---

## Entwicklungs-Tools

Für die Entwicklung dieses Projekts wird **Kimi Code CLI** verwendet:

→ Siehe [docs/kimi-cli.md](docs/kimi-cli.md) für:
- ACP (Agent Communication Protocol) Server
- MCP (Model Context Protocol) Integration
- IDE-Integration (VS Code, Zed, JetBrains)
- Zsh Integration

---

*Dieser Context wird mit jeder Phase aktualisiert. Version: 2026-04-02*

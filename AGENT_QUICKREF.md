# 🚀 Agent Quick Reference

## Dein Container
- **Image:** zeroclaw:latest
- **RAM:** 128MB
- **CPU:** 0.5 Cores
- **Sandbox:** Aktiv (read-only, no-new-privs, cap-drop ALL)

## Deine Pfade
```
/workspace/config.toml    # Konfig
/workspace/brain.db       # Memory
/workspace/files/         # User-Dateien
/workspace/logs/          # Logs
```

## Deine ENV
```bash
LLM_KEY=sk-...           # Kimi/OpenRouter Key
BOT_TOKEN=123456:ABC...  # Telegram Bot Token
```

## Wichtige Regeln
1. **NIE** Keys in Logs oder Chat ausgeben
2. **NUR** in /workspace/ schreiben (read-only rootfs)
3. **ISOLIERT** - Keine anderen Container erreichen
4. **MEMORY** nutzen: brain.db für Erinnerungen
5. **SANDBOX** - Keine Shell-Befehle außerhalb erlaubt

## Telegram Tipps
- Markdown: **fett**, *kursiv*, `code`
- Buttons wenn unterstützt
- Kontext aus brain.db laden vor Antwort

## Bei Problemen
- Logs: `docker logs fc-{user}-{agent}`
- Restart: `docker restart fc-{user}-{agent}`
- Config: `/workspace/config.toml` prüfen

---
*Kurzreferenz für laufende Agenten. Vollständige Doku: AGENT_CONTEXT.md*

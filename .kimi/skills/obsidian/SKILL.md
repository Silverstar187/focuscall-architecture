# Obsidian Vault Skill

## Overview

Direkter Zugriff auf den lokalen Obsidian Vault via REST API. Kein MCP nötig — funktioniert sofort per curl.

## Konfiguration

| Eigenschaft | Wert |
|-------------|------|
| **API URL** | `https://127.0.0.1:27124` |
| **API Key** | `6c1a0c359e02d6ef5e0133b8ed8ca51d9f5294967c43782b75112422db2f3840` |
| **Vault** | focuscall.ai Vault (Root-Level, kein Unterordner) |

## Verfügbare Dateien

- `00 - focuscall.ai Home.md`
- `01 - Architecture.md`
- `02 - Provisioning Flow.md`
- `03 - Security.md`
- `04 - Knowledge Graph.md`
- `05 - Deployment Guide.md`
- `06 - Troubleshooting.md`
- `07 - API Reference.md`
- `08 - Roadmap & TODOs.md`
- `09 - Agent Context.md`
- `10 - Auto-Provisioner v1.md`
- `README.md`
- `focuscall.ai.md`

## Nutzung (Shell-Befehle)

### Alle Dateien listen
```bash
curl -s -H "Authorization: Bearer 6c1a0c359e02d6ef5e0133b8ed8ca51d9f5294967c43782b75112422db2f3840" \
  https://127.0.0.1:27124/vault/ | python3 -c "import json,sys; [print('-',f) for f in json.load(sys.stdin)['files']]"
```

### Note lesen (Beispiel: Architektur)
```bash
curl -s -H "Authorization: Bearer 6c1a0c359e02d6ef5e0133b8ed8ca51d9f5294967c43782b75112422db2f3840" \
  "https://127.0.0.1:27124/vault/01%20-%20Architecture.md"
```

### Volltext-Suche
```bash
curl -s -H "Authorization: Bearer 6c1a0c359e02d6ef5e0133b8ed8ca51d9f5294967c43782b75112422db2f3840" \
  "https://127.0.0.1:27124/search/simple/?query=provisioning" | python3 -m json.tool
```

### Note schreiben/aktualisieren
```bash
curl -s -X PUT \
  -H "Authorization: Bearer 6c1a0c359e02d6ef5e0133b8ed8ca51d9f5294967c43782b75112422db2f3840" \
  -H "Content-Type: text/markdown" \
  --data "# Neuer Inhalt" \
  "https://127.0.0.1:27124/vault/Meine%20Note.md"
```

## Hinweise

- Pfade immer URL-enkodiert (Leerzeichen = `%20`)
- Self-signed Cert ist im System-Keychain installiert → kein `-k` Flag nötig
- Key ggf. neu generieren: Obsidian → Local REST API Plugin → neuen Key kopieren → diese Datei aktualisieren

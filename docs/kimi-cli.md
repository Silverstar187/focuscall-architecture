# 🤖 Kimi Code CLI

> AI Agent für das Terminal - unterstützt ACP (Agent Communication Protocol) und MCP (Model Context Protocol)

---

## Was ist Kimi Code CLI?

**Kimi Code CLI** ist ein KI-Agent der im Terminal läuft und bei Software-Entwicklungsaufgaben hilft:

- Code lesen und bearbeiten
- Shell-Befehle ausführen
- Webseiten suchen und abrufen
- Autonom planen und Aktionen anpassen

**Repository:** https://github.com/MoonshotAI/kimi-cli  
**Dokumentation:** https://moonshotai.github.io/kimi-cli/

---

## Installation

```bash
pip install kimi-cli
```

---

## Key Features

### 🖥️ Shell Command Mode

Kimi kann direkt als Shell verwendet werden:

```bash
# Wechsle mit Ctrl-X in den Shell-Modus
# Dann direkt Shell-Befehle ausführen
```

### 🔌 ACP (Agent Communication Protocol)

Kimi unterstützt ACP out-of-the-box für IDE-Integration:

```bash
# Starte Kimi als ACP-Server
kimi acp
```

**IDE Konfiguration:**

Für Zed (`~/.config/zed/settings.json`):
```json
{
  "agent_servers": {
    "Kimi Code CLI": {
      "type": "custom",
      "command": "kimi",
      "args": ["acp"],
      "env": {}
    }
  }
}
```

Für JetBrains (`~/.jetbrains/acp.json`):
```json
{
  "agent_servers": {
    "Kimi Code CLI": {
      "type": "custom",
      "command": "kimi",
      "args": ["acp"],
      "env": {}
    }
  }
}
```

### 🧩 MCP (Model Context Protocol)

MCP-Server verwalten:

```bash
# HTTP Server hinzufügen
kimi mcp add --transport http context7 https://mcp.context7.com/mcp \
  --header "CONTEXT7_API_KEY: ctx7sk-your-key"

# Mit OAuth
kimi mcp add --transport http --auth oauth linear https://mcp.linear.app/mcp

# Stdio Server
kimi mcp add --transport stdio chrome-devtools -- npx chrome-devtools-mcp@latest

# Liste aller Server
kimi mcp list

# Server entfernen
kimi mcp remove chrome-devtools

# Autorisieren
kimi mcp auth linear
```

**Ad-hoc MCP Config:**

```bash
kimi --mcp-config-file /path/to/mcp.json
```

Beispiel `mcp.json`:
```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

### 📝 VS Code Extension

Kimi kann über die [Kimi Code VS Code Extension](https://marketplace.visualstudio.com/items?itemName=moonshot-ai.kimi-code) in VS Code integriert werden.

### 🐚 Zsh Integration

```bash
# Plugin installieren
git clone https://github.com/MoonshotAI/zsh-kimi-cli.git \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli

# In ~/.zshrc hinzufügen:
plugins=(... kimi-cli)
```

Nach dem Neustart von Zsh: `Ctrl-X` für Agent-Modus.

---

## Wichtige Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `kimi` | Interaktiver Modus |
| `kimi acp` | ACP Server starten |
| `kimi mcp list` | MCP Server auflisten |
| `kimi info` | Versionsinfo |
| `kimi login` | Login |
| `kimi logout` | Logout |

---

## Weitere Ressourcen

- **Getting Started:** https://moonshotai.github.io/kimi-cli/
- **LLM-friendly docs:** https://moonshotai.github.io/kimi-cli/llms.txt
- **GitHub:** https://github.com/MoonshotAI/kimi-cli

# SUBAGENTS — 3x Kimi via tmux

## Layout

```
┌─────────────────────────────────────────┐
│         Cursor (Claude Code)            │  ← Koordinator (ich)
├────────────┬────────────┬───────────────┤
│  agent-1   │  agent-2   │   agent-3     │  ← 3x Kimi (Subagenten)
│   kimi     │   kimi     │    kimi       │
└────────────┴────────────┴───────────────┘
```

Claude läuft in Cursor oben — Kimi läuft in 3 tmux-Sessions unten (je ein Terminal-Split).

---

## Schnellstart: 3 Subagenten aufmachen

### 1. Sessions prüfen / erstellen

```bash
tmux list-sessions

# Falls noch nicht vorhanden:
tmux rename-session -t main agent-1
tmux new-session -d -s agent-2 -c ~/ZeroClaw
tmux new-session -d -s agent-3 -c ~/ZeroClaw
```

### 2. Cursor-Terminal 3x vertikal teilen

In Cursor: Terminal öffnen → 2x `Split Terminal` (Icon oben rechts im Terminal-Panel).

Dann in jedem der 3 Splits einmalig einfügen:

```bash
tmux attach -t agent-1   # Split 1
tmux attach -t agent-2   # Split 2
tmux attach -t agent-3   # Split 3
```

### 3. Kimi starten

```bash
kimi
```

Kimi startet standardmäßig mit **YOLO Mode** und **allen konfigurierten MCP-Servern** (Obsidian, Trello, Excalidraw).

---

## Kimi korrekt bedienen (von Claude aus per tmux)

### Aufgabe senden

```bash
# Prompt an laufendes Kimi schicken
tmux send-keys -t agent-2 'Aufgabe hier' Enter
```

### Status prüfen — IMMER zuerst

```bash
# Sichtbaren Bildschirm auslesen (kein scrollback!)
tmux capture-pane -t agent-2 -p | grep -v "^[[:space:]]*$" | tail -5

# Welcher Prozess läuft?
tmux list-panes -t agent-2 -F "#{pane_current_command}"
# → python3.13 = Kimi läuft
# → zsh        = Shell, Kimi nicht aktiv
```

### Kimi beenden — ZUVERLÄSSIGE METHODE

```bash
# Shell-PID des Panes → Kindprozess (Kimi) finden → nur Kimi killen
pid=$(tmux list-panes -t agent-2 -F "#{pane_pid}")
child=$(pgrep -P $pid | head -1)
kill $child
# Shell bleibt stehen!
```

### Alle 3 auf einmal beenden

```bash
for a in agent-1 agent-2 agent-3; do
  pid=$(tmux list-panes -t $a -F "#{pane_pid}")
  child=$(pgrep -P $pid | head -1)
  [ -n "$child" ] && kill $child
done
```

> NIEMALS `Ctrl-D` per `tmux send-keys` — killt Shell mit. NIEMALS `clear` an Kimi schicken — wird als Prompt interpretiert.

### Alternate Screen Problem (schwarzes Terminal)

Wenn Kimi unclean abgebrochen wurde, bleibt das Terminal in einem leeren/schwarzen Zustand (Alternate Screen Buffer). Fix:

```bash
# Option 1: reset im Shell-Modus
tmux send-keys -t agent-2 'reset' Enter

# Option 2: Prozess-PID finden und killen
tmux list-panes -t agent-2 -F "#{pane_pid}"
kill -9 <pid>
# Session ggf. neu erstellen:
tmux new-session -d -s agent-2 -c ~/ZeroClaw
```

---

## Kimi Slash Commands (wichtigste)

| Befehl | Funktion |
|---|---|
| `/yolo` | YOLO Mode togglen (alle Bestätigungen überspringen) |
| `/exit` | Kimi beenden |
| `/clear` | Kontext löschen (nicht Terminal!) |
| `/new` | Neue Session starten (ohne Kimi zu beenden) |
| `/mcp` | MCP-Server Status anzeigen |
| `/model` | Modell wechseln |
| `/debug` | Token/Kontext-Info anzeigen |

## Kimi Keyboard Shortcuts

| Shortcut | Funktion |
|---|---|
| `Ctrl-D` | Kimi beenden (Input leer) |
| `Ctrl-C` | Laufenden Task unterbrechen / Input leeren |
| `Ctrl-X` | Toggle Agent/Shell-Modus |
| `Shift-Tab` | Plan-Modus togglen |

---

## Parallele Ausführung

```bash
# Alle 3 gleichzeitig anstoßen
tmux send-keys -t agent-1 'Aufgabe 1' Enter
tmux send-keys -t agent-2 'Aufgabe 2' Enter
tmux send-keys -t agent-3 'Aufgabe 3' Enter

# Ergebnisse einsammeln
sleep 15
for a in agent-1 agent-2 agent-3; do
  echo "=== $a ===" && tmux capture-pane -t $a -p | grep -v "^[[:space:]]*$" | tail -10
done
```

---

## Orchestrator (primeline-ai/claude-tmux-orchestration)

Installiert unter `./_orchestrator/`. Für komplexe, lang laufende Aufgaben mit Monitoring.

### Starten

```bash
./_orchestrator/orch-bootstrap.sh

export SESSION_NAME="orch-zeroclaw"
export ORCH_DIR="$(pwd)/_orchestrator"
export PROJECT_ROOT="$(pwd)"

./_orchestrator/spawn-worker.sh w1 sonnet "Aufgabe"
./_orchestrator/spawn-worker.sh w2 haiku  "Aufgabe"
```

### Kritische tmux-Details aus dem Orchestrator-Source

```bash
# RICHTIG: literal mode + separates Enter (verhindert Sonderzeichen-Bugs bei #, !)
tmux send-keys -t "$SESSION:w1" -l "$PROMPT_TEXT"
sleep 0.5
tmux send-keys -t "$SESSION:w1" Enter

# Multiline-Prompts: paste-buffer statt send-keys
echo "$PROMPT" | tmux load-buffer -b "buf-w1" -
tmux paste-buffer -p -d -b "buf-w1" -t "$SESSION:w1"

# ANSI strippen vor Regex-Matching
tmux capture-pane -t pane -p | sed -E 's/\x1b\[[0-9;:?<=>]*[a-zA-Z]//g'
```

### Heartbeat & Watchdog

- **Heartbeat**: Prüft alle 30–300s ob Worker idle — sendet `/orchestrate-cycle`
- **Rate-Limit-Watchdog**: Erkennt 429-Fehler, wartet 65s, schickt explizites Retry
- **Worker-States**: `SAFE_TO_RESTART` · `DO_NOT_INTERRUPT` · `CONTEXT_LOW_CONTINUE`

### Wann Orchestrator, wann direkt Kimi?

| Szenario | Ansatz |
|---|---|
| Kurze Aufgabe (<25 turns) | direkt Kimi per `tmux send-keys` |
| Lange Aufgabe mit MCP/Hooks | Orchestrator + `spawn-worker.sh` |
| Parallele unabhängige Tasks | Orchestrator mit w1/w2/w3 |

---

## MCP-Verfügbarkeit (alle Sessions)

| Server | Status |
|---|---|
| obsidian | ✓ Connected |
| trello | ✓ Connected |
| excalidraw | ✓ Connected |
| Gmail | Needs auth |
| Notion | Needs auth |
| Google Calendar | Needs auth |

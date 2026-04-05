# Skill: tmux-subagents
# Description: Koordination von 3 Kimi-Subagenten via tmux in ZeroClaw

## Setup

3 tmux-Sessions: `agent-1`, `agent-2`, `agent-3`
Claude (ich) koordiniert — Kimi läuft in jedem als Subagent.

```bash
# Sessions prüfen
tmux list-sessions

# Neu erstellen (falls weg)
tmux new-session -d -s agent-2 -c ~/ZeroClaw
tmux new-session -d -s agent-3 -c ~/ZeroClaw
```

## WICHTIG: Status IMMER zuerst prüfen

```bash
# Welcher Prozess läuft?
tmux list-panes -t agent-2 -F "#{pane_current_command}"
# python3.13 = Kimi aktiv
# zsh        = Shell, Kimi nicht aktiv

# Sichtbarer Screen (nicht scrollback)
tmux capture-pane -t agent-2 -p | grep -v "^[[:space:]]*$" | tail -5
```

## Kimi starten

```bash
# Kimi-Alias in .zshrc: kimi='kimi --yolo --mcp-config-file ~/.kimi/mcp.json'
# IMMER über Alias starten — nie nacktes 'kimi' ohne Alias
tmux send-keys -t agent-2 'kimi' Enter
```

## Kimi beenden — ZUVERLÄSSIGE METHODE

```bash
# Shell-PID des Panes holen → Kindprozess (= Kimi) finden → nur Kimi killen
pid=$(tmux list-panes -t agent-2 -F "#{pane_pid}")
child=$(pgrep -P $pid | head -1)
kill $child
# Shell bleibt stehen, nur Kimi wird beendet
```

### Alle 3 auf einmal beenden

```bash
for a in agent-1 agent-2 agent-3; do
  pid=$(tmux list-panes -t $a -F "#{pane_pid}")
  child=$(pgrep -P $pid | head -1)
  [ -n "$child" ] && kill $child
done
```

> NIEMALS `Ctrl-D` per tmux send-keys schicken — sendet EOF an Kimi UND Shell → Session stirbt.
> NIEMALS `clear` als Kimi-Prompt schicken — Kimi interpretiert es als Aufgabe.

## Alternate Screen Problem (schwarzes Terminal)

Wenn Kimi unclean abgebrochen wurde → Terminal bleibt schwarz/leer:

```bash
# Fix 1: reset
tmux send-keys -t agent-2 'reset' Enter

# Fix 2: Prozess killen + Session neu
pid=$(tmux list-panes -t agent-2 -F "#{pane_pid}")
kill -9 $pid
sleep 1
tmux new-session -d -s agent-2 -c ~/ZeroClaw
```

## Aufgaben senden

```bash
# Prompt an laufendes Kimi
tmux send-keys -t agent-2 'Aufgabe hier' Enter

# Multiline (aus _orchestrator Quelle)
echo "$PROMPT" | tmux load-buffer -b "buf-w2" -
tmux paste-buffer -p -d -b "buf-w2" -t agent-2

# Sonderzeichen sicher (literal mode)
tmux send-keys -t agent-2 -l "$PROMPT_TEXT"
sleep 0.5
tmux send-keys -t agent-2 Enter
```

## Alle 3 parallel

```bash
for a in agent-1 agent-2 agent-3; do
  tmux send-keys -t $a 'Aufgabe' Enter
done

sleep 15
for a in agent-1 agent-2 agent-3; do
  echo "=== $a ===" && tmux capture-pane -t $a -p | grep -v "^[[:space:]]*$" | tail -8
done
```

## Kimi Slash Commands

| Befehl | Wirkung |
|---|---|
| `/exit` | Beenden |
| `/yolo` | YOLO toggle |
| `/clear` | Kontext reset |
| `/new` | Neue Session |
| `/mcp` | MCP Status |

## tmux.conf (gesetzt in ~/.tmux.conf)

```
set-option -g default-shell /bin/zsh
set-option -g default-command "zsh -i -l"   ← lädt .zshrc mit Aliases
set -sg escape-time 0                        ← kein Delay für Kimi TUI
set -g mouse on
```

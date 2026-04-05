#!/usr/bin/env bash
# heartbeat.sh — Claude Code tmux Orchestrator heartbeat loop
#
# Keeps the orchestrator alive by sending cycle prompts at adaptive intervals.
# Reads worker statuses, detects idle/stuck states, logs every cycle.
#
# ENV required: SESSION_NAME, ORCH_DIR, PROJECT_ROOT
# Started by: orch-bootstrap.sh (via nohup)
#
# Full guide: https://primeline.cc/blog/tmux-orchestration

set -euo pipefail

# --- Defaults from ENV or fallback ---
SESSION_NAME="${SESSION_NAME:?SESSION_NAME not set}"
ORCH_DIR="${ORCH_DIR:?ORCH_DIR not set}"
PROJECT_ROOT="${PROJECT_ROOT:?PROJECT_ROOT not set}"

CONFIG_FILE="${ORCH_DIR}/config.json"
PID_FILE="${ORCH_DIR}/heartbeat.pid"
READY_FILE="${ORCH_DIR}/.ready"
STOP_FILE="${ORCH_DIR}/.stop"
LOG_FILE="${ORCH_DIR}/log.jsonl"
SESSION_FILE="${ORCH_DIR}/session.json"

# --- Load config intervals ---
INTERVAL_STUCK=$(jq -r '.intervals.stuck_seconds // 30' "$CONFIG_FILE")
INTERVAL_NORMAL=$(jq -r '.intervals.normal_seconds // 120' "$CONFIG_FILE")
INTERVAL_IDLE=$(jq -r '.intervals.idle_seconds // 300' "$CONFIG_FILE")

# Validate integers
for var_name in INTERVAL_STUCK INTERVAL_NORMAL INTERVAL_IDLE; do
  if ! [[ "${!var_name}" =~ ^[0-9]+$ ]]; then
    echo "[heartbeat] FATAL: $var_name is not a valid integer: '${!var_name}'"
    exit 1
  fi
done

# Current interval (adaptive)
CURRENT_INTERVAL="$INTERVAL_NORMAL"
CYCLE_COUNT=0

# Orchestrator pane target — MUST use SESSION:0 (first window, created by bootstrap).
# Using bare SESSION_NAME targets whichever window is active, which could be a worker.
ORCH_PANE="${SESSION_NAME}:0"

# --- ANSI strip ---
# Removes ANSI escape sequences from tmux capture-pane output.
# Must run BEFORE any regex matching (idle detection, send verification).
# Covers: CSI (cursor/color), OSC (title/hyperlinks), DCS (device control),
#          charset switches, SI/SO control chars.
strip_ansi() {
  sed -E \
    -e 's/\x1b\[[0-9;:?<=>]*[a-zA-Z]//g' \
    -e 's/\x1b\][^\x07\x1b]*(\x07|\x1b\\)//g' \
    -e 's/\x1bP[^\x1b]*(\x1b\\|$)//g' \
    -e 's/\x1b[()][0-9A-Za-z]//g' \
    -e 's/[\x0e\x0f]//g'
}

# --- Logging ---
log_event() {
  local event_type="$1"
  local details="${2:-}"
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq -nc \
    --arg ts "$ts" \
    --arg type "$event_type" \
    --arg details "$details" \
    --argjson cycle "$CYCLE_COUNT" \
    '{ts: $ts, type: $type, cycle: $cycle, details: $details}' >> "$LOG_FILE"
}

# --- Signal trap for clean shutdown ---
cleanup() {
  rm -f "$PID_FILE" "$READY_FILE"
  log_event "heartbeat_stop" "signal_caught" 2>/dev/null || true
  echo "[heartbeat] Caught signal. Cleaned up."
  exit 0
}
trap cleanup SIGTERM SIGINT

# --- PID alive-check ---
check_pid_alive() {
  if [[ -f "$PID_FILE" ]]; then
    local stored_pid
    stored_pid=$(cat "$PID_FILE")
    if [[ "$$" != "$stored_pid" ]]; then
      if kill -0 "$stored_pid" 2>/dev/null; then
        echo "[heartbeat] Another heartbeat running (PID $stored_pid). Exiting."
        exit 0
      else
        echo "[heartbeat] Stale PID file (PID $stored_pid dead). Taking over."
        echo "$$" > "$PID_FILE"
      fi
    fi
  fi
}

# --- Check if a tmux pane is idle ---
# Returns 0 if idle (ready for input), 1 if busy.
# Examines last 12 lines of capture-pane output.
check_pane_idle() {
  local target="${1:-$ORCH_PANE}"
  local captured
  captured=$(tmux capture-pane -t "$target" -p -S -12 2>/dev/null | strip_ansi) || return 1

  # Spinner patterns = busy (check first, overrides idle)
  if echo "$captured" | grep -qE '(Running|thinking|Searching|Reading|Writing|Editing)'; then
    return 1
  fi

  # Idle patterns (Claude Code prompt characters)
  if echo "$captured" | grep -qE '(❯[\s ]*$|>\s*$|waiting for input|claude\s+code\s+v[0-9.]+|\$\s*$)'; then
    return 0
  fi

  # Unknown state — assume busy (safe default)
  return 1
}

# --- Send command to tmux pane ---
# Uses send-keys -l (literal) + separate Enter + verify via capture-pane.
# Retries up to max_retries times on delivery failure.
send_to_pane() {
  local target="$1"
  local message="$2"
  local max_retries="${3:-3}"

  local attempt=0
  while [[ $attempt -lt $max_retries ]]; do
    attempt=$((attempt + 1))

    # Send literal text (avoids shell interpretation of special chars)
    tmux send-keys -t "$target" -l "$message"
    sleep 0.5

    # Send Enter separately (prevents race condition with input buffer)
    tmux send-keys -t "$target" Enter
    sleep 1.0

    # Verify delivery via capture-pane
    local captured
    captured=$(tmux capture-pane -t "$target" -p -S -5 2>/dev/null | strip_ansi) || true

    if echo "$captured" | grep -qF "${message:0:40}"; then
      log_event "send_ok" "target=$target attempt=$attempt"
      return 0
    fi

    log_event "send_retry" "target=$target attempt=$attempt"
    sleep 1.0
  done

  log_event "send_fail" "target=$target message=${message:0:60}"
  return 1
}

# --- Collect worker statuses ---
collect_workers() {
  local workers_dir="${ORCH_DIR}/workers"
  local statuses=()

  if [[ -d "$workers_dir" ]]; then
    for wfile in "$workers_dir"/*.json; do
      [[ -f "$wfile" ]] || continue
      local wid
      wid=$(basename "$wfile" .json)
      local status
      status=$(jq -r '.status // "unknown"' "$wfile" 2>/dev/null) || status="error"
      local last_update
      last_update=$(jq -r '.updated // "never"' "$wfile" 2>/dev/null) || last_update="never"
      statuses+=("${wid}:${status}:${last_update}")
    done
  fi

  echo "${statuses[*]:-none}"
}

# --- Determine adaptive interval ---
# Adapts heartbeat frequency based on worker activity:
#   stuck (stale >3 normal intervals) = 30s (fast polling)
#   active workers                    = 120s (normal)
#   no workers / all done             = 300s (idle, save resources)
determine_interval() {
  local worker_info="$1"

  if [[ "$worker_info" == "none" ]]; then
    CURRENT_INTERVAL="$INTERVAL_IDLE"
    return
  fi

  local has_active=false
  local has_stuck=false

  IFS=' ' read -ra entries <<< "$worker_info"
  for entry in "${entries[@]}"; do
    IFS=':' read -r wid status last_update <<< "$entry"
    case "$status" in
      working|running|in_progress)
        has_active=true
        # Check for stale (no update for >3 normal intervals)
        if [[ "$last_update" != "never" ]]; then
          local update_epoch now_epoch age stale_threshold
          # Cross-platform ISO8601 to epoch conversion
          if [[ "$(uname)" == "Darwin" ]]; then
            update_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_update" +%s 2>/dev/null) || update_epoch=0
          else
            update_epoch=$(date -d "$last_update" +%s 2>/dev/null) || update_epoch=0
          fi
          now_epoch=$(date +%s)
          age=$(( now_epoch - update_epoch ))
          stale_threshold=$(( INTERVAL_NORMAL * 3 ))
          if [[ $age -gt $stale_threshold ]]; then
            has_stuck=true
          fi
        fi
        ;;
      waiting|blocked)
        has_active=true
        ;;
      done|stopped|error)
        ;;
    esac
  done

  if [[ "$has_stuck" == true ]]; then
    CURRENT_INTERVAL="$INTERVAL_STUCK"
  elif [[ "$has_active" == true ]]; then
    CURRENT_INTERVAL="$INTERVAL_NORMAL"
  else
    CURRENT_INTERVAL="$INTERVAL_IDLE"
  fi
}

# --- Check for worker escalations ---
check_escalations() {
  local inbox_dir="${ORCH_DIR}/inbox"
  [[ -d "$inbox_dir" ]] || return 0

  for wdir in "$inbox_dir"/*/; do
    [[ -d "$wdir" ]] || continue
    local esc_file="${wdir}escalation.json"
    if [[ -f "$esc_file" ]]; then
      local wid
      wid=$(basename "$wdir")
      local question
      question=$(jq -r '.question // "unknown"' "$esc_file" 2>/dev/null)
      local blocking
      blocking=$(jq -r '.blocking // false' "$esc_file" 2>/dev/null)
      log_event "escalation" "worker=$wid blocking=$blocking question=${question:0:80}"
    fi
  done
}

# --- Update session state ---
update_session() {
  # Args: $1 = worker_info (unused but kept for extensibility)
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  if [[ -f "$SESSION_FILE" ]]; then
    local tmp
    tmp=$(mktemp)
    if jq \
      --arg ts "$ts" \
      --argjson cycle "$CYCLE_COUNT" \
      --arg interval "$CURRENT_INTERVAL" \
      '.last_cycle = $ts | .cycle_count = $cycle | .current_interval = ($interval | tonumber)' \
      "$SESSION_FILE" > "$tmp"; then
      mv "$tmp" "$SESSION_FILE"
    else
      rm -f "$tmp"
    fi
  fi
}

# --- Interruptible sleep (checks .stop every 5s) ---
interruptible_sleep() {
  local duration="$1"
  local remaining="$duration"
  while [[ $remaining -gt 0 ]]; do
    [[ -f "$STOP_FILE" ]] && return 1
    local chunk=5
    [[ $remaining -lt $chunk ]] && chunk=$remaining
    sleep "$chunk"
    remaining=$((remaining - chunk))
  done
  return 0
}

# --- Main Heartbeat Loop ---
main() {
  # Write own PID (heartbeat owns its PID file, not bootstrap)
  echo "$$" > "$PID_FILE"

  echo "[heartbeat] Started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[heartbeat] Session: $SESSION_NAME | PID: $$ | Interval: ${CURRENT_INTERVAL}s"
  log_event "heartbeat_start" "session=$SESSION_NAME interval=$CURRENT_INTERVAL pid=$$"

  while true; do
    # Check stop file
    if [[ -f "$STOP_FILE" ]]; then
      log_event "heartbeat_stop" "stop_file_detected"
      echo "[heartbeat] Stop file detected. Shutting down."
      rm -f "$PID_FILE"
      exit 0
    fi

    # PID alive-check (prevent duplicate heartbeats)
    check_pid_alive

    # Interruptible sleep (returns 1 if .stop detected mid-sleep)
    if ! interruptible_sleep "$CURRENT_INTERVAL"; then
      log_event "heartbeat_stop" "stop_during_sleep"
      echo "[heartbeat] Stop detected during sleep. Shutting down."
      rm -f "$PID_FILE"
      exit 0
    fi

    CYCLE_COUNT=$((CYCLE_COUNT + 1))

    # --- COLLECT ---
    local worker_info
    worker_info=$(collect_workers)

    # --- EVALUATE ---
    determine_interval "$worker_info"
    check_escalations

    # --- ACT ---
    if check_pane_idle "$ORCH_PANE"; then
      touch "$READY_FILE"

      # Only send cycle command if there are active workers
      if [[ "$worker_info" != "none" ]]; then
        send_to_pane "$ORCH_PANE" "/orchestrate-cycle" 2 || true
      fi
    else
      log_event "pane_busy" "skipped_send cycle=$CYCLE_COUNT"
    fi

    # --- LOG ---
    update_session "$worker_info"
    log_event "cycle_complete" "workers=$worker_info interval=$CURRENT_INTERVAL"

    echo "[heartbeat] Cycle $CYCLE_COUNT | Workers: $worker_info | Next: ${CURRENT_INTERVAL}s"
  done
}

main "$@"

#!/usr/bin/env bash
# spawn-worker.sh — Spawn a Claude Code worker session in tmux
#
# Creates a new tmux window, boots Claude Code with worker identity,
# switches to the target model, and injects the task prompt.
#
# Usage: spawn-worker.sh <worker_id> <model> <task_description> [context_files...]
# Example: spawn-worker.sh w1 sonnet "Implement auth module" src/auth.ts src/db.ts
#
# ENV required: SESSION_NAME, ORCH_DIR, PROJECT_ROOT
# Set by: orch-bootstrap.sh (or export manually)
#
# Full guide: https://primeline.cc/blog/tmux-orchestration

set -euo pipefail

# --- Args ---
WORKER_ID="${1:?Usage: spawn-worker.sh <worker_id> <model> <task_description> [context_files...]}"
MODEL="${2:?Missing model (sonnet|haiku|opus)}"
TASK_DESC="${3:?Missing task description}"
shift 3
CONTEXT_FILES=("$@")

# --- ENV ---
SESSION_NAME="${SESSION_NAME:?SESSION_NAME not set}"
ORCH_DIR="${ORCH_DIR:?ORCH_DIR not set}"
PROJECT_ROOT="${PROJECT_ROOT:?PROJECT_ROOT not set}"

PROJECT_NAME=$(basename "$PROJECT_ROOT")
BRANCH="orch/feature/${WORKER_ID}"
WORKER_DIR="${ORCH_DIR}/workers"
RESULTS_DIR="${ORCH_DIR}/results/${WORKER_ID}"
INBOX_DIR="${ORCH_DIR}/inbox/${WORKER_ID}"
PANE_TARGET="${SESSION_NAME}:${WORKER_ID}"

# --- Helpers ---
strip_ansi() {
  sed -E \
    -e 's/\x1b\[[0-9;:?<=>]*[a-zA-Z]//g' \
    -e 's/\x1b\][^\x07\x1b]*(\x07|\x1b\\)//g' \
    -e 's/\x1bP[^\x1b]*(\x1b\\|$)//g' \
    -e 's/\x1b[()][0-9A-Za-z]//g' \
    -e 's/[\x0e\x0f]//g'
}

log() { echo "[spawn:${WORKER_ID}] $*"; }
fail() { echo "[spawn:${WORKER_ID}] FATAL: $*" >&2; exit 1; }

# --- Pre-checks ---
tmux has-session -t "$SESSION_NAME" 2>/dev/null || fail "tmux session '$SESSION_NAME' not found. Run orch-bootstrap.sh first."
[[ "$MODEL" =~ ^(sonnet|haiku|opus)$ ]] || fail "Invalid model: $MODEL (must be sonnet|haiku|opus)"

# --- Create worker directories ---
mkdir -p "$WORKER_DIR" "$RESULTS_DIR" "$INBOX_DIR"

# ============================================================
# STEP 1: Create tmux window for worker
# ============================================================
log "Step 1/6: Creating tmux window '${WORKER_ID}'..."

# Kill existing window if present (clean respawn)
tmux kill-window -t "$PANE_TARGET" 2>/dev/null || true

tmux new-window -t "$SESSION_NAME" -n "$WORKER_ID" -c "$PROJECT_ROOT"
sleep 0.5

# ============================================================
# STEP 2: Start Claude Code with worker identity ENV
# ============================================================
log "Step 2/6: Starting Claude Code with ORCHESTRATOR_WORKER_ID=${WORKER_ID}..."

BOOT_CMD="export ORCHESTRATOR_WORKER_ID='${WORKER_ID}' && export PROJECT_ROOT='${PROJECT_ROOT}' && cd '${PROJECT_ROOT}' && claude --dangerously-skip-permissions"

tmux send-keys -t "$PANE_TARGET" -l "$BOOT_CMD"
sleep 0.5
tmux send-keys -t "$PANE_TARGET" Enter

# ============================================================
# STEP 3: Wait for Claude Code to boot (poll for idle prompt)
# ============================================================
log "Step 3/6: Waiting for Claude Code to boot (max 60s)..."

WAITED=0
BOOT_OK=false
while [[ $WAITED -lt 60 ]]; do
  sleep 3
  WAITED=$((WAITED + 3))

  CAPTURED=$(tmux capture-pane -t "$PANE_TARGET" -p -S -12 2>/dev/null | strip_ansi) || continue

  # Check for idle prompt (not a spinner)
  if echo "$CAPTURED" | grep -qE '❯|>\s*$'; then
    if ! echo "$CAPTURED" | grep -qE '(Running|thinking|Searching)'; then
      BOOT_OK=true
      break
    fi
  fi
done

if [[ "$BOOT_OK" != true ]]; then
  fail "Claude Code did not reach idle state within 60s"
fi
log "Step 3/6: Claude Code booted (${WAITED}s)"

# Double-Enter Protocol: dismiss any trust/welcome prompts that may appear
# on first boot with --dangerously-skip-permissions
tmux send-keys -t "$PANE_TARGET" Enter
sleep 1.0
tmux send-keys -t "$PANE_TARGET" Enter
sleep 1.0

# ============================================================
# STEP 4: Switch to target model
# ============================================================
log "Step 4/6: Switching to /${MODEL}..."
tmux send-keys -t "$PANE_TARGET" -l "/${MODEL}"
sleep 0.5
tmux send-keys -t "$PANE_TARGET" Enter
sleep 3

# ============================================================
# STEP 5: Inject startup prompt via paste-buffer
# ============================================================
log "Step 5/6: Injecting startup prompt..."

# Build context section from provided files
CONTEXT_SECTION=""
if [[ ${#CONTEXT_FILES[@]} -gt 0 ]]; then
  CONTEXT_SECTION=$'### CONTEXT\nRelevant files to read first:'
  for cf in "${CONTEXT_FILES[@]}"; do
    CONTEXT_SECTION+=$'\n'"- ${cf}"
  done
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build the full startup prompt
STARTUP_PROMPT="## WORKER ${WORKER_ID} — ${PROJECT_NAME}
You are a worker in a tmux orchestration system.

### TASK
${TASK_DESC}

### COORDINATION RULES (mandatory)
- Status: Write and keep _orchestrator/workers/${WORKER_ID}.json updated
- Output: Save results to _orchestrator/results/${WORKER_ID}/
- Issues: Write blockers to _orchestrator/inbox/${WORKER_ID}/
- Git: Work on branch ${BRANCH} — commit yes, push no
- Do NOT spawn additional tmux workers
- Do NOT end this session yourself

### STATUS SCHEMA
Write your first status file immediately:
\`\`\`json
{
  \"worker_id\": \"${WORKER_ID}\",
  \"status\": \"working\",
  \"task\": \"${TASK_DESC:0:100}\",
  \"model\": \"${MODEL}\",
  \"branch\": \"${BRANCH}\",
  \"started\": \"${TIMESTAMP}\",
  \"updated\": \"${TIMESTAMP}\",
  \"progress\": \"Starting task\",
  \"turns\": 0,
  \"blockers\": []
}
\`\`\`

### WHEN UNCERTAIN — ASK, DON'T GUESS
Write to _orchestrator/inbox/${WORKER_ID}/escalation.json:
{\"type\":\"guidance\",\"question\":\"...\",\"context\":\"...\",\"blocking\":true/false}
- blocking: true  -> Set status to \"waiting\", pause until response
- blocking: false -> Continue working on other parts, response comes async

${CONTEXT_SECTION}

### GO
Write your status file FIRST, then start working on the task."

# Multiline injection via paste-buffer.
# send-keys breaks on newlines. load-buffer reads from stdin into a named
# tmux buffer, paste-buffer injects it into the target pane cleanly.
# -p = paste bracket mode (prevents shell interpretation)
# -d = delete buffer after paste (cleanup)
BUFFER_NAME="orch-${WORKER_ID}"
echo "$STARTUP_PROMPT" | tmux load-buffer -b "$BUFFER_NAME" -
tmux paste-buffer -p -d -b "$BUFFER_NAME" -t "$PANE_TARGET"
sleep 0.5
tmux send-keys -t "$PANE_TARGET" Enter

# ============================================================
# STEP 6: Poll for first status write (max 90s)
# ============================================================
log "Step 6/6: Waiting for worker to write first status (max 90s)..."

STATUS_FILE="${WORKER_DIR}/${WORKER_ID}.json"
WAITED=0
STATUS_OK=false
while [[ $WAITED -lt 90 ]]; do
  sleep 5
  WAITED=$((WAITED + 5))

  if [[ -f "$STATUS_FILE" ]]; then
    # Verify it's valid JSON with expected worker_id
    local_wid=$(jq -r '.worker_id // empty' "$STATUS_FILE" 2>/dev/null) || continue
    if [[ "$local_wid" == "$WORKER_ID" ]]; then
      STATUS_OK=true
      break
    fi
  fi
done

if [[ "$STATUS_OK" != true ]]; then
  log "WARNING: Worker did not write status within 90s. It may still be processing."
  log "Check manually: tmux select-window -t ${PANE_TARGET}"
else
  log "Step 6/6: Worker status confirmed (${WAITED}s)"
fi

# ============================================================
# Done
# ============================================================
echo ""
log "=== Worker ${WORKER_ID} spawned ==="
log "  Model:   ${MODEL}"
log "  Branch:  ${BRANCH}"
log "  Status:  ${STATUS_FILE}"
log "  Results: ${RESULTS_DIR}/"
log "  Inbox:   ${INBOX_DIR}/"
log ""
log "  View:    tmux select-window -t ${PANE_TARGET}"
log "  Attach:  tmux attach -t ${SESSION_NAME}"

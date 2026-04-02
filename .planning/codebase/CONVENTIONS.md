# Coding Conventions

**Analysis Date:** 2026-04-02

## Languages and Their Conventions

This codebase uses three languages across two subsystems:
- **Python 3.11** — provisioning backend (`provisioning/provision.py`, `provisioning/webhook-receiver.py`)
- **TypeScript (Deno)** — Supabase Edge Function (`provisioning/edge-function.ts`)
- **Bash** — orchestrator shell scripts (`_orchestrator/*.sh`)

Each language follows distinct conventions documented below.

---

## Python Conventions

### Naming Patterns

**Files:**
- `snake_case.py` with hyphen allowed for CLI scripts: `webhook-receiver.py`, `provision.py`

**Functions:**
- Public API functions: `snake_case` — `provision_container()`, `deprovision_container()`, `list_containers()`
- Private/internal helpers: leading underscore + `snake_case` — `_load_registry()`, `_save_registry()`, `_open_registry_lock()`, `_release_registry_lock()`, `_set_instance_status()`, `_update_instance_field()`, `_verify_hmac()`, `_check_timestamp()`

**Variables:**
- Module-level constants: `UPPER_SNAKE_CASE` — `REGISTRY_PATH`, `WORKSPACE_BASE`, `ZEROCLAW_IMAGE`, `PORT_BASE`, `HEALTH_CHECK_ATTEMPTS`, `MAX_REQUEST_AGE_SECONDS`
- Local variables: `snake_case`
- Logger: always named `log` (not `logger`) — `log = logging.getLogger("provision")`

**Types:**
- Return type annotations on public functions: `-> dict[str, Any]`, `-> None`, `-> bool`
- Parameter annotations on all function signatures
- `str | None` union syntax (Python 3.10+ style)

### Module-Level Constants Pattern

All configurable values read from environment at module import time:

```python
REGISTRY_PATH: str = os.getenv("REGISTRY_PATH", "/opt/focuscall/registry.json")
WORKSPACE_BASE: str = os.getenv("WORKSPACE_BASE", "/opt/focuscall/workspaces")
```

Hard-fail for required secrets (no default):
```python
WEBHOOK_SECRET: str = os.environ["WEBHOOK_SECRET"]  # Hard fail if missing
```

### Docstrings

All public functions have docstrings. Format: triple-quoted, first line is one-sentence summary, body uses numbered "Steps:" lists for multi-step procedures:

```python
def provision_container(...) -> dict[str, Any]:
    """
    Provision a ZeroClaw container for a user/agent pair.

    Steps:
      1. Allocate port from registry (fcntl-locked)
      2. Create workspace directory
      ...
    """
```

Private helpers get one-line docstrings:
```python
def _load_registry(lock_fd: int) -> dict:
    """Read and parse registry.json. Caller must hold lock_fd."""
```

### File-Level Module Docstrings

Every Python file opens with a triple-quoted module docstring covering: purpose, security notes, and required ENV vars:

```python
"""
provision.py — Docker SDK provisioning logic for focuscall.ai
...
SECURITY NOTE:
  Keys (llm_key, bot_token) are NEVER written to disk.
  ...
Config env vars (injected by docker-compose.infra.yml):
  REGISTRY_PATH        — /opt/focuscall/registry.json
  ...
"""
```

### Code Style

**Formatting:**
- No automated formatter config detected (no `.black`, `.flake8`, `.ruff.toml`)
- Follows PEP 8 visually: 4-space indent, lines ~100 chars max
- Blank lines: 2 between top-level functions, 1 between logical sections within functions

**Imports:**
- Standard library first, then third-party, then local
- `import json as _json` used for inline imports inside function bodies to indicate "local only"

**Section Headers (ASCII art separators):**
Functions and logical blocks are separated with `# ── Section Name ────` style banners:
```python
# ── Registry helpers (with file locking for concurrent access) ─────────────────
# ── Core provisioning ──────────────────────────────────────────────────────────
# ── Step 1: Allocate port ─────────────────────────────────────────────────────
```

This is a project-wide convention — use `# ── Name ──...──` (em-dash with trailing dashes).

**Inline Security Comments:**
Sensitive fields get inline comments at every use site:
```python
llm_key: str,      # NEVER written to disk — Docker ENV only
bot_token: str,    # NEVER written to disk — Docker ENV only
```

### Error Handling

Pattern: raise `RuntimeError` with a descriptive message, always chain with `from exc`:
```python
raise RuntimeError(f"Failed to create workspace {workspace}: {exc}") from exc
```

Specific Docker errors are caught by type before the generic fallback:
```python
except docker.errors.ImageNotFound:
    ...
except docker.errors.APIError as exc:
    ...
```

Always update registry status to `"error"` before raising, so callers can inspect state.

### Logging

- Logger: `log = logging.getLogger("module-name")` at module level
- Formatting: `%(asctime)s %(levelname)s %(name)s %(message)s` with ISO8601 timestamps
- `log.info()` for normal operation milestones
- `log.warning()` for expected-but-notable conditions (stale containers, missing entries)
- `log.error()` for failures before raising
- `log.debug()` for health check loop noise
- Always use `%s` %-style formatting (not f-strings) in log calls: `log.info("Port %d for %s", port, key)`
- For multi-field structured log lines, use keyword-style: `log.info("Complete: user_id=%s agent_id=%s result=%s", ...)`

### Pydantic Models

Request/response models use `BaseModel`. Optional fields typed with `str | None = None`:
```python
class ProvisionRequest(BaseModel):
    user_id: str
    agent_id: str
    llm_key: str       # Passed directly to Docker ENV — never written to disk
    bot_token: str     # Passed directly to Docker ENV — never written to disk
    llm_provider: str
    llm_key_vault_id: str | None = None
    bot_token_vault_id: str | None = None
```

---

## TypeScript (Deno) Conventions

**File:** `provisioning/edge-function.ts`

### Naming Patterns

**Variables/functions:** `camelCase` — `hmacSign`, `llmKeyVaultId`, `botTokenVaultId`, `signatureMessage`
**Interfaces:** PascalCase — `ProvisionRequest`, `VaultEntry`
**Constants:** `camelCase` for derived runtime values, `UPPER_SNAKE_CASE` for env var references (only in comments/docs)

### Type Annotations

All function signatures have explicit return types:
```typescript
async function hmacSign(secret: string, message: string): Promise<string>
serve(async (req: Request): Promise<Response> => { ... })
```

Interfaces defined for all request/response shapes.

### Error Handling

Pattern: `try/catch` blocks around every external call (Vault, fetch). Each catch returns a JSON `Response` with appropriate HTTP status. Error messages include detail from the caught exception:
```typescript
return new Response(
  JSON.stringify({
    error: "Failed to store credentials in Vault",
    detail: err instanceof Error ? err.message : String(err),
  }),
  { status: 500, headers: { "Content-Type": "application/json" } },
);
```

### Logging

`console.log()` for normal operation, `console.error()` for failures. Messages are human-readable strings with interpolated values:
```typescript
console.log(`Vault storage OK: llm_key_vault_id=${llmKeyVaultId} ...`);
console.error("Vault storage failed:", err);
```

### Section Headers

Same `// ── Section Name ──────` style as Python files, indicating this is a project-wide convention across languages:
```typescript
// ── Parse and validate request body ────────────────────────────────────────
// ── Store keys in Supabase Vault (pgsodium AES-256-GCM) ────────────────────
```

---

## Bash Conventions

**Files:** `_orchestrator/orch-bootstrap.sh`, `_orchestrator/spawn-worker.sh`, `_orchestrator/heartbeat.sh`, `_orchestrator/rate-limit-watchdog.sh`

### Shebang and Safety Flags

Every script opens with:
```bash
#!/usr/bin/env bash
set -euo pipefail
```

### Naming Patterns

**Script-level variables:** `UPPER_SNAKE_CASE` for all exported/significant variables — `SESSION_NAME`, `ORCH_DIR`, `PROJECT_ROOT`, `WORKER_ID`, `CURRENT_INTERVAL`
**Function names:** `snake_case` — `check_deps()`, `ensure_session()`, `kill_stale_heartbeat()`, `strip_ansi()`, `log_event()`, `check_pane_idle()`, `send_to_pane()`, `collect_workers()`, `determine_interval()`
**Local variables:** `local snake_case` — always declare with `local` inside functions
**Loop variables:** single-word lowercase: `wid`, `status`, `entry`, `session`

### Required ENV Validation

Required ENV vars use the `:?` pattern to fail fast with a message:
```bash
SESSION_NAME="${SESSION_NAME:?SESSION_NAME not set}"
ORCH_DIR="${ORCH_DIR:?ORCH_DIR not set}"
```

Optional ENV vars use `:-` with defaults:
```bash
PROJECT_ROOT="${PROJECT_ROOT:-}"
ORCH_DIR="${ORCH_DIR:-$SCRIPT_DIR}"
```

### Logging Functions

Scripts define colored logging helpers:
```bash
log_info()  { echo -e "${GREEN}[orch]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[orch]${NC} $*"; }
log_error() { echo -e "${RED}[orch]${NC} $*"; }
```

`heartbeat.sh` uses structured JSONL logging via `jq`:
```bash
log_event() {
  jq -nc --arg ts "$ts" --arg type "$event_type" ... '{ts: $ts, type: $type, ...}' >> "$LOG_FILE"
}
```

### Section Separators

Numbered step sections in multi-step scripts use `# ====` style banners:
```bash
# ============================================================
# STEP 1: Create tmux window for worker
# ============================================================
```

Within-section comments use `# ---` style:
```bash
# --- Dependency Check ---
# --- Session Ensure ---
```

### Error Handling

Fatal errors use a `fail()` helper that writes to stderr and exits:
```bash
fail() { echo "[spawn:${WORKER_ID}] FATAL: $*" >&2; exit 1; }
```

Non-fatal errors use `|| true` to suppress exit on `set -e`:
```bash
tmux kill-window -t "$PANE_TARGET" 2>/dev/null || true
```

---

## Documentation Conventions

### Markdown Style

All `.md` files use GitHub-flavored Markdown. README and agent context files use emoji section markers (this is intentional for visual scanning):
```markdown
## 📁 Repository Struktur
## 🔐 Security Highlights
## 🤖 Für Agenten
```

Planning documents (`planning/*.md`) use YAML frontmatter with structured metadata fields: `phase`, `plan`, `type`, `wave`, `depends_on`, `files_modified`, `autonomous`, `requirements`, `must_haves`.

### Language

- User-facing docs (README, AGENT_CONTEXT, AGENT_QUICKREF): German (primary audience is German-speaking operators and agents)
- Code comments and docstrings: English
- Log messages: English
- Planning documents: German

### Security Comments

Any field that handles secrets MUST have an inline comment at every declaration and use site noting it is never written to disk:
```python
llm_key: str,      # NEVER written to disk — Docker ENV only
```
```typescript
llm_key,       // Plain-text for Docker ENV (secured in transit by HTTPS+HMAC)
```

This is a hard project convention, not optional.

---

## Import Organization

### Python

```python
# Standard library
import json
import logging
import os
import pathlib

# Third-party
import docker
import fcntl
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local
from provision import deprovision_container, list_containers, provision_container
```

### TypeScript (Deno)

```typescript
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
```

Pin exact versions in Deno imports.

---

## Composite Naming Patterns

**Container names:** `fc-{user_id}-{agent_id}` — e.g. `fc-oliver-health`
**Instance keys:** `{user_id}-{agent_id}` — e.g. `oliver-health`
**Vault secret names:** `llm_key_{user_id}_{agent_id}`, `bot_token_{user_id}_{agent_id}`
**Workspace paths:** `{WORKSPACE_BASE}/{user_id}/{agent_id}/`
**Worker branches:** `orch/feature/{worker_id}`
**tmux session name:** `orch-{project-name-lowercase-hyphenated}`
**tmux window name:** `{worker_id}` (e.g. `w1`, `w2`)

---

*Convention analysis: 2026-04-02*

# Testing Patterns

**Analysis Date:** 2026-04-02

## Test Coverage Summary

**Current state: No automated tests exist in this codebase.**

No test files were found (`test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`). No test framework configuration files were found (`pytest.ini`, `pyproject.toml`, `jest.config.*`, `vitest.config.*`, `deno.json` with test tasks). No CI pipeline exists (no `.github/` directory).

This is an early-stage project (Phase 1 active, per README roadmap). The codebase is production-oriented code with zero test infrastructure.

---

## Test Framework

**Runner:** Not configured
**Assertion Library:** None
**Run Commands:** None defined

Recommended frameworks for this stack:
- **Python:** `pytest` with `pytest-asyncio` for FastAPI endpoints
- **TypeScript (Deno):** Deno's built-in test runner (`deno test`)
- **Bash:** `bats` (Bash Automated Testing System)

---

## What Is Tested (Manual / Implicit)

### Implicit Testing via Health Checks

The only runtime verification is the health-check loop in `provisioning/provision.py`:

```python
# 10 attempts, 2s apart — GET http://{container_ip}:{port}/health
healthy = False
for attempt in range(1, HEALTH_CHECK_ATTEMPTS + 1):
    time.sleep(HEALTH_CHECK_INTERVAL_SEC)
    try:
        with urllib.request.urlopen(health_url, timeout=3) as resp:
            if resp.status == 200:
                healthy = True
                break
    except Exception as exc:
        log.debug("Health check attempt %d/%d failed: %s", ...)
```

This verifies the container is up after provisioning but is not a test — it is production code.

### Verification Steps in Planning Documents

`planning/260401-92r-PLAN.md` contains `<verify>` blocks with shell one-liners used during initial development:

```bash
python3 -c "import ast; ast.parse(open('...webhook-receiver.py').read()); ast.parse(open('...provision.py').read()); print('Python syntax OK')"
test -f "...Dockerfile" && test -f "...config.toml.tmpl" && echo "All 4 support files exist"
```

These are ad-hoc checks, not a test suite. They verify syntax and file existence only.

---

## What Is NOT Tested (Critical Gaps)

### High-Priority Gaps

**HMAC signature validation (`provisioning/webhook-receiver.py` — `_verify_hmac()`, `_check_timestamp()`):**
- No test for: valid signature accepted
- No test for: invalid signature rejected with 401
- No test for: expired timestamp rejected (replay attack scenario)
- No test for: missing headers rejected
- Risk: Authentication bypass would be silent

**Registry concurrency (`provisioning/provision.py` — `_load_registry()`, `_save_registry()`, `_open_registry_lock()`):**
- No test for: concurrent `provision_container()` calls don't corrupt registry
- No test for: port allocation is unique under concurrent load
- No test for: lock file cleanup after crash
- Risk: Port collision or registry corruption under load

**Container provisioning lifecycle (`provisioning/provision.py` — `provision_container()`):**
- No test for: happy path (requires Docker daemon)
- No test for: stale container removal and re-provisioning
- No test for: `deprovision_container()` cleans workspace
- No test for: health check timeout triggers cleanup and error status
- Risk: Silent failures leave orphaned containers or workspaces

**Webhook endpoint integration (`provisioning/webhook-receiver.py`):**
- No test for: POST `/provision` returns 202 with valid payload
- No test for: DELETE `/provision/{user_id}/{agent_id}` requires HMAC
- No test for: GET `/instances` returns registry contents
- No test for: background task failure does not crash the receiver
- Risk: Endpoint regressions are invisible

**Edge Function key handling (`provisioning/edge-function.ts`):**
- No test for: Vault storage failure returns 500 (not 202)
- No test for: missing required fields returns 400
- No test for: VPS webhook unreachable returns 502
- Risk: Key loss if Vault error path silently proceeds to webhook

### Medium-Priority Gaps

**Orchestrator shell scripts (`_orchestrator/`):**
- `heartbeat.sh` `determine_interval()` — no test for stale worker detection logic
- `heartbeat.sh` `check_pane_idle()` — no test for ANSI strip correctness with edge-case escape sequences
- `spawn-worker.sh` — no test for boot detection timeout fallback
- `rate-limit-watchdog.sh` — no test for exponential backoff calculation

**Config template rendering (`provisioning/provision.py` lines 146-158):**
- No test for: missing `$VAR` in template raises `KeyError`
- No test for: rendered config contains expected values
- No test for: rendered config contains no secret values

**Orchestrator config JSON (`_orchestrator/config.json`):**
- No test for: malformed JSON causes `jq` parse failure and appropriate error

---

## Recommended Test Structure (If Adding Tests)

### Python Tests

Location pattern: `provisioning/tests/` directory

```
provisioning/
├── tests/
│   ├── test_provision.py        # Unit tests for provision.py
│   ├── test_webhook_receiver.py # Integration tests for FastAPI endpoints
│   └── conftest.py              # Fixtures (mock Docker client, temp registry)
├── provision.py
└── webhook-receiver.py
```

**Mocking approach for `provision.py`:**
```python
# Use pytest-mock to mock docker.from_env()
def test_provision_allocates_port(tmp_path, mocker):
    mocker.patch("provision.docker.from_env")
    # Set REGISTRY_PATH and WORKSPACE_BASE to tmp_path
    ...
```

**FastAPI test client approach for `webhook-receiver.py`:**
```python
from fastapi.testclient import TestClient
from webhook_receiver import app

client = TestClient(app)

def test_provision_endpoint_missing_headers():
    response = client.post("/provision", json={...})
    assert response.status_code == 401
```

### Deno Tests

Location pattern: `provisioning/edge-function.test.ts` co-located with the source.

```typescript
import { assertEquals } from "https://deno.land/std@0.208.0/testing/asserts.ts";

Deno.test("hmacSign produces consistent signatures", async () => {
  const sig1 = await hmacSign("secret", "message");
  const sig2 = await hmacSign("secret", "message");
  assertEquals(sig1, sig2);
});
```

### Bash Tests (bats)

Location pattern: `_orchestrator/tests/` directory.

```bash
# _orchestrator/tests/test_heartbeat.bats
@test "determine_interval returns idle when no workers" {
  source "$BATS_TEST_DIRNAME/../heartbeat.sh"
  determine_interval "none"
  [ "$CURRENT_INTERVAL" -eq "$INTERVAL_IDLE" ]
}
```

---

## CI/CD

No CI pipeline exists. No `.github/workflows/` directory is present.

If CI is added, minimum checks should include:
1. Python syntax check: `python3 -m py_compile provisioning/*.py`
2. Python type check: `mypy provisioning/`
3. Deno lint: `deno lint provisioning/edge-function.ts`
4. Shell lint: `shellcheck _orchestrator/*.sh`

---

## Test Data / Fixtures

No fixture files exist. Recommended test data patterns when tests are written:

**Registry fixture (Python):**
```python
@pytest.fixture
def registry_path(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"next_port": 42000, "instances": {}}))
    return path
```

**HMAC test vectors (Python/Deno):**
Keep a fixed secret + message + expected signature in test fixtures to catch any accidental algorithm change.

---

*Testing analysis: 2026-04-02*

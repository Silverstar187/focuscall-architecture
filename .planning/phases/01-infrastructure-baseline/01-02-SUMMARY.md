---
phase: 01-infrastructure-baseline
plan: 02
subsystem: testing
tags: [pytest, pytest-asyncio, httpx, fastapi, docker, unittest.mock]

# Dependency graph
requires:
  - phase: 01-infrastructure-baseline
    provides: provision.py and webhook-receiver.py source files under test
provides:
  - pytest test suite (13 tests) covering provision.py and webhook-receiver.py
  - conftest.py with HMAC and file-isolation fixtures
  - pyproject.toml configuring asyncio_mode=auto
affects:
  - Any phase that modifies provision.py or webhook-receiver.py (tests act as regression guard)
  - CI pipeline setup (these tests are the CI target)

# Tech tracking
tech-stack:
  added: [pytest-asyncio, httpx (AsyncClient + ASGITransport), importlib for hyphenated module names]
  patterns:
    - importlib.import_module for files with hyphens in name
    - patch.object(module, "func") when module imported via importlib
    - provision_env fixture patching both os.environ AND module-level globals
    - _make_docker_mock helper centralizing container mock setup

key-files:
  created:
    - provisioning/pyproject.toml
    - provisioning/conftest.py
    - provisioning/test_webhook.py
    - provisioning/test_provision.py
  modified: []

key-decisions:
  - "Use importlib.import_module('webhook-receiver') because hyphen in filename prevents plain import"
  - "patch.object(webhook_receiver, 'provision_container') instead of patch('webhook_receiver.provision_container') because importlib gives a different namespace"
  - "provision_env patches both os.environ and module-level globals (REGISTRY_PATH etc.) because provision.py reads them at import time"
  - "conftest.py sets WEBHOOK_SECRET with direct assignment before any imports — setdefault is insufficient"

patterns-established:
  - "Pattern: WEBHOOK_SECRET set at top of conftest.py before any app imports"
  - "Pattern: provision_env fixture for all tests that touch registry/workspace/template"
  - "Pattern: _make_docker_mock helper returns (mock_docker, mock_container, mock_client) tuple"

requirements-completed: [INFRA-04]

# Metrics
duration: 8min
completed: 2026-04-02
---

# Phase 01 Plan 02: pytest Test Suite for provision.py and webhook-receiver.py Summary

**13-test pytest suite covering HMAC auth, FastAPI endpoints, and Docker container lifecycle — all mocked, zero external dependencies**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-02T20:52:00Z
- **Completed:** 2026-04-02T21:00:53Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Pytest infrastructure with asyncio_mode=auto and shared fixtures for HMAC generation and tmp_path file isolation
- 7 webhook endpoint tests covering health check, all 401 auth failure paths, and successful provision/deprovision
- 6 provision.py unit tests covering happy path, idempotency, health check failure, deprovision cleanup, registry listing, and port increment

## Task Commits

1. **Task 1: pytest config + shared fixtures** - `8969a0e` (feat)
2. **Task 2: test_webhook.py — 7 endpoint tests** - `e840a6e` (feat)
3. **Task 3: test_provision.py — 6 unit tests** - `edf3b52` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `provisioning/pyproject.toml` - Pytest configuration: asyncio_mode=auto, testpaths=.
- `provisioning/conftest.py` - WEBHOOK_SECRET env setup, make_hmac_headers fixture, provision_env fixture
- `provisioning/test_webhook.py` - 7 FastAPI endpoint tests using AsyncClient + ASGITransport
- `provisioning/test_provision.py` - 6 Docker-mocked unit tests for provision/deprovision/list logic

## Decisions Made

- Used `importlib.import_module("webhook-receiver")` because the hyphen in the filename makes a plain `import` statement syntactically impossible.
- Used `patch.object(webhook_receiver, "provision_container")` instead of `patch("webhook_receiver.provision_container")` because the importlib-loaded module lives in a different namespace.
- The `provision_env` fixture patches both `os.environ` AND the module-level globals (`REGISTRY_PATH`, `WORKSPACE_BASE`, `CONFIG_TEMPLATE_PATH`) in `provision.py` because those constants are read at import time — env var changes alone do not retroactively update them.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all tests passed on first run.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- INFRA-04 requirement satisfied: `pytest provisioning/ -x` exits 0 with 13 green tests
- No Docker daemon, network access, or VPS required to run tests
- Ready for CI integration or Phase 02 work that modifies provisioning backend

---
*Phase: 01-infrastructure-baseline*
*Completed: 2026-04-02*

## Self-Check: PASSED

- FOUND: provisioning/pyproject.toml
- FOUND: provisioning/conftest.py
- FOUND: provisioning/test_webhook.py
- FOUND: provisioning/test_provision.py
- FOUND: .planning/phases/01-infrastructure-baseline/01-02-SUMMARY.md
- FOUND commit: 8969a0e (feat(01-02): pytest config + shared fixtures)
- FOUND commit: e840a6e (feat(01-02): test_webhook.py)
- FOUND commit: edf3b52 (feat(01-02): test_provision.py)

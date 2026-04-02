---
phase: 1
slug: infrastructure-baseline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23.x |
| **Config file** | `provisioning/pyproject.toml` — Wave 0 creates this |
| **Quick run command** | `pytest provisioning/ -x -q` |
| **Full suite command** | `pytest provisioning/ -v --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest provisioning/ -x -q`
- **After every plan wave:** Run `pytest provisioning/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | INFRA-03 | manual | `ssh ... systemctl is-enabled focuscall-webhook` | N/A — manual | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | AUTH-03 | manual | Supabase SQL editor check | N/A — manual | ⬜ pending |
| 01-02-T1 | 01-02 | 1 | INFRA-04 | unit | `pytest provisioning/test_webhook.py -x -q` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 01-02 | 1 | INFRA-04 | unit | `pytest provisioning/test_webhook.py -x -q` | ❌ W0 | ⬜ pending |
| 01-02-T3 | 01-02 | 1 | INFRA-04 | unit | `pytest provisioning/test_provision.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `provisioning/conftest.py` — env setup, shared HMAC fixture, tmp_path registry redirect
- [ ] `provisioning/test_webhook.py` — FastAPI endpoint tests (7 test cases)
- [ ] `provisioning/test_provision.py` — provision.py unit tests (6 test cases)
- [ ] `provisioning/pyproject.toml` — pytest config with `asyncio_mode = "auto"`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| systemd service enabled | INFRA-03 | Requires SSH to VPS | `ssh user@vps systemctl is-enabled focuscall-webhook` — must return `enabled` |
| RLS policy on user_agents | AUTH-03 | Requires Supabase dashboard access | Open Supabase SQL editor, run `SELECT * FROM pg_policies WHERE tablename = 'user_agents';` — must return at least 1 row |

---

## Minimum Test Coverage (INFRA-04)

**test_provision.py** — must cover:
- `provision_container` happy path returns `{"status": "running", ...}`
- `provision_container` returns existing instance if already running (idempotency)
- `deprovision_container` removes container, workspace, registry entry
- `list_containers` returns registry contents
- Port allocation increments `next_port`
- Health check failure returns `{"status": "error", ...}`

**test_webhook.py** — must cover:
- `GET /health` returns 200
- `POST /provision` with valid HMAC + timestamp returns 202
- `POST /provision` with missing headers returns 401
- `POST /provision` with expired timestamp returns 401
- `POST /provision` with wrong signature returns 401
- `DELETE /provision/{uid}/{aid}` with valid HMAC returns 200

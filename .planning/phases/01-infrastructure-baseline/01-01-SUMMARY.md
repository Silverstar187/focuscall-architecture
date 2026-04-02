---
phase: 01-infrastructure-baseline
plan: 01
subsystem: infra
tags: [systemd, supabase, rls, env, webhook, vps]

# Dependency graph
requires: []
provides:
  - focuscall-webhook systemd service enabled for VPS boot persistence
  - .env.local patched with correct WEBHOOK_SECRET (64-char hex) and VPS_WEBHOOK_URL (direct IP)
  - Supabase RLS verified active on user_agents with ALL-cmd per-user policy
affects:
  - 02-provisioning-flow
  - 03-frontend

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct IP VPS_WEBHOOK_URL pattern (bypass broken DNS, use http://91.99.209.45:9000/provision)"
    - "Supabase ALL-cmd RLS policy pattern (single policy covers SELECT/INSERT/UPDATE/DELETE)"

key-files:
  created:
    - .planning/phases/01-infrastructure-baseline/01-01-verification.md
  modified:
    - /Users/pwrunltd/focuscall-ai-frontend/.env.local

key-decisions:
  - "Use direct IP (91.99.209.45) instead of DNS name for VPS_WEBHOOK_URL — DNS was broken at time of fix"
  - "RLS ALL-cmd policy already in place — no additional per-operation policies needed"

patterns-established:
  - "VPS communication: always use direct IP URL until DNS is confirmed stable"
  - "Supabase RLS: verify rowsecurity=true and policy cmd before creating duplicate policies"

requirements-completed:
  - INFRA-03
  - AUTH-03

# Metrics
duration: ~15min (automated) + human action time
completed: 2026-04-02
---

# Phase 01 Plan 01: Infrastructure Baseline Summary

**Webhook receiver pinned to VPS boot via systemd, .env.local fixed with real secret and direct-IP URL, and Supabase RLS confirmed active on user_agents with a single ALL-cmd per-user policy**

## Performance

- **Duration:** ~15 min automation + async human actions
- **Started:** 2026-04-02
- **Completed:** 2026-04-02
- **Tasks:** 2
- **Files modified:** 1 (.env.local) + 1 verification record created

## Accomplishments

- `.env.local` patched: `WEBHOOK_SECRET` filled with real 64-char hex value, `VPS_WEBHOOK_URL` switched from broken DNS to `http://91.99.209.45:9000/provision`
- `focuscall-webhook` systemd service enabled — survives VPS reboot, confirmed `active (running)`
- Supabase `user_agents` RLS verified: `rowsecurity=true`, existing ALL-cmd policy `auth.uid() = user_id` covers every operation — no new SQL needed

## Task Commits

1. **Task 1: Patch .env.local** — `00534fd` (feat)
2. **Task 2: systemd enable + RLS verify (human-action)** — `b1a7512` (chore — verification record)

**Plan metadata:** _(docs commit below)_

## Files Created/Modified

- `/Users/pwrunltd/focuscall-ai-frontend/.env.local` — WEBHOOK_SECRET and VPS_WEBHOOK_URL corrected
- `.planning/phases/01-infrastructure-baseline/01-01-verification.md` — Human-action evidence record

## Decisions Made

- Use direct IP `http://91.99.209.45:9000/provision` for VPS_WEBHOOK_URL — DNS name `vps.focuscall.ai` was unresolvable at fix time; direct IP is reliable until DNS is fixed
- Existing Supabase ALL-cmd RLS policy is sufficient — creating separate SELECT/INSERT/UPDATE/DELETE policies would duplicate coverage; no SQL run

## Deviations from Plan

None — plan executed exactly as written. Task 1 was automated, Task 2 was a human-action checkpoint that returned successful results for both sub-actions.

## Issues Encountered

None. Both manual actions (systemd enable and RLS verification) succeeded on first attempt. RLS was already enabled with a policy more permissive than the plan's minimum requirement (ALL vs SELECT-only spec).

## User Setup Required

None for this plan — all setup was performed by the operator during Task 2.

## Next Phase Readiness

All three infrastructure blockers from STATE.md are now resolved:
- WEBHOOK_SECRET and VPS_WEBHOOK_URL are correct in .env.local
- focuscall-webhook persists across VPS reboots
- user_agents RLS is active and verified

Phase 01 Plan 02 (pytest test suite) was already completed (`28ea487`). Phase 01 is complete — Phase 02 provisioning flow can proceed.

---
*Phase: 01-infrastructure-baseline*
*Completed: 2026-04-02*

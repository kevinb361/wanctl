---
phase: 259-read-only-netwatch-route-ownership-inspection
plan: 02
subsystem: steering-health-daemon
tags: [routeros, netwatch, route-ownership, steering-health, live-proof]

requires:
  - phase: 259-read-only-netwatch-route-ownership-inspection
    provides: RouteOwnershipInspector cached read-only ownership snapshot
provides:
  - ownership_inspection top-level steering health section
  - SteeringDaemon ownership inspector lifecycle wiring
  - live INSPECT_PROOF_PASS harness for deployed /opt/wanctl
  - no-regression coverage for route_management health shape
affects: [steering-daemon, steering-health, phase-260-readiness]

tech-stack:
  added: []
  patterns:
    - additive health section beside existing route_management contract
    - per-file /opt/wanctl deploy with live proof harness
    - readonly_validator gate before RouterOS proof harness run_cmd

key-files:
  created:
    - scripts/phase259-ownership-proof.py
    - tests/test_phase259_ownership_proof.py
    - .planning/phases/259-read-only-netwatch-route-ownership-inspection/VERIFICATION.md
  modified:
    - src/wanctl/steering/health.py
    - src/wanctl/steering/daemon.py
    - tests/test_health_check.py
    - pyproject.toml

key-decisions:
  - "ownership_inspection is a top-level health sibling of route_management; route_management shape remains unchanged."
  - "SteeringDaemon starts RouteOwnershipInspector unconditionally so inspection is independent of route-management mode."
  - "The live proof harness validates read-only commands before any RouterOS client run_cmd call."
patterns-established:
  - "Live RouterOS ownership proof records counts and attribution only, not route detail or secrets."
  - "Deployed script bootstraps /opt as import path before asserting wanctl imports resolve under /opt/wanctl."
requirements-completed: [INSPECT-03, SAFE-21]

duration: 45min
completed: 2026-06-25
---

# Phase 259 Plan 02: Ownership Health Wiring and Live Proof Summary

**Steering health now exposes cached read-only route ownership evidence with live cake-shaper proof and unchanged route_management payload shape**

## Performance

- **Duration:** 45 min
- **Started:** 2026-06-25T00:58:00Z
- **Completed:** 2026-06-25T01:42:55Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- Added a top-level `ownership_inspection` section to steering health, sourced from the cached inspector snapshot and rendered as a sibling of `route_management`.
- Wired `RouteOwnershipInspector` into `SteeringDaemon`: construct/start after route-management initialization, expose `ownership_inspection` from `get_health_data()`, and stop before closing the router client during cleanup.
- Added `scripts/phase259-ownership-proof.py`, a deployed proof harness that validates read-only RouterOS commands before any `run_cmd`, runs one inspector refresh, and emits `INSPECT_PROOF_PASS` / `INSPECT_PROOF_FAIL` verdicts.
- Deployed the changed files to `cake-shaper`, ran the live proof over RouterOS REST, restarted `steering.service`, and confirmed `ownership_inspection` is present in `:9102/health` while `route_management` keys remain unchanged.

## Task Commits

Each task was committed atomically:

1. **Task W0-1: Health/proof RED tests** - `9fb53072` (test)
2. **Task W1-1: ownership_inspection health section** - `10532707` (feat)
3. **Task W1-2: daemon inspector lifecycle wiring** - `9ae06482` (feat)
4. **Task W2-1: live ownership proof harness** - `c7e2b9a1` (feat)
5. **Deploy fix: proof harness /opt import bootstrap** - `47d1234f` (fix)

**Plan metadata:** pending in docs closeout commit

## Files Created/Modified

- `src/wanctl/steering/health.py` - adds `_build_ownership_inspection_section()` and top-level `ownership_inspection` wiring.
- `src/wanctl/steering/daemon.py` - starts/stops `RouteOwnershipInspector` and includes cached snapshot in daemon health data.
- `scripts/phase259-ownership-proof.py` - live read-only ownership proof harness for deployed `/opt/wanctl`.
- `tests/test_phase259_ownership_proof.py` - harness happy-path, mutation rejection before `run_cmd`, and fail-closed inspector-error tests.
- `tests/test_health_check.py` - ownership health rendering and route-management shape no-regression tests.
- `pyproject.toml` - allows the plan-required hyphenated proof harness filename.
- `.planning/phases/259-read-only-netwatch-route-ownership-inspection/VERIFICATION.md` - automated and live proof evidence.

## Decisions Made

- Kept `ownership_inspection` separate from `route_management` instead of nesting it. This preserves existing health consumers while making ownership evidence explicit.
- Started the inspector unconditionally in the daemon, matching the plan requirement that inspection must work even when route-management is off or dry-run.
- Used service-equivalent secret loading for the live harness after the first attempt failed closed with REST 401; secret values were not printed or persisted.
- Added `/opt` import bootstrapping to the proof harness because direct script execution from `/opt/wanctl/scripts` does not naturally put `/opt` on `sys.path` outside the systemd service environment.

## Deviations from Plan

### Auto-fixed Issues

**1. Deployed proof harness import path**
- **Found during:** live deploy/proof run preparation
- **Issue:** The standalone script imported `wanctl` before ensuring `/opt` was on `sys.path`; direct `python3 /opt/wanctl/scripts/phase259-ownership-proof.py ...` would fail outside the service environment.
- **Fix:** Insert `/opt` into `sys.path` when `/opt/wanctl` exists, before importing `wanctl` modules.
- **Files modified:** `scripts/phase259-ownership-proof.py`
- **Verification:** `tests/test_phase259_ownership_proof.py` passed; ruff passed; deployed script resolved `wanctl.__file__=/opt/wanctl/__init__.py`.
- **Committed in:** `47d1234f`

---

**Total deviations:** 1 auto-fixed (deploy/runtime import-path correctness).
**Impact on plan:** No scope change; required to make the planned operator command work as written.

## Issues Encountered

- Broad `ruff check src/wanctl/steering tests scripts` reports unrelated pre-existing lint failures in older scripts/tests. Touched-file ruff passed, and the plan's phase test slice passed.
- First live proof run failed closed with RouterOS REST 401 because the standalone shell did not load `/etc/wanctl/secrets`. Re-running with the service-equivalent environment produced `INSPECT_PROOF_PASS` without exposing secret values.
- Remote `py_compile` initially failed writing `__pycache__` under root-owned `/opt/wanctl/scripts` when run as the SSH user. Re-ran the compile under `sudo -n env PYTHONPATH=/opt`, which passed.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_phase259_ownership_proof.py -q` → 3 passed
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -k "ownership or route_management" -q` → 3 passed
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_route_ownership_inspector.py -q` → 209 passed
- `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py tests/test_phase259_ownership_proof.py tests/test_health_check.py tests/test_route_ownership_guard.py tests/test_routeros_rest.py tests/test_readonly_validator.py -q` → 332 passed
- `.venv/bin/ruff check src/wanctl/steering/route_ownership_inspector.py src/wanctl/steering/health.py src/wanctl/steering/daemon.py tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py tests/test_phase259_ownership_proof.py tests/test_health_check.py scripts/phase259-ownership-proof.py pyproject.toml` → All checks passed
- `git diff --check` → clean
- Live proof on `cake-shaper` → `INSPECT_PROOF_PASS observed_owner=netwatch configured_owner=netwatch match=True netwatch_entries=3 route_mutating_active=4 total_routes=17 default_routes=4`
- Post-restart health proof → `status=healthy`, `steering=SPECTRUM_GOOD`, `ownership_inspection_present=True`, `inspector_status=ok`, and `route_management_keys=enabled,mode,active_owner,active_allowed,blocked_reason,guard,reconciliation,circuit_breaker,last_intended_action,last_applied_action,rollback_ready,last_event`

## User Setup Required

None - the operator-gated live proof and service restart were completed on `cake-shaper`. Backup anchor: `/opt/wanctl/.phase259-backup-20260625T014037Z`.

## Next Phase Readiness

Phase 260 can consume live `ownership_inspection` evidence from steering health and rerun the dry-run observation/canary-readiness packet with Netwatch still as active owner. SAFE-21 remains in force: no active route-owner flip is included in this milestone.

---
*Phase: 259-read-only-netwatch-route-ownership-inspection*
*Completed: 2026-06-25*

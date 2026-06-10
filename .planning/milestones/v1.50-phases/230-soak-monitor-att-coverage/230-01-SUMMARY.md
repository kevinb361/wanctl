---
phase: 230-soak-monitor-att-coverage
plan: 01
subsystem: ops-monitoring
tags: [bash, soak-monitor, cake-autorate, att, pytest, shellcheck]

requires:
  - phase: 229-att-deploy-path-artifact-tests
    provides: ATT cake-autorate artifact inventory and live unit names
provides:
  - WAN-parameterized external cake-autorate mode detection for soak-monitor error scans
  - ATT live-unit coverage for per-WAN and aggregate service error scans
  - Fake-ssh regression test proving aggregate JSON units reflect external mode without host contact
affects: [phase-230, phase-231, soak-monitor, migration-hardening]

tech-stack:
  added: []
  patterns:
    - pytest static script assertions plus fake PATH ssh shim for bash behavior testing
    - bash arrays populated with read -r -a before passing unit lists to check_errors

key-files:
  created:
    - tests/test_soak_monitor_att_coverage.py
    - .planning/phases/230-soak-monitor-att-coverage/deferred-items.md
  modified:
    - scripts/soak-monitor.sh
    - .claude/context.md

key-decisions:
  - "Kept native wanctl@<wan>.service as the fallback scan path when a WAN is not in external cake-autorate mode."
  - "Derived aggregate JSON units and non-JSON labels/hints from the same live-unit array to prevent per-WAN and aggregate drift."

patterns-established:
  - "External-mode scan units are selected by is_external_cake_mode + external_units_for rather than Spectrum-only branches."
  - "Runtime output behavior for soak-monitor --json is tested with a local fake ssh shim, avoiding live host contact in the default suite."

requirements-completed: [MON-01, MON-02]

duration: 9min
completed: 2026-06-10
---

# Phase 230 Plan 01: soak-monitor ATT Coverage Summary

**soak-monitor now routes ATT external-controller error scans through the live cake-autorate ATT units, with fake-ssh regression coverage for aggregate JSON output.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-10T02:12:10Z
- **Completed:** 2026-06-10T02:21:09Z
- **Tasks:** 3 completed
- **Files modified:** 4

## Accomplishments

- Added RED regression coverage for ATT live-unit scanning, generalized mode detection, aggregate `--json` unit output, and shellcheck cleanliness.
- Added `is_external_cake_mode` and `external_units_for`, including the ATT-only Silicom watchdog unit.
- Replaced all four Spectrum-hardcoded error-scan call sites with per-WAN external-mode routing and array-safe `check_errors` calls.
- Updated aggregate JSON/non-JSON service scans so their reported unit lists are generated from the same live-unit array used for journal scanning.

## Task Commits

1. **Task 1: Write failing regression test for ATT live-unit coverage and generalized mode detection** - `b94bb57e` (test)
2. **Task 2: Add generalized external-mode predicate + per-WAN unit map; fix both per-WAN error branches** - `2cb3ad14` (feat)
3. **Task 3: Generalize the aggregate summary scan (JSON + non-JSON) to iterate WANs through external mode** - `6f941c5f` (feat)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `tests/test_soak_monitor_att_coverage.py` - New static and fake-ssh behavior regression tests for ATT live-unit coverage.
- `scripts/soak-monitor.sh` - Generalized external-mode predicate, per-WAN unit map, per-WAN scan dispatch, aggregate unit generation, JSON output, and journal hint.
- `.claude/context.md` - Added current validation note for the new Phase 230 regression coverage to satisfy the repository documentation hook.
- `.planning/phases/230-soak-monitor-att-coverage/deferred-items.md` - Logged out-of-scope full-suite failures from historical Phase 220/221 boundary tests.

## Decisions Made

- Kept `wanctl@${wan}.service` as the fallback when external mode is not detected, preserving rollback/native-mode support.
- Used `read -r -a` arrays from `external_units_for` before calling `check_errors`, avoiding unquoted command substitution and any `SC2046` suppression.
- Built aggregate JSON units, non-JSON labels, and journal hints from the same generated unit array so reporting cannot drift from what is scanned.

## Deviations from Plan

### Auto-fixed Issues

None - no Rules 1-3 implementation deviations were required.

### Execution Adjustments

**1. Repository hook documentation note**
- **Found during:** Task 1 commit
- **Issue:** The pre-commit hook requires documentation context when new Python test functions are introduced.
- **Fix:** Added a concise `.claude/context.md` validation note for the new Phase 230 regression coverage.
- **Files modified:** `.claude/context.md`
- **Verification:** Commit hook passed without `--no-verify`.
- **Committed in:** `b94bb57e`

---

**Total deviations:** 0 auto-fixed; 1 execution adjustment.
**Impact on plan:** No behavior scope creep. The documentation note is local context only.

## Issues Encountered

- Full `.venv/bin/pytest tests/ -q` reported 21 failures in historical Phase 220/221 boundary tests because they refuse committed `src/wanctl/` drift since `PHASE214_BASE_SHA=50f3d5136830c284b190b29de939a84406531ecc`. This plan did not modify `src/wanctl/`; focused Plan 230 tests and SAFE-14 plan-scope controller-diff checks passed. Logged in `deferred-items.md`.

## Verification

- `shellcheck -S error scripts/soak-monitor.sh` — PASS
- `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` — PASS (`5 passed`)
- `grep -c 'is_spectrum_cake_trial_active "kevin@10.10.110.223"' scripts/soak-monitor.sh` — PASS (`0`)
- `grep -c 'shellcheck disable=SC2046' scripts/soak-monitor.sh` — PASS (`0`)
- `git diff --stat 87980bdf -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/backends/ src/wanctl/alert_engine.py src/wanctl/fusion_healer.py` — PASS (empty)
- `.venv/bin/pytest tests/ -q` — DEFERRED/PRE-EXISTING (`5355 passed, 12 skipped, 2 deselected, 21 failed` in Phase 220/221 boundary tests unrelated to this plan)

## Known Stubs

None. Stub-pattern scan only matched local string initializers used to build JSON/labels in `scripts/soak-monitor.sh`; no placeholder UI/data stubs were introduced.

## Threat Flags

None. The only security-relevant surface is the planned read-only SSH/systemctl/journalctl monitoring path already covered by the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 230-02: read-only ATT live-unit scan evidence and SAFE-14 boundary proof. No controller-path files were touched by this plan.

## Self-Check: PASSED

- Found files: `tests/test_soak_monitor_att_coverage.py`, `scripts/soak-monitor.sh`, `230-01-SUMMARY.md`, `deferred-items.md`
- Found commits: `b94bb57e`, `2cb3ad14`, `6f941c5f`

---
*Phase: 230-soak-monitor-att-coverage*
*Completed: 2026-06-10*

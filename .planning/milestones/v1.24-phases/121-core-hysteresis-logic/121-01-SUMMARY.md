---
phase: 121-core-hysteresis-logic
plan: 01
subsystem: controller
tags: [hysteresis, dwell-timer, deadband, state-machine, tdd]

# Dependency graph
requires: []
provides:
  - "QueueController dwell timer gating GREEN->YELLOW transitions (HYST-01)"
  - "QueueController deadband margin for YELLOW->GREEN recovery (HYST-02)"
  - "Dwell counter reset on below-threshold cycles (HYST-03)"
  - "Direction parity: adjust() and adjust_4state() both protected (HYST-04)"
affects:
  [
    122-hysteresis-configuration,
    123-hysteresis-observability,
    124-production-validation,
  ]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "dwell timer counter pattern (consecutive cycle gating)",
      "asymmetric deadband (entry vs exit threshold split)",
    ]

key-files:
  created: []
  modified:
    - src/wanctl/autorate_continuous.py
    - tests/test_queue_controller.py

key-decisions:
  - "Used >= for deadband boundary (exact boundary stays YELLOW, must drop strictly below)"
  - "Deferred existing fixture backward-compat updates to GREEN phase (can't add kwargs before constructor accepts them)"

patterns-established:
  - "Dwell timer: _yellow_dwell counter increments on above-threshold, resets on below-threshold, gates transition at dwell_cycles"
  - "Asymmetric deadband: entry at threshold, exit at (threshold - deadband_ms) with >= comparison"
  - "Backward compat: dwell_cycles=0, deadband_ms=0.0 disables hysteresis (existing tests use this)"

requirements-completed: [HYST-01, HYST-02, HYST-03, HYST-04]

# Metrics
duration: 12min
completed: 2026-03-31
---

# Phase 121 Plan 01: Core Hysteresis Logic Summary

**Dwell timer (3-cycle gate) and deadband margin (3ms hysteresis band) on QueueController GREEN/YELLOW boundary for both upload and download state machines**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-31T10:24:39Z
- **Completed:** 2026-03-31T10:36:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- QueueController absorbs transient EWMA crossings: <3 consecutive above-threshold cycles stay GREEN
- YELLOW->GREEN recovery requires delta below (threshold - 3.0ms), preventing boundary oscillation
- Both adjust() (3-state/upload) and adjust_4state() (4-state/download) protected with identical logic
- RED transitions remain immediate (1 sample), SOFT_RED sustain counter unchanged
- 22 new hysteresis tests added, all 68 test_queue_controller tests pass, 87 QueueController-related tests pass
- dwell_cycles=0, deadband_ms=0.0 backward compatibility escape hatch verified

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for dwell timer, deadband, and direction parity** - `80a4d79` (test)
2. **Task 2: Implement dwell timer and deadband in QueueController** - `d74db1a` (feat)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Added dwell_cycles, deadband_ms params to QueueController.**init**; rewrote zone classification in adjust() and adjust_4state() with dwell gate and deadband logic
- `tests/test_queue_controller.py` - Added 22 new hysteresis tests (6 test classes), 2 new hysteresis fixtures, updated 4 existing constructors for backward compat

## Decisions Made

- Used `>=` comparison for deadband boundary (delta exactly at threshold - deadband stays YELLOW; must drop strictly below to recover to GREEN)
- Deferred existing fixture `dwell_cycles=0` updates from TDD RED phase to GREEN phase (can't pass kwargs the constructor doesn't accept yet)
- Inline QueueController constructors in transition sequence tests updated with `dwell_cycles=0, deadband_ms=0.0` to preserve immediate-transition behavior

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed deadband boundary comparison operator**

- **Found during:** Task 2 (implementation)
- **Issue:** Plan specified `delta > (target_delta - deadband_ms)` but test expects exact boundary (delta == threshold - deadband) to stay YELLOW
- **Fix:** Changed to `delta >= (target_delta - deadband_ms)` in both adjust() and adjust_4state()
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** test_deadband_at_exact_boundary passes
- **Committed in:** d74db1a (Task 2 commit)

**2. [Rule 1 - Bug] Reordered fixture backward-compat updates**

- **Found during:** Task 1 (test writing)
- **Issue:** Plan said to update existing fixtures with dwell_cycles=0 in RED phase, but constructor doesn't accept kwargs yet causing TypeError on all existing tests
- **Fix:** Deferred fixture updates to Task 2 (GREEN phase) when constructor accepts the new params
- **Files modified:** tests/test_queue_controller.py
- **Verification:** All 45 existing tests pass in RED phase, all 68 tests pass in GREEN phase
- **Committed in:** d74db1a (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing test failures in test_container_network_audit.py (ModuleNotFoundError) and test_asymmetry_health.py (MagicMock serialization) -- unrelated to this plan, not addressed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Hysteresis logic is complete with hardcoded defaults (dwell_cycles=3, deadband_ms=3.0)
- Phase 122 (Hysteresis Configuration) can now wire these params to YAML config and SIGUSR1 hot-reload
- Phase 123 (Observability) can expose \_yellow_dwell counter in health endpoint

## Self-Check: PASSED

- SUMMARY.md exists: FOUND
- Commit 80a4d79 (Task 1): FOUND
- Commit d74db1a (Task 2): FOUND
- src/wanctl/autorate_continuous.py: FOUND
- tests/test_queue_controller.py: FOUND

---

_Phase: 121-core-hysteresis-logic_
_Completed: 2026-03-31_

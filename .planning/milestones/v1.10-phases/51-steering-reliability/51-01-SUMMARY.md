---
phase: 51-steering-reliability
plan: 01
subsystem: steering
tags: [daemon, state-machine, anomaly-detection, logging, watchdog]

# Dependency graph
requires: []
provides:
  - Legacy state name warning logging with rate-limiting in _is_current_state_good
  - Anomaly detection cycle-skip semantics (return True instead of False)
affects: [steering, daemon-loop, watchdog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Log-once pattern via _legacy_state_warned set for rate-limited warnings"

key-files:
  created: []
  modified:
    - src/wanctl/steering/daemon.py
    - tests/test_steering_daemon.py

key-decisions:
  - "Log-once pattern using set rather than counter -- simpler, zero-overhead after first warning per name"
  - "Anomaly cycle-skip uses same return True as normal success -- daemon loop treats both as healthy"

patterns-established:
  - "Log-once set pattern: _legacy_state_warned tracks warned names, O(1) lookup at 20Hz"

requirements-completed: [STEER-01, STEER-02]

# Metrics
duration: 14min
completed: 2026-03-07
---

# Phase 51 Plan 01: Legacy State Warning + Anomaly Cycle-Skip Summary

**Legacy state names log warnings with rate-limiting; anomaly detection returns True (cycle-skip) to prevent watchdog escalation on transient network events**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-07T11:09:55Z
- **Completed:** 2026-03-07T11:24:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- STEER-01: _is_current_state_good logs a warning when legacy state names (SPECTRUM_GOOD, WAN1_GOOD, WAN2_GOOD) match, with log-once semantics per name per daemon lifetime
- STEER-02: Anomaly detection (delta > MAX_SANE_RTT_DELTA_MS) now returns True from run_cycle, preventing consecutive_failures increment and avoiding watchdog restart on transient network anomalies
- 10 new tests added (6 legacy state, 4 anomaly cycle-skip), 2010 total tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Legacy state warning + anomaly cycle-skip semantics**
   - `463d5e4` (test) - failing tests for legacy state warning and anomaly cycle-skip
   - `60ce446` (feat) - implementation passing all tests

## Files Created/Modified
- `src/wanctl/steering/daemon.py` - Added _legacy_state_warned set to __init__, warning logging in _is_current_state_good, changed anomaly return False to True
- `tests/test_steering_daemon.py` - TestLegacyStateWarning (6 tests), TestAnomalyCycleSkip (4 tests), updated existing anomaly test assertion

## Decisions Made
- Log-once pattern using a set (`_legacy_state_warned`) rather than a counter or external rate-limiter -- simplest approach with O(1) lookup per cycle at 20Hz
- Anomaly returns same `True` as normal success -- the daemon loop only cares about success/failure, and anomaly-skip is intentionally "not a failure"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing anomaly test assertion**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Existing test `test_run_cycle_extreme_rtt_delta_skips_cycle` asserted `result is False`, which contradicts the STEER-02 fix
- **Fix:** Changed assertion to `result is True` with comment explaining STEER-02 semantics
- **Files modified:** tests/test_steering_daemon.py
- **Verification:** All 190 tests in test_steering_daemon.py pass
- **Committed in:** 60ce446 (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in existing test matching old behavior)
**Impact on plan:** Necessary correction -- existing test was asserting the buggy behavior that STEER-02 fixes.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Legacy state warning and anomaly cycle-skip are complete
- Ready for 51-02 plan execution (next steering reliability tasks)

---
*Phase: 51-steering-reliability*
*Completed: 2026-03-07*

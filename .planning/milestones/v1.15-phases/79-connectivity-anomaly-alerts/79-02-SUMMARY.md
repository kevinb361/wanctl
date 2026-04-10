---
phase: 79-connectivity-anomaly-alerts
plan: 02
subsystem: alerting
tags: [anomaly-detection, baseline-drift, flapping, deque, ewma]

requires:
  - phase: 78-congestion-steering-alerts
    provides: AlertEngine fire() pattern, per-rule config overrides
  - phase: 79-connectivity-anomaly-alerts/01
    provides: Connectivity alert wiring, _check_connectivity_alerts method
provides:
  - _check_baseline_drift() method for EWMA baseline RTT drift detection
  - _check_flapping_alerts() method for congestion zone flapping detection
  - Independent DL/UL flapping tracking with sliding window deques
affects: [80-alert-delivery-dashboard]

tech-stack:
  added: []
  patterns:
    - "Sliding window deque for transition counting (flapping detection)"
    - "Absolute percentage drift for bidirectional threshold detection"
    - "Per-rule parameter override (drift_threshold_pct, flap_threshold, flap_window_sec)"

key-files:
  created:
    - tests/test_anomaly_alerts.py
  modified:
    - src/wanctl/autorate_continuous.py

key-decisions:
  - "Baseline drift uses absolute percentage (detects both ISP degradation and routing improvements)"
  - "Flapping uses simple deque of monotonic timestamps (lighter than FlapDetector pattern from steering)"
  - "Per-rule overrides for all thresholds (drift_threshold_pct, flap_threshold, flap_window_sec)"

patterns-established:
  - "Deque-based sliding window: append timestamp on change, prune older-than-window, count remaining"
  - "No timer state needed for baseline drift -- cooldown suppression handles re-fire naturally"

requirements-completed: [ALRT-06, ALRT-07]

duration: 6min
completed: 2026-03-12
---

# Phase 79 Plan 02: Anomaly Alerts Summary

**Baseline RTT drift detection (absolute %) and congestion zone flapping (sliding window deque) with independent DL/UL tracking**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-12T16:15:32Z
- **Completed:** 2026-03-12T16:21:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Baseline drift fires when EWMA baseline diverges beyond configured percentage from initial baseline (default 50%)
- Congestion zone flapping detection fires independently for DL and UL when transitions exceed threshold in time window
- All 17 new tests pass, all 25 existing congestion alert tests pass (42 total, no regressions)
- Per-rule overrides for drift_threshold_pct, flap_threshold, flap_window_sec, severity

## Task Commits

Each task was committed atomically:

1. **Task 1: Baseline drift detection with percentage threshold** - `0df847b` (feat)
2. **Task 2: Congestion zone flapping detection with independent DL/UL tracking** - `e9b7aa1` (feat)

_Note: TDD tasks -- tests and implementation committed together after GREEN phase_

## Files Created/Modified

- `tests/test_anomaly_alerts.py` - 17 tests for baseline drift (7) and flapping detection (10), 523 lines
- `src/wanctl/autorate_continuous.py` - Added `from collections import deque`, flapping state vars in **init**, `_check_baseline_drift()`, `_check_flapping_alerts()`, wired into `run_cycle()`

## Decisions Made

- Used absolute percentage for drift detection so both upward drift (ISP degradation) and downward drift (routing change) are detected
- Used simple deque of monotonic timestamps for flapping (lighter than the FlapDetector pattern from steering_confidence.py which uses TimerState and penalty thresholds)
- No timer state needed for baseline drift -- AlertEngine cooldown suppression handles re-fire timing naturally
- Strict `>` comparison for window pruning (transition at exactly window boundary is kept)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All anomaly detection alerts complete (ALRT-06, ALRT-07)
- Phase 79 complete (connectivity + anomaly alerts)
- Ready for Phase 80 (alert delivery/dashboard integration)

## Self-Check: PASSED

- tests/test_anomaly_alerts.py: FOUND
- src/wanctl/autorate_continuous.py: FOUND
- Commit 0df847b: FOUND
- Commit e9b7aa1: FOUND

---

_Phase: 79-connectivity-anomaly-alerts_
_Completed: 2026-03-12_

---
phase: 160-congestion-detection
plan: 02
subsystem: controller
tags: [cake, refractory, congestion-detection, queue-controller, health-endpoint]

requires:
  - phase: 160-01
    provides: "QueueController CAKE-aware adjust_4state/adjust with cake_snapshot param"
provides:
  - "Refractory period masking CAKE signals for N cycles after dwell bypass"
  - "CAKE snapshot passing through _run_congestion_assessment hot path"
  - "YAML config parsing for detection thresholds with bounds validation"
  - "SIGUSR1 reload updates detection thresholds and refractory state"
  - "Health endpoint detection section with refractory and counter values"
affects: [160-congestion-detection, health-endpoint, production-deploy]

tech-stack:
  added: []
  patterns: ["refractory period anti-oscillation", "per-direction refractory independence"]

key-files:
  created: []
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - tests/test_wan_controller.py
    - tests/test_cake_signal.py
    - tests/test_health_check.py
    - tests/test_asymmetry_gate.py

key-decisions:
  - "Refractory masking applied before passing snapshot to QueueController, not after"
  - "DL and UL refractory counters are fully independent"
  - "Disabling cake_signal via SIGUSR1 zeros refractory counters and detection thresholds"

patterns-established:
  - "Refractory period: counter set on dwell bypass, decremented each cycle, masks snapshot to None"
  - "Detection threshold parsing: isinstance + bool exclusion + bounds clamping pattern"

requirements-completed: [DETECT-01, DETECT-02, DETECT-03, DETECT-04]

duration: 32min
completed: 2026-04-10
---

# Phase 160 Plan 02: CAKE Detection Integration Summary

**Refractory period anti-oscillation with CAKE snapshot wiring through congestion assessment, YAML threshold parsing, and health endpoint detection state**

## Performance

- **Duration:** 32 min
- **Started:** 2026-04-10T01:20:34Z
- **Completed:** 2026-04-10T01:52:54Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- CAKE snapshots now flow through _run_congestion_assessment to QueueController with refractory masking
- Refractory period prevents cascading rate reductions: 40 cycles (2s) cooldown after dwell bypass
- Detection thresholds parsed from YAML with bounds validation (drop_rate [1.0, 1000.0], backlog [100, 10M], refractory [1, 200])
- SIGUSR1 reload updates thresholds, refractory cycles, and QueueController state (zeroes on disable)
- Health endpoint exposes detection section: refractory remaining, configured cycles, bypass/suppression counts
- 18 new tests covering refractory, config parsing, reload, and health endpoint detection

## Task Commits

Each task was committed atomically:

1. **Task 1: Refractory period + congestion assessment wiring + config parsing** - `4d1b01b` (feat)
2. **Task 2: Refractory period + config + health tests** - `963cdad` (test)
3. **Task 3: Full regression gate** - `d96ad76` (fix)

## Files Created/Modified
- `src/wanctl/wan_controller.py` - Refractory counters, CAKE snapshot passing, detection config parsing, SIGUSR1 reload, health detection section
- `src/wanctl/health_check.py` - Detection subsection in _build_cake_signal_section
- `tests/test_wan_controller.py` - TestRefractoryPeriod (6 tests)
- `tests/test_cake_signal.py` - TestCakeSignalConfigDetectionParsing (6 tests), TestCakeSignalReloadDetection (3 tests)
- `tests/test_health_check.py` - 3 detection tests in TestBuildCakeSignalSection
- `tests/test_asymmetry_gate.py` - Fixed capture_adjust to accept cake_snapshot kwarg

## Decisions Made
- Refractory masking applied before snapshot reaches QueueController (not after zone decision) for clean separation
- DL/UL refractory fully independent -- one direction's bypass doesn't affect the other
- Disabling cake_signal via SIGUSR1 resets both refractory counters to 0 and zeros all thresholds

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed capture_adjust signature in test_asymmetry_gate.py**
- **Found during:** Task 3 (Full regression gate)
- **Issue:** TestCongestionAssessmentIntegration tests used custom capture_adjust functions without **kwargs, failing when cake_snapshot kwarg was passed
- **Fix:** Added **kwargs to both capture_adjust function signatures
- **Files modified:** tests/test_asymmetry_gate.py
- **Verification:** All 28 asymmetry gate tests pass
- **Committed in:** d96ad76

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Fix necessary for test compatibility with new cake_snapshot parameter. No scope creep.

## Issues Encountered
- Pre-existing test failures (RateLimiter MagicMock TypeError, missing configs/steering.yaml, integration test crash) confirmed as unrelated to Phase 160 changes

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CAKE detection fully wired: snapshots flow through hot path with refractory safety
- Health endpoint exposes full detection observability
- Ready for Phase 160 Plan 03 (if any) or production deploy
- DETECT-04 verified: only drop_rate (excluding Bulk) used in detection paths, no total_drop_rate

## Self-Check: PASSED

All 6 files verified present. All 3 commit hashes verified in git log.

---
*Phase: 160-congestion-detection*
*Completed: 2026-04-10*

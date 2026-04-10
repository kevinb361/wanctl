---
phase: 101-signal-processing-tuning
plan: 01
subsystem: tuning
tags: [hampel, ewma, signal-processing, settling-time, outlier-rate, jitter]

# Dependency graph
requires:
  - phase: 98-tuning-foundation
    provides: TuningResult, SafetyBounds, StrategyFn type alias, analyzer framework
  - phase: 99-congestion-threshold-calibration
    provides: StrategyFn pattern reference (congestion_thresholds.py)
provides:
  - tune_hampel_sigma: StrategyFn for Hampel sigma optimization from outlier rate
  - tune_hampel_window: StrategyFn for Hampel window sizing from jitter
  - tune_alpha_load: StrategyFn for load EWMA time constant from settling time
affects: [101-02, 102-advanced-tuning]

# Tech tracking
tech-stack:
  added: []
  patterns: [target-based-tuning, counter-delta-rate, jitter-window-interpolation, step-response-analysis]

key-files:
  created:
    - src/wanctl/tuning/strategies/signal_processing.py
    - tests/test_signal_processing_strategy.py
  modified: []

key-decisions:
  - "tune_alpha_load outputs load_time_constant_sec (0.5-10s range), NOT raw alpha_load, to survive clamp_to_step rounding and trivial change filter"
  - "Outlier rate computed from counter deltas between consecutive 1m timestamps, divided by 1200 samples/min"
  - "Jitter-to-window mapping uses linear interpolation between MIN_WINDOW=5 and MAX_WINDOW=15"
  - "Step detection requires delta > max(2x median_jitter, 2.0ms) for robustness"
  - "Conservative 20% move toward target tc per tuning cycle to prevent oscillation"

patterns-established:
  - "Counter-delta rate: monotonic counter metrics (outlier_count) analyzed via consecutive deltas, negative deltas discarded for counter resets"
  - "Target-based tuning: sigma tuned toward 5-15% outlier rate range rather than optimizing a derived metric (avoids feedback loop)"
  - "Step response settling: measure EWMA settling time by scanning forward from detected RTT steps"

requirements-completed: [SIGP-01, SIGP-02, SIGP-03]

# Metrics
duration: 6min
completed: 2026-03-19
---

# Phase 101 Plan 01: Signal Processing Tuning Strategies Summary

**Three StrategyFn functions for Hampel sigma (outlier rate target 5-15%), Hampel window (jitter-based interpolation), and load EWMA time constant (step response settling time analysis)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-19T11:52:19Z
- **Completed:** 2026-03-19T11:58:36Z
- **Tasks:** 1 (TDD: RED + GREEN + bug fix)
- **Files modified:** 2

## Accomplishments
- Three signal processing tuning strategies implemented as pure StrategyFn functions
- tune_hampel_sigma adjusts sigma toward target outlier rate range (5-15%) using counter deltas
- tune_hampel_window maps jitter level to window size (5-15) via linear interpolation
- tune_alpha_load outputs load_time_constant_sec from step response settling time analysis
- 20 unit tests covering sufficient/insufficient data, convergence, direction, field correctness
- All tests pass, ruff clean, mypy clean

## Task Commits

Each task was committed atomically (TDD pattern):

1. **Task 1 RED: Failing tests** - `362d36e` (test)
2. **Task 1 GREEN: Implementation + test fixes** - `3535153` (feat)
3. **Task 1 bug fix: Log format string** - `ab2930e` (fix)

## Files Created/Modified
- `src/wanctl/tuning/strategies/signal_processing.py` - Three StrategyFn functions (384 lines)
- `tests/test_signal_processing_strategy.py` - 20 unit tests across 3 test classes (431 lines)

## Decisions Made
- tune_alpha_load outputs parameter="load_time_constant_sec" (NOT "alpha_load") to survive clamp_to_step rounding and 0.1 trivial change filter (Pitfall 3 from research)
- Outlier rate computed as delta of consecutive 1m outlier_count values divided by 1200 samples/min (Pitfall 1: counter is monotonic)
- Step detection threshold = max(2x median_jitter, 2.0ms) for robustness against noise
- 20% conservative move toward target tc per cycle prevents oscillation
- Window size returned as float; int conversion deferred to applier

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed log format string in tune_hampel_sigma**
- **Found during:** Task 1 (REFACTOR review)
- **Issue:** Format string `%.1%%` is invalid Python format specifier
- **Fix:** Changed to `%.1f%%`
- **Files modified:** src/wanctl/tuning/strategies/signal_processing.py
- **Verification:** ruff check passes, no runtime format error
- **Committed in:** ab2930e

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial format string fix. No scope creep.

## Issues Encountered
- Test helper for step response data needed iteration: initial EWMA settling was too slow to settle within MAX_SETTLING_WINDOW=600s. Fixed by adjusting alpha_per_minute in test helper to produce realistic settling within the scan window. Also needed to return RTT to baseline between steps to create proper up-step/down-step pairs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Three strategy functions ready for wiring in Plan 02
- Plan 02 will extend _apply_tuning_to_controller for hampel_sigma_threshold and hampel_window_size
- Plan 02 will add load_time_constant_sec -> alpha conversion in applier
- Plan 02 will implement SIGP-04 layer-based round-robin in maintenance loop

---
*Phase: 101-signal-processing-tuning*
*Completed: 2026-03-19*

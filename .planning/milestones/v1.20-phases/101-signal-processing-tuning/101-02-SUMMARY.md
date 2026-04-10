---
phase: 101-signal-processing-tuning
plan: 02
subsystem: tuning
tags:
  [
    layer-rotation,
    round-robin,
    hampel,
    ewma,
    signal-processing,
    applier,
    deque-resize,
  ]

# Dependency graph
requires:
  - phase: 98-tuning-foundation
    provides: TuningResult, SafetyBounds, TuningConfig, analyzer, applier
  - phase: 99-congestion-threshold-calibration
    provides: calibrate_target_bloat, calibrate_warn_bloat StrategyFn pattern
  - phase: 100-safety-revert-detection
    provides: is_parameter_locked, check_and_revert, PendingObservation
  - phase: 101-01
    provides: tune_hampel_sigma, tune_hampel_window, tune_alpha_load strategies
provides:
  - Layer-based round-robin in maintenance loop (SIGNAL -> EWMA -> THRESHOLD)
  - Extended _apply_tuning_to_controller for signal processing params
  - Extended current_params with 3 new parameters
  - WANController._tuning_layer_index for rotation state
affects: [102-advanced-tuning]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [layer-based-round-robin, tc-to-alpha-conversion, deque-resize-preservation]

key-files:
  created:
    - tests/test_tuning_layer_rotation.py
  modified:
    - src/wanctl/autorate_continuous.py

key-decisions:
  - "Layer rotation uses modular index (wc._tuning_layer_index % 3) for wrap-around"
  - "EWMA layer uses load_time_constant_sec (NOT alpha_load) as parameter name to survive clamp_to_step rounding"
  - "tc-to-alpha conversion (alpha = 0.05 / tc) happens at apply time only, not in strategy"
  - "Deque resize via deque(existing, maxlen=new) preserves most recent elements"
  - "Layer definitions placed inside isinstance(TuningConfig) guard but outside per-WAN loop (define once, use for all WANs)"

patterns-established:
  - "Layer-based round-robin: strategies grouped into layers (SIGNAL, EWMA, THRESHOLD), one layer per tuning cycle via modular index"
  - "Deque resize pattern: deque(existing_deque, maxlen=new_size) preserves rightmost N elements when shrinking"
  - "Domain conversion at apply boundary: parameters tuned in human-readable domain (seconds), converted to internal domain (alpha) only at point of application"

requirements-completed: [SIGP-04]

# Metrics
duration: 7min
completed: 2026-03-19
---

# Phase 101 Plan 02: Layer Rotation Wiring Summary

**Layer-based round-robin (signal->EWMA->threshold) in maintenance loop with extended applier for Hampel sigma, window resize, and tc-to-alpha conversion**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-19T12:01:45Z
- **Completed:** 2026-03-19T12:08:45Z
- **Tasks:** 2 (1 auto + 1 TDD)
- **Files modified:** 2

## Accomplishments

- Extended \_apply_tuning_to_controller with 3 new parameter handlers (hampel_sigma_threshold, hampel_window_size, load_time_constant_sec)
- Implemented layer-based round-robin: cycle 0=signal, cycle 1=EWMA, cycle 2=threshold, then wraps
- Added WANController.\_tuning_layer_index for rotation persistence across tuning cycles
- Extended current_params dict with 3 new signal processing parameters
- Deque resize for window size changes preserves most recent elements (Pitfall 2 fix)
- tc-to-alpha conversion at apply time: alpha = 0.05 / tc (Pitfall 3 fix)
- 17 new tests covering applier, rotation, current_params, and lock filtering

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend applier and WANController init** - `7517c5d` (feat)
2. **Task 2 RED: Failing tests** - `2c8f94b` (test)
3. **Task 2 GREEN: Layer rotation in maintenance loop** - `858ed28` (feat)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Extended \_apply_tuning_to_controller (3 new param handlers), layer definitions (SIGNAL/EWMA/THRESHOLD), round-robin selection, extended current_params, \_tuning_layer_index init
- `tests/test_tuning_layer_rotation.py` - 17 tests: 4 applier signal processing, 4 tc-to-alpha conversion, 3 current_params extension, 6 layer rotation + lock filtering (358 lines)

## Decisions Made

- Layer rotation uses simple modular index (% 3) rather than explicit state machine -- simpler, same behavior
- EWMA layer uses "load_time_constant_sec" as parameter name, NOT "alpha_load", because the tc range (0.5-10s) survives clamp_to_step's round(1) and the trivial change filter (abs < 0.1), while alpha values (0.005-0.1) would be destroyed
- tc-to-alpha conversion happens only in \_apply_tuning_to_controller, never in strategy functions -- clean domain boundary
- Deque resize uses deque(existing, maxlen=new) constructor which preserves rightmost elements when shrinking
- Layer definitions are local variables inside the isinstance(TuningConfig) guard block, defined once per tuning cycle and used for all WANs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 SIGP requirements now satisfied (SIGP-01 through SIGP-04)
- Phase 101 complete: signal processing tuning strategies + layer rotation wiring
- Ready for Phase 102: Advanced Tuning

## Self-Check: PASSED

- All files exist on disk
- All 3 commits verified in git log
- 77 tests pass across tuning test files (0 failures)
- ruff check clean
- Pre-existing mypy errors only (ReflectorScorer section, unrelated)

---

_Phase: 101-signal-processing-tuning_
_Completed: 2026-03-19_

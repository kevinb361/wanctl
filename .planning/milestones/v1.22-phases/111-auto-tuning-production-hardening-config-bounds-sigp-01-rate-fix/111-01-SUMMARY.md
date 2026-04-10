---
phase: 111-auto-tuning-production-hardening-config-bounds-sigp-01-rate-fix
plan: 01
subsystem: tuning
tags: [signal-processing, hampel, outlier-rate, config-bounds, adaptive-tuning]

requires:
  - phase: 098-tuning-foundation
    provides: signal_processing.py strategies (tune_hampel_sigma, tune_hampel_window)
provides:
  - SIGP-01 rate normalization fix (time-gap-aware denominator)
  - MAX_WINDOW=21 constant (unblocks ATT window proposals beyond 15)
  - Widened config bounds for 4 tuning parameters
  - Density-aware test coverage for outlier rate calculation
affects: [tuning, signal-processing, production-config]

tech-stack:
  added: []
  patterns:
    - "time_gap / CYCLE_INTERVAL for recording-density-independent rate normalization"
    - "MAX_WINDOW decoupled from per-WAN config bounds (code constant is ceiling, bounds enforce limits)"

key-files:
  created: []
  modified:
    - src/wanctl/tuning/strategies/signal_processing.py
    - tests/test_signal_processing_strategy.py
    - configs/spectrum.yaml (deployment-only, gitignored)
    - configs/att.yaml (deployment-only, gitignored)

key-decisions:
  - "Compute samples_per_sec from CYCLE_INTERVAL (1.0/0.05=20) rather than adding a new constant"
  - "MAX_WINDOW=21 is code ceiling; per-WAN config bounds enforce actual limits per deployment"
  - "Config files are gitignored -- bound changes applied to deployment configs directly, not tracked in git"

patterns-established:
  - "Rate normalization: expected_samples = time_gap * (1.0 / CYCLE_INTERVAL) handles any recording density"
  - "TestHampelSigmaRecordingDensity: parametrized density testing pattern for metrics strategies"

requirements-completed: [SIGP-01-FIX, BOUNDS-SPECTRUM, BOUNDS-ATT]

duration: 5min
completed: 2026-03-25
---

# Phase 111 Plan 01: Config Bounds + SIGP-01 Rate Fix Summary

**Fixed 60x outlier rate underestimate in SIGP-01 via time-gap-aware normalization, updated MAX_WINDOW to 21, widened 4 config bounds stuck at limits**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-25T15:33:27Z
- **Completed:** 2026-03-25T15:38:44Z
- **Tasks:** 2
- **Files modified:** 4 (2 tracked, 2 deployment-only)

## Accomplishments

- Fixed SIGP-01 outlier rate calculation: replaced `delta / SAMPLES_PER_MINUTE` with `delta / (time_gap * samples_per_sec)` using actual time gaps between consecutive DB records
- Updated MAX_WINDOW constant from 15 to 21, unblocking ATT hampel_window proposals beyond 15
- Widened 4 config bounds: Spectrum target_bloat_ms min 10->5, warn_bloat_ms min 25->15, baseline_rtt_max min 30->25; ATT hampel_window_size max 15->21
- Added 7 new tests: parametrized density tests (1s/5s/60s), converged rate, zero time gap, single sample, MAX_WINDOW alignment
- All 27 tests pass (20 existing + 7 new), ruff clean, mypy clean
- Removed unused SAMPLES_PER_MINUTE constant

## Task Commits

Each task was committed atomically:

1. **Task 1: Widen tuning bounds in Spectrum and ATT configs** - deployment-only (configs are gitignored, changes applied to `/home/kevin/projects/wanctl/configs/`)
2. **Task 2 (TDD RED): Failing tests** - `e583938` (test)
3. **Task 2 (TDD GREEN): Fix SIGP-01 + MAX_WINDOW + test updates** - `3be6059` (feat)

## Files Created/Modified

- `src/wanctl/tuning/strategies/signal_processing.py` - Fixed SIGP-01 rate normalization, removed SAMPLES_PER_MINUTE, updated MAX_WINDOW=21
- `tests/test_signal_processing_strategy.py` - Added TestHampelSigmaRecordingDensity and TestMaxWindowAlignment classes, updated stale MAX_WINDOW=15 comments
- `configs/spectrum.yaml` - Widened 3 tuning bounds (deployment-only, gitignored)
- `configs/att.yaml` - Widened hampel_window_size max to 21 (deployment-only, gitignored)

## Decisions Made

- Computed `samples_per_sec = 1.0 / CYCLE_INTERVAL` rather than adding a new constant -- derived from existing source of truth
- MAX_WINDOW=21 as code ceiling; per-WAN config bounds enforce actual limits (Spectrum still capped at 15 by its bounds)
- Config YAML files are gitignored (deployment-specific) -- changes applied directly to main repo configs for deployment
- Kept pre-existing ruff warnings (F401 on TuningResult and MIN_SAMPLES imports) as out-of-scope per deviation rules

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_moderate_jitter_interpolates bounds for MAX_WINDOW=21**

- **Found during:** Task 2 (TDD GREEN)
- **Issue:** Existing test hardcoded interpolation expectations based on MAX_WINDOW=15; with MAX_WINDOW=21 the interpolation formula gives 15.0 not 11.25
- **Fix:** Updated expected range from `10.0-12.0` to `14.0-16.0` and comment from `15 - 10 * ...` to `21 - 16 * ...`
- **Files modified:** tests/test_signal_processing_strategy.py
- **Verification:** Test passes with correct interpolation math
- **Committed in:** 3be6059

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary adjustment to existing test expectations after MAX_WINDOW change. No scope creep.

## Issues Encountered

- Config files (spectrum.yaml, att.yaml) are gitignored -- cannot be committed to git. Changes applied directly to deployment configs in the main repo directory.

## Known Stubs

None -- all changes are fully wired and functional.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SIGP-01 rate normalization is correct for any recording density
- ATT tuner can now propose window sizes up to 21
- Spectrum tuner can now explore lower bounds for target_bloat_ms, warn_bloat_ms, and baseline_rtt_max
- Config changes require deployment to production containers (cake-spectrum, cake-att) to take effect

## Self-Check: PASSED

- All files exist: signal_processing.py, test_signal_processing_strategy.py, 111-01-SUMMARY.md
- All commits verified: e583938 (TDD RED), 3be6059 (TDD GREEN)

---

_Phase: 111-auto-tuning-production-hardening-config-bounds-sigp-01-rate-fix_
_Completed: 2026-03-25_

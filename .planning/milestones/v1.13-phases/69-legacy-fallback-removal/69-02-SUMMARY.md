---
phase: 69-legacy-fallback-removal
plan: 02
subsystem: config
tags: [deprecation, config-validation, calibrate, steering, legacy-cleanup]

# Dependency graph
requires:
  - phase: 69-legacy-fallback-removal plan 01
    provides: deprecate_param helper and 5 legacy param wiring
provides:
  - Cleaned validate_sample_counts (2-param, 2-tuple return)
  - calibrate.py generates baseline_time_constant_sec and load_time_constant_sec
  - cake_aware deprecation warning in steering daemon
  - CONFIG_SCHEMA.md deprecated parameters table
affects: [70-confidence-graduation]

# Tech tracking
tech-stack:
  added: []
  patterns: [local-constant-avoids-coupling, warn-and-ignore-deprecated-key]

key-files:
  created: []
  modified:
    - src/wanctl/config_validation_utils.py
    - src/wanctl/calibrate.py
    - src/wanctl/steering/daemon.py
    - tests/test_config_validation_utils.py
    - tests/test_calibrate.py
    - tests/test_steering_daemon.py
    - docs/CONFIG_SCHEMA.md
    - CHANGELOG.md

key-decisions:
  - "_CYCLE_INTERVAL_SEC local constant in calibrate.py avoids import coupling to autorate_continuous"
  - "cake_aware warning placed in _load_operational_mode (where mode dict is accessed)"

patterns-established:
  - "Local constant pattern: tools that need daemon interval define their own copy to avoid runtime coupling"

requirements-completed: [LGCY-04, LGCY-07]

# Metrics
duration: 20min
completed: 2026-03-11
---

# Phase 69 Plan 02: Legacy Param Cleanup Summary

**Cleaned validate_sample_counts to 2-param/2-tuple API, calibrate.py generates modern time constant names, cake_aware retired with deprecation warning**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-11T12:26:02Z
- **Completed:** 2026-03-11T12:46:20Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Removed bad_samples/good_samples from validate_sample_counts, now returns (red_samples_required, green_samples_required) 2-tuple
- calibrate.py generates baseline_time_constant_sec and load_time_constant_sec using local \_CYCLE_INTERVAL_SEC constant (no autorate_continuous coupling)
- cake_aware key in steering config produces deprecation warning and is ignored
- CONFIG_SCHEMA.md updated with modern param names and comprehensive deprecated parameters table (all 8 legacy params)
- CHANGELOG.md updated with Phase 69 entries
- 2,277 tests passing, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Failing tests** - `e1e49cb` (test)
2. **Task 1 (TDD GREEN): Implementation** - `7107ca2` (feat)
3. **Task 2: Documentation updates** - `02888e0` (docs)

_Task 1 followed TDD: RED (failing tests) -> GREEN (implementation passes)_

## Files Created/Modified

- `src/wanctl/config_validation_utils.py` - Removed bad_samples/good_samples, 2-tuple return
- `src/wanctl/calibrate.py` - Added \_CYCLE_INTERVAL_SEC, generates modern time constant keys
- `src/wanctl/steering/daemon.py` - cake_aware deprecation warning in \_load_operational_mode
- `tests/test_config_validation_utils.py` - Updated for 2-param/2-tuple signature
- `tests/test_calibrate.py` - Tests for modern time constant keys in generated config
- `tests/test_steering_daemon.py` - Tests for cake_aware deprecation warning
- `docs/CONFIG_SCHEMA.md` - Modern params in tables/examples, deprecated params section
- `CHANGELOG.md` - Phase 69 legacy deprecation entries

## Decisions Made

- Used \_CYCLE_INTERVAL_SEC = 0.05 as a local constant in calibrate.py to avoid importing CYCLE_INTERVAL_SECONDS from autorate_continuous (prevents coupling calibration tool to daemon runtime)
- Placed cake_aware deprecation warning in \_load_operational_mode() since that's where the mode dict is already accessed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 69 complete (all legacy fallback removal done)
- LGCY-03 (Plan 01), LGCY-04, LGCY-07 (Plan 02) all satisfied
- Ready for Phase 70 (confidence graduation) or Phase 71/72

---

_Phase: 69-legacy-fallback-removal_
_Completed: 2026-03-11_

## Self-Check: PASSED

- All 8 modified files verified on disk
- All 3 task commits verified in git history (e1e49cb, 7107ca2, 02888e0)
- 2,277 tests passing, zero regressions

---
phase: 118-metrics-retention-strategy
plan: 01
subsystem: config
tags: [retention, downsampling, config-validation, storage, prometheus]

# Dependency graph
requires:
  - phase: 117-pyroute2-netlink-backend
    provides: stable netlink backend for CAKE stats (no config changes)
provides:
  - Extended STORAGE_SCHEMA with per-granularity retention thresholds
  - get_storage_config() returning retention config dict with deprecation support
  - validate_retention_tuner_compat() cross-section validation function
  - get_downsample_thresholds() factory for config-driven thresholds
  - downsample_metrics() thresholds parameter for runtime config injection
affects:
  [118-02 daemon wiring, autorate_continuous, steering daemon, SIGUSR1 reload]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [lazy-import for circular dependency, config-driven threshold factory]

key-files:
  created: []
  modified:
    - src/wanctl/config_base.py
    - src/wanctl/config_validation_utils.py
    - src/wanctl/storage/downsampler.py
    - tests/test_config_base.py
    - tests/test_config_validation_utils.py
    - tests/test_storage_downsampler.py

key-decisions:
  - "Lazy import of deprecate_param in config_base.py to break circular dependency with config_validation_utils"
  - "Unified thresholds: each tier's age_seconds controls both downsampling trigger and source data deletion"
  - "prometheus_compensated is boolean modifier that changes defaults and relaxes validation (not curated preset)"
  - "DOWNSAMPLE_THRESHOLDS = get_downsample_thresholds() preserves backward compat for all existing importers"

patterns-established:
  - "Config-driven threshold factory: get_downsample_thresholds() returns same dict structure with configurable ages"
  - "Cross-section validation: validate_retention_tuner_compat() checks storage.retention vs tuning.lookback_hours"
  - "Prometheus-compensated mode: boolean modifier relaxes validation to warning instead of error"

requirements-completed: [RETN-01, RETN-02, RETN-03]

# Metrics
duration: 6min
completed: 2026-03-27
---

# Phase 118 Plan 01: Config Schema and Validation for Metrics Retention Summary

**Per-granularity retention thresholds in YAML config with cross-section tuner validation and prometheus_compensated mode**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-27T16:07:45Z
- **Completed:** 2026-03-27T16:13:46Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Extended STORAGE_SCHEMA with 4 new retention fields (raw_age_seconds, aggregate_1m_age_seconds, aggregate_5m_age_seconds, prometheus_compensated)
- Rewrote get_storage_config() to return per-granularity retention config with deprecate_param() backward compat for retention_days
- Added validate_retention_tuner_compat() cross-section validation protecting tuner data availability
- Replaced hardcoded DOWNSAMPLE_THRESHOLDS with config-driven get_downsample_thresholds() factory
- Added thresholds parameter to downsample_metrics() for runtime config injection
- 21 new tests across 3 test files, all passing (239 total across modified files)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend config schema and get_storage_config()** - `cef5b07` (test) + `684751f` (feat)
2. **Task 2: Cross-section validation and config-driven thresholds** - `f4188df` (test) + `fd71dbe` (feat)

_TDD: Each task has RED (test) and GREEN (feat) commits._

## Files Created/Modified

- `src/wanctl/config_base.py` - Extended STORAGE_SCHEMA, rewrote get_storage_config() with retention section
- `src/wanctl/config_validation_utils.py` - Added validate_retention_tuner_compat() function
- `src/wanctl/storage/downsampler.py` - Added get_downsample_thresholds() factory, thresholds param on downsample_metrics()
- `tests/test_config_base.py` - Added TestGetStorageConfigRetention (10 tests)
- `tests/test_config_validation_utils.py` - Added TestValidateRetentionTunerCompat (6 tests)
- `tests/test_storage_downsampler.py` - Added TestGetDownsampleThresholds (3 tests) and TestDownsampleMetricsWithThresholds (2 tests)

## Decisions Made

- Used lazy import for deprecate_param inside get_storage_config() to break circular dependency (config_base -> config_validation_utils -> config_base)
- Unified thresholds: age_seconds controls both when data is downsampled and when source data is deleted (no separate knobs)
- prometheus_compensated is a boolean modifier that changes 5m default to 48h and relaxes validation from error to warning
- DOWNSAMPLE_THRESHOLDS = get_downsample_thresholds() keeps backward compat for all existing importers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Broke circular import between config_base and config_validation_utils**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** Adding `from wanctl.config_validation_utils import deprecate_param` to config_base.py created circular import (config_validation_utils imports ConfigValidationError from config_base)
- **Fix:** Used lazy import inside get_storage_config() function body instead of module-level import
- **Files modified:** src/wanctl/config_base.py
- **Verification:** All tests pass, mypy clean
- **Committed in:** 684751f (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary fix for correct imports. No scope creep.

## Issues Encountered

None beyond the circular import handled as a deviation.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all config values are fully wired to functional code paths.

## Next Phase Readiness

- Config infrastructure complete for Plan 02 to wire into daemons
- get_storage_config() returns retention dict ready for daemon consumption
- validate_retention_tuner_compat() ready to be called at startup and SIGUSR1 reload
- get_downsample_thresholds() ready to receive config values from daemon integration
- downsample_metrics(thresholds=...) ready for config-driven invocation

## Self-Check: PASSED

All 6 files verified present. All 4 commit hashes verified in git log.

---

_Phase: 118-metrics-retention-strategy_
_Completed: 2026-03-27_

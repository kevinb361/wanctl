---
phase: 118-metrics-retention-strategy
plan: 02
subsystem: storage
tags:
  [retention, daemon-wiring, SIGUSR1, config-driven, maintenance, downsampling]

# Dependency graph
requires:
  - phase: 118-metrics-retention-strategy
    plan: 01
    provides: get_storage_config() with retention dict, validate_retention_tuner_compat(), get_downsample_thresholds()
provides:
  - Config-driven per-granularity cleanup in both daemons (autorate + steering)
  - SIGUSR1 retention config reload with validation (error keeps old config)
  - Cross-section validation at daemon startup blocking dangerous configs
  - Config-driven downsample thresholds in periodic maintenance
  - Example configs documenting storage.retention section
affects:
  [production deployment, operator config changes, runtime retention tuning]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      config-driven retention wiring through daemon lifecycle,
      SIGUSR1 reload with validation guard,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/storage/retention.py
    - src/wanctl/storage/maintenance.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - configs/examples/spectrum-vm.yaml.example
    - configs/examples/att-vm.yaml.example
    - tests/test_storage_retention.py
    - tests/test_storage_maintenance.py

key-decisions:
  - "MagicMock guard on retention_config in _init_storage() using isinstance(dict) check for test safety"
  - "SIGUSR1 retention reload catches ConfigValidationError and keeps old config (logs error, does not raise)"
  - "Steering daemon passes config.data.get('tuning') to validation even though steering may not have tuning section (None handled gracefully)"
  - "1h tier uses aggregate_5m_age_seconds as its cutoff (final tier shares longest retention)"

patterns-established:
  - "Config-driven retention: storage_config.get('retention') flows from YAML through get_storage_config() into cleanup and downsampler"
  - "SIGUSR1 retention reload: validate before apply, error preserves previous config"
  - "Cross-section validation at startup: raises ConfigValidationError to block dangerous configs"

requirements-completed: [RETN-01, RETN-02, RETN-03]

# Metrics
duration: 17min
completed: 2026-03-27
---

# Phase 118 Plan 02: Daemon Wiring for Config-Driven Retention Summary

**Per-granularity retention wired into both daemons with SIGUSR1 reload, cross-section validation at startup, and config-driven downsample thresholds**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-27T16:49:15Z
- **Completed:** 2026-03-27T17:06:17Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Per-granularity cleanup_old_metrics() deletes raw/1m/5m/1h data using tier-specific age thresholds from retention config
- run_startup_maintenance() passes retention_config to both cleanup and downsample_metrics with custom thresholds
- Both daemons (autorate + steering) use config-driven retention at startup and periodic maintenance
- SIGUSR1 reloads retention config with validate_retention_tuner_compat guard (error keeps old config)
- Cross-section validation fires at startup in both daemons, blocking dangerous retention/tuner combos
- Example configs document new storage.retention section with comments for operators
- 8 new per-granularity tests + 4 new maintenance retention_config tests, 292 relevant tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Update retention cleanup and maintenance to accept config-driven thresholds** - `12366b6` (test) + `342af32` (feat) [TDD RED + GREEN]
2. **Task 2: Wire retention config into both daemons with SIGUSR1 reload** - `18a6b2f` (feat)

_TDD: Task 1 has RED (test) and GREEN (feat) commits._

## Files Created/Modified

- `src/wanctl/storage/retention.py` - Per-granularity cleanup via retention_config dict with tier-specific cutoffs
- `src/wanctl/storage/maintenance.py` - Config-driven startup maintenance with retention_config and custom downsample thresholds
- `src/wanctl/autorate_continuous.py` - maintenance_retention_config replaces retention_days, SIGUSR1 reload, periodic maintenance with custom thresholds
- `src/wanctl/steering/daemon.py` - retention_config extraction, cross-section validation, config-driven startup maintenance
- `configs/examples/spectrum-vm.yaml.example` - New storage.retention section with raw/1m/5m age and prometheus_compensated
- `configs/examples/att-vm.yaml.example` - Same storage.retention section structure
- `tests/test_storage_retention.py` - TestCleanupPerGranularity class with 8 per-granularity cleanup tests
- `tests/test_storage_maintenance.py` - TestStartupMaintenanceRetentionConfig class with 4 retention_config pass-through tests

## Decisions Made

- Used isinstance(dict) guard on retention_config in \_init_storage() to protect against MagicMock in tests
- SIGUSR1 retention reload catches ConfigValidationError specifically (not broad Exception) to keep old config on validation failure
- Steering daemon passes config.data.get("tuning") which returns None when no tuning section; validate_retention_tuner_compat handles None gracefully by skipping the check
- 1h granularity tier uses aggregate_5m_age_seconds as its cutoff since it is the final aggregation tier

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing flaky test: test_boundary_data_at_exactly_retention_days fails intermittently due to time.time() advancing between insert and cutoff calculation (timing-sensitive boundary condition). Out of scope.
- Pre-existing test failures in test_container_network_audit.py (missing module), test_dashboard/ (missing httpx), test_deployment_contracts.py (requests version mismatch), and test_netlink_cake_backend.py (ruff B905 strict=). All out of scope.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all config values are fully wired to functional code paths.

## Next Phase Readiness

- Retention config is fully wired end-to-end from YAML through both daemons
- Operators can now configure per-granularity retention via YAML and reload via SIGUSR1
- Phase 118 is complete: config schema (Plan 01) + daemon wiring (Plan 02)

## Self-Check: PASSED

All 8 files verified present. All 3 commit hashes verified in git log.

---

_Phase: 118-metrics-retention-strategy_
_Completed: 2026-03-27_

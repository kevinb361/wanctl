---
phase: 42-maintenance-scheduling
plan: 01
subsystem: storage
tags: [sqlite, retention, downsampling, startup, maintenance]

# Dependency graph
requires:
  - phase: 38-time-series-storage
    provides: cleanup_old_metrics(), downsample_metrics(), vacuum_if_needed()
  - phase: 39-data-recording
    provides: record_config_snapshot() startup pattern
provides:
  - run_startup_maintenance() helper function
  - Automatic DB maintenance at daemon startup
  - Bounded database growth
  - Downsampled data for long-range queries
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Startup maintenance wrapper pattern (cleanup + vacuum + downsample)
    - Error isolation in maintenance (log but don't block startup)

key-files:
  created:
    - src/wanctl/storage/maintenance.py
    - tests/test_storage_maintenance.py
  modified:
    - src/wanctl/storage/__init__.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py

key-decisions:
  - "Maintenance errors logged but don't block daemon startup"
  - "Summary log only when work is done (not on every startup)"
  - "Use existing retention_days from storage config with 7-day default"

patterns-established:
  - "run_startup_maintenance(conn, retention_days, log) - single entry point for all maintenance"
  - "Return dict with results + error field for graceful error handling"

# Metrics
duration: 4min
completed: 2026-01-25
---

# Phase 42 Plan 01: Maintenance Scheduling Summary

**Startup maintenance wires cleanup_old_metrics() and downsample_metrics() to both daemons, closing tech debt gap**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-26T01:58:02Z
- **Completed:** 2026-01-26T02:01:49Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Created run_startup_maintenance() helper that calls cleanup + vacuum + downsample in sequence
- Wired maintenance to autorate daemon startup (after record_config_snapshot)
- Wired maintenance to steering daemon startup (after record_config_snapshot)
- 12 new tests for maintenance functionality

## Task Commits

Each task was committed atomically:

1. **Task 1: Create maintenance helper module** - `1a9655a` (feat)
2. **Task 2: Wire maintenance to autorate daemon startup** - `203ba0f` (feat)
3. **Task 3: Wire maintenance to steering daemon startup and add tests** - `0e4c7eb` (feat)

## Files Created/Modified
- `src/wanctl/storage/maintenance.py` - New module with run_startup_maintenance()
- `src/wanctl/storage/__init__.py` - Export run_startup_maintenance
- `src/wanctl/autorate_continuous.py` - Call maintenance in main()
- `src/wanctl/steering/daemon.py` - Call maintenance in main()
- `tests/test_storage_maintenance.py` - 12 tests covering maintenance

## Decisions Made
- Maintenance errors are logged but do not block daemon startup (daemon stability priority)
- Summary log only appears when work is done (avoids noise on every startup)
- Uses existing retention_days from storage config with 7-day default fallback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tech debt closed: cleanup_old_metrics() and downsample_metrics() now called at startup
- Database will stay bounded (old data deleted)
- Downsampled data available for long-range queries (1m, 5m, 1h granularity)
- Phase 42 complete - gap closure milestone finished

---
*Phase: 42-maintenance-scheduling*
*Completed: 2026-01-25*

---
phase: 76-alert-engine
plan: 01
subsystem: infra
tags: [sqlite, alerting, cooldown, persistence]

# Dependency graph
requires:
  - phase: none
    provides: "Existing MetricsWriter singleton and storage/schema.py"
provides:
  - "AlertEngine class with fire(), cooldown suppression, SQLite persistence"
  - "ALERTS_SCHEMA constant and updated create_tables()"
affects:
  [
    76-02-alert-config,
    77-congestion-detection,
    78-delivery-layer,
    80-health-history,
  ]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "per-event (type, wan) cooldown suppression via time.monotonic()",
      "graceful persistence errors (log warning, never crash)",
    ]

key-files:
  created:
    - src/wanctl/alert_engine.py
    - tests/test_alert_engine.py
  modified:
    - src/wanctl/storage/schema.py

key-decisions:
  - "Cooldown key is (alert_type, wan_name) tuple -- per-type per-WAN independent suppression"
  - "Persistence errors logged as warnings, never crash the daemon"
  - "AlertEngine accepts writer=None for no-persistence mode (useful for testing and degraded operation)"
  - "get_active_cooldowns() method for health endpoint and debugging visibility"

patterns-established:
  - "AlertEngine(enabled, default_cooldown_sec, rules, writer) constructor pattern"
  - "fire() returns bool indicating whether alert was emitted or suppressed"
  - "Per-rule cooldown_sec overrides default_cooldown_sec via rules dict"

requirements-completed: [INFRA-01, INFRA-03]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 76 Plan 01: Alert Engine Core Summary

**AlertEngine with (type, wan) cooldown suppression using time.monotonic() and SQLite alerts table persistence via MetricsWriter**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T11:07:46Z
- **Completed:** 2026-03-12T11:10:21Z
- **Tasks:** 1 (TDD: RED -> GREEN)
- **Files modified:** 3

## Accomplishments

- AlertEngine class with fire(), \_is_cooled_down(), \_persist_alert(), get_active_cooldowns()
- ALERTS_SCHEMA with alerts table and two indexes (timestamp, type+wan+timestamp)
- create_tables() now creates both metrics and alerts tables
- 21 new tests covering fire/suppress/persist, cooldown expiry, per-rule overrides, enabled gates, no-writer mode, persistence errors, schema validation

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `02018c7` (test)
2. **Task 1 (GREEN): AlertEngine implementation** - `d4d2c55` (feat)

_TDD task with RED (failing tests) and GREEN (implementation) commits._

## Files Created/Modified

- `src/wanctl/alert_engine.py` - AlertEngine class with fire(), cooldown, persistence (172 lines)
- `src/wanctl/storage/schema.py` - Added ALERTS_SCHEMA constant and updated create_tables()
- `tests/test_alert_engine.py` - 21 tests across 7 test classes (348 lines)

## Decisions Made

- Cooldown key is (alert_type, wan_name) tuple for per-type per-WAN independent suppression
- Persistence errors logged as warnings, never crash the daemon (follows handle_errors philosophy)
- AlertEngine accepts writer=None for no-persistence mode
- get_active_cooldowns() returns remaining seconds dict for health endpoint use

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AlertEngine ready for config wiring (Plan 02: YAML config loading)
- Both daemons can instantiate AlertEngine after config support is added
- alerts table will be created automatically when MetricsWriter initializes

## Self-Check: PASSED

All files exist, all commits verified.

---

_Phase: 76-alert-engine_
_Completed: 2026-03-12_

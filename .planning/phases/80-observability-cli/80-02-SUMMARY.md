---
phase: 80-observability-cli
plan: 02
subsystem: infra
tags: [sqlite, cli, alerts, argparse, tabulate]

# Dependency graph
requires:
  - phase: 78-alert-persistence
    provides: alerts table schema and persistence in SQLite
provides:
  - query_alerts() function in reader.py for reuse by API/CLI
  - --alerts flag on wanctl-history CLI for operator alert inspection
affects: [api-endpoints, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      query_alerts follows query_metrics read-only connection pattern,
      alert formatting with details truncation,
    ]

key-files:
  created: [tests/test_alert_history.py]
  modified: [src/wanctl/storage/reader.py, src/wanctl/history.py]

key-decisions:
  - "query_alerts() follows identical pattern to query_metrics() for consistency"
  - "Details JSON parsed into dict with fallback to raw string on error"
  - "Alert table truncates details to 60 chars; JSON output includes full details plus ISO timestamp"

patterns-established:
  - "Alert query pattern: read-only connection, WHERE clause builder, JSON details parsing"
  - "format_alerts_table/format_alerts_json dual output following format_table/format_json precedent"

requirements-completed: [INFRA-04]

# Metrics
duration: 6min
completed: 2026-03-12
---

# Phase 80 Plan 02: Alert History CLI Summary

**query_alerts() reader function and --alerts CLI flag for wanctl-history with time range, type, and WAN filtering**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-12T16:48:07Z
- **Completed:** 2026-03-12T16:54:42Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- query_alerts() function with start_ts/end_ts/alert_type/wan filtering and JSON details parsing
- --alerts flag on wanctl-history CLI with table and JSON output modes
- format_alerts_table() with Timestamp/Type/Severity/WAN/Details columns (60-char truncation)
- format_alerts_json() with ISO timestamp enrichment for readability
- 13 new tests covering query function and CLI behavior, 0 regressions in 47 existing history tests

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for alert history** - `c498234` (test)
2. **Task 1 (GREEN): query_alerts() and --alerts implementation** - `894475b` (feat)

_Note: RED commit was from prior agent session (80-01 scope overlap); content verified identical._

## Files Created/Modified

- `src/wanctl/storage/reader.py` - Added query_alerts() function following query_metrics() pattern
- `src/wanctl/history.py` - Added --alerts flag, format_alerts_table(), format_alerts_json()
- `tests/test_alert_history.py` - 13 tests for query_alerts() and --alerts CLI behavior

## Decisions Made

- query_alerts() follows identical read-only connection pattern as query_metrics() for consistency
- Details column parsed from JSON to dict with graceful fallback (keeps raw string on parse error)
- Alert table format truncates details to 60 chars for terminal readability
- JSON output enriches records with timestamp_iso field for human readability
- --alerts bypasses granularity selection and metrics-specific DB existence check (alerts table may exist independently)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lint and format fixes**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** Unused timedelta import and unsorted import block in test file, formatting in history.py
- **Fix:** ruff check --fix and ruff format applied
- **Files modified:** tests/test_alert_history.py, src/wanctl/history.py
- **Verification:** ruff check and ruff format clean
- **Committed in:** 894475b (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor lint/format fix, no scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Alert history queryable via CLI for operator use
- query_alerts() available for future API endpoint integration
- All existing wanctl-history functionality preserved

## Self-Check: PASSED

- All 3 source/test files exist on disk
- Both commits (c498234, 894475b) verified in git log
- query_alerts() function present in reader.py
- --alerts flag present in history.py
- 13/13 tests passing, 0 regressions

---

_Phase: 80-observability-cli_
_Completed: 2026-03-12_

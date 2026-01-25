---
phase: 40-cli-tool
plan: 02
subsystem: cli
tags: [argparse, tabulate, sqlite, metrics, time-series]

# Dependency graph
requires:
  - phase: 40-01
    provides: MetricsReader module with query_metrics, compute_summary, select_granularity
provides:
  - wanctl-history CLI command for querying metrics database
  - Duration parsing (1h, 30m, 7d format)
  - Table, JSON, and summary output modes
  - Time range filtering (--last, --from/--to)
  - Metric and WAN filtering
affects: [41-cleanup, production-observability]

# Tech tracking
tech-stack:
  added: []
  patterns: [argparse CLI pattern, adaptive value formatting]

key-files:
  created:
    - src/wanctl/history.py
    - tests/test_history_cli.py
  modified:
    - pyproject.toml

key-decisions:
  - "Default time range is --last 1h when no time args provided"
  - "State metrics show percentage distribution instead of numeric stats"
  - "Exit 0 on empty results with informational message"

patterns-established:
  - "Duration parsing: regex + timedelta with units dict"
  - "Adaptive value formatting: remove trailing zeros"

# Metrics
duration: 8min
completed: 2026-01-25
---

# Phase 40 Plan 02: CLI Tool Summary

**wanctl-history CLI with duration parsing, table/JSON/summary output, and 47 integration tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-25T22:50:18Z
- **Completed:** 2026-01-25T22:58:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created wanctl-history CLI tool for querying metrics database
- Duration parsing supports s/m/h/d/w units (e.g., "1h", "30m", "7d")
- Three output modes: table (default), JSON, summary statistics
- State metrics show percentage distribution (GREEN: 85%, YELLOW: 10%, etc.)
- 47 comprehensive tests covering all CLI functionality

## Task Commits

Each task was committed atomically:

1. **Task 1: Create history.py CLI module** - `0520645` (feat)
2. **Task 2: Register entry point and install** - `4aafa3c` (chore)
3. **Task 3: Add CLI integration tests** - `65eb63b` (test)

## Files Created/Modified

- `src/wanctl/history.py` - CLI entry point with argument parsing and output formatting (318 lines)
- `pyproject.toml` - Added wanctl-history entry point
- `tests/test_history_cli.py` - CLI integration tests (584 lines)

## Decisions Made

- **Default time range:** --last 1h when no args (common use case)
- **State metrics:** Show percentage distribution instead of numeric stats (more useful for state enums)
- **Empty results:** Exit 0 with message (not an error condition)
- **Timestamp format:** Local time "YYYY-MM-DD HH:MM:SS" (user-friendly)
- **Value formatting:** Adaptive precision removes trailing zeros (25.5 not 25.500000)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed MetricsWriter API in test fixture**

- **Found during:** Task 3 (CLI integration tests)
- **Issue:** Test fixture used `record_metric` method which doesn't exist; correct method is `write_metric`
- **Fix:** Changed fixture to use `write_metric` with correct parameter order (timestamp, wan_name, metric_name, value)
- **Files modified:** tests/test_history_cli.py
- **Verification:** All 47 tests pass
- **Committed in:** 65eb63b (Task 3 commit)

**2. [Rule 3 - Blocking] Added singleton reset in test fixture**

- **Found during:** Task 3 (CLI integration tests)
- **Issue:** MetricsWriter singleton retained previous test's db path; new path wasn't used
- **Fix:** Called `MetricsWriter._reset_instance()` before and after each test to ensure clean state
- **Files modified:** tests/test_history_cli.py
- **Verification:** All 47 tests pass with isolated databases
- **Committed in:** 65eb63b (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were necessary for test isolation. No scope creep.

## Issues Encountered

None - plan executed smoothly after test fixture corrections.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- wanctl-history command available after `pip install -e .`
- CLI-01 through CLI-05 requirements fulfilled
- Ready for Phase 41 cleanup

---
*Phase: 40-cli-tool*
*Completed: 2026-01-25*

---
phase: 87-benchmark-storage-comparison
plan: 02
subsystem: benchmark-cli
tags: [benchmark, compare, history, cli, argparse, tabulate]

requires:
  - phase: 87-01
    provides: store_benchmark(), query_benchmarks(), subparser skeleton, _colorize()
provides:
  - compute_deltas() for numeric field comparison
  - format_comparison() with grade delta, latency/throughput tables, metadata
  - run_compare() with default latest-vs-previous and specific-ID modes
  - format_history() with tabulated table display
  - run_history() with --last/--from/--to/--wan filters
  - --json output for both compare and history subcommands
affects: []

tech-stack:
  added: []
  patterns:
    [
      grade-arrow display with color direction,
      delta coloring inversion for latency vs throughput,
      ISO timestamp truncation for display,
      comparability warnings to stderr,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/benchmark.py
    - tests/test_benchmark.py

key-decisions:
  - "Negative latency delta = green (improved), positive = red (worse); inverted for throughput"
  - "Grade improvement/degradation detected via grade_order index comparison"
  - "Comparability warnings go to stderr (don't block comparison)"
  - "format_history uses tabulate library (already a project dependency)"
  - "History --wan uses hist_wan dest to avoid shadowing global --wan flag"
  - "run_compare with 0 IDs fetches latest 2; with 2 IDs fetches those specific runs"

patterns-established:
  - "Delta color inversion pattern: latency negative=good, throughput positive=good"
  - "Comparability warning pattern: stderr warning + continue (not blocking)"
  - "Timestamp display truncation: fromisoformat -> strftime('%Y-%m-%d %H:%M')"

requirements-completed: [STOR-02, STOR-03]

duration: 10min
completed: 2026-03-15
---

# Phase 87 Plan 02: Compare & History Subcommands Summary

**Compare subcommand with grade delta and color-coded metrics, history subcommand with tabulated display and time-range filtering**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-15T18:43:30Z
- **Completed:** 2026-03-15T18:53:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- compute_deltas() computes after-before for 11 numeric fields (latency, throughput, baseline)
- format_comparison() shows grade arrow ("C -> A+"), latency/throughput tables with colored deltas, and metadata
- run_compare() defaults to latest-vs-previous, supports specific IDs, warns on non-comparable runs
- format_history() produces tabulated table with ID, Timestamp, WAN, Grade, Avg Latency, DL Mbps, Label
- run_history() supports --last (timedelta), --from/--to (timestamp), --wan filters
- Both subcommands support --json structured output
- 26 new tests, all 137 benchmark tests pass (backward compatible)
- main() routes compare/history to real handlers (replaces Plan 01 stubs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Compare subcommand with grade delta and color-coded metrics** (TDD)
   - `c94b6d0` (test: failing tests for compute_deltas, format_comparison, run_compare)
   - `ecf9af2` (feat: implementation of compare + history handlers)
2. **Task 2: History subcommand with time-range filtering and table display** (TDD)
   - `84baa44` (test: history format and run tests)

## Files Created/Modified

- `src/wanctl/benchmark.py` - Added compute_deltas(), format_comparison(), run_compare(), format_history(), run_history(); replaced subcommand stubs; added tabulate import
- `tests/test_benchmark.py` - Added TestComputeDeltas (3), TestFormatComparison (6), TestRunCompare (7), TestFormatHistory (5), TestRunHistory (5) = 26 new tests

## Decisions Made

- Negative latency delta colored green (improvement), positive red (worse); inverted for throughput
- Grade improvement/degradation detected via ordered index comparison (F < D < C < B < A < A+)
- Comparability warnings (different server/duration) go to stderr but do not block comparison
- format_history uses tabulate library (already a dependency from wanctl-history)
- History subparser --wan uses dest="hist_wan" to avoid shadowing global --wan flag
- run_compare with 0 IDs fetches latest 2 (limit=2); with 2 IDs fetches those specific runs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- This is the final plan in Phase 87 and the final phase of v1.17
- All STOR requirements complete: STOR-01 (storage), STOR-02 (compare), STOR-03 (history), STOR-04 (auto-store)
- All v1.17 milestone requirements complete across phases 84-87

## Self-Check: PASSED

All 2 source/test files verified present. All 3 task commits verified in git log. All 5 new functions verified in source.

---

_Phase: 87-benchmark-storage-comparison_
_Completed: 2026-03-15_

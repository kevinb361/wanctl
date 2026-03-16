---
phase: 87-benchmark-storage-comparison
plan: 01
subsystem: storage
tags: [sqlite, benchmark, storage, query, cli, argparse]

requires:
  - phase: 86-bufferbloat-benchmarking
    provides: BenchmarkResult dataclass, wanctl-benchmark CLI, run_benchmark()
provides:
  - BENCHMARKS_SCHEMA with 19-column benchmarks table and 2 indexes
  - store_benchmark() writer function for benchmark persistence
  - query_benchmarks() read-only query with wan/time/id/limit filters
  - detect_wan_name() auto-detect from container hostname
  - argparse subparser skeleton (compare/history stubs) for Plan 02
  - --wan/--label/--db CLI flags for storage control
  - auto-store wiring in main() after successful benchmark run
affects: [87-02-benchmark-storage-comparison]

tech-stack:
  added: []
  patterns:
    [
      benchmark storage flat table,
      ISO 8601 TEXT timestamp comparison,
      auto-store-then-display,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/storage/schema.py
    - src/wanctl/storage/reader.py
    - src/wanctl/storage/__init__.py
    - src/wanctl/benchmark.py
    - tests/test_storage_schema.py
    - tests/test_benchmark.py

key-decisions:
  - "Flat table with all BenchmarkResult fields as columns (no JSON blob) for direct SQL filtering"
  - "ISO 8601 TEXT timestamp in benchmarks (not INTEGER epoch) for human readability and lexicographic ordering"
  - "Auto-store before output display so result is persisted even if display fails"
  - "detect_wan_name() uses socket.gethostname() with cake- prefix convention"
  - "Subparser stubs return 0 with stderr message (Plan 02 replaces)"

patterns-established:
  - "Benchmark storage uses flat table pattern (no JSON serialization for queryable fields)"
  - "query_benchmarks() follows exact query_alerts() pattern (read-only conn, WHERE 1=1, ORDER DESC)"
  - "store_benchmark() calls create_tables() before insert (idempotent schema migration)"
  - "Auto-store prints to stderr so stdout remains clean for --json piping"

requirements-completed: [STOR-01, STOR-04]

duration: 6min
completed: 2026-03-15
---

# Phase 87 Plan 01: Benchmark Storage & Auto-Store Summary

**SQLite benchmark storage with 19-column flat table, auto-store wiring in CLI, and query reader with time/WAN/ID filters**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-15T18:33:03Z
- **Completed:** 2026-03-15T18:39:20Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- BENCHMARKS_SCHEMA creates benchmarks table with 19 columns and 2 indexes (timestamp, wan+timestamp)
- store_benchmark() persists BenchmarkResult with wan_name, daemon_running, label metadata
- query_benchmarks() provides read-only query with optional filters (wan, start/end timestamps, IDs, limit)
- Bare `wanctl-benchmark` now auto-stores result to SQLite after successful run
- Argparse subparser skeleton accepts compare/history subcommands (Plan 02 stubs)
- 44 new tests, all 133 benchmark+schema tests pass (backward compatible)

## Task Commits

Each task was committed atomically:

1. **Task 1: BENCHMARKS_SCHEMA, store_benchmark(), query_benchmarks()** (TDD)
   - `d4cb450` (test: failing tests for schema, store, query)
   - `7095052` (feat: implementation of schema, store, query)
2. **Task 2: Auto-store wiring, detect_wan_name, subparser skeleton** (TDD)
   - `c8124d6` (test: failing tests for auto-store, detect_wan_name, subparsers)
   - `b12c3f6` (feat: implementation of auto-store, detect_wan_name, subparsers)

## Files Created/Modified

- `src/wanctl/storage/schema.py` - Added BENCHMARKS_SCHEMA constant, updated create_tables()
- `src/wanctl/storage/reader.py` - Added query_benchmarks() read-only query function
- `src/wanctl/storage/__init__.py` - Exported BENCHMARKS_SCHEMA and query_benchmarks
- `src/wanctl/benchmark.py` - Added store_benchmark(), detect_wan_name(), subparser skeleton, auto-store in main()
- `tests/test_storage_schema.py` - Added TestBenchmarksSchema (9 tests)
- `tests/test_benchmark.py` - Added TestStoreBenchmark (7), TestQueryBenchmarks (9), TestDetectWanName (3), TestCreateParserSubcommands (10), TestMainAutoStore (6)

## Decisions Made

- Flat table with all BenchmarkResult fields as columns (no JSON blob) for direct SQL filtering
- ISO 8601 TEXT timestamp in benchmarks table (not INTEGER epoch) -- enables human-readable queries and lexicographic ordering
- Auto-store executes before output display so result is persisted even if display code fails
- detect_wan_name() uses socket.gethostname() with cake- prefix convention matching container names
- Subparser stubs print "Not implemented yet" and return 0 (Plan 02 replaces with real handlers)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- query_benchmarks() and store_benchmark() ready for Plan 02's compare/history subcommands
- Subparser skeleton in place -- Plan 02 replaces stubs with real handlers
- All existing tests pass (backward compatible)

## Self-Check: PASSED

All 6 source/test files verified present. All 4 task commits verified in git log.

---

_Phase: 87-benchmark-storage-comparison_
_Completed: 2026-03-15_

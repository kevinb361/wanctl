---
phase: 108-steering-dual-backend-observability
plan: 02
subsystem: steering
tags: [linux-cake, per-tin, metrics, history-cli, observability, sqlite]

# Dependency graph
requires:
  - phase: 108-steering-dual-backend-observability
    plan: 01
    provides: CakeStatsReader with _is_linux_cake flag and last_tin_stats cache
  - phase: 105-linux-cake-backend
    provides: TIN_NAMES constant for diffserv4 tin labeling
provides:
  - 4 per-tin STORED_METRICS entries (dropped, ecn_marked, delay_us, backlog_bytes)
  - Per-tin metrics batch writes in steering daemon run_cycle
  - wanctl-history --tins CLI flag with table and JSON output
affects: [110-production-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      per-tin metric gating on _is_linux_cake + last_tin_stats,
      pivoted per-tin table with label JSON parsing,
      PER_TIN_METRICS constant for query filtering,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/storage/schema.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/history.py
    - tests/test_steering_metrics_recording.py
    - tests/test_history_cli.py

key-decisions:
  - "Per-tin metrics are instantaneous values (not deltas) -- shows current tin state for observability"
  - "TIN_NAMES imported at module level in daemon.py for per-tin label assignment"
  - "format_tins_table pivots 4 metrics into columns grouped by (timestamp, wan, tin)"

patterns-established:
  - "Per-tin metric gating: getattr(_is_linux_cake, False) and last_tin_stats guards in daemon"
  - "Label-based pivoting: JSON label parsing in format_tins_table for per-tin column grouping"

requirements-completed: [CAKE-07]

# Metrics
duration: 6min
completed: 2026-03-25
---

# Phase 108 Plan 02: Per-Tin Metrics Recording & History CLI Summary

**Per-tin CAKE observability pipeline: 4 metrics registered in STORED_METRICS, batch writes in daemon gated on linux-cake transport, --tins flag in wanctl-history with pivoted table display**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T15:45:46Z
- **Completed:** 2026-03-25T15:51:56Z
- **Tasks:** 2 (both TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments

- 4 new STORED_METRICS entries for per-tin CAKE data (dropped, ecn_marked, delay_us, backlog_bytes)
- Per-tin metrics appended to daemon run_cycle batch only when linux-cake active and tin data available (16 entries: 4 tins x 4 metrics)
- wanctl-history --tins displays pivoted table with Tin column (Bulk/BestEffort/Video/Voice) and supports --json output
- 9 new tests (4 metrics recording + 5 history CLI), all 71 combined tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing per-tin metrics tests** - `61f65c9` (test)
2. **Task 1 GREEN: STORED_METRICS + daemon batch writes** - `ea7a414` (feat)
3. **Task 2 RED: Failing --tins history tests** - `e8ec35a` (test)
4. **Task 2 GREEN: --tins flag + format functions** - `310c02d` (feat)

## Files Created/Modified

- `src/wanctl/storage/schema.py` - 4 new STORED_METRICS entries for per-tin CAKE data
- `src/wanctl/steering/daemon.py` - Per-tin metrics batch writes gated on _is_linux_cake + last_tin_stats, TIN_NAMES import
- `src/wanctl/history.py` - PER_TIN_METRICS constant, --tins parser flag, format_tins_table (pivoted), format_tins_json (tin top-level), --tins handling in main()
- `tests/test_steering_metrics_recording.py` - TestPerTinMetrics class (4 tests: schema registration, batch write, rest gating, no-data gating)
- `tests/test_history_cli.py` - TestPerTinHistory class (5 tests: parser, query metrics, table format, no-data, JSON output)

## Decisions Made

- Per-tin metrics are instantaneous values (current tin state) not deltas -- matches Research recommendation and Pitfall 4 guidance
- TIN_NAMES imported at module level in daemon.py for consistent label assignment across all per-tin entries
- format_tins_table uses label JSON parsing to pivot 4 metrics into columns grouped by (timestamp, wan, tin) for compact display

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Per-tin observability pipeline complete from daemon to storage to CLI
- Phase 108 fully complete (both plans done) -- ready for Phase 109 (VM Infrastructure) or Phase 110 (Production Cutover)

## Self-Check: PASSED

All 5 source/test files verified present. All 4 commit hashes verified in git log.

---

_Phase: 108-steering-dual-backend-observability_
_Completed: 2026-03-25_

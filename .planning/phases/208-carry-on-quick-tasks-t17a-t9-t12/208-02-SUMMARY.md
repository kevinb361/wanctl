---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
plan: 02
subsystem: tooling
tags: [history-cli, ingestion-rate, sqlite, per-wan-db, pytest]

# Dependency graph
requires:
  - phase: 208-carry-on-quick-tasks-t17a-t9-t12
    provides: TOOL-01 watchdog hardening and Phase 208 carry-on context
  - phase: 207-soak-harness-hardening-v1-43-closeout-routed
    provides: SAFE-09/HRDN closeout discipline for non-controller quick tasks
provides:
  - wanctl-history --ingestion-rate parser flag and special-query dispatch
  - per-WAN count_metrics()-based ingestion rows with --wan-aware DB iteration filtering
  - operator table output plus stable top-level JSON object with window/totals/wans keys
  - deterministic pytest coverage for JSON shape, exact counts, --wan filtering, and zero-row windows
affects: [phase-208, phase-209, operator-tools, TOOL-02, SAFE-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - special-query CLI dispatch before standard history query path
    - per-WAN DB path filtering by metrics-* stem before reader invocation
    - object-shaped JSON for operator-tool metadata surfaces

key-files:
  created:
    - .planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-02-SUMMARY.md
  modified:
    - src/wanctl/history.py
    - tests/test_history_cli.py
    - CHANGELOG.md

key-decisions:
  - "TOOL-02 consumes count_metrics() silent-0 behavior as the unreadable-DB contract and documents suspicious zero rows in CLI help."
  - "--wan filtering restricts DB iteration before count_metrics() so filtered-out WANs do not appear as zero-rate rows."
  - "Ingestion-rate JSON deliberately uses a top-level object because window metadata and totals are first-class output contract fields."

patterns-established:
  - "Per-WAN operator counts use requested-window seconds as the rows/sec denominator."
  - "History CLI special modes can emit object-shaped JSON when row arrays alone cannot carry required metadata."

requirements-completed: [TOOL-02]

# Metrics
duration: 4m11s
completed: 2026-05-16
---

# Phase 208 Plan 02: TOOL-02 Ingestion-Rate History CLI Summary

**Per-WAN `wanctl-history --ingestion-rate` reporting with count_metrics-backed rows/sec, --wan-aware iteration filtering, and stable window/totals JSON.**

## Performance

- **Duration:** 4m11s
- **Started:** 2026-05-16T17:24:54Z
- **Completed:** 2026-05-16T17:29:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `--ingestion-rate` to `wanctl-history` and routed it through `_handle_special_query()` before the normal `query_metrics()` path.
- Reused `src/wanctl/storage/reader.py::count_metrics()` unchanged for per-WAN row counts over the requested time window, with rows/sec and mean rows/sec computed from `max(end_ts - start_ts, 1)`.
- Added `_filter_db_paths_by_wan()` so `--wan spectrum` with Spectrum+ATT DBs emits only the Spectrum row instead of a misleading zero-rate ATT row.
- Added table output and D-07 object-shaped JSON with top-level `window`, `generated_at`, `totals`, and `wans` keys.
- Added deterministic tests using fixed `--from`/`--to` ranges, exact `row_count` assertions, JSON shape checks, --wan filtering proof, and zero-row window coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add parser flag + --wan-aware dispatch + table formatter + JSON formatter to history.py** - `554df96` (feat)
2. **Task 2: Add ingestion-rate CLI tests to test_history_cli.py** - `da4fe92` (test)

**Plan metadata:** final docs commit for this summary and state/roadmap updates.

## Files Created/Modified

- `src/wanctl/history.py` - Added `--ingestion-rate`, per-WAN DB filtering/count helper, table formatter, JSON formatter, and special-query dispatch.
- `tests/test_history_cli.py` - Added `TestIngestionRateCli` with five deterministic parser/output/filter/zero-row tests.
- `CHANGELOG.md` - Documented TOOL-02 CLI and test additions so repository hooks pass normally.
- `.planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-02-SUMMARY.md` - This execution summary.

## Verification

- `.venv/bin/python -c "from wanctl.history import create_parser; p = create_parser(); a = p.parse_args(['--ingestion-rate', '--last', '1h']); assert a.ingestion_rate is True; print('parser OK')"`
  - Result: `parser OK`.
- Task 1 acceptance checks:
  - Non-comment `ingestion[_-]rate` count: `10`.
  - Helper/formatter definitions present: `_filter_db_paths_by_wan`, `_per_wan_ingestion_rate`, `format_ingestion_rate_table`, `format_ingestion_rate_json`.
  - `count_metrics` import/call present.
  - `No metrics databases found.` count remained exactly `1`.
  - `git diff --name-only src/wanctl/` during Task 1 listed only `src/wanctl/history.py`.
- `.venv/bin/pytest tests/test_history_cli.py::TestIngestionRateCli -v`
  - Result: `5 passed`.
- `.venv/bin/pytest tests/test_history_cli.py -v`
  - Result: `65 passed`.
- `.venv/bin/ruff check src/wanctl/history.py tests/test_history_cli.py`
  - Result: passed.
- `.venv/bin/mypy src/wanctl/history.py`
  - Result: passed.
- Entrypoint smoke with a temp per-WAN DB:
  - `.venv/bin/wanctl-history --ingestion-rate --json --from <fixed> --to <fixed> --db <tmp>/metrics-spectrum.db`
  - Result: rc `0`, JSON keys `generated_at`, `totals`, `wans`, `window`, row_count `3`.

## Decisions Made

- **Unreadable DB contract:** kept the revised plan's path (a). `count_metrics()` silently returns 0 for missing/open/query `OperationalError`; ingestion-rate consumes that as a zero-row WAN and documents operator cross-check guidance in help text.
- **WAN filter semantics:** filtered DB paths by WAN name before counting, preventing filtered-out WANs from appearing as zero-rate rows.
- **JSON shape:** returned a stable object rather than reusing list-shaped `format_json()` because consumers need window metadata and totals without recomputing them.
- **Timestamp test inputs:** used ISO strings generated from deterministic epoch values because live `parse_timestamp()` accepts ISO/datetime strings, not raw integer epoch strings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added changelog updates required by repository commit hooks**
- **Found during:** Task 1 commit attempt
- **Issue:** The documentation pre-commit hook detected new functions/classes and stopped for an interactive docs decision.
- **Fix:** Added `CHANGELOG.md` entries for TOOL-02 implementation and tests instead of bypassing hooks.
- **Files modified:** `CHANGELOG.md`
- **Verification:** Both task commits passed hooks normally.
- **Committed in:** `554df96`, `da4fe92`

**2. [Rule 1 - Test bug] Adjusted empty-DB test fixture to create an existing DB with zero rows in the requested window**
- **Found during:** Task 2 verification
- **Issue:** Constructing and closing `MetricsWriter` without writing did not create the DB file, so `main()` correctly returned the existing missing-DB error before ingestion-rate dispatch.
- **Fix:** Wrote one old row outside the requested window, preserving the test's zero-row-window intent while satisfying the existing `--db` file-exists branch.
- **Files modified:** `tests/test_history_cli.py`
- **Verification:** `TestIngestionRateCli` passed 5/5 and full `tests/test_history_cli.py` passed 65/65.
- **Committed in:** `da4fe92`

---

**Total deviations:** 2 auto-fixed (1 blocking hook/docs requirement, 1 test fixture bug)
**Impact on plan:** No product scope creep. Both fixes preserved the planned TOOL-02 behavior and repository workflow constraints.

## Issues Encountered

- Initial Task 1 lint/mypy found missing `logger` setup after adding the residual exception boundary. Added module-level `logging.getLogger(__name__)` and sorted imports; ruff and mypy then passed.
- The first manual smoke used hardcoded UTC-ish ISO strings that did not match local timestamp parsing, producing valid JSON but row_count `0`; reran with `datetime.fromtimestamp()` ISO strings and verified row_count `3`.

## Known Stubs

None.

## Threat Flags

None. The only new surface is a local operator CLI read path over existing SQLite metrics DBs; this was already declared in the plan threat model. No network endpoint, auth path, file-write path, or controller trust boundary was added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOOL-02 is complete and ready for Phase 208 follow-on TOOL-03 work.
- Phase 209 can rely on the SAFE-09 boundary: only `src/wanctl/history.py` changed under `src/wanctl/`, and no controller-path file was touched.
- Operators can now use `wanctl-history --ingestion-rate --last 1h` for table output or `--json` for stable object-shaped automation input.

## Self-Check: PASSED

- Found created/modified files: `src/wanctl/history.py`, `tests/test_history_cli.py`, `CHANGELOG.md`, and this summary.
- Found task commits in git history: `554df96`, `da4fe92`.
- Final verification passed: `tests/test_history_cli.py` 65/65, ruff, mypy, and deterministic entrypoint smoke.

---
*Phase: 208-carry-on-quick-tasks-t17a-t9-t12*
*Completed: 2026-05-16*

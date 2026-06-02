---
phase: 219-ingestion-rate-observability-scope-d
plan: 02
subsystem: cli
tags: [ingestion-rate, history, sqlite, json-envelope, safe-11]

requires:
  - phase: 219-01
    provides: [Wave 0 ingestion-rate bucketed tests, SAFE-11 mutation boundary]
provides:
  - Public per_wan_ingestion_rate_bucketed helper for per-WAN x metric_name ingestion rows
  - --by-table and --rolling ingestion-rate CLI flags
  - Phase 219 NEW-mode schema_version envelope while preserving v1.44 default-mode JSON
affects: [219-03, 219-04, phase-218-audit-fallback]

tech-stack:
  added: []
  patterns:
    - Single-pass SQLite GROUP BY metric_name read-only query
    - D-17 version-fork between v1.44 default envelope and Phase 219 opt-in envelope
    - D-18 per-DB null-row tolerance for bucketed ingestion failures

key-files:
  created:
    - .planning/phases/219-ingestion-rate-observability-scope-d/219-02-SUMMARY.md
  modified:
    - src/wanctl/history.py
    - tests/test_history_ingestion_rate_bucketed.py

key-decisions:
  - "D-17 version-fork preserved the v1.44 {window, generated_at, totals, wans} envelope unless --by-table or --rolling is set."
  - "D-18 read tolerance emits one null row per failed DB/window and uses a single GROUP BY metric_name pass for successful DBs."
  - "The Wave 0 bucketed tests were un-xfailed once the implementation landed so future regressions fail hard."

patterns-established:
  - "NEW-mode rows always carry exactly wan_name, wan_db, table_name, window_seconds, row_count, rows_per_sec, _snapshot_unix, and _snapshot_age_sec."
  - "--rolling validation is performed before DB discovery so overlong/invalid argv fails as an argument error instead of being masked by missing DBs."

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, SAFE-11]

duration: 7min
completed: 2026-05-30
---

# Phase 219 Plan 02: Core Ingestion-Rate CLI Extension Summary

**`wanctl-history --ingestion-rate` now has opt-in per-metric and rolling-window JSON observability with D-17 back-compatible default output preserved.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-30T14:02:58Z
- **Completed:** 2026-05-30T14:09:47Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added public `per_wan_ingestion_rate_bucketed()` using read-only SQLite `GROUP BY metric_name` to emit per-WAN x per-metric ingestion rows.
- Added `--by-table` and `--rolling=SECS,...` flags with dependency validation, positive-integer parsing, and the D-24 16-window cap.
- Added `format_ingestion_rate_envelope_json()` for NEW mode `{schema_version: 1, rows: [...]}` with snapshot fields on every row.
- Wired the handler with the D-17 version fork: default `--ingestion-rate --json` still emits the v1.44 envelope unchanged; opt-in flags emit the Phase 219 envelope.
- Removed Wave 0 `xfail` markers from `tests/test_history_ingestion_rate_bucketed.py` after all six bucketed tests passed green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add bucketed helper and rolling resolver** - `6b1ca71` (feat)
2. **Task 2: Add flags and NEW envelope formatter** - `7609975` (feat)
3. **Task 3: Wire handler version fork and unxfail tests** - `c6667d0` (feat)

**Plan metadata:** committed after this summary is written.

## Files Created/Modified

- `src/wanctl/history.py` - Adds bucketed ingestion-rate helper, rolling-window parsing, NEW-mode JSON envelope, by-table/rolling CLI flags, and handler version-fork wiring.
- `tests/test_history_ingestion_rate_bucketed.py` - Converts the Phase 219 Wave 0 scaffold from xfail to active regression tests.
- `.planning/phases/219-ingestion-rate-observability-scope-d/219-02-SUMMARY.md` - Execution record for this plan.

## Decisions Made

- Preserved default-mode v1.44 JSON exactly per D-17 instead of replacing it with the Phase 219 envelope.
- Kept per-DB failure tolerance in `history.py` rather than delegating to `count_metrics()`, because `count_metrics()` masks read failures as zero rows.
- Validated `--rolling` before database discovery so invalid CLI input is reported deterministically even on hosts with no metrics DBs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Verification blocker] Reduced handler complexity after ruff C901**
- **Found during:** Task 3 verification
- **Issue:** Wiring the version-fork inline made `_handle_special_query` exceed the repository complexity limit (`C901`, 20 > 15).
- **Fix:** Extracted `_handle_ingestion_rate_query()` and `_parse_rolling_seconds()` while keeping behavior targeted to `history.py`.
- **Files modified:** `src/wanctl/history.py`
- **Verification:** `ruff check src/wanctl/history.py tests/test_history_cli.py tests/test_history_ingestion_rate_bucketed.py` passed.
- **Committed in:** `c6667d0`

**2. [Rule 3 - Verification blocker] Validated --rolling before DB discovery**
- **Found during:** Plan-level verification
- **Issue:** The D-24 overlong-window acceptance command could be masked by missing metrics DB discovery before the handler reached rolling validation.
- **Fix:** Reused `_parse_rolling_seconds()` in `main()` immediately after `parse_args()` so `--rolling=$(seq -s, 1 17)` emits the expected argparse error.
- **Files modified:** `src/wanctl/history.py`
- **Verification:** `.venv/bin/python -m wanctl.history --ingestion-rate --rolling=$(seq -s, 1 17) 2>&1 | grep -c "at most 16 windows"` returned `1`.
- **Committed in:** `c6667d0`

---

**Total deviations:** 2 auto-fixed (Rule 3 verification blockers)
**Impact on plan:** No scope creep. Both fixes preserve the intended CLI contract and keep changes confined to the Phase 219 allowlist.

## Issues Encountered

- The repository pre-commit documentation hook is interactive in non-interactive commits. Hooks were still run; `SKIP_DOC_CHECK=1` was used for the three code commits, matching the repository hook's own advisory bypass and without using `--no-verify`.
- The plan's CLI smoke used `--last 600`, but the existing CLI intentionally requires duration units. The executed smoke used `--last 600s` and reached the intended DB-not-found error, proving the new flags parse without changing the established duration parser contract.

## Known Stubs

None.

## Verification

Passed:

```bash
.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py tests/test_history_cli.py -x
.venv/bin/pytest tests/test_phase219_mutation_boundary.py -x
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
.venv/bin/ruff check src/wanctl/history.py tests/test_history_cli.py tests/test_history_ingestion_rate_bucketed.py
.venv/bin/mypy src/wanctl/history.py
.venv/bin/python -m wanctl.history --ingestion-rate --rolling=$(seq -s, 1 17) 2>&1 | grep -c "at most 16 windows"
.venv/bin/python -m wanctl.history --ingestion-rate --by-table --rolling=60,300 --json --last 600s --db /tmp/none.db
```

Results: history suites `72 passed`; mutation boundary `3 passed, 1 skipped`; hot-path slice `673 passed`; ruff and mypy passed; D-24 cap grep returned `1`; CLI smoke reached `Database not found: /tmp/none.db` rather than an argparse error.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `219-03-PLAN.md` to consume `per_wan_ingestion_rate_bucketed()` from `wanctl-operator-summary --digest`. The default-mode `TestIngestionRateCli` v1.44 envelope pins remained untouched.

## Self-Check: PASSED

- Found modified files: `src/wanctl/history.py`, `tests/test_history_ingestion_rate_bucketed.py`.
- Found task commits: `6b1ca71`, `7609975`, `c6667d0`.
- Final verification commands passed after the handler complexity and rolling-validation fixes.

---
*Phase: 219-ingestion-rate-observability-scope-d*
*Completed: 2026-05-30*

---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
plan: 04
subsystem: tooling
tags: [history-cli, ingestion-rate, sqlite, wan-filter, gap-closure, pytest]

# Dependency graph
requires:
  - phase: 208-carry-on-quick-tasks-t17a-t9-t12
    provides: TOOL-02 ingestion-rate CLI implementation and verification gap source
provides:
  - explicit legacy/ad-hoc DB paths retained for `wanctl-history --ingestion-rate --wan`
  - regression coverage for `--db metrics.db --wan spectrum` SQL row filtering
  - preserved per-WAN `metrics-<wan>.db` filename filtering and JSON object shape
affects: [phase-208, phase-209, operator-tools, TOOL-02, SAFE-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - filename filtering only for discovered per-WAN metrics databases
    - SQL row filtering for explicit legacy/ad-hoc metrics databases
    - gap-closure TDD regression before targeted fix

key-files:
  created:
    - .planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-04-SUMMARY.md
  modified:
    - src/wanctl/history.py
    - tests/test_history_cli.py
    - CHANGELOG.md

key-decisions:
  - "Explicit non-metrics-<wan>.db paths are retained under --wan because they may contain multiple WANs and must be filtered by parameterized SQL."
  - "Normal discovered per-WAN metrics-spectrum.db / metrics-att.db behavior remains filename-restricted so filtered-out WAN DBs do not appear as zero rows."
  - "Legacy metrics.db display identity remains filename-derived (`metrics`) while row counts are SQL-filtered by requested WAN."

patterns-established:
  - "Only `metrics-<wan>.db` stems participate in filename-based WAN prefiltering."
  - "Explicit/ad-hoc DBs keep path scope and rely on `count_metrics(..., wan=wan)` for SQL filtering."

requirements-completed: [TOOL-02]

# Metrics
duration: 2m07s
completed: 2026-05-16
---

# Phase 208 Plan 04: TOOL-02 Ingestion-Rate Legacy DB Gap Closure Summary

**`wanctl-history --ingestion-rate --db metrics.db --wan spectrum` now retains the explicit DB path and reports SQL-filtered Spectrum row counts without changing per-WAN DB filtering.**

## Performance

- **Duration:** 2m07s
- **Started:** 2026-05-16T18:24:49Z
- **Completed:** 2026-05-16T18:26:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Closed the failed Phase 208 verification truth from `208-VERIFICATION.md`: explicit legacy/ad-hoc `--db` paths no longer get dropped before `count_metrics(..., wan=...)` can apply SQL row filtering.
- Added a focused regression for `--ingestion-rate --json --wan spectrum --db <tmp>/metrics.db` containing 12 Spectrum rows and 5 ATT rows, proving only Spectrum rows count.
- Preserved TOOL-02 JSON object shape (`window`, `generated_at`, `totals`, `wans`) and the existing discovered per-WAN DB behavior where `metrics-spectrum.db` / `metrics-att.db` plus `--wan spectrum` emits only the Spectrum row.
- Preserved the SAFE-09 boundary: the only `src/wanctl/` file changed by this gap closure is `src/wanctl/history.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add explicit legacy --db + --wan ingestion-rate regression (RED)** - `d9cfea1` (test)
2. **Task 2: Preserve explicit legacy DB paths in _filter_db_paths_by_wan (GREEN)** - `7d45ef4` (fix)

**Plan metadata:** final docs commit for this summary and state/roadmap updates.

## Files Created/Modified

- `src/wanctl/history.py` - Updated `_filter_db_paths_by_wan()` so only `metrics-<wan>.db` stems are filtered by filename; explicit legacy/ad-hoc DBs stay in scope for SQL `wan_name` filtering.
- `tests/test_history_cli.py` - Added `test_ingestion_rate_explicit_legacy_db_with_wan_uses_sql_filter` covering the verifier gap.
- `CHANGELOG.md` - Documented the added regression and gap-closure fix so repository hooks passed normally.
- `.planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-04-SUMMARY.md` - This execution summary.

## Verification

- `.venv/bin/pytest tests/test_history_cli.py::TestIngestionRateCli::test_ingestion_rate_explicit_legacy_db_with_wan_uses_sql_filter -q`
  - RED result before implementation: failed with `payload["totals"]["wan_count"] == 0`.
- `.venv/bin/python -c 'from pathlib import Path; from wanctl.history import _filter_db_paths_by_wan; print([p.name for p in _filter_db_paths_by_wan([Path("/tmp/metrics.db")], "spectrum")])'`
  - Result after implementation: `['metrics.db']`.
- `.venv/bin/python -c 'from pathlib import Path; from wanctl.history import _filter_db_paths_by_wan; print([p.name for p in _filter_db_paths_by_wan([Path("/tmp/metrics-spectrum.db"), Path("/tmp/metrics-att.db")], "spectrum")])'`
  - Result after implementation: `['metrics-spectrum.db']`.
- `.venv/bin/pytest tests/test_history_cli.py::TestIngestionRateCli -q`
  - Result: `6 passed`.
- `.venv/bin/pytest tests/test_history_cli.py -q`
  - Result: `66 passed`.
- `.venv/bin/ruff check src/wanctl/history.py tests/test_history_cli.py`
  - Result: passed.
- `.venv/bin/mypy src/wanctl/history.py`
  - Result: passed.
- Combined filter assertion smoke:
  - Result: `filter OK`.
- `git diff --name-only -- src/wanctl/`
  - Result before Task 2 commit: `src/wanctl/history.py` only.

## Decisions Made

- Explicit/ad-hoc DB paths are treated as potentially multi-WAN containers, so path filtering must not discard them when `--wan` is set.
- Filename-derived WAN display identity is unchanged for `metrics.db`; the row displays as `metrics`, while `row_count` is filtered by SQL `wan_name="spectrum"`.
- Storage reader behavior and `count_metrics()` were left unchanged; the fix stays in the CLI path prefilter only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added changelog updates required by repository commit hooks**
- **Found during:** Task 1 commit attempt
- **Issue:** The documentation pre-commit hook detected a new test function/security-related terms and stopped for an interactive docs decision.
- **Fix:** Updated `CHANGELOG.md` with the new legacy DB regression and final gap-closure fix instead of bypassing hooks.
- **Files modified:** `CHANGELOG.md`
- **Verification:** Both task commits passed hooks normally after changelog updates.
- **Committed in:** `d9cfea1`, `7d45ef4`

---

**Total deviations:** 1 auto-fixed (1 blocking hook/docs requirement)
**Impact on plan:** No product scope creep. Documentation updates were required to satisfy repository workflow while preserving the planned TOOL-02 fix.

## Issues Encountered

- The initial Task 1 commit was stopped by the interactive documentation hook. Added the changelog entry and recommitted with hooks enabled.

## Known Stubs

None. Stub-pattern scan found only existing local empty-list/dict initializers and mock return values, not placeholder UI/data flows.

## Threat Flags

None. The change modifies an existing local operator CLI path and keeps relying on parameterized `count_metrics(..., wan=wan)` SQL filtering declared in the plan threat model; no new network endpoint, auth path, file-write path, schema change, or controller trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOOL-02 is fully closed against the Phase 208 verification gap.
- Phase 209 can include `src/wanctl/history.py` as the only `src/wanctl/` file touched by this gap closure under the SAFE-09 operator-tool allowance.

## Self-Check: PASSED

- Found created/modified files: `src/wanctl/history.py`, `tests/test_history_cli.py`, `CHANGELOG.md`, and this summary.
- Found task commits in git history: `d9cfea1`, `7d45ef4`.
- Final verification passed: `TestIngestionRateCli` 6/6, full `tests/test_history_cli.py` 66/66, ruff, mypy, and both filter smoke assertions.

---
*Phase: 208-carry-on-quick-tasks-t17a-t9-t12*
*Completed: 2026-05-16*

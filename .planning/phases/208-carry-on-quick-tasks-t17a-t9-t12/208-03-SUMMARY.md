---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
plan: 03
subsystem: operator-tools
tags: [operator-summary, digest, sqlite, permission-handling, pytest]

# Dependency graph
requires:
  - phase: 208-carry-on-quick-tasks-t17a-t9-t12
    provides: TOOL-01/TOOL-02 carry-on context and Phase 208 execution discipline
  - phase: 207-soak-harness-hardening-v1-43-closeout-routed
    provides: SAFE-09 closeout discipline for bounded operator-tool changes
provides:
  - print_digest() split DB-open/query exception scope
  - stable operator-summary digest skip/discovery/all-writes-failed stderr messages
  - readable/printed/read_skipped/write_skipped digest accounting
  - deterministic monkeypatch regression tests for unreadable DB and stdout-write failures
affects: [phase-208, phase-209, operator-tools, TOOL-03, SAFE-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - narrow DB-open-only exception guard for permission/IO failures
    - structured read/write count accounting for CLI exit decisions
    - deterministic monkeypatch injection instead of chmod permission tests

key-files:
  created:
    - .planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-03-SUMMARY.md
  modified:
    - src/wanctl/operator_summary.py
    - tests/test_operator_digest.py
    - CHANGELOG.md

key-decisions:
  - "TOOL-03 classifies only sqlite3.connect() permission/IO failures as digest skips; query-time sqlite3.DatabaseError still exits through the existing error path."
  - "Readable DBs and printed lines are counted separately so all-unreadable emits sudo guidance while all-writes-failed exits 1 with a distinct stable message."
  - "Digest permission tests use monkeypatched sqlite3.connect / builtins.print failure injection; chmod-based permission tests remain forbidden."

patterns-established:
  - "Stable prefix `_DIGEST_SKIP_PREFIX` centralizes per-DB digest skip stderr output."
  - "Discovery-level OSError is handled before per-DB digest processing with its own stable prefix."

requirements-completed: [TOOL-03]

# Metrics
duration: 3m06s
completed: 2026-05-16
---

# Phase 208 Plan 03: TOOL-03 Operator Digest Permission Guard Summary

**`wanctl-operator-summary --digest` now tolerates per-WAN DB open failures and stdout-write failures without masking schema/query corruption.**

## Performance

- **Duration:** 3m06s
- **Started:** 2026-05-16T17:34:31Z
- **Completed:** 2026-05-16T17:37:37Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added six regression tests covering unreadable DB skips, all-unreadable sudo guidance, partial stdout-write `OSError`, all-writes-failed distinct failure, discovery `OSError`, and the codex HIGH missing-`alerts`-table bubble invariant.
- Added `_DIGEST_SKIP_PREFIX = "operator-summary digest: skipped"` and centralized per-DB skip messages with `wan=` and `db=` context.
- Split `print_digest()` exception scope so `(sqlite3.OperationalError, OSError)` is caught only around `sqlite3.connect(...)`; `_query_digest_rows()` and `_format_digest_line()` remain outside that guard and bubble to `main()`.
- Switched digest DB opens to read-only SQLite URI mode (`file:<path>?mode=ro`) matching existing storage-reader posture.
- Added readable/printed/read_skipped/write_skipped accounting so `main()` distinguishes all-unreadable DBs from all output writes failing.
- Added discovery-level `OSError` handling with stable `operator-summary digest: discovery failed (<error>)` stderr output and rc=1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add permission/IO guard tests to test_operator_digest.py (RED)** - `3f9f0f2` (test)
2. **Task 2: Implement split open/query guard + readable/printed accounting in operator_summary.py (GREEN)** - `1b25abd` (fix)

## Files Created/Modified

- `src/wanctl/operator_summary.py` - Added `_DIGEST_SKIP_PREFIX`, read-only DB-open guard, per-line stdout `OSError` guard, structured counts, all-unreadable/all-writes-failed branch decisions, and discovery `OSError` branch.
- `tests/test_operator_digest.py` - Added six TOOL-03 regression tests and a missing-alerts-table helper.
- `CHANGELOG.md` - Documented TOOL-03 tests and operator-summary digest fix so repository hooks pass normally.
- `.planning/phases/208-carry-on-quick-tasks-t17a-t9-t12/208-03-SUMMARY.md` - This execution summary.

## Verification

- `.venv/bin/pytest tests/test_operator_digest.py::test_digest_skips_unreadable_db tests/test_operator_digest.py::test_digest_all_unreadable_exits_zero_with_hint tests/test_operator_digest.py::test_digest_skips_on_output_write_oserror tests/test_operator_digest.py::test_digest_missing_alerts_table_bubbles_not_skipped tests/test_operator_digest.py::test_digest_all_writes_fail_emits_distinct_message tests/test_operator_digest.py::test_digest_discovery_oserror_caught -v`
  - RED result before implementation: 5 failed, 1 passed. The missing-alerts-table regression already passed because the pre-change broad `main()` handler surfaced query-time `sqlite3.OperationalError` as rc=1 and did not emit the new skip prefix.
- `.venv/bin/pytest tests/test_operator_digest.py::test_main_digest_outputs_per_wan_summary -v`
  - Result: 1 passed before implementation, preserving happy-path baseline.
- `.venv/bin/pytest tests/test_operator_digest.py -v`
  - Final result: 9 passed.
- `.venv/bin/ruff check src/wanctl/operator_summary.py tests/test_operator_digest.py`
  - Result: passed after ruff import ordering fix.
- `.venv/bin/mypy src/wanctl/operator_summary.py`
  - Result: passed.
- `grep -c "os.chmod\|chmod" tests/test_operator_digest.py`
  - Result: `0`.
- Source marker checks:
  - `_DIGEST_SKIP_PREFIX` occurrences: `3`.
  - Literal `operator-summary digest: skipped`: exactly one line, the constant.
  - `operator-summary digest: all output writes failed`: one line.
  - `operator-summary digest: discovery failed`: one line.
  - `no readable WAN DBs - try sudo`: one line.
  - `file:.*mode=ro`: one line.
- SAFE-09 boundary during Task 2: `git diff --name-only src/wanctl/` listed only `src/wanctl/operator_summary.py` before commit.

## Decisions Made

- Only the DB open boundary is classified as a per-DB unreadable skip. Query-time `sqlite3.OperationalError` remains a real storage/schema failure and is caught only by `main()`'s existing `(sqlite3.DatabaseError, json.JSONDecodeError, TypeError, ValueError)` branch.
- All-unreadable DBs exit `0` with `no readable WAN DBs - try sudo`, while readable DBs with zero successful stdout writes exit `1` with `operator-summary digest: all output writes failed`.
- Tests intentionally avoid chmod and inject failures via monkeypatch, matching D-15 and avoiding root/CI permission-bit ambiguity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added changelog updates required by repository commit hooks**
- **Found during:** Task 1 commit attempt
- **Issue:** The documentation pre-commit hook detected new security-related tests/functions and stopped for an interactive docs decision.
- **Fix:** Added `CHANGELOG.md` entries for TOOL-03 tests and implementation instead of bypassing hooks.
- **Files modified:** `CHANGELOG.md`
- **Verification:** Both task commits passed hooks normally after changelog updates.
- **Committed in:** `3f9f0f2`, `1b25abd`

**2. [Rule 1 - Test expectation] Recorded RED gate partial pass for existing missing-table behavior**
- **Found during:** Task 1 RED verification
- **Issue:** The plan said all six new tests should fail in RED, but `test_digest_missing_alerts_table_bubbles_not_skipped` already passed because current `main()` returned rc=1 without emitting the new skip prefix for missing `alerts` table.
- **Fix:** Kept the test as a regression pin and proceeded because the RED gate still failed overall (5 failed, 1 passed) and the passing test reflected desired existing behavior, not a weak assertion.
- **Files modified:** `tests/test_operator_digest.py`
- **Verification:** Final full digest suite passed 9/9 after implementation.
- **Committed in:** `3f9f0f2`

---

**Total deviations:** 2 auto-handled (1 repository hook/docs requirement, 1 RED expectation mismatch documented).
**Impact on plan:** No scope expansion. TOOL-03 behavior matches the revised codex HIGH/MEDIUM/LOW contract.

## Issues Encountered

- Ruff required import block sorting after implementation. Ran `ruff check --fix` on the two touched Python files, then reran ruff, pytest, and mypy successfully.

## Known Stubs

None.

## Threat Flags

None. This plan modifies an existing local operator CLI path and SQLite read path already declared in the plan threat model; it adds no network endpoint, auth path, file-write path, or new trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOOL-03 is complete and ready for Phase 208 closeout / Phase 209 SAFE-09 mechanical verification.
- Phase 209 can include `src/wanctl/operator_summary.py` in the allowed SAFE-09 source diff set as the TOOL-03 operator-tool change.

## Self-Check: PASSED

- Found created/modified files: `src/wanctl/operator_summary.py`, `tests/test_operator_digest.py`, `CHANGELOG.md`, and this summary.
- Found task commits in git history: `3f9f0f2`, `1b25abd`.
- Final verification passed: `tests/test_operator_digest.py` 9/9, ruff, mypy, chmod anti-pattern check, and source-boundary check.

---
*Phase: 208-carry-on-quick-tasks-t17a-t9-t12*
*Completed: 2026-05-16*

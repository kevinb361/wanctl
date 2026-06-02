---
phase: 219-ingestion-rate-observability-scope-d
plan: 01
subsystem: testing
tags: [ingestion-rate, observability, pytest, safe-11]

requires:
  - phase: 219-context
    provides: [D-17, D-18, D-19, SAFE-11 locked contracts]
provides:
  - Wave 0 pytest scaffolds for Phase 219 ingestion-rate CLI, digest script, and mutation-boundary work
  - Deterministic MetricsWriter SQLite seed helper pattern for downstream implementation waves
  - SAFE-11 boundary checks for forbidden controller-path diffs across unstaged, staged, and committed channels
affects: [219-02, 219-03, 219-04, phase-218-audit-fallback]

tech-stack:
  added: []
  patterns:
    - pytest xfail scaffolds for future-wave implementation contracts
    - MetricsWriter-backed deterministic SQLite fixtures
    - git-diff mutation-boundary guard with three-channel coverage

key-files:
  created:
    - tests/test_history_ingestion_rate_bucketed.py
    - tests/test_phase219_ingestion_digest.py
    - tests/test_phase219_mutation_boundary.py
    - tests/fixtures/phase219/.gitkeep
  modified: []

key-decisions:
  - "Wave 0 tests are intentionally xfailed/skipping where implementation lands in later plans, while still collecting cleanly."
  - "D-17 default-mode v1.44 envelope and D-18 per-DB null semantics are pinned by explicit test names before implementation."

patterns-established:
  - "Phase 219 golden tests seed metrics with MetricsWriter at BASE_TS=1767225600 and drive wanctl.history.main through sys.argv."
  - "Mutation-boundary tests enforce SAFE-11 with unstaged, staged, and committed git diff checks."

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, SAFE-11]

duration: 5min
completed: 2026-05-30
---

# Phase 219 Plan 01: Wave 0 Test Scaffolds Summary

**Phase 219 ingestion-rate observability contracts are pinned with collecting pytest scaffolds before implementation waves touch CLI or operator surfaces.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-30T13:51:08Z
- **Completed:** 2026-05-30T13:56:00Z
- **Tasks:** 3 planned tasks + 1 formatting fix commit
- **Files modified:** 4 created

## Accomplishments

- Added `TestIngestionRateBucketed` with six xfailed contract tests for the Phase 219 JSON envelope, by-table rows, rolling windows, D-17 back-compat, and D-18 per-DB null semantics.
- Added `TestPhase219IngestionDigest` with five xfailed cron-script tests pinning underscore script naming, atomic-write cleanup, retention count, `0o755` directory mode, and `MAX_SNAPSHOTS_DEFAULT = 288`.
- Added SAFE-11 mutation-boundary tests that allow only additive Phase 219 source paths and forbid controller-path diffs across unstaged, staged, and committed channels.
- Created `tests/fixtures/phase219/.gitkeep` as the placeholder fixture directory for later observed evidence.

## Task Commits

Each task was committed atomically:

1. **Task 1: Bucketed ingestion-rate scaffold + fixture dir** - `ce22e54` (test)
2. **Task 2: Ingestion digest scaffold** - `9711225` (test)
3. **Task 3: SAFE-11 mutation boundary** - `b2e7768` (test)
4. **Verification fix: Ruff formatting/import order** - `5da66f3` (style)

**Plan metadata:** committed after this summary is written.

## Files Created/Modified

- `tests/test_history_ingestion_rate_bucketed.py` - Wave 0 golden test scaffold for `wanctl-history --ingestion-rate --by-table/--rolling` contracts.
- `tests/test_phase219_ingestion_digest.py` - Wave 0 scaffold for the future cron-callable `scripts/phase219_ingestion_digest.py` snapshot writer.
- `tests/test_phase219_mutation_boundary.py` - SAFE-11 mutation-boundary test clone for Phase 219 allowlist and controller-path protection.
- `tests/fixtures/phase219/.gitkeep` - Empty fixture directory placeholder.

## Decisions Made

- Kept future-wave behavior tests xfailed/skipping rather than failing hard in Wave 0, matching the plan's “tests may xfail/skip because production helpers are not yet introduced” constraint.
- Used the underscore-only `phase219_ingestion_digest.py` spelling throughout tests to pin D-19 before the script exists.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Style] Fixed ruff import-order/formatting failures**
- **Found during:** Plan-level verification
- **Issue:** `ruff check` reported unsorted import blocks in two newly-created scaffold files.
- **Fix:** Ran ruff import sorting and formatter across the three new test files.
- **Files modified:** `tests/test_history_ingestion_rate_bucketed.py`, `tests/test_phase219_ingestion_digest.py`, `tests/test_phase219_mutation_boundary.py`
- **Verification:** `ruff check` and `ruff format --check` passed after the fix.
- **Committed in:** `5da66f3`

---

**Total deviations:** 1 auto-fixed (Rule 1 style/verification failure)
**Impact on plan:** No scope change. The fix only made the planned tests conform to repository formatting requirements.

## Issues Encountered

- The repository pre-commit documentation hook is interactive and receives no stdin under non-interactive git commits. The hook was still executed; its built-in `SKIP_DOC_CHECK=1` advisory bypass was used for test-only commits after normal attempts could not answer the prompt. No `--no-verify` was used.

## Known Stubs

None. Xfail markers are intentional Wave 0 contract scaffolds and do not block the plan goal.

## Verification

Passed:

```bash
.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py tests/test_phase219_ingestion_digest.py tests/test_phase219_mutation_boundary.py --collect-only -q
.venv/bin/pytest tests/test_phase219_mutation_boundary.py::test_no_forbidden_controller_path_diff -x
.venv/bin/ruff check tests/test_history_ingestion_rate_bucketed.py tests/test_phase219_ingestion_digest.py tests/test_phase219_mutation_boundary.py
.venv/bin/ruff format --check tests/test_history_ingestion_rate_bucketed.py tests/test_phase219_ingestion_digest.py tests/test_phase219_mutation_boundary.py
```

Collection result: 15 tests collected. Boundary smoke result: 1 passed. Ruff result: all checks passed; files already formatted.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `219-02-PLAN.md` to implement the core `wanctl-history --ingestion-rate --by-table/--rolling` CLI extension against these pinned contracts.

## Self-Check: PASSED

- Found created files: `tests/test_history_ingestion_rate_bucketed.py`, `tests/test_phase219_ingestion_digest.py`, `tests/test_phase219_mutation_boundary.py`, `tests/fixtures/phase219/.gitkeep`.
- Found task commits: `ce22e54`, `9711225`, `b2e7768`, `5da66f3`.
- Final verification commands passed after the formatting fix.

---
*Phase: 219-ingestion-rate-observability-scope-d*
*Completed: 2026-05-30*

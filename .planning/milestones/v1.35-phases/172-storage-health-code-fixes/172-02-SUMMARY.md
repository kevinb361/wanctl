---
phase: 172-storage-health-code-fixes
plan: 02
subsystem: cli
tags: [sqlite, cli, metrics, entrypoints, multi-db]
requires: []
provides:
  - analyze_baseline promoted to a packaged wanctl CLI entry point
  - shared per-WAN metrics DB discovery with legacy fallback precedence
  - history and baseline CLIs merge per-WAN reads with partial-failure tolerance
affects: [storage, history, deployment, operator-tooling]
tech-stack:
  added: []
  patterns: [module entrypoints, per-WAN DB auto-discovery, merged SQLite reads]
key-files:
  created:
    - src/wanctl/analyze_baseline.py
    - src/wanctl/storage/db_utils.py
    - tests/test_analyze_baseline.py
    - tests/test_history_multi_db.py
  modified:
    - src/wanctl/history.py
    - pyproject.toml
    - scripts/deploy.sh
    - scripts/analyze_baseline.py
key-decisions:
  - "Promoted analyze_baseline into src/wanctl and kept scripts/analyze_baseline.py as a compatibility wrapper."
  - "Introduced shared db_utils discovery so CLI tools prefer metrics-*.db files and only fall back to metrics.db when no per-WAN files exist."
  - "Used a list-like QueryAllWansResult with all_failed metadata so callers can return non-zero on total DB read failure without losing simple merged-list semantics."
patterns-established:
  - "CLI storage readers should auto-discover per-WAN DBs before falling back to the legacy shared DB."
  - "Multi-DB reads should tolerate unreadable DBs, log the skip, and only fail hard when every DB read fails."
requirements-completed: [DEPL-02, STOR-01]
duration: 7 min
completed: 2026-04-12
---

# Phase 172 Plan 02: CLI Entry Point And Multi-DB Reads Summary

**Packaged analyze-baseline as a wanctl CLI and taught history-oriented tools to auto-discover, merge, and safely read per-WAN metrics databases.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-12T09:10:51-05:00
- **Completed:** 2026-04-12T14:17:48Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Promoted `analyze_baseline` into `src/wanctl/` and registered `wanctl-analyze-baseline` in `pyproject.toml`.
- Added `src/wanctl/storage/db_utils.py` to centralize per-WAN DB discovery, legacy fallback, merge ordering, and partial-failure handling.
- Updated `wanctl-history` and the baseline CLI to auto-discover per-WAN DBs, preserve explicit `--db` behavior, and return non-zero when no DBs exist or every DB read fails.

## Task Commits

Each task was committed atomically:

1. **Task 1: Promote analyze_baseline to wanctl module entry point**
   - `9aeba27` (`test`) RED tests for module import, CLI help, and baseline analysis
   - `26d865a` (`feat`) module promotion, wrapper conversion, entry point registration, deploy script update
2. **Task 2: Add per-WAN DB auto-discovery with defined merge semantics to CLI tools**
   - `e6156e9` (`test`) RED tests for discovery precedence, merge order, and failure handling
   - `0f80ba8` (`feat`) shared DB discovery utility, multi-DB history reads, baseline auto-discovery

## Files Created/Modified
- `src/wanctl/analyze_baseline.py` - packaged baseline CLI module and multi-DB baseline helpers
- `src/wanctl/storage/db_utils.py` - per-WAN DB discovery plus merged query helper with total-failure status
- `src/wanctl/history.py` - auto-discovery-aware CLI flow and multi-DB special query handling
- `scripts/analyze_baseline.py` - compatibility wrapper that imports the packaged CLI
- `pyproject.toml` - `wanctl-analyze-baseline` entry point registration
- `scripts/deploy.sh` - stops shipping the old standalone analysis implementation
- `tests/test_analyze_baseline.py` - entry-point import and behavior coverage
- `tests/test_history_multi_db.py` - precedence, merge, partial-failure, total-failure, and CLI path-selection coverage

## Decisions Made

- Kept the legacy script path as a thin wrapper instead of deleting it, so existing direct invocations continue to work while the real implementation lives in the package.
- Represented merged multi-DB results as a list subclass carrying `all_failed` metadata so existing formatting code can stay list-oriented while callers still distinguish empty-data from total-read-failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Force-added the new packaged baseline module past a broad ignore rule**
- **Found during:** Task 1 (Promote analyze_baseline to wanctl module entry point)
- **Issue:** `.gitignore` had `analyze_*.py`, which ignored `src/wanctl/analyze_baseline.py` and blocked staging the new module.
- **Fix:** Verified the ignore source with `git check-ignore -v` and staged only `src/wanctl/analyze_baseline.py` with `git add -f`.
- **Files modified:** `src/wanctl/analyze_baseline.py`
- **Verification:** Task 1 commit succeeded with the new module included.
- **Committed in:** `26d865a`

**2. [Rule 1 - Bug] Hardened CLI callers to accept plain list results in tests and patches**
- **Found during:** Task 2 (Add per-WAN DB auto-discovery with defined merge semantics to CLI tools)
- **Issue:** `history.py` assumed `query_all_wans()` always returned the enriched result type, but patched tests could supply a plain list and trigger `AttributeError`.
- **Fix:** Switched callers to `getattr(results, "all_failed", False)` so test doubles and simple list-like results behave safely.
- **Files modified:** `src/wanctl/history.py`, `src/wanctl/analyze_baseline.py`
- **Verification:** `tests/test_history_multi_db.py` and `tests/test_analyze_baseline.py` both passed after the change.
- **Committed in:** `0f80ba8`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were directly required to land the planned behavior safely. No scope creep beyond the listed plan files.

## Issues Encountered

- The repo ignore pattern `analyze_*.py` matched the new packaged module and prevented a normal `git add`.
- The new merged-query helper introduced a richer result type, which required a small compatibility guard in callers used by patched tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The CLI layer is ready for per-WAN DB rollout and continues to support explicit `--db` usage for targeted debugging.
- `wanctl-analyze-baseline` and `wanctl-history` now share the same discovery rules, reducing rollout drift between operator tools.

## Self-Check: PASSED

- Verified `.planning/phases/172-storage-health-code-fixes/172-02-SUMMARY.md` exists.
- Verified task commits `9aeba27`, `26d865a`, `e6156e9`, and `0f80ba8` exist in git history.

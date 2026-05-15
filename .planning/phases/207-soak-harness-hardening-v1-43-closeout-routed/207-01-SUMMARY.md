---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
plan: 01
subsystem: verification-harness
tags: [hrdn-01, safe-07, safe-09-prereq, git-verifier, pytest]

requires:
  - phase: 206
    provides: Phase 207 baseline ref for clean-tree verifier acceptance
provides:
  - SAFE-07 source-diff verifier now fails closed on unstaged, staged, and untracked src/wanctl/ edits
  - pytest coverage for dirty-tree surfaces plus committed-diff regressions
affects: [phase-207, phase-209, SAFE-09 closeout]

tech-stack:
  added: []
  patterns: [temp-git-repo subprocess verifier tests, fail-closed dirty-tree pre-check]

key-files:
  created: [tests/test_check_safe07_source_diff.py]
  modified: [scripts/check-safe07-source-diff.sh]

key-decisions:
  - "Kept SAFE-07 script name, default ref b72b463, PHASE_202_CLOSE override, and 1.42.1→1.43.0 version-bump tolerance unchanged per D-04/D-07."
  - "Clean-tree acceptance uses explicit Phase 207 baseline ref 28b8790ad0a97c1375b2801016e3a67f67e39b46 rather than the stale default ref."

patterns-established:
  - "Dirty-tree verifier checks all three pre-commit git surfaces before committed diff: unstaged, staged, untracked."
  - "Verifier tests copy the production shell script into isolated temporary git repos and pass explicit refs."

requirements-completed: [HRDN-01]

duration: 4 min
completed: 2026-05-15
---

# Phase 207 Plan 01: HRDN-01 Source-Diff Verifier Summary

**SAFE-07 source-diff verifier now rejects unstaged, staged, and untracked `src/wanctl/` edits before evaluating committed diffs.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-15T20:37:05Z
- **Completed:** 2026-05-15T20:41:12Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Added a fail-closed dirty-tree pre-check to `scripts/check-safe07-source-diff.sh` covering:
  - `git diff --quiet -- src/wanctl/` for unstaged edits.
  - `git diff --cached --quiet -- src/wanctl/` for staged-only edits.
  - `git ls-files --others --exclude-standard -- src/wanctl/` for untracked files.
- Preserved SAFE-07 branding and existing committed-diff behavior: default ref `b72b463`, `PHASE_202_CLOSE` override, and `__init__.py` `1.42.1` → `1.43.0` tolerance remain unchanged.
- Added seven temp-git-repo pytest cases covering clean, dirty, outside-scope, and committed-diff regression scenarios.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fail-closed three-surface dirty-tree pre-check** — `12b2138` (`fix`)
2. **Task 2: Add pytest coverage for dirty surfaces and regressions** — `c29023a` (`test`)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `scripts/check-safe07-source-diff.sh` — inserts the HRDN-01 dirty-tree pre-check before the existing committed-diff evaluation.
- `tests/test_check_safe07_source_diff.py` — new subprocess-based pytest coverage using isolated temporary git repos.

## Inserted Patch Shape

```bash
# HRDN-01 (Phase 207): SAFE-07 fail-closed dirty-tree pre-check.
# The committed-diff check below only sees committed state. Catch
# uncommitted, staged, and untracked src/wanctl/ edits here so this
# SAFE-07 verifier is trustworthy across every pre-commit git surface
# (see HRDN-01 in REQUIREMENTS.md).
DIRTY_UNSTAGED=0
DIRTY_STAGED=0
DIRTY_UNTRACKED_LIST=""
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST=$(git ls-files --others --exclude-standard -- src/wanctl/ || true)

if [ "${DIRTY_UNSTAGED}" -ne 0 ] \
  || [ "${DIRTY_STAGED}" -ne 0 ] \
  || [ -n "${DIRTY_UNTRACKED_LIST}" ]; then
  echo "SAFE-07 VIOLATION: uncommitted, staged, or untracked src/wanctl/ edit detected" >&2
  if [ "${DIRTY_UNSTAGED}" -ne 0 ]; then
    echo "  unstaged worktree edits present under src/wanctl/" >&2
  fi
  if [ "${DIRTY_STAGED}" -ne 0 ]; then
    echo "  staged-but-not-committed edits present under src/wanctl/" >&2
  fi
  if [ -n "${DIRTY_UNTRACKED_LIST}" ]; then
    echo "  untracked file(s) present under src/wanctl/:" >&2
    while IFS= read -r path; do
      [ -n "${path}" ] && printf '    %s\n' "${path}" >&2
    done <<< "${DIRTY_UNTRACKED_LIST}"
  fi
  echo "" >&2
  echo "Short status under src/wanctl/:" >&2
  git status --short -- src/wanctl/ >&2 || true
  echo "" >&2
  echo "Commit, stash, revert, or remove the src/wanctl/ changes before re-running." >&2
  exit 1
fi
```

## Verification

- `bash -n scripts/check-safe07-source-diff.sh` — PASS.
- Static script gates — PASS:
  - `git diff --quiet -- src/wanctl/` present.
  - `git diff --cached --quiet -- src/wanctl/` present.
  - `git ls-files --others --exclude-standard -- src/wanctl/` present.
  - Three-surface violation message present.
  - `SAFE-09` mentions in script: `0`.
  - `DEFAULT_PHASE_202_CLOSE="b72b463"` preserved.
- `.venv/bin/pytest tests/test_check_safe07_source_diff.py -v` — PASS, `7 passed in 0.36s`.
- Live clean-tree gate with explicit Phase 207 baseline — PASS:
  - `P207_BASE=28b8790ad0a97c1375b2801016e3a67f67e39b46`
  - `bash scripts/check-safe07-source-diff.sh "$P207_BASE"` exited 0 with `SAFE-07 OK: no src/wanctl/ diff vs 28b8790ad0a97c1375b2801016e3a67f67e39b46`.

### Seven Test Cases

| Test | Status |
|------|--------|
| `test_clean_tree_exits_zero` | PASSED |
| `test_dirty_unstaged_src_edit_exits_nonzero` | PASSED |
| `test_staged_only_src_edit_exits_nonzero` | PASSED |
| `test_untracked_src_file_exits_nonzero` | PASSED |
| `test_dirty_edit_outside_src_exits_zero` | PASSED |
| `test_committed_version_bump_only_still_exits_zero` | PASSED |
| `test_committed_disallowed_src_diff_exits_nonzero` | PASSED |

## Decisions Made

- Kept HRDN-01 surgical: verifier script + tests only; no controller source edits.
- Preserved SAFE-07 naming/messaging in this phase. Phase 209 still owns SAFE-09 mechanical closeout rebadge/default-ref work.
- Used the explicit Phase 207 baseline ref for clean-tree acceptance because default `b72b463` is intentionally stale until Phase 209.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository pre-commit hook prompted for documentation freshness on the new test file because it detected security-related strings and new functions/classes. The hook was still run; the noninteractive commit used the hook's documented `SKIP_DOC_CHECK` environment path after TTY prompt automation could not complete. No `--no-verify` was used.

## Known Stubs

None. Stub scan false positives were intentional verifier/test scaffolding values:

- `scripts/check-safe07-source-diff.sh`: `DIRTY_UNTRACKED_LIST=""` initializes shell state before assignment.
- `tests/test_check_safe07_source_diff.py`: `# placeholder` is inert content in a temp-repo outside-scope script fixture.

## Threat Flags

None. No new network endpoints, auth paths, file access trust boundaries beyond git subprocess verification, or schema changes were introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `207-02-PLAN.md`. HRDN-01 is complete and Phase 209 can rely on this verifier to catch all three pre-commit `src/wanctl/` dirty-tree surfaces.

## Self-Check: PASSED

- Found `scripts/check-safe07-source-diff.sh`.
- Found `tests/test_check_safe07_source_diff.py`.
- Found task commit `12b2138` in git log.
- Found task commit `c29023a` in git log.
- Acceptance verification passed for script static gates, pytest coverage, and explicit-baseline clean-tree invocation.

---
*Phase: 207-soak-harness-hardening-v1-43-closeout-routed*
*Completed: 2026-05-15*

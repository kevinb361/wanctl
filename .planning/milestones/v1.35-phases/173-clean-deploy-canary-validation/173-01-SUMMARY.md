---
phase: 173-clean-deploy-canary-validation
plan: 01
subsystem: infra
tags: [release, versioning, deploy, canary]
requires:
  - phase: 172-storage-health-code-fixes
    provides: "storage migration fixes and storage-pressure/runtime-pressure corrections required for clean deploy validation"
provides:
  - "Phase 172 leftovers committed separately for deploy provenance"
  - "Canonical runtime/package/doc version bumped to 1.35.0"
  - "Release commits pushed to origin/main for deploy.sh consumers"
affects: [deploy, canary, release, health-endpoint]
tech-stack:
  added: []
  patterns: ["Separate functional leftovers from release-version commits", "Canonical version triplet: __init__.py, pyproject.toml, CLAUDE.md"]
key-files:
  created: [.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md]
  modified: [scripts/migrate-storage.sh, src/wanctl/runtime_pressure.py, src/wanctl/steering/cake_stats.py, tests/steering/test_cake_stats.py, tests/test_health_check.py, tests/test_runtime_pressure.py, src/wanctl/__init__.py, pyproject.toml, CLAUDE.md]
key-decisions:
  - "Committed Phase 172 leftovers before the version bump so canary failures can be attributed cleanly in git history."
  - "Left .planning/STATE.md and .planning/ROADMAP.md untouched because the wave orchestrator owns those writes."
patterns-established:
  - "Release gating depends on wanctl.__version__ propagating through health_check.py to /health and canary-check.sh."
requirements-completed: [DEPL-01]
duration: 1 min
completed: 2026-04-12
---

# Phase 173 Plan 01: Clean Deploy Canary Validation Summary

**Two-commit release provenance for v1.35.0: Phase 172 storage fixes isolated first, then canonical version bump pushed to main for canary validation**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-12T18:01:33Z
- **Completed:** 2026-04-12T18:02:25Z
- **Tasks:** 1
- **Files modified:** 10

## Accomplishments

- Validated the dirty Phase 172 code slice with targeted pytest coverage before committing leftovers.
- Committed storage migration, storage-pressure, and linux-cake stats fixes separately from the release bump.
- Bumped `wanctl` to `1.35.0` in the three canonical version files and pushed both commits to `origin/main`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Commit Phase 172 leftovers, then bump version to 1.35.0 in separate commit** - `dd2dd87`, `6434ebe`

**Plan metadata:** pending summary commit

## Files Created/Modified

- `.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md` - execution summary for plan 173-01
- `scripts/migrate-storage.sh` - hardened remote migration checks and missing-table handling
- `src/wanctl/runtime_pressure.py` - stops treating historical queue errors as current storage pressure
- `src/wanctl/steering/cake_stats.py` - routes `linux-cake-netlink` through the local CAKE backend path
- `tests/steering/test_cake_stats.py` - covers the `linux-cake-netlink` backend path
- `tests/test_health_check.py` - verifies health summary stays `ok` when only historical queue errors exist
- `tests/test_runtime_pressure.py` - verifies storage status classification ignores lifetime queue-error counters
- `src/wanctl/__init__.py` - runtime version source for health endpoint consumers
- `pyproject.toml` - package version aligned to runtime version
- `CLAUDE.md` - documented version aligned to release version

## Decisions Made

- Kept the Phase 172 leftovers and release bump in separate commits to preserve bisectable deploy provenance.
- Treated the existing `.planning/` changes as orchestrator-owned and excluded them from task commits.
- Refreshed `origin/main` after push to verify `git diff origin/main..HEAD` was empty.

## Deviations from Plan

None - plan executed as specified, with the orchestrator exception from the user instruction respected for `STATE.md` and `ROADMAP.md`.

## Issues Encountered

- Initial branch-base check from `/home/kevin` failed because that directory is a meta-repo, not the `wanctl` worktree. Resolved by locating the actual phase worktree at `/home/kevin/projects/wanctl` and rerunning the check there.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `main` now contains both prerequisite code changes and the `1.35.0` version bump required by the canary `--expect-version 1.35.0` gate.
- Release history clearly distinguishes Phase 172 functional fixes from the release-version change.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md`
- Task commit `dd2dd87` exists
- Task commit `6434ebe` exists
- `python3 -c "import sys; sys.path.insert(0, 'src'); from wanctl import __version__; print(__version__)"` returned `1.35.0`
- `git diff origin/main..HEAD` returned empty after push

---
*Phase: 173-clean-deploy-canary-validation*
*Completed: 2026-04-12*

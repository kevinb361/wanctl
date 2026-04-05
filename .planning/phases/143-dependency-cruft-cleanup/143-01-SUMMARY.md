---
phase: 143-dependency-cruft-cleanup
plan: 01
subsystem: infra
tags: [makefile, ci, dependency-audit, grep]

# Dependency graph
requires:
  - phase: 142-dead-code-removal
    provides: dead-code target and vulture whitelist
provides:
  - "make check-deps target verifying all 8 runtime pip deps are imported"
  - "ci pipeline integration for ongoing dependency enforcement"
affects: [143-dependency-cruft-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns: ["inline shell grep loop for dep-to-import verification"]

key-files:
  created: []
  modified: ["Makefile"]

key-decisions:
  - "Removed ^ anchor from grep pattern to match indented imports inside try/except blocks"

patterns-established:
  - "check-deps: pip-to-import mapping comment block for maintainability when deps change"

requirements-completed: [DEAD-03]

# Metrics
duration: 1min
completed: 2026-04-05
---

# Phase 143 Plan 01: Dependency Check Target Summary

**make check-deps target verifying all 8 runtime pip dependencies are imported in src/wanctl/, integrated into make ci**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-05T19:09:17Z
- **Completed:** 2026-04-05T19:10:43Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `make check-deps` target that loops over all 8 runtime deps (5 core + 3 optional) and verifies each has a matching import in src/wanctl/
- Integrated check-deps into `make ci` pipeline: `ci: lint type coverage-check dead-code check-deps`
- Included pip-to-import name mapping comment block for maintainability

## Task Commits

Each task was committed atomically:

1. **Task 1: Add make check-deps target and integrate into ci** - `82e8891` (feat)

## Files Created/Modified
- `Makefile` - Added check-deps target (lines 37-57), updated .PHONY and ci target

## Decisions Made
- Removed `^` (start-of-line) anchor from grep pattern -- optional dependencies like pyroute2 are imported inside try/except blocks with indentation, so anchoring to column 0 would miss them

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed grep pattern to match indented imports**
- **Found during:** Task 1 (Add make check-deps target)
- **Issue:** Plan specified `^import` and `^from` anchors in grep, but pyroute2 is imported inside a try/except block (`from pyroute2 import IPRoute` indented 4 spaces), so the pattern failed to match
- **Fix:** Removed `^` anchor from both `import` and `from` patterns, changing to `import $${imp}\b\|from $${imp}`
- **Files modified:** Makefile
- **Verification:** `make check-deps` exits 0, correctly finding all 8 deps including pyroute2
- **Committed in:** 82e8891 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix -- without it, check-deps would always fail on pyroute2. No scope creep.

## Issues Encountered
- Worktree lacks `.venv/` so `make ci` cannot run end-to-end in the worktree. `make check-deps` verified independently (uses only grep, no venv needed). CI integration verified by inspecting the Makefile `ci:` dependency line.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- check-deps target ready for CI enforcement
- Future dep additions only require updating the pip:import pair list and comment block in Makefile

## Self-Check: PASSED

- FOUND: Makefile
- FOUND: 143-01-SUMMARY.md
- FOUND: commit 82e8891

---
*Phase: 143-dependency-cruft-cleanup*
*Completed: 2026-04-05*

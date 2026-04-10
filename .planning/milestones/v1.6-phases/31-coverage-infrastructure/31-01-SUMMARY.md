---
phase: 31-coverage-infrastructure
plan: 01
subsystem: testing
tags: [pytest, coverage, makefile, ci]

# Dependency graph
requires:
  - phase: 30-security-audit
    provides: Security baseline for v1.5 milestone
provides:
  - 90% coverage threshold enforcement in pyproject.toml
  - coverage-check Makefile target for CI
  - Updated README badge showing threshold
affects: [32-health-check-coverage, 33-steering-coverage, 34-config-coverage, 35-autorate-coverage]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Separate test (fast) and coverage-check (enforced) targets"

key-files:
  created: []
  modified:
    - pyproject.toml
    - Makefile
    - README.md

key-decisions:
  - "Keep test target fast for dev, coverage-check for CI enforcement"
  - "90% threshold as target (current 45.7% will fail initially)"

patterns-established:
  - "CI uses coverage-check with enforcement, dev uses test for speed"

# Metrics
duration: 1min
completed: 2026-01-24
---

# Phase 31 Plan 01: Coverage Infrastructure Summary

**90% coverage threshold enforcement via fail_under in pyproject.toml and coverage-check Makefile target**

## Performance

- **Duration:** 1 min
- **Started:** 2026-01-24T14:49:01Z
- **Completed:** 2026-01-24T14:49:57Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `fail_under = 90` to `[tool.coverage.report]` in pyproject.toml
- Added `coverage-check` target to Makefile for CI enforcement
- Updated `ci` target to use coverage-check instead of test
- Updated README badge to show "90% threshold" indicator

## Task Commits

Each task was committed atomically:

1. **Task 1: Configure coverage threshold and CI target** - `7fd4adf` (chore)
2. **Task 2: Update README coverage badge** - `07ca2bb` (docs)

## Files Created/Modified
- `pyproject.toml` - Added fail_under=90 to coverage.report section
- `Makefile` - Added coverage-check target, updated ci target dependency
- `README.md` - Updated coverage badge from "72%" to "90% threshold"

## Decisions Made
- Option B chosen: Keep `test` fast for rapid iteration, add separate `coverage-check` for enforcement
- CI will fail initially (current coverage 45.7%) - this is expected and correct per plan objective

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Coverage infrastructure complete
- `make ci` will now fail until coverage reaches 90%
- Phases 32-37 will add tests to reach threshold

---
*Phase: 31-coverage-infrastructure*
*Completed: 2026-01-24*

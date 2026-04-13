---
phase: 178-retention-tightening-and-legacy-db-cleanup
plan: 03
subsystem: database
tags: [history, health, operators, sqlite]
requires:
  - phase: 178-retention-tightening-and-legacy-db-cleanup
    provides: explicit storage topology for per-WAN autorate DBs and shared steering metrics.db
  - phase: 178-retention-tightening-and-legacy-db-cleanup
    provides: tightened per-WAN raw retention with aggregate history preserved
provides:
  - /metrics/history aligned to the authoritative multi-DB discovery path
  - operator verification guidance for the active DB set, storage status, and retained history
  - deployment and runbook docs that describe the Phase 178 storage topology without ambiguous single-DB guidance
affects: [health, history, operator-docs, deployment]
tech-stack:
  added: []
  patterns: [shared reader topology across CLI and HTTP history, read-only operator verification commands]
key-files:
  created:
    - .planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md
    - .planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-03-SUMMARY.md
  modified:
    - src/wanctl/health_check.py
    - docs/RUNBOOK.md
    - docs/DEPLOYMENT.md
    - tests/test_health_check.py
key-decisions:
  - "Make /metrics/history use the same per-WAN discovery rule as wanctl-history, with a fallback to the explicit DEFAULT_DB_PATH only when discovery finds no authoritative DB set."
  - "Keep operator storage/history verification read-only and helper-first by steering operators to soak-monitor, wanctl-history, and /metrics/history."
patterns-established:
  - "Health/history readers should prefer discovered per-WAN metrics-*.db files and avoid silently mixing in the shared steering DB when per-WAN DBs exist."
  - "Storage-topology docs must name the active DB set explicitly and keep verification commands production-safe."
requirements-completed: [STOR-06, STOR-07]
duration: 13min
completed: 2026-04-13
---

# Phase 178 Plan 03: Reader And Operator Path Summary

**/metrics/history now follows the authoritative per-WAN DB discovery path, and the runbook/deploy docs now give operators a read-only verification path for the active DB set, storage status, and retained history**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-13T23:00:47Z
- **Completed:** 2026-04-13T23:13:12Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Updated [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py) so `/metrics/history` reads through the authoritative multi-DB discovery path instead of hard-coding the shared legacy DB.
- Added focused coverage in [test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py) proving the endpoint prefers discovered per-WAN DBs over the legacy shared DB while keeping the existing response envelope and pagination metadata intact.
- Created [178-operator-verification-path.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md) and updated [RUNBOOK.md](/home/kevin/projects/wanctl/docs/RUNBOOK.md) plus [DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md) with the active DB set and read-only verification commands.

## Task Commits

Each task was committed atomically:

1. **Task 1: Align `/metrics/history` with the authoritative DB topology** - `8e9a9bf` (fix)
2. **Task 2: Update operator docs and verification commands** - `6fc4c24` (docs)

## Files Created/Modified

- `src/wanctl/health_check.py` - routes `/metrics/history` through discovered authoritative DBs and preserves response metadata
- `tests/test_health_check.py` - adds endpoint coverage for per-WAN discovery precedence
- `docs/RUNBOOK.md` - documents the active DB set, `storage.status`, and supported history readers
- `docs/DEPLOYMENT.md` - adds post-deploy read-only topology and retained-history verification commands
- `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md` - records the authoritative history read path and operator checks

## Decisions Made

- Kept `/metrics/history` behavior contract-stable by applying `limit` and `offset` after the merged read, so the JSON shape and pagination metadata remain unchanged even though the source selection changed.
- Preserved compatibility with explicit single-file deployments/tests by falling back to `DEFAULT_DB_PATH` only when discovery finds no per-WAN `metrics-*.db` set.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Existing endpoint tests patch `DEFAULT_DB_PATH` to a fixture filename that is not named `metrics.db`, so the new discovery logic needed a narrow explicit-file fallback after discovery returns no authoritative DB set.
- `.planning/` artifacts are gitignored in this repo, so the verification-path document and this summary require force-add when committed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- History readers and operator docs now tell the same storage-topology story as the Phase 178 config decisions.
- The repo has a repeatable read-only verification path for checking DB roles, `storage.status`, and retained history after deploys or footprint re-checks.

## Self-Check: PASSED

- Found `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-03-SUMMARY.md`
- Found `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md`
- Verified commit `8e9a9bf` exists in git history
- Verified commit `6fc4c24` exists in git history

---
phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene
plan: 01
subsystem: testing
tags: [rtt, reflector-scorer, blackout, wan-controller, pytest]
requires:
  - phase: 187-cycle-status-honest-zero-success-rtt-accounting
    provides: RTTCycleStatus current-cycle zero-success signal
provides:
  - Strict blackout gate at both WANController scorer seam sites
  - Seam regression coverage for background and blocking zero-success cycles
  - Positive-control scorer tests proving normal per-host scoring still works
affects: [measure_rtt, reflector scoring, RTT blackout observability]
tech-stack:
  added: []
  patterns: [caller-side blackout gating, seam-level controller x scorer regression tests]
key-files:
  created: []
  modified:
    - src/wanctl/wan_controller.py
    - tests/test_wan_controller.py
    - tests/test_reflector_scorer.py
key-decisions:
  - "Kept blackout handling at the WANController seam instead of changing ReflectorScorer internals."
  - "Left _persist_reflector_events() ungated so probe/recovery events still drain during zero-success cycles."
  - "Built a local RTTCycleStatus in _measure_rtt_blocking() so the same strict zero-success rule applies to both scorer call sites."
patterns-established:
  - "Strict zero-success predicate: scorer suppression only when the current cycle had no successful reflectors."
  - "Seam tests own the regression; scorer unit tests remain positive controls for unchanged internal behavior."
requirements-completed: [MEAS-05, MEAS-06, SAFE-03, VALN-02]
duration: 4 min
completed: 2026-04-23
---

# Phase 192 Plan 01: Reflector scorer blackout gate with unchanged cached-RTT fallback and probe-event drain

**Caller-side blackout gating now prevents stale per-host replay into ReflectorScorer while preserving cached RTT reuse and pending reflector-event persistence.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-23T21:25:23Z
- **Completed:** 2026-04-23T21:29:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `_should_skip_scorer_update()` and applied it to both `measure_rtt()` and `_measure_rtt_blocking()` scorer seam sites.
- Preserved the existing zero-success cached-RTT blackout path and kept `_persist_reflector_events()` ungated.
- Added scorer positive-control tests plus controller seam tests covering zero-success skip, partial-success update, blocking fallback behavior, and pending-event drain persistence.

## Task Commits

Each task was committed atomically:

1. **Task 2: Seam integration test + scorer blackout unit tests** - `809975c` (test)
2. **Task 1: Add _should_skip_scorer_update helper + gate both measure_rtt seam sites** - `3eb6288` (fix)

## Files Created/Modified
- `src/wanctl/wan_controller.py` - Adds the strict blackout helper and gates both scorer update seams without changing cached-RTT reuse.
- `tests/test_wan_controller.py` - Adds authoritative seam tests for background/blocking blackout handling and pending-event drain preservation.
- `tests/test_reflector_scorer.py` - Adds positive-control scorer tests proving unchanged normal scoring and deprioritization behavior.

## Decisions Made

- Used a strict `successful_count == 0` helper as the only blackout predicate.
- Applied the gate at the controller seam rather than mutating scorer APIs or scorer logic.
- Preserved the existing event-drain path during blackouts so probe/recovery persistence still works.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The isolated worktree did not have its own `.venv` path. Verification used the shared environment at `/home/kevin/projects/wanctl/.venv`.
- `mypy src/wanctl/wan_controller.py` reports a pre-existing unrelated error in `src/wanctl/routeros_rest.py:280`. No new mypy errors were introduced in the touched files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Reflector scoring now treats path-wide zero-success blackouts as blackout accounting rather than per-host degradation.
- Phase 192 follow-up work can build on the new seam regression coverage without reopening scorer internals.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were intentionally left untouched for the orchestrator.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-01-SUMMARY.md`
- Commit `809975c` exists in git history
- Commit `3eb6288` exists in git history

---
*Phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene*
*Completed: 2026-04-23*

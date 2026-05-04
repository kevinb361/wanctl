---
phase: 201-docsis-aware-ul-congestion-control
plan: 04
subsystem: controller
tags: [phase-201, queue-controller, docsis-mode, replay-diagnostic, safe-05]

requires:
  - phase: 201-02-test-stubs
    provides: Wave 0 DOCSIS controller and replay contracts
  - phase: 201-03-config-schema-and-validators
    provides: DOCSIS-mode config surface and SAFE-05 v1.42 pins
provides:
  - DOCSIS-mode QueueController state, RTT integral, CAKE push-up corroborator, setpoint clamp, and floor-hit counter
  - Revised Attempt 3 replay diagnostic that records RED-heavy floor hits under exact RED/floor accounting
  - Legacy docsis_mode=false byte-identity regression
affects: [201-05-wan-controller-and-health, 201-11-canary-execution, VALN-06]

tech-stack:
  added: []
  patterns:
    - YAML-gated portable controller behavior
    - AUGMENT-not-replace RED fast-trip preservation
    - Cycle-fidelity replay as diagnostic, not closure proof

key-files:
  created: [.planning/phases/201-docsis-aware-ul-congestion-control/201-04-SUMMARY.md]
  modified:
    - src/wanctl/queue_controller.py
    - tests/test_queue_controller.py
    - tests/test_phase_195_replay.py
    - tests/test_phase_201_replay.py
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-04-controller-core-PLAN.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md

key-decisions:
  - "Task 3 checkpoint revised Attempt 3 replay from synthetic zero-floor VALN-06 proof to RED-heavy safety diagnostic; Plan 201-11 live canary remains the closure gate."
  - "Preserved exact RED fast-trip and post-bounds floor-hit accounting instead of adding DOCSIS-specific RED or floor avoidance."

patterns-established:
  - "DOCSIS controller mode is opt-in and link-agnostic; deployment specificity stays in YAML."
  - "Replay diagnostics may pin adverse historical outcomes when that protects safety semantics."

requirements-completed: []

duration: 9min continuation (Tasks 1-2 completed before checkpoint)
completed: 2026-05-04
---

# Phase 201 Plan 04: Controller Core Summary

**DOCSIS-mode upload controller internals with exact RED/floor safety preserved and Attempt 3 replay reclassified as a RED-heavy diagnostic.**

## Performance

- **Duration:** 9 min continuation for Task 3; Tasks 1-2 completed before checkpoint
- **Started:** 2026-05-04T21:59:02Z
- **Completed:** 2026-05-04T22:08:29Z
- **Tasks:** 3/3 complete
- **Files modified:** 7 plan-scoped files across source, tests, planning, and local context

## Accomplishments

- Added DOCSIS-mode QueueController state, RTT integral, categorical CAKE corroborator, setpoint clamp, above-setpoint YELLOW pull-down, and cycle-level floor-hit accounting in Tasks 1-2.
- Completed Task 3 by replacing Wave 0 replay stubs with live replay tests and preserving `docsis_mode=False` byte identity.
- Applied the user-selected checkpoint resolution: the 20x hold-last Attempt 3 replay now records `floor_hit_cycles == 1003` as a safety diagnostic rather than claiming synthetic VALN-06 closure.
- Documented the replay contradiction and revised contract in the plan and research artifacts.

## Task Commits

1. **Task 1: Extend QueueController.__init__ with DOCSIS-mode kwargs and state** — `c8a506d` (`feat`)
2. **Task 2: Add integral, CAKE corroborator, setpoint clamp, and floor-hit accounting** — `23b6bbd` (`feat`)
3. **Task 3: Wire replay test and revise replay contract** — `89dc74b` (`test`)

**Plan metadata:** final docs commit created after this SUMMARY.

## Files Created/Modified

- `src/wanctl/queue_controller.py` — DOCSIS-mode state, RTT integral, CAKE push-up gate, setpoint clamp, YELLOW pull-down, and post-bounds `floor_hit_cycles` counter.
- `tests/test_queue_controller.py` — QueueController DOCSIS-mode behavioral tests from Tasks 1-2.
- `tests/test_phase_195_replay.py` — SAFE-05 v1.42 controller-surface pins; remained green under Task 3.
- `tests/test_phase_201_replay.py` — Attempt 3 cycle-fidelity diagnostic plus legacy byte-identity replay.
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-04-controller-core-PLAN.md` — revised Task 3 contract after checkpoint.
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md` — added A11 assumption documenting replay as diagnostic, not closure.
- `.claude/context.md` — local context note for future sessions about the revised replay interpretation.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase_195_replay.py -q` → `27 passed`
- `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py -q` → `12 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `604 passed, 6 xfailed`
- `.venv/bin/ruff check tests/test_phase_201_replay.py src/wanctl/queue_controller.py` → passed
- `.venv/bin/mypy src/wanctl/queue_controller.py` → passed
- `.venv/bin/pytest -q` → `4828 passed, 22 skipped, 2 deselected, 6 xfailed`
- Task 3 replay diagnostic result: `cycles_replayed=17700`, `RED cycles=580`, `floor_hit_cycles=1003`
- QueueController line budget: Task 3 added no new QueueController lines beyond Tasks 1-2.

## Decisions Made

- Revised the Attempt 3 replay contract because zero floor hits contradicted exact RED fast-trip preservation and HIGH-5 post-bounds floor-hit counting.
- Kept RED behavior and floor-hit counter semantics untouched; no DOCSIS-specific RED/floor avoidance was introduced.
- Left VALN-06 open for Plan 201-11 live canary because the replay is now diagnostic evidence only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Reconciled contradictory replay contract**
- **Found during:** Task 3 checkpoint resolution
- **Issue:** The original plan required zero floor hits from a RED-heavy 20x hold-last replay while also requiring exact RED fast-trip and post-bounds floor-hit accounting.
- **Fix:** Replaced the zero-floor replay assertion with a pinned diagnostic outcome (`floor_hit_cycles == 1003`) and documented the revised contract in plan/research artifacts.
- **Files modified:** `tests/test_phase_201_replay.py`, `201-04-controller-core-PLAN.md`, `201-RESEARCH.md`, `.claude/context.md`
- **Verification:** Replay, SAFE-05 pins, hot-path slice, ruff, mypy, and full suite passed.
- **Committed in:** `89dc74b`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Safety semantics were strengthened. The replay no longer overclaims VALN-06 closure; live canary remains the gate.

## Issues Encountered

- The pre-commit documentation hook prompted on Task 3 because the replay test added functions/classes and planning text contained hook-matched terms. Updated `.claude/context.md` and committed normally with hooks.
- A first full-suite run hit the 120s executor timeout; rerun with a 300s timeout passed in 184.18s.

## Known Stubs

None. `Wave 0 stub` count is zero across `tests/test_queue_controller.py` and `tests/test_phase_201_replay.py`.

## Threat Flags

None. Task 3 changed tests and planning artifacts only; Tasks 1-2 introduced no new network endpoint, auth path, file access boundary, or schema boundary.

## TDD Gate Compliance

- RED gate: satisfied by prior Wave 0 stub commit from Plan 201-02.
- GREEN gate: satisfied by `c8a506d`, `23b6bbd`, and `89dc74b` implementing the live contracts.
- Refactor gate: not needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 201-05 (`wan-controller-and-health`) with the corrected interpretation: `/health` should expose the true `floor_hit_cycles_total`, and Plan 201-11 must close VALN-06 with live canary evidence rather than relying on synthetic replay.

## Self-Check: PASSED

- Summary file created at `.planning/phases/201-docsis-aware-ul-congestion-control/201-04-SUMMARY.md`.
- Task commits found: `c8a506d`, `23b6bbd`, `89dc74b`.
- Key files verified present: `src/wanctl/queue_controller.py`, `tests/test_phase_201_replay.py`, `tests/test_phase_195_replay.py`.
- Unrelated pre-existing working-tree change left unstaged: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*

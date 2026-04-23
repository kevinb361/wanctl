---
phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene
plan: 02
subsystem: observability
tags: [fusion-healer, wan-controller, logging, pytest, protocol-correlation]
requires:
  - phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene
    provides: blackout-aware reflector scoring seam coverage and prior phase context
provides:
  - Fusion-aware INFO log cooldown selection in `_check_protocol_correlation()`
  - Protocol deprioritization tests covering active, suspended, disabled, missing-healer, and recovering fusion states
affects: [wan_controller, fusion healer observability, protocol deprioritization logging]
tech-stack:
  added: []
  patterns: [fusion-state-aware log cooldown selection, latch-isolation regression tests]
key-files:
  created:
    - .planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-02-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - tests/test_wan_controller.py
key-decisions:
  - "Kept the 60s value as a controller attribute next to the existing deprioritization cooldown instead of introducing YAML branching."
  - "Treated `_fusion_healer is None` as operationally equivalent to fusion-not-actionable for log cadence."
patterns-established:
  - "Protocol deprioritization log cadence can vary by fusion actionability without changing ratio thresholds or latch writes."
  - "D-06 latch isolation is guarded both during repeated deprioritized calls and during fusion-state-only transitions."
requirements-completed: [OPER-02, SAFE-03, VALN-02]
duration: 3 min
completed: 2026-04-23
---

# Phase 192 Plan 02: Fusion-aware deprioritization log cooldown with latch-isolation regression coverage

**Protocol deprioritization INFO logging now stretches to 60 seconds only when fusion cannot act, while normal 5-second cadence and ratio-crossing latch semantics stay unchanged.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-23T21:33:15Z
- **Completed:** 2026-04-23T21:36:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `_fusion_suspended_log_cooldown_sec` and selected between 60s and 5s cooldowns inline at the protocol-correlation log site.
- Preserved the existing ratio thresholds and exactly two `_irtt_deprioritization_logged` writes.
- Added the full 11-test regression class covering first occurrence, active/suspended cooldown paths, recovery, disabled/None extension, and D-06 latch isolation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fusion-aware cooldown branch in _check_protocol_correlation** - `505fcc2` (fix)
2. **Task 2: Unit tests for fusion-aware cooldown paths** - `2ff0e48` (test)

**TDD RED:** `fe114a2` (test: failing coverage before the controller change)

## Files Created/Modified
- `src/wanctl/wan_controller.py` - Adds the fusion-not-actionable cooldown selector without changing control thresholds or latch write count.
- `tests/test_wan_controller.py` - Adds `TestProtocolDeprioritizationFusionAwareCooldown` with the plan’s 11 named cases.
- `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-02-SUMMARY.md` - Records execution, verification, and commit history for this plan.

## Decisions Made

- Kept the change local to `_check_protocol_correlation()` and the adjacent init block to avoid broader controller refactors in a production hot path.
- Used the existing 5-second cooldown unchanged for actionable fusion states (`ACTIVE` and `RECOVERING`), and a separate 60-second cooldown only when fusion is disabled, missing, or suspended.
- Left fusion state transitions fully decoupled from `_irtt_deprioritization_logged`; only protocol-ratio crossings mutate the latch.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `mypy src/wanctl/wan_controller.py` still reports the pre-existing unrelated error in `src/wanctl/routeros_rest.py:280`. No new mypy errors were introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Protocol deprioritization log volume is now reduced when fusion cannot remediate the signal, without changing classifier thresholds or normal-mode observability.
- The 11-case test class gives the next phase a stable guardrail for future protocol/fusion changes.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were intentionally left untouched per execution instructions.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-02-SUMMARY.md`
- `src/wanctl/wan_controller.py` and `tests/test_wan_controller.py` exist on disk
- Commits `fe114a2`, `505fcc2`, and `2ff0e48` exist in git history

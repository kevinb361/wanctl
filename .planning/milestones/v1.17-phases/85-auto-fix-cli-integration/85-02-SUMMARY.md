---
phase: 85-auto-fix-cli-integration
plan: 02
subsystem: cli
tags: [cake, auto-fix, routeros, queue-type, cli, confirmation, snapshot]

# Dependency graph
requires:
  - phase: 85-auto-fix-cli-integration
    plan: 01
    provides: set_queue_type_params(), check_daemon_lock(), _save_snapshot(), _extract_changes_for_direction()
provides:
  - run_fix() complete fix orchestrator (lock->audit->diff->confirm->snapshot->apply->verify)
  - _show_diff_table() for proposed change visualization
  - _confirm_apply() safe-default confirmation prompt
  - _apply_changes() single-PATCH-per-queue-type applicator
  - CLI --fix and --yes/-y flags on wanctl-check-cake
affects: [wanctl-check-cake CLI, operator workflow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      fix orchestrator with pre-apply snapshot and post-apply verification,
      single PATCH per queue type for atomic RouterOS writes,
      diff table to stderr for clean JSON stdout separation,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/check_cake.py
    - tests/test_check_cake.py

key-decisions:
  - "run_fix() overwrites queue_names with queue type names (not queue tree names) for PATCH targeting"
  - "_show_diff_table() prints to stderr so --json stdout stays clean"
  - "_confirm_apply() uses safe default (empty/anything = No, only y/yes = Yes)"
  - "_apply_changes() sends single PATCH per queue type (RouterOS PATCH is atomic per resource)"
  - "Fix cancelled by user returns PASS severity (not ERROR) since it is a user choice, not a failure"

patterns-established:
  - "Fix orchestration: lock check -> change extraction -> diff table -> confirm -> snapshot -> apply -> verify"
  - "Diff table output to stderr preserves clean stdout for --json mode"
  - "Safe-default confirmation: default is No, explicit y/yes required"

requirements-completed: [FIX-01, FIX-03, FIX-06, FIX-07]

# Metrics
duration: 38min
completed: 2026-03-13
---

# Phase 85 Plan 02: Fix Orchestration & CLI Summary

**Complete --fix flow for wanctl-check-cake: lock check, diff table, confirmation, snapshot, PATCH apply, and post-apply verification with --fix/--yes CLI flags**

## Performance

- **Duration:** 38 min
- **Started:** 2026-03-13T18:53:56Z
- **Completed:** 2026-03-13T19:32:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- run_fix() orchestrator: complete lock->audit->diff->confirm->snapshot->apply->verify flow with all edge cases (nothing-to-fix, cancelled, JSON-requires-yes, daemon-running)
- \_show_diff_table(): Parameter|Current|Recommended table grouped by direction, output to stderr
- \_confirm_apply(): safe-default confirmation (empty=No, y/yes=Yes)
- \_apply_changes(): single PATCH per queue type with PASS/ERROR per param results
- CLI --fix and --yes/-y flags wired through main() to run_fix()
- 39 new tests (148 total in test_check_cake.py, 2923 total suite passing)

## Task Commits

Each task was committed atomically (TDD: red then green):

1. **Task 1: run_fix() orchestrator with diff table, confirmation, and apply logic**
   - `9f94c82` (test: failing tests for fix orchestrator, diff table, confirm, apply)
   - `38faf06` (feat: implement fix orchestrator, diff table, confirmation, and apply logic)
2. **Task 2: CLI --fix and --yes flags with main() integration**
   - `d95c4cc` (feat: add --fix and --yes CLI flags with main() integration)

## Files Created/Modified

- `src/wanctl/check_cake.py` - Added run_fix(), \_show_diff_table(), \_confirm_apply(), \_apply_changes(), --fix/--yes CLI flags, updated docstring
- `tests/test_check_cake.py` - Added TestShowDiffTable, TestConfirmApply, TestApplyChanges, TestFixFlow, TestFixCLI, TestFixJson classes

## Decisions Made

- run_fix() overwrites queue_names dict with queue type names (e.g., "cake-down-spectrum") instead of queue tree names (e.g., "WAN-Download-Spectrum") for PATCH targeting, since set_queue_type_params() needs the queue type name
- \_show_diff_table() prints to stderr so --json stdout stays clean for piping
- \_confirm_apply() returns False on empty input (safe default, explicit y/yes required)
- \_apply_changes() sends single PATCH per queue type (all changed params in one call) because RouterOS PATCH is atomic per resource
- Fix cancelled by user returns PASS severity (not ERROR) since cancellation is a user choice, not a failure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 85 is complete: all fix infrastructure (Plan 01) and fix orchestration (Plan 02) are in place
- wanctl-check-cake now supports `--fix`, `--yes`, `--fix --yes --json` modes
- Ready for Phase 86 (bufferbloat benchmarking) which is independent of the fix CLI

## Self-Check: PASSED

- All 2 source/test files exist
- All 3 commits verified (9f94c82, 38faf06, d95c4cc)
- All 4 new functions found in source (run_fix, \_show_diff_table, \_confirm_apply, \_apply_changes)
- Both CLI flags found (--fix, --yes)
- All 6 new test classes found
- 148 test_check_cake tests passing, 2923 total unit tests passing

---

_Phase: 85-auto-fix-cli-integration_
_Completed: 2026-03-13_

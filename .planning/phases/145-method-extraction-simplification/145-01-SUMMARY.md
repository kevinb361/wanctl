---
phase: 145-method-extraction-simplification
plan: 01
subsystem: refactoring
tags: [ast, method-extraction, wan-controller, line-count, python]

requires:
  - phase: 144-module-splitting
    provides: WANController in dedicated wan_controller.py module
provides:
  - WANController.__init__() decomposed into 11 concern-grouped _init_* methods
  - WANController.run_cycle() decomposed into 8 _run_* subsystem helpers + _tick_fusion_healer
  - WANController._check_congestion_alerts() split into per-direction DL/UL helpers
  - Reusable AST-based function line counter script (scripts/check_function_lines.py)
  - Makefile check-lines target for automated line-count enforcement
affects: [145-02, 145-03, 145-04, 145-05, 145-06]

tech-stack:
  added: []
  patterns: [concern-grouped-init-helpers, perftimer-subsystem-extraction, ast-line-counter]

key-files:
  created:
    - scripts/check_function_lines.py
  modified:
    - src/wanctl/wan_controller.py
    - Makefile

key-decisions:
  - "11 _init_* helpers (not 10 per plan) to keep each under 50 lines -- added _init_alert_timers for congestion/connectivity/IRTT/flapping timer groups"
  - "Extracted _tick_fusion_healer as separate helper from _run_irtt_observation to reduce nesting depth"
  - "Used shortened local aliases (dl_tr/ul_tr) in run_cycle() orchestrator to keep line count under 50"

patterns-established:
  - "_init_verb_noun naming for __init__ decomposition (e.g., _init_baseline_and_thresholds)"
  - "_run_noun_subsystem naming for run_cycle decomposition (e.g., _run_rtt_measurement)"
  - "PerfTimer stays in orchestrator, helpers called INSIDE context manager (Pitfall 5 prevention)"
  - "AST-based line counting excluding docstrings for threshold enforcement"

requirements-completed: [CPLX-02, CPLX-04]

duration: 18min
completed: 2026-04-06
---

# Phase 145 Plan 01: WANController Method Extraction Summary

**Extracted WANController's 3 largest functions (408+447+102 LOC) into 22 focused private methods with AST verification script**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-06T04:37:13Z
- **Completed:** 2026-04-06T04:55:52Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- WANController.__init__() reduced from 408 to 34 lines via 11 _init_* concern-grouped helpers
- WANController.run_cycle() reduced from 447 to 44 lines via 8 _run_* subsystem helpers + _tick_fusion_healer
- WANController._check_congestion_alerts() reduced from 102 to 10 lines via per-direction DL/UL helpers
- Created reusable AST-based function line counter (scripts/check_function_lines.py) for all subsequent plans
- wan_controller.py net LOC reduced from 2,579 to 2,410 (-169 lines, -6.5%)
- All 83 test_wan_controller.py tests pass unchanged -- zero behavioral regression

## Task Commits

Each task was committed atomically:

1. **Task 1: AST-based function line count verification script** - `8d2cf0a` (feat)
2. **Task 2: Extract WANController.__init__()** - `2c41ade` (feat)
3. **Task 3: Extract run_cycle() and _check_congestion_alerts()** - `078e6db` (feat)

## Files Created/Modified
- `scripts/check_function_lines.py` - AST-based function line counter with --threshold and --show-all flags
- `src/wanctl/wan_controller.py` - WANController with 22 new private methods replacing inline code
- `Makefile` - Added check-lines target for automated line-count enforcement

## Decisions Made
- 11 init helpers instead of 10 -- separated alert timers (congestion, connectivity, IRTT loss, flapping) into _init_alert_timers for cohesion
- Extracted _tick_fusion_healer as standalone helper from IRTT observation to reduce nesting and keep _run_irtt_observation under 50 lines
- Fixed mypy type annotations for transition_reason parameters (str | None, not str) to match actual return types from QueueController.adjust_4state/adjust

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type mismatch for transition_reason parameters**
- **Found during:** Task 3
- **Issue:** _run_congestion_assessment return type declared `str` but QueueController returns `str | None` for transition_reason
- **Fix:** Updated return type to `tuple[str, int, str | None, str, int, str | None, float]` and _run_logging_metrics parameter types to `str | None`
- **Files modified:** src/wanctl/wan_controller.py
- **Verification:** mypy shows no errors on new code (pre-existing errors unrelated)
- **Committed in:** 078e6db (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Type fix necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- WANController method extraction complete -- all 3 mega-functions now under 50 lines
- scripts/check_function_lines.py available for Plans 02-06 verification
- Makefile check-lines target ready for CI integration
- 22 new private methods with docstrings provide clear subsystem boundaries

---
*Phase: 145-method-extraction-simplification*
*Completed: 2026-04-06*

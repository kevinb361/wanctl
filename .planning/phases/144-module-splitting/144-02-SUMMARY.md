---
phase: 144-module-splitting
plan: 02
subsystem: infra
tags: [refactoring, module-extraction, python-imports]

# Dependency graph
requires: [144-01]
provides:
  - "WANController in standalone wan_controller.py (2,579 LOC)"
  - "_apply_tuning_to_controller co-located in wan_controller.py"
  - "4 controller constants in wan_controller.py"
  - "autorate_continuous.py reduced from 3,660 to 1,095 LOC (orchestrator only)"
  - "PROFILE_REPORT_INTERVAL re-export eliminated"
affects: [144-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Forward reference string annotation for _apply_tuning_to_controller(wc: 'WANController')"
    - "Mock patch targets must follow symbol to new module (wan_controller.record_*)"

key-files:
  created:
    - src/wanctl/wan_controller.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/autorate_config.py
    - pyproject.toml
    - vulture_whitelist.py
    - tests/ (37 test files updated)

key-decisions:
  - "Kept forward reference string 'WANController' in _apply_tuning_to_controller since function is defined before class in wan_controller.py"
  - "Added C901 per-file-ignore for wan_controller.py (run_cycle=36, _apply_tuning=22) -- inherited complexity from autorate_continuous.py"
  - "Updated mock patch targets for record_ping_failure, record_rate_limit_event, record_router_update, record_autorate_cycle from wanctl.autorate_continuous to wanctl.wan_controller"

patterns-established:
  - "autorate_continuous.py re-imports WANController, _apply_tuning_to_controller, CYCLE_INTERVAL_SECONDS from wan_controller for entry-point compatibility"

requirements-completed: [CPLX-01]

# Metrics
duration: 40min
completed: 2026-04-05
---

# Phase 144 Plan 02: WANController Extraction Summary

**Extracted WANController (~2,396 LOC) and _apply_tuning_to_controller (~93 LOC) to wan_controller.py, completing the monolith decomposition into 5 modules**

## Performance

- **Duration:** 40 min
- **Started:** 2026-04-05T23:28:55Z
- **Completed:** 2026-04-05T24:08:55Z
- **Tasks:** 2
- **Files modified:** 41 (1 new module, 40 existing files updated)

## Accomplishments

- Extracted WANController (2,579 LOC including imports/constants) to wan_controller.py
- Co-located _apply_tuning_to_controller (93 LOC) in same module (direct WANController dependency)
- Moved 4 controller constants: CYCLE_INTERVAL_SECONDS, DEFAULT_RATE_LIMIT_MAX_CHANGES, DEFAULT_RATE_LIMIT_WINDOW_SECONDS, FORCE_SAVE_INTERVAL_CYCLES
- Eliminated PROFILE_REPORT_INTERVAL re-export from autorate_continuous.py (D-06)
- Updated CYCLE_INTERVAL_SECONDS import in autorate_config.py from autorate_continuous to wan_controller (resolves Plan 01 circular dependency workaround)
- autorate_continuous.py reduced from 3,660 to 1,095 LOC (70% reduction from Plan 01 start)
- All 4,177 tests pass, vulture clean, ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract WANController + _apply_tuning + constants to wan_controller.py** - `79fb9f0` (feat)
2. **Task 2: Verify residual autorate_continuous.py and run full CI** - `0a2abb1` (chore)

## Files Created/Modified

- `src/wanctl/wan_controller.py` - WANController class + _apply_tuning_to_controller + 4 controller constants
- `src/wanctl/autorate_continuous.py` - Removed WANController, _apply_tuning, constants, PROFILE_REPORT_INTERVAL re-export; updated docstring
- `src/wanctl/autorate_config.py` - CYCLE_INTERVAL_SECONDS local import updated from autorate_continuous to wan_controller
- `pyproject.toml` - Added C901 per-file-ignore for wan_controller.py
- `vulture_whitelist.py` - Updated comment referencing wan_controller.py
- `tests/` - 37 test files updated with new import paths and mock targets

## Module Decomposition Complete

After Plan 01 + Plan 02, the original 5,218-LOC monolith is now 5 focused modules:

| Module | LOC | Responsibility |
|--------|-----|----------------|
| wan_controller.py | 2,579 | Core WAN control loop, congestion state, rate adjustment |
| autorate_config.py | 1,200 | YAML config loading, validation, threshold computation |
| autorate_continuous.py | 1,095 | Daemon lifecycle, orchestrator, main() entry point |
| queue_controller.py | 347 | 3/4-state bandwidth state machine |
| routeros_interface.py | 50 | RouterOS command dispatch adapter |

Total: 5,271 LOC across 5 modules (vs 5,218 in monolith -- 53 lines of import overhead)

## Decisions Made

- **Forward reference preserved:** `_apply_tuning_to_controller` uses `wc: "WANController"` string annotation because it's defined before the class in wan_controller.py. Adding `from __future__ import annotations` was considered but rejected as too risky for a pure refactor.
- **C901 per-file-ignore:** wan_controller.py inherits run_cycle (complexity 36) and _apply_tuning (22) from autorate_continuous.py. Added per-file-ignore since this is structural extraction, not a complexity reduction phase.
- **Mock patch retargeting:** 8 mock patches in test_wan_controller.py had to change from `wanctl.autorate_continuous.record_*` to `wanctl.wan_controller.record_*` because Python mock.patch targets the name in the importing module's namespace.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated mock patch targets for metrics recording functions**
- **Found during:** Task 1
- **Issue:** 8 patches in test_wan_controller.py referenced `wanctl.autorate_continuous.record_ping_failure`, `record_rate_limit_event`, `record_router_update`, `record_autorate_cycle` which now live in wan_controller's namespace
- **Fix:** Updated all 8 patches to target `wanctl.wan_controller.record_*`
- **Files modified:** tests/test_wan_controller.py
- **Committed in:** 79fb9f0

**2. [Rule 1 - Bug] Fixed import sorting violations in test files**
- **Found during:** Task 2
- **Issue:** 7 test files had unsorted imports after WANController moved to wan_controller module (isort I001)
- **Fix:** Ran `ruff check --fix` to auto-sort imports
- **Files modified:** 6 test files
- **Committed in:** 0a2abb1

**3. [Rule 1 - Bug] Fixed Windows line endings in test files**
- **Found during:** Task 1
- **Issue:** Several test files had `\r\n` line endings causing sed regex `$` to not match, leaving some WANController imports unreplaced
- **Fix:** Applied sed replacement with explicit `\r` handling
- **Committed in:** 79fb9f0

---

**Total deviations:** 3 auto-fixed (3x Rule 1 - bugs from relocated code references)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing test failure: `test_production_steering_yaml_no_unknown_keys` fails due to missing `configs/steering.yaml` file -- not caused by this plan, deselected during test runs.
- Pre-existing mypy errors: 25 errors in 4 files (check_cake.py, autorate_continuous.py, steering/daemon.py) -- all existed before this plan, 0 new errors introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Monolith decomposition complete: 5,218 LOC -> 5 modules
- autorate_continuous.py is now a clean 1,095 LOC orchestrator
- pyproject.toml entry point unchanged (`wanctl = "wanctl.autorate_continuous:main"`)
- Ready for Plan 03 (docstring audit and CONFIG_SCHEMA sync)

## Self-Check: PASSED

- src/wanctl/wan_controller.py exists with class WANController and _apply_tuning_to_controller
- Both task commits found in git history (79fb9f0, 0a2abb1)
- Zero remaining WANController/_apply_tuning imports from autorate_continuous
- 4,177 tests pass (1 pre-existing deselection)
- Vulture dead code check passes
- Ruff lint check passes

---
*Phase: 144-module-splitting*
*Completed: 2026-04-05*

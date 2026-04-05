---
phase: 144-module-splitting
plan: 01
subsystem: infra
tags: [refactoring, module-extraction, python-imports]

# Dependency graph
requires: []
provides:
  - "QueueController in standalone queue_controller.py (347 LOC)"
  - "Config class in standalone autorate_config.py (1,200 LOC)"
  - "RouterOS adapter in standalone routeros_interface.py (50 LOC)"
  - "autorate_continuous.py reduced from 5,218 to 3,660 LOC"
affects: [144-02-PLAN, 144-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local imports for circular dependency avoidance (CYCLE_INTERVAL_SECONDS)"
    - "Module-level re-import in autorate_continuous.py for backward compatibility"

key-files:
  created:
    - src/wanctl/queue_controller.py
    - src/wanctl/autorate_config.py
    - src/wanctl/routeros_interface.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/check_config.py
    - pyproject.toml
    - tests/ (21 test files updated)

key-decisions:
  - "Used local import for CYCLE_INTERVAL_SECONDS in Config._load_threshold_config to avoid circular import (autorate_config <-> autorate_continuous)"
  - "Added C901 per-file-ignore for queue_controller.py since adjust_4state complexity 21 was inherited from autorate_continuous.py"
  - "Updated mock patch targets in tests to reference new module locations (routeros_interface.get_router_client_with_failover)"

patterns-established:
  - "Extracted classes import from their new canonical modules, autorate_continuous.py re-imports for entry-point compatibility"

requirements-completed: [CPLX-01]

# Metrics
duration: 83min
completed: 2026-04-05
---

# Phase 144 Plan 01: Foundation Class Extraction Summary

**Extracted QueueController, Config, and RouterOS from 5,218-LOC monolith into 3 focused modules, reducing autorate_continuous.py by 1,558 lines**

## Performance

- **Duration:** 83 min
- **Started:** 2026-04-05T22:01:27Z
- **Completed:** 2026-04-05T23:24:58Z
- **Tasks:** 3
- **Files modified:** 27 (3 new modules, 24 existing files updated)

## Accomplishments

- Extracted QueueController (347 LOC) to queue_controller.py with 3-state and 4-state congestion logic
- Extracted Config (1,200 LOC) and 5 config constants to autorate_config.py with all validation
- Extracted RouterOS adapter (50 LOC) to routeros_interface.py
- All 4,177 tests pass with zero behavioral changes
- autorate_continuous.py reduced from 5,218 to 3,660 LOC (30% reduction)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract QueueController to queue_controller.py** - `4a0aecd` (feat)
2. **Task 2: Extract Config class to autorate_config.py** - `88b4fba` (feat)
3. **Task 3: Extract RouterOS to routeros_interface.py** - `3fdbd6e` (feat)

## Files Created/Modified

- `src/wanctl/queue_controller.py` - QueueController 3/4-state bandwidth state machine
- `src/wanctl/autorate_config.py` - Config class + 5 config constants (DEFAULT_BASELINE_UPDATE_THRESHOLD_MS, DEFAULT_HARD_RED_BLOAT_MS, MIN/MAX_SANE_BASELINE_RTT, MBPS_TO_BPS)
- `src/wanctl/routeros_interface.py` - RouterOS command dispatch adapter
- `src/wanctl/autorate_continuous.py` - Removed 3 classes, added re-imports from new modules
- `src/wanctl/check_config.py` - Updated Config import path
- `pyproject.toml` - Added C901 per-file-ignore for queue_controller.py
- `tests/` - 21 test files updated with new import paths and mock targets

## Decisions Made

- **Circular import avoidance:** Config._load_threshold_config uses CYCLE_INTERVAL_SECONDS via local import (`from wanctl.autorate_continuous import CYCLE_INTERVAL_SECONDS`) rather than module-level import to prevent circular dependency. Plan 02 will relocate CYCLE_INTERVAL_SECONDS to wan_controller.py.
- **C901 ignore:** QueueController.adjust_4state has complexity 21 (inherited from autorate_continuous.py which had a blanket C901 ignore). Added per-file-ignore for queue_controller.py since this is a structural move, not a refactor.
- **Mock target updates:** Tests patching `wanctl.autorate_continuous.get_router_client_with_failover` updated to `wanctl.routeros_interface.get_router_client_with_failover` since RouterOS moved. Similarly, logging mock targets in test_asymmetry_analyzer.py updated to `wanctl.autorate_config.logging`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated logger name in QueueController tests**
- **Found during:** Task 1
- **Issue:** QueueController._logger uses `logging.getLogger(__name__)` which changed from `wanctl.autorate_continuous` to `wanctl.queue_controller`, causing 4 caplog tests to fail
- **Fix:** Updated `logger="wanctl.autorate_continuous"` to `logger="wanctl.queue_controller"` in test_queue_controller.py
- **Files modified:** tests/test_queue_controller.py
- **Committed in:** 4a0aecd

**2. [Rule 1 - Bug] Updated logging mock targets for Config tests**
- **Found during:** Task 2
- **Issue:** test_asymmetry_analyzer.py patched `wanctl.autorate_continuous.logging` for Config methods, but Config now lives in autorate_config
- **Fix:** Updated 6 patch targets to `wanctl.autorate_config.logging`
- **Files modified:** tests/test_asymmetry_analyzer.py
- **Committed in:** 88b4fba

**3. [Rule 1 - Bug] Updated mock patch targets for RouterOS factory**
- **Found during:** Task 3
- **Issue:** 7 test patches referenced `wanctl.autorate_continuous.get_router_client_with_failover` which no longer exists there
- **Fix:** Updated patches to `wanctl.routeros_interface.get_router_client_with_failover`
- **Files modified:** tests/test_alerting_config.py, tests/test_asymmetry_persistence.py, tests/test_autorate_error_recovery.py
- **Committed in:** 3fdbd6e

**4. [Rule 1 - Bug] Updated source inspection path in phase53 cleanup test**
- **Found during:** Task 3
- **Issue:** test_phase53_code_cleanup.py inspected autorate_continuous.py source for RouterOS class definition
- **Fix:** Updated to inspect routeros_interface.py
- **Files modified:** tests/test_phase53_code_cleanup.py
- **Committed in:** 3fdbd6e

---

**Total deviations:** 4 auto-fixed (4x Rule 1 - bugs from relocated code references)
**Impact on plan:** All fixes necessary for correctness. Module moves inherently require updating all references. No scope creep.

## Issues Encountered

- Pre-existing test failure: `test_production_steering_yaml_no_unknown_keys` fails due to missing `configs/steering.yaml` file -- not caused by this plan, deselected during test runs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- autorate_continuous.py now at 3,660 LOC, ready for Plan 02 (WANController extraction)
- CYCLE_INTERVAL_SECONDS remains in autorate_continuous.py with a local import in autorate_config.py -- Plan 02 should relocate it
- pyproject.toml entry point unchanged (`wanctl = "wanctl.autorate_continuous:main"`)

## Self-Check: PASSED

- All 3 new module files exist with correct class definitions
- All 3 task commits found in git history
- All re-imports present in autorate_continuous.py
- 4,177 tests pass (1 pre-existing deselection)
- vulture dead code check passes

---
*Phase: 144-module-splitting*
*Completed: 2026-04-05*

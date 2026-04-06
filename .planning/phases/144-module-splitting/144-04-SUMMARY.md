---
phase: 144-module-splitting
plan: 04
subsystem: infra
tags: [refactoring, module-extraction, gap-closure, validators]

# Dependency graph
requires: [144-03]
provides:
  - "check_steering_validators.py with steering+linux-cake validators and KNOWN_STEERING_PATHS (478 eff LOC)"
  - "check_config_validators.py reduced to autorate-only validators and KNOWN_AUTORATE_PATHS (569 eff LOC)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local import of check_paths/check_env_vars in _run_steering_validators to avoid circular dependency"
    - "Local import of validate_linux_cake in _run_autorate_validators (moved to steering module)"
    - "Duplicated _walk_leaf_paths (9 LOC) in check_steering_validators.py to avoid circular imports"

key-files:
  created:
    - src/wanctl/check_steering_validators.py
  modified:
    - src/wanctl/check_config_validators.py
    - src/wanctl/check_config.py
    - tests/test_check_config.py

key-decisions:
  - "validate_linux_cake grouped with steering validators since linux-cake is a transport concern; autorate dispatcher imports it via local import"
  - "check_paths and check_env_vars remain in check_config_validators (autorate module) since they are autorate-first utilities; steering dispatcher imports them via local import"
  - "Unused imports removed: yaml from check_config_validators, os/re/validate_bandwidth_order/validate_threshold_order from check_steering_validators"

requirements-completed: [CPLX-01]

# Metrics
duration: 7min
completed: 2026-04-06
---

# Phase 144 Plan 04: Gap Closure -- check_config_validators Split Summary

**Split check_config_validators.py (1026 eff LOC) into autorate-only (569 eff LOC) and steering-only (478 eff LOC) validator modules, closing the SC1 gap**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-06T02:53:54Z
- **Completed:** 2026-04-06T03:01:37Z
- **Tasks:** 2/2
- **Files modified:** 4 (1 new module, 3 existing files updated)

## Accomplishments

- Extracted KNOWN_STEERING_PATHS, 5 steering validators, validate_linux_cake, and _run_steering_validators to new check_steering_validators.py
- Reduced check_config_validators.py from 1026 to 569 eff LOC (autorate validators only)
- New check_steering_validators.py at 478 eff LOC (steering + linux-cake validators)
- Both modules have module-level docstrings stating single responsibility
- All 268 related tests pass with zero behavioral changes (1 pre-existing deselection)
- No re-export shims (per D-06)
- Ruff clean, vulture dead-code clean

## Task Commits

1. **Task 1: Extract steering validators to check_steering_validators.py** - `e91fbc3` (feat)
2. **Task 2: Update import sites and verify full test suite** - `e91dfc0` (feat)

## Files Created/Modified

- `src/wanctl/check_steering_validators.py` -- KNOWN_STEERING_PATHS, validate_steering_schema_fields, validate_steering_cross_fields, check_steering_unknown_keys, check_steering_deprecated_params, check_steering_cross_config, validate_linux_cake, _run_steering_validators
- `src/wanctl/check_config_validators.py` -- Reduced to KNOWN_AUTORATE_PATHS, validate_schema_fields, validate_cross_fields, check_unknown_keys, check_paths, check_env_vars, check_deprecated_params, _run_autorate_validators
- `src/wanctl/check_config.py` -- Updated main() local import to dispatch steering validators from check_steering_validators
- `tests/test_check_config.py` -- Split import block: autorate validators from check_config_validators, steering validators from check_steering_validators

## LOC Distribution After Gap Closure

| Module | Before | After | Delta |
|--------|--------|-------|-------|
| check_config_validators.py | 1,026 | 569 | -457 |
| check_steering_validators.py | - | 478 | +478 |

## Decisions Made

- **validate_linux_cake placement:** Grouped with steering validators since linux-cake is a transport concern that logically belongs with steering domain. Autorate dispatcher imports it via local import since autorate configs can also use linux-cake transport.
- **Shared utilities (check_paths, check_env_vars):** Kept in check_config_validators.py since they were originally autorate utilities. Steering dispatcher imports them via local import to avoid duplication of larger functions.
- **_walk_leaf_paths duplication:** Duplicated 9 LOC helper (established Phase 144 pattern) rather than creating a shared utility module.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing imports for shared functions in _run_steering_validators**
- **Found during:** Task 1
- **Issue:** _run_steering_validators calls check_paths() and check_env_vars() which remain in check_config_validators.py, but the plan's import list did not include importing from check_config_validators
- **Fix:** Added local import of check_paths and check_env_vars from check_config_validators inside _run_steering_validators
- **Files modified:** src/wanctl/check_steering_validators.py
- **Committed in:** e91fbc3

**2. [Rule 3 - Blocking] Missing imports for validate_linux_cake in _run_autorate_validators**
- **Found during:** Task 1
- **Issue:** validate_linux_cake moved to check_steering_validators but _run_autorate_validators still calls it
- **Fix:** Added local import of validate_linux_cake from check_steering_validators inside _run_autorate_validators
- **Files modified:** src/wanctl/check_config_validators.py
- **Committed in:** e91fbc3

**3. [Rule 1 - Bug] Plan import list included unused imports for check_steering_validators.py**
- **Found during:** Task 1
- **Issue:** Plan specified importing os, re, validate_bandwidth_order, validate_threshold_order -- none used by steering validators
- **Fix:** Removed unused imports, confirmed with ruff check
- **Files modified:** src/wanctl/check_steering_validators.py
- **Committed in:** e91fbc3

**4. [Rule 1 - Bug] Plan import list omitted required imports for check_steering_validators.py**
- **Found during:** Task 1
- **Issue:** Plan said not to import yaml or Path, but check_steering_cross_config uses yaml.safe_load and Path
- **Fix:** Added yaml and Path imports to check_steering_validators.py
- **Files modified:** src/wanctl/check_steering_validators.py
- **Committed in:** e91fbc3

**5. [Rule 1 - Bug] Unused yaml import in check_config_validators.py after extraction**
- **Found during:** Task 1
- **Issue:** yaml was only used by check_steering_cross_config which moved to the new module
- **Fix:** Removed yaml import from check_config_validators.py
- **Files modified:** src/wanctl/check_config_validators.py
- **Committed in:** e91fbc3

---

**Total deviations:** 5 auto-fixed (2x Rule 3 blocking, 3x Rule 1 bugs from plan import list inaccuracies)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing test failure: `test_production_steering_yaml_no_unknown_keys` fails due to missing `configs/steering.yaml` file -- not caused by this plan (documented in Plan 03 SUMMARY).

## Self-Check: PASSED

- All 4 files exist (1 new module, 3 modified)
- Both task commits found in git history (e91fbc3, e91dfc0)
- Both modules importable without circular import errors
- 268 tests pass (1 pre-existing deselection)
- Ruff clean, vulture clean

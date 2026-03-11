---
phase: 69-legacy-fallback-removal
plan: 01
subsystem: config
tags: [deprecation, config-validation, legacy-cleanup, ewma-alpha]

# Dependency graph
requires:
  - phase: 68-dead-code-removal
    provides: clean codebase with cake_aware removed
provides:
  - deprecate_param() centralized helper in config_validation_utils.py
  - 5 legacy config params produce deprecation warnings with value translation
affects: [69-02, 70-confidence-graduation]

# Tech tracking
tech-stack:
  added: []
  patterns: [deprecate_param warn+translate for legacy config migration]

key-files:
  created: []
  modified:
    - src/wanctl/config_validation_utils.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - tests/test_config_validation_utils.py
    - tests/test_autorate_config.py
    - tests/test_steering_daemon.py

key-decisions:
  - "deprecate_param injects translated value into dict so existing if/elif/else chains pick it up with zero structural change"
  - "alpha -> time_constant translation uses cycle_interval/alpha formula preserving mathematical equivalence"
  - "When both old and new keys present, modern key wins silently (no warning)"

patterns-established:
  - "deprecate_param pattern: check old_key, translate with optional transform_fn, inject into dict under new_key, log warning"

requirements-completed: [LGCY-03]

# Metrics
duration: 16min
completed: 2026-03-11
---

# Phase 69 Plan 01: Deprecation Helper & Config Warning Wiring Summary

**Centralized deprecate_param() helper with warn+translate wiring for 5 legacy config params (alpha_baseline, alpha_load, spectrum_download, spectrum_upload, cake_state_sources.spectrum)**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-11T12:07:17Z
- **Completed:** 2026-03-11T12:23:40Z
- **Tasks:** 1
- **Files modified:** 6

## Accomplishments
- Created `deprecate_param()` helper in `config_validation_utils.py` with optional `transform_fn` for value translation
- Wired autorate alpha_baseline and alpha_load through deprecation path with cycle_interval/alpha transform
- Wired steering spectrum_download, spectrum_upload, and cake_state_sources.spectrum through deprecation path (identity)
- 18 new tests (12 for helper, 2 for autorate warnings, 4 for steering warnings)
- All 2272 unit tests pass, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for deprecate_param** - `e1afd27` (test)
2. **Task 1 (GREEN): Implementation + wiring + updated tests** - `4d830ec` (feat)

_TDD task: RED commit has import error (expected), GREEN commit implements and passes all tests._

## Files Created/Modified
- `src/wanctl/config_validation_utils.py` - Added `deprecate_param()` helper function
- `src/wanctl/autorate_continuous.py` - Added deprecation calls before alpha if/elif/else chains
- `src/wanctl/steering/daemon.py` - Replaced manual spectrum->primary fallbacks with deprecate_param calls
- `tests/test_config_validation_utils.py` - 12 new tests for `TestDeprecateParam` class
- `tests/test_autorate_config.py` - 2 new deprecation warning tests + 1 updated existing test
- `tests/test_steering_daemon.py` - 4 new legacy deprecation warning tests

## Decisions Made
- Used dict injection pattern: deprecate_param returns translated value, caller injects into dict under new_key, then existing if/elif/else chain picks it up naturally -- minimal structural change to production code
- When both old and new keys are present, modern key wins silently (no warning, no translation) -- prevents double-processing
- Fixed ruff UP035 violation: imported `Callable` from `collections.abc` instead of `typing` (Python 3.12 idiom)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff UP035 import violation**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `from typing import Callable` triggers ruff UP035; Python 3.12 requires `from collections.abc import Callable`
- **Fix:** Changed import to `from collections.abc import Callable`
- **Files modified:** `src/wanctl/config_validation_utils.py`
- **Verification:** `ruff check` passes, all tests pass
- **Committed in:** `4d830ec` (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Trivial import fix required for lint compliance. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- deprecate_param() helper is ready for reuse in plan 69-02 (remaining 3 legacy params)
- Pattern established: import deprecate_param, call before existing config loading, inject translated value

---
*Phase: 69-legacy-fallback-removal*
*Completed: 2026-03-11*

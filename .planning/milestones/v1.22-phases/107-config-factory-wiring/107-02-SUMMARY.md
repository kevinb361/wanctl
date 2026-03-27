---
phase: 107-config-factory-wiring
plan: 02
subsystem: cli
tags: [check-config, linux-cake, validation, cake-params, offline-validator]

# Dependency graph
requires:
  - phase: 106-cake-optimization-parameters
    provides: "VALID_OVERHEAD_KEYWORDS in cake_params module"
provides:
  - "validate_linux_cake() in check_config.py for offline linux-cake config validation"
  - "KNOWN_AUTORATE_PATHS updated with cake_params.* paths"
  - "14 new tests in TestLinuxCakeValidation"
affects: [107-config-factory-wiring, 110-production-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns: ["lazy import for cross-module validation (VALID_OVERHEAD_KEYWORDS)"]

key-files:
  created: []
  modified:
    - src/wanctl/check_config.py
    - tests/test_check_config.py

key-decisions:
  - "Lazy import VALID_OVERHEAD_KEYWORDS inside validate_linux_cake to avoid circular import risk"
  - "tc binary absence is WARN not ERROR -- check-config is an offline validator (D-08)"
  - "cake_params validation only fires when router.transport is linux-cake (D-03)"

patterns-established:
  - "Transport-gated validation: validate_linux_cake checks transport before doing work"

requirements-completed: [CONF-04]

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 107 Plan 02: Linux-CAKE Config Validation Summary

**validate_linux_cake() added to wanctl-check-config: validates cake_params structure, interfaces, overhead keywords, and tc binary with 14 TDD tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-25T14:32:13Z
- **Completed:** 2026-03-25T14:34:42Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- validate_linux_cake() validates cake_params section, interface fields, overhead keywords, and tc binary
- KNOWN_AUTORATE_PATHS extended with 6 cake_params paths preventing false-positive unknown key warnings
- 14 new tests covering all validation branches (transport skip, missing section, invalid types, interfaces, overhead, tc)
- Wired into _run_autorate_validators() dispatcher -- runs automatically on all autorate config checks
- 99 total check_config tests passing, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for linux-cake validation** - `22c62b9` (test)
2. **Task 1 (GREEN): Implement validate_linux_cake and wire into dispatcher** - `8a1fd4a` (feat)

## Files Created/Modified
- `src/wanctl/check_config.py` - Added validate_linux_cake() function, 6 cake_params paths in KNOWN_AUTORATE_PATHS, wired into _run_autorate_validators
- `tests/test_check_config.py` - Added TestLinuxCakeValidation class with 14 comprehensive tests

## Decisions Made
- Lazy import of VALID_OVERHEAD_KEYWORDS inside function body to avoid circular import risk between check_config and cake_params modules
- tc binary absence produces WARN (not ERROR) because check-config is an offline validator that may run on dev machines without iproute2
- Overhead field is optional -- absence is not an error, only invalid values are flagged
- Early return when cake_params is missing/not-a-dict prevents cascading errors on sub-fields

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- check-config now validates linux-cake transport configs offline
- Ready for Phase 108 (steering dual-backend) or remaining Phase 107 plans
- Operators can validate their linux-cake YAML before deployment

---
*Phase: 107-config-factory-wiring*
*Completed: 2026-03-25*

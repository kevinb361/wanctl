---
phase: 106-cake-optimization-parameters
plan: 01
subsystem: infra
tags: [cake, qdisc, tc, linux, network, bufferbloat]

# Dependency graph
requires:
  - phase: 105-linux-cake-backend
    provides: LinuxCakeBackend.initialize_cake(params) and validate_cake(expected)
provides:
  - build_cake_params() direction-aware param builder for initialize_cake()
  - build_expected_readback() for validate_cake() numeric conversion
  - UPLOAD_DEFAULTS / DOWNLOAD_DEFAULTS / TUNABLE_DEFAULTS constants
  - VALID_OVERHEAD_KEYWORDS and EXCLUDED_PARAMS validation sets
affects: [106-02, 107-factory-wiring, 109-vm-startup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      dual-layer defaults (hardcoded + config override),
      YAML underscore-to-tc-hyphen key translation,
    ]

key-files:
  created:
    - src/wanctl/cake_params.py
    - tests/test_cake_params.py
  modified: []

key-decisions:
  - "Overhead keywords stored as overhead_keyword key (standalone tc token), not numeric overhead"
  - "YAML underscore keys translated to tc hyphen keys via YAML_TO_TC_KEY mapping"
  - "build_expected_readback uses lookup tables for known values, fallback parsing for unknown"

patterns-established:
  - "Direction-aware defaults: UPLOAD_DEFAULTS/DOWNLOAD_DEFAULTS merged with TUNABLE_DEFAULTS"
  - "Config override semantics: False explicitly disables (not truthy check)"
  - "Excluded param validation: raises ConfigValidationError for nat/wash/autorate-ingress"

requirements-completed:
  [CAKE-01, CAKE-02, CAKE-03, CAKE-05, CAKE-06, CAKE-08, CAKE-09, CAKE-10]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 106 Plan 01: CAKE Params Builder Summary

**Direction-aware CakeParamsBuilder with upload ack-filter, download ingress+ecn, overhead keyword validation, and readback-to-numeric conversion**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T22:38:03Z
- **Completed:** 2026-03-24T22:41:19Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments

- build_cake_params() constructs direction-aware CAKE param dicts from hardcoded defaults + YAML config overrides
- build_expected_readback() converts overhead keywords to numeric, rtt strings to microseconds, memlimit to bytes
- Excluded params (nat, wash, autorate-ingress) raise ConfigValidationError at config load time
- Overhead keyword validation against 11 known tc-cake(8) keywords
- 54 tests passing, ruff clean, mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `28a4aba` (test)
2. **Task 1 GREEN: CakeParamsBuilder implementation** - `3a556ce` (feat)

## Files Created/Modified

- `src/wanctl/cake_params.py` - CakeParamsBuilder module: direction defaults, config override, overhead keyword, readback conversion
- `tests/test_cake_params.py` - 54 tests across 12 test classes covering all CAKE requirements

## Decisions Made

- Overhead keyword stored as `overhead_keyword` key in params dict (standalone tc token, not numeric `overhead` key-value)
- YAML config uses underscore keys (split_gso, ack_filter) translated to tc hyphen keys via YAML_TO_TC_KEY
- build_expected_readback uses lookup tables (RTT_TO_MICROSECONDS, MEMLIMIT_TO_BYTES) for known values with fallback string parsing for unknown values
- ConfigValidationError from config_base.py reused (no new exception types)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all functions are fully implemented with real logic.

## Next Phase Readiness

- cake_params.py ready for consumption by Plan 02 (initialize_cake overhead_keyword extension)
- build_expected_readback ready for validate_cake integration
- All 8 CAKE requirements (CAKE-01 through CAKE-10, minus CAKE-04 and CAKE-07) satisfied by builder defaults

## Self-Check: PASSED

- FOUND: src/wanctl/cake_params.py
- FOUND: tests/test_cake_params.py
- FOUND: 106-01-SUMMARY.md
- FOUND: 28a4aba (RED commit)
- FOUND: 3a556ce (GREEN commit)

---

_Phase: 106-cake-optimization-parameters_
_Completed: 2026-03-24_

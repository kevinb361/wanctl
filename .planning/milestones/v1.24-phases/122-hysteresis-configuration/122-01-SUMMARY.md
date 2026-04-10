---
phase: 122-hysteresis-configuration
plan: 01
subsystem: config
tags: [yaml, schema-validation, hysteresis, dwell-timer, deadband]

# Dependency graph
requires:
  - phase: 121-core-hysteresis-logic
    provides: "QueueController dwell_cycles/deadband_ms constructor params with hardcoded defaults"
provides:
  - "YAML config parsing for dwell_cycles (int 0-20, default 3) and deadband_ms (float 0.0-20.0, default 3.0)"
  - "WANController wiring from config to both download/upload QueueController instances"
  - "SCHEMA validation entries with type and bounds checking"
  - "check_config KNOWN_KEYS entries preventing unknown-key warnings"
affects:
  [
    122-02-PLAN (SIGUSR1 reload needs config attrs),
    123-hysteresis-observability,
    124-production-validation,
  ]

# Tech tracking
tech-stack:
  added: []
  patterns: ["thresh.get() with defaults for optional hysteresis params"]

key-files:
  created:
    - tests/test_hysteresis_config.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/check_config.py
    - tests/conftest.py

key-decisions:
  - "min=0 allows disabling hysteresis (dwell_cycles=0, deadband_ms=0.0) as backward-compat escape hatch"
  - "Shared hysteresis params (not per-direction) matching Phase 121 design: both DL and UL use same values"

patterns-established:
  - "Hysteresis config follows existing thresh.get() pattern with defaults matching QueueController constructor defaults"

requirements-completed: [CONF-01, CONF-03]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 122 Plan 01: Hysteresis Configuration Summary

**YAML config wiring for dwell_cycles and deadband_ms with schema validation, sensible defaults (3/3.0), and QueueController pass-through**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T13:13:20Z
- **Completed:** 2026-03-31T13:17:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Config.\_load_threshold_config parses dwell_cycles (default 3) and deadband_ms (default 3.0) from YAML thresholds section
- WANController passes both values to both download and upload QueueController instances
- SCHEMA validates dwell_cycles as int [0,20] and deadband_ms as (int,float) [0.0,20.0]
- check_config KNOWN_KEYS includes both new keys, preventing unknown-key warnings
- 8 tests covering parsing, defaults, zero-disable, schema entries, and wiring

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hysteresis params to Config parsing, SCHEMA, and KNOWN_KEYS** - `dc83da2` (feat)
2. **Task 2: Tests for config parsing, defaults, schema validation, and wiring** - `d18a4bb` (test)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - SCHEMA entries, \_load_threshold_config parsing, WANController wiring
- `src/wanctl/check_config.py` - KNOWN_KEYS entries for dwell_cycles and deadband_ms
- `tests/test_hysteresis_config.py` - 8 tests: parsing, defaults, zero-disable, schema, wiring
- `tests/conftest.py` - Added dwell_cycles/deadband_ms to shared mock_autorate_config fixture

## Decisions Made

- min=0 allows disabling hysteresis (dwell_cycles=0, deadband_ms=0.0) as backward-compat escape hatch from Phase 121
- Shared hysteresis params (not per-direction) matching Phase 121 design: both DL and UL use same values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added dwell_cycles/deadband_ms to shared conftest fixture**

- **Found during:** Task 2 (test creation)
- **Issue:** Shared mock_autorate_config fixture in conftest.py lacked hysteresis params; existing WANController tests relied on MagicMock auto-creating attributes (returning MagicMock objects instead of proper int/float values)
- **Fix:** Added config.dwell_cycles = 3 and config.deadband_ms = 3.0 to shared fixture
- **Files modified:** tests/conftest.py
- **Verification:** All existing tests still pass with proper typed values
- **Committed in:** d18a4bb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Ensures future tests using shared fixture get proper typed values instead of MagicMock objects. No scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Config parsing complete, ready for 122-02 (SIGUSR1 hot-reload)
- config.dwell_cycles and config.deadband_ms available for reload method to update at runtime
- All 76 tests pass (68 existing + 8 new)

---

_Phase: 122-hysteresis-configuration_
_Completed: 2026-03-31_

## Self-Check: PASSED

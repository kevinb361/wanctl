---
phase: 94-owd-asymmetric-detection
plan: 01
subsystem: signal-processing
tags: [irtt, owd, asymmetry, congestion-detection, frozen-dataclass]

# Dependency graph
requires:
  - phase: 89-irtt-foundation
    provides: "IRTTResult dataclass, IRTTMeasurement class, _parse_json()"
  - phase: 92-observability
    provides: "IRTT health endpoint, SQLite metrics persistence"
provides:
  - "IRTTResult with send_delay_median_ms and receive_delay_median_ms fields"
  - "AsymmetryAnalyzer class computing direction from send/receive delay ratio"
  - "AsymmetryResult frozen dataclass with direction, ratio, delays"
  - "DIRECTION_ENCODING dict for SQLite float persistence"
  - "_load_owd_asymmetry_config with warn+default validation"
affects: [94-02, 96-signal-fusion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ratio-based asymmetry detection (NTP-independent)"
    - "Noise guard for sub-0.1ms delays"
    - "Capped ratio (100.0) for divide-by-zero guards"

key-files:
  created:
    - src/wanctl/asymmetry_analyzer.py
    - tests/test_asymmetry_analyzer.py
  modified:
    - src/wanctl/irtt_measurement.py
    - src/wanctl/autorate_continuous.py
    - tests/test_irtt_measurement.py

key-decisions:
  - "OWD fields added with 0.0 defaults to preserve backward compat with all existing IRTTResult constructors"
  - "Ratio capped at 100.0 on divide-by-zero instead of infinity for SQLite REAL column safety"
  - "_MIN_DELAY_MS=0.1 noise floor: both delays below this returns symmetric (not unknown)"

patterns-established:
  - "AsymmetryResult frozen dataclass follows IRTTResult/SignalResult pattern"
  - "Transition logging pattern: INFO on direction change, suppress repeats"
  - "Config validation: warn+default with isinstance+bool exclusion guard"

requirements-completed: [ASYM-01]

# Metrics
duration: 33min
completed: 2026-03-17
---

# Phase 94 Plan 01: OWD Asymmetric Detection Foundation Summary

**IRTTResult extended with send/receive OWD fields, AsymmetryAnalyzer computing direction from ratio with configurable threshold, DIRECTION_ENCODING for SQLite persistence**

## Performance

- **Duration:** 33 min
- **Started:** 2026-03-17T22:14:41Z
- **Completed:** 2026-03-17T22:48:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Extended IRTTResult with send_delay_median_ms and receive_delay_median_ms (0.0 defaults for backward compat)
- Created AsymmetryAnalyzer computing upstream/downstream/symmetric/unknown from send/receive delay ratio
- Added DIRECTION_ENCODING dict mapping directions to float values for SQLite persistence
- Config loading with warn+default validation for ratio_threshold >= 1.0
- 32 new tests (4 IRTTResult OWD + 28 asymmetry analyzer) all passing
- Full test suite green: 3364 tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend IRTTResult and \_parse_json with OWD fields** - `5641e56` (feat)
2. **Task 2: Create AsymmetryAnalyzer module with config loading** - `8e79e24` (feat)

## Files Created/Modified

- `src/wanctl/irtt_measurement.py` - Added send_delay_median_ms, receive_delay_median_ms fields and \_parse_json extraction
- `src/wanctl/asymmetry_analyzer.py` - NEW: AsymmetryAnalyzer, AsymmetryResult, DIRECTION_ENCODING
- `src/wanctl/autorate_continuous.py` - Added \_load_owd_asymmetry_config method and call in config sequence
- `tests/test_irtt_measurement.py` - Updated SAMPLE_IRTT_JSON, added 4 OWD field tests
- `tests/test_asymmetry_analyzer.py` - NEW: 28 tests covering direction, edge cases, logging, config

## Decisions Made

- OWD fields placed as last fields with defaults (= 0.0) to avoid breaking existing IRTTResult constructors
- Ratio capped at 100.0 (not infinity) when one delay is zero, for SQLite REAL column safety
- \_MIN_DELAY_MS = 0.1 as internal noise floor; both delays below this returns "symmetric" with ratio 1.0
- Noise guard returns "symmetric" (not "unknown") because data is present but too small for meaningful ratios

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AsymmetryAnalyzer ready for daemon wiring in Plan 02
- IRTTResult OWD fields available for all consumers reading IRTT results
- DIRECTION_ENCODING ready for SQLite persistence in Plan 02
- Config loader wired; owd_asymmetry YAML section will be read on daemon startup

## Self-Check: PASSED

- All 6 files verified present
- Both task commits (5641e56, 8e79e24) verified in git log
- Full test suite: 3364 passed

---

_Phase: 94-owd-asymmetric-detection_
_Completed: 2026-03-17_

---
phase: 94-owd-asymmetric-detection
plan: 02
subsystem: signal-processing
tags: [irtt, owd, asymmetry, health-endpoint, sqlite, metrics]

# Dependency graph
requires:
  - phase: 94-owd-asymmetric-detection (plan 01)
    provides: "AsymmetryAnalyzer, AsymmetryResult, DIRECTION_ENCODING, IRTTResult OWD fields"
  - phase: 92-observability
    provides: "IRTT health endpoint section, SQLite metrics persistence, STORED_METRICS"
provides:
  - "AsymmetryAnalyzer wired per-WAN in WANController.__init__"
  - "_last_asymmetry_result attribute for downstream consumers (health, fusion)"
  - "asymmetry_direction and asymmetry_ratio in IRTT health endpoint"
  - "wanctl_irtt_asymmetry_ratio and _direction SQLite metrics with IRTT dedup guard"
affects: [96-signal-fusion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Asymmetry metrics inside existing IRTT dedup guard (_last_irtt_write_ts)"
    - "Direction encoded as float via DIRECTION_ENCODING.get() for REAL column"
    - "_last_asymmetry_result = None explicit init for MagicMock truthy trap prevention"

key-files:
  created:
    - tests/test_asymmetry_persistence.py
    - tests/test_asymmetry_health.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/health_check.py
    - src/wanctl/storage/schema.py
    - tests/test_health_check.py
    - tests/test_health_alerting.py
    - tests/test_storage_schema.py

key-decisions:
  - "Asymmetry metrics use same IRTT dedup guard (_last_irtt_write_ts) -- no separate dedup needed"
  - "Health endpoint IRTT unavailable section stays minimal (no asymmetry fields) -- consistent with existing pattern"
  - "MagicMock truthy trap: _last_asymmetry_result=None set on all existing mock WANControllers across 3 test files"

patterns-established:
  - "_last_asymmetry_result attribute follows _last_signal_result pattern for health endpoint consumption"
  - "Asymmetry fields in IRTT health section: direction string + rounded ratio, unknown/null fallbacks"

requirements-completed: [ASYM-02, ASYM-03]

# Metrics
duration: 25min
completed: 2026-03-17
---

# Phase 94 Plan 02: OWD Asymmetric Detection Integration Summary

**AsymmetryAnalyzer wired per-WAN in WANController, direction/ratio in IRTT health section, SQLite persistence with IRTT dedup guard, 28 new tests**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-17T22:51:26Z
- **Completed:** 2026-03-17T23:16:45Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Wired AsymmetryAnalyzer into WANController.**init** with config-driven ratio_threshold
- Added asymmetry_direction and asymmetry_ratio to IRTT health endpoint section (3 cases: full data, awaiting, disabled)
- Persisted wanctl_irtt_asymmetry_ratio and wanctl_irtt_asymmetry_direction to SQLite inside existing IRTT dedup guard
- Direction encoded as float (0/1/2/3) via DIRECTION_ENCODING.get() for REAL column compatibility
- Fixed MagicMock truthy trap across 3 existing test files (7 mock fixtures updated)
- 28 new tests (21 persistence + 7 health), full suite green: 3390 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire AsymmetryAnalyzer into WANController and persist to SQLite** - `9244894` (test, RED) + `a39248e` (feat, GREEN)
2. **Task 2: Add asymmetry fields to IRTT health endpoint section** - `5f2b181` (test, RED) + `b429204` (feat, GREEN)

_Note: TDD tasks have separate RED/GREEN commits_

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Import + **init** wiring + run_cycle analyze() + metrics_batch persistence
- `src/wanctl/health_check.py` - asymmetry_direction/ratio in IRTT full data + awaiting sections
- `src/wanctl/storage/schema.py` - Two new STORED_METRICS entries for asymmetry
- `tests/test_asymmetry_persistence.py` - NEW: 21 tests for WANController wiring, metrics, dedup, encoding
- `tests/test_asymmetry_health.py` - NEW: 7 tests for health endpoint asymmetry fields
- `tests/test_health_check.py` - Added \_last_asymmetry_result=None to 7 mock fixtures
- `tests/test_health_alerting.py` - Added \_last_asymmetry_result=None to 1 mock fixture
- `tests/test_storage_schema.py` - Added asymmetry metric keys to expected set

## Decisions Made

- Asymmetry metrics reuse existing IRTT dedup guard (\_last_irtt_write_ts) rather than introducing a separate dedup timestamp -- both are IRTT-derived and share the same write cadence
- IRTT unavailable section (available: false) stays minimal with no asymmetry fields -- consistent with the existing pattern where disabled/binary_not_found sections only have available + reason
- Set \_last_asymmetry_result = None on all mock WANControllers across test_health_check.py, test_health_alerting.py to prevent MagicMock truthy trap (MagicMock attributes are not None, causing round() on MagicMock)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock truthy trap in existing health check tests**

- **Found during:** Task 2 (health endpoint implementation)
- **Issue:** Existing mock WANControllers in test_health_check.py and test_health_alerting.py lacked \_last_asymmetry_result=None, causing MagicMock to be treated as a real AsymmetryResult (not None), failing on round(MagicMock.ratio, 2)
- **Fix:** Added wan.\_last_asymmetry_result = None to all 8 mock WANController fixtures
- **Files modified:** tests/test_health_check.py, tests/test_health_alerting.py
- **Verification:** All 66 health tests pass
- **Committed in:** b429204 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed ruff import ordering**

- **Found during:** Task 2 (full suite verification)
- **Issue:** Import `AsymmetryAnalyzer, AsymmetryResult, DIRECTION_ENCODING` not in alphabetical order
- **Fix:** Reordered to `DIRECTION_ENCODING, AsymmetryAnalyzer, AsymmetryResult`
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** ruff check passes
- **Committed in:** b429204 (Task 2 commit)

**3. [Rule 1 - Bug] Updated test_storage_schema.py expected keys**

- **Found during:** Task 2 (full suite verification)
- **Issue:** test_stored_metrics_has_expected_keys had hardcoded key set missing new asymmetry entries
- **Fix:** Added wanctl_irtt_asymmetry_ratio and \_direction to expected_keys set
- **Files modified:** tests/test_storage_schema.py
- **Verification:** Full suite passes (3390 tests)
- **Committed in:** b429204 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 94 complete (Plans 01 + 02): ASYM-01, ASYM-02, ASYM-03 all satisfied
- \_last_asymmetry_result available on WANController for Phase 96 signal fusion
- Asymmetry direction/ratio visible in health endpoint for operator awareness
- SQLite persistence enables trend analysis for future alerting

## Self-Check: PASSED

- All 8 files verified present
- All 4 task commits (9244894, a39248e, 5f2b181, b429204) verified in git log
- Full test suite: 3390 passed

---

_Phase: 94-owd-asymmetric-detection_
_Completed: 2026-03-17_

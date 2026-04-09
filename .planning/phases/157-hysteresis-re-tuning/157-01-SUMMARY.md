---
phase: 157-hysteresis-re-tuning
plan: 01
subsystem: config
tags: [yaml, hysteresis, dwell-suppression, dead-config]

# Dependency graph
requires: []
provides:
  - "Corrected suppression_alert_threshold config key in spectrum.yaml"
affects: [157-02, 157-03]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - configs/spectrum.yaml

key-decisions:
  - "Value 20 chosen as explicit threshold -- matches code default in wan_controller.py:534"

patterns-established: []

requirements-completed: [TUNE-01]

# Metrics
duration: 2min
completed: 2026-04-09
---

# Phase 157 Plan 01: Fix Dead Config Key Summary

**Replaced dead `suppression_alert_pct: 5.0` with code-matching `suppression_alert_threshold: 20` in spectrum.yaml**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T17:35:23Z
- **Completed:** 2026-04-09T17:37:22Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Removed dead config key `suppression_alert_pct: 5.0` that was never read by any code
- Added explicit `suppression_alert_threshold: 20` matching the key read at wan_controller.py:533-534
- Verified 37/40 hysteresis tests pass (3 pre-existing failures unrelated to this change)

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace dead suppression_alert_pct with suppression_alert_threshold** - No git commit (configs/spectrum.yaml is gitignored by design -- site-specific config)

**Plan metadata:** (included in SUMMARY commit)

_Note: configs/*.yaml are gitignored as site-specific files. The change was applied to the local development config. Production deploy will sync via deploy.sh._

## Files Created/Modified
- `configs/spectrum.yaml` - Replaced `suppression_alert_pct: 5.0` with `suppression_alert_threshold: 20` (line 71)

## Decisions Made
- Value 20 chosen as explicit threshold -- matches the code's existing default in wan_controller.py:534 (`cm_config.get("thresholds", {}).get("suppression_alert_threshold", 20)`)
- No code changes needed -- the code already reads the correct key with the correct default

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
- 3 pre-existing test failures in test_hysteresis_observability.py (TestHysteresisHealthEndpoint x2, TestSIGUSR1ChainIncludesSuppressionReload x1) confirmed unrelated to config change by running tests both with and without the change. These are from Phase 156 asymmetry gate code and a missing _reload_suppression_alert_config in autorate_continuous.py.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- spectrum.yaml now has correct suppression_alert_threshold key for Plan 02 baseline measurement
- Production deploy via deploy.sh will sync the corrected config

## Self-Check: PASSED
- 157-01-SUMMARY.md: FOUND
- configs/spectrum.yaml suppression_alert_threshold: 20: FOUND (count=1)
- configs/spectrum.yaml suppression_alert_pct: ABSENT (count=0)

---
*Phase: 157-hysteresis-re-tuning*
*Completed: 2026-04-09*

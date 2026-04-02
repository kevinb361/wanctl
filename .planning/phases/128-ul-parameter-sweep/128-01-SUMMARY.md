---
phase: 128-ul-parameter-sweep
plan: 01
subsystem: tuning
tags: [cable, docsis, linux-cake, upload, rrul, a-b-testing, flent]

# Dependency graph
requires:
  - phase: 127-dl-parameter-sweep
    provides: DL winners applied as baseline for UL testing
provides:
  - All 3 UL parameters validated on linux-cake transport
  - UL results documented in 127-DL-RESULTS.md and CABLE_TUNING.md
affects: [129-cake-rtt-confirmation, 130-production-config-commit]

# Tech tracking
tech-stack:
  added: []
  patterns: [cumulative-a-b-testing, ul-dl-independent-validation]

key-files:
  created: []
  modified:
    - .planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md
    - docs/CABLE_TUNING.md

key-decisions:
  - "UL step_up_mbps=2 wins over 1 on linux-cake -- faster feedback allows larger step without oscillation"
  - "UL factor_down=0.85 confirmed -- constrained upstream still needs aggressive RED decay regardless of transport"
  - "UL green_required=3 confirmed -- matches DL finding that linux-cake feedback makes 3 cycles sufficient"

patterns-established:
  - "UL/DL parameter convergence on linux-cake: both directions benefit from faster recovery (green_required=3)"
  - "Transport speed affects step sizing: linux-cake allows larger steps for both DL (15->10) and UL (1->2)"

requirements-completed: [TUNE-02]

# Metrics
duration: 8min
completed: 2026-04-02
---

# Phase 128 Plan 01: UL Parameter Sweep Summary

**3 UL parameters A/B tested on linux-cake transport -- step_up_mbps changed from 1 to 2, factor_down=0.85 and green_required=3 confirmed**

## Performance

- **Duration:** ~8 min (testing 17:53-18:01 CDT, documentation automated)
- **Started:** 2026-04-02T22:53:00Z
- **Completed:** 2026-04-02T23:10:00Z
- **Tasks:** 5 (4 checkpoint + 1 auto)
- **Files modified:** 2

## Accomplishments

- All 3 UL parameters (factor_down, step_up_mbps, green_required) tested on linux-cake transport with RRUL flent against Dallas netperf server
- 1 of 3 UL parameters changed: step_up_mbps 1->2 (faster feedback allows larger step)
- 2 of 3 UL parameters confirmed: factor_down=0.85, green_required=3
- Results documented in both 127-DL-RESULTS.md (detailed) and docs/CABLE_TUNING.md (reference guide)

## Task Commits

Each task was committed atomically:

1. **Task 0: Gate check and verify UL starting conditions** - checkpoint (human-verified)
2. **Task 1: Test UL factor_down (0.85 vs 0.90)** - checkpoint (human-verified, winner: 0.85)
3. **Task 2: Test UL step_up_mbps (1 vs 2)** - checkpoint (human-verified, winner: 2)
4. **Task 3: Test UL green_required (3 vs 5)** - checkpoint (human-verified, winner: 3)
5. **Task 4: Document UL results** - `da54dae` (docs)

## Files Created/Modified

- `.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` - Added UL Parameter Sweep section with 3 test results, summary table, key insight
- `docs/CABLE_TUNING.md` - Updated linux-cake UL params in recommended config, added UL Parameters subsection, updated UL vs DL note

## Test Results

| #   | Parameter         | Values Tested | Winner | Changed? | Key Metric                              |
| --- | ----------------- | ------------- | ------ | -------- | --------------------------------------- |
| 1   | UL factor_down    | 0.85 vs 0.90  | 0.85   | No       | median -17%, p99 -12%, throughput +40%  |
| 2   | UL step_up_mbps   | 1 vs 2        | 2      | YES      | median -12%, p99 -58%                   |
| 3   | UL green_required | 3 vs 5        | 3      | No       | median -20%, p99 -31%, throughput +178% |

### Final UL Configuration (linux-cake)

```yaml
continuous_monitoring:
  upload:
    factor_down: 0.85 # Confirmed (same as REST)
    step_up_mbps: 2 # Changed from 1 (was REST winner)
    green_required: 3 # Confirmed (matches DL linux-cake finding)
```

## Decisions Made

- UL step_up_mbps=2 selected over 1: p99 improvement (-58%) outweighs slight throughput loss (-19%), and the latency reduction is the primary goal for bufferbloat control
- UL green_required=3 confirmed despite REST finding of 5: linux-cake's faster feedback loop makes 3 cycles sufficient for both DL and UL directions
- UL factor_down=0.85 confirmed: the constrained ~38 Mbps upstream still needs aggressive RED decay regardless of transport speed

## Deviations from Plan

None -- plan executed exactly as written. All 4 checkpoint tasks completed by operator, Task 4 automated documentation executed as specified.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required.

## Known Stubs

None -- all data is wired from actual A/B test results.

## Next Phase Readiness

- All UL parameters validated, ready for Phase 129 (CAKE RTT + Confirmation Pass)
- Phase 129 will test CAKE rtt parameter and re-test response group for interaction effects
- Production VM currently running with all DL + UL winners applied via SIGUSR1

## Self-Check: PASSED

- FOUND: .planning/phases/128-ul-parameter-sweep/128-01-SUMMARY.md
- FOUND: .planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md
- FOUND: docs/CABLE_TUNING.md
- FOUND: da54dae (Task 4 commit)

---

_Phase: 128-ul-parameter-sweep_
_Completed: 2026-04-02_

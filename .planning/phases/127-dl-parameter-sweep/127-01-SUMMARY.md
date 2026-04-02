---
phase: 127-dl-parameter-sweep
plan: 01
subsystem: tuning
tags: [cable, docsis, linux-cake, rrul, a-b-testing, flent, parameter-sweep]

requires:
  - phase: 126-pre-test-gate
    provides: Verified linux-cake transport active, CAKE qdiscs on VM, no double-shaping
provides:
  - "Validated DL parameter set for linux-cake transport (9 params, 6 changed)"
  - "REST vs linux-cake comparison table in CABLE_TUNING.md"
  - "Raw A/B test data in 127-DL-RESULTS.md"
affects:
  [
    128-ul-parameter-sweep,
    129-cake-rtt-confirmation,
    130-production-config-commit,
  ]

tech-stack:
  added: []
  patterns:
    [
      "linux-cake A/B methodology: cumulative winners, RRUL flent, SIGUSR1 reload",
    ]

key-files:
  created:
    - ".planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md"
  modified:
    - "docs/CABLE_TUNING.md"

key-decisions:
  - "6 of 9 DL params changed from REST values: green_required=3, step_up=10, factor_down=0.85, target_bloat=15, warn_bloat=60, hard_red=100"
  - "3 params confirmed transport-independent (DOCSIS-intrinsic): factor_down_yellow=0.92, dwell_cycles=5, deadband_ms=3.0"
  - "linux-cake faster feedback shifts tuning toward less aggressive response + wider thresholds"

patterns-established:
  - "Transport-specific tuning: same controller code, different optimal parameters per transport backend"
  - "DOCSIS-intrinsic vs transport-dependent parameter classification"

requirements-completed: [TUNE-01, RSLT-01]

duration: 40min
completed: 2026-04-02
---

# Phase 127 Plan 01: DL Parameter Sweep Summary

**9 DL parameters A/B tested on linux-cake transport via RRUL flent -- 6 of 9 changed from REST-validated values, revealing transport-dependent tuning shift toward gentler response and wider thresholds**

## Performance

- **Duration:** ~40 min (17:00-17:36 CDT test window + documentation)
- **Started:** 2026-04-02T22:00:00Z (approximate)
- **Completed:** 2026-04-02T22:45:00Z
- **Tasks:** 11 (1 gate + 9 human A/B tests + 1 auto documentation)
- **Files modified:** 2

## Accomplishments

- All 9 DL parameters tested sequentially with cumulative winners on linux-cake transport
- Discovered that linux-cake's faster feedback loop (~0.1ms vs ~15-30ms REST) fundamentally shifts optimal tuning
- Updated CABLE_TUNING.md with complete REST-vs-linux-cake comparison and recommended linux-cake parameters
- Classified parameters as DOCSIS-intrinsic (3 unchanged) vs transport-dependent (6 changed)

## Task Commits

Each checkpoint task was executed by the human operator on production. The auto task was committed:

1. **Tasks 0-9: A/B testing** - Human-executed on cake-shaper VM (no git commits)
2. **Task 10: Documentation** - `c14f920` (docs: results + CABLE_TUNING.md update)

**Plan metadata:** (this commit)

## Files Created/Modified

- `.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` - Raw A/B test data for all 9 parameters with metrics, winners, and analysis
- `docs/CABLE_TUNING.md` - Added linux-cake Transport Results section with REST comparison table, recommended parameters, and rationale

## Decisions Made

1. **green_required: 5 -> 3** - Faster recovery safe on linux-cake; REST needed 5 to compensate for stale data
2. **step_up_mbps: 15 -> 10** - Smaller steps avoid overshoot with faster feedback loop
3. **factor_down: 0.90 -> 0.85** - Deeper RED cuts resolve congestion faster with direct tc
4. **target_bloat_ms: 9 -> 15** - CAKE AQM handles small buildups; tight threshold unnecessary on linux-cake
5. **warn_bloat_ms: 45 -> 60** - Spacing between thresholds preserved (45ms headroom vs 36ms on REST)
6. **hard_red_bloat_ms: 60 -> 100** - Needs operating room above warn_bloat=60 for SOFT_RED to work

## Deviations from Plan

None - plan executed exactly as written. All 9 parameters tested sequentially with cumulative winners applied.

## Issues Encountered

None. Cable plant conditions were consistent throughout the 36-minute test window (afternoon load, Spectrum DOCSIS).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 128 (UL Parameter Sweep) ready to execute immediately
- 3 UL parameters to test: step_up_mbps, factor_down, green_required
- All DL winners already applied on production VM
- Phase 129 (CAKE RTT + Confirmation) depends on 128 completing first

## Self-Check: PASSED

- 127-DL-RESULTS.md: FOUND (10 winner entries)
- 127-01-SUMMARY.md: FOUND
- docs/CABLE_TUNING.md: FOUND (linux-cake Transport section present)
- Commit c14f920: FOUND

---

_Phase: 127-dl-parameter-sweep_
_Completed: 2026-04-02_

---
phase: 02-interval-optimization
plan: 01
subsystem: performance
tags: [interval-optimization, ewma, steering, cycle-time, 250ms]

# Dependency graph
requires:
  - phase: 01-profiling
    provides: Baseline performance metrics (30-41ms cycle execution, 96% headroom available)
provides:
  - 250ms cycle interval operational (2x faster than 500ms)
  - EWMA time constants preserved via alpha adjustments
  - Steering threshold timing preserved via sample count adjustments
  - Initial stability validation (zero errors, stable baselines, <3% router CPU)
affects: [02-02-100ms-testing, 02-03-50ms-testing, production-finalization]

# Tech tracking
tech-stack:
  added: []
  patterns: [time-constant-preservation, sample-count-scaling]

key-files:
  created:
    - docs/INTERVAL_TESTING_250MS.md
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - configs/spectrum.yaml (not in git)
    - configs/att.yaml (not in git)
    - configs/steering_config_v2.yaml (not in git)

key-decisions:
  - "Reduced EWMA alphas by 2x to preserve time constants (100s baseline, 10s load)"
  - "Increased steering sample counts by 2x to preserve wall-clock timing (4s RED, 30s GREEN)"
  - "Increased history sizes by 2x to maintain 2-minute windows"
  - "User decision: Skip 24-48h extended monitoring, proceed to 50ms testing (fail-fast approach)"

patterns-established:
  - "Mathematical scaling: interval decrease Nx → alpha decrease Nx, sample counts increase Nx"
  - "Time-constant preservation: wall-clock behavior maintained across interval changes"

issues-created: []

# Metrics
duration: 28min
completed: 2026-01-13
---

# Phase 2 Plan 1: 250ms Interval Testing Summary

**250ms cycle interval deployed with perfect stability - 2x faster congestion response operational**

## Performance

- **Duration:** 28 minutes
- **Started:** 2026-01-13T18:43:59Z
- **Completed:** 2026-01-13T19:11:56Z
- **Tasks:** 4/4 completed
- **Files modified:** 5 (2 Python, 3 YAML configs)

## Accomplishments

- Calculated and deployed 250ms interval parameters with mathematical verification
- Updated EWMA alphas (2x reduction) to preserve time constants
- Updated steering thresholds (2x sample increases) to preserve wall-clock timing
- Deployed to production on both WANs (Spectrum + ATT)
- Validated initial stability: zero errors, perfect timing, stable baselines
- Documented findings in INTERVAL_TESTING_250MS.md

## Task Commits

Each task was committed atomically:

1. **Task 1: Calculate and apply 250ms parameters** - `e0a90ec` (feat)
   - CYCLE_INTERVAL_SECONDS: 0.5s → 0.25s
   - EWMA alphas reduced 2x (Spectrum, ATT)
   - Steering thresholds doubled (red_samples: 2→16, green_samples: 15→120)
   - MAX_HISTORY_SAMPLES: 240→480

2. **Task 2: Deploy to production** - `17ad12c` (feat)
   - Deployed configs to cake-spectrum and cake-att containers
   - Restarted wanctl@spectrum, wanctl@att, steering services
   - Verified 250ms cycle timing in logs

3. **Task 3: Monitor stability (checkpoint)** - No separate commit (checkpoint approved inline)
   - Initial monitoring: 5 minutes active observation
   - Verified: zero errors, stable baselines, perfect timing, router CPU 1-3%
   - User decision: Skip extended monitoring, proceed to 50ms

4. **Task 4: Document findings** - `88cdc5f` (docs)
   - Created comprehensive testing document
   - Documented parameters, results, observations, recommendations

**Plan metadata:** (this commit) - `docs(02-01): complete 250ms interval testing plan`

## Files Created/Modified

**Created:**
- `docs/INTERVAL_TESTING_250MS.md` - Comprehensive test results and analysis

**Modified (Python):**
- `src/wanctl/autorate_continuous.py` - CYCLE_INTERVAL_SECONDS = 0.25
- `src/wanctl/steering/daemon.py` - MAX_HISTORY_SAMPLES = 480, ASSESSMENT_INTERVAL_SECONDS = 0.25

**Modified (YAML, not in git):**
- `configs/spectrum.yaml` - alpha_baseline: 0.005→0.0025, alpha_load: 0.05→0.025
- `configs/att.yaml` - alpha_baseline: 0.00375→0.001875, alpha_load: 0.05→0.025
- `configs/steering_config_v2.yaml` - interval_seconds: 2→0.25, red_samples: 2→16, green_samples: 15→120, history_size: 60→480

## Decisions Made

**1. Time-constant preservation via alpha scaling**
- Rationale: When interval decreases Nx, alpha must decrease ~Nx to maintain same wall-clock smoothing behavior
- Result: 100s baseline and 10s load time constants preserved exactly

**2. Sample count scaling for steering thresholds**
- Rationale: RED/GREEN activation based on sustained condition duration (wall-clock), not sample count
- Result: 4s RED activation and 30s GREEN recovery preserved exactly (16×0.25s, 120×0.25s)

**3. Skip extended 24-48h monitoring**
- Rationale: User prefers fail-fast approach - push to limits immediately rather than incremental validation
- Result: Proceeding directly to 50ms testing (plan 02-03) to find actual performance limits

**4. Config files not committed to git**
- Rationale: Config files contain deployment-specific settings and secrets
- Result: Only Python source changes tracked in git, configs deployed separately

## Deviations from Plan

None - plan executed exactly as written, including checkpoint approval.

## Issues Encountered

None - deployment and initial monitoring completed without any issues.

## Initial Stability Results

**Cycle Timing:**
- Spectrum: 247-253ms (±1.2% variance, normal for cable)
- ATT: 249-251ms (±0.4% variance, exceptional consistency)

**Baseline RTT Stability:**
- Spectrum: 25.8ms baseline, <1ms drift observed
- ATT: 28.0ms baseline, 0ms drift (rock solid)

**Router CPU Impact:**
- MikroTik RB5009: 1-3% CPU (4x polling rate)
- Headroom: 96% (target <30%)
- Negligible impact from interval reduction

**Error Count:**
- Spectrum: 0 errors/warnings
- ATT: 0 errors/warnings
- Steering: 0 errors/warnings

**System State:**
- Both WANs: GREEN/GREEN throughout monitoring
- No oscillation or flapping
- Flash wear protection working (redundant updates skipped)

## Mathematical Verification

All time constants verified to preserve wall-clock behavior:

| Time Constant | Formula | Result | Status |
|---------------|---------|--------|--------|
| Baseline (Spectrum) | 400 samples × 0.25s | 100s | ✓ |
| Load (Spectrum) | 40 samples × 0.25s | 10s | ✓ |
| Baseline (ATT) | 533 samples × 0.25s | 133s | ✓ |
| Load (ATT) | 40 samples × 0.25s | 10s | ✓ |
| RED activation | 16 samples × 0.25s | 4s | ✓ |
| GREEN recovery | 120 samples × 0.25s | 30s | ✓ |
| History window | 480 samples × 0.25s | 120s (2min) | ✓ |

## Next Phase Readiness

**Ready for:** 02-03-PLAN.md (50ms interval testing)

**Rationale:** User prefers fail-fast approach. Skipping incremental 100ms test (02-02) to immediately test theoretical performance limit (50ms is ~80% of cycle execution time).

**Blockers:** None

**Concerns:**
- 50ms represents 20x faster than original 1s interval
- Cycle execution (30-41ms) approaches interval time (50ms)
- May hit scheduler timing limitations
- Aggressive test to find actual system limits

**Recommendations:**
1. Proceed to 50ms testing (02-03) with caution
2. Monitor for timing violations (cycles exceeding 50ms)
3. Watch for cycle skipping or delayed execution
4. Be prepared for immediate rollback if unstable

---

*Phase: 02-interval-optimization*
*Plan: 01 of 3*
*Completed: 2026-01-13*
*Next: 02-03-PLAN.md (50ms extreme interval test)*

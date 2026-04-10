---
phase: 103-fix-fusion-baseline-deadlock
plan: 01
subsystem: autorate
tags: [ewma, baseline, fusion, irtt, signal-processing, deadlock-fix]

# Dependency graph
requires:
  - phase: 96-dual-signal-fusion-core
    provides: _compute_fused_rtt, fusion ICMP/IRTT weighting
provides:
  - Split signal path: fused RTT for load EWMA, ICMP-only for baseline EWMA
  - Fixes baseline freeze/corruption when IRTT path diverges from ICMP
  - icmp_rtt parameter semantics in _update_baseline_if_idle
affects: [adaptive-tuning, congestion-thresholds]

# Tech tracking
tech-stack:
  added: []
  patterns: [signal-path-split, icmp-only-baseline]

key-files:
  created:
    - tests/test_fusion_baseline.py
  modified:
    - src/wanctl/autorate_continuous.py
    - tests/test_autorate_baseline_bounds.py
    - tests/test_autorate_error_recovery.py
    - tests/test_wan_controller.py

key-decisions:
  - "Inline load EWMA in run_cycle instead of modifying update_ewma signature (preserves ~32 test call sites)"
  - "Freeze gate delta uses icmp_rtt - baseline_rtt (instantaneous ICMP, not EWMA-smoothed) -- Hampel filter provides sufficient noise rejection"
  - "update_ewma() method preserved unchanged for backward compatibility -- run_cycle() bypasses it"

patterns-established:
  - "Signal path split: fused for load_rtt (congestion sensitivity), ICMP-only for baseline_rtt (idle reference)"
  - "Baseline is an ICMP-derived concept -- never contaminate with fused/IRTT signals"

requirements-completed: [FBLK-01, FBLK-02, FBLK-03, FBLK-04, FBLK-05]

# Metrics
duration: 44min
completed: 2026-03-19
---

# Phase 103 Plan 01: Fix Fusion Baseline Deadlock Summary

**Split EWMA signal path in run_cycle: fused RTT drives load_rtt for congestion sensitivity, ICMP-only filtered_rtt drives baseline_rtt to prevent IRTT path divergence from freezing or corrupting baseline**

## Performance

- **Duration:** 44 min
- **Started:** 2026-03-19T13:53:53Z
- **Completed:** 2026-03-19T14:38:48Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- Fixed fusion baseline deadlock where IRTT path divergence (ATT: 43ms IRTT vs 29ms ICMP) permanently froze baseline via persistent delta > 3ms threshold
- Split run_cycle signal path: load_rtt EWMA uses fused signal, _update_baseline_if_idle uses ICMP-only filtered_rtt
- Changed freeze gate delta from `self.load_rtt - self.baseline_rtt` to `icmp_rtt - self.baseline_rtt`
- 9 new regression tests across 5 classes covering all FBLK requirements
- 3676 total tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for fusion baseline deadlock (RED)** - `ebbb7e0` (test)
2. **Task 2: Fix signal path split in autorate_continuous.py (GREEN)** - `ecfce90` (feat)

## Files Created/Modified
- `tests/test_fusion_baseline.py` - 9 tests across 5 classes covering FBLK-01 through FBLK-05 (330 lines)
- `src/wanctl/autorate_continuous.py` - Split EWMA in run_cycle, renamed _update_baseline_if_idle parameter to icmp_rtt, fixed delta computation
- `tests/test_wan_controller.py` - Updated 3 bounds tests for new delta semantics (icmp_rtt within threshold distance)
- `tests/test_autorate_baseline_bounds.py` - Updated 5 bounds tests: keyword rename measured_rtt -> icmp_rtt, adjusted values for new delta gate
- `tests/test_autorate_error_recovery.py` - Updated 2 TCP fallback tests: no longer mock update_ewma (run_cycle inlines EWMA)

## Decisions Made
- Inline load EWMA in run_cycle rather than modifying update_ewma() signature -- preserves ~32 test call sites that call update_ewma() directly
- Freeze gate delta uses instantaneous `icmp_rtt - baseline_rtt` instead of adding a second ICMP-only load EWMA -- Hampel filter already removes outliers, no additional smoothing needed
- update_ewma() preserved unchanged for backward compatibility -- run_cycle() bypasses it with the split path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 3 bounds tests in test_wan_controller.py**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Tests set icmp_rtt values far from baseline (e.g., 200.0 with baseline=90.0), causing delta >= threshold which freezes baseline before reaching bounds check code
- **Fix:** Adjusted test values so icmp_rtt is within threshold distance of baseline while still exercising bounds rejection (e.g., baseline=99.0, icmp_rtt=101.5, alpha=0.5 -> new_baseline=100.25 > max 100.0)
- **Files modified:** tests/test_wan_controller.py
- **Verification:** All 5 TestBaselineRttBoundsRejection tests pass
- **Committed in:** ecfce90 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed 5 bounds tests in test_autorate_baseline_bounds.py**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Tests used `measured_rtt=` keyword argument (renamed to `icmp_rtt`) and some used values too far from baseline for new delta gate
- **Fix:** Renamed keyword to `icmp_rtt=`, adjusted values for test_baseline_above_max_rejected, test_baseline_within_bounds_accepted, and test_baseline_at_max_boundary_accepted
- **Files modified:** tests/test_autorate_baseline_bounds.py
- **Verification:** All 5 TestBaselineBoundsValidation tests pass
- **Committed in:** ecfce90 (Task 2 commit)

**3. [Rule 1 - Bug] Fixed 2 TCP fallback tests in test_autorate_error_recovery.py**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Tests patched `update_ewma` and asserted it was called, but run_cycle no longer calls update_ewma (inlines the EWMA split instead)
- **Fix:** Removed update_ewma mock, verify load_rtt changed instead (proves TCP RTT flowed through signal path)
- **Files modified:** tests/test_autorate_error_recovery.py
- **Verification:** Both tests pass, full suite green
- **Committed in:** ecfce90 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bug fixes in existing tests)
**Impact on plan:** All auto-fixes necessary to maintain test correctness after semantic change in _update_baseline_if_idle. No scope creep.

## Issues Encountered
None -- fix was minimal and well-scoped as planned.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Fusion baseline deadlock is fixed, baseline correctly tracks ICMP idle
- Congestion zone delta (load_rtt - baseline_rtt) now represents fused_load vs icmp_baseline -- slightly different magnitude than pre-fix but directionally correct
- Adaptive tuning (Phases 98-102) can proceed with correct baseline semantics
- Production deployment: old baseline values in state files will naturally converge to ICMP-only baseline over time (no migration needed)

---
*Phase: 103-fix-fusion-baseline-deadlock*
*Completed: 2026-03-19*

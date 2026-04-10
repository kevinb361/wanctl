---
phase: 47-cycle-profiling-infrastructure
plan: 01
subsystem: profiling
tags: [perf_timer, operation_profiler, monotonic_timing, cycle_profiling]

# Dependency graph
requires: []
provides:
  - "PerfTimer instrumentation in WANController.run_cycle() with 4 labeled subsystem timers"
  - "PerfTimer instrumentation in SteeringDaemon.run_cycle() with 4 labeled subsystem timers"
  - "OperationProfiler(max_samples=1200) accumulation in both daemons"
  - "--profile CLI flag on both daemons for periodic profiling reports"
affects: [48-hot-path-optimization, 49-telemetry-monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PerfTimer context manager wrapping subsystem blocks in run_cycle()"
    - "_record_profiling() helper for recording + periodic report emission"
    - "Flag-based early return pattern to preserve PerfTimer elapsed_ms accuracy"

key-files:
  created: []
  modified:
    - "src/wanctl/autorate_continuous.py"
    - "src/wanctl/steering/daemon.py"
    - "tests/test_autorate_continuous.py"
    - "tests/test_steering_daemon.py"

key-decisions:
  - "save_state() stays AFTER router communication (not inside state_management timer) to preserve original error-path behavior"
  - "Flag-based early returns instead of returning inside PerfTimer blocks, ensuring elapsed_ms is captured in __exit__"
  - "anomaly_detected flag pattern in steering to preserve timer measurement even on delta > MAX_SANE_RTT_DELTA_MS"

patterns-established:
  - "PerfTimer wrapping: use flag variables for early returns, check flags after timer block exits"
  - "Profiling report interval: PROFILE_REPORT_INTERVAL = 1200 cycles (60s at 50ms)"
  - "_record_profiling() helper centralizes all profiler.record() + periodic report logic"

requirements-completed: [PROF-01, PROF-02]

# Metrics
duration: 23min
completed: 2026-03-06
---

# Phase 47 Plan 01: Cycle Profiling Instrumentation Summary

**Per-subsystem PerfTimer instrumentation in both autorate and steering run_cycle() with OperationProfiler accumulation and --profile CLI flag for periodic reports**

## Performance

- **Duration:** 23 min
- **Started:** 2026-03-06T17:06:51Z
- **Completed:** 2026-03-06T17:29:32Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Autorate WANController.run_cycle() wraps 3 subsystems (rtt_measurement, state_management, router_communication) with PerfTimer and records 4 labels including cycle_total
- Steering SteeringDaemon.run_cycle() wraps 3 subsystems (cake_stats, rtt_measurement, state_management) with PerfTimer and records 4 labels including cycle_total
- Both daemons accumulate timing in OperationProfiler(max_samples=1200) with periodic report every 1200 cycles when --profile flag is set
- 14 new TDD tests (7 per daemon) covering all profiling labels, report emission, and CLI flag
- 1909 total tests pass, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Instrument autorate daemon with per-subsystem profiling** - `90d6177` (feat)
2. **Task 2: Instrument steering daemon with per-subsystem profiling** - `d41a3be` (feat)

## Files Created/Modified
- `src/wanctl/autorate_continuous.py` - Added PerfTimer/OperationProfiler imports, PROFILE_REPORT_INTERVAL constant, _profiler/_profiling_enabled attrs, _record_profiling() helper, PerfTimer wrapping in run_cycle(), --profile argparse flag
- `src/wanctl/steering/daemon.py` - Same pattern as autorate: imports, constant, attrs, helper, timer wrapping, --profile flag
- `tests/test_autorate_continuous.py` - TestProfilingInstrumentation class with 7 tests
- `tests/test_steering_daemon.py` - TestSteeringProfilingInstrumentation class with 7 tests

## Decisions Made
- **save_state() placement:** Kept save_state() AFTER router communication block (not inside state_management timer) to preserve original behavior where save_state is not called on router failure. Two existing tests explicitly verify this contract.
- **Flag-based early returns:** Instead of returning inside PerfTimer context manager blocks (where elapsed_ms is still 0.0), used flag variables (rtt_early_return, router_failed, anomaly_detected) and checked them after timer blocks exit. This ensures accurate timing capture.
- **cycle_start uses perf_counter:** Changed from time.monotonic() to time.perf_counter() for cycle_start, matching PerfTimer's high-precision timing source.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed save_state placement to preserve error-path behavior**
- **Found during:** Task 2 (full test suite regression check)
- **Issue:** Plan instructed moving save_state() inside state_management timer, but this caused it to execute before router communication, breaking the invariant that save_state is not called on router failure
- **Fix:** Moved save_state() and record_autorate_cycle() back to after router communication block, outside any PerfTimer
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** test_router_failure_does_not_save_state and test_run_cycle_does_not_save_on_failure pass
- **Committed in:** d41a3be (Task 2 commit)

**2. [Rule 1 - Bug] Fixed PerfTimer elapsed_ms access pattern**
- **Found during:** Task 1 (implementation analysis)
- **Issue:** Plan showed returning inside PerfTimer blocks with rtt_timer.elapsed_ms, but elapsed_ms is only set in __exit__ which hasn't fired yet
- **Fix:** Used flag-based early return pattern (set flag inside timer, check after block exits)
- **Files modified:** src/wanctl/autorate_continuous.py, src/wanctl/steering/daemon.py
- **Verification:** All profiling tests pass with correct timing values
- **Committed in:** 90d6177, d41a3be

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep. Timer labels and profiling behavior match plan exactly.

## Issues Encountered
- Import sorting: ruff flagged unsorted imports after adding perf_profiler import. Auto-fixed with `ruff check --fix`.
- mypy type narrowing: After restructuring run_cycle with flag-based returns, mypy couldn't prove measured_rtt was not None. Added assert for type safety.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both daemons fully instrumented with per-subsystem timing
- --profile flag available for production profiling data collection
- OperationProfiler accumulation ready for Phase 48 optimization analysis
- Timer labels: autorate_{rtt_measurement, router_communication, state_management, cycle_total} and steering_{cake_stats, rtt_measurement, state_management, cycle_total}

---
*Phase: 47-cycle-profiling-infrastructure*
*Completed: 2026-03-06*

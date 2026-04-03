---
phase: 131-cycle-budget-profiling
plan: 02
subsystem: profiling
tags: [py-spy, flamegraph, rrul, cycle-budget, rtt-measurement, icmp, profiling]

# Dependency graph
requires:
  - phase: 131-01
    provides: 6 sub-timers in run_cycle + health endpoint subsystems breakdown
provides:
  - Per-subsystem timing data under idle and RRUL load (3 profiling runs)
  - py-spy flamegraph SVG showing per-function CPU usage during RRUL
  - Analysis document identifying top 3 cycle-time consumers with measured durations
  - Phase 132 recommendation: optimize RTT measurement path (short-term) + non-blocking I/O (medium-term)
affects: [132-cycle-budget-optimization]

# Tech tracking
tech-stack:
  added: [py-spy]
  patterns:
    - "3-run profiling methodology: 1 idle baseline + 2 RRUL loaded"
    - "py-spy at 200Hz for 30s captures ~4300 samples"
    - "Health endpoint subsystems as primary profiling data source"

key-files:
  created:
    - .planning/phases/131-cycle-budget-profiling/131-ANALYSIS.md
  modified: []

key-decisions:
  - "RTT measurement is the bottleneck (84.6% of budget), not SQLite metrics writing (6.6%)"
  - "Recommended Phase 132 approach: Option A (optimize RTT path) + Option D (non-blocking I/O)"
  - "50ms cycle interval should be preserved -- optimization preferred over wider interval"

patterns-established:
  - "Production profiling via deploy + flent RRUL + health endpoint capture + py-spy"

requirements-completed: [PERF-01]

# Metrics
duration: 35min
completed: 2026-04-03
---

# Phase 131 Plan 02: Production Profiling and Analysis Summary

**RTT measurement consumes 84.6% of 50ms cycle budget under RRUL load (42ms avg, p99=116ms); SQLite hypothesis disproven at 6.6%; Phase 132 to optimize ICMP path + non-blocking I/O**

## Performance

- **Duration:** ~35 min (deploy + 3 profiling runs + analysis + checkpoint)
- **Started:** 2026-04-03T08:22:00Z
- **Completed:** 2026-04-03T09:00:00Z
- **Tasks:** 3 (2 auto + 1 checkpoint)
- **Files modified:** 1

## Accomplishments

- Deployed instrumented code to production and collected 3 profiling runs (1 idle + 2 RRUL loaded)
- Captured py-spy flamegraph (4316 samples at 200Hz) confirming RTT measurement path as dominant consumer
- Disproved pre-profiling hypothesis: SQLite metrics writing averages only 3.3ms (not 40-60ms assumed)
- Identified top 3 consumers: rtt_measurement (42.3ms/84.6%), router_communication (3.4ms/6.8%), logging_metrics (3.3ms/6.6%)
- Produced analysis document with concrete Phase 132 recommendation approved by operator

## Task Commits

Each task was committed atomically:

1. **Task 1: Deploy instrumentation and collect profiling data** - `fa8ce11` (feat)
2. **Task 2: Write analysis document** - `fa8ce11` (feat) (combined with Task 1)
3. **Task 3: Verify profiling results and approve Phase 132 recommendation** - checkpoint (approved)

## Files Created/Modified

- `.planning/phases/131-cycle-budget-profiling/131-ANALYSIS.md` - Complete profiling analysis with 3 timing tables, top 3 consumers, py-spy flamegraph analysis, idle vs load comparison, and Phase 132 recommendation

## Decisions Made

- **RTT measurement is the real bottleneck:** 42.3ms avg under load (84.6% of 50ms budget). The ThreadPoolExecutor + ICMP ping chain is the dominant cost, not SQLite.
- **SQLite hypothesis disproven:** logging_metrics averages only 3.3ms (6.6%), far below the 40-60ms pre-profiling assumption.
- **Phase 132 recommendation approved:** Option A (optimize RTT measurement path -- reduce hosts, tighten timeouts) for immediate relief + Option D (non-blocking RTT architecture) for long-term fix.
- **Preserve 50ms interval:** Optimization preferred over widening to 75ms, which would sacrifice sub-second congestion detection.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - profiling is complete and py-spy was installed as planned.

## Next Phase Readiness

- Phase 132 has clear optimization targets: rtt_measurement path (84.6% of budget)
- Analysis document provides 4 options (A-D) with Phase 132 recommendation: A + D
- Flamegraph and sub-timer data available for detailed function-level optimization planning

## Self-Check: PASSED

All files exist, all commits verified.

---

_Phase: 131-cycle-budget-profiling_
_Completed: 2026-04-03_

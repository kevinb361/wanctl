---
phase: 79-connectivity-anomaly-alerts
plan: 01
subsystem: alerting
tags: [icmp, connectivity, wan-offline, recovery, monotonic-timer]

# Dependency graph
requires:
  - phase: 78-congestion-steering-alerts
    provides: "_check_congestion_alerts pattern, AlertEngine wiring, sustained timer model"
provides:
  - "_check_connectivity_alerts() method with wan_offline/wan_recovered alert types"
  - "raw_measured_rtt capture in run_cycle() for pre-fallback ICMP tracking"
affects: [79-02, health-endpoint, dashboard-alerts]

# Tech tracking
tech-stack:
  added: []
  patterns: ["connectivity sustained timer with recovery gate (ALRT-04/05)"]

key-files:
  created:
    - tests/test_connectivity_alerts.py
  modified:
    - src/wanctl/autorate_continuous.py

key-decisions:
  - "raw_measured_rtt captured before fallback processing so connectivity alerts track actual ICMP reachability"
  - "Connectivity alerts called inside PerfTimer block (before early return) to track both online and offline cycles"

patterns-established:
  - "raw_measured_rtt pattern: capture measure_rtt() result before handle_icmp_failure() modifies it"

requirements-completed: [ALRT-04, ALRT-05]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 79 Plan 01: Connectivity Alerts Summary

**WAN offline detection after 30s sustained ICMP failure with recovery gate and per-rule sustained_sec override**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T16:14:54Z
- **Completed:** 2026-03-12T16:17:57Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- wan_offline fires with severity=critical after configurable sustained_sec (default 30s) of all ICMP targets unreachable
- wan_recovered fires with severity=recovery when ICMP returns, includes outage_duration_sec and current_rtt
- Recovery gate: wan_recovered only fires if wan_offline actually fired (brief glitches suppressed)
- Per-rule sustained_sec override consistent with Phase 78 congestion alert pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: WAN offline/recovery detection** (TDD)
   - RED: `4519619` (test) - 11 failing tests for offline/recovery detection
   - GREEN: `e80e001` (feat) - Implementation passing all 11 tests

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `tests/test_connectivity_alerts.py` - 11 tests covering offline detection, recovery gate, per-rule override, cooldown, timer reset
- `src/wanctl/autorate_continuous.py` - \_check_connectivity_alerts() method, connectivity timer state vars, raw_measured_rtt in run_cycle()

## Decisions Made

- Captured raw_measured_rtt before fallback processing so connectivity alerts track actual ICMP reachability (not fallback-substituted values)
- Placed \_check_connectivity_alerts call inside the PerfTimer block before rtt_early_return check so both online and offline cycles are tracked

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Connectivity alerts ready; Phase 79 plan 02 (high RTT anomaly detection) can proceed
- wan_offline and wan_recovered alert types available in AlertEngine rules config

## Self-Check: PASSED

All files exist. All commits verified.

---

_Phase: 79-connectivity-anomaly-alerts_
_Completed: 2026-03-12_

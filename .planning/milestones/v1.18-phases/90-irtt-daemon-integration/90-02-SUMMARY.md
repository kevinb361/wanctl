---
phase: 90-irtt-daemon-integration
plan: 02
subsystem: measurement
tags: [irtt, protocol-correlation, daemon, threading, icmp, udp]

# Dependency graph
requires:
  - phase: 90-irtt-daemon-integration plan 01
    provides: IRTTThread, IRTTMeasurement, IRTTResult, cadence_sec config
provides:
  - IRTTThread wired into autorate daemon lifecycle (start/stop)
  - Cached IRTT result read each cycle (zero blocking)
  - ICMP/UDP protocol correlation with deprioritization detection
  - _start_irtt_thread() helper and _check_protocol_correlation() method
affects: [92-metrics-observability, health-endpoint, signal-fusion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      protocol-correlation-ratio,
      first-detect-repeat-recovery-logging,
      autouse-mock-fixture,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/autorate_continuous.py
    - tests/test_irtt_thread.py
    - tests/test_autorate_entry_points.py

key-decisions:
  - "Protocol correlation thresholds: ratio > 1.5 (ICMP deprioritized) or < 0.67 (UDP deprioritized)"
  - "Stale IRTT results (>3x cadence) skip correlation and set _irtt_correlation to None"
  - "IRTT thread stopped in finally block step 0.5 (after state save, before lock cleanup)"
  - "Autouse _mock_irtt_thread fixture in entry point tests prevents MagicMock thread starts when irtt binary is installed"

patterns-established:
  - "Protocol correlation ratio: load_rtt / irtt_rtt_mean_ms with thresholds 1.5/0.67"
  - "First-detect/repeat/recovery log pattern: INFO on first detection, DEBUG on repeat, INFO on recovery"
  - "Test harness pattern: _make_controller_harness() binds real WANController method to MagicMock attrs"

requirements-completed: [IRTT-03, IRTT-07]

# Metrics
duration: 19min
completed: 2026-03-16
---

# Phase 90 Plan 02: IRTT Daemon Integration Summary

**IRTTThread wired into autorate daemon lifecycle with cached result reads each cycle, ICMP/UDP protocol correlation, and deprioritization detection at ratio > 1.5 or < 0.67**

## Performance

- **Duration:** 19 min
- **Started:** 2026-03-16T22:12:56Z
- **Completed:** 2026-03-16T22:31:56Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- IRTTThread lifecycle wired into main() (started after health server, stopped in finally block before locks)
- Cached IRTT result read each run_cycle() at DEBUG with zero blocking (IRTT-03)
- Protocol correlation computed: ICMP/UDP ratio with deprioritization thresholds (IRTT-07)
- First-detect at INFO, repeat at DEBUG, recovery at INFO log pattern
- 13 new tests (11 TestProtocolCorrelation + 2 TestStartIRTTThread), all 3196 passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire IRTTThread into main() and run_cycle() with protocol correlation** - `6cb7b9c` (feat)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Added imports, \_irtt_thread/\_irtt_correlation state attrs, cached result read in run_cycle(), \_check_protocol_correlation(), \_start_irtt_thread() helper, shutdown in finally block
- `tests/test_irtt_thread.py` - Added TestProtocolCorrelation (11 tests) and TestStartIRTTThread (2 tests)
- `tests/test_autorate_entry_points.py` - Added autouse \_mock_irtt_thread fixture to prevent MagicMock thread starts

## Decisions Made

- Protocol correlation thresholds: ratio > 1.5 (ICMP deprioritized) or < 0.67 (UDP deprioritized) -- standard ISP throttling detection thresholds
- Stale IRTT results (>3x cadence) skip correlation, clearing \_irtt_correlation to None
- IRTT thread stopped at step 0.5 in finally block (after state save, before lock cleanup) -- matches daemon shutdown priority order
- Added autouse fixture in test_autorate_entry_points.py because irtt binary is installed on dev machine, causing MagicMock cadence_sec to start real threads

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added autouse \_mock_irtt_thread fixture in entry point tests**

- **Found during:** Task 1 (verification step)
- **Issue:** Entry point tests use MagicMock configs where irtt_config is a MagicMock. With irtt binary installed on dev machine, \_start_irtt_thread() would create a real IRTTThread with MagicMock cadence_sec, causing TypeError in threading.Event.wait()
- **Fix:** Added autouse `_mock_irtt_thread` fixture that patches `_start_irtt_thread` to return None for all entry point tests
- **Files modified:** tests/test_autorate_entry_points.py
- **Verification:** Full test suite 3196/3196 passing, no warnings
- **Committed in:** 6cb7b9c (part of task commit)

**2. [Rule 1 - Bug] Moved get_latest() call out of log message to local variable**

- **Found during:** Task 1 (implementation)
- **Issue:** Plan's \_check_protocol_correlation referenced self.\_irtt_thread.get_latest().rtt_mean_ms directly in the INFO log message, which could return None between the check and the log
- **Fix:** Fetched result via local variable with None guard, used 0.0 fallback for UDP RTT display
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** Tests pass, no potential NoneType errors
- **Committed in:** 6cb7b9c (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- IRTT daemon integration complete (Phase 90 done)
- IRTT measurements run in background, results cached for zero-blocking reads
- Protocol correlation detects ISP deprioritization patterns
- Ready for Phase 91 (container networking) and Phase 92 (metrics/observability)

---

## Self-Check: PASSED

- [x] src/wanctl/autorate_continuous.py exists
- [x] tests/test_irtt_thread.py exists
- [x] tests/test_autorate_entry_points.py exists
- [x] 90-02-SUMMARY.md exists
- [x] Commit 6cb7b9c exists

---

_Phase: 90-irtt-daemon-integration_
_Completed: 2026-03-16_

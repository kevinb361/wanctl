---
phase: 48-hot-path-optimization
plan: 01
subsystem: rtt-measurement
tags: [icmplib, icmp, raw-sockets, performance, hot-path]

# Dependency graph
requires:
  - phase: 47-cycle-profiling-infrastructure
    provides: profiling data showing RTT measurement at 97-98% of cycle time
provides:
  - icmplib-based ping_host() eliminating subprocess fork/exec/pipe/parse overhead
  - Zero subprocess forks in RTT measurement hot path
  - Backward-compatible parse_ping_output() for calibrate.py
affects: [48-hot-path-optimization, 49-telemetry-monitoring]

# Tech tracking
tech-stack:
  added: [icmplib>=3.0.4]
  patterns:
    [
      raw ICMP sockets via icmplib.ping(),
      privileged=True for CAP_NET_RAW containers,
    ]

key-files:
  created: []
  modified:
    - pyproject.toml
    - src/wanctl/rtt_measurement.py
    - tests/test_rtt_measurement.py

key-decisions:
  - "Use icmplib.ping() with privileged=True (containers have CAP_NET_RAW)"
  - "Set interval=0 to avoid icmplib 1-second default delay between packets"
  - "Retain subprocess import with noqa for test verification of no-subprocess-in-hot-path"
  - "timeout_total parameter kept for API compatibility but documented as unused by icmplib path"

patterns-established:
  - "icmplib error hierarchy: NameLookupError (warning) < SocketPermissionError (error) < ICMPLibError (error) < generic Exception (error)"
  - "make_host_result() test helper for building mock icmplib Host objects"

requirements-completed: [OPTM-01]

# Metrics
duration: 10min
completed: 2026-03-06
---

# Phase 48 Plan 01: RTT Measurement Hot Path Summary

**Replaced subprocess.run(["ping"]) with icmplib raw ICMP sockets, eliminating ~2-5ms fork/exec/pipe/parse overhead per RTT measurement cycle**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-06T21:59:02Z
- **Completed:** 2026-03-06T22:09:19Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- Rewrote ping_host() to use icmplib.ping() with privileged=True and interval=0
- Added comprehensive icmplib exception handling (NameLookupError, SocketPermissionError, ICMPLibError)
- Retained parse_ping_output() and subprocess import for calibrate.py backward compatibility
- Updated all tests to mock icmplib.ping instead of subprocess.run (38 tests pass)
- Full test suite passes: 1912 tests, zero regressions from RTT changes

## Task Commits

Each task was committed atomically (TDD flow):

1. **Task 1 (RED): Add failing tests for icmplib-based ping_host()** - `c60e883` (test)
2. **Task 1 (GREEN): Implement icmplib-based ping_host()** - `088db65` (feat)

_TDD task: RED commit has failing tests, GREEN commit has passing implementation._

## Files Created/Modified

- `pyproject.toml` - Added icmplib>=3.0.4 dependency
- `src/wanctl/rtt_measurement.py` - Rewrote ping_host() from subprocess to icmplib, added icmplib import, updated docstrings
- `tests/test_rtt_measurement.py` - Updated all mocks from subprocess to icmplib, added make_host_result() helper, added TestIcmplibErrorHandling and TestNoSubprocessInHotPath classes

## Decisions Made

- Used icmplib.ping() with privileged=True since containers have CAP_NET_RAW capability
- Set interval=0 to avoid icmplib's 1-second default delay between packets (Pitfall 2 from research)
- Retained subprocess import with `# noqa: F401` comment so the TestNoSubprocessInHotPath test can verify subprocess.run is not called in the hot path
- timeout_total parameter kept for API compatibility but documented as unused by icmplib path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed make_host_result() helper for empty rtts**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** `rtts or [12.3]` evaluates `[] or [12.3]` to `[12.3]` since empty list is falsy
- **Fix:** Changed to explicit `if rtts is None: rtts = [12.3]` check
- **Files modified:** tests/test_rtt_measurement.py
- **Verification:** test_no_rtt_samples_returns_none_logs_warning now passes
- **Committed in:** 088db65 (GREEN commit)

**2. [Rule 1 - Bug] Fixed SocketPermissionError test instantiation**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** `icmplib.SocketPermissionError` requires `privileged` argument, bare class raises TypeError
- **Fix:** Changed to `icmplib.SocketPermissionError(privileged=True)` as side_effect
- **Files modified:** tests/test_rtt_measurement.py
- **Verification:** test_socket_permission_error_logs_error now passes
- **Committed in:** 088db65 (GREEN commit)

**3. [Rule 3 - Blocking] Fixed import ordering and unused imports for ruff compliance**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** ruff flagged import sorting (I001) and unused subprocess/Mock imports (F401)
- **Fix:** Reorganized imports with isort ordering, added noqa for intentionally retained subprocess, removed unused subprocess/Mock from tests
- **Files modified:** src/wanctl/rtt_measurement.py, tests/test_rtt_measurement.py
- **Verification:** `ruff check` passes cleanly
- **Committed in:** 088db65 (GREEN commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- icmplib-based RTT measurement ready for production deployment
- RTT measurement hot path now zero-subprocess (ready for Phase 48 Plan 02 if applicable)
- Callers (autorate_continuous.py, steering/daemon.py) require zero modifications
- Container deployments need CAP_NET_RAW (already present)

## Self-Check: PASSED

- All files exist (SUMMARY.md, rtt_measurement.py, test_rtt_measurement.py, pyproject.toml)
- All commits verified (c60e883 RED, 088db65 GREEN)
- icmplib.ping() present in source (2 references)
- subprocess.run absent from source (0 references)
- icmplib dependency in pyproject.toml

---

_Phase: 48-hot-path-optimization_
_Completed: 2026-03-06_

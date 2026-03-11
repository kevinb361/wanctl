---
phase: 63-dead-code-stale-api-cleanup
plan: 01
subsystem: infra
tags: [dead-code, pexpect, subprocess, icmplib, cleanup, dependencies]

# Dependency graph
requires:
  - phase: 62-deployment-alignment
    provides: "Aligned deployment artifacts (pyproject.toml as source of truth)"
provides:
  - "Clean production dependencies (6 deps, no pexpect)"
  - "Simplified RTTMeasurement API (no timeout_total)"
  - "Simplified get_ping_timeout (no total parameter)"
affects: [64-config-boilerplate, 65-contract-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RTTMeasurement constructor: logger, timeout_ping, aggregation_strategy, log_sample_stats"

key-files:
  created: []
  modified:
    - pyproject.toml
    - requirements.txt
    - docker/Dockerfile
    - scripts/install.sh
    - src/wanctl/rtt_measurement.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/timeouts.py
    - tests/test_rtt_measurement.py
    - tests/test_timeouts.py

key-decisions:
  - "Steering per-ping timeout set to 2 (matching daemon config default, not 3 from old 10//3)"
  - "container_install_spectrum.sh updated locally but is gitignored (legacy script)"

patterns-established:
  - "RTTMeasurement API: 4 params (logger, timeout_ping, aggregation_strategy, log_sample_stats)"
  - "get_ping_timeout: single param (component), no total/per-ping distinction"

requirements-completed: [DEAD-01, DEAD-02, DEAD-03]

# Metrics
duration: 8min
completed: 2026-03-10
---

# Phase 63 Plan 01: Dead Code & Stale API Cleanup Summary

**Removed pexpect dependency, dead subprocess import, and stale timeout_total parameter -- 6 production deps, clean RTTMeasurement API**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-10T12:18:15Z
- **Completed:** 2026-03-10T12:26:39Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Removed pexpect from all 4 tracked deployment artifacts (pyproject.toml, requirements.txt, Dockerfile, install.sh)
- Removed dead subprocess import from rtt_measurement.py and simplified RTTMeasurement constructor
- Eliminated timeout_total/timeout_ping_total plumbing from steering daemon and timeouts.py
- 2207 tests passing, all modified files pass ruff check

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove pexpect from all deployment artifacts** - `5f6c5f2` (chore)
2. **Task 2: Remove dead subprocess import and stale timeout_total API** - `86fb889` (feat)

## Files Created/Modified

- `pyproject.toml` - Removed pexpect from dependencies (7 to 6)
- `requirements.txt` - Removed pexpect line
- `docker/Dockerfile` - Removed pexpect from pip install block
- `scripts/install.sh` - Removed 4 pexpect references (check, pip install, warning, install command)
- `src/wanctl/rtt_measurement.py` - Removed subprocess import and timeout_total parameter
- `src/wanctl/steering/daemon.py` - Removed DEFAULT_STEERING_PING_TOTAL_TIMEOUT import, timeout_ping_total config, timeout_total kwarg
- `src/wanctl/timeouts.py` - Removed DEFAULT_STEERING_PING_TOTAL_TIMEOUT constant, simplified get_ping_timeout
- `tests/test_rtt_measurement.py` - Renamed TestNoSubprocessInHotPath to TestIcmplibInHotPath, simplified assertion
- `tests/test_timeouts.py` - Removed 3 dead tests, updated steering ping timeout assertions

## Decisions Made

- Steering per-ping timeout in get_ping_timeout set to `2` (matching the steering daemon Config.\_load_timeouts default of `timeouts.get("ping", 2)`), rather than the old `10 // 3 = 3`
- container_install_spectrum.sh was updated but is gitignored (legacy unreferenced script)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dead code removed, production dependencies are clean
- RTTMeasurement API simplified for any future callers
- Ready for Phase 64 (config boilerplate extraction)

## Self-Check: PASSED

All 9 modified files verified on disk. Both task commits (5f6c5f2, 86fb889) confirmed in git log.

---

_Phase: 63-dead-code-stale-api-cleanup_
_Completed: 2026-03-10_

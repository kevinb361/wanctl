---
phase: 148-test-robustness-performance
plan: 01
subsystem: testing
tags: [pytest-xdist, pytest-timeout, ci-enforcement, mock-quality, prometheus]

# Dependency graph
requires:
  - phase: 147-interface-decoupling
    provides: get_health_data() public facade on WANController and SteeringDaemon
provides:
  - pytest-xdist parallel execution configured via addopts
  - pytest-timeout 2s per-test cap with thread method
  - CI brittleness gate (cross-module private patch counter)
  - Root conftest Prometheus registry reset for xdist isolation
  - Fixed 7 MagicMock test failures in test_alert_engine.py
affects: [148-02, 148-03]

# Tech tracking
tech-stack:
  added: [pytest-xdist>=3.8.0, pytest-timeout>=2.4.0]
  patterns: [autouse-prometheus-reset, typed-mock-return-values, ast-based-ci-enforcement]

key-files:
  created:
    - scripts/check_test_brittleness.py
  modified:
    - pyproject.toml
    - Makefile
    - tests/conftest.py
    - tests/test_alert_engine.py

key-decisions:
  - "timeout_method=thread to avoid SIGALRM issues with xdist workers"
  - "Brittleness threshold starts at 3 (SC1 safety valve) -- Plan 02 will fix violations and lower"
  - "Fixed mock leakage by providing typed get_health_data() return values instead of patching private attrs"

patterns-established:
  - "Typed mock return values: always set get_health_data.return_value with real typed dicts, not MagicMock auto-generation"
  - "Autouse Prometheus reset: root conftest fixture ensures clean metrics registry per xdist worker"
  - "AST-based CI gate: scripts/check_test_brittleness.py counts cross-module private patches"

requirements-completed: [TEST-02, TEST-03]

# Metrics
duration: 8min
completed: 2026-04-08
---

# Phase 148 Plan 01: Test Infrastructure & Brittleness Enforcement Summary

**pytest-xdist parallel execution with 2s timeout, CI brittleness gate, and 7 MagicMock test failures fixed via typed return values**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-08T17:38:05Z
- **Completed:** 2026-04-08T17:46:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Installed pytest-xdist and pytest-timeout as dev dependencies with addopts configuration
- Fixed all 7 test_alert_engine.py MagicMock failures by providing typed get_health_data() return values
- Created AST-based CI brittleness script that counts cross-module private patches per test file
- Added autouse Prometheus registry reset fixture for xdist worker isolation
- 114/114 test_alert_engine tests pass, 4252 total tests collected

## Task Commits

Each task was committed atomically:

1. **Task 1: Install xdist+timeout, configure pyproject.toml/Makefile, add Prometheus reset, fix alert_engine tests** - `9dc7ddb` (feat)
2. **Task 2: Create check_test_brittleness.py CI script and add Makefile target** - `f74ad6c` (feat)

## Files Created/Modified
- `pyproject.toml` - Added pytest-xdist, pytest-timeout deps; configured addopts with -n auto --timeout=2
- `Makefile` - Added check-brittleness target, added to ci recipe, -p no:randomly for coverage
- `tests/conftest.py` - Added autouse reset_prometheus_registry fixture
- `tests/test_alert_engine.py` - Fixed 7 MagicMock failures: typed get_health_data() return values, needs_rate_limiting=False
- `scripts/check_test_brittleness.py` - New AST-based CI script counting cross-module private patches

## Decisions Made
- Used `timeout_method = "thread"` instead of default signal-based timeout to avoid SIGALRM issues with xdist worker processes
- Fixed WiringAutorate tests by setting `mock_router.needs_rate_limiting = False` (simplest fix, avoids needing to mock rate_limit_params dict internals)
- Fixed HealthAlerting and SteeringHealthAlerting tests by providing complete typed `get_health_data.return_value` dicts instead of patching private attributes -- aligns with Phase 147 public facade pattern
- Brittleness threshold set to 3 (not 0) because test_check_cake.py has 8 cross-module patches that Plan 02 will address

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 can now run brittleness script to identify and fix cross-module patches
- Plan 03 can leverage xdist parallel execution for performance testing
- test_check_cake.py has 8 cross-module patches exceeding threshold 3 -- Plan 02's primary target

## Self-Check: PASSED

All 5 created/modified files verified on disk. Both task commits (9dc7ddb, f74ad6c) verified in git log.

---
*Phase: 148-test-robustness-performance*
*Completed: 2026-04-08*

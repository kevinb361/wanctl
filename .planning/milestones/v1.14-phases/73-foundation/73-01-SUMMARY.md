---
phase: 73-foundation
plan: 01
subsystem: dashboard
tags: [textual, httpx, tui, config, poller, async]

# Dependency graph
requires:
  - phase: none
    provides: "First plan in new milestone, no prior dependencies"
provides:
  - "wanctl[dashboard] optional dependency group (textual + httpx)"
  - "wanctl-dashboard CLI entry point"
  - "DashboardConfig with XDG, YAML loading, CLI override precedence"
  - "EndpointPoller with async polling, backoff, offline detection"
  - "Shared test fixtures (sample health responses)"
affects: [73-02, 73-03]

# Tech tracking
tech-stack:
  added: [textual, httpx]
  patterns:
    [XDG config loading, async poller with backoff, optional dependency group]

key-files:
  created:
    - src/wanctl/dashboard/__init__.py
    - src/wanctl/dashboard/config.py
    - src/wanctl/dashboard/poller.py
    - src/wanctl/dashboard/app.py
    - tests/test_dashboard/__init__.py
    - tests/test_dashboard/conftest.py
    - tests/test_dashboard/test_config.py
    - tests/test_dashboard/test_poller.py
    - tests/test_dashboard/test_entry_point.py
  modified:
    - pyproject.toml

key-decisions:
  - "Simple YAML config loader (not BaseConfig) for dashboard-specific config"
  - "httpx.AsyncClient passed into poll() for testability and lifecycle control"
  - "asyncio.run() in tests instead of pytest-asyncio (not in dev deps)"
  - "datetime.UTC alias per pyupgrade/ruff UP017 rule"

patterns-established:
  - "Dashboard config: XDG_CONFIG_HOME/wanctl/dashboard.yaml with CLI override"
  - "Poller pattern: EndpointPoller per endpoint, httpx.AsyncClient shared"
  - "Backoff pattern: normal_interval on success, backoff_interval on failure"

requirements-completed:
  [INFRA-01, INFRA-02, INFRA-03, INFRA-04, POLL-01, POLL-02, POLL-03, POLL-04]

# Metrics
duration: 8min
completed: 2026-03-11
---

# Phase 73 Plan 01: Foundation Summary

**Dashboard package infrastructure with XDG config loading, CLI entry point, and async endpoint poller with independent backoff**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-11T18:22:16Z
- **Completed:** 2026-03-11T18:30:56Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Installable `wanctl[dashboard]` with textual and httpx optional deps
- `wanctl-dashboard` CLI entry point with argparse (--autorate-url, --steering-url, --refresh-interval)
- DashboardConfig dataclass with YAML loading, XDG support, CLI precedence, wan_rate_limits
- EndpointPoller with async polling, online/offline tracking, last_seen timestamp, backoff (2s/5s)
- 30 tests passing across config, entry point, and poller modules
- Ruff and mypy clean

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Package infrastructure and config module**
   - `6929d71` test(73-01): add failing tests for dashboard config and entry point
   - `2cdf2d4` feat(73-01): implement dashboard config module and entry point

2. **Task 2: Async endpoint poller with independent polling and backoff**
   - `de5f16d` test(73-01): add failing tests for async endpoint poller
   - `f02fca6` feat(73-01): implement async endpoint poller with backoff

## Files Created/Modified

- `pyproject.toml` - Added wanctl-dashboard entry point and dashboard optional deps
- `src/wanctl/dashboard/__init__.py` - Package marker
- `src/wanctl/dashboard/config.py` - DEFAULTS, DashboardConfig, load_dashboard_config, apply_cli_overrides, get_config_dir
- `src/wanctl/dashboard/poller.py` - EndpointPoller with async poll, backoff, offline detection
- `src/wanctl/dashboard/app.py` - parse_args, main entry point, DashboardApp placeholder
- `tests/test_dashboard/__init__.py` - Test package marker
- `tests/test_dashboard/conftest.py` - sample_autorate_response, sample_steering_response, tmp_config_dir fixtures
- `tests/test_dashboard/test_config.py` - 14 config tests (defaults, YAML, XDG, CLI override, wan_rate_limits)
- `tests/test_dashboard/test_poller.py` - 12 poller tests (success, failure, backoff, independence)
- `tests/test_dashboard/test_entry_point.py` - 4 entry point tests (importability, pyproject correctness)

## Decisions Made

- Used simple YAML loader (not BaseConfig) per CONTEXT.md decision -- dashboard config is user-facing, not daemon config with schema validation
- httpx.AsyncClient passed into poll() rather than created internally -- enables testability and app-level lifecycle control
- Used asyncio.run() in tests rather than adding pytest-asyncio to dev deps -- keeps dependency footprint minimal
- Used datetime.UTC alias (Python 3.11+) per pyupgrade/ruff UP017 rule

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed httpx and textual in dev venv**

- **Found during:** Task 1 (before writing tests)
- **Issue:** httpx and textual not installed in .venv, imports would fail
- **Fix:** Ran `.venv/bin/pip install httpx textual`
- **Files modified:** None (runtime install only)
- **Verification:** Import succeeds in test runs

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for test execution. No scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dashboard package fully installable via `pip install wanctl[dashboard]`
- Config module ready for Plan 02 (widget rendering) and Plan 03 (app wiring)
- Poller module ready for Plan 03 (DashboardApp integration with Textual workers)
- Shared test fixtures ready for all subsequent dashboard test files

## Self-Check: PASSED

- All 9 created files verified on disk
- All 4 task commits verified in git history (6929d71, 2cdf2d4, de5f16d, f02fca6)
- 30 tests passing, ruff clean, mypy clean

---

_Phase: 73-foundation_
_Completed: 2026-03-11_

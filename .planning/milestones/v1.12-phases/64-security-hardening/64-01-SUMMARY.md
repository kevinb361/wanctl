---
phase: 64-security-hardening
plan: 01
subsystem: auth
tags: [security, router-client, ssl, password-management, warnings]

# Dependency graph
requires:
  - phase: 63-dead-code-cleanup
    provides: "Clean router client codebase"
provides:
  - "clear_router_password() helper for zeroing config passwords post-construction"
  - "_resolve_password() for eager env-var resolution"
  - "_create_transport_with_password() for explicit password passing"
  - "Per-request SSL warning suppression via warnings.catch_warnings"
  - "_request() method replacing direct session.get/patch/post calls"
affects: [daemon-startup, router-client, routeros-rest]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Eager password resolution at FailoverRouterClient init time"
    - "Per-request warning suppression via warnings.catch_warnings context manager"
    - "Session.request delegate pattern for mock compatibility in tests"

key-files:
  created: []
  modified:
    - "src/wanctl/router_client.py"
    - "src/wanctl/routeros_rest.py"
    - "tests/test_router_client.py"
    - "tests/test_routeros_rest.py"
    - "tests/test_router_behavioral.py"
    - "tests/test_phase53_code_cleanup.py"

key-decisions:
  - "FailoverRouterClient resolves password eagerly at init, stores as _resolved_password"
  - "Per-request SSL warning suppression uses warnings.catch_warnings, not urllib3.disable_warnings"
  - "Test fixtures updated with session.request delegate pattern for mock compatibility"

patterns-established:
  - "Eager credential resolution: resolve secrets at construction, not at use-time"
  - "Per-request warning suppression: use warnings.catch_warnings context manager around individual HTTP calls"

requirements-completed: [SECR-01, SECR-02]

# Metrics
duration: 15min
completed: 2026-03-10
---

# Phase 64 Plan 01: Router Credential Lifetime & SSL Warning Scope Summary

**Eager password resolution with clear_router_password() helper and per-request SSL warning suppression via warnings.catch_warnings**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-10T13:02:38Z
- **Completed:** 2026-03-10T13:18:11Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- FailoverRouterClient eagerly resolves ${ENV_VAR} passwords at init, stores in _resolved_password
- clear_router_password(config) zeros out config.router_password after client construction
- Re-probe after password clearing works because password was resolved at init time
- Removed process-wide urllib3.disable_warnings; replaced with per-request warnings.catch_warnings
- 13 new tests (7 for SECR-01, 6 for SECR-02), all 2,220 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: FailoverRouterClient eagerly resolves password and exposes clear helper** - `59d2220` (feat)
2. **Task 2: Per-session SSL warning suppression in RouterOSREST** - `4d021f9` (feat)

_Note: TDD tasks with RED/GREEN in same commit for clarity._

## Files Created/Modified
- `src/wanctl/router_client.py` - Added _resolve_password(), clear_router_password(), _create_transport_with_password(); FailoverRouterClient stores _resolved_password
- `src/wanctl/routeros_rest.py` - Removed urllib3.disable_warnings; added _request() with per-request warning suppression; replaced all session.get/patch/post with _request()
- `tests/test_router_client.py` - Added TestClearRouterPassword class (7 tests); updated all FailoverRouterClient test patches
- `tests/test_routeros_rest.py` - Added TestSSLWarningSuppressionPerSession class (6 tests); added session.request delegate fixture
- `tests/test_router_behavioral.py` - Added _add_request_delegate helper; updated _make_rest_client
- `tests/test_phase53_code_cleanup.py` - Updated CLEAN-05 test to verify new per-request suppression behavior

## Decisions Made
- FailoverRouterClient resolves password eagerly at init using same ${ENV_VAR} logic as RouterOSREST.from_config
- _create_transport_with_password() constructs RouterOSREST directly (not via from_config) to avoid re-reading config.router_password
- SSH transport unaffected by password clearing (uses SSH keys, not passwords)
- Test mock_session fixtures updated with request delegate pattern rather than mocking _request method directly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated CLEAN-05 test for new behavior**
- **Found during:** Task 2 (per-session SSL warning suppression)
- **Issue:** test_phase53_code_cleanup.py::TestClean05WarningScopedToSession::test_disable_warnings_called_when_verify_ssl_false asserted the OLD behavior (urllib3.disable_warnings is called)
- **Fix:** Updated test to verify new behavior (disable_warnings NOT called, _suppress_ssl_warnings flag set instead)
- **Files modified:** tests/test_phase53_code_cleanup.py
- **Verification:** All 2,220 tests pass
- **Committed in:** 4d021f9 (Task 2 commit)

**2. [Rule 3 - Blocking] Added session.request delegate for test mock compatibility**
- **Found during:** Task 2 (per-session SSL warning suppression)
- **Issue:** Changing from self._session.get() to self._session.request("GET", ...) broke all existing REST client tests that mock session.get/patch/post
- **Fix:** Added _make_session_request_delegate() and _add_request_delegate() helpers to route session.request() calls to the appropriate method mocks
- **Files modified:** tests/test_routeros_rest.py, tests/test_router_behavioral.py
- **Verification:** All 116 router-related tests pass
- **Committed in:** 4d021f9 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SECR-01 and SECR-02 complete, ready for Phase 64 Plan 02 (remaining security hardening)
- clear_router_password() is available for daemon startup code to call after client construction
- No blockers

---
*Phase: 64-security-hardening*
*Completed: 2026-03-10*

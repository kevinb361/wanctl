---
phase: 21-critical-safety-tests
plan: 02
subsystem: testing
tags: [safety-invariants, transport-failover, rest-api, ssh, pytest]
dependency-graph:
  requires: []
  provides: [TEST-03, FailoverRouterClient, get_router_client_with_failover]
  affects: [daemon-reliability, production-resilience]
tech-stack:
  added: []
  patterns: [transport-failover, lazy-client-creation, sticky-fallback]
key-files:
  created:
    - tests/test_router_client.py
  modified:
    - src/wanctl/router_client.py
decisions:
  - "Failover is sticky: once triggered, stays on fallback until close()"
  - "Lazy client creation: fallback only instantiated on first failure"
  - "Catches ConnectionError, TimeoutError, OSError for comprehensive coverage"
metrics:
  duration: "7 minutes"
  completed: "2026-01-21"
---

# Phase 21 Plan 02: Transport Failover Tests Summary

**REST-to-SSH automatic failover with 16 tests proving daemon resilience against REST API failures.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-21T13:09:01Z
- **Completed:** 2026-01-21T13:15:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented `FailoverRouterClient` class with automatic REST-to-SSH fallback
- Added `get_router_client_with_failover` factory function
- Created 16 comprehensive tests proving failover behavior
- Proved SAFETY INVARIANT: REST API failures auto-fallback to SSH

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement transport failover wrapper** - `8a43354` (feat)
   - Note: Bundled with 21-01 commit due to parallel execution
2. **Task 2: Add transport failover tests (TEST-03)** - `7c68e04` (test)

## Files Created/Modified

- `src/wanctl/router_client.py` - Added FailoverRouterClient, _create_transport, get_router_client_with_failover
- `tests/test_router_client.py` - 16 tests covering failover behavior

## What Was Built

### FailoverRouterClient Implementation

```python
class FailoverRouterClient:
    """Router client wrapper with automatic REST-to-SSH failover."""

    def run_cmd(self, cmd: str) -> tuple[int, str, str]:
        """Execute command with automatic failover."""
        if self._using_fallback:
            return self._get_fallback().run_cmd(cmd)
        try:
            return self._get_primary().run_cmd(cmd)
        except (ConnectionError, TimeoutError, OSError) as e:
            self._using_fallback = True
            return self._get_fallback().run_cmd(cmd)
```

Key behaviors:
- **Lazy creation:** Clients only instantiated when needed
- **Sticky fallback:** Once triggered, stays on fallback
- **Comprehensive error handling:** ConnectionError, TimeoutError, OSError
- **Operational logging:** Warnings logged on failover for visibility

### TEST-03: Transport Failover Tests (16 tests)

| Test | Description |
|------|-------------|
| test_ssh_transport_selection | SSH transport selected when config specifies |
| test_rest_transport_selection | REST transport selected when config specifies |
| test_invalid_transport_raises | Invalid transport raises ValueError |
| test_rest_failure_triggers_ssh_fallback | PRIMARY SAFETY TEST: ConnectionError triggers SSH |
| test_timeout_triggers_fallback | TimeoutError triggers SSH fallback |
| test_oserror_triggers_fallback | OSError triggers SSH fallback |
| test_subsequent_calls_use_fallback | After failover, stays on SSH |
| test_primary_success_no_fallback | Success path: no fallback created |
| test_close_closes_both_transports | Resource cleanup verifies both closed |
| test_close_safe_when_no_clients_created | Safe to close without any calls |
| test_failover_logs_warning | Operational visibility: warning logged |
| test_custom_transport_order | SSH->REST fallback works too |
| test_fallback_client_lazy_creation | Fallback not created until needed |
| test_default_transports | Default: REST primary, SSH fallback |
| test_custom_transports | Constructor accepts custom transports |
| test_initial_state | Initial: no clients, not using fallback |

## Safety Invariant Proven

> **SAFETY INVARIANT:** REST API failures must automatically fall back to SSH transport. This prevents daemon crashes when REST API is temporarily unavailable.

The primary safety test (`test_rest_failure_triggers_ssh_fallback`) proves:
1. ConnectionError on REST triggers failover
2. SSH client is created as fallback
3. Command succeeds via SSH
4. Warning is logged for operational visibility

## Decisions Made

1. **Sticky fallback:** Once failover occurs, the client stays on fallback transport until `close()`. This avoids repeated REST failures and log noise.

2. **Lazy client creation:** Fallback client is only created when primary fails. This avoids wasting resources when REST works fine.

3. **Comprehensive error coverage:** Catches `ConnectionError`, `TimeoutError`, and `OSError` to handle network unreachable, connection refused, timeout, and socket errors.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Test `test_rest_transport_selection` initially failed due to patching at wrong level (RouterOSREST is imported inside function). Fixed by patching at source module `wanctl.routeros_rest.RouterOSREST`.

## Test Count Impact

| File | Before | After | Added |
|------|--------|-------|-------|
| test_router_client.py | 0 | 16 | +16 |
| **Total project** | 701 | 717 | +16 |

## Verification Results

```
tests/test_router_client.py: 16 passed
Full test suite: 716 passed, 1 skipped (integration test - live network)
ruff check: All checks passed!
mypy: Success - no issues found
```

## Next Phase Readiness

- TEST-03 complete
- Phase 21 Critical Safety Tests complete (TEST-01, TEST-02, TEST-03)
- Ready for Phase 22 (Deployment Safety)
- No blockers identified

---
*Phase: 21-critical-safety-tests*
*Completed: 2026-01-21*

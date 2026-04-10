---
phase: 15-steeringdaemon-refactoring
plan: 03
subsystem: steering
tags: [refactoring, steering-daemon, routing-control, s4-fix]

# Dependency graph
requires:
  - phase: 07-core-algorithm-analysis
    provides: S4 recommendation for routing control extraction
provides:
  - execute_steering_transition() method
  - Unit tests for routing transitions
  - Unified routing control across state machines
affects: [15-steeringdaemon-refactoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Extraction pattern: routing control consolidated into single method"
    - "Boolean return pattern: success/failure from router operations"

key-files:
  created: []
  modified:
    - src/wanctl/steering/daemon.py
    - tests/test_steering_daemon.py

key-decisions:
  - "Method takes enable_steering boolean rather than separate enable/disable methods"
  - "Transition logging and metrics recording consolidated in helper"
  - "State update only happens on router success"

patterns-established:
  - "Routing transition pattern: (from_state, to_state, enable_flag) -> bool"

issues-created: []

# Metrics
duration: 30 min
completed: 2026-01-13
---

# Phase 15 Plan 03: Extract Routing Control - Summary

**Extracted routing control logic (~24 lines x 4 occurrences = ~96 lines consolidated) from both state machine methods into execute_steering_transition() method with 15 new unit tests**

## Performance

- **Duration:** 30 min
- **Started:** 2026-01-13
- **Completed:** 2026-01-13
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `execute_steering_transition(from_state, to_state, enable_steering) -> bool` method
- Replaced 4 inline routing control blocks (2 in CAKE-aware, 2 in legacy state machine)
- Consolidated router enable/disable, transition logging, state update, and metrics recording
- Added 15 comprehensive unit tests for routing transitions
- Test count at 579 (all passing)

## Task Details

### Task 1: Create execute_steering_transition() Method

**Location:** `src/wanctl/steering/daemon.py` (lines 575-612)

**Method signature:**
```python
def execute_steering_transition(
    self,
    from_state: str,
    to_state: str,
    enable_steering: bool
) -> bool:
```

**Responsibilities:**
1. Call `router.enable_steering()` or `router.disable_steering()` based on flag
2. On failure: log error, return False (state unchanged)
3. On success: call `state_mgr.log_transition(from_state, to_state)`
4. On success: update `state["current_state"] = to_state`
5. Record metrics if `config.metrics_enabled`
6. Return True

### Task 2: Update State Machine Methods

**_update_state_machine_cake_aware()** - 2 callsites updated:
- Lines 757-761: Enable steering on RED threshold
- Lines 793-797: Disable steering on GREEN recovery

**_update_state_machine_legacy()** - 2 callsites updated:
- Lines 844-848: Enable steering on bad threshold
- Lines 871-875: Disable steering on recovery

Each callsite now:
```python
if self.execute_steering_transition(
    current_state, target_state, enable_steering=True/False
):
    counter = 0
    state_changed = True
```

## Test Coverage Added

**TestExecuteSteeringTransition class with 15 tests:**

- **Enable steering tests:**
  - `test_enable_steering_calls_router_enable`
  - `test_enable_steering_success_updates_state`
  - `test_enable_steering_success_logs_transition`
  - `test_enable_steering_failure_returns_false`
  - `test_enable_steering_failure_logs_error`

- **Disable steering tests:**
  - `test_disable_steering_calls_router_disable`
  - `test_disable_steering_success_updates_state`
  - `test_disable_steering_success_logs_transition`
  - `test_disable_steering_failure_returns_false`
  - `test_disable_steering_failure_logs_error`

- **Metrics tests:**
  - `test_metrics_recorded_when_enabled`
  - `test_metrics_not_recorded_when_disabled`
  - `test_metrics_not_recorded_on_router_failure`

- **Integration tests:**
  - `test_transition_returns_true_allows_counter_reset`
  - `test_transition_returns_false_prevents_counter_reset`

## Lines Changed

- **Original inline code per callsite:** ~12 lines (router call + log transition + state update + metrics + else error)
- **New callsite:** ~4 lines (if statement with method call)
- **Lines saved:** ~8 lines x 4 callsites = ~32 lines removed from state machines
- **Helper method added:** ~38 lines (with docstring)
- **Net simplification:** State machine methods more focused on decision logic

## Decisions Made

1. **Single method with flag:** Using `enable_steering: bool` parameter rather than separate `enable_transition()` and `disable_transition()` methods reduces duplication.

2. **State update inside helper:** The `state["current_state"] = to_state` update is done in the helper rather than at each callsite, ensuring consistency.

3. **Metrics after state update:** Metrics are recorded only after successful state update, maintaining the exact behavior of the original code.

## Verification

- [x] `make ci` passes (all 579 tests)
- [x] `execute_steering_transition()` method exists with proper docstring
- [x] Both state machine methods use the helper (no inline routing)
- [x] Routing failure behavior preserved (stay in current state)
- [x] Metrics recording preserved (only on success, only if enabled)

## Deviations from Plan

None - plan executed as designed. The work was partially implemented during 15-01 session and completed in this session.

## Next Phase Readiness

- Ready for 15-04-PLAN.md (daemon loop extraction) - already completed
- State machine methods simplified for potential S6 unification
- Routing control is now centralized and testable

---
*Phase: 15-steeringdaemon-refactoring*
*Completed: 2026-01-13*

# Phase 15 Plan 04: Extract Daemon Control Loop - Summary

## Completed: 2026-01-13

## What Was Done

### Task 1: Create run_daemon_loop() Function

Created a new module-level function `run_daemon_loop()` in `daemon.py` that encapsulates the daemon control loop logic:

**Location:** `src/wanctl/steering/daemon.py` (lines 1030-1102)

**Function signature:**
```python
def run_daemon_loop(
    daemon: SteeringDaemon,
    config: SteeringConfig,
    logger: logging.Logger,
    shutdown_event: threading.Event,
) -> int:
```

**Responsibilities extracted from main():**
- Cycle execution with run_cycle() call
- Consecutive failure tracking (MAX_CONSECUTIVE_FAILURES = 3)
- Systemd watchdog notification management
- Degraded mode notification after sustained failures
- Sleep timing with cycle interval compensation
- Graceful shutdown on event signal

### Task 2: Update main() to Call Extracted Function

Simplified main() by replacing the inline loop (45 lines) with a single call:
```python
return run_daemon_loop(daemon, config, logger, shutdown_event)
```

main() now handles only:
- Argument parsing
- Signal handler registration
- Config loading and validation
- Component initialization
- Lock acquisition
- Daemon creation
- Delegation to run_daemon_loop()
- Exception handling and cleanup

### Task 3: Add Unit Tests

Created `tests/test_steering_daemon.py` with 13 tests for run_daemon_loop():

**Test coverage:**
- `test_shutdown_event_stops_loop` - Immediate shutdown before any cycles
- `test_shutdown_after_cycles` - Shutdown after specified cycle count
- `test_consecutive_failure_counting` - Failure counter increments correctly
- `test_failure_counter_resets_on_success` - Counter resets after success
- `test_watchdog_disabled_after_max_failures` - Watchdog stops after 3 failures
- `test_watchdog_notification_on_success` - Watchdog notified on each success
- `test_degraded_notification_after_failures` - Degraded status after failures
- `test_sleep_timing_respects_interval` - Cycles spaced by measurement_interval
- `test_sleep_handles_slow_cycle` - No hang when cycle exceeds interval
- `test_systemd_available_logged` - Systemd status logged at startup
- `test_systemd_not_available` - No systemd log when not available
- `test_returns_zero_on_graceful_shutdown` - Exit code 0 on clean shutdown
- `test_startup_message_logged` - Startup message with interval logged

## Files Modified

1. `src/wanctl/steering/daemon.py`
   - Added `import threading` to imports
   - Added `run_daemon_loop()` function (72 lines)
   - Simplified `main()` by removing inline loop

2. `src/wanctl/steering/__init__.py`
   - Added `run_daemon_loop` to imports from daemon
   - Added `run_daemon_loop` to `__all__` exports

3. `tests/test_steering_daemon.py` (new file)
   - Added `TestRunDaemonLoop` class with 13 test methods

## Test Results

```
579 passed in 13.18s
```

All existing tests continue to pass, plus 13 new tests for the extracted daemon loop.

## Design Decisions

1. **Parameters instead of global access:** The function takes explicit parameters (daemon, config, logger, shutdown_event) rather than accessing globals, making it testable in isolation.

2. **Return value:** Returns exit code (int) to allow main() to pass through to sys.exit(), maintaining the same interface.

3. **Watchdog state local:** The watchdog_enabled flag and consecutive_failures counter are local to the function, not stored in state, as they are ephemeral runtime state.

4. **No modification to algorithm:** The loop logic is identical to what was in main() - this is a pure extraction with no behavioral changes.

## Benefits Achieved

1. **Testability:** The daemon loop can now be tested in isolation with mocked dependencies
2. **Clarity:** main() is now focused on initialization and cleanup
3. **Maintainability:** The loop logic is self-contained and documented
4. **Reusability:** The function could be called from alternative entry points if needed

---
phase: 50-critical-hot-loop-transport-fixes
plan: 01
subsystem: transport-retry, autorate-loop
tags: [hot-loop, retry, shutdown, performance]
dependency_graph:
  requires: []
  provides: [sub-cycle-retry-params, interruptible-main-loop-sleep]
  affects: [routeros_ssh, routeros_rest, autorate_continuous]
tech_stack:
  added: []
  patterns: [shutdown_event.wait-for-interruptible-sleep]
key_files:
  created:
    - tests/test_hot_loop_retry_params.py
  modified:
    - src/wanctl/routeros_ssh.py
    - src/wanctl/routeros_rest.py
    - src/wanctl/autorate_continuous.py
    - tests/test_autorate_entry_points.py
decisions:
  - "backoff_factor=1.0 (flat retry) chosen over exponential for hot-loop: with only 2 attempts and 50ms budget, escalation is meaningless"
  - "max_delay=0.1 caps worst-case retry at 100ms including jitter, well within 50ms cycle budget (cycle can overrun once)"
  - "shutdown_event.wait(timeout=) matches existing steering daemon pattern at daemon.py:1524"
metrics:
  duration: 559s
  completed: "2026-03-07T06:45:55Z"
  tasks_completed: 1
  tasks_total: 1
  tests_added: 11
  tests_total_passing: 1991
requirements: [LOOP-01, LOOP-04]
---

# Phase 50 Plan 01: Sub-Cycle Retry Delays & Shutdown Event Wait Summary

Sub-cycle retry params (max_attempts=2, initial_delay=0.05, backoff_factor=1.0) on both transport run_cmd methods, plus shutdown_event.wait replacing time.sleep in autorate main loop.

## Task Results

### Task 1: Sub-cycle retry delays on run_cmd and shutdown_event.wait in main loop (TDD)

**Status:** Complete
**Commits:** b61c17b (RED), e337f1c (GREEN)

**Changes:**

1. `RouterOSSSH.run_cmd` decorator: `@retry_with_backoff(max_attempts=2, initial_delay=0.05, backoff_factor=1.0, max_delay=0.1)` -- down from max_attempts=3, initial_delay=1.0, backoff_factor=2.0 (was 3s+ blocking, now ~75ms max)
2. `RouterOSREST.run_cmd` decorator: identical change
3. `autorate_continuous.py` main loop: `shutdown_event.wait(timeout=sleep_time)` replaces `time.sleep(sleep_time)` -- instant signal responsiveness instead of waiting up to 50ms
4. Added `get_shutdown_event` to signal_utils import in autorate_continuous.py
5. Updated `test_control_loop_sleeps_remainder_of_interval` to verify shutdown_event.wait usage

**Tests added:** 11 new tests in `tests/test_hot_loop_retry_params.py`

- 4 tests verifying SSH run_cmd decorator params via closure inspection
- 4 tests verifying REST run_cmd decorator params via closure inspection
- 1 test verifying transient failure blocking time < 200ms
- 2 tests verifying shutdown_event.wait pattern in autorate source

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_control_loop_sleeps_remainder_of_interval**

- **Found during:** Task 1 (TDD GREEN)
- **Issue:** Existing test patched `time.sleep` and asserted it was called, but the implementation now uses `shutdown_event.wait` instead
- **Fix:** Updated test to mock `get_shutdown_event` returning a mock event, assert `mock_event.wait.call_count >= 1`
- **Files modified:** tests/test_autorate_entry_points.py
- **Commit:** e337f1c

**2. Skipped docstring fix (line 7 "2-second" -> "50ms")**

- Plan explicitly noted: "Skip the docstring fix -- that belongs to CLEAN-02 in Phase 53"
- Correctly deferred per plan instructions

## Verification

```
grep -n "retry_with_backoff" src/wanctl/routeros_ssh.py
  -> 188: @retry_with_backoff(max_attempts=2, initial_delay=0.05, backoff_factor=1.0, max_delay=0.1)

grep -n "retry_with_backoff" src/wanctl/routeros_rest.py
  -> 152: @retry_with_backoff(max_attempts=2, initial_delay=0.05, backoff_factor=1.0, max_delay=0.1)

grep -n "shutdown_event.wait" src/wanctl/autorate_continuous.py
  -> 2104: shutdown_event.wait(timeout=sleep_time)

grep -n "time.sleep" src/wanctl/autorate_continuous.py
  -> (no matches -- time.sleep removed from main loop)

pytest tests/ --ignore=tests/integration/ -q
  -> 1991 passed
```

## Key Decisions

1. **Flat retry (backoff_factor=1.0):** With only 2 attempts in a 50ms cycle, exponential backoff adds no value. The retry delay is fixed at ~50ms (+jitter).
2. **max_delay=0.1:** Safety cap ensures retry never exceeds 100ms even if parameters are misconfigured.
3. **retry_utils.py defaults unchanged:** Non-hot-loop callers (calibrate, steering) still get the original max_attempts=3, initial_delay=1.0 defaults when they don't override.

## Self-Check: PASSED

All 6 files verified present. Both commits (b61c17b, e337f1c) verified in git log.

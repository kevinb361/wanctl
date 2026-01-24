---
created: 2026-01-23T12:01
title: Fix socket ResourceWarning in health server tests
area: testing
files:
  - src/wanctl/health_check.py
  - src/wanctl/steering/health.py
  - tests/test_health_check.py
  - tests/test_steering_health.py
---

## Problem

Running tests with `-W error` reveals unclosed socket warnings in health server tests:

```
pytest.PytestUnraisableExceptionWarning: Exception ignored in: <socket.socket fd=25...>
```

This causes 29 test failures when running `pytest -W error`:
- tests/test_health_check.py (4 failures)
- tests/test_steering_health.py (25 failures)

The sockets aren't being properly closed during test teardown.

## Solution

1. Ensure health server sockets are properly closed in `shutdown()` method
2. Add explicit `socket.close()` calls where needed
3. Consider using context managers for socket lifecycle
4. Verify all tests pass with `-W error` after fix

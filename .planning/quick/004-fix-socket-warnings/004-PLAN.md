---
phase: quick-004
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/health_check.py
  - src/wanctl/steering/health.py
autonomous: true

must_haves:
  truths:
    - "pytest -W error passes for health server tests"
    - "Sockets are closed during server shutdown"
  artifacts:
    - path: "src/wanctl/health_check.py"
      provides: "HealthCheckServer with proper socket cleanup"
      contains: "server_close"
    - path: "src/wanctl/steering/health.py"
      provides: "SteeringHealthServer with proper socket cleanup"
      contains: "server_close"
  key_links:
    - from: "HealthCheckServer.shutdown()"
      to: "HTTPServer.server_close()"
      via: "method call after shutdown()"
    - from: "SteeringHealthServer.shutdown()"
      to: "HTTPServer.server_close()"
      via: "method call after shutdown()"
---

<objective>
Fix socket ResourceWarning in health server tests by properly closing sockets during shutdown.

Purpose: Both health servers (autorate on 9101, steering on 9102) call `server.shutdown()` which stops the serve_forever() loop but doesn't close the underlying socket. Must add `server.server_close()` to release the socket resource.

Output: Clean pytest runs with `-W error` flag (no ResourceWarning for unclosed sockets)
</objective>

<execution_context>
@/home/kevin/.claude/get-shit-done/workflows/execute-plan.md
@/home/kevin/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/wanctl/health_check.py
@src/wanctl/steering/health.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add server_close() to both health server shutdown methods</name>
  <files>
    src/wanctl/health_check.py
    src/wanctl/steering/health.py
  </files>
  <action>
In both HealthCheckServer.shutdown() and SteeringHealthServer.shutdown():

1. Add `self.server.server_close()` after `self.server.shutdown()` and before `self.thread.join()`

The shutdown() method stops the serve_forever() loop.
The server_close() method actually closes the socket.

Order matters: shutdown() first (stops accepting), then server_close() (releases socket), then thread.join() (waits for thread).

Example pattern:
```python
def shutdown(self) -> None:
    """Cleanly shut down the health check server."""
    self.server.shutdown()
    self.server.server_close()
    self.thread.join(timeout=5.0)
```
  </action>
  <verify>
Run: `.venv/bin/pytest tests/test_health_check.py tests/test_steering_health.py -W error -v`
All 39 tests should pass with no ResourceWarning about unclosed sockets.
  </verify>
  <done>
pytest -W error passes for all health server tests (test_health_check.py: 11 tests, test_steering_health.py: 28 tests).
  </done>
</task>

</tasks>

<verification>
```bash
# Full verification command
.venv/bin/pytest tests/test_health_check.py tests/test_steering_health.py -W error -v

# Should see: 39 passed
# Should NOT see: ResourceWarning about unclosed sockets
```
</verification>

<success_criteria>
- All 39 health server tests pass with `-W error` flag
- No ResourceWarning for unclosed sockets
- No regressions in existing functionality
</success_criteria>

<output>
After completion, create `.planning/quick/004-fix-socket-warnings/004-SUMMARY.md`
</output>

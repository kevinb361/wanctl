---
phase: "253"
plan: "253-02"
status: complete
completed: 2026-06-20
requirements:
  - HEALTH-01
  - HEALTH-02
  - HEALTH-03
  - CB-01
  - CB-03
  - SAFE-19
---

# Plan 253-02 Summary — Route Decision Policy + Reconciliation/Circuit Breaker

## Completed

- Added `src/wanctl/steering/route_decision.py`.
  - Pure decision policy; it does not call RouterOS or `RouteManager`.
  - Requires RED congestion with supporting CAKE signals and consecutive degraded samples before preferring alternate route state.
  - Requires sustained GREEN recovery before preferring primary route state.
  - Blocks route action intent when router reachability, route-state knowledge, or circuit status is unsafe.
  - Emits structured evidence for decisions, counters, and preconditions.
- Extended `src/wanctl/steering/route_manager.py`.
  - Added startup reconciliation of configured route anchors through mocked RouterOS route print command forms.
  - Added reconciliation status, route state, circuit breaker, last intended action, last applied action, and health-friendly snapshot state.
  - Active apply requires enabled active mode, guard allowed, reconciliation ok, circuit closed, router client present, and known route target.
  - Router apply failure opens the circuit and does not mark `last_applied_action` successful.
  - Open circuit blocks further apply attempts before issuing mutation commands.
- Added minimal `SteeringDaemon` helper initialization.
  - Default/off route management initializes state but issues no route print/enable/disable commands.
  - Dry-run/active configurations inspect guard/reconcile through the same mock-testable seams.

## Files Changed

- `src/wanctl/steering/route_decision.py`
- `src/wanctl/steering/route_manager.py`
- `src/wanctl/steering/route_ownership_guard.py`
- `src/wanctl/steering/daemon.py`
- `tests/test_route_decision_policy.py`
- `tests/test_route_manager.py`
- `tests/test_route_ownership_guard.py`
- `tests/test_daemon_interaction.py` (verified unchanged behavior)

## Verification

Observed passing outputs:

```text
.venv/bin/pytest -o addopts='' tests/test_route_decision_policy.py tests/test_route_manager.py tests/test_route_ownership_guard.py tests/test_daemon_interaction.py tests/test_check_config.py -q
179 passed in 0.82s

.venv/bin/ruff check ...
All checks passed!

.venv/bin/mypy src/wanctl/
Success: no issues found in 107 source files
```

Final phase slice also passed:

```text
504 passed in 40.47s
All checks passed!
Success: no issues found in 107 source files
scope check passed
```

## Safety Notes

- Route decision policy is pure and mutation-free.
- RouteManager tests use fake router clients only.
- No live RouterOS route mutation, Netwatch disablement, production config mutation, systemd change, CAKE/qdisc change, or production default flip occurred.

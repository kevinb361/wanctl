---
phase: "252"
plan: "252-01"
status: complete
completed: 2026-06-19
requirements:
  - CFG-01
  - CFG-02
  - CFG-03
  - SAFE-19
---

# 252-01 Summary — Route-Management Config Schema, Validation, and Dry-Run Surface

## Result

Implemented the inert route-management config and dry-run planning surface for `steering.service`.

## Changes

- Added `SteeringConfig._load_route_management_config()` in `src/wanctl/steering/daemon.py`.
  - Missing `route_management` now loads as:
    - `route_management_enabled = False`
    - `route_management_mode = "off"`
    - `route_management_routes = {}`
- Added `src/wanctl/steering/route_manager.py`.
  - `RouteManager.plan_or_apply()` returns structured `RouteActionResult` values.
  - `off` and `dry_run` modes never call the router client.
  - `active` mode is explicitly blocked/fail-closed in Phase 252.
- Extended `src/wanctl/check_steering_validators.py`.
  - Added `route_management.*` known paths, including dynamic route anchors.
  - Added fail-closed cross-field validation for active mode, missing routes, malformed route maps, and empty/non-string anchors.
- Updated docs/examples.
  - `configs/examples/steering.yaml.example` includes a disabled/off route-management example.
  - `docs/STEERING.md` documents the dry-run surface and states Netwatch remains interim owner.
  - `docs/CONFIGURATION.md` points steering route-management config to `docs/STEERING.md`.
- Added/extended tests.
  - `tests/test_route_manager.py`
  - `tests/test_check_config.py`

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_route_manager.py tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py -q`
  - PASS: `270 passed in 0.98s`
- `.venv/bin/ruff check ...`
  - PASS: `All checks passed!`
- `.venv/bin/mypy src/wanctl/`
  - PASS: `Success: no issues found in 105 source files`
- `git diff --check`
  - PASS
- Docs/example assertions
  - PASS: route-management example exists, remains disabled/off, and docs state dry-run does not mutate RouterOS routes.

## Safety

No live RouterOS commands, Netwatch changes, systemd changes, CAKE qdisc changes, controller threshold changes, or production default flips were performed. All route-management behavior added here is inert unless later phases explicitly wire guarded/canaried active ownership.

---
phase: quick-6
plan: 1
subsystem: steering-daemon, dashboard
tags: [health-endpoint, config, dual-wan, polling]
dependency_graph:
  requires: []
  provides: [config-driven-health-bind, dual-autorate-polling]
  affects: [steering/daemon.py, dashboard/config.py, dashboard/app.py]
tech_stack:
  added: []
  patterns: [conditional-poller, route-wan-data-helper]
key_files:
  created: []
  modified:
    - src/wanctl/steering/daemon.py
    - src/wanctl/dashboard/config.py
    - src/wanctl/dashboard/app.py
    - tests/test_dashboard/test_config.py
    - tests/test_dashboard/test_app.py
decisions:
  - "_route_wan_data() helper extracted to share logic between primary and secondary pollers"
  - "Secondary poller is None when URL empty, conditional creation avoids any overhead in single mode"
metrics:
  duration: 4min
  completed: "2026-03-11T21:39:00Z"
  tasks: 2
  files: 5
  tests_added: 14
---

# Quick Task 6: LAN-Accessible Health Endpoints and Dual-WAN Polling Summary

Config-driven steering health server bind (host/port from YAML) and dual-poller dashboard mode for true multi-container WAN monitoring.

## Task Summary

| Task | Name                                          | Commit  | Files                                        |
| ---- | --------------------------------------------- | ------- | -------------------------------------------- |
| 1    | Steering health config + dashboard config/CLI | a975c3d | daemon.py, config.py, app.py, test_config.py |
| 2    | Dashboard dual-poller mode                    | be00bfd | app.py, test_app.py                          |

## Changes

### Steering Daemon (Task 1)

- Added `_load_health_check_config()` to SteeringConfig: reads `health_check.host`, `health_check.port`, `health_check.enabled` from YAML with defaults `127.0.0.1:9102`
- Called at end of `_load_specific_fields()` orchestration chain
- `run_steering_daemon()` now uses `config.health_check_host/port` instead of hardcoded values
- Health server start wrapped in `config.health_check_enabled` guard

### Dashboard Config (Task 1)

- Added `secondary_autorate_url: ""` to DEFAULTS and DashboardConfig dataclass
- `load_dashboard_config()` reads from YAML
- `apply_cli_overrides()` supports `--secondary-autorate-url` CLI arg
- 7 new config tests: default value, YAML loading, CLI override, None preservation

### Dashboard Dual-Poller (Task 2)

- `DashboardApp.__init__` conditionally creates `_secondary_autorate_poller` when URL is non-empty
- Extracted `_route_wan_data()` helper: routes WAN data to panel, sparkline, and gauge by WAN number
- `_poll_autorate()` dual mode: when secondary configured, primary routes only WAN 1
- `_poll_autorate()` single mode: preserves exact existing behavior (wans[:2] from single endpoint)
- Added `_poll_secondary_autorate()`: routes secondary response wans[0] to WAN 2
- `on_mount()` starts secondary polling timer when configured
- `action_refresh()` polls secondary when configured
- 7 new dual-poller tests: single behavior preservation, poller creation, routing isolation, refresh

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- 145/145 dashboard tests passing (14 new)
- ruff check clean on all modified source and test files
- All existing tests pass unchanged (zero regressions)

## Self-Check: PASSED

- All 5 modified files exist on disk
- Commit a975c3d (Task 1) verified in git log
- Commit be00bfd (Task 2) verified in git log

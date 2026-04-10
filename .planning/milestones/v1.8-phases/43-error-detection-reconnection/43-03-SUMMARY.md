---
phase: 43
plan: 03
type: summary
subsystem: health-endpoints
tags: [health-check, router-connectivity, monitoring, observability]
dependencies:
  requires: [43-01, 43-02]
  provides: [router-connectivity-visibility]
  affects: [monitoring-alerting, operations]
tech-stack:
  added: []
  patterns: [health-endpoint-aggregation, connectivity-reporting]
key-files:
  created: []
  modified:
    - src/wanctl/health_check.py
    - src/wanctl/steering/health.py
    - tests/test_health_check.py
    - tests/test_steering_health.py
decisions:
  - Router connectivity aggregated as top-level router_reachable boolean
  - Health degrades when ANY router is unreachable (all() aggregation)
  - Defaults to reachable=true when no controller/daemon (startup state)
metrics:
  duration: 6 minutes
  completed: 2026-01-29
---

# Phase 43 Plan 03: Health Endpoint Connectivity Reporting Summary

Health endpoints now report router connectivity state, enabling external monitoring and alerting when router communication fails.

## Changes Made

### Task 1: Autorate Health Endpoint (1a9a670)

Updated `src/wanctl/health_check.py` `_get_health_status()`:

1. Added `router_connectivity` section to each WAN's health info:
   ```json
   "router_connectivity": {
     "is_reachable": true,
     "consecutive_failures": 0,
     "last_failure_type": null,
     "last_failure_time": null
   }
   ```

2. Added top-level `router_reachable` boolean (aggregate of all WANs)

3. Health status now factors router reachability:
   - Degrades to 503 if ANY WAN's router is unreachable
   - Remains healthy (200) if all routers reachable AND consecutive_failures < 3

### Task 2: Steering Health Endpoint (a55a700)

Updated `src/wanctl/steering/health.py` `_get_health_status()`:

1. Added `router_connectivity` section with full state

2. Added top-level `router_reachable` boolean

3. Health status now factors router reachability:
   - Degrades to 503 if router unreachable
   - Defaults to reachable=true when no daemon (startup)

### Task 3: Router Connectivity Tests (3f38b63)

Added 11 new tests across both health modules:

**Autorate health tests:**
- `test_health_includes_router_connectivity_per_wan`
- `test_health_includes_router_reachable_aggregate`
- `test_health_degrades_when_router_unreachable`
- `test_health_healthy_when_router_reachable`
- `test_health_router_reachable_without_controller`
- `test_health_degrades_with_any_wan_unreachable`

**Steering health tests:**
- `test_steering_health_includes_router_connectivity`
- `test_steering_health_includes_router_reachable`
- `test_steering_health_degrades_when_router_unreachable`
- `test_steering_health_healthy_when_router_reachable`
- `test_steering_health_router_reachable_defaults_true_without_daemon`

## Example Health Response

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.1,
  "version": "1.7.0",
  "consecutive_failures": 0,
  "router_reachable": true,
  "wan_count": 1,
  "wans": [
    {
      "name": "spectrum",
      "baseline_rtt_ms": 24.5,
      "load_rtt_ms": 28.3,
      "download": {"current_rate_mbps": 800.0, "state": "GREEN"},
      "upload": {"current_rate_mbps": 35.0, "state": "GREEN"},
      "router_connectivity": {
        "is_reachable": true,
        "consecutive_failures": 0,
        "last_failure_type": null,
        "last_failure_time": null
      }
    }
  ]
}
```

## Verification

- All 1784 unit tests pass
- Type checking passes for both health modules
- Health endpoints return correct status codes (200 vs 503)
- Router connectivity properly aggregated across multiple WANs

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] Health endpoint response includes router_connectivity per WAN
- [x] Health endpoint includes top-level router_reachable boolean
- [x] Health status degrades (503) when router is unreachable
- [x] Health status remains healthy (200) when router is reachable
- [x] Steering health endpoint reports connectivity state
- [x] All existing health tests continue to pass

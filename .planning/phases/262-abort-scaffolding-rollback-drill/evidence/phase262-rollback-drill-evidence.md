# Phase 262 Rollback Drill Evidence

## Drill: Manual Rollback via SIGUSR1 (active -> dry_run)

### Pre-Rollback State
- mode: active
- active_owner: unknown
- last_abort: None
- active_allowed: False (guard: conflict, 4 Netwatch entries)

### Rollback Trigger
- Config change: mode active -> dry_run in /etc/wanctl/steering.yaml
- Signal: SIGUSR1 to steering PID 952841

### Post-Rollback State (verified 5s after SIGUSR1)
- mode: dry_run
- active_owner: netwatch
- circuit_open: False
- rollback_ready: True

### last_abort (health endpoint)
```json
{
  "trip_condition": "manual_rollback",
  "mode_before": "active",
  "mode_after": "dry_run",
  "timestamp": 1782717458.0992954
}
```

### last_event (health endpoint)
```json
{
  "event": "abort_to_netwatch",
  "trip_condition": "manual_rollback",
  "mode_before": "active",
  "route_revert_results": {
    "spectrum": true,
    "att": true,
    "att_policy": true
  },
  "mode_after": "dry_run"
}
```

### Log Evidence
```
Jun 29 02:17:37 [INFO] SIGUSR1 received, reloading config (dry_run + wan_state + webhook_url + route_management)
Jun 29 02:17:38 [WARNING] [ROUTE_MANAGEMENT] Config reload: mode=active->dry_run
Jun 29 02:17:38 [INFO] MANUAL ROLLBACK: mode changed active->dry_run — reverting to Netwatch
```

### Verification
- [x] Mode reverted to dry_run
- [x] active_owner is netwatch
- [x] last_abort shows correct mode_before=active
- [x] Route revert results: all true (spectrum, att, att_policy)
- [x] Circuit breaker reset (open=False)
- [x] No abort spam in logs (0 ABORT entries post-drill)
- [x] Health endpoint healthy
- [x] No service restarts beyond the initial mode flip

### Bugs Fixed During Drill
1. Netwatch contention fired on every cycle (checked guard conflicts, not observed_owner)
2. _reload_route_management_config was in SteeringConfig, not SteeringDaemon (AttributeError)
3. mode_before was always "dry_run" (reload happened before abort captured mode)
4. last_abort missing from health endpoint (_build_route_management_section omitted it)

---
gsd_state_version: 1.0
milestone: v1.15
milestone_name: Alerting & Notifications
status: executing
stopped_at: Completed 79-01-PLAN.md (connectivity offline/recovery alerts)
last_updated: "2026-03-12T16:18:00Z"
last_activity: 2026-03-12 -- Completed 79-01-PLAN.md (connectivity offline/recovery alerts)
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 8
  completed_plans: 7
  percent: 88
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-11)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.15 Alerting & Notifications -- Phase 79 plan 1 of 2 complete

## Position

**Milestone:** v1.15 Alerting & Notifications
**Phase:** 79 of 80 (Connectivity Anomaly Alerts)
**Plan:** 1 of 2 in current phase
**Status:** Executing
**Last activity:** 2026-03-12 -- Completed 79-01-PLAN.md (connectivity offline/recovery alerts)
**Last session:** 2026-03-12T16:18:00Z
**Stopped at:** Completed 79-01-PLAN.md (connectivity offline/recovery alerts)

Progress: [█████████░] 88% (Phase 79 plan 1/2)

## Performance Metrics

**Velocity:**

- Total plans completed: 7
- Average duration: 7.7 min
- Total execution time: 0.90 hours

| Phase | Plan | Duration | Tasks | Files |
| ----- | ---- | -------- | ----- | ----- |
| 76    | 01   | 3min     | 1     | 3     |
| 76    | 02   | 4min     | 1     | 3     |
| 77    | 01   | 15min    | 2     | 4     |
| 77    | 02   | 18min    | 1     | 5     |
| 78    | 01   | 6min     | 1     | 2     |
| 78    | 02   | 5min     | 1     | 2     |
| 79    | 01   | 3min     | 1     | 2     |

## Accumulated Context

### Key Decisions

- Alert engine embedded in both daemons (not standalone process)
- Per-event cooldown suppression (not global rate limit)
- Discord webhook delivery first, ntfy.sh later (DLVR-F01)
- Generic webhook layer for extensibility
- Alerting disabled by default (opt-in via config)
- Alert history in existing SQLite metrics database
- Cooldown key is (alert_type, wan_name) tuple for per-type per-WAN independent suppression
- Persistence errors logged as warnings, never crash the daemon
- AlertEngine accepts writer=None for no-persistence mode
- \_load_alerting_config() on both daemon configs (not BaseConfig) -- follows per-daemon config pattern
- AlertEngine always instantiated (enabled or disabled) so detection code calls fire() unconditionally
- webhook_url stored as-is during config parsing, validated in Phase 77 delivery layer
- Inline retry loop in WebhookDelivery (not decorator) for cleaner thread-context control
- RateLimiter reuse from rate_utils.py for webhook rate limiting
- delivery_status column added to ALERTS_SCHEMA (pending/delivered/failed)
- update_webhook_url validates https:// prefix, empty clears delivery
- delivery_callback as optional Callable on AlertEngine (fire-then-deliver pattern)
- \_persist_alert returns rowid for delivery tracking (alert_id passed to callback)
- Webhook URL validation at daemon wiring layer, not config parsing layer
- SIGUSR1 reload chain: dry_run + wan_state + webhook_url (three independent reloads)
- conftest mock fixtures must explicitly set alerting_config=None (MagicMock truthy leakage fix)
- DL congested = RED or SOFT_RED; UL congested = RED only (3-state model)
- RED->SOFT_RED shares congestion timer; GREEN/YELLOW clears timer
- Recovery gate: congestion_recovered only fires if congestion_sustained fired first
- Zone-dependent severity: RED=critical, SOFT_RED=warning, recovery=recovery
- Per-rule sustained_sec override via rules dict (same pattern as cooldown_sec)
- time.monotonic() for steering duration tracking (not ISO timestamp parsing from state file)
- steering_recovered severity="recovery" for green Discord embed (consistent with congestion recovery)
- default_sustained_sec in steering config for cross-daemon config structure symmetry
- raw_measured_rtt captured before fallback processing for accurate connectivity alert tracking
- \_check_connectivity_alerts called inside PerfTimer block before early return to track both online and offline cycles

### Known Issues

None.

### Blockers

None.

### Pending Todos

3 todos in `.planning/todos/pending/`:

- Research IRTT as RTT measurement alternative (general) -- deferred to future milestone
- Integration test for router communication (testing) -- low priority, contract tests added in v1.12
- Narrow layout truncates WAN panel content (dashboard/ui) -- low priority, wide layout works fine

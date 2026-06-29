# Phase 266: WAN-Driven Route Failover — Bridge Congestion State to Route Management

**Milestone**: v1.59 (Widen-the-Canary)
**Phase**: 266
**Status**: PLANNED
**Created**: 2026-06-29
**Depends on**: Phase 265 (4 routes reconciled, backup route active)

## Context

Phase 265 added the backup route, so all 4 default routes are now under wanctl management:
- `spectrum` — "Spectrum" (gw=70.123.224.1, dist=1) — primary
- `att` — "ATT" (gw=192.168.2.254, dist=2) — secondary
- `att_policy` — "Force ATT_OUT to ATT WAN" (gw=99.126.112.1, dist=1) — policy
- `backup` — "Backup to Spectrum if ATT fails" (gw=70.123.224.1, dist=2) — backup

Route management currently only reconciles routes exist and are in the expected state. It does NOT make failover decisions. The steering daemon already detects WAN congestion (RED/YELLOW/GREEN) but acts through binary mangle-rule steering, not route enable/disable.

**The gap:** wanctl knows when a WAN is congested but doesn't use route management to respond. This phase bridges congestion state to route management actions.

## Goal

When wanctl detects Spectrum WAN is RED (confirmed congestion), use route management to:
1. Disable the Spectrum primary route (dist=1)
2. Traffic falls through to ATT (dist=2) and backup (dist=2)

When Spectrum recovers to GREEN:
1. Re-enable the Spectrum primary route
2. Traffic returns to normal

This is the first time route management makes a *decision* based on WAN state rather than just reconciling static routes.

## Requirements

- **FAIL-01**: Route management responds to Spectrum RED by disabling the spectrum route
- **FAIL-02**: Route management responds to Spectrum GREEN by re-enabling the spectrum route
- **FAIL-03**: Hysteresis prevents flapping — require sustained RED (N consecutive cycles) before failover
- **FAIL-04**: Recovery requires sustained GREEN (M consecutive cycles) before re-enable
- **FAIL-05**: Failover decision is logged with evidence (state, cycle count, timestamp)
- **FAIL-06**: Abort path still works — circuit breaker or Netwatch contention still triggers abort_to_netwatch
- **FAIL-07**: ATT route is NOT managed by congestion state (ATT remains always-enabled)

## Success Criteria

1. Synthetic test: inject RED state → spectrum route disabled within N cycles → verify route state on router
2. Synthetic test: inject GREEN state → spectrum route re-enabled within M cycles → verify route state on router
3. Hysteresis: single-cycle RED flash does NOT trigger failover
4. Abort path: trigger circuit breaker → abort_to_netwatch fires, all routes re-enabled, mode=dry_run
5. Live observation: no unplanned route changes during normal operation (GREEN state)
6. Health endpoint shows: `last_failover_event` with trip reason and timestamp

## Risk Mitigation

- **Hysteresis** — no single-sample decisions, minimum sustained state required
- **Abort path armed** — any trip condition still reverts to Netwatch
- **Spectrum-only** — only the Spectrum primary route is congestion-reactive. ATT and policy routes are static.
- **Observability** — every route action logged with evidence, visible in health endpoint
- **Rollback**: SIGUSR1 manual rollback to dry_run (proven in Phase 262)
- **SAFE-22**: No controller-path changes to congestion detection logic. Only new bridging layer between existing state and route management.

## Design

### Hysteresis Parameters (provisional)
- **RED threshold**: 3 consecutive RED cycles (150ms × 3 = ~1.5s minimum)
- **GREEN threshold**: 5 consecutive GREEN cycles (150ms × 5 = ~2.5s minimum)
- **Rationale**: RED needs fast response (sub-2s), GREEN needs sustained proof to prevent ping-pong

### Decision Flow
```
steering cycle → congestion state → failover_bridge → route_manager.plan_or_apply
```

The bridge lives in the daemon cycle, between the existing congestion assessment and the route_manager. It:
1. Tracks consecutive RED/GREEN counts (hysteresis state machine)
2. When RED threshold crossed → `route_manager.plan_or_apply("disable", "spectrum")`
3. When GREEN threshold crossed → `route_manager.plan_or_apply("enable", "spectrum")`
4. No-op when state is stable (no threshold crossed)

### What Does NOT Change
- Congestion detection logic (assess_congestion_state) — unchanged
- Steering confidence model — unchanged
- Binary mangle steering — unchanged (runs in parallel)
- ATT route management — static, never congestion-reactive
- Abort trip conditions — unchanged

## Execution Plan

### Wave 1: Failover Bridge Code
- Add `FailoverBridge` class in `src/wanctl/steering/failover_bridge.py`
- Hysteresis state machine: consecutive RED/GREEN counters, threshold crossing detection
- Configuration: thresholds from steering.yaml `route_management.failover` section

### Wave 2: Daemon Integration
- Wire `FailoverBridge` into daemon cycle (after congestion assessment, before abort checks)
- Spectrum-only: only act on the primary WAN's congestion state
- Config: `route_management.failover.enabled`, `red_cycles`, `green_cycles`

### Wave 3: Synthetic Tests
- Unit tests for FailoverBridge hysteresis (all edge cases: threshold boundaries, state transitions, resets)
- Integration test: mock RED/GREEN injection → verify route_manager actions
- Verify abort path still overrides failover decisions

### Wave 4: Deploy + Live Observation
- Deploy to cake-shaper
- Verify no unplanned route changes during GREEN operation
- Optional: synthetic RED injection via test tooling (if available)
- Soak: 24h minimum observation

## Entry Gates

- Phase 265 stable (4 routes reconciled, no aborts)
- Guardian watchdog running (job f557c287adfc)
- Bug fix `dd7f38b0` deployed (reload route list on SIGUSR1)

## Out of Scope

- ATT congestion-reactive failover (Phase 267+)
- Both-WAN ownership (Phase 268+)
- Netwatch deletion (Phase 269+, retirement milestone)
- Removing binary mangle steering (future decision, not automatic)

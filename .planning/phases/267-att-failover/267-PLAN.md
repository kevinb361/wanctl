# Phase 267: ATT Failover — Bidirectional WAN Route Control

**Milestone**: v1.59 (Widen-the-Canary)
**Phase**: 267
**Status**: PLANNED
**Created**: 2026-06-29
**Depends on**: Phase 266 (Spectrum failover soak cleared)

## Entry Gate

- Phase 266 soak: 24h clean observation (no flapping, no unexpected disables)
- No circuit breaker trips during Phase 266 soak
- Spectrum failover verified at least one RED→disable→GREEN→enable cycle (live or synthetic)

## Scope

Extend failover bridge to support ATT routes. When wanctl detects ATT is RED, disable ATT routes to force traffic to Spectrum. When ATT recovers, re-enable.

**Current state (266):**
- Spectrum failover only: congestion_state is primary WAN (Spectrum)
- Bridge acts on `spectrum` route key only

**Target state (267):**
- Bidirectional: Spectrum failover (266) + ATT failover (267)
- Each WAN has its own independent FailoverBridge instance
- Config-driven: which WANs get failover, with per-WAN thresholds

## Why This Matters

With only Spectrum failover, wanctl can move traffic OFF Spectrum onto ATT. But if ATT is the one congested, wanctl has no route-level tool to move traffic off ATT — it can only steer NEW connections via mangle rules. Bidirectional failover gives wanctl symmetric control.

## Design

### Per-WAN Bridges

```yaml
route_management:
  failover:
    spectrum:
      enabled: true
      red_cycles: 3
      green_cycles: 5
    att:
      enabled: true
      red_cycles: 4      # ATT gets more tolerance (backup role)
      green_cycles: 6
```

### Architecture Change

- `FailoverBridgeGroup` replaces single `FailoverBridge` in daemon
- Group holds a dict of bridges keyed by WAN name
- Each bridge needs its own congestion state source
- **Problem**: currently `congestion_state` in the daemon cycle is only for the primary WAN (Spectrum). Need a way to assess ATT congestion separately.

### Congestion Source for ATT

Options:
1. **Use the ATT wanctl controller's health endpoint** (`:9101` on cake-shaper is Spectrum; need ATT controller health) — but ATT controller may not be running as a separate wanctl instance
2. **Add secondary RTT/ping monitoring** in the steering daemon specifically for ATT failover decisions
3. **Reuse the existing WAN zone detection** — `_wan_zone` already tracks which WAN is primary

**Recommended**: Option 2 — lightweight RTT backend for ATT. The steering daemon already has `build_rtt_backend` capability. Add a secondary RTT backend pointing at ATT's gateway, assess ATT congestion independently, feed it to the ATT bridge.

### Route Keys

- ATT primary: `att` (gw=10.123.48.1, dist=2)
- ATT policy: `att_policy` (gw=10.123.48.1, dist=1, via ATT_OUT)
- When ATT is RED: disable BOTH `att` and `att_policy` (or just `att`?)
- **Decision**: disable `att` only. `att_policy` is for forcing traffic TO ATT — disabling it would break policy routing.

## Implementation Plan

### Wave 1: FailoverBridgeGroup + config refactor
- Create `FailoverBridgeGroup` managing a dict of `FailoverBridge` instances
- Config schema: `route_management.failover` becomes a dict of WAN → settings
- Backward compat: if `failover` is a flat dict (single WAN), wrap in group
- Unit tests for group management

### Wave 2: Secondary RTT backend for ATT
- Add `secondary_rtt_backend` config under `steering.yaml`
- Build ATT RTT backend in daemon init (uses same `build_rtt_backend` factory)
- Measure ATT RTT each cycle, compute ATT congestion state
- Feed ATT congestion state to ATT bridge

### Wave 3: Integration + cycle wiring
- Replace single bridge call in `run_cycle` with group iteration
- Health endpoint: `failover` becomes a dict per WAN
- Config reload: rebuild bridges when failover config changes

### Wave 4: Deploy + observe
- Deploy to cake-shaper
- Enable ATT failover in config
- Soak 24h with bidirectional failover

## Risks

1. **Extra RTT overhead**: +1 ping per cycle to ATT gateway (negligible at 2s interval)
2. **Bridge conflict**: both bridges trying to disable routes simultaneously — unlikely since only one WAN is primary at a time, but possible during failover transitions
3. **ATT congestion assessment accuracy**: single-ping RTT may not represent ATT queue state as accurately as CAKE state from the Spectrum controller

## Exit Criteria

- Both bridges operational and independent
- ATT failover triggers on RED, recovers on GREEN
- No flapping under normal load
- Health endpoint shows per-WAN failover status

## Not In Scope

- Netwatch removal (Phase 268)
- Multi-WAN load balancing (future, not widen path)
- Failover based on queue depth or packet loss (RTT only for now)

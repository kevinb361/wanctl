# Phase 265: Widen-the-Canary — Add Backup Route + Soak Validation

**Milestone**: v1.59 (Widen-the-Canary)
**Phase**: 265
**Status**: PLANNED
**Created**: 2026-06-29
**Depends on**: Phase 264 (live flip proven stable for >= 24h soak)

## Context

Phase 264 flipped wanctl to active mode with 3 routes:
- `spectrum` — "Spectrum" (gw=70.123.224.1)
- `att` — "ATT" (gw=192.168.2.254)
- `att_policy` — "Force ATT_OUT to ATT WAN" (gw=99.126.112.1)

Missing: `backup` — "Backup to Spectrum if ATT fails" (gw=70.123.224.1, distance 2)

The widen path: add the backup route, prove stability, then consider bringing Spectrum primary under full management.

## Goal

Add the "Backup to Spectrum if ATT fails" route to the active route management config and prove stable operation. Soak for 24h minimum before considering further widening.

## Requirements

- **WIDEN-01**: Backup route added to steering.yaml `route_management.routes` section
- **WIDEN-02**: Route reconciliation succeeds for all 4 routes (including new backup)
- **WIDEN-03**: No abort events during 24h soak
- **WIDEN-04**: Guard remains clean (no conflicts) during soak
- **WIDEN-05**: Circuit breaker stays closed during soak

## Success Criteria

1. `route_management.routes` has 4 entries (spectrum, att, att_policy, backup)
2. `reconciliation.status` is "ok" for all 4 routes
3. Soak watchdog reports zero alerts over 24h period
4. Health endpoint shows: mode=active, active_owner=wanctl, guard=clean, cb=closed
5. No route flapping or unexpected ownership changes

## Risk Mitigation

- **Abort path remains armed** — any trip condition reverts to Netwatch
- **One route at a time** — only adding the backup route (lowest impact)
- **Rollback**: set mode to dry_run via SIGUSR1 (proven in Phase 262)
- **SAFE-22**: No controller-path changes, only config addition

## Execution Plan

1. **Wave 1**: Add backup route to steering.yaml config (comment: "Backup to Spectrum if ATT fails")
2. **Wave 2**: Deploy config change to cake-shaper via SIGUSR1 reload (no restart needed)
3. **Wave 3**: Verify reconciliation, guard, and ownership for all 4 routes
4. **Wave 4**: 24h soak observation via watchdog cron (already running)

## Entry Gates

- Phase 264 soak period >= 24h with zero abort events
- Guardian watchdog cron job running (job f557c287adfc)
- Current active mode state: mode=active, active_owner=wanctl, guard=clean

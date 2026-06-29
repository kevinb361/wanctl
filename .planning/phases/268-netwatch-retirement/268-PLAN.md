# Phase 268: Netwatch Retirement — Full WAN Route Ownership

**Milestone**: v1.59 (Widen-the-Canary)
**Phase**: 268
**Status**: PLANNED
**Created**: 2026-06-29
**Depends on**: Phase 267 soak cleared (bidirectional failover stable 24h)

## Entry Gate

- Phase 267 soak: 24h clean with both Spectrum and ATT failover bridges operational
- At least one failover cycle verified per WAN (RED→disable→GREEN→enable)
- No flapping or circuit breaker trips during either 266 or 267 soak
- Guard status consistently clean, reconciliation stable at 4 routes

## Scope

Remove RouterOS netwatch entries entirely. wanctl's route management guard becomes the sole authority for route ownership. No more dependency on RouterOS-level monitoring for route health.

## Current State

RouterOS currently has 3 netwatch entries:
1. `/ping 8.8.8.8` → disabled (was: remove spectrum route on failure)
2. `/ping 8.8.4.4` → disabled (was: remove att route on failure)
3. `/ping 1.1.1.1` → disabled (was: remove backup route on failure)

All are disabled — no active route mutation. But they still exist as monitoring stubs from the Netwatch era.

## Why This Matters

Netwatch is the last vestige of the old routing model. Even disabled, it's:
- **Confusing**: operators see netwatch entries and wonder if they should be enabled
- **Drift risk**: someone could enable a netwatch entry and conflict with wanctl
- **Incomplete story**: "wanctl owns routes" isn't true until Netwatch is gone

After this phase, wanctl is the single source of truth for all default routes.

## Design

### What wanctl needs instead of Netwatch

Netwatch did one thing: detect WAN failure and remove the default route. Wanctl already does this via:
- **Congestion assessment** → RTT-based detection (more granular than ping)
- **Failover bridge** → hysteresis-gated route disable/enable
- **Route reconciliation** → verifies routes exist and match config

**Missing piece**: wanctl currently doesn't detect a *complete WAN outage* (router unreachable, interface down) the same way Netwatch ping would. The failover bridge only acts on congestion state, which requires RTT measurement. If the WAN is completely dead, RTT fails and congestion_state becomes... what?

### RTT Failure Mode Analysis

When ping fails (host unreachable):
- `rtt_value` from `read_rtt()` returns `None` or infinity
- Current daemon: `if rtt_value is None: return` — cycle continues, no congestion update
- Failover bridge: doesn't see a state update, so no action

**Problem**: if Spectrum goes completely offline, the bridge won't failover because it never sees RED — it sees nothing.

### Solution: Treat RTT failure as RED

Add a mechanism: if RTT measurement fails N consecutive times, treat it as RED for failover purposes. This bridges the gap between "congested" and "dead".

Implementation:
- Track consecutive RTT failures in the bridge or daemon
- After N failures (default: 3, ~6 seconds), emit RED to the bridge
- Bridge then triggers normal failover logic (with hysteresis)

This is conservative — 3 failed pings at 2s intervals = 6 seconds before even starting the RED counter. With 3 RED cycles needed for failover, total time is 6s + 1.5s = 7.5s before route disable. Acceptable for a complete outage.

### Netwatch Removal Steps

1. **Verify RTT failure → RED path works** (synthetic test first, then live dry-run)
2. **Remove netwatch entries** via RouterOS API
3. **Update guard** to no longer inspect netwatch entries
4. **Soak** with netwatch gone — verify wanctl handles outage scenarios

## Implementation Plan

### Wave 1: RTT failure → RED bridge
- Track consecutive RTT failures per WAN
- After N failures, emit RED to the corresponding bridge
- Unit tests: RTT failure triggers failover path
- Live dry-run: verify behavior without actually removing netwatch

### Wave 2: Netwatch removal + guard update
- RouterOS API call to remove netwatch entries
- Update `RouteOwnershipGuard` to no longer expect netwatch entries
- Update `RouteOwnershipInspector` to not report netwatch status
- Remove netwatch-related fields from health endpoint

### Wave 3: Integration tests + verification
- Test: WAN offline → routes disabled → WAN back → routes enabled
- Test: guard no longer reports netwatch conflicts
- Regression: ensure nothing breaks without netwatch

### Wave 4: Deploy + observe
- Deploy to cake-shaper
- Remove netwatch entries
- Soak 48h (longer because this is irreversible — well, reversible by recreating entries, but higher risk)

## Risks

1. **RTT failure detection gap**: if RTT backend itself fails (not WAN, but the measurement tool), we might false-positive failover. Mitigation: only act on complete RTT failure (None, not high RTT), and require consecutive failures.
2. **Reversibility**: removing netwatch is reversible (just add entries back), but recreating them mid-outage is risky. Always remove during a stable period.
3. **Guard false confidence**: guard currently checks for netwatch entries. After removal, guard needs a different source of truth that netwatch isn't interfering.

## Exit Criteria

- Netwatch entries removed, not recreated
- Guard reports clean without netwatch
- RTT failure → failover path verified (at least synthetic)
- 48h soak with no unexpected behavior

## Not In Scope

- Removing Netwatch CLI package from RouterOS (entries gone is enough)
- Changing how wanctl detects partial outages (congestion vs complete failure)
- Adding synthetic failure testing infrastructure

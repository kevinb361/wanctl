---
created: 2026-06-18T13:55:41Z
title: Route ownership: migrate Netwatch failover into wanctl or explicitly retire overlap
area: steering
priority: high
resolves_phase: 264
files:
  - src/wanctl/steering/daemon.py
  - src/wanctl/routeros_client.py
  - docs/STEERING.md
  - docs/DEPLOYMENT.md
  - .planning/todos/done/2026-04-01-wanctl-driven-wan-failover-via-rest-api.md
  - infra-ansible artifact: artifacts/network-changes/20260618-netwatch-policy-fix/REPORT.md
---

## Problem

`main-router` still has RouterOS Netwatch entries (`Monitor-Spectrum`, `Monitor-ATT`) that directly enable/disable WAN routes via `Enable-*` / `Disable-*` scripts. On 2026-06-18 those scripts were repaired to run with narrower `read,write,test` policy after Netwatch was firing but blocked by RouterOS script permissions.

This makes the current state sane, but ownership remains ambiguous: Netwatch is the interim hard-failover mechanism, while wanctl has richer multi-signal WAN health and already has a historical design note for wanctl-driven RouterOS route management.

If wanctl/steering later grows route mutation while Netwatch remains active, both systems could fight over the same RouterOS routes and cause route flapping or unclear incident attribution.

## Desired end state

Exactly one component owns WAN route mutation.

Preferred long-term shape:

- wanctl/steering owns route failover/failback using multi-target/multi-protocol health evidence.
- RouterOS Netwatch is disabled, retired, or converted to alert-only after wanctl route ownership is proven.
- A visible ownership guard prevents simultaneous Netwatch + wanctl route mutation.

Netwatch may remain the interim route owner until wanctl route ownership is implemented and proven.

## Requirements / acceptance criteria

- Document route ownership decision: Netwatch interim vs wanctl authoritative.
- Add a config-gated wanctl route-management mode; default must be safe/off unless explicitly enabled.
- Use RouterOS REST/API through the existing router integration boundary; do not add ad hoc shell/SSH route mutation in the hot path.
- Detect and fail closed or warn loudly if RouterOS Netwatch route-mutating entries are still active while wanctl route mutation is enabled.
- Require hysteresis / consecutive-failure thresholds; do not replace Netwatch's binary single-ping failure with an equally brittle single-target test.
- Handle circuit-breaker semantics: if wanctl crashes or loses router API access, routes must not remain in a surprising disabled state without an alert/rollback path.
- Produce alerts/logs for route disable/enable decisions with the evidence that caused them.
- Include rollback plan: disable wanctl route mutation and re-enable/restore Netwatch ownership if needed.
- Add tests for ownership guard, threshold behavior, RouterOS API failure, idempotent route enable/disable, and startup state reconciliation.

## Evidence / context

- `wanctl/.planning/todos/done/2026-04-01-wanctl-driven-wan-failover-via-rest-api.md` already captured the design thesis: Netwatch was the interim fix; wanctl route management is the richer future path.
- `infra-ansible` 2026-06-18 router audit found Netwatch script permission failures and repaired the four script policies only; route state was not manually changed.
- Current cake-autorate topology means pure `wanctl@{wan}` controllers are inactive, but `steering.service` remains active and consumes bridge-written state.

## Suggested implementation sequence

1. Design-only phase: decide whether `steering.service` is the route owner, and record Netwatch coexistence policy.
2. Read-only inventory: inspect live RouterOS Netwatch entries and target route comments before enabling any mutation.
3. Implement config-gated route owner with dry-run/observe mode first.
4. Add ownership guard: refuse active mutation if route-mutating Netwatch entries are enabled unless an explicit migration flag is set.
5. Canary on one WAN with Snapshot-A / rollback anchor and Discord/ops alert proof.
6. Disable or retire Netwatch route mutation only after wanctl route ownership is proven.

## Out of scope

- No immediate live route mutation.
- No disabling Netwatch until wanctl ownership is implemented, tested, and operator-approved.
- No threshold tuning based solely on this todo; use recorded WAN health evidence.

## Closure — 2026-07-18

Completed by v1.59. Live read-only verification shows `route_management.mode=active`, `active_owner=wanctl`, `guard.status=ok`, `conflict_count=0`, six reconciled routes, and matching observed/configured ownership. RouterOS Netwatch route mutation was retired in Phase 268. This todo no longer represents pending work.

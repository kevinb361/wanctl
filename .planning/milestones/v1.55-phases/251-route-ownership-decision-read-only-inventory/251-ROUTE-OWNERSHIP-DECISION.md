# Phase 251 — Route Ownership Decision

**Date:** 2026-06-19
**Milestone:** v1.55 Route Ownership / Netwatch Retirement
**Phase:** 251 Route Ownership Decision + Read-Only Inventory
**Status:** Decision recorded; live inventory still required for Snapshot-A

## Decision

Netwatch remains the interim route owner until wanctl route ownership is implemented, guarded, tested, canaried, and explicitly accepted.

The future target is wanctl-owned route failover/failback through `steering.service`, because current production has both WAN shaping paths owned by external cake-autorate plus wanctl state bridges while `steering.service` remains the active cross-WAN decision process consuming bridge-written state.

This is not authorization to mutate live routes. Phase 251 is read-only.

## Current Owner

RouterOS Netwatch is the current interim owner of WAN default-route mutation.

Known current model from planning/history:

- `Monitor-Spectrum` watches Spectrum reachability and calls Spectrum route scripts.
- `Monitor-ATT` watches ATT reachability and calls ATT route scripts.
- Route-mutating scripts are expected to be named `Disable-Spectrum`, `Enable-Spectrum`, `Disable-ATT`, and `Enable-ATT`.
- On 2026-06-18 those scripts were repaired to use narrower `read,write,test` policy after Netwatch fired but could not execute scripts due to RouterOS permission errors.

The live read-only inventory in this phase is the source of truth for exact current names, IDs, policies, route comments, route state, and any drift from those expectations.

## Future Owner Contract

Exactly one component may mutate WAN default routes at a time.

Allowed ownership states:

1. `netwatch-active` — Netwatch mutates WAN routes; wanctl observes only.
2. `wanctl-dry-run` — wanctl computes/logs intended route actions; Netwatch remains the only mutator.
3. `wanctl-active` — wanctl mutates WAN routes; Netwatch route mutation is disabled, retired, or converted to alert-only.
4. `manual-rollback` — operator intentionally restores Netwatch ownership using Snapshot-A evidence.

Forbidden ownership state:

- Active route-mutating Netwatch entries and active wanctl route mutation against the same WAN default routes with no guard or explicit migration gate.

## Netwatch Coexistence Policy

During v1.55 planning and implementation before an approved canary:

- Netwatch remains active/interim route owner.
- wanctl must not enable, disable, set, add, remove, or otherwise mutate WAN default routes.
- wanctl route-management implementation work must start with safe/off defaults.
- Dry-run/observe mode must be available before active mutation.
- Future active mutation must fail closed if route-mutating Netwatch entries/scripts are enabled unless an explicit migration acknowledgement is present and documented.

## Retirement Policy

Netwatch may be disabled, retired, or converted to alert-only only after all of these are true:

1. wanctl route-management config exists and defaults safe/off.
2. Dry-run/observe mode has produced sane decisions against live state.
3. Ownership guard detects route-mutating Netwatch entries/scripts.
4. Multi-signal failover/failback logic has hysteresis and startup reconciliation.
5. RouterOS route operations are idempotent and use the existing router integration boundary.
6. Snapshot-A rollback is captured and verified.
7. An operator explicitly approves an active one-WAN canary in Phase 254.
8. The canary is accepted or Netwatch rollback is proven.

## Incident Attribution

Until the ownership state changes:

- Route disable/enable events are attributed to RouterOS Netwatch and its scripts.
- wanctl/steering may influence latency-sensitive mangle steering, but does not own WAN default-route mutation.
- If WAN route state changes unexpectedly before Phase 254, inspect Netwatch entries, script run-count/last-start, RouterOS logs, and manual operator commands before blaming wanctl.

When wanctl route ownership is later enabled:

- Route decisions must log the evidence that caused disable/enable.
- Health/operator output must surface route-owner mode, guard status, last intended action, last applied action, and rollback readiness.
- Netwatch must no longer be an unguarded route mutator for those routes.

## Migration Guard Requirements

Future wanctl active route mutation must include a guard that treats enabled route-mutating Netwatch entries as an active-mode blocker.

The guard must inspect at least:

- Netwatch entries matching expected WAN monitors (`Monitor-Spectrum`, `Monitor-ATT`) and broader Spectrum/ATT patterns discovered by Snapshot-A.
- Netwatch up/down scripts that call route-mutating scripts.
- Route-mutating scripts such as `Enable-*` / `Disable-*` that target WAN default routes.
- Target route IDs/comments/gateways/distances discovered by the live inventory.

Guard behavior must be fail-closed for active mutation. Warning-only is acceptable for dry-run/observe mode, but the warning must be visible in logs and operator/health output.

## Out of Scope

Phase 251 does not:

- Disable Netwatch.
- Enable wanctl route mutation.
- Change RouterOS routes, Netwatch entries, or scripts.
- Tune failover thresholds.
- Change CAKE qdiscs or controller behavior.
- Restart live services.
- Convert Netwatch to alert-only.

## Open Inputs for Phase 252

Phase 252 should use the Phase 251 live inventory to define exact config fields and RouterOS API operations, including:

- Canonical WAN-to-route mapping keys.
- Route comment/ID anchor strategy.
- Netwatch/script discovery query strategy.
- REST support gap for `/ip/route`, `/tool/netwatch`, and `/system/script` in `RouterOSREST.run_cmd()`.
- Snapshot-A route/script names that the ownership guard must recognize.
- Whether any live naming drift means the guard should use comments, route IDs, script body parsing, or a config-declared explicit route map.

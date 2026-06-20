# Phase 254 Canary Approval Record

Timestamp: 2026-06-20T01:16:00Z

## Operator Decision

Decision: Decline active canary; keep Netwatch interim owner.

APPROVED_ACTIVE_CANARY: false

## Reason

The active route-management canary is not approved because the deployed steering service on `cake-shaper` does not currently expose the Phase 253 route-management health surface required by the Phase 254 gate.

Verified read-only evidence:

- `steering.service` is active on `cake-shaper`.
- Steering health is bound to `127.0.0.1:9102` on `cake-shaper`, not reachable directly as `10.10.110.223:9102`.
- `ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health'` returned healthy steering health for version `1.47.0`.
- The steering health payload contains `summary` and `wan_awareness`, but does not contain `route_management`.
- `/etc/wanctl/steering.yaml` on `cake-shaper` has no `route_management` block.
- The cake-shaper / cake-autorate state bridges at `10.10.110.223:9101` and `10.10.110.227:9101` are healthy, but their payload source is `cake-autorate-state-bridge` and they do not contain route-management approval fields.

## Canary Scope

No active canary scope is approved.

No route mutation is authorized.

## Authorization Statement

This approval record does not authorize route mutation, Netwatch mutation, production config mutation, systemd changes, CAKE/qdisc changes, or production default flips.

## Forbidden Actions Still Not Approved

- RouterOS route enable/disable/set/add/remove.
- RouterOS Netwatch enable/disable/set/remove.
- RouterOS script run/set/add/remove.
- Production `/etc/wanctl` or `/etc/cake-autorate` edits.
- systemd restart/reload/enable/disable.
- CAKE/qdisc changes.
- Production default flip to wanctl route ownership.
- Netwatch retirement or alert-only conversion.

## Rollback Evidence Path

- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md`

Rollback is not needed in this run because no active mutation was performed.

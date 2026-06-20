# Phase 254 Canary Runbook

Generated: 2026-06-20T01:10:00Z

## Evidence Preflight

Latest dry-run observation artifact:

- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/dry-run-observation-20260620T010520Z.md`

Latest pre-canary approval packet:

- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/pre-canary-approval-packet.md`

Snapshot-A rollback evidence:

- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md`

Drift status: human review required before canary.

Health/operator evidence verdict: blocked.

- `curl -fsS http://127.0.0.1:9102/health` failed with connection refused from this execution context.
- `wanctl.operator_summary http://127.0.0.1:9102/health` failed because the endpoint was unavailable.
- Required production `route_management` health evidence was not collected.

## Canary Scope

No active canary recommended.

There is no approved one-WAN/default-route active mutation scope in this runbook.

Both-WAN canary and Netwatch retirement are out of scope. Netwatch remains the interim route owner.

## Commands / Changes Requiring Approval

No mutation commands are approved by this runbook.

The following remain examples of mutation-shaped actions that would require a future explicit approval record before execution:

- RouterOS route enable/disable/set/add/remove.
- RouterOS Netwatch enable/disable/set/remove.
- RouterOS script run/set/add/remove.
- Production `/etc/wanctl` or `/etc/cake-autorate` edits.
- systemd restart/reload/enable/disable.
- CAKE/qdisc changes.
- Any production default flip to wanctl route ownership.

## Stop Criteria

Any future canary must refuse to start or stop immediately if any of these are true:

- steering health endpoint unavailable;
- `route_management` health section missing;
- operator summary cannot show route owner/guard/circuit/mode;
- guard status is conflict/error;
- reconciliation status is not `ok`;
- route circuit breaker is open;
- unexpected `last_applied_action` before active approval;
- RouterOS route/API command failure;
- operator abort;
- live route/Netwatch drift from rollback evidence;
- missing rollback evidence;
- observation timeout;
- any unplanned route/Netwatch state change.

## Rollback Procedure

### Code rollback

If route-management code is suspected, revert to the previously deployed wanctl version or stop using the route-management path. This is separate from route/Netwatch ownership rollback.

### Config rollback

Keep route management safe/off or dry-run only:

```yaml
route_management:
  enabled: false
  mode: "off"
  # migration_acknowledged: false
```

Do not edit production config or restart/reload services unless explicitly approved in a future canary packet.

### Route/Netwatch ownership rollback

Use Snapshot-A to restore Netwatch ownership if a future approved canary changes it:

- `Monitor-Spectrum` and `Monitor-ATT` enabled and invoking expected scripts;
- `Enable-Spectrum`, `Disable-Spectrum`, `Enable-ATT`, `Disable-ATT` present with expected route-comment actions;
- default route comments and enabled/disabled states restored from Snapshot-A;
- no manual route toggles without approved rollback procedure.

## Approval Checkpoint

CHECKPOINT REQUIRED: do not mutate routes, Netwatch, production config, systemd, CAKE/qdisc, or defaults until operator approves this runbook during Plan 254-02 execution.

Current runbook recommendation: decline active canary and keep Netwatch interim owner.

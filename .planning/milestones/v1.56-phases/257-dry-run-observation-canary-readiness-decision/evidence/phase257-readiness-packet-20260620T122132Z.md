# Phase 257 Readiness Packet

Verdict: not-ready

APPROVED_ACTIVE_CANARY: false
NETWATCH_REMAINS_OWNER: true
NO_ROUTE_OWNER_FLIP: true

## Evidence Inputs

- Command file: `.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-commands-20260620T120700Z.txt`
- Validator: `.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-validator-20260620T120700Z.py`
- Raw observation data: `.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-observation-raw-20260620T122132Z.json`
- Observation transcript: `.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-observation-transcript-20260620T122132Z.md`
- Phase 256 rollback anchors: `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-rollback-anchors-20260620T033704Z.md`
- Plan summary: `.planning/phases/257-dry-run-observation-canary-readiness-decision/257-01-SUMMARY.md`

## Readiness Criteria Matrix

| Criterion | Observed | Status | Readiness impact |
|-----------|----------|--------|------------------|
| guard status ok/supported | `guard.status=error`, `guard.active_allowed=false`, `blocked_reason=failed to read RouterOS netwatch: Command failed` | fail | Forces `not-ready`. |
| reconciliation ok | `reconciliation.status=ok`, `route_count=3` | pass | Route target reconciliation is healthy. |
| circuit breaker closed | `circuit_breaker.open=false`, `failure_count=0` | pass | Circuit does not block dry-run observation. |
| no intended mutation | `last_intended_action=null` before/after | pass | No route action was intended during observation. |
| no applied mutation | `last_applied_action=null` before/after | pass | No route action was applied during observation. |
| live route/Netwatch inventory matches targets | RouterOS identity/Netwatch/script/route read-only commands returned `255`; `/etc/wanctl/ssh/router.key` not accessible on `cake-shaper` | fail | Supported live ownership inspection was not proven. |
| rollback anchors current | Phase 256 anchors exist at `/var/lib/wanctl/phase256-backups/20260620T033704Z` per recorded evidence | pass | Rollback evidence is available for the safe/off deployment state. |
| bridge/state services healthy | `10.10.110.223:9101` and `10.10.110.227:9101` returned `status=healthy` | pass | Bridge endpoints healthy, separately from route-management acceptance. |
| SAFE-20 no-mutation proof | command-line scan found `MUTATION_TOKEN_HITS: []`; no restart/reload/route/Netwatch/qdisc commands issued | pass | No forbidden mutation class occurred. |

## Intended vs Live Summary

Route-management health from `127.0.0.1:9102/health` remained healthy and dry-run-only across a 636-second observation window:

- `enabled=true`
- `mode=dry_run`
- `active_owner=netwatch`
- `active_allowed=false`
- `guard.status=error`
- `reconciliation.status=ok`
- `reconciliation.route_count=3`
- `circuit_breaker.open=false`
- `last_intended_action=null`
- `last_applied_action=null`
- `rollback_ready=true`

Operator summary route fields agreed with the route-management payload:

- `route_owner=netwatch`
- `route_guard_status=error`
- `route_circuit_open=false`
- `route_mode=dry_run`
- `route_active_allowed=false`

Live RouterOS identity, Netwatch, script, and route inventory could not be collected through the validated SSH command shape because `cake-shaper` reported:

```text
Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory.
admin@10.10.99.1: Permission denied (publickey,password).
```

That is an evidence gap, not a mutation or remediation request.

## SAFE-20 No-Mutation Proof

Preserved.

- `APPROVED_ACTIVE_CANARY: false`
- `NETWATCH_REMAINS_OWNER: true`
- `NO_ROUTE_OWNER_FLIP: true`
- `NO_ROUTEROS_ROUTE_MUTATION: true`
- `NO_NETWATCH_MUTATION: true`
- `NO_CAKE_QDISC_CHANGE: true`
- No controller threshold retuning.
- No service restart/reload.
- No production route-owner flip.
- No active route-management canary.

The only live commands issued were the ten predeclared `COMMAND:` lines in the validated command file. The validator printed `READONLY_COMMANDS_VALIDATED`, and the local negative self-test printed `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED` before any live command execution.

## Rollback Evidence

Rollback anchor path from Phase 256:

```text
/var/lib/wanctl/phase256-backups/20260620T033704Z
```

Recorded restore commands remain in:

```text
.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-rollback-anchors-20260620T033704Z.md
```

This packet did not perform a deploy, config edit, restart, reload, route mutation, Netwatch change, CAKE/qdisc change, or owner flip, so no new rollback action was needed.

## Blockers and Remediation

1. Supported ownership inspection is still not proven.
   - Evidence: `guard.status=error` and validated RouterOS SSH inventory commands returned `255` because `/etc/wanctl/ssh/router.key` is not accessible on `cake-shaper`.
   - Impact: `ready-for-approval` is blocked by D-257-02 / D-257-03.
   - Safe remediation: fix or provision the read-only RouterOS SSH inspection path, then re-run this read-only observation packet. Do not disable Netwatch or mutate routes as part of remediation.

2. Live Netwatch/default-route inventory is missing.
   - Evidence: `/tool netwatch print detail`, `/system script print detail`, and `/ip route print detail` all failed via the validated read-only path.
   - Impact: wanctl intended route targets cannot be matched against live Netwatch/default-route state.
   - Safe remediation: prove a deterministic read-only inventory command path and repeat the comparison.

No active canary approval is requested here.

## Next Recommendation

Keep Netwatch as the active/interim route owner. Do not run an active route-management canary yet.

Recommended next phase/milestone shape: repair or provision supported read-only RouterOS ownership inspection on `cake-shaper`, then rerun a bounded read-only/dry-run observation. Only after guard status is ok/supported and live route/Netwatch inventory matches should a separate future phase ask for explicit operator approval for an active canary.

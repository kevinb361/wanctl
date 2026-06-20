# Phase 254 Pre-Canary Approval Packet

Generated: 2026-06-20T01:08:00Z

## Recommendation:

Recommendation: keep Netwatch interim owner / no active canary.

Do not proceed to active wanctl route mutation from this evidence set.

## Dry-Run Observation Verdict

Observation artifact:

- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/dry-run-observation-20260620T010520Z.md`

Verdict: blocked for active canary approval.

Reasons:

1. The cake-shaper / cake-autorate state bridge at `http://10.10.110.223:9101/health` is reachable and healthy, but its payload source is `cake-autorate-state-bridge` and it does not contain the steering `route_management` section required for route-ownership canary approval.
2. The steering health endpoint at `http://127.0.0.1:9102/health` was unavailable from the execution context. The required `route_management` section could not be scraped.
3. `wanctl.operator_summary http://127.0.0.1:9102/health` also failed because the same endpoint was unreachable. Running operator summary against cake-shaper `9101` is not a substitute because that bridge payload has no `summary` section.
4. RouterOS read-only inventory commands succeeded and produced raw artifacts, but the lightweight summary parser did not identify the expected Netwatch names from the live Netwatch output. The captured Netwatch output shows enabled simple checks for `1.1.1.1` and `8.8.8.8`, but not the names `Monitor-Spectrum` / `Monitor-ATT` in that output format.
5. No-mutation proof passed for issued command lines only.

## Snapshot-A

Snapshot-A rollback evidence path:

- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`

Snapshot-A human inventory path:

- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md`

Drift status: human review required before canary.

Read-only RouterOS evidence from this run:

- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200521/main-router__phase254_20260620T010520Z_cmd01.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200523/main-router__phase254_20260620T010520Z_cmd02.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200524/main-router__phase254_20260620T010520Z_cmd03.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200526/main-router__phase254_20260620T010520Z_cmd04.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200528/main-router__phase254_20260620T010520Z_cmd05.txt`

## Proposed Canary Scope

No active canary recommended.

A future approval packet may propose exactly one WAN/default-route scope only after all blockers are cleared:

- steering health endpoint with `route_management` is reachable from the observation context;
- cake-shaper / cake-autorate bridge health is treated as WAN congestion evidence only, not route-management approval evidence;
- operator summary exposes route owner / guard / circuit / route mode;
- Netwatch identity and route/script ownership drift are reconciled against Snapshot-A;
- rollback evidence is refreshed or confirmed current.

## Actions Still Forbidden Without Operator Approval

The following remain forbidden:

- live RouterOS route enable/disable/set/add/remove;
- RouterOS Netwatch enable/disable/set/remove;
- RouterOS script run/set/add/remove;
- production config mutation under `/etc/wanctl` or `/etc/cake-autorate`;
- systemd restart/reload/enable/disable;
- CAKE/qdisc mutation;
- production default flip to wanctl route ownership;
- Netwatch retirement or alert-only conversion.

## Stop criteria

Any future canary must stop or refuse to start if any of these occur:

- steering health endpoint unavailable;
- health `route_management.guard.status` is `conflict` or `error`;
- route reconciliation status is not `ok`;
- circuit breaker is open;
- `last_applied_action` changes unexpectedly before approved active canary;
- RouterOS route/API command failure;
- operator abort;
- live route/Netwatch drift from rollback evidence;
- missing rollback evidence;
- observation timeout;
- any unplanned route/Netwatch state change.

## Rollback procedure

### Code rollback

If route-management code causes unexpected behavior, revert to the previously deployed wanctl version or stop using the route-management code path. Code rollback is distinct from route ownership rollback.

### Config rollback

Keep or restore route management to safe/off or dry-run only:

```yaml
route_management:
  enabled: false
  mode: "off"
  # migration_acknowledged: false
```

Do not mutate production config or restart/reload services unless that action is explicitly approved in a future canary plan.

### Route/Netwatch ownership rollback

Use Snapshot-A as the rollback anchor:

- ensure `Monitor-Spectrum` and `Monitor-ATT` are enabled and calling the expected `Enable-*` / `Disable-*` scripts;
- ensure the four route-mutating scripts are present with the expected policy / ownership shape;
- restore default-route enabled/disabled states and comments from Snapshot-A;
- do not manually toggle live routes without an approved rollback procedure.

## Operator approval checklist

Before any future Plan 254-02 active canary can be approved, all boxes must be checked:

- [ ] Latest dry-run observation artifact has no evidence gaps.
- [ ] Steering health endpoint exposes `route_management` from the production observation context.
- [ ] Operator summary shows route owner, guard, circuit, and route mode.
- [ ] Netwatch names/scripts/routes are reconciled against Snapshot-A or a refreshed read-only snapshot.
- [ ] Exact one-WAN canary scope is written down.
- [ ] Stop criteria are accepted.
- [ ] Code rollback, config rollback, and route/Netwatch ownership rollback are understood.
- [ ] Operator explicitly approves active route mutation at the Plan 254-02 checkpoint.

## Final decision

Pending final Phase 254 decision. Valid final decision options:

- `keep-netwatch`
- `keep-wanctl-for-approved-scope`
- `retire-or-alert-only-netwatch`
- `rollback-to-netwatch`

Current recommendation for Plan 254-02: decline active canary and record final decision `keep-netwatch` unless the health/Netwatch evidence gaps are resolved first.

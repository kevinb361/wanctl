# Phase 256 Health Proof — Route-Management Surface + Bridge Separation

Timestamp: 2026-06-20T03:41:24Z
Host: `cake-shaper`
Deploy transcript: `phase256-deploy-restart-20260620T034124Z.md`

## Verdict

health-proof-passed

## Steering Route-Management Health

Acceptance endpoint:

```text
http://127.0.0.1:9102/health
```

Result:

```text
HEALTH healthy 1.47.0 True
```

`True` means the steering health payload contains `route_management`.

Route-management section:

```json
{
  "active_allowed": false,
  "active_owner": "netwatch",
  "blocked_reason": "ownership guard does not allow active route management",
  "circuit_breaker": {
    "failure_count": 0,
    "last_error": null,
    "open": false
  },
  "enabled": true,
  "guard": {
    "active_allowed": false,
    "blocked_reason": "failed to read RouterOS netwatch: Command failed",
    "conflict_count": 0,
    "status": "error"
  },
  "last_applied_action": null,
  "last_event": null,
  "last_intended_action": null,
  "mode": "dry_run",
  "reconciliation": {
    "checked_at": 1781926954.778941,
    "error": null,
    "route_count": 3,
    "status": "ok"
  },
  "rollback_ready": true
}
```

Acceptance interpretation:

- `route_management.enabled: true`.
- `route_management.mode: dry_run`.
- `route_management.active_owner: netwatch`.
- `route_management.active_allowed: false`.
- `last_intended_action: null`.
- `last_applied_action: null`.
- `rollback_ready: true`.
- Reconciliation found 3 configured route targets.

Fail-closed guard note:

- `guard.status: error` because REST does not support `/tool netwatch print detail`.
- This is visible evidence and blocks active route management: `active_allowed: false`.
- No route mutation occurred.

## Operator Summary Fields

The health `summary.rows[0]` exposes operator-facing route fields:

```json
{
  "route_owner": "netwatch",
  "route_guard_status": "error",
  "route_circuit_open": false,
  "route_mode": "dry_run",
  "route_active_allowed": false
}
```

This satisfies the Phase 256 visibility goal for owner/mode/guard/circuit/active-allowed state. It also surfaces the guard evidence gap for future canary readiness.

## Bridge Health Baseline

Bridge/service check:

```text
BRIDGE_SERVICES=active,active,active,active
```

Services checked:

- `cake-autorate-spectrum.service`
- `cake-autorate-att.service`
- `cake-autorate-spectrum-state-bridge.service`
- `cake-autorate-att-state-bridge.service`

Socket bindings after deploy:

```text
LISTEN 0      5      10.10.110.227:9101      0.0.0.0:*
LISTEN 0      5      10.10.110.223:9101      0.0.0.0:*
LISTEN 0      5          127.0.0.1:9102      0.0.0.0:*
```

Bridge health endpoints are `10.10.110.223:9101` and `10.10.110.227:9101`. They are not route-management acceptance. Route-management acceptance is steering localhost `127.0.0.1:9102/health`.

## Runtime / Restart Health

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
ExecMainStartTimestamp=Fri 2026-06-19 22:42:33 CDT
ExecStart=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
WorkingDirectory=/opt/wanctl
```

`NRestarts=0` indicates no automatic restart loop after the planned manual restart.

Runtime health from payload:

- status: `healthy`
- router_reachable: `true`
- cycle_budget.status: `ok`
- runtime.status: `ok`
- storage.status: `ok`
- errors.consecutive_failures: `0`
- counters.cake_read_failures: `0`

## No-Mutation Proof

Issued command transcript was reviewed from `phase256-deploy-restart-20260620T034124Z.raw.log`.

Allowed mutation classes executed:

- rsync code deployment to `/opt/wanctl` under approved rollback anchors;
- append route-management `dry_run` block to `/etc/wanctl/steering.yaml` under approved rollback anchors;
- `sudo systemctl restart steering.service` only.

Forbidden mutation classes did not occur:

- No RouterOS route mutation.
- No Netwatch disablement.
- No CAKE/qdisc change.
- No controller threshold retuning.
- No route-owner flip.
- No active route-management mode/canary.

The health payload corroborates no route apply:

- `last_intended_action: null`
- `last_applied_action: null`
- `active_allowed: false`
- `mode: dry_run`
- `active_owner: netwatch`

## Evidence Gap / Follow-Up

The route ownership guard attempts Netwatch inspection through the current REST client and receives:

```text
Unsupported command for REST API: /tool netwatch print detail
```

Impact:

- Active mode remains blocked/fail-closed.
- Safe/off/dry-run health proof is still valid.
- Future active canary readiness needs a supported Netwatch inspection method or explicit operator decision.

# Phase 256 Deploy/Restart Transcript

Timestamp: 2026-06-20T03:41:24Z
Host: `cake-shaper`
Approval record: `phase256-approval-record-20260620T034124Z.md`
Rollback anchors: `phase256-rollback-anchors-20260620T033704Z.md`
Raw transcript: `phase256-deploy-restart-20260620T034124Z.raw.log`

## Scope Executed

Executed bounded safe/off route-management surface deployment:

- deployed route-management-capable code to flat `/opt/wanctl` via rsync of `src/wanctl/`;
- added `route_management` block to `/etc/wanctl/steering.yaml`;
- target config: `enabled: true`, `mode: "dry_run"`, `migration_acknowledged: false`;
- restarted only `steering.service`;
- verified steering health and bridge service continuity.

Not executed:

- No RouterOS route mutation.
- No Netwatch disablement.
- No CAKE/qdisc change.
- No controller threshold retuning.
- No route-owner flip.
- No active route-management mode/canary.
- No restart/reload of cake-autorate or state-bridge services.

## Local Precheck

```text
.venv/bin/pytest -o addopts='' tests/test_check_config.py -k 'route_management' -q
.........                                                                [100%]
9 passed, 133 deselected in 0.37s

.venv/bin/python -m compileall -q src/wanctl
# passed
```

## Pre-State

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH healthy 1.47.0 False
BRIDGE_SERVICES=active,active,active,active
```

Interpretation:

- steering was healthy before deploy;
- health did not expose `route_management` before deploy;
- cake-autorate services and state bridges were active.

## Code Deploy

Command class:

```bash
rsync -av --delete --exclude='__pycache__' --exclude='*.pyc' --rsync-path='sudo rsync' --chmod=F644,D755 --chown=root:root src/wanctl/ cake-shaper:/opt/wanctl/
```

This matches the repo's flat deploy shape from `scripts/deploy.sh` (`src/wanctl/` to `/opt/wanctl/` with `--delete`). The transcript shows stale live `/opt/wanctl/scripts/*` files were removed because they are not part of the deployed `src/wanctl/` tree:

```text
deleting scripts/wanctl-operator-summary
deleting scripts/validate-deployment.sh
deleting scripts/phase247-fping-shadow.py
deleting scripts/compact-metrics-dbs.sh
deleting scripts/analyze_baseline.py
deleting scripts/
```

Health after deploy/restart passed, so rollback was not needed.

## Config Edit

Added this route-management target shape to `/etc/wanctl/steering.yaml`:

```yaml
route_management:
  enabled: true
  mode: "dry_run"
  migration_acknowledged: false
  routes:
    spectrum:
      comment: "Spectrum"
    att:
      comment: "ATT"
    att_policy:
      comment: "Force ATT_OUT to ATT WAN"
```

Post-edit config shape:

```json
{"enabled": true, "migration_acknowledged": false, "mode": "dry_run", "route_keys": ["att", "att_policy", "spectrum"], "route_management_present": true}
```

## Restart

Restarted only:

```text
steering.service
```

Did not restart/reload:

```text
cake-autorate-spectrum.service
cake-autorate-att.service
cake-autorate-spectrum-state-bridge.service
cake-autorate-att-state-bridge.service
```

## Post-State

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH healthy 1.47.0 True
BRIDGE_SERVICES=active,active,active,active
```

Systemd detail:

```text
Active: active (running) since Fri 2026-06-19 22:42:33 CDT
Main PID: 3949257 (python3)
ExecMainStartTimestamp=Fri 2026-06-19 22:42:33 CDT
ExecStart=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
WorkingDirectory=/opt/wanctl
User=wanctl
Group=wanctl
FragmentPath=/etc/systemd/system/steering.service
```

`NRestarts=0` means no automatic restart loop occurred after the planned manual restart.

## Route-Management Health Result

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

Interpretation:

- Route-management surface is present.
- Mode is `dry_run`.
- Active owner remains `netwatch`.
- Active route management is not allowed.
- Guard failed closed because REST does not support `/tool netwatch print detail`; this is visible as `guard.status: error` and `active_allowed: false`.
- Startup route reconciliation succeeded for 3 configured route targets.
- Circuit breaker is closed with zero failures.
- No intended or applied route action occurred.
- Rollback is ready.

## Warnings / Follow-Up

Journal warning after restart:

```text
Unsupported command for REST API: /tool netwatch print detail
```

This is a route-ownership guard evidence gap, not a mutation. It keeps active mode blocked/fail-closed. Future active-canary readiness will need either a REST-supported Netwatch inspection path, an SSH guard path, or a deliberate operator decision about Netwatch evidence.

No warning/error entries were present in `journalctl -u steering.service --since '5 minutes ago' -p warning..alert` at the final check beyond the startup warning shown in status context.

## Rollback

Rollback was not needed.

Rollback commands remain available from the preflight anchor:

```bash
sudo tar --numeric-owner --xattrs --acls -C /opt -xzf /var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz
sudo install -m 0640 -o root -g wanctl /var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml /etc/wanctl/steering.yaml
sudo systemctl restart steering.service
```

## SAFE-20

Preserved.

No RouterOS route mutation.
No Netwatch disablement.
No CAKE/qdisc change.
No controller threshold retuning.
No route-owner flip.
No active route-management mode/canary.

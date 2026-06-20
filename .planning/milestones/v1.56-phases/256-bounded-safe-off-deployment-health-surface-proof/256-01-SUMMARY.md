---
phase: 256
plan: 256-01
status: complete
completed: 2026-06-20T03:41:24Z
last_updated: 2026-06-20T03:41:24Z
requirements:
  - DEPLOY-02
  - DEPLOY-03
  - CONFIG-03
  - SAFE-20
verdict: safe-off-dry-run-deployed
---

# Phase 256 Plan 256-01 Summary — Safe/Off Dry-Run Deploy + Restart

## What Was Done

Executed the operator-approved rollback-anchor preflight, then after fresh approval executed the bounded safe/off dry-run deploy/restart from Plan 256-01.

Created:

- `evidence/phase256-approval-record-20260620T033704Z.md`
- `evidence/phase256-rollback-anchors-20260620T033704Z.md`
- `evidence/phase256-approval-record-20260620T034124Z.md`
- `evidence/phase256-deploy-restart-20260620T034124Z.raw.log`
- `evidence/phase256-deploy-restart-20260620T034124Z.md`

Remote backup directory on `cake-shaper`:

- `/var/lib/wanctl/phase256-backups/20260620T033704Z`

Remote backup artifacts:

- `/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.sha256`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/steering-shape-redacted.json`

## Key Findings

- Before deploy, `/etc/wanctl/steering.yaml` had no `route_management` block.
- Existing steering confidence was already live (`confidence.dry_run: false`), but that is existing steering behavior and not route-management.
- Backup manifest contains 304 files for the pre-deploy flat `/opt/wanctl` tree.
- Config backup checksum: `f9e57bbe8d20a92b6d13ae0b322a474620d18461ea530720c314d3475359e6e1`.
- Code backup tar checksum: `5b15673551a3b06d73807adb5b934fb925e9eced2c659c24c38394e3cd8c4fe9`.
- After deploy, `route_management` is present in steering health.
- Route-management mode is `dry_run` and `active_allowed=false`.
- Active owner remains `netwatch`.

## Deploy / Restart Result

Approved deploy target:

- `route_management.enabled: true`
- `route_management.mode: dry_run`
- `route_management.migration_acknowledged: false`

Only `steering.service` was restarted.

Post-deploy result:

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH healthy 1.47.0 True
BRIDGE_SERVICES=active,active,active,active
```

Rollback was not needed.

## Verification

Post-preflight service/health check before deploy:

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH_STATUS=healthy 1.47.0 False
BRIDGE_SERVICES=active,active,active,active
```

No restart occurred during preflight; `NRestarts` stayed `0`.

Post-deploy service/health check:

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH healthy 1.47.0 True
BRIDGE_SERVICES=active,active,active,active
```

## Not Done

Still not executed:

- no RouterOS route mutation;
- no Netwatch disablement;
- no CAKE/qdisc change;
- no route-owner flip;
- no active route-management canary.

## Restore Commands Now Available

Code tree restore:

```bash
sudo tar --numeric-owner --xattrs --acls -C /opt -xzf /var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz
```

Config restore:

```bash
sudo install -m 0640 -o root -g wanctl /var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml /etc/wanctl/steering.yaml
```

Restart after restore, only if rollback is explicitly required:

```bash
sudo systemctl restart steering.service
```

## Current Verdict

`safe-off-dry-run-deployed`

Next step is Phase 256 closeout and then Phase 257 dry-run observation/readiness decision. Active route mutation remains future-gated.

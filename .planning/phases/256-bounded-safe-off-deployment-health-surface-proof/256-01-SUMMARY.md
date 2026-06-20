---
phase: 256
plan: 256-01
status: partial-preflight-complete
completed: null
last_updated: 2026-06-20T03:37:04Z
requirements:
  - DEPLOY-02
  - DEPLOY-03
  - CONFIG-03
  - SAFE-20
verdict: rollback-anchors-created-deploy-still-gated
---

# Phase 256 Plan 256-01 Summary — Rollback Anchor Preflight Only

## What Was Done

Executed only the operator-approved rollback-anchor preflight from Plan 256-01.

Created:

- `evidence/phase256-approval-record-20260620T033704Z.md`
- `evidence/phase256-rollback-anchors-20260620T033704Z.md`

Remote backup directory on `cake-shaper`:

- `/var/lib/wanctl/phase256-backups/20260620T033704Z`

Remote backup artifacts:

- `/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.sha256`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml`
- `/var/lib/wanctl/phase256-backups/20260620T033704Z/steering-shape-redacted.json`

## Key Findings

- `/etc/wanctl/steering.yaml` currently has no `route_management` block.
- Existing steering confidence is live (`confidence.dry_run: false`), but this is existing steering behavior and not route-management.
- Backup manifest contains 304 files for the current flat `/opt/wanctl` tree.
- Config backup checksum: `f9e57bbe8d20a92b6d13ae0b322a474620d18461ea530720c314d3475359e6e1`.
- Code backup tar checksum: `5b15673551a3b06d73807adb5b934fb925e9eced2c659c24c38394e3cd8c4fe9`.

## Verification

Post-preflight service/health check:

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH_STATUS=healthy 1.47.0 False
BRIDGE_SERVICES=active,active,active,active
```

No restart occurred; `NRestarts` stayed `0`.

## Not Done

The operator approved preflight only. Therefore these remain gated and were not executed:

- no deploy;
- no live config edit;
- no `steering.service` restart/reload;
- no route-management health proof expected yet;
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

## Current Verdict

`rollback-anchors-created-deploy-still-gated`

Next step requires fresh explicit operator approval for safe/off or dry-run deploy/config edit/restart of `steering.service`.

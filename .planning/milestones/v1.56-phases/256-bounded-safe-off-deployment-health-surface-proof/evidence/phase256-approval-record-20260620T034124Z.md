# Phase 256 Approval Record

Timestamp: 2026-06-20T03:41:24Z
Operator source: chat instruction `approve option 2`

APPROVED_PHASE256_DEPLOY: true
APPROVED_PHASE256_ROLLBACK_ANCHOR_PREFLIGHT: already-complete

## Approved Scope

Approved for bounded safe/off route-management surface deployment:

- deploy route-management-capable steering code to the flat `/opt/wanctl` tree on `cake-shaper`;
- add `route_management` block to `/etc/wanctl/steering.yaml` with `enabled: true`, `mode: "dry_run"`, `migration_acknowledged: false`;
- restart only `steering.service`;
- verify steering health at `127.0.0.1:9102/health` exposes `route_management`;
- verify cake-autorate services and state bridges remain healthy;
- rollback using Phase 256 anchors if health fails.

## Explicitly Not Approved

- no RouterOS route mutation;
- no Netwatch disablement/retirement/edit;
- no CAKE/qdisc mutation;
- no controller threshold retuning;
- no route-owner flip;
- no active route-management mode/canary;
- no restart/reload of cake-autorate or state-bridge services.

## Rollback Anchors Used

Existing backup directory:

```text
/var/lib/wanctl/phase256-backups/20260620T033704Z
```

Code restore:

```bash
sudo tar --numeric-owner --xattrs --acls -C /opt -xzf /var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz
```

Config restore:

```bash
sudo install -m 0640 -o root -g wanctl /var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml /etc/wanctl/steering.yaml
```

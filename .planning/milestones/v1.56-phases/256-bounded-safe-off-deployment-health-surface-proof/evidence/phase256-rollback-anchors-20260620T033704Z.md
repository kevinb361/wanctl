# Phase 256 Rollback Anchors — Preflight Only

Timestamp: 2026-06-20T03:37:04Z
Host: `cake-shaper`
Approval record: `phase256-approval-record-20260620T033704Z.md`

## Scope Applied

Approved and executed only rollback-anchor preflight:

- privileged backup of current flat `/opt/wanctl`;
- privileged backup/redacted parse of `/etc/wanctl/steering.yaml`;
- verification of backup artifacts;
- post-preflight health/service checks.

Not executed:

- no deploy;
- no config edit;
- no service restart or reload;
- no RouterOS route mutation;
- no Netwatch disablement;
- no CAKE/qdisc change;
- no route-owner flip;
- no active route-management mode/canary.

## Backup Paths

Remote backup directory:

```text
/var/lib/wanctl/phase256-backups/20260620T033704Z
```

Artifacts:

```text
CODE_TAR=/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz
CODE_MANIFEST=/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.sha256
CONFIG_BACKUP=/var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml
CONFIG_SHAPE=/var/lib/wanctl/phase256-backups/20260620T033704Z/steering-shape-redacted.json
```

Permissions / ownership:

```text
STAT_BACKUP_DIR=/var/lib/wanctl/phase256-backups/20260620T033704Z directory 700 root:root
STAT_CODE_TAR=/var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz regular file 644 root:root 1595968
STAT_CONFIG_BACKUP=/var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml regular file 600 root:root 4706
```

## Checksums and Manifest

```text
VERIFY_BACKUP_DIR=ok
VERIFY_CODE_TAR=ok
VERIFY_CODE_MANIFEST=ok
CODE_MANIFEST_LINES=304
VERIFY_CONFIG_BACKUP=ok
VERIFY_CONFIG_SHAPE=ok
CODE_TAR_SHA256=5b15673551a3b06d73807adb5b934fb925e9eced2c659c24c38394e3cd8c4fe9
CODE_MANIFEST_SHA256=6a62811cb99dd9af835d5517b77955423a36a325f97c3fb743e6252a7e43a910
CONFIG_BACKUP_SHA256=f9e57bbe8d20a92b6d13ae0b322a474620d18461ea530720c314d3475359e6e1
CONFIG_SHAPE_SHA256=f988e37f5d7f46b9dd72f82ef5a846cb04e0e447ab1924e794e12926da2c6d85
```

Note: the first transcript attempted `wc -l < "$code_manifest"` outside sudo and got a permission-denied reporting line. The manifest had already been created by a root-shell command. The follow-up verification used `sudo -n wc -l "$code_manifest"` and verified 304 manifest lines.

## Redacted Config Shape

The live config backup was parsed through PyYAML and written as a redacted shape file on the remote host. No secrets were printed or copied into this planning artifact.

Redacted shape:

```json
{
  "confidence": {
    "dry_run": false,
    "recovery_threshold": 20,
    "steer_threshold": 55
  },
  "logging_keys": [
    "debug_log",
    "main_log"
  ],
  "mangle_rule_comment_present": true,
  "measurement": {
    "interval_seconds": 0.5,
    "ping_count": 3,
    "ping_host": "1.1.1.1"
  },
  "mode": {
    "enable_yellow_state": true,
    "reset_counters": false,
    "use_confidence_scoring": true
  },
  "path": "/etc/wanctl/steering.yaml",
  "route_management": null,
  "route_management_present": false,
  "route_management_route_keys": [],
  "router": {
    "host": "10.10.99.1",
    "port": 443,
    "transport": "rest",
    "verify_ssl": false
  },
  "state": {
    "file": "/var/lib/wanctl/steering_state.json",
    "history_size": 240
  },
  "top_level_keys": [
    "cake_state_sources",
    "capacity_protection",
    "confidence",
    "lock_file",
    "lock_timeout",
    "logging",
    "mangle_rule",
    "measurement",
    "mode",
    "router",
    "state",
    "storage",
    "thresholds",
    "timeouts",
    "topology",
    "wan_name",
    "wan_state"
  ],
  "topology": {
    "alternate_wan": "att",
    "primary_wan": "spectrum",
    "primary_wan_config": "/etc/wanctl/spectrum.yaml"
  },
  "wan_state": {
    "enabled": true,
    "grace_period_sec": 30,
    "red_weight": 25,
    "staleness_threshold_sec": 5,
    "wan_override": false
  }
}
```

Key config finding:

- `/etc/wanctl/steering.yaml` currently has no `route_management` block.
- Existing steering confidence mode is live (`confidence.dry_run: false`), but this is the existing steering behavior, not route-management; Phase 256 did not change it.

## Restore Commands

Code tree restore command:

```bash
sudo tar --numeric-owner --xattrs --acls -C /opt -xzf /var/lib/wanctl/phase256-backups/20260620T033704Z/opt-wanctl.tar.gz
```

Config restore command:

```bash
sudo install -m 0640 -o root -g wanctl /var/lib/wanctl/phase256-backups/20260620T033704Z/steering.yaml /etc/wanctl/steering.yaml
```

If a future approved deploy/restart fails after code/config changes, restore both anchors and restart only `steering.service` under that future approval's rollback path.

## Post-Preflight Health / No-Restart Proof

Follow-up verification after backup creation:

```text
SERVICE_ACTIVE=active
SERVICE_NRESTARTS=0
HEALTH_STATUS=healthy 1.47.0 False
BRIDGE_SERVICES=active,active,active,active
```

Interpretation:

- `steering.service` remained active.
- `NRestarts` remained `0`.
- steering health remained healthy at version `1.47.0`.
- steering health still did not expose `route_management`, as expected because no deploy/config edit/restart occurred.
- both cake-autorate services and both state bridges remained active.

## SAFE-20

Preserved.

No RouterOS route mutation.
No Netwatch disablement.
No CAKE/qdisc change.
No controller threshold retuning.
No production config edit.
No systemd restart/reload.
No route-owner flip.
No active route-management mode/canary.

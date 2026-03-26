# Phase 112 Plan 02: Production VM Security Audit Findings

**Audited:** 2026-03-26
**Target:** cake-shaper VM (10.10.110.223)
**Method:** SSH inline commands (per D-08)

## File Permissions (FSCAN-04)

### /etc/wanctl/ (Configuration Directory)

| Path                             | Actual | Expected | Owner       | Status |
| -------------------------------- | ------ | -------- | ----------- | ------ |
| `/etc/wanctl/`                   | 0750   | 0750     | root:wanctl | PASS   |
| `/etc/wanctl/secrets`            | 0640   | 0600     | root:wanctl | NOTE   |
| `/etc/wanctl/att.yaml`           | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/spectrum.yaml`      | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/steering.yaml`      | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/cable.yaml.example` | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/dsl.yaml.example`   | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/fiber.yaml.example` | 0640   | 0640     | root:wanctl | PASS   |
| `/etc/wanctl/ssh/`               | 0750   | 0750     | root:wanctl | PASS   |

**NOTE on `/etc/wanctl/secrets` (0640 vs expected 0600):**
The file is 0640 with owner root:wanctl. This means the `wanctl` group can read it, which is required for the wanctl service (running as `wanctl` user) to read the router password. Changing to 0600 would break the service. The plan's expectation of 0600 is incorrect -- 0640 with group=wanctl is the correct production permission for this file. No world-readable access exists.

**Additional finding:** Two `.bak` files exist with owner `root:root` (not `root:wanctl`):

- `/etc/wanctl/spectrum.yaml.bak.20260325-195530` (0640, root:root)
- `/etc/wanctl/spectrum.yaml.bak.20260326-064031` (0640, root:root)

These backup files are not readable by the wanctl group. This is acceptable since they are not used at runtime, but cleanup could be considered.

### /var/lib/wanctl/ (State Directory)

| Path                         | Actual | Expected | Owner         | Status |
| ---------------------------- | ------ | -------- | ------------- | ------ |
| `/var/lib/wanctl/`           | 0750   | 0750     | wanctl:wanctl | PASS   |
| `att_state.json`             | 0600   | 0600     | wanctl:wanctl | PASS   |
| `spectrum_state.json`        | 0600   | 0600     | wanctl:wanctl | PASS   |
| `steering_state.json`        | 0600   | 0600     | wanctl:wanctl | PASS   |
| `steering_state.json.backup` | 0600   | 0600     | wanctl:wanctl | PASS   |
| `steering_state.json.lock`   | 0644   | -        | wanctl:wanctl | NOTE   |
| `metrics.db`                 | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `metrics.db-shm`             | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `metrics.db-wal`             | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `metrics.db.corrupt`         | 0644   | -        | wanctl:wanctl | NOTE   |
| `.ssh/`                      | 0700   | 0700     | wanctl:wanctl | PASS   |

**NOTE on metrics.db (0644):** The SQLite database and its journal files (shm, wal) are world-readable (0644). While these contain only performance metrics (not secrets), restricting to 0640 would be slightly better practice. Low priority -- no sensitive data exposed.

**NOTE on metrics.db.corrupt:** A 284MB corrupt database file exists. This is dead weight on disk. Consider cleanup.

**NOTE on steering_state.json.lock:** Lock file is 0644 (world-readable, empty). Standard for lock files.

### /var/log/wanctl/ (Log Directory)

| Path                | Actual | Expected | Owner         | Status |
| ------------------- | ------ | -------- | ------------- | ------ |
| `/var/log/wanctl/`  | 0750   | 0750     | wanctl:wanctl | PASS   |
| `spectrum.log`      | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `att.log`           | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `steering.log`      | 0644   | 0640     | wanctl:wanctl | NOTE   |
| `*.log.N` (rotated) | 0644   | 0640     | wanctl:wanctl | NOTE   |

**NOTE on log files (0644):** All log files are world-readable. The directory itself restricts access (0750), so users outside the wanctl group cannot traverse to these files. However, the files themselves could be tightened to 0640. Low priority since directory permissions provide adequate access control.

### /opt/wanctl/ (Application Code)

| Path            | Actual | Expected | Owner     | Status |
| --------------- | ------ | -------- | --------- | ------ |
| `/opt/wanctl/`  | 0755   | 0755     | root:root | PASS   |
| All `.py` files | 0644   | 0644     | root:root | PASS   |
| Subdirectories  | 0755   | 0755     | root:root | PASS   |

**NOTE:** Application code is deployed as a flat directory of `.py` files (no `src/` subdirectory). Code is root-owned and world-readable, which is standard for application code that contains no secrets.

**Additional finding:** An `autorate_continuous.py.bak` (178KB) file exists in `/opt/wanctl/`. This is dead weight and should be cleaned up.

### Permissions Summary

| Category                   | Items Checked | PASS   | NOTE   | FAIL  |
| -------------------------- | ------------- | ------ | ------ | ----- |
| Config (/etc/wanctl/)      | 9             | 8      | 1      | 0     |
| State (/var/lib/wanctl/)   | 11            | 6      | 5      | 0     |
| Logs (/var/log/wanctl/)    | 8             | 1      | 7      | 0     |
| Application (/opt/wanctl/) | 3             | 3      | 0      | 0     |
| **Total**                  | **31**        | **18** | **13** | **0** |

**No FAIL findings.** All critical security permissions are correct. Notes are low-priority improvements for defense-in-depth.

---

## systemd Security Assessment (FSCAN-05)

### Service Inventory

| Unit                        | Type              | Status           | Exposure Score | Level   |
| --------------------------- | ----------------- | ---------------- | -------------- | ------- |
| `wanctl@spectrum.service`   | Template instance | active (running) | 8.4            | EXPOSED |
| `wanctl@att.service`        | Template instance | active (running) | 8.4            | EXPOSED |
| `steering.service`          | Standalone        | active (running) | 8.4            | EXPOSED |
| `wanctl-nic-tuning.service` | Oneshot           | active (exited)  | 9.6            | UNSAFE  |

**NOTE:** The steering service is named `steering.service` (not `wanctl-steering.service`). The plan referenced the wrong name. Its unit file is at `/etc/systemd/system/steering.service`.

### wanctl@spectrum.service / wanctl@att.service (Score: 8.4 EXPOSED)

Both use the same template (`wanctl@.service`), so their security analysis is identical.

**Already hardened (PASS):**

| Setting                | Status                              |
| ---------------------- | ----------------------------------- |
| `User=wanctl`          | Non-root user identity              |
| `NoNewPrivileges=yes`  | Cannot acquire new privileges       |
| `ProtectSystem=strict` | Strict read-only OS filesystem      |
| `PrivateTmp=yes`       | Isolated temp directory             |
| `ProtectHome=yes`      | No home directory access            |
| `SupplementaryGroups=` | No supplementary groups             |
| `KeyringMode=`         | No shared key material              |
| `Delegate=`            | No delegated cgroup subtree         |
| `NotifyAccess=`        | Children cannot alter service state |
| `PrivateMounts=`       | Cannot install system mounts        |

**Not hardened (top impact opportunities):**

| Setting                                          | Impact    | CAP_NET_RAW Compatible? | Notes                                                                  |
| ------------------------------------------------ | --------- | ----------------------- | ---------------------------------------------------------------------- |
| `PrivateNetwork=`                                | 0.5       | NO                      | Service requires network access for ICMP ping and router REST API      |
| `RestrictNamespaces=~user`                       | 0.3       | YES                     | Can safely restrict user namespace creation                            |
| `RestrictAddressFamilies=~...` (exotic)          | 0.3       | PARTIAL                 | Can restrict exotic but must keep AF_INET, AF_UNIX, AF_NETLINK         |
| `RestrictAddressFamilies=~AF_(INET\|INET6)`      | 0.3       | NO                      | Must keep -- service uses TCP/UDP for router comm and IRTT             |
| `CapabilityBoundingSet=~CAP_SYS_ADMIN`           | 0.3       | YES                     | Can drop SYS_ADMIN                                                     |
| `CapabilityBoundingSet=~CAP_SYS_PTRACE`          | 0.3       | YES                     | Can drop PTRACE                                                        |
| `CapabilityBoundingSet=~CAP_SET(UID\|GID\|PCAP)` | 0.3       | YES                     | Can drop UID/GID change caps                                           |
| `SystemCallArchitectures=`                       | 0.2       | YES                     | Can restrict to native arch only                                       |
| `ProtectKernelTunables=`                         | 0.2       | YES                     | Can add -- service doesn't modify sysctl                               |
| `ProtectKernelModules=`                          | 0.2       | YES                     | Can add -- service doesn't load modules                                |
| `ProtectKernelLogs=`                             | 0.2       | YES                     | Can add -- service doesn't access kernel logs                          |
| `ProtectControlGroups=`                          | 0.2       | YES                     | Can add -- service doesn't modify cgroups                              |
| `ProtectClock=`                                  | 0.2       | YES                     | Can add -- service doesn't change clock                                |
| `PrivateDevices=`                                | 0.2       | YES                     | Can add -- service doesn't use devices                                 |
| `RestrictSUIDSGID=`                              | 0.2       | YES                     | Can add -- service doesn't create SUID files                           |
| `CapabilityBoundingSet=~CAP_NET_ADMIN`           | 0.2       | CAREFUL                 | Currently granted via AmbientCapabilities; needed for tc/CAKE commands |
| `RestrictAddressFamilies=~AF_PACKET`             | 0.2       | YES                     | Can restrict packet sockets                                            |
| `IPAddressDeny=`                                 | 0.2       | PARTIAL                 | Could define allowlist but complex with dynamic router/reflector IPs   |
| `DeviceAllow=`                                   | 0.2       | YES                     | Can set empty device ACL                                               |
| `ProtectProc=`                                   | 0.2       | YES                     | Can set `invisible` or `ptraceable`                                    |
| `SystemCallFilter=~@...` (11 categories)         | 2.2 total | YES (most)              | Major reduction possible; see details below                            |
| `UMask=`                                         | 0.1       | YES                     | Set `UMask=0027` to prevent world-readable file creation               |

### steering.service (Score: 8.4 EXPOSED)

Analysis is identical to `wanctl@.service` except:

- `AmbientCapabilities=CAP_NET_RAW` only (no `CAP_NET_ADMIN`) -- steering doesn't run tc commands
- Same 10 PASS items, same unhardened items

### wanctl-nic-tuning.service (Score: 9.6 UNSAFE)

This is a `Type=oneshot` service that runs as root to configure NICs. It has almost no hardening because it runs as root and needs device/sysfs access. This is acceptable for a oneshot service that only runs at boot, but some hardening is possible.

### Current Unit Files

#### wanctl@.service (template)

```ini
[Unit]
Description=wanctl Adaptive CAKE Autorate Daemon - %i
Documentation=https://github.com/kevinb361/wanctl
After=network-online.target systemd-networkd-wait-online.service
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=300

[Service]
Type=simple
User=wanctl
Group=wanctl
WorkingDirectory=/opt/wanctl
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml
Restart=on-failure
RestartSec=5s
WatchdogSec=30s
Environment=PYTHONPATH=/opt
Environment=WANCTL_STATE_DIR=/var/lib/wanctl
Environment=WANCTL_LOG_DIR=/var/log/wanctl
Environment=WANCTL_RUN_DIR=/run/wanctl
EnvironmentFile=-/etc/wanctl/secrets
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wanctl-%i
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/wanctl /var/log/wanctl /run/wanctl
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
```

#### steering.service

```ini
[Unit]
Description=wanctl Adaptive WAN Steering Daemon
Documentation=https://github.com/kevinb361/wanctl
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=wanctl
Group=wanctl
WorkingDirectory=/opt/wanctl
ExecStart=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
Restart=on-failure
RestartSec=5s
WatchdogSec=30s
Environment=PYTHONPATH=/opt
Environment=WANCTL_STATE_DIR=/var/lib/wanctl
Environment=WANCTL_LOG_DIR=/var/log/wanctl
Environment=WANCTL_RUN_DIR=/run/wanctl
EnvironmentFile=-/etc/wanctl/secrets
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wanctl-steering
AmbientCapabilities=CAP_NET_RAW
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/wanctl /var/log/wanctl /run/wanctl
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
```

#### wanctl-nic-tuning.service

```ini
[Unit]
Description=wanctl NIC tuning (ring buffers + IRQ affinity)
After=systemd-networkd-wait-online.service
Before=wanctl@.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/ethtool -G ens16 rx 4096 tx 4096
ExecStart=/usr/sbin/ethtool -G ens17 rx 4096 tx 4096
ExecStart=/usr/sbin/ethtool -G ens27 rx 4096 tx 4096
ExecStart=/usr/sbin/ethtool -G ens28 rx 4096 tx 4096
ExecStart=/usr/sbin/ethtool -K ens16 rx-udp-gro-forwarding on
ExecStart=/usr/sbin/ethtool -K ens17 rx-udp-gro-forwarding on
ExecStart=/usr/sbin/ethtool -K ens27 rx-udp-gro-forwarding on
ExecStart=/usr/sbin/ethtool -K ens28 rx-udp-gro-forwarding on
ExecStart=/bin/bash -c "for irq in $(grep -E 'ens16|ens17' /proc/interrupts | awk '{print $1}' | tr -d ':'); do echo 0 > /proc/irq/$irq/smp_affinity_list; done"
ExecStart=/bin/bash -c "for irq in $(grep -E 'ens27|ens28' /proc/interrupts | awk '{print $1}' | tr -d ':'); do echo 1 > /proc/irq/$irq/smp_affinity_list; done"

[Install]
WantedBy=multi-user.target
```

### Hardening Opportunities

Prioritized by impact and compatibility with wanctl's requirements.

#### High Priority (Phase 115 - OPSEC-01)

These settings can be safely added with minimal risk. Combined, they could reduce the score from 8.4 to approximately 4.0-5.0.

**1. System call filtering** (2.2 exposure reduction potential)

```ini
SystemCallArchitectures=native
SystemCallFilter=~@clock @cpu-emulation @debug @module @mount @obsolete @reboot @swap
```

- Safe: wanctl uses only standard POSIX syscalls + network I/O
- Must keep: `@privileged` (for cap_net_raw), `@raw-io` (for ICMP), `@resources` (for process management)
- **CAP_NET_RAW requirement:** `@raw-io` filter must NOT be applied; ICMP raw sockets need it

**2. Kernel protection** (0.8 exposure reduction)

```ini
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
```

- All safe: wanctl doesn't touch kernel tunables, modules, or cgroups

**3. Device and filesystem** (0.6 exposure reduction)

```ini
PrivateDevices=yes
DeviceAllow=
RestrictSUIDSGID=yes
LockPersonality=yes
```

- All safe: wanctl doesn't use devices or create SUID files

**4. Namespace restriction** (0.7 exposure reduction)

```ini
RestrictNamespaces=yes
```

- Safe: wanctl doesn't create any namespaces

**5. Capability bounding** (1.5+ exposure reduction)

```ini
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
```

- For wanctl@.service: keep CAP_NET_RAW + CAP_NET_ADMIN (tc commands)
- For steering.service: keep CAP_NET_RAW only
- Drop all other capabilities (SYS_ADMIN, PTRACE, CHOWN, etc.)

**6. Address family restriction** (0.5 exposure reduction)

```ini
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
```

- Keep: AF_INET (router REST), AF_INET6 (if used), AF_UNIX (logging), AF_NETLINK (tc)
- Restrict: AF_PACKET and all exotic families

**7. UMask** (0.1 exposure reduction)

```ini
UMask=0027
```

- Prevents world-readable files. Would fix the log/metrics 0644 issue going forward.

**8. Process visibility** (0.3 exposure reduction)

```ini
ProtectProc=invisible
ProcSubset=pid
```

- Safe: wanctl doesn't inspect other processes' /proc entries

#### Low Priority / Requires Testing

**9. Memory protection** (0.1 exposure reduction)

```ini
MemoryDenyWriteExecute=yes
```

- Usually safe for Python, but some C extensions may JIT. Test before deploying.

**10. Realtime restriction** (0.1 exposure reduction)

```ini
RestrictRealtime=yes
```

- Safe unless wanctl uses RT scheduling (it doesn't).

#### Cannot Apply

| Setting              | Reason                                                |
| -------------------- | ----------------------------------------------------- |
| `PrivateNetwork=yes` | Service needs network access (router API, ICMP, IRTT) |
| `PrivateUsers=yes`   | Conflicts with AmbientCapabilities                    |
| `IPAddressDeny=`     | Router and reflector IPs are dynamic/configurable     |
| `RootDirectory=`     | Would require full chroot setup, high risk            |
| `RemoveIPC=yes`      | Requires DynamicUser or explicit IPC cleanup          |

### Estimated Score After Hardening

With all high-priority items applied:

| Unit                        | Current     | Estimated After    | Reduction   |
| --------------------------- | ----------- | ------------------ | ----------- |
| `wanctl@spectrum.service`   | 8.4 EXPOSED | ~3.5-4.5 OK/MEDIUM | ~4.0 points |
| `wanctl@att.service`        | 8.4 EXPOSED | ~3.5-4.5 OK/MEDIUM | ~4.0 points |
| `steering.service`          | 8.4 EXPOSED | ~3.5-4.5 OK/MEDIUM | ~4.0 points |
| `wanctl-nic-tuning.service` | 9.6 UNSAFE  | ~8.0 EXPOSED       | ~1.6 points |

The NIC tuning service will remain high because it runs as root and needs hardware access. This is acceptable for a oneshot boot service.

### Cleanup Opportunities Found

1. **metrics.db.corrupt** (284MB) in `/var/lib/wanctl/` -- dead weight, safe to remove
2. **autorate_continuous.py.bak** (178KB) in `/opt/wanctl/` -- dead weight, safe to remove
3. **spectrum.yaml.bak.\*** (2 files) in `/etc/wanctl/` -- dead weight, safe to remove after confirming no rollback need

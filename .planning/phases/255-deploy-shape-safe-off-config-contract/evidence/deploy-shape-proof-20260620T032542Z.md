# Phase 255 Deploy-Shape Proof

Timestamp: 20260620T032542Z

## Command Validation

- Command file: `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/deploy-shape-readonly-commands-20260620T032457Z.txt`
- Validation artifact: `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/deploy-shape-command-validation-20260620T032457Z.json`
- passed: true
- command count: 23

## Issued Commands

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper hostnamectl --static

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper uname -a

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper uptime

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl is-active steering.service cake-autorate-spectrum.service cake-autorate-att.service cake-autorate-spectrum-state-bridge.service cake-autorate-att-state-bridge.service

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl status steering.service --no-pager -l

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl cat steering.service

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl show steering.service -p FragmentPath -p ExecStart -p WorkingDirectory -p User -p Group -p Environment -p NRestarts

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper pgrep -af wanctl

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper pgrep -af steering

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper ss -ltnp

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper readlink -f /opt/wanctl

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper stat -c %n__%F__%a__%U:%G__%s__%y /etc/wanctl/steering.yaml /opt/wanctl

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper ls -ld /opt/wanctl /opt/wanctl/.git /etc/wanctl /run/wanctl /var/lib/wanctl

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl rev-parse HEAD

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl status --short --branch

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl log -1 --oneline

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper python3 -V

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper /opt/wanctl/.venv/bin/python -V

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n route_management /etc/wanctl/steering.yaml

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n health /etc/wanctl/steering.yaml

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n port /etc/wanctl/steering.yaml

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper curl -fsS http://127.0.0.1:9102/health

COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper curl -fsS http://127.0.0.1:9101/health

## Host and Service Identity

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper hostnamectl --static
EXIT: 0
cake-shaper
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper uname -a
EXIT: 0
Linux cake-shaper 6.12.90+deb13.1-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.12.90-2 (2026-05-27) x86_64 GNU/Linux
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper uptime
EXIT: 0
22:25:43 up 3 days,  7:09,  1 user,  load average: 0.09, 0.10, 0.14
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl is-active steering.service cake-autorate-spectrum.service cake-autorate-att.service cake-autorate-spectrum-state-bridge.service cake-autorate-att-state-bridge.service
EXIT: 0
active
active
active
active
active
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl status steering.service --no-pager -l
EXIT: 0
● steering.service - wanctl Adaptive WAN Steering Daemon
     Loaded: loaded (/etc/systemd/system/steering.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-06-18 19:33:28 CDT; 1 day 2h ago
 Invocation: 86ef7d701834428a805c3cbe31ef955e
       Docs: https://github.com/kevinb361/wanctl
   Main PID: 2763525 (python3)
      Tasks: 2 (limit: 32)
     Memory: 81.2M (high: 256M, max: 384M, available: 174.7M, peak: 83M)
        CPU: 36min 29.858s
     CGroup: /system.slice/steering.service
             └─2763525 /usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml

Jun 19 22:22:09 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:22:09,463 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=32.4ms ewma=16.3ms drops=0 q=0 | early warning, no action
Jun 19 22:22:10 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:22:10,461 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=29.7ms ewma=17.1ms drops=0 q=0 | early warning, no action
Jun 19 22:22:30 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:22:30,982 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=41.4ms ewma=17.4ms drops=0 q=0 | early warning, no action
Jun 19 22:24:27 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:27,547 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=44.1ms ewma=16.6ms drops=0 q=0 | early warning, no action
Jun 19 22:24:50 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:50,556 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=39.0ms ewma=18.9ms drops=0 q=0 | early warning, no action
Jun 19 22:24:51 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:51,064 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=46.1ms ewma=27.1ms drops=0 q=0 | early warning, no action
Jun 19 22:24:51 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:51,517 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=0.3ms ewma=19.0ms drops=0 q=0 | early warning, no action
Jun 19 22:24:52 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:52,062 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=44.4ms ewma=26.6ms drops=0 q=0 | early warning, no action
Jun 19 22:24:52 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:52,520 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=1.3ms ewma=19.0ms drops=0 q=0 | early warning, no action
Jun 19 22:24:53 cake-shaper wanctl-steering[2763525]: 2026-06-19 22:24:53,026 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=8.4ms ewma=15.8ms drops=0 q=0 | early warning, no action
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl show steering.service -p FragmentPath -p ExecStart -p WorkingDirectory -p User -p Group -p Environment -p NRestarts
EXIT: 0
NRestarts=0
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml ; ignore_errors=no ; start_time=[Thu 2026-06-18 19:33:28 CDT] ; stop_time=[n/a] ; pid=2763525 ; code=(null) ; status=0/0 }
Environment=PYTHONPATH=/opt WANCTL_STATE_DIR=/var/lib/wanctl WANCTL_LOG_DIR=/var/log/wanctl WANCTL_RUN_DIR=/run/wanctl
WorkingDirectory=/opt/wanctl
User=wanctl
Group=wanctl
FragmentPath=/etc/systemd/system/steering.service
```

## Steering Unit and Process Shape

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl cat steering.service
EXIT: 0
# /etc/systemd/system/steering.service
[Unit]
Description=wanctl Adaptive WAN Steering Daemon
Documentation=https://github.com/kevinb361/wanctl
After=network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=300

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
NoNewPrivileges=yes

# Filesystem protection
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ReadWritePaths=/var/lib/wanctl /var/log/wanctl /run/wanctl

# Kernel protection
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
LockPersonality=yes

# Capability bounding -- steering only needs CAP_NET_RAW (no tc commands)
CapabilityBoundingSet=CAP_NET_RAW

# Namespace and address family restrictions
RestrictNamespaces=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
RestrictSUIDSGID=yes
RestrictRealtime=yes

# System call filtering
SystemCallArchitectures=native
SystemCallFilter=~@clock @cpu-emulation @debug @module @mount @obsolete @reboot @swap

# Memory and process
MemoryDenyWriteExecute=yes
UMask=0027

# Process visibility
ProtectProc=invisible
ProcSubset=pid

# Device ACL
DeviceAllow=

# Resource limits (sized from production observation 2026-03-26)
# Steering cgroup=221MB RSS=57MB, Tasks=2
MemoryMax=384M
MemoryHigh=256M
TasksMax=32
LimitNOFILE=1024

[Install]
WantedBy=multi-user.target
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper systemctl show steering.service -p FragmentPath -p ExecStart -p WorkingDirectory -p User -p Group -p Environment -p NRestarts
EXIT: 0
NRestarts=0
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml ; ignore_errors=no ; start_time=[Thu 2026-06-18 19:33:28 CDT] ; stop_time=[n/a] ; pid=2763525 ; code=(null) ; status=0/0 }
Environment=PYTHONPATH=/opt WANCTL_STATE_DIR=/var/lib/wanctl WANCTL_LOG_DIR=/var/log/wanctl WANCTL_RUN_DIR=/run/wanctl
WorkingDirectory=/opt/wanctl
User=wanctl
Group=wanctl
FragmentPath=/etc/systemd/system/steering.service
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper pgrep -af wanctl
EXIT: 0
794 /bin/sh /usr/local/sbin/wanctl-bpctl-watchdog-petter
924 /bin/sh /usr/local/sbin/wanctl-bpctl-watchdog-petter
2763525 /usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper pgrep -af steering
EXIT: 0
2763525 /usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper ss -ltnp
EXIT: 0
State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
LISTEN 0      5      10.10.110.227:9101      0.0.0.0:*          
LISTEN 0      5      10.10.110.223:9101      0.0.0.0:*          
LISTEN 0      128          0.0.0.0:22        0.0.0.0:*          
LISTEN 0      5          127.0.0.1:9102      0.0.0.0:*          
LISTEN 0      128             [::]:22           [::]:*
```


Repo unit reference: `deploy/systemd/steering.service`. Live unit content above is the observed source for Phase 256 planning.

## Code Deployment Shape

- `/opt/wanctl` git HEAD: `unknown`
- `/opt/wanctl` git status: `unknown`

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper readlink -f /opt/wanctl
EXIT: 0
/opt/wanctl
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper stat -c %n__%F__%a__%U:%G__%s__%y /etc/wanctl/steering.yaml /opt/wanctl
EXIT: 1
/opt/wanctl__directory__755__root:root__4096__2026-06-19 15:16:40.884155965 -0500
STDERR:
stat: cannot statx '/etc/wanctl/steering.yaml': Permission denied
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper ls -ld /opt/wanctl /opt/wanctl/.git /etc/wanctl /run/wanctl /var/lib/wanctl
EXIT: 2
drwxr-x--- 4 root   wanctl 4096 Jun 19 15:17 /etc/wanctl
drwxr-xr-x 9 root   root   4096 Jun 19 15:16 /opt/wanctl
drwxr-xr-x 2 wanctl wanctl  140 Jun 19 15:17 /run/wanctl
drwxr-x--- 5 wanctl wanctl 4096 Jun 19 22:25 /var/lib/wanctl
STDERR:
ls: cannot access '/opt/wanctl/.git': No such file or directory
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl rev-parse HEAD
EXIT: 128
STDERR:
fatal: not a git repository (or any of the parent directories): .git
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl status --short --branch
EXIT: 128
STDERR:
fatal: not a git repository (or any of the parent directories): .git
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper git -C /opt/wanctl log -1 --oneline
EXIT: 128
STDERR:
fatal: not a git repository (or any of the parent directories): .git
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper python3 -V
EXIT: 0
Python 3.13.5
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper /opt/wanctl/.venv/bin/python -V
EXIT: 127
STDERR:
bash: line 1: /opt/wanctl/.venv/bin/python: No such file or directory
```


Code rollback anchor: blocked/unknown from read-only inspection; Phase 256 must not proceed until this is resolved.

## Config Shape

- `/etc/wanctl/steering.yaml` route_management shape: absent-or-not-found

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n route_management /etc/wanctl/steering.yaml
EXIT: 2
STDERR:
grep: /etc/wanctl/steering.yaml: Permission denied
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n health /etc/wanctl/steering.yaml
EXIT: 2
STDERR:
grep: /etc/wanctl/steering.yaml: Permission denied
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper grep -n port /etc/wanctl/steering.yaml
EXIT: 2
STDERR:
grep: /etc/wanctl/steering.yaml: Permission denied
```

Secrets were not intentionally read or printed; only targeted grep/stat metadata was collected.

## Health Binding Baseline

- Steering health `127.0.0.1:9102`: ok

- Steering health contains `route_management`: False

- Bridge health `127.0.0.1:9101`: failed

- Bridge health on `:9101` is bridge/rate-state evidence only, not route-management acceptance evidence.
- `:9101` is not route-management acceptance for Phase 256.

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper curl -fsS http://127.0.0.1:9102/health
EXIT: 0
{
  "status": "healthy",
  "uptime_seconds": 96733.8,
  "version": "1.47.0",
  "steering": {
    "enabled": false,
    "state": "SPECTRUM_GOOD",
    "mode": "active"
  },
  "congestion": {
    "primary": {
      "state": "GREEN",
      "state_code": 0,
      "tins": [
        {
          "tin_name": "Bulk",
          "dropped_packets": 0,
          "ecn_marked_packets": 0,
          "avg_delay_us": 3,
          "peak_delay_us": 10,
          "backlog_bytes": 0,
          "sparse_flows": 8,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "BestEffort",
          "dropped_packets": 67755,
          "ecn_marked_packets": 604,
          "avg_delay_us": 32,
          "peak_delay_us": 112,
          "backlog_bytes": 0,
          "sparse_flows": 3,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Video",
          "dropped_packets": 524454,
          "ecn_marked_packets": 14348,
          "avg_delay_us": 41,
          "peak_delay_us": 90,
          "backlog_bytes": 0,
          "sparse_flows": 0,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Voice",
          "dropped_packets": 1,
          "ecn_marked_packets": 0,
          "avg_delay_us": 2,
          "peak_delay_us": 11,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        }
      ]
    }
  },
  "decision": {
    "last_transition_time": "2026-06-19T18:01:00.158699+00:00",
    "time_in_state_seconds": 33883.2
  },
  "counters": {
    "red_count": 0,
    "good_count": 0,
    "cake_read_failures": 0
  },
  "confidence": {
    "primary": 0
  },
  "errors": {
    "consecutive_failures": 0,
    "cake_read_failures": 0
  },
  "thresholds": {
    "green_rtt_ms": 5.0,
    "yellow_rtt_ms": 15.0,
    "red_rtt_ms": 15.0,
    "red_samples_required": 2,
    "green_samples_required": 15
  },
  "router_connectivity": {
    "is_reachable": true,
    "consecutive_failures": 0,
    "last_failure_type": null,
    "last_failure_time": null,
    "outage_duration_seconds": null
  },
  "pid": 2763525,
  "cycle_budget": {
    "cycle_time_ms": {
      "avg": 41.4,
      "p95": 60.2,
      "p99": 81.8
    },
    "utilization_pct": 8.3,
    "overrun_count": 299,
    "status": "ok",
    "warning_threshold_pct": 80.0
  },
  "rtt_source": {
    "current": "wanctl_backend",
    "last_successful": "wanctl_backend",
    "last_rtt_ms": 23.34,
    "last_measurement_age_sec": 0.336,
    "counts": {
      "wanctl_backend": 192981,
      "autorate_health": 286,
      "autorate_irtt": 0,
      "history_fallback": 0
    },
    "producer": "wanctl-backend",
    "backend": "icmplib",
    "source_ip": "10.10.110.223"
  },
  "wan_awareness": {
    "enabled": true,
    "zone": "GREEN",
    "effective_zone": "GREEN",
    "grace_period_active": false,
    "staleness_age_sec": 0.7,
    "stale": false,
    "confidence_contribution": 0,
    "degrade_timer_remaining": null
  },
  "storage": {
    "pending_writes": 0,
    "queue": {
      "drained_total": 0,
      "error_total": 0
    },
    "writes": {
      "success_total": 193338,
      "failure_total": 0,
      "lock_failure_total": 0,
      "volume_total": 4445283,
      "last_duration_ms": 0.4489370039664209,
      "max_duration_ms": 728.6828809883446
    },
    "checkpoint": {
      "busy": 0,
      "wal_pages": 0,
      "checkpointed_pages": 0,
      "maintenance_lock_skipped_total": 0
    },
    "files": {
      "db_bytes": 733679616,
      "wal_bytes": 4255992,
      "shm_bytes": 32768,
      "total_bytes": 737968376,
      "db_exists": true,
      "wal_exists": true,
      "shm_exists": true
    },
    "status": "ok"
  },
  "runtime": {
    "process": "steering",
    "rss_bytes": 90288128,
    "swap_bytes": 0,
    "memory_status": "ok",
    "swap_status": "ok",
    "cycle_status": "ok",
    "status": "ok"
  },
  "alerting": {
    "enabled": false,
    "fire_count": 0,
    "active_cooldowns": []
  },
  "router_reachable": true,
  "disk_space": {
    "path": "/var/lib/wanctl",
    "free_bytes": 12588806144,
    "total_bytes": 30878322688,
    "free_pct": 40.8,
    "status": "ok"
  },
  "summary": {
    "service": "steering",
    "status": "healthy",
    "alerts": {
      "enabled": false,
      "fire_count": 0,
      "active_cooldowns": 0,
      "status": "disabled"
    },
    "rows": [
      {
        "name": "steering",
        "status": "ok",
        "state": "SPECTRUM_GOOD",
        "congestion_state": "GREEN",
        "wan_zone": "GREEN",
        "router_reachable": true,
        "storage_status": "ok",
        "runtime_status": "ok"
      }
    ]
  }
}
```

```text
COMMAND: ssh -o BatchMode=yes -o ConnectTimeout=10 cake-shaper curl -fsS http://127.0.0.1:9101/health
EXIT: 7
STDERR:
curl: (7) Failed to connect to 127.0.0.1 port 9101 after 0 ms: Could not connect to server
```

## Rollback Anchor Readiness

- Code rollback anchor: blocked/unknown

- Config rollback anchor: current `/etc/wanctl/steering.yaml` metadata observed read-only; Phase 256 must create a dated backup before any live edit.

- Service rollback/stop signals: current steering and bridge service states above; Phase 256 must compare post-deploy health and rollback on degradation.

- Snapshot-A remains future route/Netwatch ownership anchor; Phase 255 did not touch RouterOS.

## No-Mutation Proof

- scanned: COMMAND lines only
- passed: true

- forbidden live mutation commands found: none

## Phase 256 Readiness

ready-for-phase256-proposal

Read-only inspection reached cake-shaper and steering health. Phase 256 proposal may be drafted, but deploy/restart remains explicitly approval-gated.

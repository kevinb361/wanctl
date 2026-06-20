# Phase 257 Observation Transcript

Timestamp: 20260620T122132Z
Host: `cake-shaper` via validated read-only command file

## Command Allowlist Proof

Command file: `/home/kevin/projects/wanctl/.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-commands-20260620T120700Z.txt`
Validator: `/home/kevin/projects/wanctl/.planning/phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-validator-20260620T120700Z.py`

Validator output:
```text
READONLY_COMMANDS_VALIDATED
```

Negative self-test output:
```text
READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED
```

Validated command file contents:
```text
COMMAND: ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health'
COMMAND: ssh cake-shaper 'systemctl is-active steering.service'
COMMAND: ssh cake-shaper 'systemctl show steering.service --property=NRestarts,ExecMainStartTimestamp,ExecStart,WorkingDirectory --no-pager'
COMMAND: ssh cake-shaper 'journalctl -u steering.service --since "-15 minutes" --no-pager'
COMMAND: ssh cake-shaper 'curl -fsS http://10.10.110.223:9101/health'
COMMAND: ssh cake-shaper 'curl -fsS http://10.10.110.227:9101/health'
COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system identity print"'
COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/tool netwatch print detail"'
COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system script print detail"'
COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/ip route print detail"'
```

## Steering Route-Management Health Before

### Steering Route-Management Health Before — 127.0.0.1:9102/health

COMMAND: ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health'
started: 2026-06-20T12:21:56Z
ended: 2026-06-20T12:21:57Z
returncode: 0

stdout:
```text
{
  "status": "healthy",
  "uptime_seconds": 31162.7,
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
          "avg_delay_us": 4,
          "peak_delay_us": 14,
          "backlog_bytes": 0,
          "sparse_flows": 7,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "BestEffort",
          "dropped_packets": 67759,
          "ecn_marked_packets": 604,
          "avg_delay_us": 20,
          "peak_delay_us": 126,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 1,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Video",
          "dropped_packets": 524520,
          "ecn_marked_packets": 14348,
          "avg_delay_us": 130,
          "peak_delay_us": 280,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Voice",
          "dropped_packets": 1,
          "ecn_marked_packets": 0,
          "avg_delay_us": 2,
          "peak_delay_us": 6,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        }
      ]
    }
  },
  "decision": {
    "last_transition_time": null,
    "time_in_state_seconds": 31162.7
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
  "pid": 3949257,
  "cycle_budget": {
    "cycle_time_ms": {
      "avg": 38.5,
      "p95": 49.5,
      "p99": 61.1
    },
    "utilization_pct": 7.7,
    "overrun_count": 36,
    "status": "ok",
    "warning_threshold_pct": 80.0
  },
  "rtt_source": {
    "current": "wanctl_backend",
    "last_successful": "wanctl_backend",
    "last_rtt_ms": 24.05,
    "last_measurement_age_sec": 0.349,
    "counts": {
      "wanctl_backend": 62235,
      "autorate_health": 32,
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
    "staleness_age_sec": 0.5,
    "stale": false,
    "confidence_contribution": 0,
    "degrade_timer_remaining": null
  },
  "route_management": {
    "enabled": true,
    "mode": "dry_run",
    "active_owner": "netwatch",
    "active_allowed": false,
    "blocked_reason": "ownership guard does not allow active route management",
    "guard": {
      "status": "error",
      "active_allowed": false,
      "conflict_count": 0,
      "blocked_reason": "failed to read RouterOS netwatch: Command failed"
    },
    "reconciliation": {
      "status": "ok",
      "error": null,
      "route_count": 3,
      "checked_at": 1781926954.778941
    },
    "circuit_breaker": {
      "open": false,
      "failure_count": 0,
      "last_error": null
    },
    "last_intended_action": null,
    "last_applied_action": null,
    "rollback_ready": true,
    "last_event": null
  },
  "storage": {
    "pending_writes": 0,
    "queue": {
      "drained_total": 0,
      "error_total": 0
    },
    "writes": {
      "success_total": 62268,
      "failure_total": 0,
      "lock_failure_total": 0,
      "volume_total": 1432143,
      "last_duration_ms": 0.5270360270515084,
      "max_duration_ms": 963.1537040113471
    },
    "checkpoint": {
      "busy": 0,
      "wal_pages": 0,
      "checkpointed_pages": 0,
      "maintenance_lock_skipped_total": 0
    },
    "files": {
      "db_bytes": 732389376,
      "wal_bytes": 4243632,
      "shm_bytes": 32768,
      "total_bytes": 736665776,
      "db_exists": true,
      "wal_exists": true,
      "shm_exists": true
    },
    "status": "ok"
  },
  "runtime": {
    "process": "steering",
    "rss_bytes": 85970944,
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
    "free_bytes": 12567453696,
    "total_bytes": 30878322688,
    "free_pct": 40.7,
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
        "runtime_status": "ok",
        "route_owner": "netwatch",
        "route_guard_status": "error",
        "route_circuit_open": false,
        "route_mode": "dry_run",
        "route_active_allowed": false
      }
    ]
  }
}
```

stderr:
```text
(empty)
```

## Bounded Observation Window

Window start: 2026-06-20T12:21:57Z
Window end: 2026-06-20T12:32:33Z
Duration: 636 seconds

Service state samples collected before and after the bounded observation window; journal lines cover `--since "-15 minutes"` using the validated command file.

### Service State / Metadata Before

### steering.service active state

COMMAND: ssh cake-shaper 'systemctl is-active steering.service'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 0

stdout:
```text
active
```

stderr:
```text
(empty)
```

### steering.service restart/start metadata

COMMAND: ssh cake-shaper 'systemctl show steering.service --property=NRestarts,ExecMainStartTimestamp,ExecStart,WorkingDirectory --no-pager'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 0

stdout:
```text
NRestarts=0
ExecMainStartTimestamp=Fri 2026-06-19 22:42:33 CDT
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml ; ignore_errors=no ; start_time=[Fri 2026-06-19 22:42:33 CDT] ; stop_time=[n/a] ; pid=3949257 ; code=(null) ; status=0/0 }
WorkingDirectory=/opt/wanctl
```

stderr:
```text
(empty)
```

## Steering Route-Management Health After

### Steering Route-Management Health After — 127.0.0.1:9102/health

COMMAND: ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health'
started: 2026-06-20T12:32:33Z
ended: 2026-06-20T12:32:33Z
returncode: 0

stdout:
```text
{
  "status": "healthy",
  "uptime_seconds": 31798.9,
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
          "avg_delay_us": 4,
          "peak_delay_us": 13,
          "backlog_bytes": 0,
          "sparse_flows": 6,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "BestEffort",
          "dropped_packets": 67759,
          "ecn_marked_packets": 604,
          "avg_delay_us": 27,
          "peak_delay_us": 267,
          "backlog_bytes": 0,
          "sparse_flows": 3,
          "bulk_flows": 1,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Video",
          "dropped_packets": 524520,
          "ecn_marked_packets": 14348,
          "avg_delay_us": 126,
          "peak_delay_us": 234,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        },
        {
          "tin_name": "Voice",
          "dropped_packets": 1,
          "ecn_marked_packets": 0,
          "avg_delay_us": 2,
          "peak_delay_us": 9,
          "backlog_bytes": 0,
          "sparse_flows": 1,
          "bulk_flows": 0,
          "unresponsive_flows": 0
        }
      ]
    }
  },
  "decision": {
    "last_transition_time": null,
    "time_in_state_seconds": 31798.9
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
  "pid": 3949257,
  "cycle_budget": {
    "cycle_time_ms": {
      "avg": 37.1,
      "p95": 47.1,
      "p99": 58.9
    },
    "utilization_pct": 7.4,
    "overrun_count": 36,
    "status": "ok",
    "warning_threshold_pct": 80.0
  },
  "rtt_source": {
    "current": "wanctl_backend",
    "last_successful": "wanctl_backend",
    "last_rtt_ms": 24.04,
    "last_measurement_age_sec": 0.465,
    "counts": {
      "wanctl_backend": 63506,
      "autorate_health": 32,
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
    "staleness_age_sec": 0.1,
    "stale": false,
    "confidence_contribution": 0,
    "degrade_timer_remaining": null
  },
  "route_management": {
    "enabled": true,
    "mode": "dry_run",
    "active_owner": "netwatch",
    "active_allowed": false,
    "blocked_reason": "ownership guard does not allow active route management",
    "guard": {
      "status": "error",
      "active_allowed": false,
      "conflict_count": 0,
      "blocked_reason": "failed to read RouterOS netwatch: Command failed"
    },
    "reconciliation": {
      "status": "ok",
      "error": null,
      "route_count": 3,
      "checked_at": 1781926954.778941
    },
    "circuit_breaker": {
      "open": false,
      "failure_count": 0,
      "last_error": null
    },
    "last_intended_action": null,
    "last_applied_action": null,
    "rollback_ready": true,
    "last_event": null
  },
  "storage": {
    "pending_writes": 0,
    "queue": {
      "drained_total": 0,
      "error_total": 0
    },
    "writes": {
      "success_total": 63539,
      "failure_total": 0,
      "lock_failure_total": 0,
      "volume_total": 1461376,
      "last_duration_ms": 0.5421849782578647,
      "max_duration_ms": 963.1537040113471
    },
    "checkpoint": {
      "busy": 0,
      "wal_pages": 0,
      "checkpointed_pages": 0,
      "maintenance_lock_skipped_total": 0
    },
    "files": {
      "db_bytes": 732352512,
      "wal_bytes": 4251872,
      "shm_bytes": 32768,
      "total_bytes": 736637152,
      "db_exists": true,
      "wal_exists": true,
      "shm_exists": true
    },
    "status": "ok"
  },
  "runtime": {
    "process": "steering",
    "rss_bytes": 86036480,
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
    "free_bytes": 12566732800,
    "total_bytes": 30878322688,
    "free_pct": 40.7,
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
        "runtime_status": "ok",
        "route_owner": "netwatch",
        "route_guard_status": "error",
        "route_circuit_open": false,
        "route_mode": "dry_run",
        "route_active_allowed": false
      }
    ]
  }
}
```

stderr:
```text
(empty)
```

## Steering Journal for Window

### steering.service journal for bounded observation window

COMMAND: ssh cake-shaper 'journalctl -u steering.service --since "-15 minutes" --no-pager'
started: 2026-06-20T12:32:33Z
ended: 2026-06-20T12:32:33Z
returncode: 0

stdout:
```text
Jun 20 07:18:42 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:18:42,944 [steering] [WARNING] Ping to 1.1.1.1 failed (no response)
Jun 20 07:18:55 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:18:55,993 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=6.6ms ewma=3.2ms drops=0 q=19 | early warning, no action
Jun 20 07:21:25 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:21:25,071 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=1.7ms ewma=2.7ms drops=0 q=12 | early warning, no action
Jun 20 07:25:26 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:25:26,735 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=29.6ms ewma=10.6ms drops=0 q=15 | early warning, no action
Jun 20 07:27:45 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:27:45,546 [steering] [INFO] Periodic maintenance: deleted=41377, downsampled=0, vacuumed=True
Jun 20 07:29:25 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:29:25,143 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=52.2ms ewma=17.4ms drops=0 q=0 | early warning, no action
Jun 20 07:29:25 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:29:25,620 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=27.9ms ewma=20.5ms drops=0 q=0 | early warning, no action
Jun 20 07:29:26 cake-shaper wanctl-steering[3949257]: 2026-06-20 07:29:26,099 [steering] [INFO] [SPECTRUM_GOOD] [YELLOW] delta=7.8ms ewma=16.7ms drops=0 q=0 | early warning, no action
```

stderr:
```text
(empty)
```

### Service Metadata After

### steering.service restart/start metadata after window

COMMAND: ssh cake-shaper 'systemctl show steering.service --property=NRestarts,ExecMainStartTimestamp,ExecStart,WorkingDirectory --no-pager'
started: 2026-06-20T12:32:33Z
ended: 2026-06-20T12:32:33Z
returncode: 0

stdout:
```text
NRestarts=0
ExecMainStartTimestamp=Fri 2026-06-19 22:42:33 CDT
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml ; ignore_errors=no ; start_time=[Fri 2026-06-19 22:42:33 CDT] ; stop_time=[n/a] ; pid=3949257 ; code=(null) ; status=0/0 }
WorkingDirectory=/opt/wanctl
```

stderr:
```text
(empty)
```

## Bridge Health Separation

`10.10.110.223:9101` and `10.10.110.227:9101` are bridge/state endpoints, not route-management acceptance. Route-management acceptance is only `127.0.0.1:9102/health` from `cake-shaper`.

### Bridge Health Separation — Spectrum 10.10.110.223:9101

COMMAND: ssh cake-shaper 'curl -fsS http://10.10.110.223:9101/health'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 0

stdout:
```text
{"status":"healthy","version":"cake-autorate-trial","uptime_seconds":null,"consecutive_failures":0,"source":"cake-autorate-state-bridge","wans":[{"name":"spectrum","measurement":{"available":true,"raw_rtt_ms":25.6,"staleness_sec":0.603703498840332},"irtt":{"available":false},"download":{"state":"GREEN","current_rate_mbps":550.0,"qdisc_bandwidth":"550Mbit"},"upload":{"state":"GREEN","current_rate_mbps":18.0,"qdisc_bandwidth":"18Mbit"},"congestion":{"dl_state":"GREEN","ul_state":"GREEN"},"last_applied":{"dl_rate":550000000,"ul_rate":18000000}}]}
```

stderr:
```text
(empty)
```

### Bridge Health Separation — ATT 10.10.110.227:9101

COMMAND: ssh cake-shaper 'curl -fsS http://10.10.110.227:9101/health'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 0

stdout:
```text
{"status":"healthy","version":"cake-autorate-trial","uptime_seconds":null,"consecutive_failures":0,"source":"cake-autorate-state-bridge","wans":[{"name":"att","measurement":{"available":true,"raw_rtt_ms":28.19181289136989,"staleness_sec":0.6236093044281006},"irtt":{"available":false},"download":{"state":"GREEN","current_rate_mbps":95.0,"qdisc_bandwidth":"95Mbit"},"upload":{"state":"GREEN","current_rate_mbps":19.0,"qdisc_bandwidth":"19Mbit"},"congestion":{"dl_state":"GREEN","ul_state":"GREEN"},"last_applied":{"dl_rate":95000000,"ul_rate":19000000}}]}
```

stderr:
```text
(empty)
```

## RouterOS Read-Only Inventory

### RouterOS identity read-only inventory

COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system identity print"'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 255

stdout:
```text
(empty)
```

stderr:
```text
Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory.
admin@10.10.99.1: Permission denied (publickey,password).
```

### RouterOS Netwatch read-only inventory

COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/tool netwatch print detail"'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:57Z
returncode: 255

stdout:
```text
(empty)
```

stderr:
```text
Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory.
admin@10.10.99.1: Permission denied (publickey,password).
```

### RouterOS script read-only inventory

COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system script print detail"'
started: 2026-06-20T12:21:57Z
ended: 2026-06-20T12:21:58Z
returncode: 255

stdout:
```text
(empty)
```

stderr:
```text
Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory.
admin@10.10.99.1: Permission denied (publickey,password).
```

### RouterOS default-route read-only inventory

COMMAND: ssh cake-shaper 'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/ip route print detail"'
started: 2026-06-20T12:21:58Z
ended: 2026-06-20T12:21:58Z
returncode: 255

stdout:
```text
(empty)
```

stderr:
```text
Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory.
admin@10.10.99.1: Permission denied (publickey,password).
```

## No-Mutation Proof

Proof source: only `COMMAND:` lines from the validated command file are scanned for mutation classes.

COMMAND_LINE_COUNT: 10
MUTATION_TOKEN_HITS: []
NO_ROUTEROS_ROUTE_MUTATION: true
NO_NETWATCH_MUTATION: true
NO_CAKE_QDISC_CHANGE: true
NO_ROUTE_OWNER_FLIP: true

## Intended vs Live Route Comparison

| Item | Observed | Classification | Notes |
|------|----------|----------------|-------|
| `route_management.enabled` | `True` | `match` | Route-management surface present on steering acceptance endpoint. |
| `route_management.mode` | `dry_run` | `match` | Dry-run mode; no active route-management canary. |
| `route_management.active_owner` | `netwatch` | `match` | Netwatch remains active/interim route owner. |
| `route_management.active_allowed` | `False` | `expected-safe-block` | Guard blocks active route management. |
| `route_management.blocked_reason` | `ownership guard does not allow active route management` | `expected-safe-block` | Fail-closed route ownership boundary. |
| `guard.status` | `error` | `evidence-gap` | Guard remains error because supported Netwatch ownership inspection is not proven. |
| `guard.active_allowed` | `False` | `expected-safe-block` | Fail-closed active gate. |
| `reconciliation.status` | `ok` | `match` | Configured route-target reconciliation is ok. |
| `reconciliation.route_count` | `3` | `match` | Three configured route targets visible to route manager. |
| `circuit_breaker.open` | `False` | `match` | Circuit breaker closed. |
| `last_intended_action` | `None` | `match` | No intended route action during observation. |
| `last_applied_action` | `None` | `match` | No applied route action during observation. |
| `rollback_ready` | `True` | `match` | Health reports rollback ready; Phase 256 anchors referenced below. |
| `operator_summary.route_owner` | `netwatch` | `match` | Operator summary agrees with route-management active_owner. |
| `operator_summary.route_guard_status` | `error` | `evidence-gap` | Summary surfaces guard error. |
| `operator_summary.route_circuit_open` | `False` | `match` | Summary surfaces closed circuit. |
| `operator_summary.route_mode` | `dry_run` | `match` | Summary surfaces dry_run. |
| `operator_summary.route_active_allowed` | `False` | `expected-safe-block` | Summary surfaces active_allowed=false. |
| `identity read-only inventory` | `returncode=255 Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory. admin@10.10.99.1: Permission denied (publickey,password).` | `evidence-gap` | Read-only RouterOS inventory was not available; no corrective command issued. |
| `Netwatch read-only inventory` | `returncode=255 Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory. admin@10.10.99.1: Permission denied (publickey,password).` | `evidence-gap` | Read-only RouterOS inventory was not available; no corrective command issued. |
| `script read-only inventory` | `returncode=255 Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory. admin@10.10.99.1: Permission denied (publickey,password).` | `evidence-gap` | Read-only RouterOS inventory was not available; no corrective command issued. |
| `default-route read-only inventory` | `returncode=255 Warning: Identity file /etc/wanctl/ssh/router.key not accessible: No such file or directory. admin@10.10.99.1: Permission denied (publickey,password).` | `evidence-gap` | Read-only RouterOS inventory was not available; no corrective command issued. |
| `Spectrum 10.10.110.223:9101` | `status=healthy rc=0` | `match` | Bridge/state endpoint only; not route-management acceptance. |
| `ATT 10.10.110.227:9101` | `status=healthy rc=0` | `match` | Bridge/state endpoint only; not route-management acceptance. |

### Rollback Anchor Reference

- Phase 256 rollback anchors: `/var/lib/wanctl/phase256-backups/20260620T033704Z`
- Evidence file: `/home/kevin/projects/wanctl/.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-rollback-anchors-20260620T033704Z.md`

### Comparison Interpretation

- `guard.status=error` and RouterOS Netwatch/default-route inventory `returncode=255` are treated as evidence gaps, not ignored.
- No comparison row proposes automatic mutation as remediation.
- Because supported ownership inspection and live RouterOS route/Netwatch inventory were not proven, final readiness must be `not-ready`.

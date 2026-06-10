# Phase 231 SOAK-01 Evidence: Migration-Held Criteria + Live Both-WAN Evaluation

**Captured:** 2026-06-10T13:27:06Z  
**Scope:** read-only live evaluation, both WANs (`spectrum`, `att`)  
**Verdict:** SOAK-01 PASS — both WANs passed `bridge_health`, `metrics_ingestion`, `no_sustained_errors`, and `qdisc_envelope` against pre-declared migration-held criteria.

## Safety Boundary

- Live host contact was read-only: `ssh`, `curl`, `journalctl`, `sqlite3 -readonly SELECT`, `tc qdisc show`, and `systemctl is-active` status reads only.
- No `systemctl start/stop/restart/enable/disable`, no `tc qdisc replace/add/del`, and no target-host writes were requested or performed.
- Evidence records only hosts/IPs/units already committed in the repo and Phase 231 plan.
- SOAK-01 live capture completed before any Phase 231 rollback exercise.

## Formal Criteria

Defined before live evaluation for the 2026-06-08 both-WAN cake-autorate migration.

| ID | Check | Threshold / Rule | Evidence Channel |
|----|-------|------------------|------------------|
| C1 | `bridge_health` | PASS iff health endpoint returns HTTP 200 and JSON `status == healthy`. | Read-only `curl --max-time 10 http://<wan-health-ip>:9101/health` over SSH. |
| C2 | `metrics_ingestion` | PASS iff metrics DB row count in trailing 24h window is `> 0`. | Read-only `sudo -n sqlite3 -readonly /var/lib/wanctl/metrics-<wan>.db 'SELECT COUNT(*) ...'`. |
| C3 | `no_sustained_errors` | PASS iff every unit has zero err-priority lines since `2026-06-08 00:00:00 UTC`, OR total lines `<= C3_MAX_TOTAL=5`, distinct UTC hours `<= C3_MAX_DISTINCT_HOURS=2`, and zero err lines in trailing `C3_CLEAN_TRAILING_HOURS=6`. | Read-only `sudo -n journalctl -u <unit> --since '2026-06-08 00:00:00 UTC' -p err --no-pager -o short-iso`. |
| C4 | `qdisc_envelope` | PASS iff DL CAKE bandwidth is within repo-configured `[min_dl_shaper_rate_kbps, max_dl_shaper_rate_kbps]` and UL CAKE bandwidth equals repo-configured `base_ul_shaper_rate_kbps`. | Read-only `sudo -n tc qdisc show dev <iface>`; thresholds parsed from `configs/cake-autorate/config.<wan>.sh`. |

The C3 unit set is a documented superset of `scripts/soak-monitor.sh`'s external-mode scan set: it includes `steering.service` for both WANs and adds `silicom-bypass-watchdog@spectrum.service` for Spectrum, while ATT includes `silicom-bypass-watchdog-cake-autorate-att.service`.

## Step A: Live Migration-Held Evaluator Capture

Command:

```bash
bash scripts/phase231-migration-held.sh --wan all --json | python3 -m json.tool
```

Captured output:

```json
[
    {
        "captured_utc": "2026-06-10T13:27:05Z",
        "checks": {
            "bridge_health": {
                "evidence": {
                    "http_code": "200",
                    "payload": {
                        "consecutive_failures": 0,
                        "source": "cake-autorate-state-bridge",
                        "status": "healthy",
                        "uptime_seconds": null,
                        "version": "cake-autorate-trial",
                        "wans": [
                            {
                                "congestion": {
                                    "dl_state": "GREEN",
                                    "ul_state": "GREEN"
                                },
                                "download": {
                                    "current_rate_mbps": 550.0,
                                    "qdisc_bandwidth": "550Mbit",
                                    "state": "GREEN"
                                },
                                "irtt": {
                                    "available": false
                                },
                                "last_applied": {
                                    "dl_rate": 550000000,
                                    "ul_rate": 18000000
                                },
                                "measurement": {
                                    "available": true,
                                    "raw_rtt_ms": 22.60283333286988,
                                    "staleness_sec": 0.5170977115631104
                                },
                                "name": "spectrum",
                                "upload": {
                                    "current_rate_mbps": 18.0,
                                    "qdisc_bandwidth": "18Mbit",
                                    "state": "GREEN"
                                }
                            }
                        ]
                    }
                },
                "pass": true
            },
            "metrics_ingestion": {
                "evidence": {
                    "db": "/var/lib/wanctl/metrics-spectrum.db",
                    "table": "metrics",
                    "timestamp_column": "timestamp"
                },
                "pass": true,
                "rows": 506628,
                "window_hours": 24
            },
            "no_sustained_errors": {
                "err_lines": 1,
                "pass": true,
                "rule": {
                    "C3_CLEAN_TRAILING_HOURS": 6,
                    "C3_MAX_DISTINCT_HOURS": 2,
                    "C3_MAX_TOTAL": 5,
                    "since": "2026-06-08 00:00:00 UTC"
                },
                "units": [
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "cake-autorate-spectrum.service"
                    },
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "cake-autorate-spectrum-state-bridge.service"
                    },
                    {
                        "distinct_utc_hours": [
                            "2026-06-08T19"
                        ],
                        "err_lines": [
                            "2026-06-08T14:38:49-05:00 cake-shaper systemctl[50231]: Failed to connect to system scope bus via local transport: Connection refused"
                        ],
                        "pass": true,
                        "total": 1,
                        "trailing_err_lines": 0,
                        "unit": "silicom-bypass-watchdog@spectrum.service"
                    },
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "steering.service"
                    }
                ]
            },
            "qdisc_envelope": {
                "dl_kbps": 550000,
                "dl_max": 600000,
                "dl_min": 500000,
                "evidence": {
                    "dl_if": "spec-router",
                    "dl_raw": "qdisc cake 8002: root refcnt 9 bandwidth 550Mbit diffserv4 triple-isolate nonat wash no-ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb ",
                    "ul_if": "spec-modem",
                    "ul_raw": "qdisc cake 8004: root refcnt 9 bandwidth 18Mbit diffserv4 triple-isolate nonat wash ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb "
                },
                "pass": true,
                "ul_expected": 18000,
                "ul_kbps": 18000
            }
        },
        "verdict": "PASS",
        "wan": "spectrum"
    },
    {
        "captured_utc": "2026-06-10T13:27:06Z",
        "checks": {
            "bridge_health": {
                "evidence": {
                    "http_code": "200",
                    "payload": {
                        "consecutive_failures": 0,
                        "source": "cake-autorate-state-bridge",
                        "status": "healthy",
                        "uptime_seconds": null,
                        "version": "cake-autorate-trial",
                        "wans": [
                            {
                                "congestion": {
                                    "dl_state": "GREEN",
                                    "ul_state": "GREEN"
                                },
                                "download": {
                                    "current_rate_mbps": 95.0,
                                    "qdisc_bandwidth": "95Mbit",
                                    "state": "GREEN"
                                },
                                "irtt": {
                                    "available": false
                                },
                                "last_applied": {
                                    "dl_rate": 95000000,
                                    "ul_rate": 19000000
                                },
                                "measurement": {
                                    "available": true,
                                    "raw_rtt_ms": 28.19181289136989,
                                    "staleness_sec": 0.4294443130493164
                                },
                                "name": "att",
                                "upload": {
                                    "current_rate_mbps": 19.0,
                                    "qdisc_bandwidth": "19Mbit",
                                    "state": "GREEN"
                                }
                            }
                        ]
                    }
                },
                "pass": true
            },
            "metrics_ingestion": {
                "evidence": {
                    "db": "/var/lib/wanctl/metrics-att.db",
                    "table": "metrics",
                    "timestamp_column": "timestamp"
                },
                "pass": true,
                "rows": 505584,
                "window_hours": 24
            },
            "no_sustained_errors": {
                "err_lines": 0,
                "pass": true,
                "rule": {
                    "C3_CLEAN_TRAILING_HOURS": 6,
                    "C3_MAX_DISTINCT_HOURS": 2,
                    "C3_MAX_TOTAL": 5,
                    "since": "2026-06-08 00:00:00 UTC"
                },
                "units": [
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "cake-autorate-att.service"
                    },
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "cake-autorate-att-state-bridge.service"
                    },
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "silicom-bypass-watchdog-cake-autorate-att.service"
                    },
                    {
                        "distinct_utc_hours": [],
                        "err_lines": [],
                        "pass": true,
                        "total": 0,
                        "trailing_err_lines": 0,
                        "unit": "steering.service"
                    }
                ]
            },
            "qdisc_envelope": {
                "dl_kbps": 95000,
                "dl_max": 100000,
                "dl_min": 60000,
                "evidence": {
                    "dl_if": "att-router",
                    "dl_raw": "qdisc cake 8001: root refcnt 9 bandwidth 95Mbit diffserv4 triple-isolate nonat nowash ingress no-ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb ",
                    "ul_if": "att-modem",
                    "ul_raw": "qdisc cake 8003: root refcnt 9 bandwidth 19Mbit diffserv4 triple-isolate nonat nowash ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb "
                },
                "pass": true,
                "ul_expected": 19000,
                "ul_kbps": 19000
            }
        },
        "verdict": "PASS",
        "wan": "att"
    }
]
```

Finding:

- `spectrum`: PASS. C3 observed one historical Spectrum watchdog err line on 2026-06-08, but it satisfied the pre-declared objective rule (`total=1`, one UTC hour, zero trailing-6h err lines).
- `att`: PASS. No C3 err lines were observed across the ATT C3 unit set.

## Step B1: Phase 230 Soak Monitor Corroboration

Command:

```bash
./scripts/soak-monitor.sh --json | python3 -m json.tool
```

Captured output:

```json
[
    {
        "wan": "spectrum",
        "health": {
            "status": "healthy",
            "version": "cake-autorate-trial",
            "uptime_seconds": null,
            "consecutive_failures": 0,
            "source": "cake-autorate-state-bridge",
            "wans": [
                {
                    "name": "spectrum",
                    "measurement": {
                        "available": true,
                        "raw_rtt_ms": 22.60283333286988,
                        "staleness_sec": 0.060965776443481445
                    },
                    "irtt": {
                        "available": false
                    },
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 550.0,
                        "qdisc_bandwidth": "550Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 18.0,
                        "qdisc_bandwidth": "18Mbit"
                    },
                    "congestion": {
                        "dl_state": "GREEN",
                        "ul_state": "GREEN"
                    },
                    "last_applied": {
                        "dl_rate": 550000000,
                        "ul_rate": 18000000
                    }
                }
            ]
        },
        "errors_1h": 0
    },
    {
        "wan": "att",
        "health": {
            "status": "healthy",
            "version": "cake-autorate-trial",
            "uptime_seconds": null,
            "consecutive_failures": 0,
            "source": "cake-autorate-state-bridge",
            "wans": [
                {
                    "name": "att",
                    "measurement": {
                        "available": true,
                        "raw_rtt_ms": 28.19181289136989,
                        "staleness_sec": 0.05299544334411621
                    },
                    "irtt": {
                        "available": false
                    },
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 95.0,
                        "qdisc_bandwidth": "95Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 19.0,
                        "qdisc_bandwidth": "19Mbit"
                    },
                    "congestion": {
                        "dl_state": "GREEN",
                        "ul_state": "GREEN"
                    },
                    "last_applied": {
                        "dl_rate": 95000000,
                        "ul_rate": 19000000
                    }
                }
            ]
        },
        "errors_1h": 0
    },
    {
        "service_group": "all-claimed-services",
        "units": [
            "cake-autorate-spectrum.service",
            "cake-autorate-spectrum-state-bridge.service",
            "cake-autorate-att.service",
            "cake-autorate-att-state-bridge.service",
            "silicom-bypass-watchdog-cake-autorate-att.service",
            "steering.service"
        ],
        "errors_1h": 0
    }
]
```

Finding:

- Phase 230 generalized soak monitor corroborates both bridges are healthy and both WANs have zero 1h service errors across its external-mode aggregate unit set.
- SOAK-01 C3 deliberately uses a broader unit set than this aggregate scan by including `silicom-bypass-watchdog@spectrum.service` and scanning since the migration anchor.

## Step B2: Ten-Unit External-Mode Inventory Corroboration

Command:

```bash
ssh -o ConnectTimeout=10 -o BatchMode=yes kevin@10.10.110.223 'systemctl is-active cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service silicom-bypass-watchdog@spectrum.service cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service steering.service wanctl@spectrum.service wanctl@att.service silicom-bypass-watchdog@att.service'
```

Captured output:

```text
ControlSocket /home/kevin/.ssh/controlmasters/kevin10.10.110.223:22 already exists, disabling multiplexing
active
active
active
active
active
active
active
inactive
inactive
inactive
```

Interpretation:

| Unit | Expected | Observed |
|------|----------|----------|
| `cake-autorate-spectrum.service` | active | active |
| `cake-autorate-spectrum-state-bridge.service` | active | active |
| `silicom-bypass-watchdog@spectrum.service` | active | active |
| `cake-autorate-att.service` | active | active |
| `cake-autorate-att-state-bridge.service` | active | active |
| `silicom-bypass-watchdog-cake-autorate-att.service` | active | active |
| `steering.service` | active | active |
| `wanctl@spectrum.service` | inactive | inactive |
| `wanctl@att.service` | inactive | inactive |
| `silicom-bypass-watchdog@att.service` | inactive | inactive |

Finding:

- The live inventory matches the expected external cake-autorate mode: seven active units and three inactive native/rollback units.
- This proves the SOAK-01 criteria were evaluated against live external-mode reality, not stale native `wanctl@{wan}` ownership assumptions.

## One-Line Verdict

SOAK-01 PASS: formal criteria were defined before evaluation, both WANs were evaluated through read-only channels with UTC timestamps and raw evidence, all four checks passed for `spectrum` and `att`, and the live inventory matched seven-active/three-inactive external mode.

# Phase 230 MON-01 Criterion-3 Evidence: ATT Live-Unit Scan Contrast

**Captured:** 2026-06-10T02:25Z  
**Scope:** read-only live observation plus local fake-ssh representative run  
**Verdict:** PASS — post-fix `soak-monitor.sh` targets the live ATT cake-autorate units and surfaces an ATT-unit error condition that the pre-fix `wanctl@att.service`-only scan would have missed.

## Safety Boundary

- Live host contact was read-only: `./scripts/soak-monitor.sh --json` and `systemctl is-active` status reads over SSH.
- No service lifecycle changes were requested or performed on production hosts.
- The representative ATT-unit error was simulated only inside a local fake-ssh shim under `/tmp/opencode/soak-monitor-evidence.Tg4LMG`; no production host was touched by that simulation.
- Evidence records only committed repo host/IP/unit names already present in the project.

## Step A: Post-Fix Live `--json` Capture

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
                        "staleness_sec": 0.3305938243865967
                    },
                    "irtt": {
                        "available": false
                    },
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 521.787,
                        "qdisc_bandwidth": "522Mbit"
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
                        "dl_rate": 521787000,
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
                        "staleness_sec": 0.4487295150756836
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

Live ATT aggregate unit-set finding:

- Contains `cake-autorate-att.service`.
- Contains `cake-autorate-att-state-bridge.service`.
- Contains `silicom-bypass-watchdog-cake-autorate-att.service`.
- Does not contain `wanctl@att.service` in the `all-claimed-services` units list.
- No naturally-present ATT-unit `err` entries were observed in the live 1h window (`att.errors_1h=0`, aggregate `errors_1h=0`). The representative local run below covers the error-condition contrast without touching production.

## Step A2: Mode-Detection Inputs

Command:

```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes kevin@10.10.110.223 'systemctl is-active cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service wanctl@att.service'
```

Captured output:

```text
active
active
active
inactive
```

Interpretation:

| Unit | Status |
|------|--------|
| `cake-autorate-att.service` | `active` |
| `cake-autorate-att-state-bridge.service` | `active` |
| `silicom-bypass-watchdog-cake-autorate-att.service` | `active` |
| `wanctl@att.service` | `inactive` |

This proves the post-fix external-mode branch was selected from live status inputs rather than defaulting to native `wanctl@att.service` scanning.

## Step B: Pre-Fix Contrast from Pinned Ref

Pre-fix source was retrieved with the pinned command:

```bash
git show 4ad2986e:scripts/soak-monitor.sh
```

Relevant pre-fix ATT branch and aggregate scan shape:

```bash
if [[ "$wan_name" == "spectrum" ]] && is_spectrum_cake_trial_active "$ssh_target"; then
    errors=$(check_errors "$ssh_target" "cake-autorate-spectrum.service" "cake-autorate-spectrum-state-bridge.service")
else
    errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
fi
```

```bash
if is_spectrum_cake_trial_active "kevin@10.10.110.223"; then
    service_errors=$(check_errors "kevin@10.10.110.223" "cake-autorate-spectrum.service" "cake-autorate-spectrum-state-bridge.service" "wanctl@att.service" "steering.service")
    service_units_json='["cake-autorate-spectrum.service","cake-autorate-spectrum-state-bridge.service","wanctl@att.service","steering.service"]'
else
    service_errors=$(check_errors "kevin@10.10.110.223" "${SERVICE_UNITS[@]}")
    service_units_json='["wanctl@spectrum.service","wanctl@att.service","steering.service"]'
fi
```

Contrast: at `4ad2986e`, ATT always falls through to `wanctl@att.service` for the per-WAN scan and appears as `wanctl@att.service` in the aggregate scan, even when the live ATT units are `cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, and `silicom-bypass-watchdog-cake-autorate-att.service`.

## Step B2: Local Fake-SSH Representative ATT-Unit Error Demonstration

Setup summary:

- A temporary PATH-first fake `ssh` was created under `/tmp/opencode/soak-monitor-evidence.Tg4LMG/bin/ssh`.
- The shim returned healthy bridge JSON for both WAN health requests.
- The shim made external mode detectable for cake-autorate WANs.
- The shim returned `3` for journal scans whose unit args included any ATT live unit and `0` for scans pointed only at `wanctl@att.service`.
- The pre-fix script was extracted with `git show 4ad2986e:scripts/soak-monitor.sh > /tmp/opencode/soak-monitor-evidence.Tg4LMG/soak-monitor-prefix.sh`.

Post-fix command:

```bash
PATH="/tmp/opencode/soak-monitor-evidence.Tg4LMG/bin:$PATH" bash scripts/soak-monitor.sh --json | python3 -m json.tool
```

Post-fix captured output:

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
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 522.0,
                        "qdisc_bandwidth": "522Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 18.0,
                        "qdisc_bandwidth": "18Mbit"
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
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 95.0,
                        "qdisc_bandwidth": "95Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 19.0,
                        "qdisc_bandwidth": "19Mbit"
                    }
                }
            ]
        },
        "errors_1h": 3
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
        "errors_1h": 3
    }
]
```

Pre-fix command:

```bash
PATH="/tmp/opencode/soak-monitor-evidence.Tg4LMG/bin:$PATH" bash /tmp/opencode/soak-monitor-evidence.Tg4LMG/soak-monitor-prefix.sh --json | python3 -m json.tool
```

Pre-fix captured output:

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
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 522.0,
                        "qdisc_bandwidth": "522Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 18.0,
                        "qdisc_bandwidth": "18Mbit"
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
                    "download": {
                        "state": "GREEN",
                        "current_rate_mbps": 95.0,
                        "qdisc_bandwidth": "95Mbit"
                    },
                    "upload": {
                        "state": "GREEN",
                        "current_rate_mbps": 19.0,
                        "qdisc_bandwidth": "19Mbit"
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
            "wanctl@att.service",
            "steering.service"
        ],
        "errors_1h": 0
    }
]
```

Representative-error finding:

- Post-fix `att.errors_1h=3` and aggregate `errors_1h=3` because the scan included the ATT live units.
- Pre-fix `att.errors_1h=0` and aggregate `errors_1h=0` against the same fake-ssh shim because the scan targeted `wanctl@att.service` instead.

## One-Line Verdict

The post-fix scan targets `cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, and `silicom-bypass-watchdog-cake-autorate-att.service`, so it surfaces ATT-unit error conditions that the pre-fix `wanctl@att.service`-only scan demonstrably missed.

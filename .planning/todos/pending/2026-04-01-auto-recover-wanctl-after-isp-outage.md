---
created: 2026-04-01T10:56:18.178Z
title: Auto-recover wanctl after ISP outage
area: infrastructure
files:
  - /etc/systemd/system/wanctl@.service
  - src/wanctl/autorate_continuous.py
---

## Problem

When the WAN goes down (ISP outage), wanctl accumulates consecutive failures until the systemd
watchdog kills the process (SIGABRT). systemd restarts it, but if the WAN is still down, it fails
again within ~41s. After 5 rapid restart-fail cycles, the circuit breaker trips
(`StartLimitBurst=5` in 5 minutes) and systemd stops auto-restarting.

When the WAN recovers (minutes to hours later), the service stays in `failed` state indefinitely.
Manual intervention required: `systemctl reset-failed wanctl@spectrum && systemctl start wanctl@spectrum`.

Observed 2026-04-01: Spectrum WAN outage at 00:04 CDT, circuit breaker tripped at 00:09.
WAN recovered by ~05:00, but service stayed dead for 5.5h until manual restart at 05:51.

ATT (DSL) was unaffected — ran continuously through the entire incident (18h+ uptime).

## Solution

Add a systemd timer (`wanctl-recovery.timer`) that periodically checks for failed wanctl units.
If a unit is in `failed` state AND WAN connectivity is restored (ping gateway + external host),
reset-failed and restart the unit.

Approach options:
- **systemd timer + shell script**: `wanctl-recovery.timer` runs every 5 minutes, checks
  `systemctl is-failed wanctl@*`, pings gateway, then `reset-failed && start`
- **systemd `RestartSec` + higher limits**: Increase `StartLimitBurst` and `StartLimitIntervalSec`
  to allow more retries with longer backoff — but this doesn't solve the root cause
- **In-process recovery**: Have the daemon itself survive WAN outages without crashing —
  freeze rates, keep watchdog alive, wait for connectivity. Most robust but biggest code change.

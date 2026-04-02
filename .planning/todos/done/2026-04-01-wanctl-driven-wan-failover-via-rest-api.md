---
created: 2026-04-01T20:40:00.000Z
title: wanctl-driven WAN failover via REST API
area: control-loop
files:
  - src/wanctl/autorate_continuous.py
  - src/wanctl/steering/daemon.py
---

## Problem

MikroTik NetWatch failover has architectural limitations:
- Pings a single external host per WAN — if that host is down (Cloudflare/Google outage), route gets disabled incorrectly
- No integration with wanctl's rich WAN health data (ICMP, TCP fallback, IRTT, signal processing)
- Binary up/down — no nuance for degradation vs outage
- Steering daemon never activates because CAKE rate clamping resolves congestion before confidence threshold is reached

wanctl already has the most accurate WAN health picture — it should drive failover directly.

## Solution

Replace NetWatch-based failover with wanctl-driven route management:

1. When wanctl detects complete WAN failure (all pings fail + TCP fallback fails + gateway reachable):
   - Disable the WAN's default route via MikroTik REST API
   - Log the failover event + Discord alert
   - ATT traffic takes over automatically (distance=2 route becomes active)

2. When WAN recovers (pings succeed again):
   - Re-enable the route via REST API
   - Log recovery + Discord alert

3. Cross-WAN awareness: ATT instance could monitor Spectrum route health
   (ATT stays alive during Spectrum outages since it's a separate service)

Key design decisions needed:
- Should autorate controller manage routes directly, or should steering daemon own this?
- How many consecutive failures before disabling route? (match NetWatch behavior: ~3 at 10s = 30s)
- Should the ATT instance be able to manage Spectrum's route? (cross-WAN coupling)
- How to handle the circuit breaker interaction? (if wanctl crashes, routes stay in last state)

This is a future milestone — NetWatch fix (external host ping) is the interim solution deployed 2026-04-01.

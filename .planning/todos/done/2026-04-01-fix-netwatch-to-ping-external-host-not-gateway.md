---
created: 2026-04-01T11:15:00.000Z
title: Fix NetWatch to ping external host not gateway for WAN failover
area: network
files:
  - router/configs/router_config.rsc:5573-5586
---

## Problem

MikroTik NetWatch Monitor-Spectrum pings the ISP gateway (70.123.224.1) to detect WAN failure.
During the 2026-04-01 midnight Spectrum outage, the gateway remained reachable (local CMTS/modem
responds to pings) even though upstream internet was completely dead. NetWatch never triggered
failover because its health check passed.

Evidence from wanctl logs: `"External pings failed but gateway 10.10.110.1 reachable"` — the
local gateway was up, but 1.1.1.1, 208.67.222.222, 9.9.9.9 all failed. Same pattern applies
to the ISP gateway (70.123.224.1) — reachable locally, dead upstream.

Result: All traffic continued routing through dead Spectrum path. DNS broke. Internet unreachable
from most machines. VPN via ATT worked only because WireGuard traffic uses explicit FORCE_OUT_ATT
mangle rules that bypass the default route.

ATT failover route (distance=2) never activated because the Spectrum route (distance=1) was
never disabled by NetWatch.

## Solution

Change NetWatch Monitor-Spectrum to ping an **external host** (e.g., 1.1.1.1) instead of the
ISP gateway. Use MikroTik's `src-address` to force the ping out the Spectrum interface so it
actually traverses the ISP's upstream path.

Current (router_config.rsc lines 5573-5575):
```
/tool netwatch
  add host=70.123.224.1 interval=2s ...
```

Proposed:
```
/tool netwatch
  add host=1.1.1.1 interval=10s src-address=<spectrum-wan-ip> ...
```

Considerations:
- Use a reliable external target (1.1.1.1 Cloudflare, 8.8.8.8 Google) — not ISP gateway
- Increase interval from 2s to 10s to avoid rate limiting on public IPs
- Set appropriate timeout and threshold (e.g., 3 failures before triggering disable)
- Apply same fix to Monitor-ATT (ping external host, not 99.126.112.1)
- Test carefully — false positive failover is worse than no failover
- MUST be done while physically at home to recover if misconfigured

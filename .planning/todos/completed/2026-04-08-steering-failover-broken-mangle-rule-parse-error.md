---
created: 2026-04-08T01:19:00.000Z
title: Steering failover broken - mangle rule parse error
area: steering
files:
  - src/wanctl/steering/
---

## Problem

Steering failover is silently broken. During tcp_12down testing (2026-04-07 19:49 CDT), the steering daemon correctly detected SPECTRUM_DEGRADED (confidence=70, drops=2176/s, queue=5612%) but **failed to enable the failover rule on the MikroTik router**.

Error log (repeated 822 times in 30 minutes):
```
[ERROR] Could not parse rule comment from: /ip firewall mangle enable [find comment~"ADAPTIVE: Steer latency-sensitive to ATT"]
[ERROR] Failed to enable steering rule
[ERROR] Failed to enable steering, staying in SPECTRUM_GOOD
```

The steering daemon is sending SSH CLI syntax (`/ip firewall mangle enable [find comment~"..."]`) but the router connection may be using REST API, or the mangle rule with that exact comment doesn't exist on the router.

This means **steering has never successfully failed over** since the cake-shaper VM migration (v1.21). The detection logic works, the confidence scoring works, but the actual router command to enable the mangle rule is broken.

## Impact

HIGH — During severe congestion events, latency-sensitive traffic (VoIP, gaming) stays on the congested Spectrum WAN instead of being steered to ATT. This defeats the entire purpose of dual-WAN steering.

## Resolution — FIXED 2026-04-07

Three stacked bugs found and fixed:

1. **`routeros_rest.py:299`** — `_parse_find_comment` regex only matched `comment=`, not `comment~` (tilde = regex match in RouterOS CLI). Fixed: `comment[~=]`.
2. **`routeros_rest.py:585`** — `find_mangle_rule_id` used REST query params `?comment=value` which MikroTik silently ignores for comments with special chars. Fixed: fetch all rules, filter client-side.
3. **`steering/daemon.py:781`** — `get_rule_status` parsed SSH CLI text output (`;;;` delimiters, `X` flags) but got JSON from REST. Fixed: REST-aware path using `find_mangle_rule_id` + direct rule GET.

Mangle rule `*313` exists on router (was always there, just couldn't be found via REST).

**E2E verified:** DEGRADED detected → rule enabled → verified → 28s steering → RECOVERED → rule disabled → verified.

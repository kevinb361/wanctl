---
created: 2026-04-08T23:35:04.832Z
title: Profile ATT cycle overrun sources
area: performance
files:
  - /etc/wanctl/att.yaml
  - /etc/wanctl/spectrum.yaml
---

## Problem

ATT accumulated 9,120+ cycle overruns. Most are 50-56ms (barely over 50ms target), some spikes to 105-253ms. Same pattern on Spectrum (54 overruns in first hour after restart).

## Root Cause (investigated 2026-04-10)

**router_communication subsystem is the bottleneck:**

| Subsystem | avg (ms) | p95 (ms) | p99 (ms) |
|-----------|----------|----------|----------|
| rtt_measurement | 0.0 | 0.0 | 0.1 |
| signal_processing | 0.2 | 0.3 | 0.9 |
| logging_metrics | 0.3 | 0.7 | 1.2 |
| **router_communication** | **1.1** | **13.5** | **16.6** |

Both WANs use `transport: "linux-cake"` which calls `subprocess.run(["tc", ...])` — forking a process every cycle. p99=16ms is Linux process scheduling jitter on the fork.

IRTT is NOT the problem (0.1ms avg — already offloaded to background thread). Original hypothesis was wrong.

## Solution

Switch both WANs from `linux-cake` to `linux-cake-netlink` in YAML config. The netlink backend (pyroute2, built in v1.23) uses kernel netlink sockets directly — no process fork. Should drop p99 from 16ms to sub-1ms.

Config change only:
```yaml
transport: "linux-cake-netlink"  # was "linux-cake"
```

**Do NOT change during v1.33 soak.** Schedule for post-milestone.

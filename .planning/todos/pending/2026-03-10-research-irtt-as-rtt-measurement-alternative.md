---
created: 2026-03-10T12:41:43.761Z
title: Research IRTT as RTT measurement alternative
area: general
files:
  - src/wanctl/rtt_measurement.py
  - src/wanctl/autorate_continuous.py
  - src/wanctl/steering/daemon.py
---

## Problem

wanctl currently uses icmplib for ICMP-based RTT measurement in both autorate and steering daemons. ICMP pings have known limitations:
- Some ISPs throttle or block ICMP (Spectrum ICMP blackout was a v1.1 issue)
- ICMP may be deprioritized by routers, giving inaccurate latency readings under load
- No ability to measure jitter, packet loss patterns, or OWD (one-way delay) in a structured way

IRTT (Isochronous Round-Trip Tester) is already running on the Dallas iperf/netperf server. It provides:
- UDP-based isochronous round-trip time measurement
- Separate upstream/downstream OWD measurement
- Jitter and packet loss statistics
- Configurable packet intervals and durations
- JSON output for easy parsing

This could provide more accurate and richer latency data than ICMP pings, especially for congestion detection.

## Solution

TBD — Research phase needed:

1. Evaluate IRTT protocol and client requirements (does it need a client binary on the wanctl containers?)
2. Compare IRTT RTT accuracy vs icmplib ICMP pings under load
3. Assess overhead — IRTT sends UDP packets at configurable intervals; need to ensure it fits within the 50ms cycle budget
4. Determine if OWD data could improve asymmetric congestion detection (upload vs download)
5. Consider as supplement to icmplib (fallback chain: IRTT → icmplib → TCP RTT) vs replacement
6. Test against the Dallas server that's already running IRTT

---
created: 2026-03-20T16:30:00.000Z
title: Auto-disable fusion when protocol correlation drops below threshold
area: control-loop
files:
  - src/wanctl/autorate_continuous.py
---

## Problem

Fusion (weighted ICMP+IRTT average) works well when both measurement paths are similar (Spectrum: ICMP 23ms, IRTT 23ms, correlation ~1.08) but backfires when paths diverge (ATT: ICMP 28ms to CDN, IRTT 44ms to Dallas, correlation 0.74). The divergence creates a permanent delta offset that locks the controller in YELLOW at floor bandwidth — ATT lost 70 Mbps DL and 12 Mbps UL capacity until fusion was manually disabled.

The protocol_correlation metric already captures this divergence (ratio of ICMP/IRTT RTT). A correlation far from 1.0 indicates the measurements are traversing different network paths and should not be fused.

## Solution

Add a correlation threshold check to `_compute_fused_rtt()`. When `protocol_correlation` drops below a configurable threshold (e.g., 0.85), automatically fall back to ICMP-only for load_rtt — effectively auto-disabling fusion without requiring manual config changes.

Could also integrate with ADVT-01 (tune_fusion_weight) — when correlation is low, the strategy should drive `fusion_icmp_weight` toward 1.0 (pure ICMP) rather than optimizing the blend ratio.

## Evidence

- ATT with fusion enabled: YELLOW @ 25/6 Mbps (floor), delta 4.8ms permanent
- ATT with fusion disabled: GREEN @ 95/18 Mbps (ceiling), delta 0.1ms
- Protocol correlation: ATT 0.74 (divergent), Spectrum 1.08 (similar)

---
created: 2026-04-08T23:35:04.832Z
title: Evaluate download DSCP tin classification
area: controller
files:
  - /etc/wanctl/spectrum.yaml
---

## Problem

Spectrum DL CAKE (ens17) shows Video tin at 1,370 packets (0.0%) vs Bulk at 144M (80%). Upload has healthy 3.9M in Video. This is expected — inbound internet traffic arrives without DSCP marks (ISPs strip them) — but means download QoS tin prioritization is effectively unused. Voice tin at 18.4M (10%) is likely DNS responses classified as EF.

## Solution

- Informational / low priority — CAKE per-flow fairness within Bulk tin already prevents starvation
- If download QoS ever matters (e.g., prioritizing video calls during congestion), would need application-aware classification (DPI, conntrack-based marking) rather than pure DSCP
- Document current tin distribution as baseline for future comparison
- The v1.28 bridge nftables DSCP rules only affect locally-originated marks, not ISP-stripped inbound

## Resolution — 2026-04-14

Completed in commit `e6a8583`.

What shipped:
- checked-in `deploy/nftables/bridge-qos.nft` was synced to the live production
  bridge classifier
- `docs/BRIDGE_QOS.md` now documents the active baseline and operator checks
- live RRUL validation confirmed download traffic classification is materially
  used on the current Linux bridge path

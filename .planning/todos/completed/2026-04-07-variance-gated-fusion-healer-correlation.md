---
created: 2026-04-07T05:34:23.835Z
title: Variance-gated fusion healer correlation
area: signal-processing
files:
  - src/wanctl/fusion_healer.py:139-167
  - src/wanctl/wan_controller.py:1839-1851
---

## Problem

The fusion healer uses Pearson correlation of ICMP vs IRTT RTT *deltas* to decide
whether protocols agree. On idle links (the majority of production time), both protocols
see near-constant RTTs with small jitter. The deltas become noise-dominated and
uncorrelated, driving Pearson r toward zero — even when the protocols agree perfectly on
absolute values (protocol_correlation 1.01-1.22).

The healer interprets r < 0.3 for 60s as "protocols disagree" and suspends fusion.
In practice this means fusion is never active in production — it enables on restart,
then suspends within 10 minutes once the idle-link correlation drops.

Recovery requires sustained r >= 0.5 for 300s, which rarely happens without active load.

## Solution

Variance-gated evaluation: only compute Pearson correlation when RTT deltas exceed a
jitter threshold (e.g., delta variance > 1ms^2). During idle periods, skip evaluation
and keep the current fusion state unchanged. This prevents noise-driven suspension
while preserving the safety mechanism during actual congestion events.

Alternative: evaluate correlation only during YELLOW+ congestion windows, when both
protocols have meaningful deltas to compare.

Low priority — current signal chain (Hampel + EWMA) handles outliers well without
fusion. Best fit for a measurement quality milestone (v1.30+).

## Resolution — 2026-04-14

Completed in commit `ec4477b`.

What shipped:
- fusion healer now skips Pearson evaluation when either ICMP or IRTT delta
  variance is below the configured minimum
- `fusion.healing.min_signal_variance` is now a real config field, default `0.1`
- production validated that fusion stays active on idle links instead of
  suspending on noise-dominated delta windows

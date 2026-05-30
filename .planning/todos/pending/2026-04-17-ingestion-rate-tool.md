---
created: 2026-04-18T02:11:13.000Z
title: Add tool for computing actual metrics.db write rates
area: tooling
resolves_phase: 219
files:
  - scripts/compare_ab.py
  - src/wanctl/storage/reader.py
---

## Problem

During the 2026-04-17 ingestion audit I initially misestimated steering write rate at 2,670 rows/sec based on `(rows deleted between startup and first periodic maintenance) / (time elapsed)`. That counted one-time catch-up deletes from retention tightening, not steady-state writes. The actual rate was ~46 rows/sec.

The mistake was easy to make and cost time to recognize. A small tool that reports true steady-state rate from a recent-samples window would prevent the same error.

## Solution

Add `scripts/metrics-rate.sh` or a subcommand on `wanctl-history`:

```bash
wanctl-history --db /var/lib/wanctl/metrics.db --rates --window 60
```

Output per metric:
- rows in last N seconds
- rows/sec
- rows/day extrapolated
- percent of total write volume

Formula: `COUNT(*) WHERE timestamp > strftime('%s','now') - N / N`. Group by metric_name. Report top 20 by volume.

Small enough to be one function in `storage/reader.py` plus a CLI flag. Also worth including a "tail rate" window (e.g. last 10 min) to smooth out transient spikes.

Motivating use case beyond this session's mistake: any future fire-on-change or sparse-sampling optimization should be validated by measuring the rate change before vs after.

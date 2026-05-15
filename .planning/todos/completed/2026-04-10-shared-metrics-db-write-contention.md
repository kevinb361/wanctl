---
created: 2026-04-10T06:15:00Z
title: Investigate shared metrics.db write contention (3 writers)
area: performance
files:
  - src/wanctl/storage/writer.py
---

## Problem

Three processes (spectrum, att, steering) write to the same 400MB SQLite database via WAL mode. SQLite WAL allows only one writer at a time — others block on the WAL write lock. At 20Hz x 2 WANs + steering, that's ~40+ write transactions/second contending on one lock. Deferred I/O worker batches help, but the contention ceiling is real.

Zombie files `att_metrics.db` and `spectrum_metrics.db` (both 0 bytes, root-owned) suggest per-WAN DBs was the original design.

## Solution

- Monitor WAL lock contention under load (look at logging_metrics p99 spikes)
- Consider per-WAN databases (each process owns its own DB) if contention grows
- Clean up zombie 0-byte DB files

## Resolution — FIXED 2026-04-14

The original premise of this todo is no longer true in production.

Live verification on `cake-shaper` showed:
- `wanctl@spectrum.service` has `/var/lib/wanctl/metrics-spectrum.db` open
- `wanctl@att.service` has `/var/lib/wanctl/metrics-att.db` open
- `steering.service` has `/var/lib/wanctl/metrics.db` open

So there are no longer three processes contending on one SQLite WAL. Each autorate daemon owns its own per-WAN database, and steering is the only live writer to the legacy shared `metrics.db`.

Additional live evidence:
- Spectrum storage health: `lock_failure_total=0`, status `ok`
- ATT storage health: `lock_failure_total=0`, status `ok`
- Steering storage health: `lock_failure_total=0`, status `ok`
- Steering `/health` showed `pending_writes=0`, `checkpoint.busy=0`

This means the original multi-writer lock-contention risk has already been engineered out. What remains is not a write-contention incident; it is simply legacy steering ownership of `metrics.db`, which is acceptable with a single writer.

If future work revisits storage layout, it should be framed as legacy DB cleanup or history-surface simplification, not as an active 3-writer contention problem.

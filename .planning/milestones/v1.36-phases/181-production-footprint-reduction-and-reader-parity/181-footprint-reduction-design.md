# Phase 181 Footprint Reduction Design

**Date:** 2026-04-14  
**Requirement:** `STOR-06`

## Problem

Phase 178 tightened shipped retention, but Phase 179 proved that production per-WAN DB files remained effectively unchanged against the fixed `2026-04-13` baseline.

The milestone still needed a reduction path that:

- actually changes live DB file size in operator terms
- stays inside storage/maintenance scope
- does not modify congestion thresholds, control timing, or decision logic

## What Failed

The first Phase 181 attempt was to shorten the shipped `aggregate_5m_age_seconds` window in the active WAN configs.

That approach was rejected in execution because it turned the reduction work into startup-time maintenance pressure. On production restart, the WAN services repeatedly hit the systemd watchdog before the daemons finished their startup path. Even though the setting was storage-only, applying it during normal daemon startup was not operationally safe enough.

## Chosen Reduction Path

Phase 181 uses an **explicit offline prune+vacuum path** instead of a runtime retention-profile change.

Implemented operator mechanism:

- [`scripts/compact-metrics-dbs.sh`](/home/kevin/projects/wanctl/scripts/compact-metrics-dbs.sh)

Current behavior:

1. stop one WAN daemon
2. delete `5m` and `1h` aggregate rows older than `24h`
3. run `PRAGMA wal_checkpoint(TRUNCATE); VACUUM;`
4. restart the WAN daemon

This targets the part of the retained history that is not required for the active 24h tuning window while forcing the SQLite file body to reflect the smaller retained set.

## Why This Is Safer

- It is explicit and operator-driven rather than hidden inside a normal restart.
- It keeps the normal runtime retention profile unchanged.
- It confines risk to a controlled maintenance window per WAN.
- It leaves controller behavior, thresholds, and queue decisions untouched.

## Production Boundary

This design intentionally does **not** claim that normal startup maintenance should perform large compaction work.

The live attempt showed that pushing heavier retention cleanup into daemon startup can collide with the watchdog budget. The explicit offline path is therefore the safer production mechanism for this milestone.

## Verification Path

Use after each WAN compaction:

```bash
./scripts/compact-metrics-dbs.sh --ssh kevin@10.10.110.223 --wan spectrum
./scripts/compact-metrics-dbs.sh --ssh kevin@10.10.110.223 --wan att
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json
./scripts/soak-monitor.sh --json
```

Final success still depends on the post-change live file sizes being materially below the fixed `2026-04-13` baseline.

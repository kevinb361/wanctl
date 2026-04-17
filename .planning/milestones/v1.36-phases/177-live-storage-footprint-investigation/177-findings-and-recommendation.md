# Phase 177 Findings And Recommendation

## Measured Facts

1. The active autorate DBs are explicitly configured per WAN and are large:
   - `metrics-spectrum.db` ≈ `5.44 GB`
   - `metrics-att.db` ≈ `5.08 GB`

2. A legacy shared `metrics.db` is still active, not inert:
   - size ≈ `751 MB`
   - fresh DB/WAL mtimes on `2026-04-13`
   - fresh raw metrics through `2026-04-13T22:39:18Z`

3. The active per-WAN DBs are not large because of WAL runaway:
   - WAL files are only about `4.2 MB`

4. The active per-WAN DBs are not large mainly because of free-page slack:
   - free-page rates are only about `0.9%` to `1.0%`

5. Downsampling is active in the per-WAN DBs:
   - oldest retained rows are already `5m`
   - newest rows are `raw`
   - observed retained window is about `31.16` hours

6. The legacy shared DB still stores fresh raw metrics, which strongly suggests an active shared-writer path remains in production.

## Interpretation

The current storage issue is not a broken checkpoint loop and not an unvacuumed database full of reclaimable slack. The footprint is mostly real retained content in the active DB bodies.

The most important ambiguity is now narrowed substantially:

- autorate appears to use the explicit per-WAN DBs
- steering likely still uses the legacy default `/var/lib/wanctl/metrics.db`

That means Phase 178 should not start by tuning retention blindly. It should first close the mixed DB-topology ambiguity, because:

- leaving steering on the legacy shared DB keeps the storage layout harder to reason about
- deleting or archiving `metrics.db` without closing that path would be unsafe
- pure retention tightening alone would reduce the per-WAN DBs but leave the active legacy DB path unresolved

## Recommendation

**Primary Phase 178 action path:** a deliberate combination, in this order:

1. **Close legacy DB-path ambiguity first**
   - prove and document whether steering is using the default shared `metrics.db`
   - if confirmed, move steering onto an explicit intended path or intentionally document/keep the shared path
   - remove stale zero-byte `spectrum_metrics.db` / `att_metrics.db` artifacts

2. **Then tighten retention/footprint on the active DBs**
   - use the now-clean runtime topology to reduce active retained size
   - keep the change conservative and observable
   - verify that health, canary, soak-monitor, operator-summary, and history queries still work

3. **Only consider schema/index/write-volume reduction if topology closure plus retention tightening is insufficient**
   - Phase 177 evidence does not yet prove that the indexes or metric mix are the dominant problem
   - it does prove the main footprint is live retained content

So Phase 178 should be framed as:

- legacy/shared DB runtime closure
- safe storage-footprint reduction on the authoritative active DBs

not as a broad storage redesign.

## Operator Re-check

Use these commands to re-check the storage footprint safely:

### Active file inventory

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
```

### Runtime storage status

```bash
./scripts/soak-monitor.sh --json
```

### Retained-window shape

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
```


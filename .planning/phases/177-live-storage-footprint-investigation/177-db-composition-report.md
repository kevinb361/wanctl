# Phase 177 DB Composition Report

**Captured:** 2026-04-13
**Scope:** Active per-WAN DB composition, retained-window shape, and storage-footprint interpretation

## Active DB Schema

All three live DBs expose the same table set:

- `alerts`
- `benchmarks`
- `metrics`
- `reflector_events`
- `tuning_params`

That means the storage question is not caused by one per-WAN DB having an obviously different schema. The footprint difference is about data volume, not table-set drift.

## Retained-Window Evidence

### Active per-WAN DBs

For both `metrics-spectrum.db` and `metrics-att.db`:

- oldest retained metric row:
  - timestamp `1776007800`
  - `2026-04-12T15:30:00Z`
  - granularity `5m`
  - sample metric `wanctl_cake_total_drop_rate`
- newest retained metric row:
  - timestamp `1776119958`
  - `2026-04-13T22:39:18Z`
  - granularity `raw`
  - sample metric `wanctl_cake_peak_delay_us`

Observed retained window:

- approximately `31.16` hours from oldest to newest sampled metric

### Legacy shared DB

For `metrics.db`:

- oldest retained metric row:
  - timestamp `1776018216`
  - `2026-04-12T18:23:36Z`
  - granularity `raw`
  - sample metric `wanctl_config_snapshot`
- newest retained metric row:
  - timestamp `1776119958`
  - `2026-04-13T22:39:18Z`
  - granularity `raw`
  - sample metric `wanctl_cake_tin_backlog_bytes`

Observed retained window:

- approximately `28.26` hours

### Interpretation of retained shape

This production evidence shows:

- downsampling is active in the per-WAN DBs
  - the oldest retained rows are already `5m`
- the active DBs still keep fresh `raw` rows at the front of the window
- the legacy `metrics.db` is not merely archival history; it still holds fresh raw metrics

So the current problem is not "retention never runs." It is that the retained live corpus is still large even with downsampling active.

## DB vs WAL vs Free-Page Evidence

### File-size comparison

| DB | DB bytes | WAL bytes | SHM bytes | Interpretation |
|----|----------|-----------|-----------|----------------|
| Spectrum | `5,441,712,128` | `4,268,352` | `1,572,864` | WAL is tiny relative to DB body |
| ATT | `5,082,914,816` | `4,243,632` | `1,343,488` | WAL is tiny relative to DB body |
| Legacy | `750,997,504` | `4,523,792` | not sampled here | WAL is tiny relative to DB body |

### Page and free-list evidence

| DB | page_count | freelist_count | page_size | free bytes | free-page % |
|----|------------|----------------|-----------|------------|-------------|
| Spectrum | `1,328,543` | `12,032` | `4096` | `49,283,072` | `0.91%` |
| ATT | `1,240,946` | `12,455` | `4096` | `51,015,680` | `1.00%` |
| Legacy | `183,370` | `0` | `4096` | `0` | `0.00%` |

## Footprint Conclusion

The multi-GB active footprint is mostly live DB content.

It is **not** primarily:

- WAL growth
  - WAL files are only about `4.2 MB` to `4.5 MB`
- reclaimable free-page slack
  - free-page percentages are only about `0.9%` to `1.0%`

So the storage question for Phase 178 is mainly about:

- how much data is being retained in the active stores
- whether too many metrics/indexes are being kept at the current retention levels
- whether the steering/shared legacy DB path should be retired, split, or tightened

## Evidence Commands

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 /var/lib/wanctl/metrics-spectrum.db ".tables" && echo --- && sudo -n sqlite3 /var/lib/wanctl/metrics-att.db ".tables" && echo --- && sudo -n sqlite3 /var/lib/wanctl/metrics.db ".tables"'
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;" && echo --- && sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;" && echo --- && sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "PRAGMA page_count; PRAGMA freelist_count; PRAGMA page_size;" && echo --- && sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "PRAGMA page_count; PRAGMA freelist_count; PRAGMA page_size;" && echo --- && sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "PRAGMA page_count; PRAGMA freelist_count; PRAGMA page_size;"'
```


# Phase 178 Operator Verification Path

## Authoritative Active DB Set

Phase 178 leaves three active metrics databases in service:

- `/var/lib/wanctl/metrics-spectrum.db`
  - authoritative autorate metrics DB for Spectrum
- `/var/lib/wanctl/metrics-att.db`
  - authoritative autorate metrics DB for ATT
- `/var/lib/wanctl/metrics.db`
  - shared steering metrics DB kept intentionally per the topology decision record

The stale zero-byte files below are not part of the active DB set:

- `/var/lib/wanctl/spectrum_metrics.db`
- `/var/lib/wanctl/att_metrics.db`

## Authoritative History Read Path

Operator-facing history reads now follow the same discovery rule in both `wanctl-history`
and the `/metrics/history` HTTP endpoint:

1. look for per-WAN DBs matching `/var/lib/wanctl/metrics-*.db`
2. if those files exist, query only that per-WAN set
3. fall back to `/var/lib/wanctl/metrics.db` only when no per-WAN DBs exist

This keeps autorate history reads aligned with the Phase 178 topology and avoids silently
mixing the shared steering DB into autorate history queries when per-WAN DBs are present.

## Production-Safe Verification Commands

### 1. Confirm the active file inventory

```bash
ssh -o BatchMode=yes <host> 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
```

Expected:

- `metrics-spectrum.db`, `metrics-att.db`, and `metrics.db` exist when autorate plus steering are active
- `spectrum_metrics.db` and `att_metrics.db` may exist as zero-byte leftovers, but they are not authoritative

### 2. Check storage status safely

```bash
./scripts/soak-monitor.sh --json
```

Expected:

- each autorate WAN reports `storage.status: ok` or another explicit status in the JSON summary
- the script remains read-only and does not mutate retention or maintenance state

### 3. Query retained history through the supported reader

```bash
ssh -o BatchMode=yes <host> 'wanctl-history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
```

Expected:

- returned rows show `wan_name` values from the per-WAN DB set
- history remains available after the raw-retention tightening because 1-minute and 5-minute aggregates are still retained

### 4. Query the HTTP history endpoint through the same read path

```bash
ssh -o BatchMode=yes <host> 'curl -s http://127.0.0.1:9101/metrics/history?range=1h&limit=5 | python3 -m json.tool'
```

Expected:

- the response shape remains `{data, metadata}`
- `metadata.total_count`, `metadata.returned_count`, `metadata.limit`, and `metadata.offset` remain present
- rows reflect the authoritative per-WAN history set when `metrics-spectrum.db` and `metrics-att.db` exist

### 5. Spot-check retained-window shape directly, read-only

```bash
ssh -o BatchMode=yes <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
```

Expected:

- per-WAN DBs show the retained autorate window
- the shared `metrics.db` still reflects steering activity and is verified separately from autorate history reads

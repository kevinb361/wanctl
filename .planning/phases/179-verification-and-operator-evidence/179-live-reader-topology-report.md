# Phase 179 Live Reader Topology Report

**Captured:** 2026-04-13T23:40:00Z
**Host:** `kevin@10.10.110.223`
**Scope:** read-only production proof of live history-reader behavior, DB topology, and retained-window shape after Phase 178

## Objective

Verify on the deployed host which history-reader paths operators can actually use today, and whether those live readers match the intended per-WAN DB discovery contract.

## Evidence Summary

- The documented `wanctl-history` wrapper is not present on the host as a shell command.
- The underlying history reader does work when invoked through the deployed module path with read-only privilege:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
```

- That CLI path returns both `att` and `spectrum` rows from the active per-WAN DB set.
- The live `/metrics/history` HTTP endpoint is bound to the WAN IPs (`10.10.110.223:9101` and `10.10.110.227:9101`), not `127.0.0.1:9101`.
- The live `/metrics/history` endpoint preserves the documented `{data, metadata}` envelope, but its current deployed behavior does not match the intended merged per-WAN topology:
  - unfiltered 1h `wanctl_rtt_ms` queries returned only `spectrum`
  - `wan=att` returned zero rows on both live autorate endpoints

## Live CLI Reader Evidence

### Command

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
```

### Result summary

- total rows: `141509`
- WANs present: `att`, `spectrum`
- row split:
  - `att`: `70761`
  - `spectrum`: `70748`

### Interpretation

- The underlying CLI reader can see both active per-WAN DBs on the deployed host.
- This is consistent with the repo-side discovery contract in `discover_wan_dbs()` and with Phase 178's intended topology.
- The production-safe invocation is currently the module form above, not the documented bare `wanctl-history` wrapper.

## Live HTTP Reader Evidence

### Commands

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.223:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms&limit=20"'
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.223:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms&wan=spectrum&limit=5"'
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.223:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms&wan=att&limit=5"'
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.227:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms&limit=20"'
```

### Result summary

- Response envelope remains compatible:
  - top-level `data`
  - top-level `metadata`
  - `metadata.total_count`
  - `metadata.returned_count`
  - `metadata.limit`
  - `metadata.offset`
  - `metadata.query`
- Both live autorate endpoints returned only `spectrum` rows for the unfiltered 1h `wanctl_rtt_ms` query.
- Explicit `wan=spectrum` returned rows as expected.
- Explicit `wan=att` returned zero rows on both live autorate endpoints.

### Interpretation

- The live HTTP endpoint is functioning and preserves the documented response shape.
- It is not currently proving merged multi-WAN history on the deployed host.
- Because the CLI reader and the HTTP reader disagree in production, operators should treat the CLI plus direct DB inventory as the authoritative cross-WAN proof path for now.

## Direct DB Spot Checks

### File inventory

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics.db /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
```

Observed:

- `/var/lib/wanctl/metrics-spectrum.db` active, non-zero
- `/var/lib/wanctl/metrics-att.db` active, non-zero
- `/var/lib/wanctl/metrics.db` active, non-zero
- `/var/lib/wanctl/spectrum_metrics.db` zero bytes
- `/var/lib/wanctl/att_metrics.db` zero bytes

### Oldest/newest retained rows

Read-only SQLite spot checks returned:

- `metrics-spectrum.db`
  - oldest: `1776007800`, `5m`, `wanctl_cake_total_drop_rate`
  - newest: `1776123370`, `raw`, `wanctl_cake_peak_delay_us`
- `metrics-att.db`
  - oldest: `1776007800`, `5m`, `wanctl_cake_total_drop_rate`
  - newest: `1776123370`, `raw`, `wanctl_cake_peak_delay_us`
- `metrics.db`
  - oldest: `1776018216`, `raw`, `wanctl_config_snapshot`
  - newest: `1776123370`, `raw`, `wanctl_cake_tin_backlog_bytes`

### Shared steering DB activity

Recent `metrics.db` read-only aggregation showed top 1h metrics dominated by steering-related shared metrics, including:

- `wanctl_wan_zone`
- `wanctl_wan_weight`
- `wanctl_wan_staleness_sec`
- `wanctl_steering_enabled`

### Interpretation

- The active file layout still matches the Phase 178 topology decision:
  - per-WAN autorate DBs at `metrics-spectrum.db` and `metrics-att.db`
  - separate shared steering DB at `metrics.db`
  - stale zero-byte leftovers under the older `*_metrics.db` names
- The oldest retained rows in the per-WAN DBs are already `5m`, while newest rows are `raw`.
- That retained shape is consistent with the post-Phase-178 retention profile: short raw window plus longer aggregate retention.

## Operator Conclusion

- Operators can repeatably prove the active DB layout and footprint outcome in production today.
- The production-safe cross-WAN history proof path is:
  - read-only file inventory
  - `./scripts/soak-monitor.sh --json`
  - `sudo -n env PYTHONPATH=/opt python3 -m wanctl.history ...`
  - direct read-only DB spot checks when needed
- `/metrics/history` remains useful for envelope and endpoint checks, but the current live deployment does not yet make it a reliable proof surface for merged cross-WAN history.

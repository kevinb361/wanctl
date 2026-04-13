# Phase 179 Live Reader Topology Report

**Captured:** `2026-04-13T23:36:55Z`
**Host:** `kevin@10.10.110.223`
**Scope:** read-only production evidence for live history readers and DB topology

## Objective

Prove on the deployed host how the supported history readers behave against the live DB layout, then separate that reader evidence from direct SQLite checks on the per-WAN autorate DBs and the shared steering DB.

## Authoritative Live Topology

Read-only inventory and helper inspection show three active metrics DBs on the host:

- `/var/lib/wanctl/metrics-spectrum.db`
  - per-WAN autorate DB for Spectrum
- `/var/lib/wanctl/metrics-att.db`
  - per-WAN autorate DB for ATT
- `/var/lib/wanctl/metrics.db`
  - shared steering DB

The deployed `wanctl` user resolves the per-WAN history set with:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n -u wanctl env PYTHONPATH=/opt python3 - <<'"'"'\"'"'"'PY'"'"'\"'"'"'
from wanctl.storage.db_utils import discover_wan_dbs
print([str(p) for p in discover_wan_dbs()])
PY'
```

Observed result:

```text
['/var/lib/wanctl/metrics-att.db', '/var/lib/wanctl/metrics-spectrum.db']
```

That is the authoritative per-WAN autorate set. The shared `metrics.db` remains separate and is not part of `discover_wan_dbs()`.

## Task 1: Live CLI And HTTP Reader Behavior

### Reader Invocation Notes

- The live host does not have a `wanctl-history` wrapper on the default SSH `PATH`.
- Running the history reader as the SSH user fails on `/var/lib/wanctl/metrics.db` permissions.
- The production-safe invocation is therefore the installed module under the deployed service account:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n -u wanctl env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
```

- The autorate HTTP listener is not bound to `127.0.0.1:9101` on this host. `ss -lnt` showed:

```text
LISTEN 0 5 10.10.110.223:9101 0.0.0.0:*
LISTEN 0 5 10.10.110.227:9101 0.0.0.0:*
LISTEN 0 5 127.0.0.1:9102    0.0.0.0:*
```

- `10.10.110.223:9101/health` reports the Spectrum autorate service.
- `10.10.110.227:9101/health` reports the ATT autorate service.
- `127.0.0.1:9102` is the separate steering health surface, not the autorate history endpoint.

### CLI Evidence: `wanctl-history`

Command:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n -u wanctl env PYTHONPATH=/opt python3 - <<'"'"'\"'"'"'PY'"'"'\"'"'"'
import json, subprocess
cmd=["python3","-m","wanctl.history","--last","1h","--metrics","wanctl_rtt_ms","--json"]
rows=json.loads(subprocess.check_output(cmd, env={"PYTHONPATH":"/opt"}, text=True))
summary={}
for row in rows:
    item=summary.setdefault(row["wan_name"], {"count": 0, "first_ts": row["timestamp"], "last_ts": row["timestamp"]})
    item["count"] += 1
    item["first_ts"] = min(item["first_ts"], row["timestamp"])
    item["last_ts"] = max(item["last_ts"], row["timestamp"])
print(json.dumps(summary, indent=2, sort_keys=True))
PY'
```

Observed result:

```json
{
  "att": {
    "count": 70765,
    "first_ts": 1776119798,
    "last_ts": 1776123398
  },
  "spectrum": {
    "count": 70669,
    "first_ts": 1776119798,
    "last_ts": 1776123398
  }
}
```

Interpretation:

- The supported CLI reader is following the discovered per-WAN DB set on the live host.
- It returns both `att` and `spectrum` rows over the same 1-hour window.
- This matches the intended Phase 178 topology for the CLI surface.

### HTTP Evidence: `/metrics/history`

Command used to show the preserved response envelope:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'curl --max-time 5 -s http://10.10.110.223:9101/metrics/history?range=1h&limit=5 | python3 -m json.tool'
```

Observed response excerpt:

```json
{
  "data": [
    {
      "timestamp": "2026-04-13T23:35:35+00:00",
      "wan_name": "spectrum",
      "metric_name": "wanctl_cake_tin_backlog_bytes",
      "value": 0.0,
      "labels": "{\"tin\": \"Voice\"}",
      "granularity": "raw"
    }
  ],
  "metadata": {
    "total_count": 171720,
    "returned_count": 5,
    "granularity": "raw",
    "limit": 5,
    "offset": 0,
    "query": {
      "start": "2026-04-13T22:35:35+00:00",
      "end": "2026-04-13T23:35:35+00:00",
      "metrics": null,
      "wan": null
    }
  }
}
```

Command used to probe WAN-specific RTT history:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'python3 - <<'"'"'\"'"'"'PY'"'"'\"'"'"'
import json, urllib.request
cases = [
    ("10.10.110.223", None),
    ("10.10.110.223", "spectrum"),
    ("10.10.110.223", "att"),
    ("10.10.110.227", None),
    ("10.10.110.227", "att"),
    ("10.10.110.227", "spectrum"),
]
for host, wan in cases:
    url = f"http://{host}:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms&limit=3"
    if wan:
        url += f"&wan={wan}"
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.load(r)
    print(json.dumps({
        "host": host,
        "wan_filter": wan,
        "total": data["metadata"]["total_count"],
        "returned": data["metadata"]["returned_count"],
        "wan_names": [row["wan_name"] for row in data["data"]],
    }, indent=2))
PY'
```

Observed result:

```json
{
  "host": "10.10.110.223",
  "wan_filter": null,
  "total": 7160,
  "returned": 3,
  "wan_names": ["spectrum", "spectrum", "spectrum"]
}
{
  "host": "10.10.110.223",
  "wan_filter": "spectrum",
  "total": 7160,
  "returned": 3,
  "wan_names": ["spectrum", "spectrum", "spectrum"]
}
{
  "host": "10.10.110.223",
  "wan_filter": "att",
  "total": 0,
  "returned": 0,
  "wan_names": []
}
{
  "host": "10.10.110.227",
  "wan_filter": null,
  "total": 7161,
  "returned": 3,
  "wan_names": ["spectrum", "spectrum", "spectrum"]
}
{
  "host": "10.10.110.227",
  "wan_filter": "att",
  "total": 0,
  "returned": 0,
  "wan_names": []
}
{
  "host": "10.10.110.227",
  "wan_filter": "spectrum",
  "total": 7161,
  "returned": 3,
  "wan_names": ["spectrum", "spectrum", "spectrum"]
}
```

Interpretation:

- The HTTP response envelope remains compatible. Live `/metrics/history` still returns `{data, metadata}` and preserves `total_count`, `returned_count`, `granularity`, `limit`, `offset`, and `query`.
- The live HTTP surface does not show the same per-WAN behavior as the CLI proof above.
- Both autorate listeners returned Spectrum rows for `wanctl_rtt_ms`, and both returned zero rows for `wan=att` in the same 1-hour window even though the ATT autorate DB is present and current.
- The live result is therefore:
  - `wanctl-history`: follows the per-WAN DB set as intended
  - `/metrics/history`: envelope is compatible, but live WAN selection is not proving the intended per-WAN behavior for ATT

## Interim Conclusion After Task 1

- The supported CLI reader and the live DB discovery helper agree on the authoritative per-WAN autorate DB set.
- The supported HTTP reader preserves its contract shape but does not currently provide equivalent ATT evidence on production.
- Any milestone claim about live reader topology must distinguish those two outcomes instead of treating the reader surfaces as interchangeable.

## Task 2: Direct SQLite Spot Checks For Retention Shape And Steering Separation

### Read-Only Commands

Per-WAN autorate DB spot checks:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp ASC LIMIT 1; SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp DESC LIMIT 1; SELECT \"5m\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"5m\" ORDER BY timestamp ASC LIMIT 1; SELECT \"5m\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"5m\" ORDER BY timestamp DESC LIMIT 1;"'
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp ASC LIMIT 1; SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp DESC LIMIT 1; SELECT \"5m\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"5m\" ORDER BY timestamp ASC LIMIT 1; SELECT \"5m\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"5m\" ORDER BY timestamp DESC LIMIT 1;"'
```

Shared steering DB spot check:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp ASC LIMIT 1; SELECT \"raw\" AS granularity, timestamp, metric_name FROM metrics WHERE granularity=\"raw\" ORDER BY timestamp DESC LIMIT 1;"'
```

### Per-WAN Autorate DB Evidence

Observed `metrics-spectrum.db` result:

```json
[{"granularity":"raw","timestamp":1776036144,"metric_name":"wanctl_rtt_ms"}]
[{"granularity":"raw","timestamp":1776123398,"metric_name":"wanctl_cake_peak_delay_us"}]
[{"granularity":"5m","timestamp":1776007800,"metric_name":"wanctl_cake_total_drop_rate"}]
[{"granularity":"5m","timestamp":1776035700,"metric_name":"wanctl_irtt_asymmetry_direction"}]
```

Observed `metrics-att.db` result:

```json
[{"granularity":"raw","timestamp":1776036224,"metric_name":"wanctl_rtt_ms"}]
[{"granularity":"raw","timestamp":1776123398,"metric_name":"wanctl_cake_peak_delay_us"}]
[{"granularity":"5m","timestamp":1776007800,"metric_name":"wanctl_cake_total_drop_rate"}]
[{"granularity":"5m","timestamp":1776035700,"metric_name":"wanctl_irtt_asymmetry_direction"}]
```

ATT current RTT presence was also confirmed directly:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT timestamp, wan_name, metric_name FROM metrics WHERE metric_name=\"wanctl_rtt_ms\" ORDER BY timestamp DESC LIMIT 3;"'
```

Observed result:

```json
[{"timestamp":1776123524,"wan_name":"att","metric_name":"wanctl_rtt_ms"},
{"timestamp":1776123524,"wan_name":"att","metric_name":"wanctl_rtt_ms"},
{"timestamp":1776123524,"wan_name":"att","metric_name":"wanctl_rtt_ms"}]
```

Interpretation:

- Both per-WAN autorate DBs contain current raw RTT history.
- Both also retain a longer-lived `5m` aggregate frontier.
- The timestamps align with the post-Phase-178 retention profile:
  - earliest retained raw rows are around `2026-04-12T23:22Z` to `2026-04-12T23:23Z`
  - latest retained raw rows are at `2026-04-13T23:36:38Z`
  - earliest retained `5m` rows begin at `2026-04-12T15:30:00Z`
- That is consistent with a short raw retention window plus longer aggregate coverage, not a 24-hour raw corpus.

### Shared Steering DB Evidence

Observed `metrics.db` result:

```json
[{"granularity":"raw","timestamp":1776018216,"metric_name":"wanctl_config_snapshot"}]
[{"granularity":"raw","timestamp":1776123397,"metric_name":"wanctl_cake_tin_backlog_bytes"}]
```

Interpretation:

- The shared `metrics.db` remains active and current.
- Its spot check shows only raw rows in this sample, and the metrics are steering/shared-surface data points rather than the retained per-WAN autorate aggregate frontier used above.
- This DB must therefore be treated separately from `metrics-spectrum.db` and `metrics-att.db` when interpreting reader behavior or retention claims.

### Live Topology Conclusion

- `discover_wan_dbs()` on the deployed host resolves only the per-WAN autorate DBs: `metrics-att.db` and `metrics-spectrum.db`.
- `wanctl-history` running as the deployed `wanctl` user follows that per-WAN set and returns both WANs over the same live window.
- `/metrics/history` remains contract-compatible at the response-envelope level, but the live endpoint evidence did not prove ATT reads: both tested listeners returned Spectrum rows and `wan=att` returned zero rows during the capture window.
- Direct SQLite checks confirm that:
  - the per-WAN DBs still hold the autorate retained window
  - the shared `metrics.db` still reflects separate steering activity
  - the retained shape is consistent with the post-Phase-178 storage profile of short raw retention plus longer aggregate coverage

## Operator Outcome

Operators can safely use this report to distinguish three separate truths on production:

1. The authoritative autorate DB topology on disk is still `metrics-spectrum.db` plus `metrics-att.db`, with `metrics.db` reserved for shared steering activity.
2. The CLI history reader matches that topology on the live host.
3. The HTTP history endpoint still preserves its response contract, but its live ATT behavior requires separate follow-up before it can be claimed equivalent to the CLI proof path.

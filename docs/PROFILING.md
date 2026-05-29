# Production Profiling Runbook

This is the active profiling runbook for wanctl v1.45+. It supersedes
[`docs/archive/PROFILING.md`](archive/PROFILING.md), which points the regex/text
collector at a data path that no longer yields `autorate_cycle_total`. For timing
background and operational guardrails, see [`docs/PERFORMANCE.md`](PERFORMANCE.md).

## Critical: capture format is JSON, not text

`autorate_cycle_total` is not emitted as a parseable text DEBUG line. The total is
stored in the structured `extra=` payload of the `"Cycle timing"` log record
(`src/wanctl/perf_profiler.py:266-294`). The text formatter drops those extras;
only the JSON formatter preserves them as top-level keys
(`src/wanctl/logging_utils.py:91-96`).

The capture window therefore runs with both:

- `WANCTL_LOG_FORMAT=json`
- `--profile --debug`

The legacy `scripts/profiling_collector.py` regex collector is not load-bearing
for `autorate_cycle_total` under this runbook. Use
`scripts/profiling_collector_json.py` for cycle-budget artifacts.

## Enable (transient systemd drop-in)

Create a temporary per-instance override:

```bash
sudo systemctl edit wanctl@spectrum
```

Paste exactly:

```ini
[Service]
Environment=WANCTL_LOG_FORMAT=json
ExecStart=
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml --profile --debug
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Record the UTC start time. `ExecStart=` must be cleared before it is re-set
because it is a systemd single-value directive.

## Pilot first (5 min disk-cost + JSON-key gate)

Before committing to the full window, run a 5-minute pilot. During the pilot,
watch the unit for cycle overruns or restarts:

```bash
ssh <spectrum-host> 'journalctl -u wanctl@spectrum -f'
```

After five minutes, verify the JSON key shape:

```bash
ssh <spectrum-host> 'jq -c "select(.message == \"Cycle timing\") | keys" /var/log/wanctl/spectrum_debug.log | head -1'
```

The key list must include `cycle_total_ms`. If the key is missing, or if the
pilot shows restart/overrun clusters, abort and re-evaluate before the full
capture.

## Drive load (D-02 driven segment, inside the window)

Run the driven segment after the drop-in is active and before the revert.
`autorate_router_write_*` only fires on rate change, so the driven segment is
what proves the router-write path was exercised:

```bash
scripts/phase213-baseline-capture.sh \
    --host dallas \
    --flent-duration 60 \
    --tests tcp_upload,rrul \
    --wans spectrum
```

## Capture (≥1h)

Let the profiling window run for at least one hour, roughly 72,000 cycles at
20Hz. Continue watching for cycle-overrun warnings or unit restarts:

```bash
ssh <spectrum-host> 'journalctl -u wanctl@spectrum -f'
```

Record the UTC end time before reverting.

## Revert (mandatory safety gate)

The profiling drop-in is temporary. Revert it immediately after the capture:

```bash
sudo systemctl revert wanctl@spectrum
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
```

Verify the override is gone and the running command is back to normal:

```bash
ssh <spectrum-host> 'systemctl cat wanctl@spectrum'
ssh <spectrum-host> 'ps -ef | grep [a]utorate_continuous'
ssh <spectrum-host> 'curl -s http://127.0.0.1:9101/health | jq -r .version'
```

Expected:

- `systemctl cat wanctl@spectrum` shows no override block / `override.conf`.
- The process command contains neither `--profile` nor `--debug` nor
  `WANCTL_LOG_FORMAT=json`.
- Service is active and `/health.version == 1.45.0`.

## Retrieve (DEBUG sink + journald)

The DEBUG sink is `/var/log/wanctl/spectrum_debug.log`, not `spectrum.log`.
`spectrum.log` is INFO-only (`configs/spectrum.yaml:153-154`,
`src/wanctl/logging_utils.py:199-208`). Pull the rotated DEBUG set into the
gitignored capture directory:

```bash
scp '<spectrum-host>:/var/log/wanctl/spectrum_debug.log*' .planning/perf/capture/
```

Concatenate oldest to newest:

```bash
cat .planning/perf/capture/spectrum_debug.log.3 \
    .planning/perf/capture/spectrum_debug.log.2 \
    .planning/perf/capture/spectrum_debug.log.1 \
    .planning/perf/capture/spectrum_debug.log \
  > .planning/perf/capture/spectrum_debug.ndjson
```

Belt-and-braces: save the matching journald window too:

```bash
ssh <spectrum-host> 'journalctl -u wanctl@spectrum --since "<window start ISO>" --until "<window end ISO>" -o cat' \
  > .planning/perf/capture/spectrum_journal.ndjson
```

Raw NDJSON stays under `.planning/perf/capture/`, which is gitignored. Commit
only aggregate `.profile.json`, storage attribution JSON, and the phase summary.

## Analyze

Aggregate the captured NDJSON into the committed D-06 profile artifact:

```bash
.venv/bin/python scripts/profiling_collector_json.py \
    .planning/perf/capture/spectrum_debug.ndjson \
    --output .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).profile.json
```

Capture storage-write attribution out of band. Use explicit window bounds; the
default is last hour (`src/wanctl/history.py:616-624`):

```bash
.venv/bin/python -m wanctl.history --ingestion-rate --wan spectrum \
    --from "<window start ISO>" --to "<window end ISO>" --json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).ingestion.json
```

Compute the D-03 verdict from the profile artifact:

```bash
jq -n --slurpfile p .planning/perf/v1.45-baseline-spectrum-*.profile.json '
  def cat(labels): [labels[] as $l | $p[0][$l].avg_ms // 0] | add;
  ($p[0]["autorate_cycle_total"].avg_ms) as $total
  | ($p[0]["autorate_cycle_total"].p99_ms) as $p99
  | { utilization_pct: ($total / 50 * 100),
      headroom_avg_ms: (50 - $total),
      passes_headroom: ($total < 40 and $p99 < 50),
      categories: {
        rtt_measurement: cat(["autorate_rtt_measurement"]),
        cake_stats: cat(["autorate_cake_stats"]),
        router_communication: cat(["autorate_router_communication"]),
        logging_metrics: cat(["autorate_logging_metrics"])
      }}
  | .category_pct = (.categories | with_entries(.value = (.value / $total * 100)))
  | .max_category_pct = (.category_pct | [.[]] | max)
  | .passes_dominance = (.max_category_pct < 40)
  | .verdict = (if .passes_headroom and .passes_dominance then "no_action" else "promote" end)'
```

For the router category, use `autorate_router_communication` only. Do not sum
`router_apply_*` / `router_write_*` into that category; they are child timers and
would double-count the router parent.

## Interpret vs D-03 absolute bars

Close as `no_action` only if all are true:

- `autorate_cycle_total.avg_ms < 40.0`
- `autorate_cycle_total.p99_ms < 50.0`
- `max(category_pct) < 40.0`

Promote to a v1.46+ optimization phase if any of those fail. Archived v1.0/v1.9
numbers are informational context only under D-04; never use them as pass/fail
gates.

## Observer-effect

DEBUG capture adds work that steady-state INFO operation does not do: roughly 12
records per cycle at 20Hz, or about 240 extra records/sec. Preferred estimate:
run adjacent five-minute `/health` windows, one with `--debug` ON and one after
the drop-in is reverted, polling `cycle_budget.cycle_time_ms.avg` every 10s.
Report the ON minus OFF delta.

Fallback caveat: state that DEBUG-captured `cycle_total` is an upper bound on
normal cost. If the upper-bound number passes the D-03 bars, that is a stronger
no-action signal.

Do not compare `/health` against DEBUG `cycle_total` inside the same window;
both read the same in-process profiler (`src/wanctl/health_check.py:101`).

## Common pitfalls

- Running the regex collector against JSON capture; it will not produce the
  corrected `autorate_cycle_total` path.
- Pulling `spectrum.log` instead of `spectrum_debug.log`; the former is INFO-only.
- Treating same-window `/health` comparison as observer-effect proof; the delta
  is approximately zero by construction.
- Editing the checked-in systemd unit instead of using a transient drop-in.
- Committing raw NDJSON; keep it under `.planning/perf/capture/`.
- Running `wanctl-history --ingestion-rate` without `--from` / `--to`.
- Summing router child timers with `autorate_router_communication` for dominance.

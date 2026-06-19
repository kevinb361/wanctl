# Phase 250 Consumer Audit Evidence — 2026-06-19T213950Z

## Objective

Audit all known consumers of stored `wanctl_cake_tin_*` metrics and decide whether skip-on-unchanged is safe.

## Metrics audited

- `wanctl_cake_tin_dropped`
- `wanctl_cake_tin_ecn_marked`
- `wanctl_cake_tin_delay_us`
- `wanctl_cake_tin_backlog_bytes`

## Producer

`src/wanctl/steering/daemon.py::_append_cake_tin_metrics`

- `src/wanctl/steering/daemon.py:2340-2388`
- Appends four metrics per tin when `cake_reader.is_linux_cake` and `cake_reader.last_tin_stats` are present.
- Uses labels `{"tin": tin_name}`.
- Values:
  - dropped: `tin.get("dropped_packets", 0)`
  - ECN: `tin.get("ecn_marked_packets", 0)`
  - delay: `tin.get("avg_delay_us", 0)`
  - backlog: `tin.get("backlog_bytes", 0)`

Classification: producer.

## Runtime current-value consumer

`src/wanctl/steering/health.py::_build_congestion_section`

- `src/wanctl/steering/health.py:230-255`
- Reads `cake_reader.last_tin_stats` directly, not SQLite.
- Exposes current health payload values under `congestion.primary.tins`.

Classification: last-value-style current telemetry, but not a SQLite stored-metric consumer.

Live proof from `cake-shaper` steering health:

```text
health_tins_present=True
health_tins_count=4
Bulk: dropped_packets=0, ecn_marked_packets=0, avg_delay_us=3, peak_delay_us=10, backlog_bytes=0
BestEffort: dropped_packets=67169, ecn_marked_packets=604, avg_delay_us=12, peak_delay_us=76, backlog_bytes=0
```

This endpoint is unaffected by SQLite skip-on-unchanged because it reads the in-memory CAKE reader cache.

## SQLite history consumer

`src/wanctl/history.py --tins`

- `src/wanctl/history.py:39-45` defines `PER_TIN_METRICS` as all four stored metrics.
- `src/wanctl/history.py:355-409` formats raw query rows into a timestamp/WAN/tin pivot table.
- `src/wanctl/history.py:412-436` emits raw JSON rows with tin extracted as a top-level field.
- `src/wanctl/history.py:940-958` queries `query_metrics(..., metrics=PER_TIN_METRICS, ...)` and prints the raw rows.

Classification: raw-history / continuous-series consumer.

Reason: `--tins` is explicitly a history query and exposes the stored rows over a time range. It does not use last-value-before-T interpolation semantics. Making rows sparse would change the shape and density of historical output.

## Counter-shaped metrics

`wanctl_cake_tin_dropped` and `wanctl_cake_tin_ecn_marked` represent cumulative counter-shaped CAKE tin values:

- dropped packets;
- ECN marked packets.

Classification: delta-sensitive / count-over-window risk.

Reason: even if the current repo does not compute deltas from these stored rows today, continuous samples preserve the ability to compute changes over arbitrary windows. Sparse skip-on-unchanged would make no-change periods disappear from raw history and could make downstream rate/delta calculations ambiguous unless consumers are upgraded to last-value-before-window semantics.

## Gauge-shaped metrics

`wanctl_cake_tin_delay_us` and `wanctl_cake_tin_backlog_bytes` are gauge-shaped values:

- average delay;
- current backlog.

Classification: likely last-value-compatible if considered alone.

But Phase 250's gate is all-or-defer for the per-tin stored metric family. A partial change to only two of four metrics would create mixed sparse/continuous row density in the same `--tins` output, which is operator-hostile and outside the phase's stated condition.

## Tests / fixtures

`tests/test_history_cli.py::TestPerTinHistory`

- verifies `--tins` queries exactly all four metrics;
- verifies table/JSON formatting of raw per-tin rows.

`tests/steering/test_steering_metrics_recording.py`

- verifies per-tin metrics are written for Linux CAKE and absent for non-Linux/no-data paths;
- current test models 16 rows for 4 tins × 4 metrics.

Classification: test-only consumers, but they encode the current continuous-row contract.

## Docs / planning consumers

- `README.md:419-420` documents `wanctl-history --tins --last 1h --json`.
- `docs/SUBSYSTEMS.md:116` documents direct `--tins` history query.
- `docs/archive/BRIDGE_QOS.md:43` preserves the same command historically.
- `.planning/seeds/SEED-007-v145-storage-hygiene-fire-on-change.md:65-71` explicitly defines the gate: last-value-before-T is safe, count/window is unsafe, otherwise defer.
- `.planning/todos/completed/2026-04-17-cake-tin-skip-on-unchanged-consumer-audit.md:21-24` records the original same gate.

Classification: doc/planning consumers. They confirm the intended gate and the operator-facing raw-history UX.

## Live SQLite check

Current stable external mode has no stored per-tin rows in the recent window:

```text
sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --tins --last 1h --json
No per-tin data found for the specified time range.
```

This means there is no current write-rate reduction to measure for stored per-tin metrics under the live external cake-autorate owner.

## Test verification

Relevant test slice:

```text
.venv/bin/pytest -o addopts='' tests/test_history_cli.py::TestPerTinHistory tests/steering/test_steering_metrics_recording.py -q
28 passed in 0.58s
```

## Verdict

Do not implement skip-on-unchanged in v1.54.

Reason:

- `wanctl-history --tins` is a raw historical row consumer, not last-value-before-T.
- dropped/ECN are counter-shaped and delta-sensitive.
- current live external mode has no stored per-tin rows to optimize anyway.
- a partial gauge-only optimization would create mixed density in one operator-facing history command and is outside the all-or-defer gate.

Disposition:

- TIN-01: complete.
- TIN-02: deferred to v1.55 / future phase pending consumer redesign or explicit acceptance of sparse semantics.
- TIN-03: deferred with TIN-02 because no implementation shipped.

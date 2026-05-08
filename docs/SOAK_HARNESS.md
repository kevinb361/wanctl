# Soak Harness

This document describes the wanctl soak capture and summary harness used for
long-running validation evidence. The harness is intentionally outside the
autorate control path: it reads `/health`, writes NDJSON, and aggregates that
capture into `soak-summary.json` for operator review.

## Purpose

The soak harness captures a long-running `/health` stream, usually for a 24 hour
window, then summarizes the capture into a small JSON artifact that can be used
for validation gates and later calibration work. It is the evidence path for
questions that cannot be answered from a single health snapshot, such as target
edge churn over time or suppression behavior by cause.

For v1.43, the harness supports the Phase 201 secondary-gate watchdog follow-up:
capture per-sample `load_rtt_delta_us`, aggregate it as histograms and
percentiles, and break it down by upload zone and suppression cause. Phase 204
uses the same shape to derive a soak-grounded D-14 successor threshold.

The harness does not tune the controller, change queue limits, or write router
state. It is a capture-and-analysis surface only.

## Files

| File | Role | Notes |
|------|------|-------|
| `scripts/soak-capture.sh` | Capture harness uploaded to a deploy target. | Runs as a long-lived shell process, reads `HEALTH_URL`, and writes one NDJSON row per second. Created in Phase 203. |
| `scripts/soak_summary_aggregate.py` | Offline summary aggregator. | Stdlib-only Python. Reads `soak-capture.ndjson` and writes `soak-summary.json`. Created in Phase 203. |
| `scripts/soak-monitor.sh` | Live operator dashboard. | Existing monitoring helper; cross-reference only. It is not the Phase 203 capture or aggregation source of truth. |

`scripts/soak-capture.sh` requires `HEALTH_URL` from the environment. It has no
hardcoded host or endpoint default.

## NDJSON Per-Row Schema

Each line of `soak-capture.ndjson` is a single JSON object. The Phase 203 schema
is flat and additive: the v1.42 fields are preserved, and seven v1.43 fields are
appended for target-edge churn analysis.

| Key | Type | Source in `/health` | Semantics |
|-----|------|---------------------|-----------|
| `t_wall` | string | capture host clock | UTC wall-clock timestamp emitted by the capture script. |
| `t_monotonic` | float | capture host `/proc/uptime` | Seconds since capture start, monotonic-clock derived. |
| `version` | string | `.version` | wanctl version reported by the health endpoint. |
| `status` | string | `.status` | Top-level service health status. |
| `floor_hit_cycles_total` | int | `.wans[0].upload.floor_hit_cycles_total` | Upload floor-hit counter at sample time. |
| `suppressions_per_min` | int | `.wans[0].upload.hysteresis.suppressions_per_min` | Legacy live dwell-hold counter. Preserved for backward compatibility; not a completed-window rate. |
| `max_delay_delta_us` | int/null | `.wans[0].upload.max_delay_delta_us` | Upload CAKE delay-delta diagnostic in microseconds when available. |
| `red_streak` | int | `.wans[0].upload.red_streak` | Consecutive upload RED-cycle diagnostic. |
| `zone_trace_tail` | array[string] | `.wans[0].upload.zone_trace[-5:]` | Last five upload zones for local context. |
| `headroom_state` | string/null | `.wans[0].upload.headroom_state` | DOCSIS headroom state, when DOCSIS mode is active. |
| `headroom_exhausted_streak` | int/null | `.wans[0].upload.headroom_exhausted_streak` | Consecutive exhausted-headroom diagnostic. |
| `anti_windup_triggers` | int/null | `.wans[0].upload.anti_windup_triggers` | Count of anti-windup interventions reported by `/health`. |
| `rtt_integral_ms_s` | float/null | `.wans[0].upload.rtt_integral_ms_s` | Upload RTT integral diagnostic in millisecond-seconds. |
| `docsis_mode_active` | bool/null | `.wans[0].upload.docsis_mode_active` | Runtime indication that DOCSIS-aware upload mode is active. |
| `red_decay_step_pct` | float/null | `.wans[0].upload.red_decay_step_pct` | Runtime echo of bounded RED decay step percentage. |
| `red_decay_delta_max_pct` | float/null | `.wans[0].upload.red_decay_delta_max_pct` | Runtime echo of bounded RED decay maximum delta percentage. |
| `load_rtt_ms` | float/null | `.wans[0].load_rtt_ms` | **Phase 203 addition.** Raw load RTT in milliseconds. |
| `baseline_rtt_ms` | float/null | `.wans[0].baseline_rtt_ms` | **Phase 203 addition.** Current baseline RTT in milliseconds. |
| `load_rtt_delta_us` | int/null | computed from `load_rtt_ms` and `baseline_rtt_ms` | **Phase 203 addition.** `floor((load_rtt_ms - baseline_rtt_ms) * 1000)`. Null when either source is null. |
| `last_zone` | string | `.wans[0].upload.hysteresis.last_zone` | **Phase 203 addition.** Upload-side zone for the sample: `GREEN`, `YELLOW`, `SOFT_RED`, or `RED`. |
| `ul_suppressions_completed_window_count` | int | `.wans[0].upload.hysteresis.suppressions_completed_window_count` | **Phase 203 addition.** Completed 60s-window suppression total from Phase 202. |
| `ul_suppressions_completed_window_by_cause` | object | `.wans[0].upload.hysteresis.suppressions_completed_window_by_cause` | **Phase 203 addition.** Completed-window suppression total by cause. |
| `ul_suppressions_lifetime_by_cause` | object | `.wans[0].upload.hysteresis.suppressions_lifetime_by_cause` | **Phase 203 addition.** Monotonic per-cause lifetime counters since process start. |

The seven Phase 203 additions are diagnostic fields only. They are projected from
already-exposed `/health` values and do not require controller behavior changes.

## `soak-summary.json` Output Schema

`scripts/soak_summary_aggregate.py` reads the NDJSON capture and emits a JSON
object with three primary sections:

```json
{
  "diagnostic_distribution": {
    "rtt_integral_ms_s": {"mean": 0.0, "max": 0.0},
    "max_delay_delta_us": {"mean": 0.0, "max": 0},
    "red_streak": {"mean": 0.0, "max": 0},
    "headroom_exhausted_samples": 0,
    "total_samples": 0,
    "load_rtt_delta_us": {
      "p50": 0,
      "p95": 0,
      "p99": 0,
      "max": 0,
      "count": 0,
      "histogram": {
        "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000],
        "counts": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
      },
      "samples_total": 0,
      "samples_filtered_null": 0
    }
  },
  "load_rtt_delta_us_by_zone_cause": {
    "GREEN": {
      "dwell_hold": {"p50": 0, "p95": 0, "p99": 0, "max": 0, "count": 0, "histogram": {"buckets_us": [], "counts": []}},
      "backlog_recovery": {"p50": 0, "p95": 0, "p99": 0, "max": 0, "count": 0, "histogram": {"buckets_us": [], "counts": []}},
      "other": {"p50": 0, "p95": 0, "p99": 0, "max": 0, "count": 0, "histogram": {"buckets_us": [], "counts": []}}
    },
    "YELLOW": {},
    "SOFT_RED": {},
    "RED": {}
  },
  "phase_203_metadata": {
    "attribution_policy": "dual",
    "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000],
    "zone_axis": "upload"
  }
}
```

### `diagnostic_distribution.load_rtt_delta_us`

This block aggregates all non-null `load_rtt_delta_us` samples:

| Field | Meaning |
|-------|---------|
| `p50` | Median load RTT delta in microseconds. |
| `p95` | 95th percentile load RTT delta in microseconds. |
| `p99` | 99th percentile load RTT delta in microseconds. |
| `max` | Maximum load RTT delta in microseconds. |
| `count` | Number of non-null samples included in percentile and histogram math. |
| `histogram.buckets_us` | Bucket boundary array used for this summary. |
| `histogram.counts` | Bucket counts. Length is `len(buckets_us) + 1`; the final count is overflow. |
| `samples_total` | Rows containing the `load_rtt_delta_us` key, including null values. |
| `samples_filtered_null` | Rows where `load_rtt_delta_us` was present but null. |

### `load_rtt_delta_us_by_zone_cause`

This matrix is 4 upload zones by 3 suppression causes: 12 cells total. Every cell
has the same shape:

```json
{
  "p50": 0,
  "p95": 0,
  "p99": 0,
  "max": 0,
  "count": 0,
  "histogram": {
    "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000],
    "counts": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  }
}
```

Empty cells are emitted as fully-zeroed objects instead of omitted fields. This
keeps downstream diffs stable and mirrors the Phase 202 "empty cause is zero, not
missing" convention.

### Preserved v1.42 Fields

The aggregator preserves the unaffected v1.42 diagnostic distribution fields
when the source rows contain the required keys:

- `rtt_integral_ms_s.mean` and `rtt_integral_ms_s.max`
- `max_delay_delta_us.mean` and `max_delay_delta_us.max`
- `red_streak.mean` and `red_streak.max`
- `headroom_exhausted_samples`
- `total_samples`

It does not compute the Phase 201 D-14 watchdog verdict. Phase 204 owns the
successor watchdog computation.

## Watchdog computation transition (CALIB-03)

Phase 204 introduces a dual-emission watchdog in `soak-summary.json`. Both
blocks are emitted side-by-side for **one transition cycle = the v1.43
milestone**; the legacy block drops in a v1.44 follow-up commit.

### `secondary_gate_legacy` (informational only — drops in v1.44)

```json
"secondary_gate_legacy": {
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE - drops in v1.44.",
  "value": 6.466842364880155,
  "threshold": 5.0,
  "window_count": 1439,
  "verdict": "fail",
  "note": "This metric is metric-semantically broken; see Phase 201 RETRO Lesson #1. Use secondary_gate_completed_window for actual gating."
}
```

### `secondary_gate_completed_window` (the real gate)

```json
"secondary_gate_completed_window": {
  "name": "ul_suppressions_completed_window_count_<statistic>",
  "value": 70.25999999999999,
  "threshold": 125,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "gate_column": "by_cause.dwell_hold",
  "verdict": "pass",
  "operator_approval": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md"
}
```

The CALIB-04 verification soak (Plan 204-05) passes iff both
`primary_gate.verdict == "pass"` and
`secondary_gate_completed_window.verdict == "pass"`. The
`secondary_gate_legacy` block is not part of the pass criterion.

### Operator-approved constants

`scripts/calib_02_threshold.json` is the machine-readable mirror of
`204-CALIB-02-OPERATOR-APPROVAL.md`. It provides `statistic`, `threshold`,
`headroom_factor`, and `gate_column` (open-Q2 slice-vs-total decision). The
aggregator loads it via `load_calib_02_constants()` at `aggregate_soak()` time.

## Histogram Bucket Interpretation

Default bucket boundaries are expressed in microseconds:

```text
[0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]
```

The defaults align with the v1.42 Spectrum threshold scale:

- `target_bloat_ms=15` -> `15000` microseconds
- `warn_bloat_ms=30` -> `30000` microseconds
- `hard_red_bloat_ms=60` -> `60000` microseconds

Bucket `i` contains values in `[buckets[i], buckets[i+1])`. The final `counts`
cell is the overflow bucket for values greater than or equal to `250000`
microseconds. Values below zero are counted in the first bucket so negative deltas
remain visible without failing aggregation.

The aggregator accepts CLI overrides:

```bash
.venv/bin/python scripts/soak_summary_aggregate.py \
  ./soak-capture.ndjson \
  -o ./soak-summary.json \
  --target-delta-us 15000 \
  --warn-delta-us 30000 \
  --hard-red-us 60000
```

The selected boundary array is written into every histogram object's `buckets_us`
field. Consumers should read the summary's `buckets_us` rather than assuming the
current source defaults.

## Cause-Tag Attribution Rule

Per-sample cause is derived from the delta in
`ul_suppressions_lifetime_by_cause` relative to the previous sample. If the
current row's lifetime counter for cause `C` is greater than the previous row's
counter for `C`, the current row is attributed to cause `C`.

Cause labels are:

- `dwell_hold` — `_apply_dwell_logic` suppressed a GREEN-to-YELLOW transition
  while the dwell timer was active.
- `backlog_recovery` — green-streak recovery was suppressed while the CAKE
  backlog condition held. This can fire every 50ms cycle while active.
- `other` — reserved fallback bucket; no current callsite is expected to fire it.

Dual-attribution is intentional. If a single 50ms cycle increments both
`dwell_hold` and `backlog_recovery`, the sample contributes to both
`(zone, dwell_hold)` and `(zone, backlog_recovery)`. Matrix counts can therefore
exceed `diagnostic_distribution.total_samples`. The summary records this as
`phase_203_metadata.attribution_policy = "dual"`.

The first NDJSON row is excluded from the zone-by-cause matrix because there is
no previous lifetime-counter sample. It is still included in the top-level
`diagnostic_distribution.load_rtt_delta_us` distribution when its delta is
non-null.

## Zone Axis Is Upload-Only

The `last_zone` field is projected from
`/health.wans[0].upload.hysteresis.last_zone`. The
`load_rtt_delta_us_by_zone_cause` matrix is therefore an upload-state matrix.
This is deliberate: the Phase 203 target metric is upload-side load RTT delta,
and v1.43's recalibration work targets the upload suppression watchdog.

Download-side aggregation is not part of Phase 203. If a future phase needs the
same matrix for download, it should add a separate field such as
`dl_load_rtt_delta_us_by_zone_cause` with a download-specific zone set.

## No-Control-Path-Change Invariant (Harness-Only)

Phase 203 is harness-only. The deliverables read existing `/health` fields and
analyze captured rows; they do not modify `src/wanctl/`, controller timing,
state transitions, thresholds, queue writes, or router behavior.

The SAFE-07 invariant is verified mechanically with:

```bash
bash scripts/check-safe07-source-diff.sh
```

The script runs the equivalent of:

```bash
git diff <phase-202-close-sha>..HEAD -- src/wanctl/
```

and exits non-zero if any control-path source diff appears. Phase 203 closeout
also keeps the SAFE-05 pin test unchanged; there is no Phase 203 symbol-count pin
because this phase adds no `src/wanctl/` symbols.

Production canary is not required for Phase 203 deliverables. The capture and
aggregation layer is local-repo tooling; production binary and soak execution
come later in the v1.43 calibration sequence.

## Limitations

- **Asymmetry-gate disabled deployments only for exact deltas.**
  `load_rtt_delta_us` uses raw `load_rtt_ms`, not an asymmetry-gate-attenuated
  effective RTT. On the v1.43 Spectrum baseline where the asymmetry gate is
  disabled, this is exact. On a future gate-enabled deployment, gate-active
  windows would over-state the delta.
- **Reference soak predates Phase 203 fields.** The v1.42 reference NDJSON lacks
  `load_rtt_ms`, `baseline_rtt_ms`, `load_rtt_delta_us`, and the cause-tag
  fields. Phase 203 uses synthetic replay fixtures for the new matrix while
  retaining v1.42 diagnostic-regression coverage for unaffected fields.
- **2-decimal RTT precision.** `/health` rounds `load_rtt_ms` and
  `baseline_rtt_ms` to two decimal places. That is 10 microsecond precision,
  which is finer than the millisecond-scale histogram boundaries used here.

## Usage Example

```bash
# On the deploy target:
HEALTH_URL=http://<host>:9101/health \
  bash scripts/soak-capture.sh "$(date -u +%Y%m%dT%H%M%SZ)"

# After the soak completes, copy soak-capture.ndjson back to the analysis host.

.venv/bin/python scripts/soak_summary_aggregate.py \
  ./soak-capture.ndjson \
  -o ./soak-summary.json
```

For live operator watching during a soak, use `scripts/soak-monitor.sh` as a
separate dashboard. It is not the source of the capture schema documented here.

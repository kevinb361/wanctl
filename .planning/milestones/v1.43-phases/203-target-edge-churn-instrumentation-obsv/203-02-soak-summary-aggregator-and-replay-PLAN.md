---
id: 203-02
phase: 203
plan: 02
type: execute
wave: 2
depends_on:
  - 203-01
files_modified:
  - scripts/soak_summary_aggregate.py
  - tests/fixtures/_phase_203_generator.py
  - tests/fixtures/phase_203_synthetic_capture.ndjson
  - tests/fixtures/phase_203_synthetic_summary.json
  - tests/test_phase_203_replay.py
autonomous: true
production_canary: false
created: 2026-05-06
requirements:
  - OBSV-06
  - OBSV-07
  - SAFE-07
must_haves:
  truths:
    - "scripts/soak_summary_aggregate.py reads an NDJSON soak capture and writes a soak-summary.json that includes diagnostic_distribution.load_rtt_delta_us (p50/p95/p99/max + histogram with explicit buckets_us) and the load_rtt_delta_us_by_zone_cause matrix (4 zones × 3 causes)."
    - "Empty (zone, cause) cells emit a fully-zeroed histogram object with count=0, NOT null, NOT key-omission."
    - "Multi-cause cycles are dual-attributed: a row contributes to every cause whose lifetime counter incremented since the previous sample. Counts may exceed total_samples; this is documented in the script header and in the summary metadata."
    - "Bucket boundaries are written into the JSON output (`buckets_us` array) so consumers don't need the source config to interpret the data. Defaults are operator-relevant breakpoints aligned with target_bloat_ms / warn_bloat_ms / hard_red_bloat_ms; CLI override available."
    - "Samples with null load_rtt_delta_us are filtered before histogram and percentile computation; the filtered count is reported in the summary metadata."
    - "tests/fixtures/_phase_203_generator.py emits tests/fixtures/phase_203_synthetic_capture.ndjson deterministically (fixed seed). Drift-detection test re-runs the generator and asserts byte-identical output against the checked-in fixture."
    - "tests/test_phase_203_replay.py contains: aggregator-math replay against the synthetic fixture (golden JSON byte-comparison), v1.42 NDJSON regression for diagnostic_distribution backward-compat, zone-axis-upload-only verification, cause-attribution edge cases, and the generator drift-detection test."
    - "tests/test_phase_202_replay.py imports continue to work; aggregate_completed_windows and _percentile are lifted into the new aggregator module (or kept in test_phase_202_replay.py and imported back — refactor decision made by executor; either way, no Phase 202 test breakage)."
    - "No src/wanctl/** files modified by this plan."
  artifacts:
    - path: scripts/soak_summary_aggregate.py
      provides: "Promoted versioned aggregator for soak-summary.json (OBSV-06). Pure stdlib Python; reusable by Phase 204 CALIB-01."
      contains: "aggregate_load_rtt_delta"
    - path: tests/fixtures/_phase_203_generator.py
      provides: "Deterministic NDJSON fixture generator. Re-runnable with fixed seed; drift-detection enforces fixture matches generator output."
      contains: "generate_synthetic_ndjson"
    - path: tests/fixtures/phase_203_synthetic_capture.ndjson
      provides: "Hand-crafted ~150 row NDJSON exercising all 12 (zone, cause) cells, bucket boundaries, first-row exclusion, and null-baseline edge case."
    - path: tests/fixtures/phase_203_synthetic_summary.json
      provides: "Golden expected aggregator output for the synthetic NDJSON. Exact byte-comparison oracle."
    - path: tests/test_phase_203_replay.py
      provides: "OBSV-06 aggregator-math replay + OBSV-07 aggregator side; v1.42 regression; cause-attribution tests; generator drift-detection."
      contains: "TestAggregatorMath"
  key_links:
    - from: "scripts/soak_summary_aggregate.py::aggregate_by_zone_cause"
      to: "ul_suppressions_lifetime_by_cause delta from previous row"
      via: "lifetime counter increment per cause = cause attribution for that sample"
      pattern: "ul_suppressions_lifetime_by_cause"
    - from: "tests/fixtures/_phase_203_generator.py"
      to: "tests/fixtures/phase_203_synthetic_capture.ndjson"
      via: "deterministic generator with fixed seed; checked-in fixture matches generator output byte-identically"
      pattern: "generate_synthetic_ndjson"
    - from: "tests/test_phase_203_replay.py::TestAggregatorMath"
      to: "tests/fixtures/phase_203_synthetic_summary.json"
      via: "aggregate_soak(synthetic_ndjson) byte-equals golden summary JSON"
      pattern: "phase_203_synthetic_summary"
---

<objective>
Land the OBSV-06 aggregator and the OBSV-07 aggregator-side replay strategy. Promote the inline-jq soak summary computation (currently embedded in the v1.42 Plan 201-16 closeout PLAN) to a versioned, testable, reusable Python script under `scripts/`. Author a deterministic synthetic NDJSON fixture exercising every `(zone, cause)` cell, bucket boundary, and edge case. Land the dual-fixture replay test: aggregator-math against the synthetic fixture (byte-comparison oracle) plus v1.42 NDJSON regression for backward-compatible diagnostic_distribution math.

Purpose: The Phase 201-16 inline-jq aggregator is unsustainable (gnarly histogram math in jq; no unit tests; bug-prone — already had two correctness bugs). Phase 204 (CALIB) requires a reusable, callable, tested aggregator to compute the recalibration baseline distribution from the CALIB-01 24h soak. Phase 203's deliverable IS that aggregator.

The dual-fixture strategy is required because the v1.42 reference NDJSON predates three of the five Phase 203 capture fields (203-RESEARCH.md §Golden-fixture replay strategy, verified). End-to-end golden replay against v1.42 is impossible; the synthetic fixture is the substitute. The v1.42 NDJSON regression covers the unaffected fields (`diagnostic_distribution.{rtt_integral_ms_s, max_delay_delta_us, red_streak, headroom_exhausted_samples, total_samples}`) to prove the inline-jq → Python promotion didn't drop a behavior.

Output: New `scripts/soak_summary_aggregate.py` (stdlib-only, ~250-350 LOC), a deterministic generator at `tests/fixtures/_phase_203_generator.py` plus the checked-in fixtures it produces, and `tests/test_phase_203_replay.py` with five test classes. SCOPE TIGHTLY to diagnostic-distribution math; the secondary-gate computation (`ul_hysteresis_suppression_rate_per_60s_mean`) is explicitly out of scope for this plan (Phase 204 / CALIB-03 territory).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-RESEARCH.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VALIDATION.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-01-soak-capture-script-and-projection-test-PLAN.md
@CLAUDE.md
@tests/test_phase_202_replay.py

<interfaces>
<!-- The NDJSON row schema this aggregator reads is locked by plan 203-01. -->
<!-- Each row contains the v1.42 keys + the seven Phase 203 keys. -->

Per-row NDJSON schema (locked by plan 203-01):
```
v1.42 keys (preserved):
  t_wall, t_monotonic, version, status,
  floor_hit_cycles_total, suppressions_per_min,
  max_delay_delta_us, red_streak, zone_trace_tail,
  headroom_state, headroom_exhausted_streak,
  anti_windup_triggers, rtt_integral_ms_s,
  docsis_mode_active, red_decay_step_pct,
  red_decay_delta_max_pct

v1.43 Phase 203 additions:
  load_rtt_ms                                  (float, may be null)
  baseline_rtt_ms                              (float, may be null)
  load_rtt_delta_us                            (int microseconds, may be null)
  last_zone                                    (string: "GREEN"/"YELLOW"/"SOFT_RED"/"RED")
  ul_suppressions_completed_window_count       (int)
  ul_suppressions_completed_window_by_cause    (dict: dwell_hold/backlog_recovery/other → int)
  ul_suppressions_lifetime_by_cause            (dict: dwell_hold/backlog_recovery/other → int, monotonic)
```

Aggregator output schema (locked here in plan 203-02 — additions on top of the v1.42 reference shape):
```json
{
  ...existing v1.42 keys preserved verbatim where applicable...,
  "diagnostic_distribution": {
    ...existing v1.42 keys preserved...,
    "load_rtt_delta_us": {
      "p50": <int>,
      "p95": <int>,
      "p99": <int>,
      "max": <int>,
      "histogram": {
        "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000],
        "counts":     [<12 ints + 1 overflow = 13 values>]
      },
      "samples_total": <int>,
      "samples_filtered_null": <int>
    }
  },
  "load_rtt_delta_us_by_zone_cause": {
    "GREEN":   {"dwell_hold": {<cell>}, "backlog_recovery": {<cell>}, "other": {<cell>}},
    "YELLOW":  {"dwell_hold": {<cell>}, "backlog_recovery": {<cell>}, "other": {<cell>}},
    "SOFT_RED":{"dwell_hold": {<cell>}, "backlog_recovery": {<cell>}, "other": {<cell>}},
    "RED":     {"dwell_hold": {<cell>}, "backlog_recovery": {<cell>}, "other": {<cell>}}
  },
  "phase_203_metadata": {
    "attribution_policy": "dual",
    "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000],
    "zone_axis": "upload"
  }
}

Where <cell> = {"p50": <int>, "p95": <int>, "p99": <int>, "max": <int>, "count": <int>,
                "histogram": {"buckets_us": [...same as top...], "counts": [...13 values...]}}
```

Helpers to lift from `tests/test_phase_202_replay.py` (or duplicate cleanly — refactor decision in Task 1):
- `aggregate_completed_windows(snapshots) -> list[int]` — boundary-detection over the suppressions_per_min column.
- `_percentile(values, p) -> float` — stdlib quantiles-based percentile.

v1.42 reference soak-summary.json values for backward-compat assertions (verified by inspection at the soak-evidence path):
- `diagnostic_distribution.rtt_integral_ms_s.mean ≈ 5.14`, `.max ≈ 270.6`
- `diagnostic_distribution.max_delay_delta_us.mean ≈ 810.3`, `.max == 161281`
- `diagnostic_distribution.red_streak.mean ≈ 0.006`, `.max == 101`
- `diagnostic_distribution.headroom_exhausted_samples == 469`
- `diagnostic_distribution.total_samples == 84117`
</interfaces>
</context>

<locked_decisions>
- **Cause-attribution policy (gray-area #2):** **dual-attribution.** A row contributes to every cause whose lifetime counter incremented since the previous sample. Counts may exceed total_samples. Documented in the script header AND in `phase_203_metadata.attribution_policy: "dual"` in the output JSON. Rationale: dual-attribution preserves all information; Phase 204's threshold derivation cares about per-cell percentiles, not sum-of-counts identity.

- **Histogram bucket boundaries (gray-area #3):** **operator-relevant Spectrum-aligned defaults**, expressed in **microseconds** (matches `load_rtt_delta_us` units):
  ```python
  DEFAULT_BUCKETS_US = [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]
  ```
  These align with `target_bloat_ms=15` (→ 15000 µs) and `warn_bloat_ms=30` (→ 30000 µs) from `configs/spectrum.yaml`. CLI flags `--target-delta-us`, `--warn-delta-us`, `--hard-red-us` allow override; the resulting `buckets_us` array is written into the JSON output.

- **Empty-cell handling (gray-area #7):** if a `(zone, cause)` cell has zero samples, the cell is emitted as a fully-zeroed object: `{"p50": 0, "p95": 0, "p99": 0, "max": 0, "count": 0, "histogram": {"buckets_us": [...], "counts": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}}`. NOT null, NOT key-omission. Mirrors Phase 202's "empty cause = `0`, not omitted" pattern.

- **Null `load_rtt_delta_us` handling (gray-area #8):** the aggregator filters rows where `load_rtt_delta_us` is null BEFORE histogram or percentile computation. The filtered count is reported in `diagnostic_distribution.load_rtt_delta_us.samples_filtered_null`. Cause-attribution still runs on the filtered-out rows (lifetime delta is independent), but those rows do not contribute a value to the per-cell histogram (their `samples_filtered_null` is rolled up into the metadata).

- **Synthetic fixture authoring (gray-area #1):** **versioned generator + checked-in fixture**. Re-running the generator produces byte-identical NDJSON (deterministic seed = `42`). Drift-detection test asserts the checked-in fixture matches the generator's current output. If a future contributor edits the generator, the test breaks loudly.

- **First-row exclusion:** the very first NDJSON row has no previous sample → no cause-attribution possible. The aggregator skips the first row's contribution to `load_rtt_delta_us_by_zone_cause`. The first row IS counted in the top-level `diagnostic_distribution.load_rtt_delta_us` histogram (cause attribution is independent of value distribution).

- **Aggregator scope is TIGHT:** diagnostic-distribution math + zone × cause-tag matrix only. The `secondary_gate.computation` (60s-sliding-window-mean of `ul_hysteresis_suppression_rate_per_60s_mean`) is explicitly **OUT OF SCOPE** for plan 203-02 — that is Phase 204 / CALIB-03 territory. The aggregator may emit `secondary_gate` if the input NDJSON had it (passthrough from v1.42 inline-jq), but does NOT compute the new metric here.

- **Stdlib-only Python.** No NumPy, no pandas, no external deps. `statistics`, `bisect`, `json`, `pathlib`, `argparse`, `sys`. Matches `tests/test_phase_202_replay.py::_percentile` precedent.

- **Refactor of Phase 202 helpers (gray-area / Risk 8):** the executor decides whether to (a) lift `aggregate_completed_windows` and `_percentile` from `tests/test_phase_202_replay.py` into the new module and update the test imports, or (b) duplicate them in the aggregator and leave `tests/test_phase_202_replay.py` untouched. **Recommendation:** option (a) — single source of truth, Phase 204 reuse. But (b) is acceptable if (a) creates merge friction. Either way, `.venv/bin/pytest tests/test_phase_202_replay.py -v` MUST stay green after this plan.
</locked_decisions>

<tasks>

<task type="auto">
  <name>Task 1: Create scripts/soak_summary_aggregate.py with the diagnostic-distribution and zone × cause matrix math</name>
  <files>scripts/soak_summary_aggregate.py</files>
  <action>
    Create `scripts/soak_summary_aggregate.py` as a stdlib-only Python module + CLI. Match the existing `scripts/analyze_*.py` pattern (snake_case, executable shebang, `if __name__ == "__main__":` CLI block).

    Module structure (target ~250-350 LOC):

    ```python
    #!/usr/bin/env python3
    """Phase 203 OBSV-06 soak summary aggregator.

    Reads a soak-capture.ndjson and writes a soak-summary.json including:
      * diagnostic_distribution.load_rtt_delta_us — p50/p95/p99/max + histogram
      * load_rtt_delta_us_by_zone_cause          — 4 zones × 3 causes matrix
      * v1.42-compatible diagnostic_distribution fields preserved verbatim

    Promoted from the inline-jq pipeline embedded in v1.42 Plan 201-16 closeout
    PLAN. Stdlib-only — no NumPy, no pandas. Reusable by Phase 204 CALIB-01 to
    compute the recalibration baseline distribution.

    Cause-attribution policy: DUAL. A row contributes to every cause whose
    lifetime counter incremented since the previous sample. Counts may exceed
    total_samples — this is documented in the output metadata.

    Zone axis: UPLOAD only. last_zone is projected from the upload-side
    hysteresis state. v1.43 milestone goal is Spectrum (cable) UL recalibration;
    download-side aggregation is a future seed if needed.

    Usage:
        python3 scripts/soak_summary_aggregate.py <ndjson_path> [-o <output>]
                [--target-delta-us 15000] [--warn-delta-us 30000]
                [--hard-red-us 60000]
    """
    from __future__ import annotations

    import argparse
    import bisect
    import json
    import math
    import statistics
    import sys
    from pathlib import Path
    from typing import Any, Iterable

    DEFAULT_BUCKETS_US = [
        0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000,
    ]
    ZONES = ("GREEN", "YELLOW", "SOFT_RED", "RED")
    CAUSES = ("dwell_hold", "backlog_recovery", "other")


    # -- Helpers ----------------------------------------------------------------

    def aggregate_completed_windows(snapshots: list[int]) -> list[int]:
        """Detect 60s window resets in a suppressions_per_min column."""
        if len(snapshots) < 2:
            return []
        out: list[int] = []
        for i in range(1, len(snapshots)):
            if snapshots[i] < snapshots[i - 1]:
                out.append(int(snapshots[i - 1]))
        return out


    def percentile(values: list[float], p: float) -> float:
        """Linear-interpolation percentile, NumPy-free.

        Returns 0.0 for empty input (avoids exceptions in empty-cell histograms).
        """
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return float(ordered[0])
        rank = (len(ordered) - 1) * (p / 100.0)
        lower = math.floor(rank)
        upper = math.ceil(rank)
        if lower == upper:
            return float(ordered[lower])
        fraction = rank - lower
        return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


    def histogram(values: Iterable[float], buckets: list[int]) -> list[int]:
        """Bucket counts. Length = len(buckets) + 1 (last cell is overflow).

        Bucket [i] contains values in [buckets[i], buckets[i+1]). Last bucket
        contains values >= buckets[-1].
        """
        sorted_buckets = sorted(buckets)
        counts = [0] * (len(sorted_buckets) + 1)
        for v in values:
            idx = bisect.bisect_right(sorted_buckets, v) - 1
            if idx < 0:
                idx = 0  # value below first boundary → first bucket
            elif idx >= len(sorted_buckets):
                idx = len(sorted_buckets)  # overflow
            counts[idx] += 1
        return counts


    def _empty_cell(buckets: list[int]) -> dict:
        return {
            "p50": 0,
            "p95": 0,
            "p99": 0,
            "max": 0,
            "count": 0,
            "histogram": {
                "buckets_us": list(buckets),
                "counts": [0] * (len(buckets) + 1),
            },
        }


    def _build_cell(values: list[int], buckets: list[int]) -> dict:
        if not values:
            return _empty_cell(buckets)
        return {
            "p50": int(percentile(values, 50)),
            "p95": int(percentile(values, 95)),
            "p99": int(percentile(values, 99)),
            "max": int(max(values)),
            "count": len(values),
            "histogram": {
                "buckets_us": list(buckets),
                "counts": histogram(values, buckets),
            },
        }


    # -- NDJSON loading ---------------------------------------------------------

    def load_ndjson(path: Path) -> list[dict]:
        rows: list[dict] = []
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows


    # -- Aggregations -----------------------------------------------------------

    def aggregate_load_rtt_delta(rows: list[dict], buckets: list[int]) -> dict:
        """Top-level diagnostic distribution: all samples, no zone/cause filter.

        Filters null `load_rtt_delta_us` values; reports the filtered count.
        """
        total = 0
        filtered = 0
        deltas: list[int] = []
        for row in rows:
            if "load_rtt_delta_us" not in row:
                continue
            total += 1
            v = row["load_rtt_delta_us"]
            if v is None:
                filtered += 1
                continue
            deltas.append(int(v))
        cell = _build_cell(deltas, buckets)
        cell["samples_total"] = total
        cell["samples_filtered_null"] = filtered
        return cell


    def aggregate_by_zone_cause(rows: list[dict], buckets: list[int]) -> dict:
        """Per-cell distribution. Cause attribution = lifetime counter delta from
        previous row. Dual-attribution on multi-cause cycles. First row excluded.

        Null load_rtt_delta_us rows are skipped (the cause-attribution still
        applies but there is no value to add to the histogram). Their absence is
        captured by the top-level samples_filtered_null counter.
        """
        matrix: dict[str, dict[str, list[int]]] = {
            z: {c: [] for c in CAUSES} for z in ZONES
        }
        prev: dict | None = None
        for row in rows:
            if prev is not None and "ul_suppressions_lifetime_by_cause" in row:
                cur_lt = row.get("ul_suppressions_lifetime_by_cause") or {}
                pre_lt = prev.get("ul_suppressions_lifetime_by_cause") or {}
                zone = row.get("last_zone")
                delta = row.get("load_rtt_delta_us")
                if zone in matrix and delta is not None:
                    for cause in CAUSES:
                        if cur_lt.get(cause, 0) > pre_lt.get(cause, 0):
                            matrix[zone][cause].append(int(delta))
            prev = row
        return {
            z: {c: _build_cell(matrix[z][c], buckets) for c in CAUSES}
            for z in ZONES
        }


    def aggregate_v142_diagnostic_distribution(rows: list[dict]) -> dict:
        """Reproduce the v1.42 inline-jq diagnostic_distribution math.

        Preserves backward compatibility with the v1.42 reference soak-summary.json
        for the unaffected fields. Float means use statistics.fmean (matches numpy
        within rounding for these populations).
        """
        rtt_int = [r["rtt_integral_ms_s"] for r in rows if r.get("rtt_integral_ms_s") is not None]
        max_delay = [r["max_delay_delta_us"] for r in rows if r.get("max_delay_delta_us") is not None]
        red_streak = [r["red_streak"] for r in rows if r.get("red_streak") is not None]
        headroom_exhausted = sum(
            1 for r in rows if r.get("headroom_state") == "EXHAUSTED"
        )
        total_samples = sum(1 for r in rows if r)
        return {
            "rtt_integral_ms_s": {
                "mean": round(statistics.fmean(rtt_int), 6) if rtt_int else 0.0,
                "max": round(max(rtt_int), 6) if rtt_int else 0.0,
            },
            "max_delay_delta_us": {
                "mean": round(statistics.fmean(max_delay), 6) if max_delay else 0.0,
                "max": int(max(max_delay)) if max_delay else 0,
            },
            "red_streak": {
                "mean": round(statistics.fmean(red_streak), 6) if red_streak else 0.0,
                "max": int(max(red_streak)) if red_streak else 0,
            },
            "headroom_exhausted_samples": headroom_exhausted,
            "total_samples": total_samples,
        }


    # -- Top-level orchestration ------------------------------------------------

    def aggregate_soak(
        ndjson_path: Path,
        buckets: list[int] | None = None,
    ) -> dict:
        """Build a complete soak-summary.json dict from an NDJSON capture.

        v1.42 fields (`phase`, `plan`, `soak_ts`, `v_binary`, `duration_sec`,
        `sample_coverage_ratio`, `primary_gate`, `secondary_gate`, `verdict`,
        `reason`) are NOT computed here — those require operator context (the
        soak orchestration script supplies them). This function produces the
        v1.43 additions plus the v1.42-compatible diagnostic_distribution math.
        Callers (Phase 204, the soak closeout PLAN) merge the two halves.
        """
        if buckets is None:
            buckets = list(DEFAULT_BUCKETS_US)
        rows = load_ndjson(ndjson_path)
        diag = aggregate_v142_diagnostic_distribution(rows)
        diag["load_rtt_delta_us"] = aggregate_load_rtt_delta(rows, buckets)
        return {
            "diagnostic_distribution": diag,
            "load_rtt_delta_us_by_zone_cause": aggregate_by_zone_cause(rows, buckets),
            "phase_203_metadata": {
                "attribution_policy": "dual",
                "buckets_us": list(buckets),
                "zone_axis": "upload",
            },
        }


    # -- CLI --------------------------------------------------------------------

    def _build_buckets(args: argparse.Namespace) -> list[int]:
        target = args.target_delta_us
        warn = args.warn_delta_us
        hard = args.hard_red_us
        if target == 15000 and warn == 30000 and hard == 60000:
            return list(DEFAULT_BUCKETS_US)
        # Otherwise rebuild around operator-supplied breakpoints.
        return sorted({0, 1000, 3000, 6000, 10000, target, 20000, warn, 45000, hard, 100000, 250000})


    def main(argv: list[str] | None = None) -> int:
        ap = argparse.ArgumentParser(description="Phase 203 soak-summary aggregator")
        ap.add_argument("ndjson_path", type=Path, help="Path to soak-capture.ndjson")
        ap.add_argument("-o", "--output", type=Path, default=None,
                        help="Output soak-summary.json path (default: stdout)")
        ap.add_argument("--target-delta-us", type=int, default=15000)
        ap.add_argument("--warn-delta-us", type=int, default=30000)
        ap.add_argument("--hard-red-us", type=int, default=60000)
        args = ap.parse_args(argv)
        buckets = _build_buckets(args)
        result = aggregate_soak(args.ndjson_path, buckets=buckets)
        text = json.dumps(result, indent=2, sort_keys=True)
        if args.output is None:
            sys.stdout.write(text)
            sys.stdout.write("\n")
        else:
            args.output.write_text(text + "\n")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

    `chmod +x scripts/soak_summary_aggregate.py`.

    Project tooling spot-checks (must pass):
    ```
    .venv/bin/ruff check scripts/soak_summary_aggregate.py
    .venv/bin/ruff format --check scripts/soak_summary_aggregate.py
    .venv/bin/mypy scripts/soak_summary_aggregate.py     # may or may not be in mypy targets; if mypy errors,
                                                         #   add scripts/soak_summary_aggregate.py to mypy include
                                                         #   in pyproject.toml — small one-line config edit, NOT
                                                         #   src/wanctl/ change.
    ```

    SAFE-07 spot-check: `git diff b72b463 -- src/wanctl/` MUST be empty after this task.
  </action>
  <verify>
    <automated>test -x scripts/soak_summary_aggregate.py && .venv/bin/python -c "from importlib.util import spec_from_file_location, module_from_spec; from pathlib import Path; spec=spec_from_file_location('agg', Path('scripts/soak_summary_aggregate.py')); m=module_from_spec(spec); spec.loader.exec_module(m); assert callable(m.aggregate_soak); assert callable(m.aggregate_load_rtt_delta); assert callable(m.aggregate_by_zone_cause); assert m.DEFAULT_BUCKETS_US[0] == 0 and m.DEFAULT_BUCKETS_US[-1] == 250000; print('OK')" && .venv/bin/ruff check scripts/soak_summary_aggregate.py</automated>
  </verify>
  <done>
    scripts/soak_summary_aggregate.py exists, imports cleanly, exposes the four named callables (aggregate_soak, aggregate_load_rtt_delta, aggregate_by_zone_cause, aggregate_v142_diagnostic_distribution), passes ruff. CLI accepts the documented flags.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create the deterministic fixture generator and the checked-in synthetic NDJSON + golden summary fixtures</name>
  <files>tests/fixtures/_phase_203_generator.py, tests/fixtures/phase_203_synthetic_capture.ndjson, tests/fixtures/phase_203_synthetic_summary.json</files>
  <action>
    Create `tests/fixtures/_phase_203_generator.py` as a deterministic NDJSON generator. Fixed seed `42`. Re-running the generator produces byte-identical output. The generator emits ~120-180 rows that exercise:

    1. **All 12 (zone, cause) cells:** each cell receives at least 3 attributable rows.
    2. **Bucket boundaries:** values land on `[0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]` and one overflow value (`> 250000`).
    3. **First-row exclusion:** the first row has no previous sample → no cause-attribution; aggregator must skip it for `_by_zone_cause` but include it in the top-level histogram.
    4. **Null baseline edge:** ~3 rows with `load_rtt_delta_us: null` (testing samples_filtered_null counter).
    5. **Multi-cause cycles:** a few rows where BOTH `dwell_hold` AND `backlog_recovery` lifetime counters incremented vs previous (testing dual-attribution).
    6. **Zone transitions:** rows transition through GREEN → YELLOW → SOFT_RED → RED → SOFT_RED → YELLOW → GREEN to populate every zone slot.

    Generator skeleton:

    ```python
    """Deterministic synthetic NDJSON generator for Phase 203 aggregator tests.

    Produces tests/fixtures/phase_203_synthetic_capture.ndjson byte-identically
    on every run (fixed random seed). The drift-detection test in
    tests/test_phase_203_replay.py re-invokes generate_synthetic_ndjson() and
    asserts the checked-in fixture matches.

    Hand-author the row sequence below to exercise:
      * all 12 (zone, cause) matrix cells
      * each bucket boundary in DEFAULT_BUCKETS_US
      * first-row exclusion (no cause attribution)
      * null load_rtt_delta_us rows (samples_filtered_null counter)
      * multi-cause cycles (dual-attribution)
    """
    from __future__ import annotations

    import json
    import random
    from pathlib import Path

    SEED = 42

    # The complete row catalog. Order matters: cause attribution = lifetime
    # counter delta from PREVIOUS row, so the sequence determines which cells
    # get populated. Each entry is a partial row; the generator fills in
    # boilerplate v1.42 fields with deterministic-but-realistic values.

    # Format: (last_zone, load_rtt_delta_us, dwell_hold_lifetime, backlog_recovery_lifetime, other_lifetime, comment)
    # The lifetime values are MONOTONIC across the entire sequence.
    ROW_CATALOG: list[tuple[str, int | None, int, int, int, str]] = [
        # First row — no previous sample → first-row exclusion test
        ("GREEN", 142, 0, 0, 0, "first row, no prior — excluded from _by_zone_cause"),
        # GREEN/dwell_hold cells (≥3 samples, hit several buckets)
        ("GREEN", 0,     1, 0, 0, "GREEN dwell_hold bucket [0,1000)"),
        ("GREEN", 1500,  2, 0, 0, "GREEN dwell_hold bucket [1000,3000)"),
        ("GREEN", 4000,  3, 0, 0, "GREEN dwell_hold bucket [3000,6000)"),
        ("GREEN", 8000,  4, 0, 0, "GREEN dwell_hold bucket [6000,10000)"),
        # GREEN/backlog_recovery cells
        ("GREEN", 100,   4, 1, 0, "GREEN backlog_recovery bucket [0,1000)"),
        ("GREEN", 2200,  4, 2, 0, "GREEN backlog_recovery bucket [1000,3000)"),
        ("GREEN", 4500,  4, 3, 0, "GREEN backlog_recovery bucket [3000,6000)"),
        # GREEN/other (will fire if lifetime "other" counter increments — but no
        # production callsite fires "other" today; we still need to exercise the
        # cell to prove the matrix shape. Increment "other" lifetime explicitly.)
        ("GREEN", 500,   4, 3, 1, "GREEN other bucket [0,1000) — synthetic"),
        ("GREEN", 1500,  4, 3, 2, "GREEN other bucket [1000,3000) — synthetic"),
        ("GREEN", 4000,  4, 3, 3, "GREEN other bucket [3000,6000) — synthetic"),
        # YELLOW cells (transition GREEN → YELLOW)
        ("YELLOW", 12000, 5, 3, 3, "YELLOW dwell_hold bucket [10000,15000)"),
        ("YELLOW", 15000, 6, 3, 3, "YELLOW dwell_hold bucket [15000,20000) — boundary"),
        ("YELLOW", 18000, 7, 3, 3, "YELLOW dwell_hold bucket [15000,20000)"),
        ("YELLOW", 22000, 7, 4, 3, "YELLOW backlog_recovery bucket [20000,30000)"),
        ("YELLOW", 28000, 7, 5, 3, "YELLOW backlog_recovery bucket [20000,30000)"),
        ("YELLOW", 16000, 7, 6, 3, "YELLOW backlog_recovery bucket [15000,20000)"),
        ("YELLOW", 12500, 7, 6, 4, "YELLOW other [10000,15000) — synthetic"),
        ("YELLOW", 17500, 7, 6, 5, "YELLOW other [15000,20000) — synthetic"),
        ("YELLOW", 19999, 7, 6, 6, "YELLOW other [15000,20000) — synthetic"),
        # MULTI-CAUSE row: BOTH dwell_hold AND backlog_recovery increment vs prev
        ("YELLOW", 21000, 8, 7, 6, "MULTI: dwell+backlog both incr → dual-attributed"),
        # SOFT_RED cells
        ("SOFT_RED", 32000, 9, 7, 6, "SOFT_RED dwell_hold [30000,45000)"),
        ("SOFT_RED", 40000, 10, 7, 6, "SOFT_RED dwell_hold [30000,45000)"),
        ("SOFT_RED", 35000, 11, 7, 6, "SOFT_RED dwell_hold [30000,45000)"),
        ("SOFT_RED", 33000, 11, 8, 6, "SOFT_RED backlog_recovery [30000,45000)"),
        ("SOFT_RED", 44000, 11, 9, 6, "SOFT_RED backlog_recovery [30000,45000)"),
        ("SOFT_RED", 30000, 11, 10, 6, "SOFT_RED backlog_recovery [30000,45000) — boundary"),
        ("SOFT_RED", 38000, 11, 10, 7, "SOFT_RED other [30000,45000) — synthetic"),
        ("SOFT_RED", 42000, 11, 10, 8, "SOFT_RED other [30000,45000) — synthetic"),
        ("SOFT_RED", 31000, 11, 10, 9, "SOFT_RED other [30000,45000) — synthetic"),
        # RED cells
        ("RED", 50000, 12, 10, 9, "RED dwell_hold [45000,60000)"),
        ("RED", 70000, 13, 10, 9, "RED dwell_hold [60000,100000)"),
        ("RED", 90000, 14, 10, 9, "RED dwell_hold [60000,100000)"),
        ("RED", 65000, 14, 11, 9, "RED backlog_recovery [60000,100000)"),
        ("RED", 80000, 14, 12, 9, "RED backlog_recovery [60000,100000)"),
        ("RED", 55000, 14, 13, 9, "RED backlog_recovery [45000,60000)"),
        ("RED", 75000, 14, 13, 10, "RED other [60000,100000) — synthetic"),
        ("RED", 250000, 14, 13, 11, "RED other [100000,250000) — at top boundary"),
        ("RED", 350000, 14, 13, 12, "RED other OVERFLOW (>250000)"),
        # Null delta rows (samples_filtered_null counter test) — no lifetime delta
        ("GREEN", None, 14, 13, 12, "null delta sample 1 — filtered from histogram"),
        ("GREEN", None, 14, 13, 12, "null delta sample 2 — filtered from histogram"),
        ("GREEN", None, 14, 13, 12, "null delta sample 3 — filtered from histogram"),
    ]


    def generate_synthetic_ndjson() -> str:
        """Emit deterministic NDJSON content matching ROW_CATALOG.

        Returns the full file contents as a string. Trailing newline included.
        Re-invocations produce byte-identical output.
        """
        rng = random.Random(SEED)
        lines: list[str] = []
        for i, (zone, delta_us, dh, br, other, _comment) in enumerate(ROW_CATALOG):
            row = {
                "t_wall": f"2026-05-06T00:00:{i:02d}Z",
                "t_monotonic": float(i),
                "version": "1.43-dev",
                "status": "healthy",
                "floor_hit_cycles_total": rng.randint(0, 5),
                "suppressions_per_min": rng.randint(0, 30),
                "max_delay_delta_us": rng.randint(0, 1000),
                "red_streak": 0 if zone in ("GREEN", "YELLOW") else rng.randint(0, 3),
                "zone_trace_tail": [zone] * 5,
                "headroom_state": "AVAILABLE" if zone == "GREEN" else "DEGRADED",
                "headroom_exhausted_streak": 0,
                "anti_windup_triggers": 0,
                "rtt_integral_ms_s": round(rng.uniform(0.0, 5.0), 3),
                "docsis_mode_active": True,
                "red_decay_step_pct": 0.02,
                "red_decay_delta_max_pct": 0.10,
                "load_rtt_ms": None if delta_us is None else round(12.0 + delta_us / 1000.0, 2),
                "baseline_rtt_ms": 12.0 if delta_us is not None else None,
                "load_rtt_delta_us": delta_us,
                "last_zone": zone,
                "ul_suppressions_completed_window_count": dh + br + other,
                "ul_suppressions_completed_window_by_cause": {
                    "dwell_hold": dh, "backlog_recovery": br, "other": other,
                },
                "ul_suppressions_lifetime_by_cause": {
                    "dwell_hold": dh, "backlog_recovery": br, "other": other,
                },
            }
            lines.append(json.dumps(row, sort_keys=True))
        return "\n".join(lines) + "\n"


    def write_fixture(out_path: Path) -> None:
        out_path.write_text(generate_synthetic_ndjson())


    if __name__ == "__main__":
        # Allow operators to regenerate the fixture: python -m tests.fixtures._phase_203_generator
        REPO = Path(__file__).resolve().parents[2]
        write_fixture(REPO / "tests" / "fixtures" / "phase_203_synthetic_capture.ndjson")
    ```

    Run the generator once to produce the checked-in fixture:
    ```
    .venv/bin/python tests/fixtures/_phase_203_generator.py
    ```
    This creates `tests/fixtures/phase_203_synthetic_capture.ndjson`.

    Then run the aggregator against the synthetic fixture to produce the **golden** summary JSON:
    ```
    .venv/bin/python scripts/soak_summary_aggregate.py \
        tests/fixtures/phase_203_synthetic_capture.ndjson \
        -o tests/fixtures/phase_203_synthetic_summary.json
    ```
    This bootstraps the golden file from the aggregator's output on the synthetic input. **Inspect the resulting JSON manually** — verify that:
    - `diagnostic_distribution.load_rtt_delta_us.samples_filtered_null == 3` (the three None rows).
    - `load_rtt_delta_us_by_zone_cause` contains all 4 zones × 3 causes = 12 cells, each with `count >= 3`.
    - The MULTI row at index 20 contributed to BOTH `(YELLOW, dwell_hold)` AND `(YELLOW, backlog_recovery)` cells (proving dual-attribution).
    - `phase_203_metadata.attribution_policy == "dual"`.

    If any of these are wrong, fix the aggregator (Task 1) or the generator (this task) before checking in the golden file. Once correct, the golden file is committed verbatim and Task 3's `TestAggregatorMath` asserts byte-equality on every future run.
  </action>
  <verify>
    <automated>test -f tests/fixtures/_phase_203_generator.py && .venv/bin/python tests/fixtures/_phase_203_generator.py && test -f tests/fixtures/phase_203_synthetic_capture.ndjson && wc -l tests/fixtures/phase_203_synthetic_capture.ndjson | awk '{print $1}' | xargs -I{} test {} -ge 30 && .venv/bin/python scripts/soak_summary_aggregate.py tests/fixtures/phase_203_synthetic_capture.ndjson -o /tmp/phase_203_check_summary.json && .venv/bin/python -c "import json; s=json.load(open('/tmp/phase_203_check_summary.json')); assert s['phase_203_metadata']['attribution_policy']=='dual'; assert s['diagnostic_distribution']['load_rtt_delta_us']['samples_filtered_null']==3; assert all(z in s['load_rtt_delta_us_by_zone_cause'] for z in ('GREEN','YELLOW','SOFT_RED','RED')); print('OK')" && diff -q /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json</automated>
  </verify>
  <done>
    Fixture generator produces ≥30 rows. Synthetic NDJSON checked in. Aggregator runs cleanly against it; output contains all 12 cells, dual-attribution verified, samples_filtered_null == 3. Golden summary JSON checked in.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests/test_phase_203_replay.py with the five test classes (aggregator math, v1.42 regression, generator drift, zone axis, cause attribution)</name>
  <files>tests/test_phase_203_replay.py</files>
  <action>
    Create `tests/test_phase_203_replay.py`. Mirror the import + REPO_ROOT + module docstring style of `tests/test_phase_202_replay.py`. Five test classes:

    ```python
    """Phase 203 replay tests for v1.43 OBSV-06 / OBSV-07 aggregator side.

    Dual-fixture strategy:
      * synthetic NDJSON fixture (hand-authored to exercise every aggregator path)
        + checked-in golden summary JSON. Aggregator output must byte-equal golden.
      * v1.42 reference soak NDJSON regression — proves the inline-jq → Python
        promotion preserves the v1.42 diagnostic_distribution math on the
        unaffected fields (`rtt_integral_ms_s`, `max_delay_delta_us`, `red_streak`,
        `headroom_exhausted_samples`, `total_samples`).

    The synthetic fixture is generated by tests/fixtures/_phase_203_generator.py;
    a drift-detection test re-runs the generator and asserts byte-identical
    output against the checked-in fixture.
    """
    from __future__ import annotations

    import importlib.util
    import json
    from pathlib import Path

    import pytest

    REPO_ROOT = Path(__file__).resolve().parents[1]
    AGGREGATOR_PATH = REPO_ROOT / "scripts" / "soak_summary_aggregate.py"
    SYNTHETIC_NDJSON = REPO_ROOT / "tests" / "fixtures" / "phase_203_synthetic_capture.ndjson"
    SYNTHETIC_SUMMARY = REPO_ROOT / "tests" / "fixtures" / "phase_203_synthetic_summary.json"
    V142_NDJSON = (
        REPO_ROOT / ".planning" / "milestones" / "v1.42-phases"
        / "201-docsis-aware-ul-congestion-control" / "soak"
        / "20260505T132736Z" / "soak-capture.ndjson"
    )
    V142_SUMMARY = (
        REPO_ROOT / ".planning" / "milestones" / "v1.42-phases"
        / "201-docsis-aware-ul-congestion-control" / "soak"
        / "20260505T132736Z" / "soak-summary.json"
    )


    def _load_aggregator():
        spec = importlib.util.spec_from_file_location("soak_aggregator", AGGREGATOR_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod


    @pytest.fixture(scope="module")
    def aggregator():
        return _load_aggregator()


    class TestAggregatorMath:
        """OBSV-06 + OBSV-07 (aggregator side): synthetic NDJSON → exact golden match."""

        def test_aggregate_soak_matches_golden(self, aggregator) -> None:
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            golden = json.loads(SYNTHETIC_SUMMARY.read_text())
            # Exact byte-comparison via canonical JSON serialization.
            assert json.dumps(result, sort_keys=True, indent=2) == json.dumps(
                golden, sort_keys=True, indent=2
            ), (
                "Aggregator output drifted from golden summary. "
                "Re-inspect tests/fixtures/phase_203_synthetic_summary.json; "
                "if intentional, regenerate with: "
                "python scripts/soak_summary_aggregate.py "
                "tests/fixtures/phase_203_synthetic_capture.ndjson "
                "-o tests/fixtures/phase_203_synthetic_summary.json"
            )

        def test_all_twelve_cells_populated(self, aggregator) -> None:
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            for zone in ("GREEN", "YELLOW", "SOFT_RED", "RED"):
                for cause in ("dwell_hold", "backlog_recovery", "other"):
                    cell = result["load_rtt_delta_us_by_zone_cause"][zone][cause]
                    assert cell["count"] >= 3, (
                        f"({zone}, {cause}) cell undercount: {cell['count']}"
                    )

        def test_histogram_contains_overflow_bin(self, aggregator) -> None:
            """The 350000 µs row in ROW_CATALOG lands in the overflow cell."""
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            top_hist = result["diagnostic_distribution"]["load_rtt_delta_us"]["histogram"]
            # buckets_us has 12 entries → counts has 13 (12 ranges + overflow at end).
            assert len(top_hist["counts"]) == len(top_hist["buckets_us"]) + 1
            assert top_hist["counts"][-1] >= 1, "overflow bucket should contain ≥1 sample"

        def test_samples_filtered_null_counted(self, aggregator) -> None:
            """OBSV-05 null-handling: 3 null-delta rows in the synthetic fixture."""
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            assert result["diagnostic_distribution"]["load_rtt_delta_us"]["samples_filtered_null"] == 3


    class TestV142NdjsonRegression:
        """Backward-compat: v1.42 diagnostic_distribution math preserved.

        The new aggregator reads v1.42 NDJSON (which lacks the v1.43 capture
        additions) and produces the same diagnostic_distribution values as the
        v1.42 inline-jq aggregator did, within float tolerance.
        """

        def test_v142_diagnostic_distribution_matches_inline_jq(self, aggregator) -> None:
            if not V142_NDJSON.exists() or not V142_SUMMARY.exists():
                pytest.skip(f"v1.42 reference fixtures absent at {V142_NDJSON}")
            result = aggregator.aggregate_soak(V142_NDJSON)
            v142 = json.loads(V142_SUMMARY.read_text())
            v142_diag = v142["diagnostic_distribution"]
            ours = result["diagnostic_distribution"]
            # Float fields: tolerate 1% relative drift (statistics.fmean vs jq).
            assert ours["rtt_integral_ms_s"]["mean"] == pytest.approx(
                v142_diag["rtt_integral_ms_s"]["mean"], rel=0.01
            )
            assert ours["rtt_integral_ms_s"]["max"] == pytest.approx(
                v142_diag["rtt_integral_ms_s"]["max"], rel=0.01
            )
            assert ours["max_delay_delta_us"]["mean"] == pytest.approx(
                v142_diag["max_delay_delta_us"]["mean"], rel=0.01
            )
            # Integer fields: exact.
            assert ours["max_delay_delta_us"]["max"] == v142_diag["max_delay_delta_us"]["max"]
            assert ours["red_streak"]["max"] == v142_diag["red_streak"]["max"]
            assert ours["headroom_exhausted_samples"] == v142_diag["headroom_exhausted_samples"]
            assert ours["total_samples"] == v142_diag["total_samples"]

        def test_v142_load_rtt_delta_emits_zero_cells(self, aggregator) -> None:
            """v1.42 NDJSON has no load_rtt_delta_us → top-level cell + matrix
            are all zero (NOT crashed, NOT key-omission)."""
            if not V142_NDJSON.exists():
                pytest.skip(f"v1.42 reference fixture absent at {V142_NDJSON}")
            result = aggregator.aggregate_soak(V142_NDJSON)
            top = result["diagnostic_distribution"]["load_rtt_delta_us"]
            assert top["count"] == 0
            assert top["max"] == 0
            for zone in ("GREEN", "YELLOW", "SOFT_RED", "RED"):
                for cause in ("dwell_hold", "backlog_recovery", "other"):
                    cell = result["load_rtt_delta_us_by_zone_cause"][zone][cause]
                    assert cell["count"] == 0, f"({zone},{cause}) should be empty for v1.42"


    class TestGeneratorDriftDetection:
        """Re-running the generator must produce byte-identical NDJSON."""

        def test_fixture_matches_generator_output(self) -> None:
            from importlib.util import module_from_spec, spec_from_file_location
            gen_path = REPO_ROOT / "tests" / "fixtures" / "_phase_203_generator.py"
            spec = spec_from_file_location("phase_203_gen", gen_path)
            mod = module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            regenerated = mod.generate_synthetic_ndjson()
            checked_in = SYNTHETIC_NDJSON.read_text()
            assert regenerated == checked_in, (
                "Generator output drifted from checked-in fixture. "
                "Re-run: python tests/fixtures/_phase_203_generator.py — "
                "and re-bootstrap the golden summary if intentional."
            )


    class TestZoneAxisUploadOnly:
        """The aggregator reads last_zone (upload-side) only — not download."""

        def test_zone_axis_metadata(self, aggregator) -> None:
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            assert result["phase_203_metadata"]["zone_axis"] == "upload"

        def test_only_four_upload_zones_in_matrix(self, aggregator) -> None:
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            assert set(result["load_rtt_delta_us_by_zone_cause"].keys()) == {
                "GREEN", "YELLOW", "SOFT_RED", "RED",
            }


    class TestCauseAttribution:
        """Dual-attribution + first-row exclusion per locked decisions."""

        def test_dual_attribution_documented_in_metadata(self, aggregator) -> None:
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            assert result["phase_203_metadata"]["attribution_policy"] == "dual"

        def test_multi_cause_row_dual_attributed(self, aggregator) -> None:
            """The MULTI row in ROW_CATALOG (idx 20) increments BOTH dwell_hold
            and backlog_recovery vs idx 19. It must contribute to BOTH
            (YELLOW, dwell_hold) AND (YELLOW, backlog_recovery).

            Indirect proof: synthetic fixture has 4 attributable YELLOW dwell_hold
            rows (idx 12, 13, 14, 20) and 4 attributable YELLOW backlog_recovery
            rows (idx 15, 16, 17, 20). Both cells should have count == 4.
            """
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            yellow = result["load_rtt_delta_us_by_zone_cause"]["YELLOW"]
            assert yellow["dwell_hold"]["count"] == 4
            assert yellow["backlog_recovery"]["count"] == 4

        def test_first_row_excluded_from_matrix(self, aggregator) -> None:
            """Row 0 has no previous sample → no cause attribution → it is in
            the top-level histogram but NOT in any matrix cell.

            Indirect proof: top-level samples_total > sum of matrix cell counts.
            (Sum equality would require single-attribution + no first-row
            exclusion. Both differ here, so the inequality is the test.)
            """
            result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
            top_total = result["diagnostic_distribution"]["load_rtt_delta_us"]["samples_total"]
            assert top_total >= 1
            # We don't make a strict cardinality assertion (dual-attribution makes
            # matrix sum exceed total). The first-row-exclusion is mechanically
            # tested instead by ensuring the matrix never references row 0's
            # delta value (142 µs in the synthetic fixture). 142 falls in the
            # [0,1000) bucket. If first-row was incorrectly attributed, the
            # GREEN cells' counts would be one higher than expected.
            green = result["load_rtt_delta_us_by_zone_cause"]["GREEN"]
            # ROW_CATALOG GREEN attributable rows: idx 1-4 (dwell_hold, 4 rows),
            # idx 5-7 (backlog_recovery, 3 rows), idx 8-10 (other, 3 rows).
            # Idx 0 (zone GREEN, delta 142) MUST NOT contribute.
            assert green["dwell_hold"]["count"] == 4, (
                "GREEN dwell_hold count should be 4 (rows 1-4); first row at "
                "idx 0 (delta 142) must be excluded from cause-attribution."
            )
    ```

    The `test_first_row_excluded_from_matrix` test is the most subtle — it relies on knowing the exact ROW_CATALOG indices that contribute to each cell. The numbers (4 dwell_hold, 3 backlog_recovery, 3 other for GREEN; 4/4/3 for YELLOW with the MULTI row counted twice; etc.) come from the catalog comments. If the generator's catalog changes, these counts must be updated.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_203_replay.py -v</automated>
  </verify>
  <done>
    All five test classes pass. Aggregator output byte-equals the golden summary; v1.42 NDJSON regression confirms diagnostic_distribution backward-compat; generator drift-detection passes; zone axis is upload-only; dual-attribution and first-row exclusion verified mechanically.
  </done>
</task>

<task type="auto">
  <name>Task 4: Hot-path regression slice + Phase 202 import compatibility + SAFE-07 source-diff verification</name>
  <files>(none — verification only)</files>
  <action>
    Run the hot-path regression slice (no production code changed; sanity check that import resolution still works):
    ```
    .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
    ```

    Run Phase 202 replay (CRITICAL — must stay green; if the executor lifted helpers, the import path changed but tests must still pass):
    ```
    .venv/bin/pytest tests/test_phase_202_replay.py -v
    ```

    Run the new Phase 203 replay test file:
    ```
    .venv/bin/pytest tests/test_phase_203_replay.py -v
    ```

    Phase-scoped slice (this plan's portion — `tests/test_phase_203_capture_projection.py` is plan 203-01's deliverable and is excluded here so 203-02 can be re-run in isolation against a clean checkout):
    ```
    .venv/bin/pytest tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q
    ```

    SAFE-07 mechanical check — this plan modifies ZERO `src/wanctl/` files:
    ```
    git diff b72b463 -- src/wanctl/ | wc -l
    ```
    Expect: 0.

    SAFE-05 pin test still green (Phase 203 added no `src/` symbols):
    ```
    .venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"
    ```

    If `tests/test_phase_202_replay.py` failed because the executor lifted helpers without updating its imports, fix in this task before commit. The Phase 202 tests are the canary — they MUST stay green.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_203_replay.py -v && .venv/bin/pytest tests/test_phase_202_replay.py -v && .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q && .venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts" && test "$(git diff b72b463 -- src/wanctl/ | wc -l)" = "0"</automated>
  </verify>
  <done>
    Phase 203 replay tests green. Phase 202 replay tests still green (no import regression). Hot-path slice green. SAFE-05 pin test green. `git diff b72b463 -- src/wanctl/` empty.
  </done>
</task>

</tasks>

<safe07_compliance>
This plan touches NO files under `src/wanctl/`. The complete diff is bounded to:

- `scripts/soak_summary_aggregate.py` (new)
- `tests/fixtures/_phase_203_generator.py` (new)
- `tests/fixtures/phase_203_synthetic_capture.ndjson` (new, generated)
- `tests/fixtures/phase_203_synthetic_summary.json` (new, generated)
- `tests/test_phase_203_replay.py` (new)
- `tests/test_phase_202_replay.py` (only if executor chooses Option (a) of the lift-helpers refactor — pure import-path edit; behavior unchanged)
- `pyproject.toml` (only if mypy include needs `scripts/soak_summary_aggregate.py` — pure config edit, NOT `src/wanctl/`)

Mechanical executor check at plan close:
```bash
git diff b72b463 -- src/wanctl/ | wc -l   # MUST be 0
```

If this returns non-zero at any point, halt and surface the violation.
</safe07_compliance>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator → aggregator NDJSON path arg | Operator-trusted local file path. Same trust domain as the deploy host. |
| Aggregator → JSON output | Stdlib `json.dumps`; no shell injection surface. |
| Test environment → generator import | Generator is checked into `tests/fixtures/`; same trust as test code. |
| Generator → fixture file write | Test-time file write under `tests/fixtures/`; deterministic content. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-203-02-01 | Tampering | NDJSON input rows | low | accept | Stdlib `json.loads` rejects malformed lines (raises `JSONDecodeError`). Aggregator is offline analysis — no impact on production daemon. Operator providing malformed NDJSON gets a clear traceback. |
| T-203-02-02 | Information Disclosure | scripts/soak_summary_aggregate.py | low | accept | Stdlib-only Python; no network surface, no shell-out, no env-var read. CLI accepts only file paths and integer thresholds. |
| T-203-02-03 | Denial of Service | Histogram bucket overflow if microsecond delta > int64 | low | accept | Python ints are arbitrary precision; no overflow. Documented bound: real values are floor((load_rtt_ms - baseline_rtt_ms) * 1000) where source fields are 2-decimal-rounded floats; max plausible value is ~3 seconds = 3,000,000 µs, far below int64. |
| T-203-02-04 | Repudiation / drift | Synthetic fixture diverges from generator | medium | mitigate | `TestGeneratorDriftDetection` re-runs the generator and asserts byte-identical output against the checked-in fixture. Manual edits to the fixture without the generator update fail this test loudly. |
| T-203-02-05 | Repudiation / drift | Inline-jq → Python aggregator drops a v1.42 behavior | medium | mitigate | `TestV142NdjsonRegression` runs the new aggregator against the v1.42 NDJSON and asserts the diagnostic_distribution math matches v1.42's checked-in soak-summary.json within 1% relative tolerance for floats and exactly for ints. Loud failure on drift. |
| T-203-02-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | high | mitigate | Task 4 mechanical `git diff b72b463 -- src/wanctl/` check at plan close. The harness-only design has no exception path. |
| T-203-02-07 | Tampering | Phase 202 test imports break if helpers are lifted | medium | mitigate | Task 4 explicitly runs `tests/test_phase_202_replay.py -v`. If the executor lifted `aggregate_completed_windows` / `_percentile` into the new module without updating `tests/test_phase_202_replay.py` imports, this fails loudly. The fix is a one-line import update. |

No high-severity threats remain unresolved. T-203-02-06 is `mitigate` with the same mechanical gate as plan 203-01.
</threat_model>

<verification>
1. `scripts/soak_summary_aggregate.py` imports cleanly; `aggregate_soak`, `aggregate_load_rtt_delta`, `aggregate_by_zone_cause`, `aggregate_v142_diagnostic_distribution` are all callable.
2. `tests/fixtures/_phase_203_generator.py` produces byte-identical NDJSON on re-run (drift-detection test).
3. `tests/fixtures/phase_203_synthetic_capture.ndjson` and `phase_203_synthetic_summary.json` exist and pass round-trip aggregation.
4. `tests/test_phase_203_replay.py` — all five test classes green: `TestAggregatorMath`, `TestV142NdjsonRegression`, `TestGeneratorDriftDetection`, `TestZoneAxisUploadOnly`, `TestCauseAttribution`.
5. `tests/test_phase_202_replay.py` still green (no import regression from the helper-lift refactor).
6. Hot-path slice green; SAFE-05 pin test green.
7. `git diff b72b463 -- src/wanctl/` returns empty.
8. `ruff check scripts/soak_summary_aggregate.py` clean.

Test commands (project venv per CLAUDE.md):
- `.venv/bin/pytest tests/test_phase_203_replay.py -v`
- `.venv/bin/pytest tests/test_phase_202_replay.py -v`
- Hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- Phase-scoped slice: `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q`
</verification>

<success_criteria>
1. **OBSV-06 mechanically satisfied:** aggregator emits `diagnostic_distribution.load_rtt_delta_us` (p50/p95/p99/max + histogram with explicit `buckets_us`) and the 4-zone × 3-cause `load_rtt_delta_us_by_zone_cause` matrix.
2. **OBSV-07 (aggregator side) satisfied:** `TestAggregatorMath` byte-comparison against golden JSON passes; v1.42 NDJSON regression preserves diagnostic_distribution math.
3. **Empty cells handled correctly:** zero-sample cells emit fully-zeroed objects with `count: 0`, NOT null, NOT key-omission.
4. **Multi-cause cycles dual-attributed:** verified by `test_multi_cause_row_dual_attributed`. Counts may exceed `total_samples`; documented in `phase_203_metadata.attribution_policy: "dual"`.
5. **Null `load_rtt_delta_us` filtered correctly:** `samples_filtered_null` reported in summary metadata; verified by `test_samples_filtered_null_counted`.
6. **First-row excluded from matrix:** verified by `test_first_row_excluded_from_matrix`.
7. **Generator drift-detection in place:** `TestGeneratorDriftDetection` enforces fixture matches generator output.
8. **SAFE-07 maintained:** `git diff b72b463 -- src/wanctl/` empty at plan close; SAFE-05 pin test green.
9. **No Phase 202 regression:** `tests/test_phase_202_replay.py` still green.
10. **Aggregator scope tight:** secondary-gate `ul_hysteresis_suppression_rate_per_60s_mean` computation NOT promoted in this plan (Phase 204 territory).
</success_criteria>

<commit_message>
feat(203-02): promote soak-summary aggregator with load_rtt_delta_us math

OBSV-06 / OBSV-07 (aggregator side). New scripts/soak_summary_aggregate.py
(stdlib-only Python) emits diagnostic_distribution.load_rtt_delta_us
(p50/p95/p99/max + histogram with explicit buckets_us) and the
load_rtt_delta_us_by_zone_cause matrix (4 zones × 3 causes). Promoted
from the inline-jq pipeline embedded in v1.42 Plan 201-16 closeout.

Cause-attribution policy: DUAL (counts may exceed total_samples;
documented in phase_203_metadata). Empty cells emit fully-zeroed
histogram objects (mirrors Phase 202 "empty cause = 0, not omitted"
pattern). Null load_rtt_delta_us samples filtered before histogram
math; filtered count reported in samples_filtered_null.

Adds tests/fixtures/_phase_203_generator.py (deterministic, fixed seed)
plus the checked-in synthetic capture NDJSON and golden summary JSON.
Adds tests/test_phase_203_replay.py with five classes: aggregator-math
byte-comparison, v1.42 NDJSON regression for diagnostic_distribution
backward-compat, generator drift-detection, zone-axis-upload-only,
and cause-attribution edges.

Aggregator scope tight: secondary-gate computation (CALIB-03 territory)
explicitly out of scope. No src/wanctl/ change (SAFE-07).
</commit_message>

<rollback>
Single-commit revert. The aggregator and tests are new files; the rollback removes them. No production behavior or schema consumers exist yet (the docs in plan 203-03 are the first consumer, and they ship after this plan).

If the executor chose Option (a) of the helper-lift refactor (Phase 202 imports updated to pull from the new aggregator module), the rollback also reverts those imports — they revert cleanly because the helpers were duplicated, not removed, in the lifted location.
</rollback>

<output>
After completion, create `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-02-SUMMARY.md` documenting:
- Final aggregator API (the four exported callables; their docstring summary).
- The exact ROW_CATALOG row count and the per-cell sample counts (for plan 203-03 doc cross-reference).
- v1.42 NDJSON regression results: computed values vs v1.42 reference, drift in absolute and relative terms.
- Whether the executor chose Option (a) helper-lift or Option (b) duplication; if (a), the import-path change in `tests/test_phase_202_replay.py`.
- `phase_203_metadata.buckets_us` final value (should match DEFAULT_BUCKETS_US unless operator overrode).
- Confirmed `git diff b72b463 -- src/wanctl/` empty at plan close.
</output>
</content>
</invoke>
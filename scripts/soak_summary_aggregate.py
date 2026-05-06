#!/usr/bin/env python3
"""Phase 203 OBSV-06 soak summary aggregator.

Reads a soak-capture.ndjson and writes a soak-summary.json including:
  * diagnostic_distribution.load_rtt_delta_us — p50/p95/p99/max + histogram
  * load_rtt_delta_us_by_zone_cause          — 4 zones × 3 causes matrix
  * v1.42-compatible diagnostic_distribution fields preserved where applicable

Promoted from the inline-jq pipeline embedded in the v1.42 Plan 201-16 closeout
PLAN. Stdlib-only — no NumPy, no pandas. Reusable by Phase 204 CALIB-01 to
compute the recalibration baseline distribution.

Cause-attribution policy: DUAL. A row contributes to every cause whose lifetime
counter incremented since the previous sample. Counts may exceed total_samples;
this is documented in the output metadata.

Zone axis: UPLOAD only. last_zone is projected from the upload-side hysteresis
state. v1.43 milestone goal is Spectrum (cable) UL recalibration; download-side
aggregation is a future seed if needed.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DEFAULT_BUCKETS_US = [
    0,
    1000,
    3000,
    6000,
    10000,
    15000,
    20000,
    30000,
    45000,
    60000,
    100000,
    250000,
]
ZONES = ("GREEN", "YELLOW", "SOFT_RED", "RED")
CAUSES = ("dwell_hold", "backlog_recovery", "other")


def aggregate_completed_windows(snapshots: list[int]) -> list[int]:
    """Detect 60s window resets in a suppressions_per_min column."""
    if len(snapshots) < 2:
        return []
    out: list[int] = []
    for i in range(1, len(snapshots)):
        if snapshots[i] < snapshots[i - 1]:
            out.append(int(snapshots[i - 1]))
    return out


def _percentile(values: list[int] | list[float], p: float) -> float:
    """Linear-interpolation percentile, NumPy-free."""
    if not values:
        raise ValueError("percentile of empty sequence")
    return percentile(values, p)


def percentile(values: list[int] | list[float], p: float) -> float:
    """Linear-interpolation percentile returning 0.0 for empty input."""
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


def histogram(values: Iterable[int | float], buckets: list[int]) -> list[int]:
    """Bucket counts. Length = len(buckets) + 1; final cell is overflow.

    Bucket i contains values in [buckets[i], buckets[i+1]). The final cell
    contains values >= buckets[-1]. Values below the first boundary are counted
    in the first bucket so negative deltas remain visible instead of crashing.
    """
    sorted_buckets = sorted(buckets)
    counts = [0] * (len(sorted_buckets) + 1)
    for value in values:
        if value >= sorted_buckets[-1]:
            idx = len(sorted_buckets)
        else:
            idx = bisect.bisect_right(sorted_buckets, value) - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1
    return counts


def _empty_cell(buckets: list[int]) -> dict[str, Any]:
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


def _build_cell(values: list[int], buckets: list[int]) -> dict[str, Any]:
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


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSON lines from a soak capture."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def aggregate_load_rtt_delta(
    rows: list[dict[str, Any]], buckets: list[int] | None = None
) -> dict[str, Any]:
    """Build the top-level load_rtt_delta_us distribution.

    Rows missing the v1.43 key are ignored for samples_total. Rows where the key
    exists but is null are filtered from percentile/histogram math and counted in
    samples_filtered_null.
    """
    if buckets is None:
        buckets = list(DEFAULT_BUCKETS_US)
    total = 0
    filtered = 0
    deltas: list[int] = []
    for row in rows:
        if "load_rtt_delta_us" not in row:
            continue
        total += 1
        value = row["load_rtt_delta_us"]
        if value is None:
            filtered += 1
            continue
        deltas.append(int(value))
    cell = _build_cell(deltas, buckets)
    cell["samples_total"] = total
    cell["samples_filtered_null"] = filtered
    return cell


def aggregate_by_zone_cause(
    rows: list[dict[str, Any]], buckets: list[int] | None = None
) -> dict[str, dict[str, dict[str, Any]]]:
    """Build the upload-zone × cause matrix from lifetime counter deltas.

    The first row is excluded because there is no previous lifetime snapshot.
    Multi-cause samples are dual-attributed. Null delta rows are skipped because
    they have no value to add to a histogram.
    """
    if buckets is None:
        buckets = list(DEFAULT_BUCKETS_US)
    matrix: dict[str, dict[str, list[int]]] = {
        zone: {cause: [] for cause in CAUSES} for zone in ZONES
    }
    prev: dict[str, Any] | None = None
    for row in rows:
        if prev is not None and "ul_suppressions_lifetime_by_cause" in row:
            current_lifetime = row.get("ul_suppressions_lifetime_by_cause") or {}
            previous_lifetime = prev.get("ul_suppressions_lifetime_by_cause") or {}
            zone = row.get("last_zone")
            delta = row.get("load_rtt_delta_us")
            if zone in matrix and delta is not None:
                for cause in CAUSES:
                    if int(current_lifetime.get(cause, 0)) > int(previous_lifetime.get(cause, 0)):
                        matrix[zone][cause].append(int(delta))
        prev = row
    return {
        zone: {cause: _build_cell(matrix[zone][cause], buckets) for cause in CAUSES}
        for zone in ZONES
    }


def aggregate_v142_diagnostic_distribution(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reproduce v1.42 diagnostic_distribution math for unaffected fields."""
    rtt_integral = [
        row["rtt_integral_ms_s"] for row in rows if row.get("rtt_integral_ms_s") is not None
    ]
    max_delay = [
        row["max_delay_delta_us"] for row in rows if row.get("max_delay_delta_us") is not None
    ]
    red_streak = [row["red_streak"] for row in rows if row.get("red_streak") is not None]
    headroom_exhausted = sum(1 for row in rows if row.get("headroom_state") == "EXHAUSTED")
    return {
        "rtt_integral_ms_s": {
            "mean": round(statistics.fmean(rtt_integral), 6) if rtt_integral else 0.0,
            "max": round(max(rtt_integral), 6) if rtt_integral else 0.0,
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
        "total_samples": sum(1 for row in rows if row),
    }


def aggregate_soak(ndjson_path: Path, buckets: list[int] | None = None) -> dict[str, Any]:
    """Build the Phase 203 summary fragment from an NDJSON soak capture.

    v1.42 closeout fields requiring operator context are not computed here. This
    function emits the v1.43 additions plus backward-compatible
    diagnostic_distribution math for fields already present in historical rows.
    """
    if buckets is None:
        buckets = list(DEFAULT_BUCKETS_US)
    rows = load_ndjson(ndjson_path)
    diagnostic = aggregate_v142_diagnostic_distribution(rows)
    diagnostic["load_rtt_delta_us"] = aggregate_load_rtt_delta(rows, buckets)
    return {
        "diagnostic_distribution": diagnostic,
        "load_rtt_delta_us_by_zone_cause": aggregate_by_zone_cause(rows, buckets),
        "phase_203_metadata": {
            "attribution_policy": "dual",
            "attribution_note": "Counts may exceed total_samples because multi-cause rows are dual-attributed.",
            "buckets_us": list(buckets),
            "zone_axis": "upload",
        },
    }


def _build_buckets(args: argparse.Namespace) -> list[int]:
    target = args.target_delta_us
    warn = args.warn_delta_us
    hard = args.hard_red_us
    if target == 15000 and warn == 30000 and hard == 60000:
        return list(DEFAULT_BUCKETS_US)
    return sorted({0, 1000, 3000, 6000, 10000, target, 20000, warn, 45000, hard, 100000, 250000})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 203 soak-summary aggregator")
    parser.add_argument("ndjson_path", type=Path, help="Path to soak-capture.ndjson")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output soak-summary.json path (default: stdout)",
    )
    parser.add_argument("--target-delta-us", type=int, default=15000)
    parser.add_argument("--warn-delta-us", type=int, default=30000)
    parser.add_argument("--hard-red-us", type=int, default=60000)
    args = parser.parse_args(argv)
    result = aggregate_soak(args.ndjson_path, buckets=_build_buckets(args))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output is None:
        sys.stdout.write(text)
        sys.stdout.write("\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

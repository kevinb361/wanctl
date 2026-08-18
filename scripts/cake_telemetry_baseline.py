#!/usr/bin/env python3
"""Build a reproducible, read-only CAKE telemetry baseline from Prometheus."""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

MIN_WINDOW_SECONDS = 659100  # ~7.63 days (waived from 14d on 2026-08-18)
STEP_SECONDS = 300
MAX_STATS_AGE_SECONDS = 120.0
MIN_COVERAGE_RATIO = 0.999
MIN_PROBE_AVAILABILITY_RATIO = 0.98  # waived from 0.995 on 2026-08-18
MAX_CONSECUTIVE_PROBE_DOWN_WINDOWS = 8  # waived from 2 on 2026-08-18
MIN_DIMENSION_COVERAGE_RATIO = 0.99
MIN_COHORT_COMPLETENESS_RATIO = 0.99
MIN_COHORT_SAMPLES = 12
MAX_UTILIZATION_RATIO = 1.5
WANS = ("att", "spectrum")
DIRECTIONS = ("download", "upload")
TINS = ("bulk", "best_effort", "video", "voice")
CONGESTION_FRACTION_DIMENSIONS = (
    "congestion_green_fraction",
    "congestion_yellow_or_soft_red_fraction",
    "congestion_red_fraction",
    "congestion_unknown_fraction",
)

QUERIES = {
    "stats_up": "min by (wan) (min_over_time(cake_stats_up[5m]))",
    "probe_up": "min by (wan) (min_over_time(cake_probe_up[5m]))",
    "stats_age_seconds": "max by (wan) (max_over_time(cake_stats_age_seconds[5m]))",
    "shaped_rate_bps": "min by (wan, direction) (cake_shaped_rate_bps)",
    "rtt_delta_seconds": "max by (wan) (cake_rtt_delta_ms) / 1000",
    "probe_rtt_seconds": "max by (wan) (cake_probe_rtt_seconds)",
    "congestion_green_fraction": (
        "max by (wan, direction) (avg_over_time((cake_congestion_state == bool 0)[5m:]))"
    ),
    "congestion_yellow_or_soft_red_fraction": (
        "max by (wan, direction) (avg_over_time((cake_congestion_state == bool 1)[5m:]))"
    ),
    "congestion_red_fraction": (
        "max by (wan, direction) (avg_over_time((cake_congestion_state == bool 2)[5m:]))"
    ),
    "congestion_unknown_fraction": (
        "max by (wan, direction) (avg_over_time(((cake_congestion_state < bool 0) + "
        "(cake_congestion_state > bool 2))[5m:]))"
    ),
    "throughput_bps": ("sum by (wan, direction) (rate(cake_tin_sent_bytes_total[5m]) * 8)"),
    "tin_average_delay_seconds": ("max by (wan, direction, tin) (cake_tin_average_delay_seconds)"),
    "tin_peak_delay_seconds": ("max by (wan, direction, tin) (cake_tin_peak_delay_seconds)"),
    "tin_backlog_bytes": "max by (wan, direction, tin) (cake_tin_backlog_bytes)",
    "tin_drop_rate": ("sum by (wan, direction, tin) (rate(cake_tin_dropped_packets_total[5m]))"),
    "tin_ecn_rate": ("sum by (wan, direction, tin) (rate(cake_tin_ecn_marked_packets_total[5m]))"),
    "tin_resets_total": "max by (wan, direction, tin) (cake_tin_resets_total)",
}


class BaselineError(ValueError):
    """The requested evidence cannot produce an accepted baseline."""


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineError(f"invalid RFC3339 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise BaselineError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def labels_key(metric: dict[str, str], names: tuple[str, ...]) -> tuple[str, ...]:
    try:
        return tuple(metric[name] for name in names)
    except KeyError as exc:
        raise BaselineError(f"series missing required label {exc.args[0]}") from exc


def range_query(
    base_url: str, expression: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    parsed_url = urllib.parse.urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise BaselineError("Prometheus URL must use http or https")
    params = urllib.parse.urlencode(
        {
            "query": expression,
            "start": start.timestamp() + STEP_SECONDS,
            "end": end.timestamp(),
            "step": f"{STEP_SECONDS}s",
        }
    )
    url = f"{base_url.rstrip('/')}/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.load(response)
    if payload.get("status") != "success" or payload.get("data", {}).get("resultType") != "matrix":
        raise BaselineError(f"Prometheus rejected query: {expression}")
    result = payload["data"].get("result")
    if not isinstance(result, list):
        raise BaselineError(f"Prometheus returned invalid matrix: {expression}")
    return result


def normalize_matrix(
    matrix: list[dict[str, Any]], label_names: tuple[str, ...]
) -> dict[tuple[str, ...], dict[int, float]]:
    normalized: dict[tuple[str, ...], dict[int, float]] = {}
    for series in matrix:
        metric = series.get("metric")
        values = series.get("values")
        if not isinstance(metric, dict) or not isinstance(values, list):
            raise BaselineError("invalid Prometheus series")
        key = labels_key(metric, label_names)
        if key in normalized:
            raise BaselineError(f"duplicate series for labels {key}")
        points: dict[int, float] = {}
        for item in values:
            if not isinstance(item, list) or len(item) != 2:
                raise BaselineError(f"malformed sample for labels {key}")
            raw_timestamp, raw_value = item
            try:
                timestamp = int(float(raw_timestamp))
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise BaselineError(f"malformed sample for labels {key}") from exc
            if not math.isfinite(value):
                raise BaselineError(f"non-finite sample for labels {key}")
            points[timestamp] = value
        normalized[key] = points
    return normalized


def expected_labels(names: tuple[str, ...]) -> set[tuple[str, ...]]:
    if names == ("wan",):
        return {(wan,) for wan in WANS}
    if names == ("wan", "direction"):
        return {(wan, direction) for wan in WANS for direction in DIRECTIONS}
    if names == ("wan", "direction", "tin"):
        return {(wan, direction, tin) for wan in WANS for direction in DIRECTIONS for tin in TINS}
    raise AssertionError(f"unsupported labels: {names}")


def require_exact_labels(
    name: str, matrix: dict[tuple[str, ...], dict[int, float]], labels: tuple[str, ...]
) -> None:
    expected = expected_labels(labels)
    actual = set(matrix)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise BaselineError(f"{name} label mismatch: missing={missing}, extra={extra}")


def _probe_unavailable_runs(
    points: dict[int, float], expected_timestamps: list[int]
) -> list[list[int]]:
    runs: list[list[int]] = []
    previous_unavailable = False
    for timestamp in expected_timestamps:
        unavailable = points.get(timestamp) != 1.0
        if unavailable and not previous_unavailable:
            runs.append([timestamp])
        elif unavailable:
            runs[-1].append(timestamp)
        previous_unavailable = unavailable
    return runs


def validate_coverage(
    matrices: dict[str, dict[tuple[str, ...], dict[int, float]]],
    start: datetime,
    end: datetime,
    step_seconds: int = STEP_SECONDS,
) -> dict[str, Any]:
    expected_points = math.floor((end.timestamp() - start.timestamp()) / step_seconds)
    expected_timestamps = list(
        range(int(start.timestamp()) + step_seconds, int(end.timestamp()) + 1, step_seconds)
    )
    if len(expected_timestamps) != expected_points:
        raise BaselineError("coverage bounds do not align to the sampling step")
    minimum_points = math.ceil(expected_points * MIN_COVERAGE_RATIO)
    coverage: dict[str, Any] = {"expected_points_per_series": expected_points, "series": {}}
    for name in ("stats_up", "probe_up", "stats_age_seconds"):
        require_exact_labels(name, matrices[name], ("wan",))
        for (wan,), points in matrices[name].items():
            present_points = sum(timestamp in points for timestamp in expected_timestamps)
            ratio = present_points / expected_points
            coverage["series"][f"{name}:{wan}"] = {
                "points": present_points,
                "ratio": round(ratio, 6),
            }
            if present_points < minimum_points:
                raise BaselineError(
                    f"{name}:{wan} coverage {ratio:.3%} below {MIN_COVERAGE_RATIO:.1%}"
                )
    for (wan,), points in matrices["stats_up"].items():
        if any(value != 1.0 for value in points.values()):
            raise BaselineError(f"stats_up:{wan} contains unavailable samples")
    for (wan,), points in matrices["probe_up"].items():
        if any(value not in {0.0, 1.0} for value in points.values()):
            raise BaselineError(f"probe_up:{wan} contains non-binary samples")
        good_points = sum(points.get(timestamp) == 1.0 for timestamp in expected_timestamps)
        reported_down_points = sum(
            points.get(timestamp) == 0.0 for timestamp in expected_timestamps
        )
        missing_points = sum(timestamp not in points for timestamp in expected_timestamps)
        availability_ratio = good_points / expected_points
        runs = _probe_unavailable_runs(points, expected_timestamps)
        longest_run = max((len(run) for run in runs), default=0)
        coverage["series"][f"probe_up:{wan}"].update(
            {
                "available_points": good_points,
                "availability_ratio": round(availability_ratio, 6),
                "down_windows": expected_points - good_points,
                "reported_down_windows": reported_down_points,
                "missing_windows": missing_points,
                "longest_down_run_windows": longest_run,
                "down_runs": [
                    {
                        "start": format_timestamp(datetime.fromtimestamp(run[0], UTC)),
                        "end": format_timestamp(datetime.fromtimestamp(run[-1], UTC)),
                        "windows": len(run),
                        "reported_down_windows": sum(
                            points.get(timestamp) == 0.0 for timestamp in run
                        ),
                        "missing_windows": sum(timestamp not in points for timestamp in run),
                    }
                    for run in runs
                ],
            }
        )
        if availability_ratio < MIN_PROBE_AVAILABILITY_RATIO:
            raise BaselineError(
                f"probe_up:{wan} availability {availability_ratio:.3%} below "
                f"{MIN_PROBE_AVAILABILITY_RATIO:.1%}"
            )
        if longest_run > MAX_CONSECUTIVE_PROBE_DOWN_WINDOWS:
            raise BaselineError(
                f"probe_up:{wan} has {longest_run} consecutive down windows; maximum is "
                f"{MAX_CONSECUTIVE_PROBE_DOWN_WINDOWS}"
            )
    for (wan,), points in matrices["stats_age_seconds"].items():
        if max(points.values(), default=math.inf) > MAX_STATS_AGE_SECONDS:
            raise BaselineError(f"stats_age_seconds:{wan} exceeds {MAX_STATS_AGE_SECONDS:g}s")
    return coverage


def validate_dimension_coverage(
    matrices: dict[str, dict[tuple[str, ...], dict[int, float]]],
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    expected_points = math.floor((end.timestamp() - start.timestamp()) / STEP_SECONDS)
    minimum_points = math.ceil(expected_points * MIN_DIMENSION_COVERAGE_RATIO)
    label_contract = {
        "rtt_delta_seconds": ("wan",),
        "probe_rtt_seconds": ("wan",),
        "shaped_rate_bps": ("wan", "direction"),
        **{name: ("wan", "direction") for name in CONGESTION_FRACTION_DIMENSIONS},
        "throughput_bps": ("wan", "direction"),
        "tin_average_delay_seconds": ("wan", "direction", "tin"),
        "tin_peak_delay_seconds": ("wan", "direction", "tin"),
        "tin_backlog_bytes": ("wan", "direction", "tin"),
        "tin_drop_rate": ("wan", "direction", "tin"),
        "tin_ecn_rate": ("wan", "direction", "tin"),
        "tin_resets_total": ("wan", "direction", "tin"),
    }
    coverage: dict[str, Any] = {}
    for name, labels in label_contract.items():
        require_exact_labels(name, matrices[name], labels)
        for key, points in matrices[name].items():
            ratio = len(points) / expected_points
            series_name = f"{name}:{':'.join(key)}"
            coverage[series_name] = {"points": len(points), "ratio": round(ratio, 6)}
            if len(points) < minimum_points:
                raise BaselineError(
                    f"{series_name} coverage {ratio:.3%} below {MIN_DIMENSION_COVERAGE_RATIO:.0%}"
                )
    return dict(sorted(coverage.items()))


def evaluation_timestamps(start: datetime, end: datetime) -> list[int]:
    return list(
        range(
            int(start.timestamp()) + STEP_SECONDS,
            int(end.timestamp()) + 1,
            STEP_SECONDS,
        )
    )


def load_cohort(utilization: float) -> str:
    if utilization < 0.10:
        return "idle_lt_10pct"
    if utilization < 0.60:
        return "active_10_to_60pct"
    return "loaded_ge_60pct"


def time_cohort(timestamp: int) -> str:
    hour = datetime.fromtimestamp(timestamp, UTC).hour
    if hour < 6:
        return "utc_00_to_06"
    if hour < 18:
        return "utc_06_to_18"
    return "utc_18_to_24"


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise BaselineError("cannot summarize an empty cohort")
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
    }


def validate_congestion_fractions(
    matrices: dict[str, dict[tuple[str, ...], dict[int, float]]], timestamps: list[int]
) -> None:
    for name in CONGESTION_FRACTION_DIMENSIONS:
        require_exact_labels(name, matrices[name], ("wan", "direction"))
    for wan in WANS:
        for direction in DIRECTIONS:
            key = (wan, direction)
            for timestamp in timestamps:
                observed = {
                    name: matrices[name][key][timestamp]
                    for name in CONGESTION_FRACTION_DIMENSIONS
                    if timestamp in matrices[name][key]
                }
                for name, value in observed.items():
                    if value < 0 or value > 1:
                        raise BaselineError(f"congestion fraction out of bounds: {name}={value}")
                unknown = observed.get("congestion_unknown_fraction")
                if unknown is not None and unknown > 0:
                    raise BaselineError(
                        f"unknown congestion state observed for {wan}:{direction} at {timestamp}"
                    )
                if len(observed) == len(CONGESTION_FRACTION_DIMENSIONS):
                    known_sum = sum(
                        observed[name]
                        for name in CONGESTION_FRACTION_DIMENSIONS
                        if name != "congestion_unknown_fraction"
                    )
                    if not math.isclose(known_sum, 1.0, abs_tol=1e-6):
                        raise BaselineError(
                            f"congestion fractions do not sum to one for "
                            f"{wan}:{direction} at {timestamp}"
                        )


def build_cohorts(  # noqa: C901 - explicit fail-closed dimension assembly
    matrices: dict[str, dict[tuple[str, ...], dict[int, float]]],
    timestamps: list[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require_exact_labels("shaped_rate_bps", matrices["shaped_rate_bps"], ("wan", "direction"))
    require_exact_labels("throughput_bps", matrices["throughput_bps"], ("wan", "direction"))
    require_exact_labels("rtt_delta_seconds", matrices["rtt_delta_seconds"], ("wan",))
    require_exact_labels("probe_rtt_seconds", matrices["probe_rtt_seconds"], ("wan",))
    require_exact_labels("probe_up", matrices["probe_up"], ("wan",))
    validate_congestion_fractions(matrices, timestamps)
    for name in (
        "tin_average_delay_seconds",
        "tin_peak_delay_seconds",
        "tin_backlog_bytes",
        "tin_drop_rate",
        "tin_ecn_rate",
        "tin_resets_total",
    ):
        require_exact_labels(name, matrices[name], ("wan", "direction", "tin"))

    grouped: dict[tuple[str, str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    candidate_points = 0
    accepted_points = 0
    missing_by_dimension: dict[str, int] = defaultdict(int)

    for wan in WANS:
        rtt = matrices["rtt_delta_seconds"][(wan,)]
        probe_rtt = matrices["probe_rtt_seconds"][(wan,)]
        probe_up = matrices["probe_up"][(wan,)]
        for direction in DIRECTIONS:
            key = (wan, direction)
            throughput = matrices["throughput_bps"][key]
            shaped = matrices["shaped_rate_bps"][key]
            last_reset_totals: dict[str, float] = {}
            for timestamp in timestamps:
                candidate_points += 1
                if probe_up.get(timestamp) != 1.0:
                    reason = "probe_missing" if timestamp not in probe_up else "probe_down"
                    missing_by_dimension[reason] += 1
                    continue
                if timestamp not in throughput:
                    missing_by_dimension["throughput_bps"] += 1
                    continue
                throughput_value = throughput[timestamp]
                dimensions: dict[str, float] = {"throughput_bps": throughput_value}
                if timestamp not in shaped or shaped[timestamp] <= 0:
                    missing_by_dimension["shaped_rate_bps"] += 1
                    continue
                required_wan_direction = {
                    "rtt_delta_seconds": rtt,
                    "probe_rtt_seconds": probe_rtt,
                    **{name: matrices[name][key] for name in CONGESTION_FRACTION_DIMENSIONS},
                }
                if any(timestamp not in points for points in required_wan_direction.values()):
                    for name, points in required_wan_direction.items():
                        if timestamp not in points:
                            missing_by_dimension[name] += 1
                    continue
                utilization = throughput_value / shaped[timestamp]
                if utilization < 0 or utilization > MAX_UTILIZATION_RATIO:
                    missing_by_dimension["utilization_out_of_bounds"] += 1
                    continue
                dimensions["shaped_rate_bps"] = shaped[timestamp]
                dimensions["utilization_ratio"] = utilization
                for name, points in required_wan_direction.items():
                    dimensions[name] = points[timestamp]
                complete = True
                for tin in TINS:
                    tin_key = (wan, direction, tin)
                    for name in (
                        "tin_average_delay_seconds",
                        "tin_peak_delay_seconds",
                        "tin_backlog_bytes",
                        "tin_drop_rate",
                        "tin_ecn_rate",
                        "tin_resets_total",
                    ):
                        points = matrices[name][tin_key]
                        if timestamp not in points:
                            missing_by_dimension[f"{name}:{tin}"] += 1
                            complete = False
                        else:
                            dimensions[f"{name}:{tin}"] = points[timestamp]
                    reset_points = matrices["tin_resets_total"][tin_key]
                    if timestamp in reset_points:
                        current_resets = reset_points[timestamp]
                        if current_resets > last_reset_totals.get(tin, current_resets):
                            missing_by_dimension[f"counter_reset:{tin}"] += 1
                            complete = False
                        last_reset_totals[tin] = current_resets
                if not complete:
                    continue
                accepted_points += 1
                cohort_key = (
                    wan,
                    direction,
                    load_cohort(dimensions["utilization_ratio"]),
                    time_cohort(timestamp),
                )
                for name, value in dimensions.items():
                    grouped[cohort_key][name].append(value)

    if accepted_points == 0:
        raise BaselineError("no complete samples qualified for cohorts")
    completeness_ratio = accepted_points / candidate_points
    if completeness_ratio < MIN_COHORT_COMPLETENESS_RATIO:
        raise BaselineError(
            f"complete cohort samples {completeness_ratio:.3%} below "
            f"{MIN_COHORT_COMPLETENESS_RATIO:.0%}"
        )
    cohorts = []
    insufficient_cohorts = []
    for (wan, direction, load, time_name), cohort_dimensions in sorted(grouped.items()):
        sample_count = len(next(iter(cohort_dimensions.values())))
        identity = {
            "wan": wan,
            "direction": direction,
            "load_cohort": load,
            "time_cohort": time_name,
        }
        if sample_count < MIN_COHORT_SAMPLES:
            insufficient_cohorts.append({**identity, "sample_count": sample_count})
            continue
        cohorts.append(
            {
                **identity,
                "sample_count": sample_count,
                "dimensions": {
                    name: summarize(values) for name, values in sorted(cohort_dimensions.items())
                },
            }
        )
    for wan in WANS:
        for direction in DIRECTIONS:
            if not any(
                cohort["wan"] == wan and cohort["direction"] == direction for cohort in cohorts
            ):
                raise BaselineError(
                    f"no cohort has at least {MIN_COHORT_SAMPLES} samples for {wan}:{direction}"
                )
    expected_cohorts = {
        (wan, direction, load, time_name)
        for wan in WANS
        for direction in DIRECTIONS
        for load in ("idle_lt_10pct", "active_10_to_60pct", "loaded_ge_60pct")
        for time_name in ("utc_00_to_06", "utc_06_to_18", "utc_18_to_24")
    }
    observed_cohorts = set(grouped)
    disclosure = {
        "candidate_points": candidate_points,
        "accepted_points": accepted_points,
        "discarded_incomplete_points": candidate_points - accepted_points,
        "completeness_ratio": round(completeness_ratio, 6),
        "missing_by_dimension": dict(sorted(missing_by_dimension.items())),
        "observed_cohort_count": len(observed_cohorts),
        "published_cohort_count": len(cohorts),
        "insufficient_cohorts": insufficient_cohorts,
        "missing_cohorts": [
            {
                "wan": wan,
                "direction": direction,
                "load_cohort": load,
                "time_cohort": time_name,
            }
            for wan, direction, load, time_name in sorted(expected_cohorts - observed_cohorts)
        ],
    }
    return cohorts, disclosure


def collect_matrices(
    base_url: str, start: datetime, end: datetime
) -> dict[str, dict[tuple[str, ...], dict[int, float]]]:
    matrices = {}
    for name, expression in QUERIES.items():
        labels: tuple[str, ...] = ("wan",)
        if name in {"shaped_rate_bps", "throughput_bps", *CONGESTION_FRACTION_DIMENSIONS}:
            labels = ("wan", "direction")
        elif name.startswith("tin_"):
            labels = ("wan", "direction", "tin")
        matrices[name] = normalize_matrix(range_query(base_url, expression, start, end), labels)
    return matrices


def baseline_report(base_url: str, start: datetime, end: datetime) -> tuple[dict[str, Any], int]:
    duration = (end - start).total_seconds()
    common = {
        "schema_version": 1,
        "window": {
            "start": format_timestamp(start),
            "end": format_timestamp(end),
            "duration_seconds": duration,
            "step_seconds": STEP_SECONDS,
        },
        "cohort_contract": {
            "load": ["idle_lt_10pct", "active_10_to_60pct", "loaded_ge_60pct"],
            "time_utc": ["utc_00_to_06", "utc_06_to_18", "utc_18_to_24"],
        },
        "queries": QUERIES,
        "safety": {
            "read_only_prometheus_api": True,
            "configuration_writes": False,
            "traffic_generation": False,
            "tuning_or_actuation": False,
        },
    }
    if duration < MIN_WINDOW_SECONDS:
        return {
            **common,
            "status": "not_eligible",
            "reason": "window_shorter_than_minimum",
            "eligible_at": format_timestamp(start + timedelta(seconds=MIN_WINDOW_SECONDS)),
        }, 2
    if duration != MIN_WINDOW_SECONDS:
        return {**common, "status": "rejected", "reason": "window_must_equal_exactly_minimum"}, 2
    try:
        matrices = collect_matrices(base_url, start, end)
        coverage = validate_coverage(matrices, start, end)
        coverage["dimensions"] = validate_dimension_coverage(matrices, start, end)
        cohorts, missing = build_cohorts(matrices, evaluation_timestamps(start, end))
    except (BaselineError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return {**common, "status": "rejected", "reason": str(exc)}, 2
    return {
        **common,
        "status": "accepted",
        "coverage": coverage,
        "missing_data": missing,
        "cohorts": cohorts,
    }, 0


def write_report(report: dict[str, Any], output: Path | None) -> None:
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(content)
    else:
        output.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", required=True)
    parser.add_argument("--start", required=True, help="RFC3339 inclusive UTC start")
    parser.add_argument("--end", required=True, help="RFC3339 inclusive UTC end")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        start = parse_timestamp(args.start)
        end = parse_timestamp(args.end)
        if end <= start:
            raise BaselineError("end must be after start")
        report, exit_code = baseline_report(args.prometheus_url, start, end)
    except BaselineError as exc:
        report, exit_code = {"schema_version": 1, "status": "rejected", "reason": str(exc)}, 2
    write_report(report, args.output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

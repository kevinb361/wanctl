#!/usr/bin/env python3
"""Build a deterministic, non-actuating tuning evidence model from a frozen baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TINS = ("bulk", "best_effort", "video", "voice")
TIN_DIMENSIONS = (
    "tin_average_delay_seconds",
    "tin_peak_delay_seconds",
    "tin_backlog_bytes",
    "tin_drop_rate",
    "tin_ecn_rate",
    "tin_resets_total",
)
SUMMARY_KEYS = ("count", "mean", "p50", "p95", "p99", "max")
STEP_SECONDS = 300
WINDOW_SECONDS = 659100  # ~7.63 days (waived from 14d on 2026-08-18)
MAX_EVALUATION_WINDOWS = WINDOW_SECONDS // STEP_SECONDS  # 2197
LOAD_COHORTS = ("idle_lt_10pct", "active_10_to_60pct", "loaded_ge_60pct")
TIME_COHORTS = ("utc_00_to_06", "utc_06_to_18", "utc_18_to_24")
CONGESTION_FRACTIONS = {
    "green": "congestion_green_fraction",
    "yellow_or_soft_red": "congestion_yellow_or_soft_red_fraction",
    "red": "congestion_red_fraction",
    "unknown_or_rejected": "congestion_unknown_fraction",
}
EXPECTED_QUERY_CONTRACT_SHA256 = "c518f359f096d5b9511d829e1b0cd5ba30c291ded7f25c75ac51cf5236ba5503"
OBS006_DECISION = ".planning/decisions/2706-waive-obs006-fourteen-day-temporal-gate.md"


class ModelError(ValueError):
    """The frozen baseline cannot produce trustworthy tuning evidence."""


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ModelError(f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelError(f"{field} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ModelError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


def require_summary(dimensions: dict[str, Any], name: str, sample_count: int) -> dict[str, float]:
    value = dimensions.get(name)
    if not isinstance(value, dict) or set(value) != set(SUMMARY_KEYS):
        raise ModelError(f"missing or invalid summary: {name}")
    summary: dict[str, float] = {}
    for key in SUMMARY_KEYS:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            raise ModelError(f"non-finite summary value: {name}.{key}")
        summary[key] = float(raw)
    if summary["count"] != sample_count:
        raise ModelError(f"summary count mismatch: {name}")
    if not summary["p50"] <= summary["p95"] <= summary["p99"] <= summary["max"]:
        raise ModelError(f"summary percentile ordering is impossible: {name}")
    if summary["mean"] > summary["max"]:
        raise ModelError(f"summary mean exceeds max: {name}")
    return summary


def build_congestion_occupancy(dimensions: dict[str, Any], sample_count: int) -> dict[str, Any]:
    summaries = {
        state: require_summary(dimensions, dimension, sample_count)
        for state, dimension in CONGESTION_FRACTIONS.items()
    }
    for state, summary in summaries.items():
        for key in ("mean", "p50", "p95", "p99", "max"):
            if summary[key] < 0 or summary[key] > 1:
                raise ModelError(f"congestion fraction out of bounds: {state}.{key}")
    unknown = summaries["unknown_or_rejected"]
    if unknown["max"] != 0:
        raise ModelError("accepted baseline contains unknown congestion state occupancy")
    known_mean = sum(summaries[state]["mean"] for state in ("green", "yellow_or_soft_red", "red"))
    if not math.isclose(known_mean, 1.0, abs_tol=1e-6):
        raise ModelError("mean congestion occupancy fractions do not sum to one")
    return {
        "method": "evaluation-sampled five-minute over-time fraction",
        "evaluation_windows": sample_count,
        "interval_seconds": STEP_SECONDS,
        "states": {
            state: {
                "mean_fraction": summary["mean"],
                "estimated_seconds": round(summary["mean"] * sample_count * STEP_SECONDS, 9),
                "window_fraction_distribution": summary,
            }
            for state, summary in summaries.items()
        },
    }


def build_model(  # noqa: C901 - explicit fail-closed schema validation
    baseline: dict[str, Any], *, input_sha256: str, semantic_valid_from: datetime
) -> dict[str, Any]:
    if baseline.get("status") != "accepted":
        raise ModelError("input baseline must have status=accepted")
    window = baseline.get("window")
    if not isinstance(window, dict):
        raise ModelError("input baseline is missing its window")
    start = parse_timestamp(window.get("start"), "window.start")
    end = parse_timestamp(window.get("end"), "window.end")
    duration = window.get("duration_seconds")
    if start < semantic_valid_from:
        raise ModelError("input window predates corrected congestion semantics")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ModelError("window.duration_seconds must be numeric")
    if duration != WINDOW_SECONDS or (end - start).total_seconds() != WINDOW_SECONDS:
        raise ModelError("input window must equal exactly the configured window")
    step = window.get("step_seconds")
    if isinstance(step, bool) or step != STEP_SECONDS:
        raise ModelError("input step_seconds must equal 300")
    expected_cohort_contract = {"load": list(LOAD_COHORTS), "time_utc": list(TIME_COHORTS)}
    if baseline.get("cohort_contract") != expected_cohort_contract:
        raise ModelError("input cohort contract does not match the fixed contract")
    queries = baseline.get("queries")
    if not isinstance(queries, dict) or not queries:
        raise ModelError("input baseline is missing its query contract")
    query_contract = json.dumps(queries, sort_keys=True, separators=(",", ":")).encode()
    query_contract_sha256 = hashlib.sha256(query_contract).hexdigest()
    if query_contract_sha256 != EXPECTED_QUERY_CONTRACT_SHA256:
        raise ModelError("input query contract does not match the fixed collector contract")
    cohorts = baseline.get("cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise ModelError("input baseline contains no cohorts")

    modeled = []
    seen: set[tuple[str, str, str, str]] = set()
    support_by_wan_direction: dict[tuple[str, str], int] = {}
    for cohort in cohorts:
        if not isinstance(cohort, dict):
            raise ModelError("invalid cohort")
        wan = cohort.get("wan")
        direction = cohort.get("direction")
        load_name = cohort.get("load_cohort")
        time_name = cohort.get("time_cohort")
        if not all(
            isinstance(value, str) and value for value in (wan, direction, load_name, time_name)
        ):
            raise ModelError("cohort identity is incomplete")
        assert isinstance(wan, str)
        assert isinstance(direction, str)
        assert isinstance(load_name, str)
        assert isinstance(time_name, str)
        if load_name not in LOAD_COHORTS or time_name not in TIME_COHORTS:
            raise ModelError("cohort identity is outside the fixed vocabulary")
        identity = (wan, direction, load_name, time_name)
        if identity in seen:
            raise ModelError(f"duplicate cohort identity: {identity}")
        seen.add(identity)
        sample_count = cohort.get("sample_count")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
            raise ModelError("cohort sample_count must be positive")
        if sample_count > MAX_EVALUATION_WINDOWS:
            raise ModelError("cohort support exceeds the fixed input window")
        support_key = (wan, direction)
        support_by_wan_direction[support_key] = (
            support_by_wan_direction.get(support_key, 0) + sample_count
        )
        if support_by_wan_direction[support_key] > MAX_EVALUATION_WINDOWS:
            raise ModelError(f"aggregate cohort support exceeds window for {wan}:{direction}")
        dimensions = cohort.get("dimensions")
        if not isinstance(dimensions, dict):
            raise ModelError("cohort dimensions are missing")
        utilization = require_summary(dimensions, "utilization_ratio", sample_count)
        throughput = require_summary(dimensions, "throughput_bps", sample_count)
        rtt_delta = require_summary(dimensions, "rtt_delta_seconds", sample_count)
        probe_rtt = require_summary(dimensions, "probe_rtt_seconds", sample_count)
        state_occupancy = build_congestion_occupancy(dimensions, sample_count)
        per_tin = {}
        for tin in TINS:
            per_tin[tin] = {
                name.removeprefix("tin_"): require_summary(
                    dimensions, f"{name}:{tin}", sample_count
                )
                for name in TIN_DIMENSIONS
            }
        modeled.append(
            {
                "wan": identity[0],
                "direction": identity[1],
                "load_cohort": identity[2],
                "time_cohort": identity[3],
                "support": {
                    "evaluation_windows": sample_count,
                    "interval_seconds": STEP_SECONDS,
                    "evaluated_interval_seconds": sample_count * STEP_SECONDS,
                },
                "throughput_utility": {
                    "throughput_bps": throughput,
                    "utilization_ratio": utilization,
                    "median_percent_of_shaped_rate": utilization["p50"] * 100,
                },
                "loaded_rtt_tail": {
                    "applicable": identity[2] == "loaded_ge_60pct",
                    "scope": "wan-level RTT repeated across direction cohorts",
                    "rtt_delta_seconds_p95": rtt_delta["p95"],
                    "rtt_delta_seconds_p99": rtt_delta["p99"],
                    "probe_rtt_seconds_p95": probe_rtt["p95"],
                    "probe_rtt_seconds_p99": probe_rtt["p99"],
                },
                "congestion_state_occupancy": state_occupancy,
                "per_tin": per_tin,
            }
        )

    covered = {(item["wan"], item["direction"]) for item in modeled}
    expected = {
        (wan, direction) for wan in ("att", "spectrum") for direction in ("download", "upload")
    }
    if covered != expected:
        raise ModelError(f"cohort WAN/direction coverage mismatch: {sorted(covered)}")

    return {
        "schema_version": 1,
        "provenance": {
            "input_sha256": input_sha256,
            "query_contract_sha256": query_contract_sha256,
            "window": window,
            "actual_duration_seconds": duration,
            "semantic_valid_from": semantic_valid_from.isoformat().replace("+00:00", "Z"),
            "obs006": {
                "decision": OBS006_DECISION,
                "accepted_baseline_inherited": False,
                "disposition": "WAIVED",
            },
        },
        "cohorts": sorted(
            modeled,
            key=lambda item: (
                item["wan"],
                item["direction"],
                item["load_cohort"],
                item["time_cohort"],
            ),
        ),
        "safety": {
            "read_only_frozen_input": True,
            "configuration_writes": False,
            "traffic_generation": False,
            "recommendation_or_actuation": False,
        },
    }


def render_model(input_path: Path, semantic_valid_from: datetime) -> str:
    content = input_path.read_bytes()
    try:
        baseline = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelError("input baseline is not valid JSON") from exc
    if not isinstance(baseline, dict):
        raise ModelError("input baseline must be a JSON object")
    model = build_model(
        baseline,
        input_sha256=hashlib.sha256(content).hexdigest(),
        semantic_valid_from=semantic_valid_from,
    )
    return json.dumps(model, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="accepted frozen baseline JSON")
    parser.add_argument("--semantic-valid-from", required=True, help="RFC3339 UTC lower bound")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        content = render_model(
            args.input,
            parse_timestamp(args.semantic_valid_from, "semantic_valid_from"),
        )
    except (ModelError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.output is None:
        sys.stdout.write(content)
    else:
        args.output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

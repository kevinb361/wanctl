from __future__ import annotations

import copy
import json
import runpy
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "cake_tuning_baseline.py"
COLLECTOR = REPO_ROOT / "scripts" / "cake_telemetry_baseline.py"
SEMANTIC_START = "2026-08-10T18:48:24.594563Z"


def _load() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _summary(value: float, count: int = 12) -> dict[str, float | int]:
    return {
        "count": count,
        "mean": value,
        "p50": value,
        "p95": value,
        "p99": value,
        "max": value,
    }


def _cohort(wan: str, direction: str) -> dict[str, Any]:
    dimensions = {
        "throughput_bps": _summary(80_000_000.0),
        "utilization_ratio": _summary(0.8),
        "rtt_delta_seconds": _summary(0.025),
        "probe_rtt_seconds": _summary(0.045),
        "congestion_green_fraction": _summary(0.5),
        "congestion_yellow_or_soft_red_fraction": _summary(0.3),
        "congestion_red_fraction": _summary(0.2),
        "congestion_unknown_fraction": _summary(0.0),
    }
    for tin_index, tin in enumerate(("bulk", "best_effort", "video", "voice"), start=1):
        for name in (
            "tin_average_delay_seconds",
            "tin_peak_delay_seconds",
            "tin_backlog_bytes",
            "tin_drop_rate",
            "tin_ecn_rate",
            "tin_resets_total",
        ):
            dimensions[f"{name}:{tin}"] = _summary(float(tin_index))
    return {
        "wan": wan,
        "direction": direction,
        "load_cohort": "loaded_ge_60pct",
        "time_cohort": "utc_18_to_24",
        "sample_count": 12,
        "dimensions": dimensions,
    }


def _baseline() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "accepted",
        "window": {
            "start": SEMANTIC_START,
            "end": "2026-08-24T18:48:24.594563Z",
            "duration_seconds": 14 * 24 * 60 * 60,
            "step_seconds": 300,
        },
        "cohort_contract": {
            "load": ["idle_lt_10pct", "active_10_to_60pct", "loaded_ge_60pct"],
            "time_utc": ["utc_00_to_06", "utc_06_to_18", "utc_18_to_24"],
        },
        "queries": runpy.run_path(str(COLLECTOR))["QUERIES"],
        "cohorts": [
            _cohort(wan, direction)
            for wan in ("att", "spectrum")
            for direction in ("download", "upload")
        ],
    }


def _set_cohort_count(cohort: dict[str, Any], count: int) -> None:
    cohort["sample_count"] = count
    for summary in cohort["dimensions"].values():
        summary["count"] = count


def _build(namespace: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    return namespace["build_model"](
        baseline or _baseline(),
        input_sha256="a" * 64,
        semantic_valid_from=datetime.fromisoformat(SEMANTIC_START.replace("Z", "+00:00")),
    )


def test_model_exposes_explicit_dimensions_provenance_and_safety() -> None:
    model = _build(_load())

    assert model["provenance"]["actual_duration_seconds"] == 14 * 24 * 60 * 60
    assert model["provenance"]["semantic_valid_from"] == SEMANTIC_START
    assert model["provenance"]["obs006"] == {
        "decision": ".planning/decisions/2706-waive-obs006-fourteen-day-temporal-gate.md",
        "accepted_baseline_inherited": False,
        "disposition": "WAIVED",
    }
    assert len(model["cohorts"]) == 4
    cohort = model["cohorts"][0]
    assert cohort["throughput_utility"]["median_percent_of_shaped_rate"] == 80.0
    assert cohort["loaded_rtt_tail"] == {
        "applicable": True,
        "scope": "wan-level RTT repeated across direction cohorts",
        "rtt_delta_seconds_p95": 0.025,
        "rtt_delta_seconds_p99": 0.025,
        "probe_rtt_seconds_p95": 0.045,
        "probe_rtt_seconds_p99": 0.045,
    }
    occupancy = cohort["congestion_state_occupancy"]
    assert occupancy["method"] == "evaluation-sampled five-minute over-time fraction"
    assert occupancy["states"]["red"]["estimated_seconds"] == 720.0
    assert occupancy["states"]["unknown_or_rejected"]["mean_fraction"] == 0.0
    assert set(cohort["per_tin"]) == {"bulk", "best_effort", "video", "voice"}
    assert model["safety"]["recommendation_or_actuation"] is False


def test_model_is_deterministic_for_reordered_frozen_cohorts() -> None:
    namespace = _load()
    baseline = _baseline()
    first = _build(namespace, baseline)
    baseline["cohorts"].reverse()
    second = _build(namespace, baseline)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_cli_replay_is_byte_stable(tmp_path: Path) -> None:
    source = tmp_path / "accepted.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    source.write_text(json.dumps(_baseline(), sort_keys=True), encoding="utf-8")
    command = [
        sys.executable,
        str(SCRIPT),
        "--input",
        str(source),
        "--semantic-valid-from",
        SEMANTIC_START,
    ]

    subprocess.run([*command, "--output", str(first)], check=True)
    subprocess.run([*command, "--output", str(second)], check=True)

    assert first.read_bytes() == second.read_bytes()


def test_model_rejects_window_before_corrected_semantics() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["window"]["start"] = "2026-08-10T18:48:23Z"
    baseline["window"]["end"] = "2026-08-24T18:48:23Z"

    with pytest.raises(namespace["ModelError"], match="predates corrected congestion semantics"):
        _build(namespace, baseline)


@pytest.mark.parametrize("status", ["rejected", "not_eligible", None])
def test_model_rejects_unaccepted_baseline(status: str | None) -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["status"] = status

    with pytest.raises(namespace["ModelError"], match="status=accepted"):
        _build(namespace, baseline)


def test_model_rejects_unknown_state_occupancy() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0]["dimensions"]["congestion_unknown_fraction"] = _summary(0.1)

    with pytest.raises(namespace["ModelError"], match="unknown congestion state occupancy"):
        _build(namespace, baseline)


def test_model_derives_occupancy_instead_of_copying_untrusted_state_time() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0]["congestion_state_time"] = {
        "sample_seconds": "banana",
        "states": {"red": {"seconds": True, "fraction": 3.0}},
    }

    model = _build(namespace, baseline)

    cohort = next(item for item in model["cohorts"] if item["wan"] == "att")
    assert "congestion_state_time" not in cohort
    assert cohort["congestion_state_occupancy"]["states"]["red"]["estimated_seconds"] == 720.0


def test_model_rejects_contradictory_mean_occupancy_fractions() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0]["dimensions"]["congestion_green_fraction"] = _summary(0.0)

    with pytest.raises(namespace["ModelError"], match="do not sum to one"):
        _build(namespace, baseline)


@pytest.mark.parametrize("step", [60, True, None])
def test_model_rejects_noncontract_step(step: int | bool | None) -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["window"]["step_seconds"] = step

    with pytest.raises(namespace["ModelError"], match="step_seconds must equal 300"):
        _build(namespace, baseline)


def test_model_rejects_non_fourteen_day_window() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["window"]["end"] = "2026-08-17T18:48:24.594563Z"
    baseline["window"]["duration_seconds"] = 7 * 24 * 60 * 60

    with pytest.raises(namespace["ModelError"], match="exactly 14 days"):
        _build(namespace, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    [("load_cohort", "loaded_ge_60pct_TYPO"), ("time_cohort", "whenever")],
)
def test_model_rejects_invalid_cohort_vocabulary(field: str, value: str) -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0][field] = value

    with pytest.raises(namespace["ModelError"], match="outside the fixed vocabulary"):
        _build(namespace, baseline)


def test_model_rejects_changed_query_or_cohort_contract() -> None:
    namespace = _load()
    changed_query = _baseline()
    changed_query["queries"]["throughput_bps"] = "different query"
    with pytest.raises(namespace["ModelError"], match="query contract"):
        _build(namespace, changed_query)

    changed_cohorts = _baseline()
    changed_cohorts["cohort_contract"]["load"] = ["loaded_ge_60pct"]
    with pytest.raises(namespace["ModelError"], match="cohort contract"):
        _build(namespace, changed_cohorts)


def test_model_rejects_missing_wan_direction_coverage() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"] = baseline["cohorts"][:-1]

    with pytest.raises(namespace["ModelError"], match="coverage mismatch"):
        _build(namespace, baseline)


def test_model_rejects_summary_count_mismatch() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0]["dimensions"]["utilization_ratio"] = _summary(0.8, count=11)

    with pytest.raises(namespace["ModelError"], match="summary count mismatch"):
        _build(namespace, baseline)


def test_model_rejects_per_cohort_support_larger_than_window() -> None:
    namespace = _load()
    baseline = _baseline()
    _set_cohort_count(baseline["cohorts"][0], 100_000)

    with pytest.raises(namespace["ModelError"], match=r"^cohort support exceeds"):
        _build(namespace, baseline)


def test_model_rejects_aggregate_wan_direction_support_larger_than_window() -> None:
    namespace = _load()
    baseline = _baseline()
    extra = copy.deepcopy(baseline["cohorts"][0])
    extra["load_cohort"] = "active_10_to_60pct"
    _set_cohort_count(extra, 4_030)
    baseline["cohorts"].append(extra)

    with pytest.raises(namespace["ModelError"], match="aggregate cohort support exceeds"):
        _build(namespace, baseline)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"p50": 0.9, "p95": 0.8}, "percentile ordering"),
        ({"mean": 0.9, "max": 0.8, "p50": 0.8, "p95": 0.8, "p99": 0.8}, "mean exceeds"),
    ],
)
def test_model_rejects_impossible_summary_ordering(updates: dict[str, float], message: str) -> None:
    namespace = _load()
    baseline = _baseline()
    summary = baseline["cohorts"][0]["dimensions"]["utilization_ratio"]
    summary.update(updates)

    with pytest.raises(namespace["ModelError"], match=message):
        _build(namespace, baseline)


@pytest.mark.parametrize(
    "updates",
    [
        {"p50": -0.5},
        {"p95": 1.5, "p99": 1.5, "max": 1.5},
    ],
)
def test_model_rejects_out_of_bounds_congestion_fraction(
    updates: dict[str, float],
) -> None:
    namespace = _load()
    baseline = _baseline()
    summary = baseline["cohorts"][0]["dimensions"]["congestion_green_fraction"]
    summary.update(updates)

    with pytest.raises(namespace["ModelError"], match="congestion fraction out of bounds"):
        _build(namespace, baseline)


def test_model_rejects_bool_congestion_fraction() -> None:
    namespace = _load()
    baseline = _baseline()
    baseline["cohorts"][0]["dimensions"]["congestion_green_fraction"]["mean"] = True

    with pytest.raises(namespace["ModelError"], match="non-finite summary value"):
        _build(namespace, baseline)


def test_full_capacity_is_accepted_independently_per_wan_direction() -> None:
    namespace = _load()
    baseline = _baseline()
    cohorts = []
    utilization_by_load = {
        "idle_lt_10pct": 0.05,
        "active_10_to_60pct": 0.2,
        "loaded_ge_60pct": 0.8,
    }
    for wan in ("att", "spectrum"):
        for direction in ("download", "upload"):
            for load_name, utilization in utilization_by_load.items():
                for time_name in ("utc_00_to_06", "utc_06_to_18", "utc_18_to_24"):
                    cohort = _cohort(wan, direction)
                    cohort["load_cohort"] = load_name
                    cohort["time_cohort"] = time_name
                    cohort["dimensions"]["utilization_ratio"] = _summary(utilization, count=448)
                    _set_cohort_count(cohort, 448)
                    cohorts.append(cohort)
    baseline["cohorts"] = cohorts

    model = _build(namespace, baseline)

    for wan in ("att", "spectrum"):
        for direction in ("download", "upload"):
            selected = [
                cohort
                for cohort in model["cohorts"]
                if cohort["wan"] == wan and cohort["direction"] == direction
            ]
            assert sum(item["support"]["evaluation_windows"] for item in selected) == 4_032
            assert (
                sum(item["support"]["evaluated_interval_seconds"] for item in selected) == 1_209_600
            )
            assert (
                sum(
                    state["estimated_seconds"]
                    for item in selected
                    for state in item["congestion_state_occupancy"]["states"].values()
                )
                == 1_209_600
            )


def test_loaded_rtt_applicability_follows_validated_load_cohort() -> None:
    namespace = _load()
    baseline = _baseline()
    for cohort in baseline["cohorts"]:
        cohort["load_cohort"] = "idle_lt_10pct"

    model = _build(namespace, baseline)

    assert all(not cohort["loaded_rtt_tail"]["applicable"] for cohort in model["cohorts"])


def test_script_has_no_network_or_control_command_surface() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "urllib" not in source
    assert "import subprocess" not in source
    assert "os.system" not in source
    assert "shell=True" not in source
    assert "cake-metrics-exporter" not in source
    assert "systemctl" not in source
    assert " tc " not in source

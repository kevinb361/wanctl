"""Phase 204 replay tests for CALIB-01 completed-window distribution math."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATOR_PATH = REPO_ROOT / "scripts" / "soak_summary_aggregate.py"
SYNTHETIC_NDJSON = REPO_ROOT / "tests" / "fixtures" / "phase_204_synthetic_capture.ndjson"
SYNTHETIC_SUMMARY = REPO_ROOT / "tests" / "fixtures" / "phase_204_synthetic_summary.json"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_aggregate_soak_matches_golden() -> None:
    """CALIB-01: synthetic NDJSON aggregate output must byte-equal golden JSON."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
    golden = json.loads(SYNTHETIC_SUMMARY.read_text(encoding="utf-8"))
    assert json.dumps(result, sort_keys=True, indent=2) == json.dumps(
        golden, sort_keys=True, indent=2
    )


def test_p99_is_explicit_number() -> None:
    """Phase 204 requires p99 explicitly; p95-only summaries are insufficient."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
    value = result["suppressions_completed_window_count_distribution"]["p99"]
    assert isinstance(value, int | float)


def test_by_cause_window_counts_use_same_boundary_set() -> None:
    """Per-cause slices retain the same explicit completed-window boundaries."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    dist = aggregator.aggregate_soak(SYNTHETIC_NDJSON)[
        "suppressions_completed_window_count_distribution"
    ]
    assert dist["valid"] is True
    assert dist["boundary_source"] == "ul_hysteresis_window_start_epoch"
    assert {cell["window_count"] for cell in dist["by_cause"].values()} == {
        dist["window_count"]
    }


def test_fixture_has_meaningful_window_count() -> None:
    """Synthetic fixture has enough completed windows for percentile math."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    dist = aggregator.aggregate_soak(SYNTHETIC_NDJSON)[
        "suppressions_completed_window_count_distribution"
    ]
    assert dist["window_count"] >= 5


def test_equal_decreasing_and_zero_windows_are_retained() -> None:
    """Snapshot values can repeat, decrease, or be zero across window boundaries."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    rows = [
        {
            "t_monotonic": 0.0,
            "ul_hysteresis_window_start_epoch": 0.0,
            "ul_suppressions_completed_window_count": 0,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": 0,
                "backlog_recovery": 0,
                "other": 0,
            },
        },
        {
            "t_monotonic": 60.0,
            "ul_hysteresis_window_start_epoch": 60.0,
            "ul_suppressions_completed_window_count": 68,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": 68,
                "backlog_recovery": 0,
                "other": 0,
            },
        },
        {
            "t_monotonic": 120.0,
            "ul_hysteresis_window_start_epoch": 120.0,
            "ul_suppressions_completed_window_count": 20,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": 12,
                "backlog_recovery": 8,
                "other": 0,
            },
        },
        {
            "t_monotonic": 180.0,
            "ul_hysteresis_window_start_epoch": 180.0,
            "ul_suppressions_completed_window_count": 0,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": 0,
                "backlog_recovery": 0,
                "other": 0,
            },
        },
        {
            "t_monotonic": 240.0,
            "ul_hysteresis_window_start_epoch": 240.0,
            "ul_suppressions_completed_window_count": 20,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": 20,
                "backlog_recovery": 0,
                "other": 0,
            },
        },
    ]
    dist = aggregator.aggregate_completed_window_distribution(rows)
    assert dist["window_count"] == 4
    assert dist["max"] == 68
    assert dist["by_cause"]["dwell_hold"]["window_count"] == 4
    assert dist["by_cause"]["backlog_recovery"]["max"] == 8


def test_missing_window_epoch_fails_closed() -> None:
    """Completed-window gates must not pass without an explicit boundary marker."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    rows = [
        {"ul_suppressions_completed_window_count": 0},
        {"ul_suppressions_completed_window_count": 68},
    ]
    dist = aggregator.aggregate_completed_window_distribution(rows)
    assert dist["valid"] is False
    assert "ul_hysteresis_window_start_epoch" in dist["reason"]
    gate = aggregator.aggregate_watchdog(
        rows,
        new_threshold=125,
        statistic="p99",
        gate_column="by_cause.dwell_hold",
    )["secondary_gate_completed_window"]
    assert gate["verdict"] == "fail"
    assert "ul_hysteresis_window_start_epoch" in gate["reason"]

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


def test_by_cause_window_counts_sum_to_top_level() -> None:
    """Per-cause slices operate on the same completed-window boundary set."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    dist = aggregator.aggregate_soak(SYNTHETIC_NDJSON)[
        "suppressions_completed_window_count_distribution"
    ]
    by_cause_total = sum(cell["window_count"] for cell in dist["by_cause"].values())
    assert by_cause_total == dist["window_count"]


def test_fixture_has_meaningful_window_count() -> None:
    """Synthetic fixture has enough completed windows for percentile math."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    dist = aggregator.aggregate_soak(SYNTHETIC_NDJSON)[
        "suppressions_completed_window_count_distribution"
    ]
    assert dist["window_count"] >= 5


def test_equal_monotonic_spans_do_not_double_count() -> None:
    """Equal adjacent samples represent plateau rows, not new boundaries."""
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    rows = [
        {"ul_suppressions_completed_window_count": 0},
        {"ul_suppressions_completed_window_count": 0},
        {"ul_suppressions_completed_window_count": 3},
        {"ul_suppressions_completed_window_count": 3},
        {"ul_suppressions_completed_window_count": 8},
    ]
    dist = aggregator.aggregate_completed_window_distribution(rows)
    assert dist["window_count"] == 2
    assert dist["max"] == 5

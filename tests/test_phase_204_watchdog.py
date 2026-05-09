"""Phase 204 CALIB-03 watchdog aggregation tests.

The legacy watchdog block is a transition-only port of the v1.42 inline-jq
suppression-rate computation. The completed-window block is the real D-14
successor gate and reads operator-approved constants from
``scripts/calib_02_threshold.json`` through ``aggregate_soak()``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATOR_PATH = REPO_ROOT / "scripts" / "soak_summary_aggregate.py"
SYNTHETIC_NDJSON = REPO_ROOT / "tests" / "fixtures" / "phase_204_synthetic_capture.ndjson"
V142_NDJSON = (
    REPO_ROOT
    / ".planning"
    / "milestones"
    / "v1.42-phases"
    / "201-docsis-aware-ul-congestion-control"
    / "soak"
    / "20260505T132736Z"
    / "soak-capture.ndjson"
)


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def aggregator() -> ModuleType:
    return _load_module(AGGREGATOR_PATH, "soak_aggregator_phase_204_watchdog")


def _make_rows(boundary_jumps: list[int]) -> list[dict]:
    """Construct synthetic rows producing the given completed-window jumps."""
    rows = []
    completed = 0
    t = 0.0
    epoch = 0.0
    for jump in boundary_jumps:
        rows.append(
            {
                "t_monotonic": t,
                "ul_hysteresis_window_start_epoch": epoch,
                "ul_suppressions_completed_window_count": completed,
                "suppressions_per_min": 0,
                "ul_suppressions_completed_window_by_cause": {
                    "dwell_hold": completed,
                    "backlog_recovery": 0,
                    "other": 0,
                },
            }
        )
        t += 60.0
        epoch = t
        completed = jump
        rows.append(
            {
                "t_monotonic": t,
                "ul_hysteresis_window_start_epoch": epoch,
                "ul_suppressions_completed_window_count": completed,
                "suppressions_per_min": 0,
                "ul_suppressions_completed_window_by_cause": {
                    "dwell_hold": completed,
                    "backlog_recovery": 0,
                    "other": 0,
                },
            }
        )
    return rows


class TestWatchdogMath:
    """CALIB-03 dual-emission shape and new-gate verdict math."""

    def test_legacy_block_shape(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10]),
            legacy_threshold=5.0,
            new_threshold=100,
            statistic="p99",
            gate_column="by_cause.dwell_hold",
        )
        assert set(result) == {"secondary_gate_legacy", "secondary_gate_completed_window"}
        legacy = result["secondary_gate_legacy"]
        assert {
            "name",
            "computation",
            "value",
            "threshold",
            "window_count",
            "verdict",
            "note",
        } <= set(legacy)

    def test_new_block_loads_from_calib_02(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
        block = result["secondary_gate_completed_window"]
        assert block["threshold"] == 125
        assert block["statistic"] == "p99"
        assert block["headroom_factor"] == 1.5
        assert block["gate_column"] == "by_cause.dwell_hold"

    def test_synthetic_pass_branch(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10, 10, 10]),
            new_threshold=100,
            statistic="p99",
            gate_column="by_cause.dwell_hold",
        )
        block = result["secondary_gate_completed_window"]
        assert block["value"] == pytest.approx(10.0)
        assert block["verdict"] == "pass"

    def test_synthetic_fail_branch(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([200, 200, 200]),
            new_threshold=100,
            statistic="p99",
            gate_column="by_cause.dwell_hold",
        )
        block = result["secondary_gate_completed_window"]
        assert block["value"] == pytest.approx(200.0)
        assert block["verdict"] == "fail"

    def test_loader_returns_operator_approved_constants(self, aggregator: ModuleType) -> None:
        constants = aggregator.load_calib_02_constants()
        assert constants["statistic"] == "p99"
        assert constants["threshold"] == 125
        assert constants["gate_column"] == "by_cause.dwell_hold"


class TestV142WatchdogRegression:
    """CALIB-03 transition oracle: legacy live-counter mean must match v1.42."""

    def test_legacy_value_matches_inline_jq_oracle(self, aggregator: ModuleType) -> None:
        if not V142_NDJSON.exists():
            pytest.skip(f"v1.42 reference fixture absent at {V142_NDJSON}")
        rows = aggregator.load_ndjson(V142_NDJSON)
        result = aggregator.aggregate_watchdog(
            rows,
            legacy_threshold=5.0,
            new_threshold=75,
            statistic="p99",
        )
        assert result["secondary_gate_legacy"]["value"] == pytest.approx(
            6.466842364880155, abs=1e-6
        )

    def test_legacy_verdict_against_v142_threshold(self, aggregator: ModuleType) -> None:
        if not V142_NDJSON.exists():
            pytest.skip(f"v1.42 reference fixture absent at {V142_NDJSON}")
        rows = aggregator.load_ndjson(V142_NDJSON)
        result = aggregator.aggregate_watchdog(
            rows,
            legacy_threshold=5.0,
            new_threshold=75,
            statistic="p99",
        )
        assert result["secondary_gate_legacy"]["verdict"] == "fail"

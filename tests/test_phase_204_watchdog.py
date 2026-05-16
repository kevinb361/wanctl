"""Phase 204 CALIB-03 watchdog aggregation tests.

The completed-window block is the D-14 successor gate and reads
operator-approved constants from ``scripts/calib_02_threshold.json`` through
``aggregate_soak()``. HRDN-03 closed the v1.42→v1.44 transition by removing
the legacy watchdog block.
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

# TOOL-01: secondary-gate block contract — exactly these 10 keys.
EXPECTED_SECONDARY_GATE_KEYS = frozenset(
    {
        "name",
        "computation",
        "value",
        "threshold",
        "statistic",
        "headroom_factor",
        "gate_column",
        "verdict",
        "reason",
        "operator_approval",
    }
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
    """CALIB-03 completed-window gate verdict math."""

    def test_new_block_loads_from_calib_02(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
        block = result["secondary_gate_completed_window"]
        assert block["threshold"] == 175
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
        assert constants["threshold"] == 175
        assert constants["gate_column"] == "by_cause.dwell_hold"

    def test_unknown_gate_column_cause_fails_closed(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10]),
            new_threshold=100,
            statistic="p99",
            gate_column="by_cause.bogus_cause",
        )
        assert set(result) == {"secondary_gate_completed_window"}
        block = result["secondary_gate_completed_window"]
        assert set(block) == EXPECTED_SECONDARY_GATE_KEYS, (
            f"block keys drifted: {set(block) ^ EXPECTED_SECONDARY_GATE_KEYS}"
        )
        assert block["verdict"] == "fail"
        assert block["value"] == 0.0
        assert block["reason"] is not None
        assert "bogus_cause" in block["reason"]

    def test_unknown_top_level_gate_column_fails_closed(
        self, aggregator: ModuleType
    ) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10]),
            new_threshold=100,
            statistic="p99",
            gate_column="totally_unknown_column",
        )
        block = result["secondary_gate_completed_window"]
        assert set(block) == EXPECTED_SECONDARY_GATE_KEYS
        assert block["verdict"] == "fail"
        assert block["value"] == 0.0
        assert block["reason"] is not None
        assert "totally_unknown_column" in block["reason"]

    def test_unsupported_statistic_fails_closed(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10]),
            new_threshold=100,
            statistic="p42",
            gate_column="by_cause.dwell_hold",
        )
        block = result["secondary_gate_completed_window"]
        assert set(block) == EXPECTED_SECONDARY_GATE_KEYS
        assert block["verdict"] == "fail"
        assert block["value"] == 0.0
        assert block["reason"] is not None
        assert "p42" in block["reason"]

    def test_valid_config_shape_regression(self, aggregator: ModuleType) -> None:
        """Regression guard: valid pass path still emits the same 10-key shape."""
        result = aggregator.aggregate_watchdog(
            _make_rows([1, 2, 3]),
            new_threshold=100,
            statistic="p99",
            gate_column="suppressions_completed_window_count_distribution",
        )
        block = result["secondary_gate_completed_window"]
        assert set(block) == EXPECTED_SECONDARY_GATE_KEYS
        assert block["verdict"] == "pass"


class TestLegacyGateRemovalContract:
    """HRDN-03 (Phase 207, v1.44): assert secondary_gate_legacy is gone end-to-end.

    Positive-removal contract: the transition cycle from v1.42 → v1.44 is
    closed; only the completed-window dual gate is emitted.
    """

    def test_aggregate_watchdog_returns_only_completed_window_key(
        self, aggregator: ModuleType
    ) -> None:
        result = aggregator.aggregate_watchdog(
            _make_rows([10]),
            new_threshold=100,
            statistic="p99",
            gate_column="by_cause.dwell_hold",
        )
        assert set(result) == {"secondary_gate_completed_window"}

    def test_aggregate_soak_summary_omits_removed_legacy_gate(
        self, aggregator: ModuleType
    ) -> None:
        result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
        assert "secondary_gate_legacy" not in result
        assert "secondary_gate_completed_window" in result

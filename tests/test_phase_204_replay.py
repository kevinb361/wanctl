"""Phase 204 replay tests for CALIB-03 watchdog integration.

This sibling to ``tests/test_phase_204_watchdog.py`` keeps the historical v1.42
NDJSON replay focused on aggregate_soak() integration: the new top-level gate
blocks must appear without drifting the Phase 203 diagnostic math.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATOR_PATH = REPO_ROOT / "scripts" / "soak_summary_aggregate.py"
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
V142_SUMMARY = V142_NDJSON.with_name("soak-summary.json")


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def aggregator() -> ModuleType:
    return _load_module(AGGREGATOR_PATH, "soak_aggregator_phase_204_replay")


class TestV142NdjsonRegressionPhase204:
    """Backward-compat replay plus completed-window gate presence (v1.44 legacy gate removed; HRDN-03)."""

    def test_aggregate_soak_v142_emits_only_completed_window_gate(
        self, aggregator: ModuleType
    ) -> None:
        if not V142_NDJSON.exists():
            pytest.skip(f"v1.42 reference fixture absent at {V142_NDJSON}")
        result = aggregator.aggregate_soak(V142_NDJSON)
        assert "secondary_gate_legacy" not in result
        assert "secondary_gate_completed_window" in result

    def test_diagnostic_distribution_phase_203_unaffected(
        self, aggregator: ModuleType
    ) -> None:
        if not V142_NDJSON.exists() or not V142_SUMMARY.exists():
            pytest.skip(f"v1.42 reference fixtures absent at {V142_NDJSON}")
        result = aggregator.aggregate_soak(V142_NDJSON)
        v142 = json.loads(V142_SUMMARY.read_text(encoding="utf-8"))
        ours = result["diagnostic_distribution"]
        v142_diag = v142["diagnostic_distribution"]
        assert ours["rtt_integral_ms_s"]["mean"] == pytest.approx(
            v142_diag["rtt_integral_ms_s"]["mean"], rel=0.01
        )

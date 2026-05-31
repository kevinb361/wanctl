"""Executable contract tests for the Phase 220 matrix aggregator."""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import pytest
import yaml

FIXTURES = Path(__file__).parent / "fixtures/phase220"
SCENARIOS = FIXTURES / "scenarios"
AGGREGATOR_PATH = Path(__file__).parents[1] / "scripts/phase220-matrix-aggregator.py"
PIN_MWU_1 = 0.0
PIN_MWU_2 = 0.26748958
PIN_BOOTSTRAP_1 = (-2.0, -2.0)
PIN_BOOTSTRAP_2 = (-2.0, 1.0)


def load_aggregator():
    spec = importlib.util.spec_from_file_location("phase220_matrix_aggregator", AGGREGATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scenario(name: str) -> Path:
    return SCENARIOS / name


def test_matrix_verdict_all_clean_yields_hypothesis_killed():
    result = load_aggregator().aggregate_scenario(scenario("all-clean.yaml"))
    assert result["matrix_verdict"] == "hypothesis_killed"


def test_matrix_verdict_single_window_non_reproduced_carries():
    result = load_aggregator().aggregate_scenario(scenario("single-window-non-reproduced.yaml"))
    assert result["matrix_verdict"] == "carried_narrower_with_close_with_prejudice_rule"


def test_matrix_verdict_two_window_non_corroborated_carries():
    result = load_aggregator().aggregate_scenario(scenario("two-window-non-corroborated.yaml"))
    assert result["matrix_verdict"] == "carried_narrower_with_close_with_prejudice_rule"
    assert result["orthogonal_corroboration"]["driver_orthogonal"] is False


def test_matrix_verdict_path_orthogonal_corroborated_defect():
    result = load_aggregator().aggregate_scenario(scenario("path-orthogonal-corroborated-defect.yaml"))
    assert result["matrix_verdict"] == "defect_located"
    assert result["orthogonal_corroboration"]["path_orthogonal"] is True


def test_matrix_verdict_driver_orthogonal_corroborated_defect():
    result = load_aggregator().aggregate_scenario(scenario("driver-orthogonal-corroborated-defect.yaml"))
    assert result["matrix_verdict"] == "defect_located"
    assert result["orthogonal_corroboration"]["driver_orthogonal"] is True


def test_canonical_never_aggregated_with_supplemental():
    result = load_aggregator().aggregate_scenario(scenario("path-orthogonal-corroborated-defect.yaml"))
    assert "canonical_dallas" in result["per_target_rollup"]
    assert "vultr-dallas" in result["per_target_rollup"]
    assert "dallas" not in result["per_target_rollup"]


def test_per_axis_rollup_distinct_from_matrix_verdict():
    result = load_aggregator().aggregate_scenario(scenario("path-orthogonal-corroborated-defect.yaml"))
    assert {"per_target_rollup", "per_path_rollup", "per_window_rollup", "matrix_verdict"}.issubset(result)
    assert result["per_path_rollup"]["att"] == "defect"
    assert result["matrix_verdict"] == "defect_located"


def test_mwu_golden_pin_1_large_effect():
    result = load_aggregator().mann_whitney_u([1.0] * 60, [3.0] * 60)
    assert result["p"] == pytest.approx(PIN_MWU_1, abs=1e-8)
    assert result["tie_correction"] == "wilcoxon-mid-rank"


def test_mwu_golden_pin_2_uniform_null():
    rng = random.Random(220)
    x = [float(value) for value in rng.choices(list(range(1, 11)), k=90)]
    y = [float(value) for value in rng.choices(list(range(1, 11)), k=90)]
    result = load_aggregator().mann_whitney_u(x, y)
    assert result["p"] == pytest.approx(PIN_MWU_2, abs=1e-8)


def test_bootstrap_ci_golden_pin_1_constant_arms():
    result = load_aggregator().bootstrap_ci_median_difference([1.0] * 60, [3.0] * 60)
    assert (result["ci_lower"], result["ci_upper"]) == pytest.approx(PIN_BOOTSTRAP_1, abs=1e-8)


def test_bootstrap_ci_golden_pin_2_uniform():
    rng = random.Random(220)
    x = [float(value) for value in rng.choices(list(range(1, 11)), k=90)]
    y = [float(value) for value in rng.choices(list(range(1, 11)), k=90)]
    result = load_aggregator().bootstrap_ci_median_difference(x, y)
    assert (result["ci_lower"], result["ci_upper"]) == pytest.approx(PIN_BOOTSTRAP_2, abs=1e-8)


def test_mwu_degenerate_returns_dict_with_p_none():
    result = load_aggregator().mann_whitney_u([], [1.0])
    assert result["degenerate"] is True
    assert result["p"] is None


def test_bootstrap_degenerate_returns_dict_with_ci_none():
    result = load_aggregator().bootstrap_ci_median_difference([], [1.0])
    assert result["degenerate"] is True
    assert result["ci_lower"] is None
    assert result["ci_upper"] is None


def test_driver_allowlist_loaded_from_yaml():
    aggregator = load_aggregator()
    definition = aggregator.load_matrix_definition(Path("scripts/phase220-matrix.yaml"))
    assert definition["driver_allowlist"] == ["reflector_loss", "cake_queue_mismatch"]
    assert aggregator.cell_verdict(
        {"target_kind": "supplemental", "is_canonical": False, "median_p99_ms": 900.0, "primary_driver": "external_path"},
        120.0,
        driver_allowlist=definition["driver_allowlist_set"],
        thresholds=definition["thresholds"],
    ) == "cell_carry"


def test_driver_orthogonal_requires_distinct_target_or_path():
    aggregator = load_aggregator()
    thresholds = yaml.safe_load(Path("scripts/phase220-matrix.yaml").read_text())["thresholds"]
    allowlist = {"reflector_loss", "cake_queue_mismatch"}
    same_pair_cells = [
        {"cell_id": "dallas__spectrum__daytime", "target_name": "dallas", "target_kind": "canonical", "path_name": "spectrum", "window_name": "daytime", "is_canonical": True, "median_p99_ms": 120.0, "primary_driver": None},
        {"cell_id": "dallas__spectrum__prime-time", "target_name": "dallas", "target_kind": "canonical", "path_name": "spectrum", "window_name": "prime-time", "is_canonical": True, "median_p99_ms": 120.0, "primary_driver": None},
        {"cell_id": "vultr-dallas__spectrum__daytime", "target_name": "vultr-dallas", "target_kind": "supplemental", "path_name": "spectrum", "window_name": "daytime", "is_canonical": False, "median_p99_ms": 610.0, "primary_driver": "reflector_loss"},
        {"cell_id": "vultr-dallas__spectrum__prime-time", "target_name": "vultr-dallas", "target_kind": "supplemental", "path_name": "spectrum", "window_name": "prime-time", "is_canonical": False, "median_p99_ms": 580.0, "primary_driver": "reflector_loss"},
    ]
    same_result = aggregator.matrix_verdict(same_pair_cells, thresholds=thresholds, driver_allowlist=allowlist)
    assert same_result["orthogonal_corroboration"]["driver_orthogonal"] is False
    assert same_result["matrix_verdict"] == "carried_narrower_with_close_with_prejudice_rule"

    different_pair_cells = [
        *same_pair_cells,
        {"cell_id": "vultr-chicago__att__daytime", "target_name": "vultr-chicago", "target_kind": "supplemental", "path_name": "att", "window_name": "daytime", "is_canonical": False, "median_p99_ms": 550.0, "primary_driver": "reflector_loss"},
    ]
    different_result = aggregator.matrix_verdict(different_pair_cells, thresholds=thresholds, driver_allowlist=allowlist)
    assert different_result["orthogonal_corroboration"]["driver_orthogonal"] is True
    assert different_result["matrix_verdict"] == "defect_located"


def test_replicate_aggregation_median_p99_three_replicates():
    result = load_aggregator().aggregate_scenario(scenario("three-replicate-outlier.yaml"))
    assert result["per_cell"]["vultr-dallas__spectrum__daytime"]["median_p99_ms"] == 610.0


def test_replicate_aggregation_single_outlier_absorbed():
    aggregator = load_aggregator()
    assert aggregator.collapse_replicate_p99([120.0, 800.0, 130.0]) == 130.0
    verdict = aggregator.cell_verdict(
        {"target_kind": "canonical", "is_canonical": True, "median_p99_ms": 130.0, "primary_driver": None},
        None,
        driver_allowlist={"reflector_loss", "cake_queue_mismatch"},
        thresholds={"canonical_control_p99_kill_ms": 200},
    )
    assert verdict == "cell_kill_clear"

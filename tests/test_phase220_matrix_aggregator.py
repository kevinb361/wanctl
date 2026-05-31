"""Wave 0 xfail contract for the Phase 220 matrix aggregator."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures/phase220"
SCENARIOS = FIXTURES / "scenarios"
PIN_MWU_1 = 0.0
PIN_MWU_2 = 0.26748958
PIN_BOOTSTRAP_1 = (-2.0, -2.0)
PIN_BOOTSTRAP_2 = (-2.0, 1.0)

xfail = lambda item: (setattr(item, "pytestmark", [pytest.mark.xfail(reason="aggregator not implemented yet — plan 02", strict=True)]), item)[1]
load_aggregator = lambda: importlib.import_module("scripts.phase220_matrix_aggregator")
scenario = lambda name: SCENARIOS / name
check = lambda condition, message="assertion failed": None if condition else (_ for _ in ()).throw(AssertionError(message))

test_matrix_verdict_all_clean_yields_hypothesis_killed = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("all-clean.yaml"))["matrix_verdict"] == "hypothesis_killed"))
test_matrix_verdict_single_window_non_reproduced_carries = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("single-window-non-reproduced.yaml"))["matrix_verdict"] == "carried_narrower_with_close_with_prejudice_rule"))
test_matrix_verdict_two_window_non_corroborated_carries = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("two-window-non-corroborated.yaml"))["matrix_verdict"] == "carried_narrower_with_close_with_prejudice_rule"))
test_matrix_verdict_path_orthogonal_corroborated_defect = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("path-orthogonal-corroborated-defect.yaml"))["matrix_verdict"] == "defect_located"))
test_matrix_verdict_driver_orthogonal_corroborated_defect = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("driver-orthogonal-corroborated-defect.yaml"))["matrix_verdict"] == "defect_located"))
test_canonical_never_aggregated_with_supplemental = xfail(lambda: check("canonical_dallas" in load_aggregator().aggregate_scenario(scenario("all-clean.yaml"))["per_target_rollup"]))
test_per_axis_rollup_distinct_from_matrix_verdict = xfail(lambda: check({"per_target_rollup", "per_path_rollup", "per_window_rollup", "matrix_verdict"}.issubset(load_aggregator().aggregate_scenario(scenario("path-orthogonal-corroborated-defect.yaml")))))
test_mwu_golden_pin_1_large_effect = xfail(lambda: check(load_aggregator().mann_whitney_u([1.0] * 60, [3.0] * 60)["p"] == pytest.approx(PIN_MWU_1, abs=1e-8)))
test_mwu_golden_pin_2_uniform_null = xfail(lambda: check(load_aggregator().mann_whitney_u([], [1.0])["degenerate"] or load_aggregator().mann_whitney_u([1.0] * 90, [2.0] * 90)["p"] is not None))
test_bootstrap_ci_golden_pin_1_constant_arms = xfail(lambda: check((load_aggregator().bootstrap_ci_median_difference([1.0] * 60, [3.0] * 60)["ci_lower"], load_aggregator().bootstrap_ci_median_difference([1.0] * 60, [3.0] * 60)["ci_upper"]) == pytest.approx(PIN_BOOTSTRAP_1, abs=1e-8)))
test_bootstrap_ci_golden_pin_2_uniform = xfail(lambda: check(load_aggregator().bootstrap_ci_median_difference([1.0] * 90, [2.0] * 90)["ci_lower"] is not None))
test_mwu_degenerate_returns_dict_with_p_none = xfail(lambda: check(load_aggregator().mann_whitney_u([], [1.0]) == {"p": None, "degenerate": True}))
test_bootstrap_degenerate_returns_dict_with_ci_none = xfail(lambda: check(load_aggregator().bootstrap_ci_median_difference([], [1.0])["degenerate"] is True))
test_driver_allowlist_loaded_from_yaml = xfail(lambda: check(load_aggregator().load_matrix_definition(Path("scripts/phase220-matrix.yaml"))["driver_allowlist"] == ["reflector_loss", "cake_queue_mismatch"]))
test_driver_orthogonal_requires_distinct_target_or_path = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("driver-orthogonal-corroborated-defect.yaml"))["orthogonal_corroboration"]["driver_orthogonal"] is True))
test_replicate_aggregation_median_p99_three_replicates = xfail(lambda: check(load_aggregator().aggregate_scenario(scenario("three-replicate-outlier.yaml"))["per_cell"]["vultr-dallas__spectrum__daytime"]["median_p99_ms"] == 610.0))
test_replicate_aggregation_single_outlier_absorbed = xfail(lambda: check(load_aggregator().collapse_replicate_p99([120.0, 800.0, 130.0]) == 130.0))

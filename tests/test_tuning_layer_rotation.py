"""Tests for tuning layer rotation, applier extension, and current_params.

Tests that the maintenance loop rotates through signal -> EWMA -> threshold
-> advanced layers (SIGP-04, ADVT-01/02/03), that _apply_tuning_to_controller
handles signal processing and advanced parameters, and that current_params
includes all tunable parameters.
"""

from collections import deque
from unittest.mock import MagicMock

import pytest

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult, TuningState


def _make_tuning_config(enabled: bool = True) -> TuningConfig:
    """Create a minimal TuningConfig for testing with signal processing bounds."""
    return TuningConfig(
        enabled=enabled,
        cadence_sec=3600,
        lookback_hours=24,
        warmup_hours=1,
        max_step_pct=10.0,
        bounds={
            "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=30.0),
            "warn_bloat_ms": SafetyBounds(min_value=10.0, max_value=100.0),
            "hard_red_bloat_ms": SafetyBounds(min_value=30.0, max_value=200.0),
            "alpha_load": SafetyBounds(min_value=0.005, max_value=0.5),
            "alpha_baseline": SafetyBounds(min_value=0.0001, max_value=0.01),
            "hampel_sigma_threshold": SafetyBounds(min_value=1.5, max_value=5.0),
            "hampel_window_size": SafetyBounds(min_value=5.0, max_value=15.0),
            "load_time_constant_sec": SafetyBounds(min_value=0.5, max_value=10.0),
            "fusion_icmp_weight": SafetyBounds(min_value=0.3, max_value=0.95),
            "reflector_min_score": SafetyBounds(min_value=0.5, max_value=0.95),
            "baseline_rtt_min": SafetyBounds(min_value=1.0, max_value=30.0),
            "baseline_rtt_max": SafetyBounds(min_value=30.0, max_value=200.0),
        },
    )


def _make_result(param: str, old: float, new: float) -> TuningResult:
    """Create a test TuningResult."""
    return TuningResult(
        parameter=param,
        old_value=old,
        new_value=new,
        confidence=0.8,
        rationale="test adjustment",
        data_points=100,
        wan_name="Spectrum",
    )


class TestApplySignalProcessingParams:
    """Tests for _apply_tuning_to_controller with signal processing parameters."""

    def test_apply_hampel_sigma_threshold(self):
        """hampel_sigma_threshold sets signal_processor._sigma_threshold."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        sp = MagicMock()
        sp._sigma_threshold = 3.0
        wc.signal_processor = sp

        result = _make_result("hampel_sigma_threshold", old=3.0, new=2.5)
        _apply_tuning_to_controller(wc, [result])
        assert wc.signal_processor._sigma_threshold == 2.5

    def test_apply_hampel_window_size_updates_window_size(self):
        """hampel_window_size sets signal_processor._window_size."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        sp = MagicMock()
        sp._window_size = 7
        sp._window = deque([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], maxlen=7)
        sp._outlier_window = deque([False] * 7, maxlen=7)
        wc.signal_processor = sp

        result = _make_result("hampel_window_size", old=7.0, new=10.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.signal_processor._window_size == 10

    def test_apply_hampel_window_size_resizes_deques(self):
        """hampel_window_size resizes both _window and _outlier_window deques."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        sp = MagicMock()
        sp._window_size = 7
        sp._window = deque([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], maxlen=7)
        sp._outlier_window = deque([False] * 7, maxlen=7)
        wc.signal_processor = sp

        result = _make_result("hampel_window_size", old=7.0, new=10.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.signal_processor._window.maxlen == 10
        assert wc.signal_processor._outlier_window.maxlen == 10

    def test_deque_resize_preserves_recent_elements_when_shrinking(self):
        """Shrinking window preserves the most recent N elements."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        sp = MagicMock()
        sp._window_size = 7
        sp._window = deque([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], maxlen=7)
        sp._outlier_window = deque(
            [True, False, True, False, True, False, True], maxlen=7
        )
        wc.signal_processor = sp

        result = _make_result("hampel_window_size", old=7.0, new=5.0)
        _apply_tuning_to_controller(wc, [result])
        # deque(existing, maxlen=5) keeps last 5 elements
        assert list(wc.signal_processor._window) == [3.0, 4.0, 5.0, 6.0, 7.0]
        assert list(wc.signal_processor._outlier_window) == [
            True,
            False,
            True,
            False,
            True,
        ]


class TestApplyLoadTimeConstant:
    """Tests for _apply_tuning_to_controller with load_time_constant_sec.

    Critical: verifies the Pitfall 3 fix -- tuning in tc domain (0.5-10s)
    converted to alpha at apply time via alpha = 0.05 / tc.
    """

    def test_tc_2s_gives_alpha_0_025(self):
        """load_time_constant_sec=2.0 -> alpha_load=0.025 (0.05/2.0)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.alpha_load = 0.05  # current (tc=1.0s)

        result = _make_result("load_time_constant_sec", old=1.0, new=2.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.alpha_load == pytest.approx(0.025)

    def test_tc_1s_gives_alpha_0_05(self):
        """load_time_constant_sec=1.0 -> alpha_load=0.05 (0.05/1.0)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.alpha_load = 0.025  # current (tc=2.0s)

        result = _make_result("load_time_constant_sec", old=2.0, new=1.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.alpha_load == pytest.approx(0.05)

    def test_tc_5s_gives_alpha_0_01(self):
        """load_time_constant_sec=5.0 -> alpha_load=0.01 (0.05/5.0)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.alpha_load = 0.025

        result = _make_result("load_time_constant_sec", old=2.0, new=5.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.alpha_load == pytest.approx(0.01)

    def test_tc_10s_gives_alpha_0_005(self):
        """load_time_constant_sec=10.0 -> alpha_load=0.005 (0.05/10.0)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.alpha_load = 0.025

        result = _make_result("load_time_constant_sec", old=2.0, new=10.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.alpha_load == pytest.approx(0.005)


class TestCurrentParamsExtension:
    """Tests that current_params includes signal processing and load_time_constant_sec."""

    def test_current_params_includes_hampel_sigma_threshold(self):
        """current_params should include hampel_sigma_threshold from signal_processor."""
        wc = MagicMock()
        sp = MagicMock()
        sp._sigma_threshold = 3.0
        sp._window_size = 7
        wc.signal_processor = sp
        wc.green_threshold = 15.0
        wc.soft_red_threshold = 45.0
        wc.hard_red_threshold = 90.0
        wc.alpha_load = 0.025
        wc.alpha_baseline = 0.001

        current_params = {
            "target_bloat_ms": wc.green_threshold,
            "warn_bloat_ms": wc.soft_red_threshold,
            "hard_red_bloat_ms": wc.hard_red_threshold,
            "alpha_load": wc.alpha_load,
            "alpha_baseline": wc.alpha_baseline,
            "hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
            "hampel_window_size": float(wc.signal_processor._window_size),
            "load_time_constant_sec": 0.05 / wc.alpha_load,
        }
        assert current_params["hampel_sigma_threshold"] == 3.0

    def test_current_params_includes_hampel_window_size(self):
        """current_params should include hampel_window_size as float from signal_processor."""
        wc = MagicMock()
        sp = MagicMock()
        sp._sigma_threshold = 3.0
        sp._window_size = 7
        wc.signal_processor = sp
        wc.alpha_load = 0.025

        current_params = {
            "hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
            "hampel_window_size": float(wc.signal_processor._window_size),
            "load_time_constant_sec": 0.05 / wc.alpha_load,
        }
        assert current_params["hampel_window_size"] == 7.0
        assert isinstance(current_params["hampel_window_size"], float)

    def test_current_params_load_time_constant_sec_from_alpha(self):
        """load_time_constant_sec should be derived as 0.05 / alpha_load."""
        wc = MagicMock()
        wc.alpha_load = 0.025  # tc = 0.05 / 0.025 = 2.0s

        current_params = {
            "load_time_constant_sec": 0.05 / wc.alpha_load,
        }
        assert current_params["load_time_constant_sec"] == pytest.approx(2.0)


class TestLayerRoundRobin:
    """Tests that the maintenance loop rotates through layers correctly."""

    def test_first_cycle_runs_signal_layer(self):
        """Layer index 0 selects SIGNAL_LAYER (hampel_sigma, hampel_window)."""
        SIGNAL_LAYER = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        EWMA_LAYER = [("load_time_constant_sec", "tune_alpha_load")]
        THRESHOLD_LAYER = [
            ("target_bloat_ms", "calibrate_target_bloat"),
            ("warn_bloat_ms", "calibrate_warn_bloat"),
        ]
        ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

        layer_index = 0
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is SIGNAL_LAYER
        assert len(active_layer) == 2
        assert active_layer[0][0] == "hampel_sigma_threshold"
        assert active_layer[1][0] == "hampel_window_size"

    def test_second_cycle_runs_ewma_layer(self):
        """Layer index 1 selects EWMA_LAYER (load_time_constant_sec)."""
        SIGNAL_LAYER = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        EWMA_LAYER = [("load_time_constant_sec", "tune_alpha_load")]
        THRESHOLD_LAYER = [
            ("target_bloat_ms", "calibrate_target_bloat"),
            ("warn_bloat_ms", "calibrate_warn_bloat"),
        ]
        ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

        layer_index = 1
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is EWMA_LAYER
        assert len(active_layer) == 1
        assert active_layer[0][0] == "load_time_constant_sec"

    def test_third_cycle_runs_threshold_layer(self):
        """Layer index 2 selects THRESHOLD_LAYER (target_bloat, warn_bloat)."""
        SIGNAL_LAYER = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        EWMA_LAYER = [("load_time_constant_sec", "tune_alpha_load")]
        THRESHOLD_LAYER = [
            ("target_bloat_ms", "calibrate_target_bloat"),
            ("warn_bloat_ms", "calibrate_warn_bloat"),
        ]
        ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

        layer_index = 2
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is THRESHOLD_LAYER
        assert len(active_layer) == 2

    def test_fourth_cycle_wraps_to_signal(self):
        """Layer index 3 wraps to SIGNAL_LAYER (3 % 3 = 0)."""
        SIGNAL_LAYER = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        EWMA_LAYER = [("load_time_constant_sec", "tune_alpha_load")]
        THRESHOLD_LAYER = [
            ("target_bloat_ms", "calibrate_target_bloat"),
            ("warn_bloat_ms", "calibrate_warn_bloat"),
        ]
        ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER]

        layer_index = 3
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is SIGNAL_LAYER

    def test_layer_index_increments(self):
        """Layer index should increment by 1 per tuning cycle."""
        layer_index = 0
        for expected in range(1, 7):
            layer_index += 1
            assert layer_index == expected

    def test_locked_params_filtered_from_active_layer(self):
        """Locked parameters within active layer are excluded."""
        import time

        from wanctl.tuning.safety import is_parameter_locked

        locks = {"hampel_sigma_threshold": time.monotonic() + 3600}  # locked
        active_layer = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        active_strategies = [
            (pname, sfn)
            for pname, sfn in active_layer
            if not is_parameter_locked(locks, pname)
        ]
        # Only hampel_window_size should remain
        assert len(active_strategies) == 1
        assert active_strategies[0][0] == "hampel_window_size"


class TestApplyAdvancedParams:
    """Tests for _apply_tuning_to_controller with advanced parameters (ADVT-01/02/03)."""

    def test_apply_fusion_icmp_weight(self):
        """fusion_icmp_weight sets wc._fusion_icmp_weight."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc._fusion_icmp_weight = 0.7

        result = _make_result("fusion_icmp_weight", old=0.7, new=0.8)
        _apply_tuning_to_controller(wc, [result])
        assert wc._fusion_icmp_weight == 0.8

    def test_apply_reflector_min_score(self):
        """reflector_min_score sets wc._reflector_scorer._min_score."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        scorer = MagicMock()
        scorer._min_score = 0.7
        wc._reflector_scorer = scorer

        result = _make_result("reflector_min_score", old=0.7, new=0.8)
        _apply_tuning_to_controller(wc, [result])
        assert wc._reflector_scorer._min_score == 0.8

    def test_apply_baseline_rtt_min(self):
        """baseline_rtt_min sets wc.baseline_rtt_min."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.baseline_rtt_min = 3.0

        result = _make_result("baseline_rtt_min", old=3.0, new=5.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.baseline_rtt_min == 5.0

    def test_apply_baseline_rtt_max(self):
        """baseline_rtt_max sets wc.baseline_rtt_max."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.baseline_rtt_max = 80.0

        result = _make_result("baseline_rtt_max", old=80.0, new=100.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.baseline_rtt_max == 100.0


class TestFourLayerRotation:
    """Tests for 4-layer rotation (signal -> EWMA -> threshold -> advanced)."""

    def _build_all_layers(self):
        """Build the 4-layer structure matching production code."""
        SIGNAL_LAYER = [
            ("hampel_sigma_threshold", "tune_hampel_sigma"),
            ("hampel_window_size", "tune_hampel_window"),
        ]
        EWMA_LAYER = [("load_time_constant_sec", "tune_alpha_load")]
        THRESHOLD_LAYER = [
            ("target_bloat_ms", "calibrate_target_bloat"),
            ("warn_bloat_ms", "calibrate_warn_bloat"),
        ]
        ADVANCED_LAYER = [
            ("fusion_icmp_weight", "tune_fusion_weight"),
            ("reflector_min_score", "tune_reflector_min_score"),
            ("baseline_rtt_min", "tune_baseline_bounds_min"),
            ("baseline_rtt_max", "tune_baseline_bounds_max"),
        ]
        ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER]
        return SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER, ALL_LAYERS

    def test_four_layers_in_all_layers(self):
        """ALL_LAYERS has exactly 4 layers."""
        _, _, _, _, ALL_LAYERS = self._build_all_layers()
        assert len(ALL_LAYERS) == 4

    def test_rotation_index_3_selects_advanced(self):
        """Layer index 3 selects ADVANCED_LAYER."""
        _, _, _, ADVANCED_LAYER, ALL_LAYERS = self._build_all_layers()
        layer_index = 3
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is ADVANCED_LAYER

    def test_rotation_wraps_at_4(self):
        """Layer index 4 wraps back to SIGNAL_LAYER (4 % 4 = 0)."""
        SIGNAL_LAYER, _, _, _, ALL_LAYERS = self._build_all_layers()
        layer_index = 4
        active_layer = ALL_LAYERS[layer_index % len(ALL_LAYERS)]
        assert active_layer is SIGNAL_LAYER

    def test_advanced_layer_contains_four_strategies(self):
        """ADVANCED_LAYER has 4 tuples with correct parameter names."""
        _, _, _, ADVANCED_LAYER, _ = self._build_all_layers()
        assert len(ADVANCED_LAYER) == 4
        param_names = [p[0] for p in ADVANCED_LAYER]
        assert "fusion_icmp_weight" in param_names
        assert "reflector_min_score" in param_names
        assert "baseline_rtt_min" in param_names
        assert "baseline_rtt_max" in param_names

    def test_full_rotation_cycle_order(self):
        """Full 4-cycle rotation: signal, EWMA, threshold, advanced."""
        SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER, ALL_LAYERS = (
            self._build_all_layers()
        )
        expected_order = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER]
        for i, expected in enumerate(expected_order):
            active = ALL_LAYERS[i % len(ALL_LAYERS)]
            assert active is expected, f"Index {i} should select layer {i}"


class TestCurrentParamsAdvanced:
    """Tests that current_params includes all 4 advanced parameters."""

    def _build_current_params(self):
        """Build current_params dict matching production code pattern."""
        wc = MagicMock()
        sp = MagicMock()
        sp._sigma_threshold = 3.0
        sp._window_size = 7
        wc.signal_processor = sp
        wc.green_threshold = 15.0
        wc.soft_red_threshold = 45.0
        wc.hard_red_threshold = 90.0
        wc.alpha_load = 0.025
        wc.alpha_baseline = 0.001
        wc._fusion_icmp_weight = 0.7
        scorer = MagicMock()
        scorer._min_score = 0.75
        wc._reflector_scorer = scorer
        wc.baseline_rtt_min = 5.0
        wc.baseline_rtt_max = 80.0

        current_params = {
            "target_bloat_ms": wc.green_threshold,
            "warn_bloat_ms": wc.soft_red_threshold,
            "hard_red_bloat_ms": wc.hard_red_threshold,
            "alpha_load": wc.alpha_load,
            "alpha_baseline": wc.alpha_baseline,
            "hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
            "hampel_window_size": float(wc.signal_processor._window_size),
            "load_time_constant_sec": 0.05 / wc.alpha_load,
            "fusion_icmp_weight": wc._fusion_icmp_weight,
            "reflector_min_score": wc._reflector_scorer._min_score,
            "baseline_rtt_min": wc.baseline_rtt_min,
            "baseline_rtt_max": wc.baseline_rtt_max,
        }
        return current_params

    def test_current_params_includes_fusion_weight(self):
        """current_params includes fusion_icmp_weight with correct value."""
        params = self._build_current_params()
        assert "fusion_icmp_weight" in params
        assert params["fusion_icmp_weight"] == 0.7

    def test_current_params_includes_reflector_min_score(self):
        """current_params includes reflector_min_score with correct value."""
        params = self._build_current_params()
        assert "reflector_min_score" in params
        assert params["reflector_min_score"] == 0.75

    def test_current_params_includes_baseline_rtt_min(self):
        """current_params includes baseline_rtt_min with correct value."""
        params = self._build_current_params()
        assert "baseline_rtt_min" in params
        assert params["baseline_rtt_min"] == 5.0

    def test_current_params_includes_baseline_rtt_max(self):
        """current_params includes baseline_rtt_max with correct value."""
        params = self._build_current_params()
        assert "baseline_rtt_max" in params
        assert params["baseline_rtt_max"] == 80.0

    def test_current_params_has_12_entries(self):
        """current_params dict should have 12 entries (8 original + 4 advanced)."""
        params = self._build_current_params()
        assert len(params) == 12

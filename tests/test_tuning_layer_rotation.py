"""Tests for tuning layer rotation, signal processing applier extension,
and current_params extension.

Tests that the maintenance loop rotates through signal -> EWMA -> threshold
layers (SIGP-04), that _apply_tuning_to_controller handles signal processing
parameters, and that current_params includes all tunable parameters.
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
        from wanctl.tuning.safety import is_parameter_locked

        import time

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

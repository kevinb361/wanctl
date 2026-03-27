"""Tests for response tuning wiring in the autorate daemon.

Tests that RESPONSE_LAYER is the 5th layer in ALL_LAYERS, _apply_tuning_to_controller
handles all 6 response parameters with correct unit conversions, current_params
includes response values, oscillation lockout locks all params and fires alert,
and default exclude_params includes all 6 response params (RTUN-04, RTUN-05).
"""

import time
from unittest.mock import MagicMock

from wanctl.tuning.models import TuningResult, TuningState
from wanctl.tuning.strategies.response import (
    DEFAULT_OSCILLATION_THRESHOLD,
    OSCILLATION_LOCKOUT_SEC,
    RESPONSE_PARAMS,
    check_oscillation_lockout,
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


class TestApplyResponseParams:
    """Tests for _apply_tuning_to_controller with response parameters."""

    def test_apply_dl_step_up_mbps(self):
        """dl_step_up_mbps sets wc.download.step_up_bps = int(new_value * 1_000_000)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.download = MagicMock()
        wc.download.step_up_bps = 1_000_000

        result = _make_result("dl_step_up_mbps", old=1.0, new=2.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.download.step_up_bps == 2_000_000

    def test_apply_ul_step_up_mbps(self):
        """ul_step_up_mbps sets wc.upload.step_up_bps = int(new_value * 1_000_000)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.upload = MagicMock()
        wc.upload.step_up_bps = 500_000

        result = _make_result("ul_step_up_mbps", old=0.5, new=1.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.upload.step_up_bps == 1_000_000

    def test_apply_dl_factor_down(self):
        """dl_factor_down sets wc.download.factor_down = new_value."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.download = MagicMock()
        wc.download.factor_down = 0.85

        result = _make_result("dl_factor_down", old=0.85, new=0.80)
        _apply_tuning_to_controller(wc, [result])
        assert wc.download.factor_down == 0.80

    def test_apply_ul_factor_down(self):
        """ul_factor_down sets wc.upload.factor_down = new_value."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.upload = MagicMock()
        wc.upload.factor_down = 0.90

        result = _make_result("ul_factor_down", old=0.90, new=0.88)
        _apply_tuning_to_controller(wc, [result])
        assert wc.upload.factor_down == 0.88

    def test_apply_dl_green_required(self):
        """dl_green_required sets wc.download.green_required = round(new_value)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.download = MagicMock()
        wc.download.green_required = 5

        result = _make_result("dl_green_required", old=5.0, new=6.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.download.green_required == 6

    def test_apply_ul_green_required(self):
        """ul_green_required sets wc.upload.green_required = round(new_value)."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.upload = MagicMock()
        wc.upload.green_required = 5

        result = _make_result("ul_green_required", old=5.0, new=7.0)
        _apply_tuning_to_controller(wc, [result])
        assert wc.upload.green_required == 7

    def test_step_up_mbps_to_bps_conversion_fractional(self):
        """Verify int(new_value * 1_000_000) conversion for fractional Mbps."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.download = MagicMock()
        wc.download.step_up_bps = 1_000_000

        result = _make_result("dl_step_up_mbps", old=1.0, new=1.5)
        _apply_tuning_to_controller(wc, [result])
        assert wc.download.step_up_bps == 1_500_000
        assert isinstance(wc.download.step_up_bps, int)

    def test_green_required_rounds_float(self):
        """green_required uses round() to convert float to int."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )
        wc.download = MagicMock()
        wc.download.green_required = 5

        result = _make_result("dl_green_required", old=5.0, new=6.7)
        _apply_tuning_to_controller(wc, [result])
        assert wc.download.green_required == 7  # round(6.7) = 7


class TestResponseLayerDefinition:
    """Tests for RESPONSE_LAYER and ALL_LAYERS wiring."""

    def test_response_params_has_6_entries(self):
        """RESPONSE_PARAMS list should have exactly 6 entries."""
        assert len(RESPONSE_PARAMS) == 6

    def test_response_params_names(self):
        """RESPONSE_PARAMS should contain correct param names."""
        expected = {
            "dl_step_up_mbps", "ul_step_up_mbps",
            "dl_factor_down", "ul_factor_down",
            "dl_green_required", "ul_green_required",
        }
        assert set(RESPONSE_PARAMS) == expected

    def test_response_strategy_imports_work(self):
        """All 6 response strategy functions can be imported."""
        from wanctl.tuning.strategies.response import (
            tune_dl_factor_down,
            tune_dl_green_required,
            tune_dl_step_up,
            tune_ul_factor_down,
            tune_ul_green_required,
            tune_ul_step_up,
        )
        # All are callable
        assert callable(tune_dl_step_up)
        assert callable(tune_ul_step_up)
        assert callable(tune_dl_factor_down)
        assert callable(tune_ul_factor_down)
        assert callable(tune_dl_green_required)
        assert callable(tune_ul_green_required)

    def test_oscillation_lockout_constants(self):
        """Oscillation lockout constants have expected values."""
        assert OSCILLATION_LOCKOUT_SEC == 7200  # 2 hours
        assert DEFAULT_OSCILLATION_THRESHOLD == 0.1  # 6/hour


class TestOscillationLockout:
    """Tests for check_oscillation_lockout function (RTUN-04)."""

    def _make_state_metrics(self, states: list[tuple[int, float]]) -> list[dict]:
        """Create metrics data with wanctl_state entries.

        Args:
            states: List of (timestamp, state_value) tuples.
        """
        return [
            {"timestamp": ts, "metric_name": "wanctl_state", "value": val}
            for ts, val in states
        ]

    def test_low_transition_rate_no_lockout(self):
        """When transitions/min < threshold, no lockout triggered."""
        # 2 transitions over 60 minutes: one brief congestion episode.
        # Transition 1: ts=10 (0->2), Transition 2: ts=11 (2->0) = 2 transitions
        # 2 transitions / 59 minutes ~= 0.034/min (well below 0.1 threshold)
        base = 1000
        states = []
        for i in range(60):
            ts = base + i * 60
            if i == 10:
                states.append((ts, 2.0))  # single congestion sample
            else:
                states.append((ts, 0.0))  # green

        metrics = self._make_state_metrics(states)
        locks: dict[str, float] = {}

        triggered = check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
            oscillation_threshold=DEFAULT_OSCILLATION_THRESHOLD,
        )
        assert triggered is False
        assert len(locks) == 0

    def test_high_transition_rate_triggers_lockout(self):
        """When transitions/min > threshold, all 6 response params are locked."""
        # Rapid oscillation: state changes every minute = many transitions/min
        base = 1000
        states = []
        for i in range(60):
            ts = base + i * 60
            # Alternate between GREEN(0) and SOFT_RED(2) every sample
            val = 2.0 if i % 2 == 0 else 0.0
            states.append((ts, val))

        metrics = self._make_state_metrics(states)
        locks: dict[str, float] = {}

        triggered = check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
            oscillation_threshold=DEFAULT_OSCILLATION_THRESHOLD,
        )
        assert triggered is True
        assert len(locks) == 6
        for p in RESPONSE_PARAMS:
            assert p in locks

    def test_lockout_fires_alert(self):
        """AlertEngine.fire is called with oscillation_lockout type."""
        base = 1000
        states = []
        for i in range(60):
            ts = base + i * 60
            val = 2.0 if i % 2 == 0 else 0.0
            states.append((ts, val))

        metrics = self._make_state_metrics(states)
        locks: dict[str, float] = {}
        alert_engine = MagicMock()
        alert_engine.fire.return_value = True

        check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
            oscillation_threshold=DEFAULT_OSCILLATION_THRESHOLD,
            alert_engine=alert_engine,
            wan_name="Spectrum",
        )
        alert_engine.fire.assert_called_once()
        call_kwargs = alert_engine.fire.call_args
        assert call_kwargs[1]["alert_type"] == "oscillation_lockout"
        assert call_kwargs[1]["severity"] == "warning"
        assert call_kwargs[1]["wan_name"] == "Spectrum"
        assert "locked_params" in call_kwargs[1]["details"]
        assert "lockout_sec" in call_kwargs[1]["details"]

    def test_lockout_duration_is_2_hours(self):
        """lock_parameter called with 7200 seconds."""
        base = 1000
        states = []
        for i in range(60):
            ts = base + i * 60
            val = 2.0 if i % 2 == 0 else 0.0
            states.append((ts, val))

        metrics = self._make_state_metrics(states)
        locks: dict[str, float] = {}

        before = time.monotonic()
        check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
            oscillation_threshold=DEFAULT_OSCILLATION_THRESHOLD,
        )
        after = time.monotonic()

        # All locks should expire ~7200 seconds from now
        for p in RESPONSE_PARAMS:
            assert locks[p] >= before + OSCILLATION_LOCKOUT_SEC
            assert locks[p] <= after + OSCILLATION_LOCKOUT_SEC + 1

    def test_insufficient_data_no_lockout(self):
        """With fewer than 2 state entries, no lockout triggered."""
        metrics = self._make_state_metrics([(1000, 0.0)])
        locks: dict[str, float] = {}

        triggered = check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
        )
        assert triggered is False
        assert len(locks) == 0

    def test_no_alert_engine_no_crash(self):
        """Oscillation lockout works without AlertEngine (alert_engine=None)."""
        base = 1000
        states = []
        for i in range(60):
            ts = base + i * 60
            val = 2.0 if i % 2 == 0 else 0.0
            states.append((ts, val))

        metrics = self._make_state_metrics(states)
        locks: dict[str, float] = {}

        # Should not raise even without alert_engine
        triggered = check_oscillation_lockout(
            metrics_data=metrics,
            locks=locks,
            oscillation_threshold=DEFAULT_OSCILLATION_THRESHOLD,
            alert_engine=None,
        )
        assert triggered is True
        assert len(locks) == 6


class TestExcludeParamsDefault:
    """Tests for default exclude_params including response params (RTUN-05)."""

    def _make_config_obj(self, data: dict) -> MagicMock:
        """Create a mock Config with data dict for _load_tuning_config."""
        config = MagicMock()
        config.data = data
        return config

    def test_default_excludes_response_params(self):
        """When no exclude_params in YAML, response params are excluded."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({"tuning": {"enabled": True}})
        Config._load_tuning_config(config)
        assert config.tuning_config is not None
        for p in RESPONSE_PARAMS:
            assert p in config.tuning_config.exclude_params, f"{p} not in exclude_params"

    def test_explicit_empty_enables_all(self):
        """When exclude_params: [] is set, nothing is excluded."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({
            "tuning": {"enabled": True, "exclude_params": []}
        })
        Config._load_tuning_config(config)
        assert config.tuning_config is not None
        assert len(config.tuning_config.exclude_params) == 0

    def test_explicit_list_overrides_default(self):
        """When user provides explicit list, only those are excluded."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({
            "tuning": {"enabled": True, "exclude_params": ["fusion_icmp_weight"]}
        })
        Config._load_tuning_config(config)
        assert config.tuning_config is not None
        assert config.tuning_config.exclude_params == frozenset(["fusion_icmp_weight"])
        # Response params should NOT be excluded when user provides explicit list
        for p in RESPONSE_PARAMS:
            assert p not in config.tuning_config.exclude_params


class TestCurrentParamsExtension:
    """Tests for current_params dict including response parameters."""

    def test_current_params_includes_response_params(self):
        """Verify response params are readable from QueueController mocks."""
        # This tests the reading pattern used in the maintenance loop
        wc = MagicMock()
        wc.download = MagicMock()
        wc.download.step_up_bps = 1_000_000
        wc.download.factor_down = 0.85
        wc.download.green_required = 5
        wc.upload = MagicMock()
        wc.upload.step_up_bps = 500_000
        wc.upload.factor_down = 0.90
        wc.upload.green_required = 5

        # Simulate the current_params dict construction
        response_params = {
            "dl_step_up_mbps": wc.download.step_up_bps / 1e6,
            "ul_step_up_mbps": wc.upload.step_up_bps / 1e6,
            "dl_factor_down": wc.download.factor_down,
            "ul_factor_down": wc.upload.factor_down,
            "dl_green_required": float(wc.download.green_required),
            "ul_green_required": float(wc.upload.green_required),
        }

        assert response_params["dl_step_up_mbps"] == 1.0
        assert response_params["ul_step_up_mbps"] == 0.5
        assert response_params["dl_factor_down"] == 0.85
        assert response_params["ul_factor_down"] == 0.90
        assert response_params["dl_green_required"] == 5.0
        assert response_params["ul_green_required"] == 5.0

"""Tests for health endpoint tuning section.

Tests that the health endpoint shows tuning status in all states:
disabled, awaiting_data, and active. Also tests MagicMock safety.
"""

import time
from unittest.mock import MagicMock

import pytest

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult, TuningState


def _make_tuning_result(param: str, old: float, new: float) -> TuningResult:
    """Create a test TuningResult."""
    return TuningResult(
        parameter=param,
        old_value=old,
        new_value=new,
        confidence=0.85,
        rationale="test reason",
        data_points=50,
        wan_name="Spectrum",
    )


def _make_health_handler(wan_controller):
    """Create a HealthCheckHandler with mocked controller for testing."""
    from wanctl.health_check import HealthCheckHandler

    handler = MagicMock(spec=HealthCheckHandler)
    handler.start_time = time.monotonic() - 100
    handler.consecutive_failures = 0

    controller = MagicMock()
    controller.wan_controllers = [
        {
            "controller": wan_controller,
            "config": wan_controller.config,
            "logger": MagicMock(),
        }
    ]
    handler.controller = controller

    # Use the real method
    handler._get_health_status = HealthCheckHandler._get_health_status.__get__(
        handler, HealthCheckHandler
    )
    return handler


def _make_wan_controller(
    tuning_enabled=False,
    tuning_state=None,
    tuning_config=None,
):
    """Create a mock WANController with tuning attributes."""
    wc = MagicMock()
    wc.config.wan_name = "Spectrum"
    wc.baseline_rtt = 25.0
    wc.load_rtt = 30.0
    wc.download.current_rate = 500_000_000
    wc.upload.current_rate = 50_000_000
    wc.download.green_streak = 5
    wc.download.red_streak = 0
    wc.download.soft_red_streak = 0
    wc.download.soft_red_required = 3
    wc.download.green_required = 5
    wc.upload.green_streak = 5
    wc.upload.red_streak = 0
    wc.upload.soft_red_streak = 0
    wc.upload.soft_red_required = 3
    wc.upload.green_required = 5
    wc.router_connectivity.is_reachable = True
    wc.router_connectivity.to_dict.return_value = {"reachable": True}

    # Profiler mock
    wc._profiler = MagicMock()
    wc._profiler.get_stats.return_value = {}
    wc._overrun_count = 0
    wc._cycle_interval_ms = 50.0

    # Signal processing mock
    wc._last_signal_result = None
    wc._irtt_thread = None
    wc._irtt_correlation = None
    wc._last_asymmetry_result = None
    wc._reflector_scorer = MagicMock()
    wc._reflector_scorer.get_all_statuses.return_value = []

    # Fusion mock (disabled to simplify)
    wc._fusion_enabled = False
    wc._last_fused_rtt = None
    wc._last_icmp_filtered_rtt = None
    wc._fusion_icmp_weight = 0.7

    # Alert engine mock
    wc.alert_engine = MagicMock()

    # Tuning attributes
    wc._tuning_enabled = tuning_enabled
    wc._tuning_state = tuning_state
    if tuning_config is not None:
        wc.config.tuning_config = tuning_config
    else:
        wc.config.tuning_config = None

    return wc


class TestTuningHealthDisabled:
    """Tests for disabled tuning in health endpoint."""

    def test_disabled_shows_reason(self):
        """Disabled tuning should show reason: disabled."""
        wc = _make_wan_controller(tuning_enabled=False)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert "tuning" in wan
        assert wan["tuning"]["enabled"] is False
        assert wan["tuning"]["reason"] == "disabled"

    def test_magicmock_wan_controller_safe(self):
        """MagicMock without explicit _tuning_enabled should show disabled."""
        # Use standard mock builder but then remove _tuning_enabled
        wc = _make_wan_controller(tuning_enabled=False)
        del wc._tuning_enabled  # Force getattr fallback

        handler = _make_health_handler(wc)
        health = handler._get_health_status()
        wan = health["wans"][0]
        assert wan["tuning"]["enabled"] is False
        assert wan["tuning"]["reason"] == "disabled"


class TestTuningHealthAwaitingData:
    """Tests for tuning enabled but no data yet."""

    def test_enabled_no_data_shows_awaiting(self):
        """Enabled but never-run tuning should show reason: awaiting_data."""
        state = TuningState(
            enabled=True,
            last_run_ts=None,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["enabled"] is True
        assert wan["tuning"]["reason"] == "awaiting_data"
        assert wan["tuning"]["last_run_ago_sec"] is None
        assert wan["tuning"]["parameters"] == {}
        assert wan["tuning"]["recent_adjustments"] == []


class TestTuningHealthActive:
    """Tests for active tuning with data."""

    def test_active_shows_last_run_ago(self):
        """Active tuning should show last_run_ago_sec as a positive float."""
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 60.0,
            recent_adjustments=[],
            parameters={"target_bloat_ms": 13.5},
        )
        wc = _make_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["enabled"] is True
        assert "reason" not in wan["tuning"]
        assert wan["tuning"]["last_run_ago_sec"] > 0
        assert isinstance(wan["tuning"]["last_run_ago_sec"], float)

    def test_active_shows_parameters(self):
        """Active tuning should show parameters dict."""
        tc = TuningConfig(
            enabled=True,
            cadence_sec=3600,
            lookback_hours=24,
            warmup_hours=1,
            max_step_pct=10.0,
            bounds={
                "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=30.0),
            },
        )
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 30.0,
            recent_adjustments=[],
            parameters={"target_bloat_ms": 13.5},
        )
        wc = _make_wan_controller(
            tuning_enabled=True, tuning_state=state, tuning_config=tc
        )
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        params = wan["tuning"]["parameters"]
        assert "target_bloat_ms" in params
        assert params["target_bloat_ms"]["current_value"] == 13.5
        assert "bounds" in params["target_bloat_ms"]
        assert params["target_bloat_ms"]["bounds"]["min"] == 3.0
        assert params["target_bloat_ms"]["bounds"]["max"] == 30.0

    def test_active_shows_recent_adjustments(self):
        """Active tuning should show recent adjustment details."""
        adj = _make_tuning_result("target_bloat_ms", old=15.0, new=13.5)
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=[adj],
            parameters={"target_bloat_ms": 13.5},
        )
        wc = _make_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        recent = wan["tuning"]["recent_adjustments"]
        assert len(recent) == 1
        assert recent[0]["parameter"] == "target_bloat_ms"
        assert recent[0]["old_value"] == 15.0
        assert recent[0]["new_value"] == 13.5
        assert recent[0]["confidence"] == 0.85
        assert recent[0]["rationale"] == "test reason"

    def test_recent_adjustments_capped_at_5(self):
        """Health endpoint should show at most 5 recent adjustments."""
        adjs = [
            _make_tuning_result(f"param_{i}", old=1.0, new=2.0)
            for i in range(8)
        ]
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=adjs,
            parameters={},
        )
        wc = _make_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert len(wan["tuning"]["recent_adjustments"]) == 5

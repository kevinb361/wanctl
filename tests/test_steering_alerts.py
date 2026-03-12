"""Unit tests for steering transition alerts (ALRT-02, ALRT-03).

Tests that steering_activated and steering_recovered alerts fire correctly
on state transitions, with appropriate details and cooldown behavior.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.alert_engine import AlertEngine
from wanctl.steering.cake_stats import CongestionSignals


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config(mock_steering_config):
    """Delegate to shared mock_steering_config from conftest.py."""
    return mock_steering_config


@pytest.fixture
def alert_engine():
    """Provide an enabled AlertEngine with no persistence for fast tests."""
    rules = {
        "steering_activated": {"enabled": True, "cooldown_sec": 60, "severity": "warning"},
        "steering_recovered": {"enabled": True, "cooldown_sec": 60, "severity": "recovery"},
    }
    return AlertEngine(enabled=True, default_cooldown_sec=300, rules=rules, writer=None)


@pytest.fixture
def mock_state_mgr():
    """Create a mock state manager with dict-based state."""
    state_mgr = MagicMock()
    state_mgr.state = {
        "current_state": "SPECTRUM_GOOD",
        "good_count": 0,
        "baseline_rtt": 25.0,
        "history_rtt": [],
        "history_delta": [],
        "transitions": [],
        "last_transition_time": None,
        "rtt_delta_ewma": 0.0,
        "queue_ewma": 0.0,
        "cake_drops_history": [],
        "queue_depth_history": [],
        "red_count": 0,
        "congestion_state": "GREEN",
        "cake_read_failures": 0,
    }
    return state_mgr


@pytest.fixture
def signals():
    """Sample CongestionSignals for testing."""
    return CongestionSignals(
        rtt_delta=25.0,
        rtt_delta_ewma=22.0,
        cake_drops=5,
        queued_packets=20,
        baseline_rtt=30.0,
    )


@pytest.fixture
def daemon(mock_config, mock_state_mgr, alert_engine):
    """Create a minimal SteeringDaemon-like object for testing alert logic.

    We import and patch the real daemon to test the actual _handle_good_state
    and _handle_degraded_state methods with alert firing.
    """
    from wanctl.steering.daemon import SteeringDaemon

    with patch.object(SteeringDaemon, "__init__", lambda self: None):
        d = SteeringDaemon.__new__(SteeringDaemon)

    d.config = mock_config
    d.state_mgr = mock_state_mgr
    d.alert_engine = alert_engine
    d.logger = MagicMock()
    d.confidence_controller = None
    d._steering_activated_time = None

    # Provide thresholds mock for _handle methods
    d.thresholds = MagicMock()
    d.thresholds.red_samples_required = 2
    d.thresholds.green_samples_required = 15

    # Mock execute_steering_transition to succeed by default
    d.execute_steering_transition = MagicMock(return_value=True)

    return d


# ---------------------------------------------------------------------------
# steering_activated tests (GOOD -> DEGRADED)
# ---------------------------------------------------------------------------


class TestSteeringActivatedAlert:
    """Tests for steering_activated alert on GOOD->DEGRADED transition."""

    def test_good_to_degraded_fires_steering_activated(self, daemon, signals):
        """GOOD->DEGRADED transition fires steering_activated alert."""
        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            spy.assert_called_once()
            call_args = spy.call_args
            assert call_args[0][0] == "steering_activated"
            assert call_args[0][1] == "warning"
            assert call_args[0][2] == "spectrum"

    def test_steering_activated_details_include_congestion_signals(self, daemon, signals):
        """steering_activated details include from_state, to_state, rtt_delta, cake_drops, queue_depth."""
        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            details = spy.call_args[0][3]
            assert details["from_state"] == "SPECTRUM_GOOD"
            assert details["to_state"] == "SPECTRUM_DEGRADED"
            assert details["rtt_delta"] == 25.0
            assert details["cake_drops"] == 5
            assert details["queue_depth"] == 20

    def test_steering_activated_includes_confidence_score_when_controller_exists(
        self, daemon, signals
    ):
        """steering_activated details include confidence_score when confidence controller exists."""
        confidence_ctrl = MagicMock()
        confidence_ctrl.timer_state.confidence_score = 85
        daemon.confidence_controller = confidence_ctrl

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            details = spy.call_args[0][3]
            assert details["confidence_score"] == 85

    def test_steering_activated_omits_confidence_score_when_controller_none(
        self, daemon, signals
    ):
        """steering_activated details omit confidence_score when confidence controller is None."""
        daemon.confidence_controller = None

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            details = spy.call_args[0][3]
            assert "confidence_score" not in details

    def test_failed_transition_does_not_fire_alert(self, daemon, signals):
        """Failed transition (execute_steering_transition returns False) does NOT fire alert."""
        daemon.execute_steering_transition = MagicMock(return_value=False)

        with patch.object(daemon.alert_engine, "fire") as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            spy.assert_not_called()

    def test_steering_activated_uses_primary_wan(self, daemon, signals):
        """steering_activated uses self.config.primary_wan as wan_name."""
        daemon.config.primary_wan = "att"

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            assert spy.call_args[0][2] == "att"

    def test_steering_activated_sets_activation_time(self, daemon, signals):
        """steering_activated sets _steering_activated_time to current monotonic time."""
        assert daemon._steering_activated_time is None

        daemon._handle_good_state(
            signals=signals,
            is_degraded=True,
            is_warning=False,
            assessment="DEGRADED",
            degrade_count=1,
            degrade_threshold=2,
        )

        assert daemon._steering_activated_time is not None
        # Should be approximately now
        assert abs(daemon._steering_activated_time - time.monotonic()) < 1.0


# ---------------------------------------------------------------------------
# steering_recovered tests (DEGRADED -> GOOD)
# ---------------------------------------------------------------------------


class TestSteeringRecoveredAlert:
    """Tests for steering_recovered alert on DEGRADED->GOOD transition."""

    def test_degraded_to_good_fires_steering_recovered(self, daemon, signals):
        """DEGRADED->GOOD transition fires steering_recovered alert."""
        daemon._steering_activated_time = time.monotonic() - 120.0

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_degraded_state(
                signals=signals,
                is_recovered=True,
                assessment="GOOD",
                recover_count=14,
                recover_threshold=15,
            )

            spy.assert_called_once()
            call_args = spy.call_args
            assert call_args[0][0] == "steering_recovered"
            assert call_args[0][1] == "recovery"
            assert call_args[0][2] == "spectrum"

    def test_steering_recovered_details_include_duration(self, daemon, signals):
        """steering_recovered details include from_state, to_state, duration_sec."""
        daemon._steering_activated_time = time.monotonic() - 120.5

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_degraded_state(
                signals=signals,
                is_recovered=True,
                assessment="GOOD",
                recover_count=14,
                recover_threshold=15,
            )

            details = spy.call_args[0][3]
            assert details["from_state"] == "SPECTRUM_DEGRADED"
            assert details["to_state"] == "SPECTRUM_GOOD"
            # Duration should be approximately 120.5 seconds
            assert isinstance(details["duration_sec"], float)
            assert abs(details["duration_sec"] - 120.5) < 1.0

    def test_steering_recovered_duration_none_when_no_activation_time(self, daemon, signals):
        """steering_recovered duration_sec is None when _steering_activated_time was never set."""
        daemon._steering_activated_time = None

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_degraded_state(
                signals=signals,
                is_recovered=True,
                assessment="GOOD",
                recover_count=14,
                recover_threshold=15,
            )

            details = spy.call_args[0][3]
            assert details["duration_sec"] is None

    def test_steering_recovered_clears_activation_time(self, daemon, signals):
        """steering_recovered clears _steering_activated_time back to None."""
        daemon._steering_activated_time = time.monotonic() - 60.0

        daemon._handle_degraded_state(
            signals=signals,
            is_recovered=True,
            assessment="GOOD",
            recover_count=14,
            recover_threshold=15,
        )

        assert daemon._steering_activated_time is None

    def test_failed_recovery_transition_does_not_fire_alert(self, daemon, signals):
        """Failed transition (execute_steering_transition returns False) does NOT fire alert."""
        daemon.execute_steering_transition = MagicMock(return_value=False)
        daemon._steering_activated_time = time.monotonic() - 60.0

        with patch.object(daemon.alert_engine, "fire") as spy:
            daemon._handle_degraded_state(
                signals=signals,
                is_recovered=True,
                assessment="GOOD",
                recover_count=14,
                recover_threshold=15,
            )

            spy.assert_not_called()

    def test_steering_recovered_uses_primary_wan(self, daemon, signals):
        """steering_recovered uses self.config.primary_wan as wan_name."""
        daemon.config.primary_wan = "att"
        daemon._steering_activated_time = time.monotonic() - 10.0

        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_degraded_state(
                signals=signals,
                is_recovered=True,
                assessment="GOOD",
                recover_count=14,
                recover_threshold=15,
            )

            assert spy.call_args[0][2] == "att"


# ---------------------------------------------------------------------------
# Cooldown suppression tests
# ---------------------------------------------------------------------------


class TestSteeringAlertCooldown:
    """Tests for cooldown suppression of steering alerts."""

    def test_rapid_steering_activated_suppressed_by_cooldown(self, daemon, signals):
        """Second rapid steering_activated is suppressed by AlertEngine cooldown."""
        # First transition fires
        daemon._handle_good_state(
            signals=signals,
            is_degraded=True,
            is_warning=False,
            assessment="DEGRADED",
            degrade_count=1,
            degrade_threshold=2,
        )

        # Now recover
        daemon._handle_degraded_state(
            signals=signals,
            is_recovered=True,
            assessment="GOOD",
            recover_count=14,
            recover_threshold=15,
        )

        # Second activation should be suppressed (within 60s cooldown)
        with patch.object(daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire) as spy:
            daemon._handle_good_state(
                signals=signals,
                is_degraded=True,
                is_warning=False,
                assessment="DEGRADED",
                degrade_count=1,
                degrade_threshold=2,
            )

            # fire() was called but returned False (suppressed)
            spy.assert_called_once()
            assert spy.return_value is False


# ---------------------------------------------------------------------------
# Duration tracking tests
# ---------------------------------------------------------------------------


class TestDurationTracking:
    """Tests for steering duration tracking via time.monotonic()."""

    def test_duration_uses_monotonic_timestamp(self, daemon, signals):
        """Duration calculation uses time.monotonic() difference from activation."""
        activation_time = time.monotonic()
        daemon._steering_activated_time = activation_time

        # Simulate 300 seconds passing
        with patch("wanctl.steering.daemon.time") as mock_time:
            mock_time.monotonic.return_value = activation_time + 300.0

            with patch.object(
                daemon.alert_engine, "fire", wraps=daemon.alert_engine.fire
            ) as spy:
                daemon._handle_degraded_state(
                    signals=signals,
                    is_recovered=True,
                    assessment="GOOD",
                    recover_count=14,
                    recover_threshold=15,
                )

                details = spy.call_args[0][3]
                assert details["duration_sec"] == 300.0


# ---------------------------------------------------------------------------
# Config: default_sustained_sec parsing
# ---------------------------------------------------------------------------


class TestSteeringAlertingConfigSustainedSec:
    """Tests for default_sustained_sec parsing in SteeringConfig._load_alerting_config."""

    def _make_config_data(self, alerting_overrides=None):
        """Build minimal config data dict with alerting section."""
        alerting = {
            "enabled": True,
            "default_cooldown_sec": 300,
            "default_sustained_sec": 60,
            "rules": {},
        }
        if alerting_overrides:
            alerting.update(alerting_overrides)
        return {
            "daemon": {"cycle_interval_sec": 1.0, "log_level": "INFO"},
            "wan": {"name": "spectrum", "primary": "spectrum", "alternate": "att"},
            "router": {"host": "10.10.99.1", "transport": "rest"},
            "thresholds": {
                "green_rtt_ms": 5.0,
                "yellow_rtt_ms": 15.0,
                "red_rtt_ms": 15.0,
            },
            "state": {"file": "/tmp/test_state.json", "history_size": 100},
            "alerting": alerting,
        }

    def test_default_sustained_sec_parsed_from_config(self):
        """default_sustained_sec is parsed from alerting config section."""
        from wanctl.steering.daemon import SteeringConfig

        with patch.object(SteeringConfig, "__init__", lambda self, data: None):
            cfg = SteeringConfig.__new__(SteeringConfig)

        cfg.data = self._make_config_data()
        cfg._load_alerting_config()

        assert cfg.alerting_config is not None
        assert cfg.alerting_config["default_sustained_sec"] == 60

    def test_default_sustained_sec_defaults_to_60(self):
        """default_sustained_sec defaults to 60 when not specified."""
        from wanctl.steering.daemon import SteeringConfig

        with patch.object(SteeringConfig, "__init__", lambda self, data: None):
            cfg = SteeringConfig.__new__(SteeringConfig)

        data = self._make_config_data()
        del data["alerting"]["default_sustained_sec"]
        cfg.data = data
        cfg._load_alerting_config()

        assert cfg.alerting_config is not None
        assert cfg.alerting_config["default_sustained_sec"] == 60

    def test_invalid_sustained_sec_non_int_disables_alerting(self):
        """Non-integer default_sustained_sec disables alerting with warning."""
        from wanctl.steering.daemon import SteeringConfig

        with patch.object(SteeringConfig, "__init__", lambda self, data: None):
            cfg = SteeringConfig.__new__(SteeringConfig)

        cfg.data = self._make_config_data({"default_sustained_sec": "sixty"})
        cfg._load_alerting_config()

        assert cfg.alerting_config is None

    def test_negative_sustained_sec_disables_alerting(self):
        """Negative default_sustained_sec disables alerting with warning."""
        from wanctl.steering.daemon import SteeringConfig

        with patch.object(SteeringConfig, "__init__", lambda self, data: None):
            cfg = SteeringConfig.__new__(SteeringConfig)

        cfg.data = self._make_config_data({"default_sustained_sec": -5})
        cfg._load_alerting_config()

        assert cfg.alerting_config is None

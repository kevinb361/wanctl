"""Tests for alerting section in health endpoints and AlertEngine.fire_count property."""

import json
import socket
import urllib.request
from unittest.mock import MagicMock

import pytest

from wanctl.alert_engine import AlertEngine
from wanctl.health_check import HealthCheckHandler, start_health_server
from wanctl.steering.health import (
    SteeringHealthHandler,
    start_steering_health_server,
)


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def default_rules():
    """Standard rules for testing."""
    return {
        "congestion_sustained": {
            "enabled": True,
            "cooldown_sec": 600,
            "severity": "critical",
        },
        "steering_activated": {
            "enabled": True,
            "cooldown_sec": 300,
            "severity": "warning",
        },
    }


@pytest.fixture
def engine(default_rules):
    """Provide an enabled AlertEngine without persistence."""
    return AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules=default_rules,
        writer=None,
    )


@pytest.fixture
def disabled_engine(default_rules):
    """Provide a disabled AlertEngine."""
    return AlertEngine(
        enabled=False,
        default_cooldown_sec=300,
        rules=default_rules,
        writer=None,
    )


class TestFireCount:
    """Tests for AlertEngine.fire_count property."""

    def test_fire_count_starts_at_zero(self, engine):
        """AlertEngine.fire_count starts at 0."""
        assert engine.fire_count == 0

    def test_fire_count_increments_on_successful_fire(self, engine):
        """AlertEngine.fire_count increments on each successful fire (not suppressed)."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert engine.fire_count == 1

        engine.fire("steering_activated", "warning", "spectrum", {})
        assert engine.fire_count == 2

    def test_fire_count_does_not_increment_when_suppressed(self, engine):
        """AlertEngine.fire_count does NOT increment when suppressed by cooldown."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert engine.fire_count == 1

        # Second fire for same (type, wan) is suppressed by cooldown
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert engine.fire_count == 1

    def test_fire_count_does_not_increment_when_disabled(self, disabled_engine):
        """AlertEngine.fire_count does NOT increment when disabled."""
        disabled_engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert disabled_engine.fire_count == 0


class TestAutorateHealthAlerting:
    """Tests for alerting section in autorate health endpoint."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset HealthCheckHandler class state before each test."""
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0
        yield
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0

    def _make_wan_controller_mock(self, alert_engine):
        """Create a mock WAN controller with the given alert engine."""
        wan_controller = MagicMock()
        wan_controller.alert_engine = alert_engine
        wan_controller.baseline_rtt = 10.0
        wan_controller.load_rtt = 12.0
        wan_controller.router_connectivity.is_reachable = True
        wan_controller.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "last_check": "2026-01-01T00:00:00Z",
        }
        wan_controller._overrun_count = 0
        wan_controller._cycle_interval_ms = 50.0
        wan_controller._profiler.stats.return_value = None
        # Mock download/upload for _get_current_state()
        wan_controller.download.current_rate = 100_000_000
        wan_controller.download.red_streak = 0
        wan_controller.download.soft_red_streak = 0
        wan_controller.download.soft_red_required = 3
        wan_controller.download.green_streak = 5
        wan_controller.download.green_required = 5
        wan_controller.upload.current_rate = 20_000_000
        wan_controller.upload.red_streak = 0
        wan_controller.upload.soft_red_streak = 0
        wan_controller.upload.soft_red_required = 3
        wan_controller.upload.green_streak = 5
        wan_controller.upload.green_required = 5
        # Phase 92: signal quality and IRTT attributes (prevent MagicMock truthy trap)
        wan_controller._last_signal_result = None
        wan_controller._irtt_thread = None
        wan_controller._irtt_correlation = None
        wan_controller._last_asymmetry_result = None
        return wan_controller

    def test_autorate_health_includes_alerting_key(self, engine):
        """Autorate health response includes 'alerting' key with enabled, fire_count, active_cooldowns."""
        wan_ctrl = self._make_wan_controller_mock(engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "alerting" in data
            assert "enabled" in data["alerting"]
            assert "fire_count" in data["alerting"]
            assert "active_cooldowns" in data["alerting"]
        finally:
            server.shutdown()

    def test_autorate_alerting_shows_disabled(self, disabled_engine):
        """Autorate alerting section shows enabled=False when alert_engine disabled."""
        wan_ctrl = self._make_wan_controller_mock(disabled_engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["alerting"]["enabled"] is False
        finally:
            server.shutdown()

    def test_autorate_alerting_shows_active_cooldowns(self, engine):
        """Autorate alerting section shows active cooldowns as list of {type, wan, remaining_sec}."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})

        wan_ctrl = self._make_wan_controller_mock(engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            cooldowns = data["alerting"]["active_cooldowns"]
            assert len(cooldowns) >= 1
            cd = cooldowns[0]
            assert "type" in cd
            assert "wan" in cd
            assert "remaining_sec" in cd
            assert cd["type"] == "congestion_sustained"
            assert cd["wan"] == "spectrum"
            assert cd["remaining_sec"] > 0
        finally:
            server.shutdown()

    def test_autorate_health_without_controller_omits_alerting(self):
        """Health response without controller omits alerting section (no crash)."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Should not crash, alerting defaults when no controller
            assert "alerting" in data
            assert data["alerting"]["enabled"] is False
            assert data["alerting"]["fire_count"] == 0
            assert data["alerting"]["active_cooldowns"] == []
        finally:
            server.shutdown()


class TestSteeringHealthAlerting:
    """Tests for alerting section in steering health endpoint."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset SteeringHealthHandler class state before each test."""
        SteeringHealthHandler.daemon = None
        SteeringHealthHandler.start_time = None
        SteeringHealthHandler.consecutive_failures = 0
        yield
        SteeringHealthHandler.daemon = None
        SteeringHealthHandler.start_time = None
        SteeringHealthHandler.consecutive_failures = 0

    def _make_daemon_mock(self, alert_engine):
        """Create a mock steering daemon with the given alert engine."""
        daemon = MagicMock()
        daemon.alert_engine = alert_engine
        daemon.state_mgr.state = {
            "current_state": "good",
            "congestion_state": "GREEN",
            "last_transition_time": None,
            "red_count": 0,
            "good_count": 0,
            "cake_read_failures": 0,
        }
        daemon.config.state_good = "good"
        daemon.config.confidence_config = None
        daemon.config.green_rtt_ms = 5
        daemon.config.yellow_rtt_ms = 15
        daemon.config.red_rtt_ms = 30
        daemon.config.red_samples_required = 3
        daemon.config.green_samples_required = 5
        daemon.confidence_controller = None
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "last_check": "2026-01-01T00:00:00Z",
        }
        daemon._profiler.stats.return_value = None
        daemon._overrun_count = 0
        daemon._cycle_interval_ms = 50.0
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        return daemon

    def test_steering_health_includes_alerting_key(self, engine):
        """Steering health response includes 'alerting' key with enabled, fire_count, active_cooldowns."""
        daemon = self._make_daemon_mock(engine)

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "alerting" in data
            assert "enabled" in data["alerting"]
            assert "fire_count" in data["alerting"]
            assert "active_cooldowns" in data["alerting"]
        finally:
            server.shutdown()

    def test_steering_alerting_shows_correct_fire_count(self, engine):
        """Steering alerting section shows correct fire_count after alerts."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        engine.fire("steering_activated", "warning", "spectrum", {})

        daemon = self._make_daemon_mock(engine)

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["alerting"]["fire_count"] == 2
        finally:
            server.shutdown()

    def test_steering_health_without_daemon_omits_alerting(self):
        """Health response without daemon omits alerting section (no crash)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Should not crash, and alerting should not be present when no daemon
            assert "alerting" not in data
        finally:
            server.shutdown()

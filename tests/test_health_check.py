"""Tests for the health check HTTP endpoint."""

import json
import time
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import find_free_port
from wanctl.health_check import (
    HealthCheckHandler,
    HealthCheckServer,
    _build_cycle_budget,
    _get_current_state,
    _get_disk_space_status,
    start_health_server,
    update_health_status,
)
from wanctl.irtt_measurement import IRTTResult
from wanctl.perf_profiler import OperationProfiler
from wanctl.signal_processing import SignalResult
from wanctl.storage.writer import MetricsWriter


def _configure_qc_health_data(qc_mock: MagicMock) -> None:
    """Configure get_health_data() on a QueueController mock.

    Uses side_effect so values are read dynamically at call time,
    allowing tests to modify private attrs after fixture setup.
    """
    def _qc_health_data():
        return {
            "hysteresis": {
                "dwell_counter": qc_mock._yellow_dwell,
                "dwell_cycles": qc_mock.dwell_cycles,
                "deadband_ms": qc_mock.deadband_ms,
                "transitions_suppressed": qc_mock._transitions_suppressed,
                "suppressions_per_min": qc_mock._window_suppressions,
                "window_start_epoch": qc_mock._window_start_time,
            },
        }
    qc_mock.get_health_data.side_effect = _qc_health_data


def _configure_wan_health_data(wan_mock: MagicMock) -> None:
    """Configure get_health_data() on a WANController mock.

    Uses side_effect so values are read dynamically at call time,
    allowing tests to modify private attrs after fixture setup.
    Also configures get_health_data() on download and upload mocks.
    """
    def _wan_health_data():
        return {
            "cycle_budget": {
                "profiler": getattr(wan_mock, "_profiler", MagicMock()),
                "overrun_count": getattr(wan_mock, "_overrun_count", 0),
                "cycle_interval_ms": getattr(wan_mock, "_cycle_interval_ms", 50.0),
                "warning_threshold_pct": getattr(wan_mock, "_warning_threshold_pct", 80.0),
            },
            "signal_result": getattr(wan_mock, "_last_signal_result", None),
            "irtt": {
                "thread": getattr(wan_mock, "_irtt_thread", None),
                "correlation": getattr(wan_mock, "_irtt_correlation", None),
                "last_asymmetry_result": getattr(wan_mock, "_last_asymmetry_result", None),
            },
            "reflector": {
                "scorer": getattr(wan_mock, "_reflector_scorer", None),
            },
            "fusion": {
                "enabled": getattr(wan_mock, "_fusion_enabled", False),
                "icmp_filtered_rtt": getattr(wan_mock, "_last_icmp_filtered_rtt", None),
                "fused_rtt": getattr(wan_mock, "_last_fused_rtt", None),
                "icmp_weight": getattr(wan_mock, "_fusion_icmp_weight", 0.7),
                "healer": getattr(wan_mock, "_fusion_healer", None),
            },
            "tuning": {
                "enabled": getattr(wan_mock, "_tuning_enabled", False),
                "state": getattr(wan_mock, "_tuning_state", None),
                "parameter_locks": getattr(wan_mock, "_parameter_locks", {}),
                "pending_observation": getattr(wan_mock, "_pending_observation", None),
            },
            "suppression_alert": {
                "threshold": getattr(wan_mock, "_suppression_alert_threshold", 20),
            },
            "burst_detection": {
                "enabled": (
                    wan_mock._burst_detection_enabled
                    if "_burst_detection_enabled" in wan_mock.__dict__
                    else True
                ),
                "result": (
                    wan_mock._last_burst_result
                    if "_last_burst_result" in wan_mock.__dict__
                    else None
                ),
                "total_bursts": (
                    wan_mock._burst_total_bursts
                    if "_burst_total_bursts" in wan_mock.__dict__
                    else 0
                ),
            },
        }
    wan_mock.get_health_data.side_effect = _wan_health_data
    _configure_qc_health_data(wan_mock.download)
    _configure_qc_health_data(wan_mock.upload)


class TestHealthCheckHandler:
    """Tests for HealthCheckHandler class."""

    def test_get_current_state_red(self):
        """Test state detection for RED state."""
        controller = MagicMock()
        controller.red_streak = 1
        controller.soft_red_streak = 0
        controller.soft_red_required = 3
        controller.green_streak = 0
        controller.green_required = 5

        assert _get_current_state(controller) == "RED"

    def test_get_current_state_soft_red(self):
        """Test state detection for SOFT_RED state."""
        controller = MagicMock()
        controller.red_streak = 0
        controller.soft_red_streak = 3
        controller.soft_red_required = 3
        controller.green_streak = 0
        controller.green_required = 5

        assert _get_current_state(controller) == "SOFT_RED"

    def test_get_current_state_green(self):
        """Test state detection for GREEN state."""
        controller = MagicMock()
        controller.red_streak = 0
        controller.soft_red_streak = 0
        controller.soft_red_required = 3
        controller.green_streak = 5
        controller.green_required = 5

        assert _get_current_state(controller) == "GREEN"

    def test_get_current_state_yellow(self):
        """Test state detection for YELLOW state."""
        controller = MagicMock()
        controller.red_streak = 0
        controller.soft_red_streak = 1
        controller.soft_red_required = 3
        controller.green_streak = 0
        controller.green_required = 5

        assert _get_current_state(controller) == "YELLOW"


@pytest.mark.timeout(5)
class TestHealthServer:
    """Integration tests for the health check server."""

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

    def test_start_and_shutdown(self):
        """Test starting and shutting down the health server."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        assert isinstance(server, HealthCheckServer)
        assert server.thread.is_alive()

        server.shutdown()
        server.thread.join(timeout=1)  # Wait for thread to finish

    def test_health_endpoint_returns_json(self):
        """Test that /health endpoint returns valid JSON."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data
            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_root_endpoint_returns_health(self):
        """Test that / endpoint returns same as /health."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "status" in data
            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_health_endpoint_with_failures(self):
        """Test that health endpoint reports degraded status with failures."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            # Update to simulate failures
            update_health_status(3)  # Equals MAX_CONSECUTIVE_FAILURES

            url = f"http://127.0.0.1:{port}/health"
            # urllib raises HTTPError for 503, so we need to catch it
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            # Read the response body from the exception
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
            assert data["consecutive_failures"] == 3
            # Close the HTTPError to release the socket
            exc_info.value.close()
        finally:
            server.shutdown()

    def test_404_on_unknown_path(self):
        """Test that unknown paths return 404."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/unknown"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)
            assert exc_info.value.code == 404
            # Close the HTTPError to release the socket
            exc_info.value.close()
        finally:
            server.shutdown()

    def test_health_with_mock_controller(self):
        """Test health endpoint with a mock controller."""
        # Create mock controller
        mock_controller = MagicMock()
        mock_wan_controller = MagicMock()
        mock_wan_controller.baseline_rtt = 24.5
        mock_wan_controller.load_rtt = 28.3

        # Mock download queue
        mock_wan_controller.download.current_rate = 800_000_000
        mock_wan_controller.download.red_streak = 0
        mock_wan_controller.download.soft_red_streak = 0
        mock_wan_controller.download.soft_red_required = 3
        mock_wan_controller.download.green_streak = 5
        mock_wan_controller.download.green_required = 5
        mock_wan_controller.download._yellow_dwell = 0
        mock_wan_controller.download.dwell_cycles = 3
        mock_wan_controller.download.deadband_ms = 3.0
        mock_wan_controller.download._transitions_suppressed = 0
        mock_wan_controller.download._window_suppressions = 0
        mock_wan_controller.download._window_start_time = 1712345000.0

        # Mock upload queue
        mock_wan_controller.upload.current_rate = 35_000_000
        mock_wan_controller.upload.red_streak = 0
        mock_wan_controller.upload.soft_red_streak = 0
        mock_wan_controller.upload.soft_red_required = 3
        mock_wan_controller.upload.green_streak = 5
        mock_wan_controller.upload.green_required = 5
        mock_wan_controller.upload._yellow_dwell = 0
        mock_wan_controller.upload.dwell_cycles = 3
        mock_wan_controller.upload.deadband_ms = 3.0
        mock_wan_controller.upload._transitions_suppressed = 0
        mock_wan_controller.upload._window_suppressions = 0
        mock_wan_controller.upload._window_start_time = 1712345000.0

        # Hysteresis observability (Phase 136)
        mock_wan_controller._suppression_alert_threshold = 20

        # Mock router connectivity state
        mock_wan_controller.router_connectivity.is_reachable = True
        mock_wan_controller.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }

        # Prevent MagicMock truthy issues for signal/IRTT/fusion attributes
        mock_wan_controller._last_signal_result = None
        mock_wan_controller._irtt_thread = None
        mock_wan_controller._irtt_correlation = None
        mock_wan_controller._last_asymmetry_result = None
        mock_wan_controller._fusion_enabled = False
        mock_wan_controller._fusion_icmp_weight = 0.7
        mock_wan_controller._last_fused_rtt = None
        mock_wan_controller._last_icmp_filtered_rtt = None
        mock_wan_controller._fusion_healer = None
        _configure_wan_health_data(mock_wan_controller)

        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}

        mock_controller.wan_controllers = [
            {"controller": mock_wan_controller, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["status"] == "healthy"
            assert data["wan_count"] == 1
            assert len(data["wans"]) == 1

            wan = data["wans"][0]
            assert wan["name"] == "spectrum"
            assert wan["baseline_rtt_ms"] == 24.5
            assert wan["load_rtt_ms"] == 28.3
            assert wan["download"]["current_rate_mbps"] == 800.0
            assert wan["download"]["state"] == "GREEN"
            assert wan["upload"]["current_rate_mbps"] == 35.0
            assert wan["upload"]["state"] == "GREEN"
        finally:
            server.shutdown()


class TestRouterConnectivityReporting:
    """Tests for router connectivity reporting in health endpoint."""

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

    @pytest.fixture
    def mock_wan_controller(self):
        """Create a mock WAN controller with router connectivity."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues for signal/IRTT/fusion attributes
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def test_health_includes_router_connectivity_per_wan(self, mock_wan_controller):
        """Test that each WAN includes router_connectivity section."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": mock_wan_controller, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "wans" in data
            assert len(data["wans"]) == 1
            assert "router_connectivity" in data["wans"][0]
            conn = data["wans"][0]["router_connectivity"]
            assert conn["is_reachable"] is True
            assert conn["consecutive_failures"] == 0
            assert conn["last_failure_type"] is None
        finally:
            server.shutdown()

    def test_health_includes_router_reachable_aggregate(self, mock_wan_controller):
        """Test that top-level router_reachable field exists."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": mock_wan_controller, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "router_reachable" in data
            assert data["router_reachable"] is True
        finally:
            server.shutdown()

    def test_health_degrades_when_router_unreachable(self, mock_wan_controller):
        """Test that health degrades (503) when router is unreachable."""
        # Set router as unreachable
        mock_wan_controller.router_connectivity.is_reachable = False
        mock_wan_controller.router_connectivity.to_dict.return_value = {
            "is_reachable": False,
            "consecutive_failures": 3,
            "last_failure_type": "timeout",
            "last_failure_time": 12345.0,
        }

        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": mock_wan_controller, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
            assert data["router_reachable"] is False
            exc_info.value.close()
        finally:
            server.shutdown()

    def test_health_healthy_when_router_reachable(self, mock_wan_controller):
        """Test that health is healthy (200) when router is reachable."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": mock_wan_controller, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["status"] == "healthy"
            assert data["router_reachable"] is True
        finally:
            server.shutdown()

    def test_health_router_reachable_without_controller(self):
        """Test that router_reachable defaults to True when no controller."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # No controller, but should still have router_reachable = True
            assert "router_reachable" in data
            assert data["router_reachable"] is True
            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_health_degrades_with_any_wan_unreachable(self):
        """Test that health degrades if ANY WAN has unreachable router."""
        # WAN 1: reachable
        wan1 = MagicMock()
        wan1.baseline_rtt = 20.0
        wan1.load_rtt = 22.0
        wan1.download.current_rate = 500_000_000
        wan1.download.red_streak = 0
        wan1.download.soft_red_streak = 0
        wan1.download.soft_red_required = 3
        wan1.download.green_streak = 5
        wan1.download.green_required = 5
        wan1.download._yellow_dwell = 0
        wan1.download.dwell_cycles = 3
        wan1.download.deadband_ms = 3.0
        wan1.download._transitions_suppressed = 0
        wan1.download._window_suppressions = 0
        wan1.download._window_start_time = 1712345000.0
        wan1.upload.current_rate = 20_000_000
        wan1.upload.red_streak = 0
        wan1.upload.soft_red_streak = 0
        wan1.upload.soft_red_required = 3
        wan1.upload.green_streak = 5
        wan1.upload.green_required = 5
        wan1.upload._yellow_dwell = 0
        wan1.upload.dwell_cycles = 3
        wan1.upload.deadband_ms = 3.0
        wan1.upload._transitions_suppressed = 0
        wan1.upload._window_suppressions = 0
        wan1.upload._window_start_time = 1712345000.0
        wan1._suppression_alert_threshold = 20
        wan1.router_connectivity.is_reachable = True
        wan1.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues for signal/IRTT/fusion attributes
        wan1._last_signal_result = None
        wan1._irtt_thread = None
        wan1._irtt_correlation = None
        wan1._last_asymmetry_result = None
        wan1._fusion_enabled = False
        wan1._fusion_icmp_weight = 0.7
        wan1._last_fused_rtt = None
        wan1._last_icmp_filtered_rtt = None
        wan1._fusion_healer = None
        _configure_wan_health_data(wan1)

        # WAN 2: unreachable
        wan2 = MagicMock()
        wan2.baseline_rtt = 25.0
        wan2.load_rtt = 30.0
        wan2.download.current_rate = 100_000_000
        wan2.download.red_streak = 0
        wan2.download.soft_red_streak = 0
        wan2.download.soft_red_required = 3
        wan2.download.green_streak = 5
        wan2.download.green_required = 5
        wan2.download._yellow_dwell = 0
        wan2.download.dwell_cycles = 3
        wan2.download.deadband_ms = 3.0
        wan2.download._transitions_suppressed = 0
        wan2.download._window_suppressions = 0
        wan2.download._window_start_time = 1712345000.0
        wan2.upload.current_rate = 10_000_000
        wan2.upload.red_streak = 0
        wan2.upload.soft_red_streak = 0
        wan2.upload.soft_red_required = 3
        wan2.upload.green_streak = 5
        wan2.upload.green_required = 5
        wan2.upload._yellow_dwell = 0
        wan2.upload.dwell_cycles = 3
        wan2.upload.deadband_ms = 3.0
        wan2.upload._transitions_suppressed = 0
        wan2.upload._window_suppressions = 0
        wan2.upload._window_start_time = 1712345000.0
        wan2._suppression_alert_threshold = 20
        wan2.router_connectivity.is_reachable = False
        wan2.router_connectivity.to_dict.return_value = {
            "is_reachable": False,
            "consecutive_failures": 5,
            "last_failure_type": "connection_refused",
            "last_failure_time": 98765.0,
        }
        # Prevent MagicMock truthy issues for signal/IRTT/fusion attributes
        wan2._last_signal_result = None
        wan2._irtt_thread = None
        wan2._irtt_correlation = None
        wan2._last_asymmetry_result = None
        wan2._fusion_enabled = False
        wan2._fusion_icmp_weight = 0.7
        wan2._last_fused_rtt = None
        wan2._last_icmp_filtered_rtt = None
        wan2._fusion_healer = None
        _configure_wan_health_data(wan2)

        mock_controller = MagicMock()
        config1 = MagicMock()
        config1.wan_name = "spectrum"
        config1.irtt_config = {"enabled": False}
        config2 = MagicMock()
        config2.wan_name = "att"
        config2.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan1, "config": config1, "logger": MagicMock()},
            {"controller": wan2, "config": config2, "logger": MagicMock()},
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
            assert data["router_reachable"] is False
            # Both WANs should still be in response
            assert len(data["wans"]) == 2
            exc_info.value.close()
        finally:
            server.shutdown()


class TestUpdateHealthStatus:
    """Tests for update_health_status function."""

    def test_updates_consecutive_failures(self):
        """Test that update_health_status updates the failure count."""
        HealthCheckHandler.consecutive_failures = 0

        update_health_status(5)
        assert HealthCheckHandler.consecutive_failures == 5

        update_health_status(0)
        assert HealthCheckHandler.consecutive_failures == 0


class TestBuildCycleBudget:
    """Unit tests for _build_cycle_budget helper function."""

    def test_returns_none_when_profiler_has_no_data(self):
        """Cold start: profiler has no samples, should return None (D9)."""
        profiler = OperationProfiler(max_samples=1200)
        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is None

    def test_returns_correct_dict_when_profiler_has_data(self):
        """Populated profiler returns dict with cycle_time_ms, utilization_pct, overrun_count."""
        profiler = OperationProfiler(max_samples=1200)
        # Record some sample data
        for val in [37.0, 38.0, 39.0, 40.0, 41.0]:
            profiler.record("autorate_cycle_total", val)

        result = _build_cycle_budget(
            profiler, overrun_count=5, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "cycle_time_ms" in result
        assert "utilization_pct" in result
        assert "overrun_count" in result
        assert result["overrun_count"] == 5
        assert "avg" in result["cycle_time_ms"]
        assert "p95" in result["cycle_time_ms"]
        assert "p99" in result["cycle_time_ms"]

    def test_utilization_pct_calculation(self):
        """utilization_pct = (avg_ms / cycle_interval_ms) * 100, rounded to 1 decimal."""
        profiler = OperationProfiler(max_samples=1200)
        # All same value = avg is exactly 37.6
        profiler.record("autorate_cycle_total", 37.6)
        profiler.record("autorate_cycle_total", 37.6)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        # (37.6 / 50.0) * 100 = 75.2
        assert result["utilization_pct"] == 75.2

    def test_cycle_time_values_rounded_to_1_decimal(self):
        """cycle_time_ms values should be rounded to 1 decimal place."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 37.654)
        profiler.record("autorate_cycle_total", 38.123)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        # Check all values are rounded to 1 decimal
        for key in ("avg", "p95", "p99"):
            value = result["cycle_time_ms"][key]
            # Multiply by 10 -- should be an integer (i.e., 1 decimal place)
            assert value == round(value, 1), f"{key} not rounded to 1 decimal: {value}"

    def test_subsystems_dict_present_when_sub_timer_data_exists(self):
        """subsystems dict should be present when profiler has sub-timer data."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)
        profiler.record("autorate_signal_processing", 5.0)
        profiler.record("autorate_logging_metrics", 30.0)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" in result
        assert "signal_processing" in result["subsystems"]
        assert "logging_metrics" in result["subsystems"]
        # Each subsystem entry should have avg, p95, p99
        for name in ("signal_processing", "logging_metrics"):
            sub = result["subsystems"][name]
            assert "avg" in sub
            assert "p95" in sub
            assert "p99" in sub

    def test_subsystems_uses_short_names(self):
        """subsystems keys should use short names (without autorate_ prefix)."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)
        profiler.record("autorate_signal_processing", 5.0)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" in result
        assert "signal_processing" in result["subsystems"]
        assert "autorate_signal_processing" not in result["subsystems"]

    def test_subsystems_omits_labels_without_data(self):
        """subsystems should only include labels that have profiler data."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)
        profiler.record("autorate_signal_processing", 5.0)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" in result
        assert "ewma_spike" not in result["subsystems"]

    def test_subsystems_absent_when_no_sub_timer_data(self):
        """subsystems should not be in result when profiler has no sub-timer data."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" not in result

    def test_subsystems_values_rounded_to_1_decimal(self):
        """subsystem values should be rounded to 1 decimal place."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)
        profiler.record("autorate_signal_processing", 1.234)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" in result
        assert result["subsystems"]["signal_processing"]["avg"] == 1.2

    def test_subsystems_all_eight_labels(self):
        """All 8 sub-timer labels should appear in subsystems when data exists."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 40.0)
        # Record all 8 sub-timer labels
        labels = [
            "autorate_rtt_measurement",
            "autorate_signal_processing",
            "autorate_ewma_spike",
            "autorate_congestion_assess",
            "autorate_irtt_observation",
            "autorate_logging_metrics",
            "autorate_router_communication",
            "autorate_post_cycle",
        ]
        for label in labels:
            profiler.record(label, 5.0)

        result = _build_cycle_budget(
            profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total"
        )
        assert result is not None
        assert "subsystems" in result
        expected_short_names = [
            "rtt_measurement",
            "signal_processing",
            "ewma_spike",
            "congestion_assess",
            "irtt_observation",
            "logging_metrics",
            "router_communication",
            "post_cycle",
        ]
        for name in expected_short_names:
            assert name in result["subsystems"], f"Expected {name} in subsystems"


class TestCycleBudgetInHealthEndpoint:
    """Integration tests for cycle_budget in autorate health endpoint."""

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

    def _make_mock_wan_controller(self, with_profiler_data=True, overrun_count=5):
        """Create a mock WAN controller with profiler attributes."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }

        # Prevent MagicMock truthy issues for signal/IRTT/fusion attributes
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None

        # Set profiler attributes (from Plan 01)
        wan._profiler = OperationProfiler(max_samples=1200)
        wan._overrun_count = overrun_count
        wan._cycle_interval_ms = 50.0
        wan._warning_threshold_pct = 80.0

        if with_profiler_data:
            for val in [37.0, 38.0, 39.0, 40.0, 41.0, 42.0, 43.0, 44.0, 45.0, 46.0]:
                wan._profiler.record("autorate_cycle_total", val)

        _configure_wan_health_data(wan)
        return wan

    def test_cycle_budget_present_when_profiler_has_data(self):
        """Health response includes cycle_budget inside each WAN when profiler has data."""
        wan = self._make_mock_wan_controller(with_profiler_data=True, overrun_count=5)
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wan_data = data["wans"][0]
            assert "cycle_budget" in wan_data
            cb = wan_data["cycle_budget"]
            assert "cycle_time_ms" in cb
            assert "avg" in cb["cycle_time_ms"]
            assert "p95" in cb["cycle_time_ms"]
            assert "p99" in cb["cycle_time_ms"]
            assert "utilization_pct" in cb
            assert "overrun_count" in cb
            assert cb["overrun_count"] == 5
        finally:
            server.shutdown()

    def test_cycle_budget_omitted_when_profiler_empty(self):
        """Health response omits cycle_budget from WAN when profiler has no data (cold start)."""
        wan = self._make_mock_wan_controller(with_profiler_data=False)
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wan_data = data["wans"][0]
            assert "cycle_budget" not in wan_data
        finally:
            server.shutdown()

    def test_existing_health_fields_unchanged_with_cycle_budget(self):
        """Adding cycle_budget does not remove or change any existing health fields."""
        wan = self._make_mock_wan_controller(with_profiler_data=True)
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Top-level fields
            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data
            assert "wan_count" in data
            assert "router_reachable" in data
            assert "consecutive_failures" in data

            # WAN fields
            wan_data = data["wans"][0]
            assert "name" in wan_data
            assert "baseline_rtt_ms" in wan_data
            assert "load_rtt_ms" in wan_data
            assert "download" in wan_data
            assert "upload" in wan_data
            assert "router_connectivity" in wan_data
        finally:
            server.shutdown()


class TestDiskSpaceStatus:
    """Tests for _get_disk_space_status helper function."""

    def test_disk_space_returns_required_keys(self):
        """Test that disk space response includes all required keys."""
        result = _get_disk_space_status(path="/tmp")
        assert "path" in result
        assert "free_bytes" in result
        assert "total_bytes" in result
        assert "free_pct" in result
        assert "status" in result

    def test_disk_space_ok_when_plenty_of_space(self):
        """Test that status is 'ok' when free space > threshold."""
        # Mock disk_usage to return plenty of space (1GB free)
        mock_usage = MagicMock()
        mock_usage.free = 1_000_000_000  # 1GB
        mock_usage.total = 10_000_000_000  # 10GB

        with patch("wanctl.health_check.shutil.disk_usage", return_value=mock_usage):
            result = _get_disk_space_status()

        assert result["status"] == "ok"
        assert result["free_bytes"] == 1_000_000_000
        assert result["total_bytes"] == 10_000_000_000
        assert result["free_pct"] == 10.0

    def test_disk_space_warning_when_low(self):
        """Test that status is 'warning' when free space < 100MB."""
        mock_usage = MagicMock()
        mock_usage.free = 50_000_000  # 50MB (below 100MB threshold)
        mock_usage.total = 10_000_000_000

        with patch("wanctl.health_check.shutil.disk_usage", return_value=mock_usage):
            result = _get_disk_space_status()

        assert result["status"] == "warning"
        assert result["free_bytes"] == 50_000_000

    def test_disk_space_unknown_on_oserror(self):
        """Test that status is 'unknown' when disk_usage raises OSError."""
        with patch(
            "wanctl.health_check.shutil.disk_usage",
            side_effect=OSError("path not found"),
        ):
            result = _get_disk_space_status(path="/nonexistent/path")

        assert result["status"] == "unknown"
        assert result["free_bytes"] == 0
        assert result["total_bytes"] == 0
        assert result["free_pct"] == 0.0
        assert result["path"] == "/nonexistent/path"


class TestDiskSpaceInHealthEndpoint:
    """Tests for disk_space field in autorate health endpoint."""

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

    def test_health_response_includes_disk_space(self):
        """Test that health response includes disk_space field."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "disk_space" in data
            ds = data["disk_space"]
            assert "path" in ds
            assert "free_bytes" in ds
            assert "total_bytes" in ds
            assert "free_pct" in ds
            assert "status" in ds
        finally:
            server.shutdown()

    def test_health_degrades_on_disk_space_warning(self):
        """Test that health status degrades when disk space is low."""
        mock_usage = MagicMock()
        mock_usage.free = 50_000_000  # 50MB, below threshold
        mock_usage.total = 10_000_000_000

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            with patch("wanctl.health_check.shutil.disk_usage", return_value=mock_usage):
                url = f"http://127.0.0.1:{port}/health"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 503
                data = json.loads(exc_info.value.read().decode())
                assert data["status"] == "degraded"
                assert data["disk_space"]["status"] == "warning"
                exc_info.value.close()
        finally:
            server.shutdown()


class TestSignalQualityHealth:
    """Tests for signal_quality section in health endpoint."""

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

    @pytest.fixture
    def mock_wan_with_signal(self):
        """Create a mock WAN controller for signal quality tests."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def _make_controller(self, wan, irtt_enabled=False):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": irtt_enabled}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def test_signal_quality_present_when_signal_result_available(self, mock_wan_with_signal):
        """signal_quality section present in WAN health when _last_signal_result is a SignalResult."""
        mock_wan_with_signal._last_signal_result = SignalResult(
            filtered_rtt=25.0,
            raw_rtt=26.1,
            jitter_ms=1.234,
            variance_ms2=2.567,
            confidence=0.891,
            is_outlier=False,
            outlier_rate=0.042,
            total_outliers=3,
            consecutive_outliers=0,
            warming_up=False,
        )
        controller = self._make_controller(mock_wan_with_signal)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            wan_data = data["wans"][0]
            assert "signal_quality" in wan_data
        finally:
            server.shutdown()

    def test_signal_quality_has_expected_keys(self, mock_wan_with_signal):
        """signal_quality section has jitter_ms, variance_ms2, confidence, outlier_rate, total_outliers, warming_up."""
        mock_wan_with_signal._last_signal_result = SignalResult(
            filtered_rtt=25.0,
            raw_rtt=26.1,
            jitter_ms=1.234,
            variance_ms2=2.567,
            confidence=0.891,
            is_outlier=False,
            outlier_rate=0.042,
            total_outliers=3,
            consecutive_outliers=0,
            warming_up=False,
        )
        controller = self._make_controller(mock_wan_with_signal)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            sq = data["wans"][0]["signal_quality"]
            assert "jitter_ms" in sq
            assert "variance_ms2" in sq
            assert "confidence" in sq
            assert "outlier_rate" in sq
            assert "total_outliers" in sq
            assert "warming_up" in sq
        finally:
            server.shutdown()

    def test_signal_quality_values_rounded(self, mock_wan_with_signal):
        """signal_quality values rounded to 3 decimal places (floats), total_outliers is int."""
        mock_wan_with_signal._last_signal_result = SignalResult(
            filtered_rtt=25.0,
            raw_rtt=26.1,
            jitter_ms=1.23456,
            variance_ms2=2.56789,
            confidence=0.89123,
            is_outlier=False,
            outlier_rate=0.04256,
            total_outliers=3,
            consecutive_outliers=0,
            warming_up=False,
        )
        controller = self._make_controller(mock_wan_with_signal)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            sq = data["wans"][0]["signal_quality"]
            assert sq["jitter_ms"] == 1.235
            assert sq["variance_ms2"] == 2.568
            assert sq["confidence"] == 0.891
            assert sq["outlier_rate"] == 0.043
            assert sq["total_outliers"] == 3
            assert isinstance(sq["total_outliers"], int)
        finally:
            server.shutdown()

    def test_signal_quality_absent_when_none(self, mock_wan_with_signal):
        """signal_quality section absent when _last_signal_result is None."""
        mock_wan_with_signal._last_signal_result = None
        controller = self._make_controller(mock_wan_with_signal)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            wan_data = data["wans"][0]
            assert "signal_quality" not in wan_data
        finally:
            server.shutdown()

    def test_signal_quality_warming_up_reflected(self, mock_wan_with_signal):
        """warming_up=True reflected correctly during Hampel warmup."""
        mock_wan_with_signal._last_signal_result = SignalResult(
            filtered_rtt=25.0,
            raw_rtt=26.1,
            jitter_ms=1.234,
            variance_ms2=2.567,
            confidence=0.891,
            is_outlier=False,
            outlier_rate=0.042,
            total_outliers=0,
            consecutive_outliers=0,
            warming_up=True,
        )
        controller = self._make_controller(mock_wan_with_signal)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            sq = data["wans"][0]["signal_quality"]
            assert sq["warming_up"] is True
        finally:
            server.shutdown()


class TestIRTTHealth:
    """Tests for irtt section in health endpoint."""

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

    @pytest.fixture
    def mock_wan_with_irtt(self):
        """Create a mock WAN controller for IRTT tests."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def _make_controller(self, wan, irtt_config=None):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = irtt_config or {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def test_irtt_disabled_reason(self, mock_wan_with_irtt):
        """irtt section available=False, reason='disabled' when IRTT disabled and no thread."""
        controller = self._make_controller(mock_wan_with_irtt, irtt_config={"enabled": False})

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert irtt["reason"] == "disabled"
        finally:
            server.shutdown()

    def test_irtt_binary_not_found_reason(self, mock_wan_with_irtt):
        """irtt section available=False, reason='binary_not_found' when enabled but no thread."""
        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "10.10.99.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert irtt["reason"] == "binary_not_found"
        finally:
            server.shutdown()

    def test_irtt_awaiting_first_measurement(self, mock_wan_with_irtt):
        """irtt section available=True, reason='awaiting_first_measurement' when thread exists but no result."""
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = None
        mock_wan_with_irtt._irtt_thread = mock_irtt_thread

        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "10.10.99.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is True
            assert irtt["reason"] == "awaiting_first_measurement"
            assert irtt["rtt_mean_ms"] is None
            assert irtt["ipdv_ms"] is None
            assert irtt["loss_up_pct"] is None
            assert irtt["loss_down_pct"] is None
            assert irtt["server"] is None
            assert irtt["staleness_sec"] is None
            assert irtt["protocol_correlation"] is None
        finally:
            server.shutdown()

    def test_irtt_full_data(self, mock_wan_with_irtt):
        """irtt section has full data when IRTT result available."""
        ts = time.monotonic() - 5.0
        irtt_result = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.3,
            ipdv_mean_ms=1.2,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="10.10.99.1",
            port=2112,
            timestamp=ts,
            success=True,
        )
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = irtt_result
        mock_wan_with_irtt._irtt_thread = mock_irtt_thread
        mock_wan_with_irtt._irtt_correlation = 0.95

        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "10.10.99.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is True
            assert irtt["rtt_mean_ms"] == 28.5
            assert irtt["ipdv_ms"] == 1.2
            assert irtt["loss_up_pct"] == 0.5
            assert irtt["loss_down_pct"] == 1.0
            assert irtt["server"] == "10.10.99.1:2112"
            assert irtt["staleness_sec"] >= 5.0  # At least 5 seconds old
            assert irtt["protocol_correlation"] == 0.95
        finally:
            server.shutdown()

    def test_irtt_protocol_correlation_none(self, mock_wan_with_irtt):
        """protocol_correlation is None when wan_controller._irtt_correlation is None."""
        ts = time.monotonic() - 2.0
        irtt_result = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.3,
            ipdv_mean_ms=1.2,
            send_loss=0.0,
            receive_loss=0.0,
            packets_sent=100,
            packets_received=100,
            server="10.10.99.1",
            port=2112,
            timestamp=ts,
            success=True,
        )
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = irtt_result
        mock_wan_with_irtt._irtt_thread = mock_irtt_thread
        mock_wan_with_irtt._irtt_correlation = None

        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "10.10.99.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["protocol_correlation"] is None
        finally:
            server.shutdown()

    def test_irtt_server_formatted_as_host_port(self, mock_wan_with_irtt):
        """server field formatted as 'host:port' string."""
        ts = time.monotonic() - 1.0
        irtt_result = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.3,
            ipdv_mean_ms=1.2,
            send_loss=0.0,
            receive_loss=0.0,
            packets_sent=100,
            packets_received=100,
            server="192.168.1.1",
            port=3000,
            timestamp=ts,
            success=True,
        )
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = irtt_result
        mock_wan_with_irtt._irtt_thread = mock_irtt_thread
        mock_wan_with_irtt._irtt_correlation = 1.02

        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "192.168.1.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["server"] == "192.168.1.1:3000"
        finally:
            server.shutdown()

    def test_irtt_staleness_computed(self, mock_wan_with_irtt):
        """staleness_sec computed from time.monotonic() - irtt_result.timestamp."""
        ts = time.monotonic() - 10.0
        irtt_result = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.3,
            ipdv_mean_ms=1.2,
            send_loss=0.0,
            receive_loss=0.0,
            packets_sent=100,
            packets_received=100,
            server="10.10.99.1",
            port=2112,
            timestamp=ts,
            success=True,
        )
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = irtt_result
        mock_wan_with_irtt._irtt_thread = mock_irtt_thread
        mock_wan_with_irtt._irtt_correlation = None

        controller = self._make_controller(
            mock_wan_with_irtt,
            irtt_config={"enabled": True, "server": "10.10.99.1"},
        )

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            # Staleness should be approximately 10 seconds (allow some margin)
            assert irtt["staleness_sec"] >= 9.5
            assert irtt["staleness_sec"] <= 15.0
        finally:
            server.shutdown()


class TestReflectorQualityHealth:
    """Tests for reflector_quality section in health endpoint."""

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

    @pytest.fixture
    def mock_wan_with_reflector(self):
        """Create a mock WAN controller for reflector quality tests."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def _make_controller(self, wan, irtt_enabled=False):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": irtt_enabled}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def test_reflector_quality_section_present(self, mock_wan_with_reflector):
        """reflector_quality section present in WAN health with available: True."""
        from wanctl.reflector_scorer import ReflectorScorer, ReflectorStatus

        scorer = MagicMock(spec=ReflectorScorer)
        scorer.get_all_statuses.return_value = [
            ReflectorStatus(
                host="1.1.1.1",
                score=0.95,
                status="active",
                measurements=50,
                consecutive_successes=0,
            ),
        ]
        mock_wan_with_reflector._reflector_scorer = scorer
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            wan_data = data["wans"][0]
            assert "reflector_quality" in wan_data
            assert wan_data["reflector_quality"]["available"] is True
        finally:
            server.shutdown()

    def test_reflector_quality_per_host_details(self, mock_wan_with_reflector):
        """Each host has score (rounded to 3 decimals), status, and measurements."""
        from wanctl.reflector_scorer import ReflectorScorer, ReflectorStatus

        scorer = MagicMock(spec=ReflectorScorer)
        scorer.get_all_statuses.return_value = [
            ReflectorStatus(
                host="1.1.1.1",
                score=0.95123,
                status="active",
                measurements=50,
                consecutive_successes=0,
            ),
            ReflectorStatus(
                host="8.8.8.8",
                score=0.72456,
                status="deprioritized",
                measurements=30,
                consecutive_successes=1,
            ),
        ]
        mock_wan_with_reflector._reflector_scorer = scorer
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            rq = data["wans"][0]["reflector_quality"]
            hosts = rq["hosts"]
            assert "1.1.1.1" in hosts
            assert hosts["1.1.1.1"]["score"] == 0.951  # rounded to 3
            assert hosts["1.1.1.1"]["status"] == "active"
            assert hosts["1.1.1.1"]["measurements"] == 50
            assert hosts["8.8.8.8"]["score"] == 0.725
            assert hosts["8.8.8.8"]["status"] == "deprioritized"
            assert hosts["8.8.8.8"]["measurements"] == 30
        finally:
            server.shutdown()

    def test_reflector_quality_all_active(self, mock_wan_with_reflector):
        """All hosts have status 'active'."""
        from wanctl.reflector_scorer import ReflectorScorer, ReflectorStatus

        scorer = MagicMock(spec=ReflectorScorer)
        scorer.get_all_statuses.return_value = [
            ReflectorStatus(
                host="1.1.1.1",
                score=0.98,
                status="active",
                measurements=50,
                consecutive_successes=0,
            ),
            ReflectorStatus(
                host="8.8.8.8",
                score=0.96,
                status="active",
                measurements=48,
                consecutive_successes=0,
            ),
        ]
        mock_wan_with_reflector._reflector_scorer = scorer
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            hosts = data["wans"][0]["reflector_quality"]["hosts"]
            assert all(h["status"] == "active" for h in hosts.values())
        finally:
            server.shutdown()

    def test_reflector_quality_deprioritized_host(self, mock_wan_with_reflector):
        """One host deprioritized shows status 'deprioritized'."""
        from wanctl.reflector_scorer import ReflectorScorer, ReflectorStatus

        scorer = MagicMock(spec=ReflectorScorer)
        scorer.get_all_statuses.return_value = [
            ReflectorStatus(
                host="1.1.1.1",
                score=0.95,
                status="active",
                measurements=50,
                consecutive_successes=0,
            ),
            ReflectorStatus(
                host="8.8.8.8",
                score=0.65,
                status="deprioritized",
                measurements=50,
                consecutive_successes=2,
            ),
        ]
        mock_wan_with_reflector._reflector_scorer = scorer
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            hosts = data["wans"][0]["reflector_quality"]["hosts"]
            assert hosts["8.8.8.8"]["status"] == "deprioritized"
            assert hosts["1.1.1.1"]["status"] == "active"
        finally:
            server.shutdown()

    def test_reflector_quality_no_scorer(self, mock_wan_with_reflector):
        """When _reflector_scorer is None, section still present with available=True and empty hosts."""
        mock_wan_with_reflector._reflector_scorer = None
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            rq = data["wans"][0]["reflector_quality"]
            assert rq["available"] is True
            assert rq["hosts"] == {}
        finally:
            server.shutdown()

    def test_reflector_quality_empty_hosts(self, mock_wan_with_reflector):
        """Scorer with no hosts returns empty hosts dict."""
        from wanctl.reflector_scorer import ReflectorScorer

        scorer = MagicMock(spec=ReflectorScorer)
        scorer.get_all_statuses.return_value = []
        mock_wan_with_reflector._reflector_scorer = scorer
        controller = self._make_controller(mock_wan_with_reflector)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            rq = data["wans"][0]["reflector_quality"]
            assert rq["available"] is True
            assert rq["hosts"] == {}
        finally:
            server.shutdown()


# =============================================================================
# FUSION HEALTH SECTION (FUSE-05)
# =============================================================================


class TestFusionHealth:
    """Tests for fusion section in health endpoint."""

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

    @pytest.fixture
    def mock_wan_with_fusion(self):
        """Create a mock WAN controller for fusion health tests."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def _make_controller(self, wan, irtt_enabled=False):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": irtt_enabled}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def test_fusion_disabled_shows_minimal_section(self, mock_wan_with_fusion):
        """Fusion disabled shows enabled=False with reason='disabled' and heal state."""
        mock_wan_with_fusion._fusion_enabled = False
        controller = self._make_controller(mock_wan_with_fusion)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            fusion = data["wans"][0]["fusion"]
            assert fusion["enabled"] is False
            assert fusion["reason"] == "disabled"
            assert fusion["heal_state"] == "no_healer"
            assert fusion["heal_grace_active"] is False
        finally:
            server.shutdown()

    def test_fusion_enabled_active_shows_full_state(self, mock_wan_with_fusion):
        """Fusion enabled with active IRTT shows full fused state."""
        mock_wan_with_fusion._fusion_enabled = True
        mock_wan_with_fusion._fusion_icmp_weight = 0.7
        mock_wan_with_fusion._last_fused_rtt = 27.0
        mock_wan_with_fusion._last_icmp_filtered_rtt = 30.0

        irtt_thread = MagicMock()
        irtt_result = IRTTResult(
            rtt_mean_ms=20.0,
            rtt_median_ms=19.5,
            ipdv_mean_ms=1.0,
            send_loss=0.0,
            receive_loss=0.0,
            packets_sent=100,
            packets_received=100,
            server="104.200.21.31",
            port=2112,
            timestamp=time.monotonic(),
            success=True,
        )
        irtt_thread.get_latest.return_value = irtt_result
        irtt_thread.cadence_sec = 10.0
        mock_wan_with_fusion._irtt_thread = irtt_thread

        controller = self._make_controller(mock_wan_with_fusion, irtt_enabled=True)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            fusion = data["wans"][0]["fusion"]
            assert fusion["enabled"] is True
            assert fusion["icmp_weight"] == 0.7
            assert fusion["irtt_weight"] == 0.3
            assert fusion["active_source"] == "fused"
            assert fusion["fused_rtt_ms"] == 27.0
            assert fusion["icmp_rtt_ms"] == 30.0
            assert fusion["irtt_rtt_ms"] == 20.0
        finally:
            server.shutdown()

    def test_fusion_enabled_icmp_only_no_irtt_thread(self, mock_wan_with_fusion):
        """Fusion enabled but IRTT thread None shows icmp_only."""
        mock_wan_with_fusion._fusion_enabled = True
        mock_wan_with_fusion._fusion_icmp_weight = 0.7
        mock_wan_with_fusion._irtt_thread = None
        mock_wan_with_fusion._last_icmp_filtered_rtt = 30.0
        mock_wan_with_fusion._last_fused_rtt = None

        controller = self._make_controller(mock_wan_with_fusion)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            fusion = data["wans"][0]["fusion"]
            assert fusion["enabled"] is True
            assert fusion["active_source"] == "icmp_only"
            assert fusion["fused_rtt_ms"] is None
            assert fusion["irtt_rtt_ms"] is None
            assert fusion["icmp_rtt_ms"] == 30.0
        finally:
            server.shutdown()

    def test_fusion_enabled_icmp_only_stale_irtt(self, mock_wan_with_fusion):
        """Fusion enabled with stale IRTT shows icmp_only."""
        mock_wan_with_fusion._fusion_enabled = True
        mock_wan_with_fusion._fusion_icmp_weight = 0.7
        mock_wan_with_fusion._last_icmp_filtered_rtt = 30.0
        mock_wan_with_fusion._last_fused_rtt = None

        irtt_thread = MagicMock()
        # Stale: 60 seconds ago with 10s cadence (60 > 30 threshold)
        irtt_result = IRTTResult(
            rtt_mean_ms=20.0,
            rtt_median_ms=19.5,
            ipdv_mean_ms=1.0,
            send_loss=0.0,
            receive_loss=0.0,
            packets_sent=100,
            packets_received=100,
            server="104.200.21.31",
            port=2112,
            timestamp=time.monotonic() - 60.0,
            success=True,
        )
        irtt_thread.get_latest.return_value = irtt_result
        irtt_thread.cadence_sec = 10.0
        mock_wan_with_fusion._irtt_thread = irtt_thread

        controller = self._make_controller(mock_wan_with_fusion, irtt_enabled=True)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            fusion = data["wans"][0]["fusion"]
            assert fusion["active_source"] == "icmp_only"
        finally:
            server.shutdown()

    def test_fusion_section_always_present(self, mock_wan_with_fusion):
        """Fusion section exists even when disabled with minimal mock."""
        mock_wan_with_fusion._fusion_enabled = False
        controller = self._make_controller(mock_wan_with_fusion)

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            wan_data = data["wans"][0]
            assert "fusion" in wan_data
        finally:
            server.shutdown()


# =============================================================================
# HYSTERESIS HEALTH ENDPOINT TESTS (OBSV-01)
# =============================================================================


class TestHysteresisHealth:
    """Tests for hysteresis sub-dict in health endpoint download/upload sections."""

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

    @pytest.fixture
    def mock_wan_with_hysteresis(self):
        """Create a mock WAN controller with hysteresis state."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 17
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 1
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 5
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 1712345000.0
        wan._suppression_alert_threshold = 20
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        _configure_wan_health_data(wan)
        return wan

    def _make_controller(self, wan):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def test_health_hysteresis_in_download(self, mock_wan_with_hysteresis):
        """Health endpoint download section has hysteresis with correct values."""
        controller = self._make_controller(mock_wan_with_hysteresis)
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            dl = data["wans"][0]["download"]["hysteresis"]
            assert dl["dwell_counter"] == 0
            assert dl["transitions_suppressed"] == 17
        finally:
            server.shutdown()

    def test_health_hysteresis_in_upload(self, mock_wan_with_hysteresis):
        """Health endpoint upload section has hysteresis with correct values."""
        controller = self._make_controller(mock_wan_with_hysteresis)
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            ul = data["wans"][0]["upload"]["hysteresis"]
            assert ul["dwell_counter"] == 1
            assert ul["transitions_suppressed"] == 5
        finally:
            server.shutdown()

    def test_health_hysteresis_keys_complete(self, mock_wan_with_hysteresis):
        """Both download and upload hysteresis dicts have all 4 required keys."""
        controller = self._make_controller(mock_wan_with_hysteresis)
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            expected_keys = {
                "dwell_counter", "dwell_cycles", "deadband_ms", "transitions_suppressed",
                "suppressions_per_min", "window_start_epoch", "alert_threshold_per_min",
            }
            dl_keys = set(data["wans"][0]["download"]["hysteresis"].keys())
            ul_keys = set(data["wans"][0]["upload"]["hysteresis"].keys())
            assert dl_keys == expected_keys
            assert ul_keys == expected_keys
        finally:
            server.shutdown()

    def test_health_hysteresis_config_values(self, mock_wan_with_hysteresis):
        """Hysteresis config values (dwell_cycles, deadband_ms) reflect configured values."""
        controller = self._make_controller(mock_wan_with_hysteresis)
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            dl = data["wans"][0]["download"]["hysteresis"]
            assert dl["dwell_cycles"] == 3
            assert dl["deadband_ms"] == 3.0
        finally:
            server.shutdown()


class TestCycleBudgetStatus:
    """Tests for cycle budget status field computation (Phase 132: PERF-03, D-06)."""

    @staticmethod
    def _make_profiler(avg_ms: float) -> OperationProfiler:
        """Build a profiler with a single total-cycle sample at the given avg_ms."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", avg_ms)
        return profiler

    def test_status_ok(self):
        """utilization=50% (25ms/50ms) with threshold=80 -> status='ok'."""
        profiler = self._make_profiler(25.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is not None
        assert result["status"] == "ok"
        assert result["utilization_pct"] == 50.0

    def test_status_warning(self):
        """utilization=84% (42ms/50ms) with threshold=80 -> status='warning'."""
        profiler = self._make_profiler(42.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is not None
        assert result["status"] == "warning"
        assert result["utilization_pct"] == 84.0

    def test_status_critical(self):
        """utilization=110% (55ms/50ms) with threshold=80 -> status='critical'."""
        profiler = self._make_profiler(55.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is not None
        assert result["status"] == "critical"
        assert result["utilization_pct"] == 110.0

    def test_status_boundary_warning(self):
        """utilization=80.0% exactly with threshold=80.0 -> status='warning' (>= comparison)."""
        profiler = self._make_profiler(40.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is not None
        assert result["status"] == "warning"
        assert result["utilization_pct"] == 80.0

    def test_status_boundary_critical(self):
        """utilization=100.0% exactly -> status='critical' (>= comparison)."""
        profiler = self._make_profiler(50.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is not None
        assert result["status"] == "critical"
        assert result["utilization_pct"] == 100.0

    def test_custom_threshold(self):
        """utilization=70% (35ms/50ms) with threshold=60 -> status='warning'."""
        profiler = self._make_profiler(35.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=60.0,
        )
        assert result is not None
        assert result["status"] == "warning"
        assert result["utilization_pct"] == 70.0

    def test_warning_threshold_in_result(self):
        """Result dict contains 'warning_threshold_pct' key matching input."""
        profiler = self._make_profiler(25.0)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=75.0,
        )
        assert result is not None
        assert "warning_threshold_pct" in result
        assert result["warning_threshold_pct"] == 75.0

    def test_none_when_no_data(self):
        """Profiler with no data still returns None (existing behavior preserved)."""
        profiler = OperationProfiler(max_samples=1200)
        result = _build_cycle_budget(
            profiler,
            overrun_count=0,
            cycle_interval_ms=50.0,
            total_label="autorate_cycle_total",
            warning_threshold_pct=80.0,
        )
        assert result is None


class TestCycleBudgetAlert:
    """Tests for cycle budget warning alert firing (Phase 132: PERF-03, D-07)."""

    @staticmethod
    def _make_controller_stub(
        threshold: float = 80.0,
        consecutive: int = 3,
        interval_ms: float = 50.0,
    ):
        """Build a minimal stub with the attributes _check_cycle_budget_alert needs."""
        from wanctl.wan_controller import WANController

        stub = MagicMock(spec=[])  # No auto-attributes
        stub._warning_threshold_pct = threshold
        stub._budget_warning_streak = 0
        stub._budget_warning_consecutive = consecutive
        stub._cycle_interval_ms = interval_ms
        stub.alert_engine = MagicMock()
        stub.wan_name = "spectrum"
        # Bind the real method to our stub
        stub._check_cycle_budget_alert = WANController._check_cycle_budget_alert.__get__(
            stub, type(stub)
        )
        return stub

    def test_alert_fires_after_consecutive_overruns(self):
        """Alert fires on Nth consecutive overrun cycle."""
        stub = self._make_controller_stub(threshold=80.0, consecutive=3)
        # 90% utilization: 45ms / 50ms
        stub._check_cycle_budget_alert(45.0)
        assert stub._budget_warning_streak == 1
        assert stub.alert_engine.fire.call_count == 0

        stub._check_cycle_budget_alert(45.0)
        assert stub._budget_warning_streak == 2
        assert stub.alert_engine.fire.call_count == 0

        stub._check_cycle_budget_alert(45.0)
        assert stub._budget_warning_streak == 3
        assert stub.alert_engine.fire.call_count == 1
        call_kwargs = stub.alert_engine.fire.call_args
        assert call_kwargs[1]["alert_type"] == "cycle_budget_warning"

    def test_alert_streak_resets_on_normal(self):
        """Streak resets to 0 when utilization drops below threshold."""
        stub = self._make_controller_stub(threshold=80.0, consecutive=3)
        # Build up streak
        stub._check_cycle_budget_alert(45.0)
        stub._check_cycle_budget_alert(45.0)
        assert stub._budget_warning_streak == 2

        # Drop below threshold: 60% utilization
        stub._check_cycle_budget_alert(30.0)
        assert stub._budget_warning_streak == 0

    def test_alert_not_fired_below_threshold(self):
        """No alert when utilization stays below threshold for many cycles."""
        stub = self._make_controller_stub(threshold=80.0, consecutive=3)
        # 70% utilization: 35ms / 50ms -- below 80% threshold
        for _ in range(100):
            stub._check_cycle_budget_alert(35.0)
        assert stub.alert_engine.fire.call_count == 0
        assert stub._budget_warning_streak == 0


class TestReloadCycleBudgetConfig:
    """Tests for SIGUSR1 cycle budget config reload (Phase 132: PERF-03)."""

    @staticmethod
    def _make_controller_stub(threshold: float = 80.0):
        """Build a minimal stub with attributes _reload_cycle_budget_config needs."""
        from wanctl.wan_controller import WANController

        stub = MagicMock(spec=[])
        stub._warning_threshold_pct = threshold
        stub.config = MagicMock()
        stub.config.config_file_path = "/tmp/test_wanctl_config.yaml"
        stub.logger = MagicMock()
        stub._reload_cycle_budget_config = (
            WANController._reload_cycle_budget_config.__get__(stub, type(stub))
        )
        return stub

    def test_reload_updates_threshold(self):
        """Reload picks up new warning_threshold_pct from YAML."""
        stub = self._make_controller_stub(threshold=80.0)

        yaml_data = {"continuous_monitoring": {"warning_threshold_pct": 90.0}}
        with patch("builtins.open", MagicMock()):
            with patch("yaml.safe_load", return_value=yaml_data):
                stub._reload_cycle_budget_config()

        assert stub._warning_threshold_pct == 90.0

    def test_reload_rejects_invalid(self):
        """Invalid (non-numeric) value keeps current threshold."""
        stub = self._make_controller_stub(threshold=80.0)

        yaml_data = {"continuous_monitoring": {"warning_threshold_pct": "invalid"}}
        with patch("builtins.open", MagicMock()):
            with patch("yaml.safe_load", return_value=yaml_data):
                stub._reload_cycle_budget_config()

        assert stub._warning_threshold_pct == 80.0

    def test_reload_rejects_out_of_range(self):
        """Out-of-range value (>200) keeps current threshold."""
        stub = self._make_controller_stub(threshold=80.0)

        yaml_data = {"continuous_monitoring": {"warning_threshold_pct": 300.0}}
        with patch("builtins.open", MagicMock()):
            with patch("yaml.safe_load", return_value=yaml_data):
                stub._reload_cycle_budget_config()

        assert stub._warning_threshold_pct == 80.0


# =============================================================================
# MERGED FROM test_health_check_history.py
# =============================================================================


@pytest.fixture(autouse=True)
def reset_handler_state():
    """Reset HealthCheckHandler class state before each test."""
    HealthCheckHandler.controller = None
    HealthCheckHandler.start_time = None
    HealthCheckHandler.consecutive_failures = 0
    yield
    HealthCheckHandler.controller = None
    HealthCheckHandler.start_time = None
    HealthCheckHandler.consecutive_failures = 0


@pytest.fixture
def sample_db(tmp_path: Path):
    """Create a temporary database with sample metrics data.

    Creates 10 sample metrics with timestamps spanning the last hour.
    """
    db_path = tmp_path / "test_metrics.db"

    # Reset singleton before creating test instance
    MetricsWriter._reset_instance()

    writer = MetricsWriter(db_path=db_path)

    # Generate sample data: 10 metrics over the last 30 minutes
    base_time = int(time.time()) - 1800  # 30 minutes ago

    # write_metrics_batch expects list of tuples:
    # (timestamp, wan_name, metric_name, value, labels, granularity)
    metrics = []
    for i in range(10):
        timestamp = base_time + (i * 180)  # Every 3 minutes
        metrics.extend(
            [
                (timestamp, "spectrum", "wanctl_rtt_ms", 25.0 + i, None, "raw"),
                (timestamp, "spectrum", "wanctl_state", 1.0, None, "raw"),  # GREEN
            ]
        )

    writer.write_metrics_batch(metrics)

    yield db_path

    # Cleanup
    MetricsWriter._reset_instance()


class TestMetricsHistoryEndpoint:
    """Integration tests for /metrics/history endpoint."""

    def test_returns_json(self, sample_db: Path):
        """GET /metrics/history returns 200 and valid JSON."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    assert response.status == 200
                    data = json.loads(response.read().decode())

                assert "data" in data
                assert "metadata" in data
                assert isinstance(data["data"], list)
            finally:
                server.shutdown()

    def test_default_time_range(self, sample_db: Path):
        """No params defaults to last 1 hour."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should find our sample data from last 30 minutes
                assert data["metadata"]["total_count"] > 0
            finally:
                server.shutdown()

    def test_range_param(self, sample_db: Path):
        """?range=1h filters to last hour."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?range=1h"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should include our sample data
                assert data["metadata"]["total_count"] > 0
            finally:
                server.shutdown()

    def test_from_to_params(self, sample_db: Path):
        """?from=...&to=... filters by absolute time range."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                # Query for a time range that includes our data
                # Use a range < 6 hours to get "raw" granularity (matching our test data)
                from datetime import datetime

                now = datetime.now()
                from_dt = now.replace(hour=0, minute=0, second=0)  # Start of today
                to_dt = now  # Now

                from_iso = from_dt.isoformat()
                to_iso = to_dt.isoformat()

                url = f"http://127.0.0.1:{port}/metrics/history?from={from_iso}&to={to_iso}"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should find data and use the from/to we specified in query
                assert "query" in data["metadata"]
                assert data["metadata"]["query"]["start"] is not None
                assert data["metadata"]["query"]["end"] is not None
            finally:
                server.shutdown()

    def test_metrics_filter(self, sample_db: Path):
        """?metrics=wanctl_rtt_ms filters by metric name."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?metrics=wanctl_rtt_ms"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # All returned records should be wanctl_rtt_ms
                for record in data["data"]:
                    assert record["metric_name"] == "wanctl_rtt_ms"
            finally:
                server.shutdown()

    def test_wan_filter(self, sample_db: Path):
        """?wan=spectrum filters by WAN name."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?wan=spectrum"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # All returned records should be spectrum
                for record in data["data"]:
                    assert record["wan_name"] == "spectrum"
            finally:
                server.shutdown()

    def test_pagination_limit(self, sample_db: Path):
        """?limit=5 returns at most 5 results."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=5"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                assert data["metadata"]["returned_count"] <= 5
                assert len(data["data"]) <= 5
                assert data["metadata"]["limit"] == 5
            finally:
                server.shutdown()

    def test_pagination_offset(self, sample_db: Path):
        """?offset=5 skips first 5 results."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                # First get all results
                url_all = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url_all, timeout=5) as response:
                    data_all = json.loads(response.read().decode())

                # Then get with offset
                url_offset = f"http://127.0.0.1:{port}/metrics/history?offset=5"
                with urllib.request.urlopen(url_offset, timeout=5) as response:
                    data_offset = json.loads(response.read().decode())

                # Offset should skip first 5
                assert data_offset["metadata"]["offset"] == 5
                if data_all["metadata"]["total_count"] > 5:
                    assert (
                        data_offset["metadata"]["returned_count"]
                        == data_all["metadata"]["total_count"] - 5
                    )
            finally:
                server.shutdown()

    def test_pagination_metadata(self, sample_db: Path):
        """Response includes total_count and returned_count."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=3"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                assert "total_count" in data["metadata"]
                assert "returned_count" in data["metadata"]
                assert data["metadata"]["total_count"] >= data["metadata"]["returned_count"]
            finally:
                server.shutdown()

    def test_empty_results(self, tmp_path: Path):
        """Returns 200 with empty data array when no matches."""
        # Create empty database (just initialize writer without adding data)
        db_path = tmp_path / "empty.db"
        MetricsWriter._reset_instance()
        _ = MetricsWriter(db_path=db_path)
        MetricsWriter._reset_instance()

        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", db_path):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    assert response.status == 200
                    data = json.loads(response.read().decode())

                assert data["data"] == []
                assert data["metadata"]["total_count"] == 0
            finally:
                server.shutdown()

    def test_response_metadata_structure(self, sample_db: Path):
        """Verify all metadata fields are present."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                metadata = data["metadata"]
                assert "total_count" in metadata
                assert "returned_count" in metadata
                assert "granularity" in metadata
                assert "limit" in metadata
                assert "offset" in metadata
                assert "query" in metadata

                query = metadata["query"]
                assert "start" in query
                assert "end" in query
                assert "metrics" in query
                assert "wan" in query
            finally:
                server.shutdown()

    def test_timestamp_format_iso8601(self, sample_db: Path):
        """Data timestamps are ISO 8601 strings."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                if data["data"]:
                    # Check first record timestamp is ISO 8601
                    ts = data["data"][0]["timestamp"]
                    assert "T" in ts  # ISO 8601 has T separator
                    assert ":" in ts  # Has time component
            finally:
                server.shutdown()


class TestHistoryParamsValidation:
    """Tests for 400 error responses on invalid params."""

    def test_invalid_range_format(self, sample_db: Path):
        """?range=abc returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?range=abc"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_limit_not_integer(self, sample_db: Path):
        """?limit=abc returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=abc"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_offset_not_integer(self, sample_db: Path):
        """?offset=xyz returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?offset=xyz"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_from_timestamp(self, sample_db: Path):
        """?from=not-a-date returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?from=not-a-date"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()


class TestHistoryHelperMethods:
    """Unit tests for helper methods used by /metrics/history."""

    def test_parse_duration_hours(self):
        """'1h' parses to 3600 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "1h")
        assert result == timedelta(seconds=3600)

    def test_parse_duration_minutes(self):
        """'30m' parses to 1800 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "30m")
        assert result == timedelta(seconds=1800)

    def test_parse_duration_days(self):
        """'7d' parses to 604800 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "7d")
        assert result == timedelta(seconds=604800)

    def test_parse_duration_weeks(self):
        """'2w' parses to 2 weeks in seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "2w")
        assert result == timedelta(seconds=604800 * 2)

    def test_parse_duration_seconds(self):
        """'60s' parses to 60 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "60s")
        assert result == timedelta(seconds=60)

    def test_parse_duration_invalid(self):
        """Invalid format raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_duration(handler, "abc")
        assert "Invalid duration" in str(exc_info.value)

    def test_parse_duration_invalid_unit(self):
        """Invalid unit raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_duration(handler, "5x")
        assert "Invalid duration" in str(exc_info.value)

    def test_parse_iso_timestamp_basic(self):
        """Basic ISO 8601 timestamp parses correctly."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_iso_timestamp(handler, "2026-01-25T14:30:00")
        assert isinstance(result, int)
        assert result > 0

    def test_parse_iso_timestamp_with_timezone(self):
        """ISO 8601 with timezone parses correctly."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_iso_timestamp(handler, "2026-01-25T14:30:00+00:00")
        assert isinstance(result, int)
        assert result > 0

    def test_parse_iso_timestamp_invalid(self):
        """Invalid timestamp raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_iso_timestamp(handler, "not-a-timestamp")
        assert "Invalid timestamp" in str(exc_info.value)

    def test_format_metric_iso8601(self):
        """Unix timestamp is converted to ISO 8601."""
        handler = MagicMock(spec=HealthCheckHandler)
        row = {
            "timestamp": 1737842400,  # Some Unix timestamp
            "wan_name": "spectrum",
            "metric_name": "wanctl_rtt_ms",
            "value": 25.5,
            "labels": None,
            "granularity": "raw",
        }
        result = HealthCheckHandler._format_metric(handler, row)

        assert "T" in result["timestamp"]  # ISO 8601 has T separator
        assert result["wan_name"] == "spectrum"
        assert result["metric_name"] == "wanctl_rtt_ms"
        assert result["value"] == 25.5

    def test_resolve_time_range_with_duration(self):
        """range param resolves to (now - duration, now)."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=timedelta(hours=1),
            from_ts=None,
            to_ts=None,
        )

        assert end_ts > start_ts
        assert (end_ts - start_ts) == 3600  # 1 hour

    def test_resolve_time_range_with_from_to(self):
        """from/to params resolve to specified range."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=None,
            from_ts=1000,
            to_ts=2000,
        )

        assert start_ts == 1000
        assert end_ts == 2000

    def test_resolve_time_range_default(self):
        """No params defaults to last 1 hour."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=None,
            from_ts=None,
            to_ts=None,
        )

        assert end_ts > start_ts
        assert (end_ts - start_ts) == 3600  # 1 hour default


class TestBurstDetectionSection:
    """Tests for burst_detection section in health endpoint (Phase 151)."""

    def _make_handler(self):
        """Create a HealthCheckHandler without starting a server."""
        handler = HealthCheckHandler.__new__(HealthCheckHandler)
        return handler

    def test_burst_detection_section_with_result(self):
        """Build burst_detection section when a BurstResult is available."""
        from wanctl.burst_detector import BurstResult

        result = BurstResult(
            acceleration=1.234, velocity=2.567, is_burst=False,
            consecutive_accel=1, warming_up=False,
        )
        health_data = {
            "burst_detection": {
                "enabled": True,
                "result": result,
                "total_bursts": 5,
            },
        }

        handler = self._make_handler()
        section = handler._build_burst_detection_section(health_data)

        assert section["enabled"] is True
        assert section["total_bursts"] == 5
        assert section["burst_response_enabled"] is False
        assert section["current_acceleration"] == 1.234
        assert section["current_velocity"] == 2.567
        assert section["is_burst"] is False
        assert section["consecutive_accel_cycles"] == 1
        assert section["warming_up"] is False

    def test_burst_detection_section_with_none_result(self):
        """Build burst_detection section when result is None (pre-warmup)."""
        health_data = {
            "burst_detection": {
                "enabled": True,
                "result": None,
                "total_bursts": 0,
            },
        }

        handler = self._make_handler()
        section = handler._build_burst_detection_section(health_data)

        assert section["enabled"] is True
        assert section["total_bursts"] == 0
        assert section["burst_response_enabled"] is False
        assert section["current_acceleration"] is None
        assert section["current_velocity"] is None
        assert section["is_burst"] is False
        assert section["consecutive_accel_cycles"] == 0
        assert section["warming_up"] is True

    def test_burst_detection_section_disabled(self):
        """Build burst_detection section when detection is disabled."""
        health_data = {
            "burst_detection": {
                "enabled": False,
                "result": None,
                "total_bursts": 0,
            },
        }

        handler = self._make_handler()
        section = handler._build_burst_detection_section(health_data)

        assert section["enabled"] is False
        assert section["burst_response_enabled"] is False


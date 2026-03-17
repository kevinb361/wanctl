"""Tests for the health check HTTP endpoint."""

import json
import socket
import time
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

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


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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
        time.sleep(0.1)  # Give thread time to finish

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

        # Mock upload queue
        mock_wan_controller.upload.current_rate = 35_000_000
        mock_wan_controller.upload.red_streak = 0
        mock_wan_controller.upload.soft_red_streak = 0
        mock_wan_controller.upload.soft_red_required = 3
        mock_wan_controller.upload.green_streak = 5
        mock_wan_controller.upload.green_required = 5

        # Mock router connectivity state
        mock_wan_controller.router_connectivity.is_reachable = True
        mock_wan_controller.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }

        # Prevent MagicMock truthy issues for signal/IRTT attributes
        mock_wan_controller._last_signal_result = None
        mock_wan_controller._irtt_thread = None
        mock_wan_controller._irtt_correlation = None
        mock_wan_controller._last_asymmetry_result = None

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
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues for signal/IRTT attributes
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
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
        wan1.upload.current_rate = 20_000_000
        wan1.upload.red_streak = 0
        wan1.upload.soft_red_streak = 0
        wan1.upload.soft_red_required = 3
        wan1.upload.green_streak = 5
        wan1.upload.green_required = 5
        wan1.router_connectivity.is_reachable = True
        wan1.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Prevent MagicMock truthy issues for signal/IRTT attributes
        wan1._last_signal_result = None
        wan1._irtt_thread = None
        wan1._irtt_correlation = None
        wan1._last_asymmetry_result = None

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
        wan2.upload.current_rate = 10_000_000
        wan2.upload.red_streak = 0
        wan2.upload.soft_red_streak = 0
        wan2.upload.soft_red_required = 3
        wan2.upload.green_streak = 5
        wan2.upload.green_required = 5
        wan2.router_connectivity.is_reachable = False
        wan2.router_connectivity.to_dict.return_value = {
            "is_reachable": False,
            "consecutive_failures": 5,
            "last_failure_type": "connection_refused",
            "last_failure_time": 98765.0,
        }
        # Prevent MagicMock truthy issues for signal/IRTT attributes
        wan2._last_signal_result = None
        wan2._irtt_thread = None
        wan2._irtt_correlation = None
        wan2._last_asymmetry_result = None

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
        result = _build_cycle_budget(profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total")
        assert result is None

    def test_returns_correct_dict_when_profiler_has_data(self):
        """Populated profiler returns dict with cycle_time_ms, utilization_pct, overrun_count."""
        profiler = OperationProfiler(max_samples=1200)
        # Record some sample data
        for val in [37.0, 38.0, 39.0, 40.0, 41.0]:
            profiler.record("autorate_cycle_total", val)

        result = _build_cycle_budget(profiler, overrun_count=5, cycle_interval_ms=50.0, total_label="autorate_cycle_total")
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

        result = _build_cycle_budget(profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total")
        assert result is not None
        # (37.6 / 50.0) * 100 = 75.2
        assert result["utilization_pct"] == 75.2

    def test_cycle_time_values_rounded_to_1_decimal(self):
        """cycle_time_ms values should be rounded to 1 decimal place."""
        profiler = OperationProfiler(max_samples=1200)
        profiler.record("autorate_cycle_total", 37.654)
        profiler.record("autorate_cycle_total", 38.123)

        result = _build_cycle_budget(profiler, overrun_count=0, cycle_interval_ms=50.0, total_label="autorate_cycle_total")
        assert result is not None
        # Check all values are rounded to 1 decimal
        for key in ("avg", "p95", "p99"):
            value = result["cycle_time_ms"][key]
            # Multiply by 10 -- should be an integer (i.e., 1 decimal place)
            assert value == round(value, 1), f"{key} not rounded to 1 decimal: {value}"


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
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }

        # Prevent MagicMock truthy issues for signal/IRTT attributes
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None

        # Set profiler attributes (from Plan 01)
        wan._profiler = OperationProfiler(max_samples=1200)
        wan._overrun_count = overrun_count
        wan._cycle_interval_ms = 50.0

        if with_profiler_data:
            for val in [37.0, 38.0, 39.0, 40.0, 41.0, 42.0, 43.0, 44.0, 45.0, 46.0]:
                wan._profiler.record("autorate_cycle_total", val)

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
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
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
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
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
        controller = self._make_controller(
            mock_wan_with_irtt, irtt_config={"enabled": False}
        )

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
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
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
            ReflectorStatus(host="1.1.1.1", score=0.95, status="active", measurements=50, consecutive_successes=0),
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
            ReflectorStatus(host="1.1.1.1", score=0.95123, status="active", measurements=50, consecutive_successes=0),
            ReflectorStatus(host="8.8.8.8", score=0.72456, status="deprioritized", measurements=30, consecutive_successes=1),
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
            ReflectorStatus(host="1.1.1.1", score=0.98, status="active", measurements=50, consecutive_successes=0),
            ReflectorStatus(host="8.8.8.8", score=0.96, status="active", measurements=48, consecutive_successes=0),
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
            ReflectorStatus(host="1.1.1.1", score=0.95, status="active", measurements=50, consecutive_successes=0),
            ReflectorStatus(host="8.8.8.8", score=0.65, status="deprioritized", measurements=50, consecutive_successes=2),
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

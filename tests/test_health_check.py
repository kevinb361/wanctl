"""Tests for the health check HTTP endpoint."""

import json
import socket
import time
import urllib.request
from unittest.mock import MagicMock

import pytest

from wanctl.health_check import (
    HealthCheckHandler,
    HealthCheckServer,
    _get_current_state,
    start_health_server,
    update_health_status,
)


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

        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"

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
        return wan

    def test_health_includes_router_connectivity_per_wan(self, mock_wan_controller):
        """Test that each WAN includes router_connectivity section."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
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

        mock_controller = MagicMock()
        config1 = MagicMock()
        config1.wan_name = "spectrum"
        config2 = MagicMock()
        config2.wan_name = "att"
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

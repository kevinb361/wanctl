"""Tests for the steering health check HTTP endpoint."""

import json
import socket
import time
import urllib.error
import urllib.request

import pytest

from wanctl import __version__
from wanctl.steering.health import (
    SteeringHealthHandler,
    SteeringHealthServer,
    start_steering_health_server,
    update_steering_health_status,
)


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestSteeringHealthServer:
    """Integration tests for the steering health check server."""

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

    def test_health_endpoint_returns_json(self):
        """Test that /health endpoint returns valid JSON with required fields."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data
        finally:
            server.shutdown()

    def test_health_root_path(self):
        """Test that / endpoint returns same response as /health."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data
            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_health_status_healthy(self):
        """Test that health endpoint returns healthy status when failures = 0."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            # Ensure failures = 0 (default from start_steering_health_server)
            assert SteeringHealthHandler.consecutive_failures == 0

            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_health_status_degraded(self):
        """Test that health endpoint returns degraded status when failures >= 3."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            # Set failures to threshold (3)
            update_steering_health_status(3)

            url = f"http://127.0.0.1:{port}/health"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
        finally:
            server.shutdown()

    def test_health_status_threshold(self):
        """Test that threshold for degraded is exactly 3 consecutive failures."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"

            # failures = 2, should still be healthy
            update_steering_health_status(2)
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())
            assert data["status"] == "healthy"

            # failures = 3, should now be degraded
            update_steering_health_status(3)
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)
            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
        finally:
            server.shutdown()

    def test_health_uptime_increases(self):
        """Test that uptime_seconds increases over time."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"

            # First request
            with urllib.request.urlopen(url, timeout=5) as response:
                data1 = json.loads(response.read().decode())
            uptime1 = data1["uptime_seconds"]

            # Wait a bit
            time.sleep(0.15)

            # Second request
            with urllib.request.urlopen(url, timeout=5) as response:
                data2 = json.loads(response.read().decode())
            uptime2 = data2["uptime_seconds"]

            # Uptime should have increased
            assert uptime2 > uptime1
        finally:
            server.shutdown()

    def test_health_version(self):
        """Test that version field matches wanctl.__version__."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["version"] == __version__
        finally:
            server.shutdown()

    def test_health_404_unknown_path(self):
        """Test that unknown paths return 404 with JSON error."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/unknown"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 404
            data = json.loads(exc_info.value.read().decode())
            assert "error" in data
            assert data["error"] == "Not found"
        finally:
            server.shutdown()

    def test_health_server_shutdown(self):
        """Test that server thread stops after shutdown()."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        assert isinstance(server, SteeringHealthServer)
        assert server.thread.is_alive()

        server.shutdown()
        time.sleep(0.1)  # Give thread time to finish

        assert not server.thread.is_alive()


class TestUpdateSteeringHealthStatus:
    """Tests for update_steering_health_status function."""

    def test_update_health_status(self):
        """Test that update_steering_health_status updates the failure count."""
        # Reset to known state
        SteeringHealthHandler.consecutive_failures = 0

        update_steering_health_status(5)
        assert SteeringHealthHandler.consecutive_failures == 5

        update_steering_health_status(0)
        assert SteeringHealthHandler.consecutive_failures == 0

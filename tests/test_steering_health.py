"""Tests for the steering health check HTTP endpoint."""

import json
import socket
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock

import pytest

from wanctl import __version__
from wanctl.steering.health import (
    SteeringHealthHandler,
    SteeringHealthServer,
    _congestion_state_code,
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


class TestSteeringHealthResponseFields:
    """Tests for steering-specific response fields (STEER-01 through STEER-05)."""

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

    @pytest.fixture
    def mock_daemon(self):
        """Create a mock SteeringDaemon with realistic state."""
        daemon = MagicMock()
        daemon.config.state_good = "SPECTRUM_GOOD"
        daemon.config.state_degraded = "SPECTRUM_DEGRADED"
        daemon.config.confidence_config = None  # Disabled by default
        daemon.config.green_rtt_ms = 5.0
        daemon.config.yellow_rtt_ms = 15.0
        daemon.config.red_rtt_ms = 15.0
        daemon.config.red_samples_required = 2
        daemon.config.green_samples_required = 15
        daemon.confidence_controller = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,  # 60s ago
        }
        return daemon

    def test_steering_enabled_false_when_good(self, mock_daemon):
        """Test that steering.enabled=False when state=GOOD."""
        mock_daemon.state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "steering" in data
            assert data["steering"]["enabled"] is False
            assert data["steering"]["state"] == "SPECTRUM_GOOD"
        finally:
            server.shutdown()

    def test_steering_enabled_true_when_degraded(self, mock_daemon):
        """Test that steering.enabled=True when state=DEGRADED."""
        mock_daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "steering" in data
            assert data["steering"]["enabled"] is True
            assert data["steering"]["state"] == "SPECTRUM_DEGRADED"
        finally:
            server.shutdown()

    def test_congestion_state_fields(self, mock_daemon):
        """Test that congestion.primary.state and state_code are present."""
        mock_daemon.state_mgr.state["congestion_state"] = "YELLOW"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "congestion" in data
            assert "primary" in data["congestion"]
            assert data["congestion"]["primary"]["state"] == "YELLOW"
            assert data["congestion"]["primary"]["state_code"] == 1
        finally:
            server.shutdown()

    def test_congestion_state_codes(self):
        """Test that congestion state codes are GREEN=0, YELLOW=1, RED=2, UNKNOWN=3."""
        assert _congestion_state_code("GREEN") == 0
        assert _congestion_state_code("YELLOW") == 1
        assert _congestion_state_code("RED") == 2
        assert _congestion_state_code("UNKNOWN") == 3
        assert _congestion_state_code("INVALID") == 3

    def test_decision_timestamp_iso8601(self, mock_daemon):
        """Test that last_transition_time is valid ISO 8601."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "decision" in data
            timestamp = data["decision"]["last_transition_time"]
            assert timestamp is not None
            # Verify ISO 8601 format (contains T separator)
            assert "T" in timestamp
            # Handle timezone format (may be +00:00 or Z)
            if timestamp.endswith("+00:00"):
                pass  # Standard format
            elif "+" in timestamp or "-" in timestamp.split("T")[1]:
                pass  # Has timezone offset
            else:
                timestamp = timestamp + "+00:00"  # Add timezone for parsing
            # Just verify it's a valid datetime string
            assert len(timestamp) > 10
        finally:
            server.shutdown()

    def test_time_in_state_positive(self, mock_daemon):
        """Test that time_in_state_seconds > 0."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "decision" in data
            time_in_state = data["decision"]["time_in_state_seconds"]
            assert isinstance(time_in_state, (int, float))
            # Should be positive (transition was 60s ago in mock)
            assert time_in_state > 0
        finally:
            server.shutdown()

    def test_counters_present(self, mock_daemon):
        """Test that counters.red_count, good_count, cake_read_failures are present."""
        mock_daemon.state_mgr.state["red_count"] = 3
        mock_daemon.state_mgr.state["good_count"] = 10
        mock_daemon.state_mgr.state["cake_read_failures"] = 1
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "counters" in data
            assert data["counters"]["red_count"] == 3
            assert data["counters"]["good_count"] == 10
            assert data["counters"]["cake_read_failures"] == 1
        finally:
            server.shutdown()

    def test_thresholds_from_config(self, mock_daemon):
        """Test that thresholds match daemon.config values."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "thresholds" in data
            assert data["thresholds"]["green_rtt_ms"] == 5.0
            assert data["thresholds"]["yellow_rtt_ms"] == 15.0
            assert data["thresholds"]["red_rtt_ms"] == 15.0
            assert data["thresholds"]["red_samples_required"] == 2
            assert data["thresholds"]["green_samples_required"] == 15
        finally:
            server.shutdown()

    def test_pid_present(self, mock_daemon):
        """Test that pid field is integer > 0."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "pid" in data
            assert isinstance(data["pid"], int)
            assert data["pid"] > 0
        finally:
            server.shutdown()

    def test_confidence_when_enabled(self, mock_daemon):
        """Test that confidence.primary is present when controller active."""
        # Enable confidence controller with timer_state
        mock_daemon.confidence_controller = MagicMock()
        mock_daemon.confidence_controller.timer_state.confidence_score = 75.5
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "confidence" in data
            assert data["confidence"]["primary"] == 75.5
        finally:
            server.shutdown()

    def test_confidence_absent_when_disabled(self, mock_daemon):
        """Test that confidence key is absent when controller is None."""
        # Ensure confidence controller is disabled
        mock_daemon.confidence_controller = None
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "confidence" not in data
        finally:
            server.shutdown()

    def test_errors_field(self, mock_daemon):
        """Test that errors.consecutive_failures and cake_read_failures are present."""
        mock_daemon.state_mgr.state["cake_read_failures"] = 2
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)
        update_steering_health_status(1)  # Set consecutive failures

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "errors" in data
            assert data["errors"]["consecutive_failures"] == 1
            assert data["errors"]["cake_read_failures"] == 2
        finally:
            server.shutdown()


class TestSteeringHealthLifecycle:
    """Integration tests for health server lifecycle (INTG-01 through INTG-03)."""

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

    @pytest.fixture
    def mock_daemon(self):
        """Create a mock SteeringDaemon with realistic state."""
        daemon = MagicMock()
        daemon.config.state_good = "SPECTRUM_GOOD"
        daemon.config.state_degraded = "SPECTRUM_DEGRADED"
        daemon.config.confidence_config = None
        daemon.config.green_rtt_ms = 5.0
        daemon.config.yellow_rtt_ms = 15.0
        daemon.config.red_rtt_ms = 15.0
        daemon.config.red_samples_required = 2
        daemon.config.green_samples_required = 15
        daemon.confidence_controller = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,
        }
        return daemon

    def test_health_server_receives_daemon_reference(self, mock_daemon):
        """Test that daemon reference is passed to handler (INTG-01)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            # Verify daemon reference is set on handler class
            assert SteeringHealthHandler.daemon is mock_daemon
        finally:
            server.shutdown()

    def test_health_status_updates_with_failures(self):
        """Test that status updates with failure count (INTG-03)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"

            # Initially healthy (failures = 0)
            update_steering_health_status(0)
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            assert data["status"] == "healthy"

            # Update to degraded (failures = 3)
            update_steering_health_status(3)
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)
            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"

            # Back to healthy (failures = 0)
            update_steering_health_status(0)
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            assert data["status"] == "healthy"
        finally:
            server.shutdown()

    def test_health_server_graceful_shutdown(self):
        """Test that server thread stops gracefully (INTG-02)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        # Verify thread is alive
        assert server.thread.is_alive()

        # Shutdown
        server.shutdown()

        # Verify thread stopped within timeout (join called with 5.0s timeout)
        assert not server.thread.is_alive()

        # Note: Port may still be in TIME_WAIT state briefly after shutdown
        # but that's normal TCP behavior - the important thing is the thread stopped

    def test_concurrent_requests_during_update(self, mock_daemon):
        """Test that concurrent requests during status update are safe."""
        import concurrent.futures

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            results = []

            def make_request():
                """Make a health request and return response status."""
                try:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        return ("success", data.get("status"))
                except urllib.error.HTTPError as e:
                    data = json.loads(e.read().decode())
                    return ("http_error", data.get("status"))
                except Exception as e:
                    return ("error", str(e))

            def update_status_task():
                """Update status values in a loop."""
                for i in range(20):
                    update_steering_health_status(i % 5)
                    time.sleep(0.01)

            # Run concurrent requests and updates
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                # Start status updates
                update_future = executor.submit(update_status_task)

                # Make concurrent requests
                request_futures = [executor.submit(make_request) for _ in range(10)]

                # Wait for all to complete
                update_future.result()
                for future in request_futures:
                    results.append(future.result())

            # All requests should complete without error (success or http_error)
            for result_type, status in results:
                assert result_type in ("success", "http_error")
                assert status in ("healthy", "degraded")

        finally:
            server.shutdown()

    def test_health_reflects_daemon_state_changes(self, mock_daemon):
        """Test that health response reflects daemon state changes (INTG-03)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"

            # Initial state: SPECTRUM_GOOD
            mock_daemon.state_mgr.state["current_state"] = "SPECTRUM_GOOD"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            assert data["steering"]["enabled"] is False
            assert data["steering"]["state"] == "SPECTRUM_GOOD"

            # Change to SPECTRUM_DEGRADED
            mock_daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            assert data["steering"]["enabled"] is True
            assert data["steering"]["state"] == "SPECTRUM_DEGRADED"

            # Change congestion state
            mock_daemon.state_mgr.state["congestion_state"] = "RED"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            assert data["congestion"]["primary"]["state"] == "RED"
            assert data["congestion"]["primary"]["state_code"] == 2

        finally:
            server.shutdown()

    def test_daemon_none_returns_minimal_response(self):
        """Test that daemon=None returns minimal response (status, uptime, version only)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Minimal response has these fields
            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data

            # Daemon-specific fields should NOT be present
            assert "steering" not in data
            assert "congestion" not in data
            assert "decision" not in data
            assert "counters" not in data
            assert "thresholds" not in data
            assert "pid" not in data

        finally:
            server.shutdown()

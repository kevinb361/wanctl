"""Tests for the steering health check HTTP endpoint."""

import json
import socket
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from wanctl import __version__
from wanctl.perf_profiler import OperationProfiler
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
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,  # 60s ago
        }
        # Router connectivity state
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
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
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,
        }
        # Router connectivity state
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
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


class TestSteeringRouterConnectivityReporting:
    """Tests for router connectivity reporting in steering health endpoint."""

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
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,
        }
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        return daemon

    def test_steering_health_includes_router_connectivity(self, mock_daemon):
        """Test that steering health includes router_connectivity section."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "router_connectivity" in data
            conn = data["router_connectivity"]
            assert conn["is_reachable"] is True
            assert conn["consecutive_failures"] == 0
            assert conn["last_failure_type"] is None
        finally:
            server.shutdown()

    def test_steering_health_includes_router_reachable(self, mock_daemon):
        """Test that steering health includes top-level router_reachable field."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "router_reachable" in data
            assert data["router_reachable"] is True
        finally:
            server.shutdown()

    def test_steering_health_degrades_when_router_unreachable(self, mock_daemon):
        """Test that steering health degrades (503) when router is unreachable."""
        # Set router as unreachable
        mock_daemon.router_connectivity.is_reachable = False
        mock_daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": False,
            "consecutive_failures": 3,
            "last_failure_type": "timeout",
            "last_failure_time": 12345.0,
        }

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "degraded"
            assert data["router_reachable"] is False
            conn = data["router_connectivity"]
            assert conn["is_reachable"] is False
            assert conn["consecutive_failures"] == 3
            assert conn["last_failure_type"] == "timeout"
        finally:
            server.shutdown()

    def test_steering_health_healthy_when_router_reachable(self, mock_daemon):
        """Test that steering health is healthy (200) when router is reachable."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["status"] == "healthy"
            assert data["router_reachable"] is True
        finally:
            server.shutdown()

    def test_steering_health_router_reachable_defaults_true_without_daemon(self):
        """Test that router_reachable defaults to True when no daemon."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # No daemon, should still have router_reachable = True
            assert "router_reachable" in data
            assert data["router_reachable"] is True
            assert data["status"] == "healthy"
        finally:
            server.shutdown()


class TestSteeringCycleBudget:
    """Tests for cycle_budget in steering health endpoint."""

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

    def _make_mock_daemon(self, with_profiler_data=True, overrun_count=2):
        """Create a mock SteeringDaemon with profiler attributes."""
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
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,
        }
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }

        # Set profiler attributes (from Plan 01)
        daemon._profiler = OperationProfiler(max_samples=1200)
        daemon._overrun_count = overrun_count
        daemon._cycle_interval_ms = 50.0

        if with_profiler_data:
            for val in [29.0, 30.0, 31.0, 32.0, 33.0, 28.0, 27.0, 31.5, 30.5, 29.5]:
                daemon._profiler.record("steering_cycle_total", val)

        return daemon

    def test_cycle_budget_present_at_top_level(self):
        """Steering health includes cycle_budget at top level when profiler has data."""
        daemon = self._make_mock_daemon(with_profiler_data=True, overrun_count=2)
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "cycle_budget" in data
            cb = data["cycle_budget"]
            assert "cycle_time_ms" in cb
            assert "avg" in cb["cycle_time_ms"]
            assert "p95" in cb["cycle_time_ms"]
            assert "p99" in cb["cycle_time_ms"]
            assert "utilization_pct" in cb
            assert "overrun_count" in cb
            assert cb["overrun_count"] == 2
        finally:
            server.shutdown()

    def test_cycle_budget_omitted_when_profiler_empty(self):
        """Steering health omits cycle_budget when profiler has no data (cold start)."""
        daemon = self._make_mock_daemon(with_profiler_data=False)
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "cycle_budget" not in data
        finally:
            server.shutdown()

    def test_cycle_budget_structure_matches_autorate(self):
        """cycle_budget structure has same keys as autorate (cycle_time_ms, utilization_pct, overrun_count)."""
        daemon = self._make_mock_daemon(with_profiler_data=True)
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            cb = data["cycle_budget"]
            # Exact same top-level keys as autorate format
            assert set(cb.keys()) == {"cycle_time_ms", "utilization_pct", "overrun_count", "status", "warning_threshold_pct"}
            # cycle_time_ms has avg, p95, p99
            assert set(cb["cycle_time_ms"].keys()) == {"avg", "p95", "p99"}
        finally:
            server.shutdown()

    def test_existing_steering_fields_unchanged(self):
        """Adding cycle_budget does not remove or change existing steering health fields."""
        daemon = self._make_mock_daemon(with_profiler_data=True)
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # All existing fields still present
            assert "status" in data
            assert "uptime_seconds" in data
            assert "version" in data
            assert "steering" in data
            assert "congestion" in data
            assert "decision" in data
            assert "counters" in data
            assert "thresholds" in data
            assert "pid" in data
            assert "router_reachable" in data
            assert "router_connectivity" in data
            assert "errors" in data
        finally:
            server.shutdown()

    def test_cold_start_no_cycle_budget(self):
        """Cold start (daemon state empty) returns 'starting' without cycle_budget."""
        daemon = self._make_mock_daemon(with_profiler_data=False)
        # Empty state to trigger cold start path
        daemon.state_mgr.state = {}
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            # "starting" status returns 503
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=5)

            assert exc_info.value.code == 503
            data = json.loads(exc_info.value.read().decode())
            assert data["status"] == "starting"
            assert "cycle_budget" not in data
            exc_info.value.close()
        finally:
            server.shutdown()


class TestDiskSpaceInSteeringHealth:
    """Tests for disk_space field in steering health endpoint."""

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

    def test_steering_health_includes_disk_space(self):
        """Test that steering health response includes disk_space field."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

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

    def test_steering_health_degrades_on_disk_warning(self):
        """Test that steering health degrades when disk space is low."""
        mock_usage = MagicMock()
        mock_usage.free = 50_000_000  # 50MB, below threshold
        mock_usage.total = 10_000_000_000

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

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

    def test_steering_health_disk_space_unknown_on_error(self):
        """Test that disk_space status is 'unknown' when path inaccessible."""
        with patch(
            "wanctl.health_check.shutil.disk_usage",
            side_effect=OSError("path not found"),
        ):
            port = find_free_port()
            server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

            try:
                url = f"http://127.0.0.1:{port}/health"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                assert data["disk_space"]["status"] == "unknown"
                # unknown disk space should NOT degrade health
                assert data["status"] == "healthy"
            finally:
                server.shutdown()


class TestWanAwarenessHealth:
    """Tests for WAN awareness section in steering health endpoint (OBSV-01)."""

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
        """Create a mock SteeringDaemon with WAN awareness attributes."""
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
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # WAN awareness attributes (enabled by default)
        daemon._wan_state_enabled = True
        daemon._wan_zone = "RED"
        daemon._wan_red_weight = None  # use class constant
        daemon._wan_soft_red_weight = None  # use class constant
        daemon._get_effective_wan_zone.return_value = "RED"
        daemon._is_wan_grace_period_active.return_value = False
        daemon.baseline_loader._get_wan_zone_age.return_value = 2.3
        daemon.baseline_loader._is_wan_zone_stale.return_value = False
        return daemon

    def test_wan_awareness_enabled_with_all_fields(self, mock_daemon):
        """Test health response includes wan_awareness with all OBSV-01 fields when enabled."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "wan_awareness" in data
            wa = data["wan_awareness"]
            assert wa["enabled"] is True
            assert wa["zone"] == "RED"
            assert wa["effective_zone"] == "RED"
            assert wa["grace_period_active"] is False
            assert wa["staleness_age_sec"] == 2.3
            assert wa["stale"] is False
            assert "confidence_contribution" in wa
        finally:
            server.shutdown()

    def test_wan_awareness_disabled_shows_raw_zone(self, mock_daemon):
        """Test health response shows enabled=false with raw zone when disabled."""
        mock_daemon._wan_state_enabled = False
        mock_daemon._wan_zone = "YELLOW"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["enabled"] is False
            assert wa["zone"] == "YELLOW"
            # Should NOT have effective_zone, grace_period_active etc when disabled
            assert "effective_zone" not in wa
            assert "confidence_contribution" not in wa
        finally:
            server.shutdown()

    def test_wan_awareness_grace_period_active(self, mock_daemon):
        """Test grace_period_active=true during startup grace period, effective_zone=None."""
        mock_daemon._is_wan_grace_period_active.return_value = True
        mock_daemon._get_effective_wan_zone.return_value = None
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["grace_period_active"] is True
            assert wa["effective_zone"] is None
            assert wa["confidence_contribution"] == 0
        finally:
            server.shutdown()

    def test_wan_awareness_confidence_contribution_red(self, mock_daemon):
        """Test confidence_contribution reflects config-driven WAN weight for RED zone."""
        # Set config-driven weight (overrides class constant)
        mock_daemon._wan_red_weight = 30
        mock_daemon._get_effective_wan_zone.return_value = "RED"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["confidence_contribution"] == 30
        finally:
            server.shutdown()

    def test_wan_awareness_confidence_contribution_zero_for_green(self, mock_daemon):
        """Test confidence_contribution=0 when effective zone is GREEN."""
        mock_daemon._get_effective_wan_zone.return_value = "GREEN"
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["confidence_contribution"] == 0
        finally:
            server.shutdown()

    def test_wan_awareness_staleness_age_numeric(self, mock_daemon):
        """Test staleness_age_sec is numeric float when file accessible, stale flag matches."""
        mock_daemon.baseline_loader._get_wan_zone_age.return_value = 4.567
        mock_daemon.baseline_loader._is_wan_zone_stale.return_value = False
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["staleness_age_sec"] == 4.6  # rounded to 1 decimal
            assert wa["stale"] is False
        finally:
            server.shutdown()

    def test_wan_zone_age_returns_none_on_oserror(self):
        """Test get_wan_zone_age() returns None on OSError."""
        from wanctl.steering.daemon import BaselineLoader

        config = MagicMock()
        config.primary_state_file.stat.side_effect = OSError("no such file")
        loader = BaselineLoader(config, MagicMock())

        result = loader.get_wan_zone_age()
        assert result is None

    def test_wan_awareness_degrade_timer_active(self, mock_daemon):
        """Test degrade_timer_remaining is float when degrade_timer active."""
        mock_daemon.confidence_controller = MagicMock()
        mock_daemon.confidence_controller.timer_state.confidence_score = 50
        mock_daemon.confidence_controller.timer_state.degrade_timer = 3.75
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["degrade_timer_remaining"] == 3.75
        finally:
            server.shutdown()

    def test_wan_awareness_degrade_timer_inactive(self, mock_daemon):
        """Test degrade_timer_remaining is null when degrade_timer is None."""
        mock_daemon.confidence_controller = MagicMock()
        mock_daemon.confidence_controller.timer_state.confidence_score = 0
        mock_daemon.confidence_controller.timer_state.degrade_timer = None
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["degrade_timer_remaining"] is None
        finally:
            server.shutdown()

    def test_wan_awareness_no_confidence_controller(self, mock_daemon):
        """Test degrade_timer_remaining is null when confidence_controller is None."""
        mock_daemon.confidence_controller = None
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=mock_daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            wa = data["wan_awareness"]
            assert wa["degrade_timer_remaining"] is None
        finally:
            server.shutdown()


class TestPerTinHealth:
    """Tests for per-tin CAKE statistics in steering health endpoint (CAKE-07)."""

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
    def mock_daemon_with_tins(self):
        """Create a mock SteeringDaemon with linux-cake and per-tin data."""
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
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        daemon.state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "congestion_state": "GREEN",
            "red_count": 0,
            "good_count": 5,
            "cake_read_failures": 0,
            "last_transition_time": time.monotonic() - 60,
        }
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Linux-cake CakeStatsReader with per-tin data
        daemon.cake_reader._is_linux_cake = True
        daemon.cake_reader.last_tin_stats = [
            {
                "dropped_packets": 0,
                "ecn_marked_packets": 0,
                "avg_delay_us": 120,
                "peak_delay_us": 500,
                "backlog_bytes": 0,
                "sparse_flows": 3,
                "bulk_flows": 0,
                "unresponsive_flows": 0,
            },
            {
                "dropped_packets": 3,
                "ecn_marked_packets": 1,
                "avg_delay_us": 80,
                "peak_delay_us": 300,
                "backlog_bytes": 1500,
                "sparse_flows": 5,
                "bulk_flows": 2,
                "unresponsive_flows": 0,
            },
            {
                "dropped_packets": 0,
                "ecn_marked_packets": 0,
                "avg_delay_us": 50,
                "peak_delay_us": 100,
                "backlog_bytes": 0,
                "sparse_flows": 1,
                "bulk_flows": 0,
                "unresponsive_flows": 0,
            },
            {
                "dropped_packets": 0,
                "ecn_marked_packets": 0,
                "avg_delay_us": 30,
                "peak_delay_us": 60,
                "backlog_bytes": 0,
                "sparse_flows": 0,
                "bulk_flows": 0,
                "unresponsive_flows": 0,
            },
        ]
        return daemon

    def test_tins_present_when_linux_cake_active(self, mock_daemon_with_tins):
        """Health endpoint includes tins array under congestion.primary when linux-cake."""
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "tins" in data["congestion"]["primary"]
            tins = data["congestion"]["primary"]["tins"]
            assert len(tins) == 4
        finally:
            server.shutdown()

    def test_tins_have_correct_names(self, mock_daemon_with_tins):
        """Each tin has tin_name matching diffserv4 order: Bulk, BestEffort, Video, Voice."""
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            tins = data["congestion"]["primary"]["tins"]
            assert tins[0]["tin_name"] == "Bulk"
            assert tins[1]["tin_name"] == "BestEffort"
            assert tins[2]["tin_name"] == "Video"
            assert tins[3]["tin_name"] == "Voice"
        finally:
            server.shutdown()

    def test_tins_have_nine_fields(self, mock_daemon_with_tins):
        """Each tin dict has 9 fields per D-06."""
        expected_fields = {
            "tin_name",
            "dropped_packets",
            "ecn_marked_packets",
            "avg_delay_us",
            "peak_delay_us",
            "backlog_bytes",
            "sparse_flows",
            "bulk_flows",
            "unresponsive_flows",
        }
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            tins = data["congestion"]["primary"]["tins"]
            for tin in tins:
                assert set(tin.keys()) == expected_fields
        finally:
            server.shutdown()

    def test_tins_have_correct_values(self, mock_daemon_with_tins):
        """Tin data values match the mock data."""
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            tins = data["congestion"]["primary"]["tins"]
            # Check BestEffort tin (index 1) for specific values
            assert tins[1]["dropped_packets"] == 3
            assert tins[1]["ecn_marked_packets"] == 1
            assert tins[1]["avg_delay_us"] == 80
            assert tins[1]["backlog_bytes"] == 1500
        finally:
            server.shutdown()

    def test_tins_omitted_when_not_linux_cake(self, mock_daemon_with_tins):
        """Health endpoint omits tins when _is_linux_cake is False (D-07)."""
        mock_daemon_with_tins.cake_reader._is_linux_cake = False
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "tins" not in data["congestion"]["primary"]
        finally:
            server.shutdown()

    def test_tins_omitted_when_last_tin_stats_none(self, mock_daemon_with_tins):
        """Health endpoint omits tins when last_tin_stats is None (first cycle)."""
        mock_daemon_with_tins.cake_reader.last_tin_stats = None
        port = find_free_port()
        server = start_steering_health_server(
            host="127.0.0.1", port=port, daemon=mock_daemon_with_tins
        )

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "tins" not in data["congestion"]["primary"]
        finally:
            server.shutdown()

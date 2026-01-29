"""Tests for router connectivity tracking module."""

import logging
import socket
import subprocess
import time
from unittest.mock import MagicMock

import pytest

from wanctl.router_connectivity import RouterConnectivityState, classify_failure_type


class TestClassifyFailureType:
    """Tests for classify_failure_type() function."""

    def test_timeout_error(self) -> None:
        """TimeoutError should classify as 'timeout'."""
        exc = TimeoutError("Operation timed out")
        assert classify_failure_type(exc) == "timeout"

    def test_socket_timeout(self) -> None:
        """socket.timeout should classify as 'timeout'."""
        # socket.timeout is an alias for TimeoutError in Python 3.10+
        # We explicitly test this alias to ensure compatibility
        exc = TimeoutError("timed out")  # socket.timeout maps to this
        assert classify_failure_type(exc) == "timeout"

    def test_subprocess_timeout(self) -> None:
        """subprocess.TimeoutExpired should classify as 'timeout'."""
        exc = subprocess.TimeoutExpired(cmd="ping", timeout=5)
        assert classify_failure_type(exc) == "timeout"

    def test_connection_refused_error(self) -> None:
        """ConnectionRefusedError should classify as 'connection_refused'."""
        exc = ConnectionRefusedError("Connection refused")
        assert classify_failure_type(exc) == "connection_refused"

    def test_connection_refused_string(self) -> None:
        """OSError with 'connection refused' in message should classify as 'connection_refused'."""
        exc = OSError("Connection refused by peer")
        assert classify_failure_type(exc) == "connection_refused"

    def test_network_unreachable(self) -> None:
        """OSError with 'network is unreachable' should classify as 'network_unreachable'."""
        exc = OSError("Network is unreachable")
        assert classify_failure_type(exc) == "network_unreachable"

    def test_no_route_to_host(self) -> None:
        """OSError with 'no route to host' should classify as 'network_unreachable'."""
        exc = OSError("No route to host")
        assert classify_failure_type(exc) == "network_unreachable"

    def test_socket_gaierror(self) -> None:
        """socket.gaierror should classify as 'dns_failure'."""
        exc = socket.gaierror(8, "nodename nor servname provided, or not known")
        assert classify_failure_type(exc) == "dns_failure"

    def test_dns_string(self) -> None:
        """OSError with 'name or service not known' should classify as 'dns_failure'."""
        exc = OSError("Name or service not known")
        assert classify_failure_type(exc) == "dns_failure"

    def test_auth_failure_string(self) -> None:
        """Exception with 'authentication failed' should classify as 'auth_failure'."""
        exc = Exception("Authentication failed for user admin")
        assert classify_failure_type(exc) == "auth_failure"

    def test_requests_connect_timeout(self) -> None:
        """requests.exceptions.ConnectTimeout should classify as 'timeout'."""
        try:
            import requests.exceptions

            exc = requests.exceptions.ConnectTimeout("Connection timed out")
            assert classify_failure_type(exc) == "timeout"
        except ImportError:
            pytest.skip("requests not available")

    def test_requests_read_timeout(self) -> None:
        """requests.exceptions.ReadTimeout should classify as 'timeout'."""
        try:
            import requests.exceptions

            exc = requests.exceptions.ReadTimeout("Read timed out")
            assert classify_failure_type(exc) == "timeout"
        except ImportError:
            pytest.skip("requests not available")

    def test_requests_connection_error_refused(self) -> None:
        """requests.exceptions.ConnectionError with 'refused' should classify as 'connection_refused'."""
        try:
            import requests.exceptions

            exc = requests.exceptions.ConnectionError("Connection refused")
            assert classify_failure_type(exc) == "connection_refused"
        except ImportError:
            pytest.skip("requests not available")

    def test_requests_connection_error_other(self) -> None:
        """requests.exceptions.ConnectionError without 'refused' should classify as 'network_unreachable'."""
        try:
            import requests.exceptions

            exc = requests.exceptions.ConnectionError("Failed to establish connection")
            assert classify_failure_type(exc) == "network_unreachable"
        except ImportError:
            pytest.skip("requests not available")

    def test_unknown_exception(self) -> None:
        """Unrecognized exceptions should classify as 'unknown'."""
        exc = ValueError("some random error")
        assert classify_failure_type(exc) == "unknown"

    def test_paramiko_auth_exception(self) -> None:
        """paramiko.AuthenticationException should classify as 'auth_failure'."""
        try:
            from paramiko import AuthenticationException

            exc = AuthenticationException("Authentication failed")
            assert classify_failure_type(exc) == "auth_failure"
        except ImportError:
            pytest.skip("paramiko not available")

    def test_case_insensitive_matching(self) -> None:
        """Error message matching should be case-insensitive."""
        exc = OSError("NETWORK IS UNREACHABLE")
        assert classify_failure_type(exc) == "network_unreachable"


class TestRouterConnectivityState:
    """Tests for RouterConnectivityState class."""

    @pytest.fixture
    def logger(self) -> logging.Logger:
        """Create a test logger."""
        return logging.getLogger("test_connectivity")

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create a mock logger for verifying log calls."""
        return MagicMock(spec=logging.Logger)

    def test_initial_state_is_reachable(self, logger: logging.Logger) -> None:
        """Initial state should show router as reachable."""
        state = RouterConnectivityState(logger)
        assert state.is_reachable is True
        assert state.consecutive_failures == 0
        assert state.last_failure_type is None
        assert state.last_failure_time is None

    def test_record_success_no_prior_failures(self, logger: logging.Logger) -> None:
        """record_success() with no prior failures should not log reconnection."""
        state = RouterConnectivityState(logger)
        state.record_success()
        assert state.is_reachable is True
        assert state.consecutive_failures == 0

    def test_record_failure_increments_counter(self, logger: logging.Logger) -> None:
        """record_failure() should increment consecutive_failures."""
        state = RouterConnectivityState(logger)
        exc = TimeoutError("timeout")
        state.record_failure(exc)
        assert state.consecutive_failures == 1
        state.record_failure(exc)
        assert state.consecutive_failures == 2

    def test_record_failure_sets_type(self, logger: logging.Logger) -> None:
        """record_failure() should set last_failure_type via classify_failure_type."""
        state = RouterConnectivityState(logger)
        exc = ConnectionRefusedError("refused")
        failure_type = state.record_failure(exc)
        assert state.last_failure_type == "connection_refused"
        assert failure_type == "connection_refused"

    def test_record_failure_sets_unreachable(self, logger: logging.Logger) -> None:
        """record_failure() should set is_reachable to False."""
        state = RouterConnectivityState(logger)
        assert state.is_reachable is True
        state.record_failure(TimeoutError("timeout"))
        assert state.is_reachable is False

    def test_record_failure_sets_time(self, logger: logging.Logger) -> None:
        """record_failure() should set last_failure_time."""
        state = RouterConnectivityState(logger)
        before = time.monotonic()
        state.record_failure(TimeoutError("timeout"))
        after = time.monotonic()
        assert state.last_failure_time is not None
        assert before <= state.last_failure_time <= after

    def test_record_success_after_failures_logs_reconnect(
        self, mock_logger: MagicMock
    ) -> None:
        """record_success() after failures should log reconnection."""
        state = RouterConnectivityState(mock_logger)
        state.record_failure(TimeoutError("timeout"))
        state.record_failure(TimeoutError("timeout"))
        assert state.consecutive_failures == 2
        assert state.is_reachable is False

        state.record_success()

        # Should have logged reconnection
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "reconnect" in call_args.lower() or "recover" in call_args.lower()

    def test_record_success_resets_counters(self, logger: logging.Logger) -> None:
        """record_success() should reset all failure tracking."""
        state = RouterConnectivityState(logger)
        state.record_failure(TimeoutError("timeout"))
        state.record_failure(TimeoutError("timeout"))
        assert state.consecutive_failures == 2
        assert state.last_failure_type is not None
        assert state.is_reachable is False

        state.record_success()

        assert state.consecutive_failures == 0
        assert state.last_failure_type is None
        assert state.last_failure_time is None
        assert state.is_reachable is True

    def test_consecutive_failures_accumulate(self, logger: logging.Logger) -> None:
        """Multiple failures should accumulate correctly."""
        state = RouterConnectivityState(logger)
        for i in range(5):
            state.record_failure(TimeoutError(f"timeout {i}"))
            assert state.consecutive_failures == i + 1

    def test_to_dict_returns_state(self, logger: logging.Logger) -> None:
        """to_dict() should return state as dictionary for health endpoint."""
        state = RouterConnectivityState(logger)
        state.record_failure(ConnectionRefusedError("refused"))

        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["is_reachable"] is False
        assert result["consecutive_failures"] == 1
        assert result["last_failure_type"] == "connection_refused"
        assert "last_failure_time" in result

    def test_to_dict_initial_state(self, logger: logging.Logger) -> None:
        """to_dict() on initial state should return clean state."""
        state = RouterConnectivityState(logger)
        result = state.to_dict()

        assert result["is_reachable"] is True
        assert result["consecutive_failures"] == 0
        assert result["last_failure_type"] is None
        assert result["last_failure_time"] is None

    def test_record_failure_returns_failure_type(self, logger: logging.Logger) -> None:
        """record_failure() should return the classified failure type."""
        state = RouterConnectivityState(logger)
        result = state.record_failure(socket.gaierror(8, "dns failed"))
        assert result == "dns_failure"

    def test_different_failure_types_update_last_type(
        self, logger: logging.Logger
    ) -> None:
        """Consecutive different failure types should update last_failure_type."""
        state = RouterConnectivityState(logger)

        state.record_failure(TimeoutError("timeout"))
        assert state.last_failure_type == "timeout"

        state.record_failure(ConnectionRefusedError("refused"))
        assert state.last_failure_type == "connection_refused"
        assert state.consecutive_failures == 2


class TestOutageDurationTracking:
    """Tests for outage duration tracking in RouterConnectivityState."""

    @pytest.fixture
    def logger(self) -> logging.Logger:
        """Create a test logger."""
        return logging.getLogger("test_outage")

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create a mock logger for verifying log calls."""
        return MagicMock(spec=logging.Logger)

    def test_outage_start_time_set_on_first_failure(
        self, logger: logging.Logger
    ) -> None:
        """outage_start_time should be set on the first failure."""
        state = RouterConnectivityState(logger)
        assert state.outage_start_time is None

        before = time.monotonic()
        state.record_failure(TimeoutError("timeout"))
        after = time.monotonic()

        assert state.outage_start_time is not None
        assert before <= state.outage_start_time <= after

    def test_outage_start_time_not_reset_on_subsequent_failure(
        self, logger: logging.Logger
    ) -> None:
        """outage_start_time should NOT be updated on subsequent failures."""
        state = RouterConnectivityState(logger)

        state.record_failure(TimeoutError("timeout"))
        first_start = state.outage_start_time

        # Small delay to ensure monotonic clock advances
        time.sleep(0.01)
        state.record_failure(TimeoutError("timeout 2"))

        assert state.outage_start_time == first_start

    def test_get_outage_duration_none_when_reachable(
        self, logger: logging.Logger
    ) -> None:
        """get_outage_duration() should return None when router is reachable."""
        state = RouterConnectivityState(logger)
        assert state.get_outage_duration() is None

    def test_get_outage_duration_returns_elapsed_time(
        self, logger: logging.Logger
    ) -> None:
        """get_outage_duration() should return elapsed seconds during outage."""
        state = RouterConnectivityState(logger)
        state.record_failure(TimeoutError("timeout"))

        # Small delay so duration > 0
        time.sleep(0.02)
        duration = state.get_outage_duration()

        assert duration is not None
        assert duration >= 0.02

    def test_record_success_logs_outage_duration(
        self, mock_logger: MagicMock
    ) -> None:
        """record_success() after failures should log outage duration."""
        state = RouterConnectivityState(mock_logger)
        state.record_failure(TimeoutError("timeout"))
        state.record_failure(TimeoutError("timeout"))

        # Small delay so duration is measurable
        time.sleep(0.01)
        state.record_success()

        # Should have logged reconnection with duration
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "outage" in call_args.lower()
        assert "2 failures" in call_args

    def test_record_success_resets_outage_start_time(
        self, logger: logging.Logger
    ) -> None:
        """record_success() should reset outage_start_time to None."""
        state = RouterConnectivityState(logger)
        state.record_failure(TimeoutError("timeout"))
        assert state.outage_start_time is not None

        state.record_success()
        assert state.outage_start_time is None

    def test_outage_duration_in_to_dict(
        self, logger: logging.Logger
    ) -> None:
        """to_dict() should include outage_duration_seconds."""
        state = RouterConnectivityState(logger)

        # When reachable, duration should be None
        result = state.to_dict()
        assert "outage_duration_seconds" in result
        assert result["outage_duration_seconds"] is None

        # When in outage, duration should be a float
        state.record_failure(TimeoutError("timeout"))
        time.sleep(0.01)
        result = state.to_dict()
        assert result["outage_duration_seconds"] is not None
        assert result["outage_duration_seconds"] >= 0.01

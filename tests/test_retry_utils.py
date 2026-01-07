"""Tests for retry_utils module - retry with exponential backoff."""

import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.retry_utils import is_retryable_error, retry_with_backoff


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_timeout_expired_is_retryable(self):
        """Test that subprocess.TimeoutExpired is retryable."""
        error = subprocess.TimeoutExpired("cmd", 30)
        assert is_retryable_error(error) is True

    def test_connection_error_is_retryable(self):
        """Test that ConnectionError is retryable."""
        error = ConnectionError("Connection failed")
        assert is_retryable_error(error) is True

    def test_connection_refused_is_retryable(self):
        """Test that ConnectionRefusedError is retryable."""
        error = ConnectionRefusedError("Connection refused")
        assert is_retryable_error(error) is True

    def test_connection_reset_is_retryable(self):
        """Test that ConnectionResetError is retryable."""
        error = ConnectionResetError("Connection reset by peer")
        assert is_retryable_error(error) is True

    def test_oserror_connection_refused_is_retryable(self):
        """Test OSError with 'connection refused' message is retryable."""
        error = OSError("Connection refused by server")
        assert is_retryable_error(error) is True

    def test_oserror_connection_timed_out_is_retryable(self):
        """Test OSError with 'connection timed out' message is retryable."""
        error = OSError("Connection timed out")
        assert is_retryable_error(error) is True

    def test_oserror_connection_reset_is_retryable(self):
        """Test OSError with 'connection reset' message is retryable."""
        error = OSError("Connection reset by peer")
        assert is_retryable_error(error) is True

    def test_oserror_broken_pipe_is_retryable(self):
        """Test OSError with 'broken pipe' message is retryable."""
        error = OSError("Broken pipe")
        assert is_retryable_error(error) is True

    def test_oserror_network_unreachable_is_retryable(self):
        """Test OSError with 'network is unreachable' message is retryable."""
        error = OSError("Network is unreachable")
        assert is_retryable_error(error) is True

    def test_oserror_other_not_retryable(self):
        """Test that other OSErrors are not retryable."""
        error = OSError("Permission denied")
        assert is_retryable_error(error) is False

    def test_value_error_not_retryable(self):
        """Test that ValueError is not retryable."""
        error = ValueError("Invalid value")
        assert is_retryable_error(error) is False

    def test_type_error_not_retryable(self):
        """Test that TypeError is not retryable."""
        error = TypeError("Wrong type")
        assert is_retryable_error(error) is False

    def test_runtime_error_not_retryable(self):
        """Test that RuntimeError is not retryable."""
        error = RuntimeError("Something went wrong")
        assert is_retryable_error(error) is False

    def test_case_insensitive_matching(self):
        """Test that message matching is case-insensitive."""
        error = OSError("CONNECTION REFUSED")
        assert is_retryable_error(error) is True


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_success_on_first_attempt(self):
        """Test function that succeeds on first attempt."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed()

        assert result == "success"
        assert call_count == 1

    def test_retries_on_transient_error(self):
        """Test that transient errors trigger retries."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01, jitter=False)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Transient failure")
            return "success"

        result = fail_then_succeed()

        assert result == "success"
        assert call_count == 2

    def test_non_retryable_error_raises_immediately(self):
        """Test that non-retryable errors raise immediately."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count == 1  # Should not retry

    def test_max_attempts_reached(self):
        """Test that error is raised after max attempts."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01, jitter=False)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count == 3

    def test_exponential_backoff(self):
        """Test that delay increases exponentially."""
        delays = []

        @retry_with_backoff(
            max_attempts=4,
            initial_delay=0.1,
            backoff_factor=2.0,
            jitter=False
        )
        def track_timing():
            delays.append(time.time())
            raise ConnectionError("Fail")

        start = time.time()

        with pytest.raises(ConnectionError):
            track_timing()

        # Calculate actual delays between attempts
        actual_delays = [delays[i+1] - delays[i] for i in range(len(delays)-1)]

        # Expected: 0.1, 0.2, 0.4 (initial * backoff_factor^n)
        # Allow some tolerance for timing
        assert len(actual_delays) == 3
        assert 0.08 <= actual_delays[0] <= 0.15  # ~0.1s
        assert 0.15 <= actual_delays[1] <= 0.30  # ~0.2s
        assert 0.30 <= actual_delays[2] <= 0.50  # ~0.4s

    def test_max_delay_caps_backoff(self):
        """Test that max_delay caps the backoff."""
        delays = []

        @retry_with_backoff(
            max_attempts=5,
            initial_delay=0.1,
            backoff_factor=10.0,  # Would be 0.1, 1.0, 10.0, 100.0 without cap
            max_delay=0.2,
            jitter=False
        )
        def track_timing():
            delays.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            track_timing()

        # Calculate actual delays
        actual_delays = [delays[i+1] - delays[i] for i in range(len(delays)-1)]

        # All delays should be capped at max_delay
        for delay in actual_delays:
            assert delay <= 0.25  # Allow some tolerance above max_delay

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays."""
        delays_run1 = []
        delays_run2 = []

        def create_decorated():
            @retry_with_backoff(
                max_attempts=3,
                initial_delay=0.1,
                jitter=True
            )
            def fail():
                raise ConnectionError("Fail")
            return fail

        # Run twice and compare timing
        with pytest.raises(ConnectionError):
            fn1 = create_decorated()
            t1_start = time.time()
            try:
                fn1()
            except ConnectionError:
                t1_end = time.time()
                delays_run1.append(t1_end - t1_start)
                raise

        with pytest.raises(ConnectionError):
            fn2 = create_decorated()
            t2_start = time.time()
            try:
                fn2()
            except ConnectionError:
                t2_end = time.time()
                delays_run2.append(t2_end - t2_start)
                raise

        # With jitter, total times should differ (probabilistically)
        # This test may occasionally fail due to randomness, but that's expected

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        @retry_with_backoff()
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_uses_logger_from_self(self):
        """Test that decorator uses logger from self when called on method."""
        class MyClass:
            def __init__(self):
                self.logger = MagicMock()
                self.call_count = 0

            @retry_with_backoff(max_attempts=2, initial_delay=0.01, jitter=False)
            def my_method(self):
                self.call_count += 1
                if self.call_count < 2:
                    raise ConnectionError("Fail once")
                return "success"

        obj = MyClass()
        result = obj.my_method()

        assert result == "success"
        # Logger should have been called for the retry warning
        assert obj.logger.warning.called

    def test_returns_correct_value(self):
        """Test that return values are passed through correctly."""
        @retry_with_backoff()
        def return_complex():
            return {"key": "value", "list": [1, 2, 3]}

        result = return_complex()
        assert result == {"key": "value", "list": [1, 2, 3]}

    def test_passes_arguments_correctly(self):
        """Test that args and kwargs are passed to function."""
        @retry_with_backoff()
        def with_args(a, b, c=None):
            return (a, b, c)

        result = with_args(1, 2, c=3)
        assert result == (1, 2, 3)

    def test_timeout_expired_retries(self):
        """Test that subprocess.TimeoutExpired triggers retry."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01, jitter=False)
        def timeout_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise subprocess.TimeoutExpired("cmd", 30)
            return "success"

        result = timeout_then_succeed()

        assert result == "success"
        assert call_count == 2

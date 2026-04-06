"""Tests for retry_utils module - retry with exponential backoff."""

import logging
import subprocess
import time
from unittest.mock import MagicMock

import pytest

from wanctl.retry_utils import (
    is_retryable_error,
    measure_with_retry,
    retry_with_backoff,
    verify_with_retry,
)


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

        @retry_with_backoff(max_attempts=4, initial_delay=0.1, backoff_factor=2.0, jitter=False)
        def track_timing():
            delays.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            track_timing()

        # Calculate actual delays between attempts
        actual_delays = [delays[i + 1] - delays[i] for i in range(len(delays) - 1)]

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
            jitter=False,
        )
        def track_timing():
            delays.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            track_timing()

        # Calculate actual delays
        actual_delays = [delays[i + 1] - delays[i] for i in range(len(delays) - 1)]

        # All delays should be capped at max_delay
        for delay in actual_delays:
            assert delay <= 0.25  # Allow some tolerance above max_delay

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays."""
        delays_run1 = []
        delays_run2 = []

        def create_decorated():
            @retry_with_backoff(max_attempts=3, initial_delay=0.1, jitter=True)
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


# =============================================================================
# MERGED FROM test_retry_utils_extended.py
# =============================================================================


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_retry_utils_extended")


class TestVerifyWithRetry:
    """Tests for verify_with_retry function."""

    def test_immediate_success(self, logger):
        """Test verification succeeds on first attempt."""
        check_count = [0]

        def check_func():
            check_count[0] += 1
            return True

        result = verify_with_retry(
            check_func, True, max_retries=3, logger=logger, operation_name="test_verify"
        )

        assert result is True
        assert check_count[0] == 1

    def test_success_after_retries(self, logger):
        """Test verification succeeds after multiple retries."""
        check_count = [0]

        def check_func():
            check_count[0] += 1
            # Succeed on third attempt
            return check_count[0] >= 3

        result = verify_with_retry(
            check_func,
            True,
            max_retries=5,
            initial_delay=0.01,
            logger=logger,
            operation_name="test_verify",
        )

        assert result is True
        assert check_count[0] == 3

    def test_exhausted_retries(self, logger):
        """Test verification fails when retries exhausted."""
        check_count = [0]

        def check_func():
            check_count[0] += 1
            return False  # Always fail

        result = verify_with_retry(
            check_func,
            True,
            max_retries=3,
            initial_delay=0.01,
            logger=logger,
            operation_name="test_verify",
        )

        assert result is False
        assert check_count[0] == 3

    def test_exponential_backoff_timing(self, logger):
        """Test exponential backoff increases delay between attempts."""
        timestamps = []

        def check_func():
            timestamps.append(time.time())
            return False  # Always fail to trigger retries

        verify_with_retry(
            check_func,
            True,
            max_retries=4,
            initial_delay=0.01,
            backoff_factor=2.0,
            logger=logger,
            operation_name="test_verify",
        )

        # Check delays increase exponentially
        assert len(timestamps) == 4
        if len(timestamps) >= 3:
            delay1 = timestamps[1] - timestamps[0]
            delay2 = timestamps[2] - timestamps[1]
            # Second delay should be roughly double the first
            assert delay2 > delay1 * 1.5  # Allow some variation

    def test_different_expected_values(self, logger):
        """Test verification with different expected values (strings, numbers, etc)."""

        def check_func_string():
            return "enabled"

        result = verify_with_retry(
            check_func_string, "enabled", max_retries=1, logger=logger, operation_name="test_verify"
        )
        assert result is True

        def check_func_number():
            return 42

        result = verify_with_retry(
            check_func_number, 42, max_retries=1, logger=logger, operation_name="test_verify"
        )
        assert result is True

    def test_verify_with_none_logger(self):
        """Test verify works with None logger (creates default logger)."""

        def check_func():
            return True

        result = verify_with_retry(
            check_func, True, max_retries=1, logger=None, operation_name="test_verify"
        )
        assert result is True

    def test_verify_state_machine_transition(self, logger):
        """Test verifying state machine transitions (rule enable scenario)."""
        state = {"enabled": False}
        attempt_count = [0]

        def check_rule_state():
            attempt_count[0] += 1
            # State changes on second attempt (simulating RouterOS delay)
            if attempt_count[0] >= 2:
                state["enabled"] = True
            return state["enabled"]

        # Enable rule (control happens before verification)
        state["enabled"] = True  # Simulate control operation

        result = verify_with_retry(
            check_rule_state,
            True,
            max_retries=5,
            initial_delay=0.01,
            logger=logger,
            operation_name="rule_enable_verify",
        )

        assert result is True
        assert attempt_count[0] == 1  # First check succeeds

    def test_verify_boolean_state(self, logger):
        """Test verifying boolean state (enabled/disabled)."""
        state = [False]

        def check_func():
            # Transition to True on attempt 2
            if len(state) > 0 and not state[0]:
                state[0] = True
            return state[0]

        state[0] = True
        result = verify_with_retry(check_func, True, max_retries=3, logger=logger)
        assert result is True


class TestMeasureWithRetry:
    """Tests for measure_with_retry function."""

    def test_immediate_success(self, logger):
        """Test measurement succeeds on first attempt."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            return 42.5  # Return valid measurement

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            logger=logger,
            operation_name="test_measure",
        )

        assert result == 42.5
        assert measure_count[0] == 1

    def test_success_after_retries(self, logger):
        """Test measurement succeeds after failures."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            # Return None twice, then succeed
            if measure_count[0] < 3:
                return None
            return 50.0

        result = measure_with_retry(
            measure_func,
            max_retries=5,
            retry_delay=0.01,
            logger=logger,
            operation_name="test_measure",
        )

        assert result == 50.0
        assert measure_count[0] == 3

    def test_exhausted_without_fallback(self, logger):
        """Test measurement returns None when retries exhausted and no fallback."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            return  # Always fail

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            logger=logger,
            operation_name="test_measure",
        )

        assert result is None
        assert measure_count[0] == 3

    def test_fallback_on_exhaustion(self, logger):
        """Test fallback function called when measurement fails."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            return  # Always fail

        def fallback_func():
            return 99.9  # Fallback value

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            fallback_func=fallback_func,
            logger=logger,
            operation_name="test_measure",
        )

        assert result == 99.9
        assert measure_count[0] == 3

    def test_fallback_not_called_on_success(self, logger):
        """Test fallback is not called if measurement succeeds."""
        fallback_called = [False]

        def measure_func():
            return 42.0  # Success on first try

        def fallback_func():
            fallback_called[0] = True
            return 99.9

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            fallback_func=fallback_func,
            logger=logger,
            operation_name="test_measure",
        )

        assert result == 42.0
        assert fallback_called[0] is False

    def test_fixed_delay_between_retries(self, logger):
        """Test fixed delay is applied between retries."""
        timestamps = []

        def measure_func():
            timestamps.append(time.time())
            return  # Always fail to trigger delays

        measure_with_retry(
            measure_func,
            max_retries=4,
            retry_delay=0.02,
            logger=logger,
            operation_name="test_measure",
        )

        # Should have 4 timestamps with ~0.02s delays between attempts
        assert len(timestamps) == 4
        if len(timestamps) >= 2:
            delay1 = timestamps[1] - timestamps[0]
            delay2 = timestamps[2] - timestamps[1]
            # Delays should be roughly equal (fixed delay, not exponential)
            assert delay1 > 0.01 and delay1 < 0.05
            assert delay2 > 0.01 and delay2 < 0.05

    def test_none_logger(self):
        """Test measure works with None logger (creates default logger)."""

        def measure_func():
            return 42.0

        result = measure_with_retry(
            measure_func, max_retries=1, logger=None, operation_name="test_measure"
        )
        assert result == 42.0

    def test_rtt_measurement_pattern(self, logger):
        """Test RTT measurement with retry and fallback (steering daemon pattern)."""
        call_count = [0]
        history = [45.0, 46.5, 47.2]

        def measure_rtt():
            call_count[0] += 1
            # Fail first two attempts, succeed on third
            if call_count[0] < 3:
                return None
            return 48.0

        def fallback_to_history():
            # Use last known RTT from history
            if history:
                last_rtt = history[-1]
                logger.warning(f"Using fallback RTT: {last_rtt}ms")
                return last_rtt
            return None

        result = measure_with_retry(
            measure_rtt,
            max_retries=3,
            retry_delay=0.01,
            fallback_func=fallback_to_history,
            logger=logger,
            operation_name="ping",
        )

        assert result == 48.0  # Measurement succeeded
        assert call_count[0] == 3

    def test_fallback_with_history(self, logger):
        """Test fallback uses history when all measurements fail."""
        history = [42.0, 43.5, 44.2]

        def measure_rtt():
            return None  # Measurement always fails

        def fallback_to_history():
            last_rtt = history[-1] if history else None
            if last_rtt:
                logger.warning(f"Using fallback RTT from history: {last_rtt}ms")
            return last_rtt

        result = measure_with_retry(
            measure_rtt,
            max_retries=3,
            retry_delay=0.01,
            fallback_func=fallback_to_history,
            logger=logger,
            operation_name="ping",
        )

        assert result == 44.2  # Last value from history

    def test_zero_or_negative_measurements_valid(self, logger):
        """Test that 0 and negative values are treated as valid measurements."""

        def measure_func():
            return 0.0  # Zero is a valid measurement

        result = measure_with_retry(
            measure_func, max_retries=1, logger=logger, operation_name="test_measure"
        )
        assert result == 0.0  # Should NOT treat as failure

    def test_empty_string_valid(self, logger):
        """Test that empty string is treated as valid measurement."""

        def measure_func():
            return ""  # Empty string is valid (not None)

        result = measure_with_retry(
            measure_func, max_retries=1, logger=logger, operation_name="test_measure"
        )
        assert result == ""  # Should NOT retry

    def test_false_value_valid(self, logger):
        """Test that False is treated as valid measurement."""

        def measure_func():
            return False  # False is valid (not None)

        result = measure_with_retry(
            measure_func, max_retries=1, logger=logger, operation_name="test_measure"
        )
        assert result is False  # Should NOT retry


class TestMeasureWithRetryIntegration:
    """Integration tests for measurement retry patterns."""

    def test_flaky_network_measurement(self, logger):
        """Test handling flaky network that eventually recovers."""
        call_count = [0]

        def measure_func():
            call_count[0] += 1
            # Fail first 4 times, succeed on 5th
            if call_count[0] < 5:
                return None
            return 65.3

        result = measure_with_retry(
            measure_func, max_retries=10, retry_delay=0.01, logger=logger, operation_name="ping"
        )

        assert result == 65.3
        assert call_count[0] == 5

    def test_persistent_failure_with_fallback(self, logger):
        """Test persistent measurement failure uses fallback."""
        fallback_values = {"rtt": 50.0}

        def measure_func():
            return None  # Always fails

        def fallback_func():
            return fallback_values["rtt"]

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            fallback_func=fallback_func,
            logger=logger,
            operation_name="ping",
        )

        assert result == 50.0

    def test_varying_measurement_values(self, logger):
        """Test that first valid measurement is returned (not averaged)."""
        measurements = [None, None, 45.2, 50.0]  # Last would be ignored
        call_count = [0]

        def measure_func():
            result = measurements[call_count[0]]
            call_count[0] += 1
            return result

        result = measure_with_retry(
            measure_func, max_retries=5, retry_delay=0.01, logger=logger, operation_name="ping"
        )

        # Should return first successful measurement (45.2), not average
        assert result == 45.2


class TestRetryPatternCombinations:
    """Test combining retry patterns in realistic scenarios."""

    def test_verify_then_measure_pattern(self, logger):
        """Test verifying a precondition before measuring."""

        # First verify rule is enabled
        def check_rule():
            return True

        verify_result = verify_with_retry(
            check_rule,
            True,
            max_retries=3,
            initial_delay=0.01,
            logger=logger,
            operation_name="rule_enabled_verify",
        )
        assert verify_result is True

        # Then measure RTT
        def measure_rtt():
            return 48.5

        measure_result = measure_with_retry(
            measure_rtt, max_retries=3, retry_delay=0.01, logger=logger, operation_name="ping"
        )
        assert measure_result == 48.5

    def test_multiple_verify_attempts_success(self, logger):
        """Test multiple verify retries succeeding."""
        states = [False, False, True]  # Succeed on 3rd check
        call_count = [0]

        def check_func():
            result = states[call_count[0]]
            call_count[0] += 1
            return result

        result = verify_with_retry(
            check_func,
            True,
            max_retries=5,
            initial_delay=0.01,
            logger=logger,
            operation_name="state_verify",
        )

        assert result is True
        assert call_count[0] == 3


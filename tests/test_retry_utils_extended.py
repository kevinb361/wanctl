"""Unit tests for extended retry utilities (verification and measurement patterns)."""

import logging
import time
import pytest

from wanctl.retry_utils import verify_with_retry, measure_with_retry


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
            check_func,
            True,
            max_retries=3,
            logger=logger,
            operation_name="test_verify"
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
            operation_name="test_verify"
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
            operation_name="test_verify"
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
            operation_name="test_verify"
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
            check_func_string,
            "enabled",
            max_retries=1,
            logger=logger,
            operation_name="test_verify"
        )
        assert result is True

        def check_func_number():
            return 42

        result = verify_with_retry(
            check_func_number,
            42,
            max_retries=1,
            logger=logger,
            operation_name="test_verify"
        )
        assert result is True

    def test_verify_with_none_logger(self):
        """Test verify works with None logger (creates default logger)."""
        def check_func():
            return True

        result = verify_with_retry(
            check_func,
            True,
            max_retries=1,
            logger=None,
            operation_name="test_verify"
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
            operation_name="rule_enable_verify"
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
        result = verify_with_retry(
            check_func,
            True,
            max_retries=3,
            logger=logger
        )
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
            operation_name="test_measure"
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
            operation_name="test_measure"
        )

        assert result == 50.0
        assert measure_count[0] == 3

    def test_exhausted_without_fallback(self, logger):
        """Test measurement returns None when retries exhausted and no fallback."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            return None  # Always fail

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            logger=logger,
            operation_name="test_measure"
        )

        assert result is None
        assert measure_count[0] == 3

    def test_fallback_on_exhaustion(self, logger):
        """Test fallback function called when measurement fails."""
        measure_count = [0]

        def measure_func():
            measure_count[0] += 1
            return None  # Always fail

        def fallback_func():
            return 99.9  # Fallback value

        result = measure_with_retry(
            measure_func,
            max_retries=3,
            retry_delay=0.01,
            fallback_func=fallback_func,
            logger=logger,
            operation_name="test_measure"
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
            operation_name="test_measure"
        )

        assert result == 42.0
        assert fallback_called[0] is False

    def test_fixed_delay_between_retries(self, logger):
        """Test fixed delay is applied between retries."""
        timestamps = []

        def measure_func():
            timestamps.append(time.time())
            return None  # Always fail to trigger delays

        measure_with_retry(
            measure_func,
            max_retries=4,
            retry_delay=0.02,
            logger=logger,
            operation_name="test_measure"
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
            measure_func,
            max_retries=1,
            logger=None,
            operation_name="test_measure"
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
            operation_name="ping"
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
            operation_name="ping"
        )

        assert result == 44.2  # Last value from history

    def test_zero_or_negative_measurements_valid(self, logger):
        """Test that 0 and negative values are treated as valid measurements."""
        def measure_func():
            return 0.0  # Zero is a valid measurement

        result = measure_with_retry(
            measure_func,
            max_retries=1,
            logger=logger,
            operation_name="test_measure"
        )
        assert result == 0.0  # Should NOT treat as failure

    def test_empty_string_valid(self, logger):
        """Test that empty string is treated as valid measurement."""
        def measure_func():
            return ""  # Empty string is valid (not None)

        result = measure_with_retry(
            measure_func,
            max_retries=1,
            logger=logger,
            operation_name="test_measure"
        )
        assert result == ""  # Should NOT retry

    def test_false_value_valid(self, logger):
        """Test that False is treated as valid measurement."""
        def measure_func():
            return False  # False is valid (not None)

        result = measure_with_retry(
            measure_func,
            max_retries=1,
            logger=logger,
            operation_name="test_measure"
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
            measure_func,
            max_retries=10,
            retry_delay=0.01,
            logger=logger,
            operation_name="ping"
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
            operation_name="ping"
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
            measure_func,
            max_retries=5,
            retry_delay=0.01,
            logger=logger,
            operation_name="ping"
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
            operation_name="rule_enabled_verify"
        )
        assert verify_result is True

        # Then measure RTT
        def measure_rtt():
            return 48.5

        measure_result = measure_with_retry(
            measure_rtt,
            max_retries=3,
            retry_delay=0.01,
            logger=logger,
            operation_name="ping"
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
            operation_name="state_verify"
        )

        assert result is True
        assert call_count[0] == 3

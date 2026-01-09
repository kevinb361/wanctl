"""Unit tests for steering_logger module."""

import logging
import pytest

from wanctl.steering_logger import SteeringLogger
from wanctl.steering.cake_stats import CongestionSignals


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    logger = logging.getLogger("test_steering_logger")
    # Clear any existing handlers
    logger.handlers.clear()
    return logger


@pytest.fixture
def steering_logger(logger):
    """Provide a SteeringLogger instance."""
    return SteeringLogger(logger, "spectrum")


@pytest.fixture
def congestion_signals():
    """Provide sample CongestionSignals."""
    return CongestionSignals(
        rtt_delta=10.0,
        rtt_delta_ewma=9.5,
        cake_drops=5,
        queued_packets=100,
        baseline_rtt=30.0
    )


class TestSteeringLoggerInitialization:
    """Tests for SteeringLogger initialization."""

    def test_initialization(self, logger):
        """Test initializing steering logger."""
        logger_obj = SteeringLogger(logger, "spectrum")
        assert logger_obj.wan_name == "SPECTRUM"
        assert logger_obj.logger == logger

    def test_wan_name_uppercase_conversion(self, logger):
        """Test WAN name is converted to uppercase."""
        logger_obj = SteeringLogger(logger, "att")
        assert logger_obj.wan_name == "ATT"


class TestLogMeasurement:
    """Tests for log_measurement method."""

    def test_log_measurement_rtt_only(self, steering_logger, caplog):
        """Test logging RTT-only measurement."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_measurement(
                current_state="SPECTRUM_GOOD",
                current_rtt=32.5,
                baseline_rtt=30.0,
                delta=2.5,
                bad_count=0,
                good_count=5,
                bad_samples_threshold=3,
                good_samples_threshold=15,
                cake_aware=False
            )

        assert "[SPECTRUM_GOOD]" in caplog.text
        assert "RTT=32.5ms" in caplog.text
        assert "baseline=30.0ms" in caplog.text
        assert "delta=2.5ms" in caplog.text

    def test_log_measurement_cake_aware(self, steering_logger, congestion_signals, caplog):
        """Test logging CAKE-aware measurement."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_measurement(
                current_state="SPECTRUM_GOOD",
                current_rtt=32.5,
                baseline_rtt=30.0,
                delta=2.5,
                signals=congestion_signals,
                cake_aware=True
            )

        assert "[SPECTRUM_GOOD]" in caplog.text
        # CAKE-aware format should include signals

    def test_log_measurement_none_baseline(self, steering_logger, caplog):
        """Test logging measurement with None baseline."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_measurement(
                current_state="SPECTRUM_GOOD",
                current_rtt=32.5,
                baseline_rtt=None,
                delta=0.0,
                cake_aware=False
            )

        assert "baseline=N/A" in caplog.text


class TestLogStateTransition:
    """Tests for log_state_transition method."""

    def test_log_state_transition_basic(self, steering_logger, caplog):
        """Test logging basic state transition."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_state_transition(
                old_state="SPECTRUM_GOOD",
                new_state="SPECTRUM_DEGRADED",
                bad_count=3,
                good_count=0
            )

        assert "State transition" in caplog.text
        assert "SPECTRUM_GOOD" in caplog.text
        assert "SPECTRUM_DEGRADED" in caplog.text
        assert "bad=3, good=0" in caplog.text

    def test_log_state_transition_with_reason(self, steering_logger, caplog):
        """Test logging state transition with reason."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_state_transition(
                old_state="SPECTRUM_GOOD",
                new_state="SPECTRUM_DEGRADED",
                reason="RTT delta exceeded"
            )

        assert "(RTT delta exceeded)" in caplog.text


class TestLogFailureWithCounter:
    """Tests for log_failure_with_counter method."""

    def test_first_failure_warning(self, steering_logger, caplog):
        """Test first failure logs at WARNING level."""
        with caplog.at_level(logging.WARNING):
            steering_logger.log_failure_with_counter(
                failure_type="CAKE stats read",
                failure_count=1,
                max_failures=3,
                context="WAN-Download-Spectrum"
            )

        assert "CAKE stats read failed" in caplog.text
        assert "failure 1/3" in caplog.text
        assert caplog.records[0].levelno == logging.WARNING

    def test_threshold_failure_error(self, steering_logger, caplog):
        """Test failure at threshold logs at ERROR level."""
        with caplog.at_level(logging.ERROR):
            steering_logger.log_failure_with_counter(
                failure_type="CAKE stats read",
                failure_count=3,
                max_failures=3
            )

        assert "CAKE stats read unavailable after 3 attempts" in caplog.text
        assert "entering sustained degraded mode" in caplog.text
        assert caplog.records[0].levelno == logging.ERROR

    def test_sustained_failure_debug(self, steering_logger, caplog):
        """Test sustained failure logs at DEBUG level."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_failure_with_counter(
                failure_type="ping",
                failure_count=5,
                max_failures=3
            )

        assert "still unavailable" in caplog.text
        assert caplog.records[0].levelno == logging.DEBUG


class TestLogRuleState:
    """Tests for log_rule_state method."""

    def test_rule_enabled_verified(self, steering_logger, caplog):
        """Test logging rule enable with verification."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_rule_state(
                rule_comment="ADAPTIVE: Steer latency-sensitive to ATT",
                state="enabled",
                verified=True,
                attempts=1
            )

        assert "Steering rule enabled" in caplog.text
        assert "ADAPTIVE" in caplog.text

    def test_rule_disabled_verified(self, steering_logger, caplog):
        """Test logging rule disable with verification."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_rule_state(
                rule_comment="ADAPTIVE",
                state="disabled",
                verified=True
            )

        assert "Steering rule disabled" in caplog.text

    def test_rule_verify_failed(self, steering_logger, caplog):
        """Test logging rule verification failure."""
        with caplog.at_level(logging.ERROR):
            steering_logger.log_rule_state(
                rule_comment="ADAPTIVE",
                state="enabled",
                verified=False,
                attempts=2
            )

        assert "FAILED verification" in caplog.text
        assert caplog.records[0].levelno == logging.ERROR

    def test_rule_verified_with_retries(self, steering_logger, caplog):
        """Test logging rule verified after multiple attempts."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_rule_state(
                rule_comment="ADAPTIVE",
                state="enabled",
                verified=True,
                attempts=3
            )

        assert "took 3 attempts" in caplog.text


class TestLogRetryAttempt:
    """Tests for log_retry_attempt method."""

    def test_retry_attempt_failure(self, steering_logger, caplog):
        """Test logging retry attempt failure."""
        with caplog.at_level(logging.WARNING):
            steering_logger.log_retry_attempt(
                operation="ping",
                attempt=1,
                max_attempts=3,
                success=False,
                context="8.8.8.8"
            )

        assert "failed on attempt 1/3" in caplog.text
        assert caplog.records[0].levelno == logging.WARNING

    def test_retry_attempt_success(self, steering_logger, caplog):
        """Test logging retry attempt success."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_retry_attempt(
                operation="rule verification",
                attempt=2,
                max_attempts=3,
                success=True
            )

        assert "succeeded on attempt 2" in caplog.text
        assert caplog.records[0].levelno == logging.INFO


class TestLogBaselineUpdate:
    """Tests for log_baseline_update method."""

    def test_baseline_initialization(self, steering_logger, caplog):
        """Test logging baseline initialization."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_baseline_update(
                old_baseline=None,
                new_baseline=30.0
            )

        assert "Baseline RTT initialized" in caplog.text
        assert "30.00ms" in caplog.text

    def test_baseline_significant_change(self, steering_logger, caplog):
        """Test logging significant baseline change."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_baseline_update(
                old_baseline=30.0,
                new_baseline=38.0,
                change_threshold=5.0
            )

        assert "Baseline RTT changed" in caplog.text
        assert "30.00ms" in caplog.text
        assert "38.00ms" in caplog.text

    def test_baseline_minor_change(self, steering_logger, caplog):
        """Test logging minor baseline change (debug level)."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_baseline_update(
                old_baseline=30.0,
                new_baseline=31.0,
                change_threshold=5.0
            )

        assert "updated" in caplog.text
        assert caplog.records[0].levelno == logging.DEBUG


class TestLogDegradedMode:
    """Tests for degraded mode logging methods."""

    def test_log_degraded_mode_entry(self, steering_logger, caplog):
        """Test logging entry into degraded mode."""
        with caplog.at_level(logging.WARNING):
            steering_logger.log_degraded_mode_entry(
                reason="CAKE stats unavailable",
                fallback="RTT-only decisions"
            )

        assert "Entering degraded mode" in caplog.text
        assert "CAKE stats unavailable" in caplog.text
        assert "RTT-only decisions" in caplog.text

    def test_log_degraded_mode_recovery(self, steering_logger, caplog):
        """Test logging recovery from degraded mode."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_degraded_mode_recovery(
                recovered_service="CAKE stats"
            )

        assert "Recovered from degraded mode" in caplog.text
        assert "CAKE stats available again" in caplog.text


class TestLogDebugCycleState:
    """Tests for log_debug_cycle_state method."""

    def test_log_debug_cycle_state(self, steering_logger, congestion_signals, caplog):
        """Test logging debug cycle state."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_debug_cycle_state(
                current_state="SPECTRUM_GOOD",
                signals=congestion_signals,
                assessment="GREEN"
            )

        assert "[SPECTRUM_GOOD]" in caplog.text
        assert "[GREEN]" in caplog.text

    def test_log_debug_with_details(self, steering_logger, congestion_signals, caplog):
        """Test logging debug cycle state with details."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_debug_cycle_state(
                current_state="SPECTRUM_DEGRADED",
                signals=congestion_signals,
                assessment="RED",
                details="RTT threshold exceeded"
            )

        assert "RTT threshold exceeded" in caplog.text


class TestLogErrorWithContext:
    """Tests for log_error_with_context method."""

    def test_log_error_with_context(self, steering_logger, caplog):
        """Test logging error with context."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            with caplog.at_level(logging.ERROR):
                steering_logger.log_error_with_context(
                    operation="Read CAKE stats",
                    error=e,
                    context="WAN-Download"
                )

        assert "Read CAKE stats failed" in caplog.text
        assert "Test error" in caplog.text


class TestLogCacheHit:
    """Tests for log_cache_hit method."""

    def test_log_cache_hit(self, steering_logger, caplog):
        """Test logging cache hit."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_cache_hit(
                cached_value="baseline RTT",
                context="measurement"
            )

        assert "Using cached baseline RTT" in caplog.text
        assert "for measurement" in caplog.text

    def test_log_cache_hit_no_context(self, steering_logger, caplog):
        """Test logging cache hit without context."""
        with caplog.at_level(logging.DEBUG):
            steering_logger.log_cache_hit(
                cached_value="previous state"
            )

        assert "Using cached previous state" in caplog.text


class TestSteeringLoggerWANNames:
    """Tests for WAN name handling in logs."""

    def test_different_wan_names(self, logger):
        """Test various WAN names are uppercased correctly."""
        for wan_name in ["spectrum", "att", "verizon", "fiber"]:
            logger_obj = SteeringLogger(logger, wan_name)
            assert logger_obj.wan_name == wan_name.upper()

    def test_state_suffix_extraction(self, steering_logger, caplog):
        """Test state name suffix extraction in logs."""
        with caplog.at_level(logging.INFO):
            steering_logger.log_state_transition(
                old_state="SPECTRUM_GOOD",
                new_state="SPECTRUM_DEGRADED"
            )

        # Should show SPECTRUM_GOOD and SPECTRUM_DEGRADED
        assert "SPECTRUM_GOOD" in caplog.text

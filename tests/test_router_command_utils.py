"""Unit tests for router command utilities."""

import logging
import pytest

from wanctl.router_command_utils import (
    check_command_success,
    safe_parse_output,
    validate_rule_status,
    extract_field_value,
    extract_queue_stats,
    handle_command_error,
)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_router_command_utils")


class TestCheckCommandSuccess:
    """Tests for check_command_success function."""

    def test_success_rc_zero(self, logger):
        """Test successful command (rc=0)."""
        result = check_command_success(0, "/queue tree print", logger=logger)
        assert result is True

    def test_failure_rc_nonzero(self, logger):
        """Test failed command (rc != 0)."""
        result = check_command_success(1, "/queue tree print", err="not found", logger=logger)
        assert result is False

    def test_failure_with_error_message(self, logger):
        """Test failed command with error message."""
        result = check_command_success(
            rc=127,
            cmd="/invalid command",
            err="syntax error",
            logger=logger,
            operation="queue update"
        )
        assert result is False

    def test_default_logger(self):
        """Test with default logger (not provided)."""
        result = check_command_success(0, "/queue tree print")
        assert result is True


class TestSafeParseOutput:
    """Tests for safe_parse_output function."""

    def test_successful_parse(self, logger):
        """Test successful parsing."""
        def parse_func(output):
            return int(output.strip())

        result = safe_parse_output("42", parse_func, logger=logger)
        assert result == 42

    def test_parse_function_returns_none(self, logger):
        """Test when parse function returns None."""
        def parse_func(output):
            return None

        result = safe_parse_output("output", parse_func, logger=logger, default=-1)
        assert result == -1

    def test_parse_exception_handling(self, logger):
        """Test exception handling in parse function."""
        def parse_func(output):
            raise ValueError("Invalid input")

        result = safe_parse_output("invalid", parse_func, logger=logger, default="default_value")
        assert result == "default_value"

    def test_empty_output(self, logger):
        """Test with empty output."""
        def parse_func(output):
            return "should_not_be_called"

        result = safe_parse_output("", parse_func, logger=logger, default=None)
        assert result is None

    def test_whitespace_only_output(self, logger):
        """Test with whitespace-only output."""
        def parse_func(output):
            return "should_not_be_called"

        result = safe_parse_output("   ", parse_func, logger=logger, default=42)
        assert result == 42


class TestValidateRuleStatus:
    """Tests for validate_rule_status function."""

    def test_rule_enabled(self, logger):
        """Test rule enabled (no X flag)."""
        output = "0 ;;; ADAPTIVE: Steer latency-sensitive to ATT"
        result = validate_rule_status(output, logger=logger)
        assert result is True

    def test_rule_disabled(self, logger):
        """Test rule disabled (X flag present)."""
        output = "0 X ;;; ADAPTIVE: Steer latency-sensitive to ATT"
        result = validate_rule_status(output, logger=logger)
        assert result is False

    def test_disabled_with_more_flags(self, logger):
        """Test disabled with additional flags."""
        output = "0 X I ;;; comment text"
        result = validate_rule_status(output, logger=logger)
        assert result is False

    def test_enabled_with_other_flags(self, logger):
        """Test enabled with other flags (but no X)."""
        output = "0 I ;;; comment text"
        result = validate_rule_status(output, logger=logger)
        assert result is True

    def test_multiline_output(self, logger):
        """Test with multiline output (uses first line only)."""
        output = "0 X ;;; disabled rule\n1 ;;; another rule"
        result = validate_rule_status(output, logger=logger)
        assert result is False  # X is on first line

    def test_empty_output(self, logger):
        """Test with empty output (rule not found)."""
        result = validate_rule_status("", logger=logger)
        assert result is None

    def test_whitespace_output(self, logger):
        """Test with whitespace-only output."""
        result = validate_rule_status("   ", logger=logger)
        assert result is None


class TestExtractFieldValue:
    """Tests for extract_field_value function."""

    def test_extract_integer_field(self, logger):
        """Test extracting an integer field."""
        output = "max-limit=940000000 name=WAN-Download"
        result = extract_field_value(output, "max-limit", int, logger=logger)
        assert result == 940000000

    def test_extract_hyphenated_field(self, logger):
        """Test extracting field with hyphens."""
        output = "queued-packets=42 dropped=5"
        result = extract_field_value(output, "queued-packets", int, logger=logger)
        assert result == 42

    def test_extract_field_with_underscore(self, logger):
        """Test field name with underscore (converts to hyphen)."""
        output = "queued-packets=10"
        result = extract_field_value(output, "queued_packets", int, logger=logger)
        assert result == 10

    def test_extract_string_field(self, logger):
        """Test extracting string field."""
        output = 'name=WAN-Download-Spectrum parent=bridge1'
        result = extract_field_value(output, "name", str, logger=logger)
        assert result == "WAN-Download-Spectrum"

    def test_extract_float_field(self, logger):
        """Test extracting float field."""
        output = "rate=1.5 bytes=1000"
        result = extract_field_value(output, "rate", float, logger=logger)
        assert result == 1.5

    def test_field_not_found(self, logger):
        """Test when field not found."""
        output = "name=WAN-Download"
        result = extract_field_value(output, "nonexistent", int, logger=logger)
        assert result is None

    def test_invalid_conversion(self, logger):
        """Test invalid type conversion."""
        output = "value=not_a_number"
        result = extract_field_value(output, "value", int, logger=logger)
        assert result is None

    def test_empty_output(self, logger):
        """Test with empty output."""
        result = extract_field_value("", "field", int, logger=logger)
        assert result is None


class TestExtractQueueStats:
    """Tests for extract_queue_stats function."""

    def test_extract_all_stats(self, logger):
        """Test extracting all queue statistics."""
        output = (
            'name="WAN-Download" packets=1000 bytes=5000000 dropped=10 '
            'queued-packets=3 queued-bytes=1500'
        )
        result = extract_queue_stats(output, logger=logger)

        assert result['packets'] == 1000
        assert result['bytes'] == 5000000
        assert result['dropped'] == 10
        assert result['queued_packets'] == 3
        assert result['queued_bytes'] == 1500

    def test_partial_stats(self, logger):
        """Test with only some stats present."""
        output = "packets=500 dropped=2"
        result = extract_queue_stats(output, logger=logger)

        assert result['packets'] == 500
        assert result['dropped'] == 2
        assert result['bytes'] == 0  # Not present, defaults to 0
        assert result['queued_packets'] == 0

    def test_bytes_without_queued_bytes(self, logger):
        """Test that 'bytes' regex doesn't match 'queued-bytes'."""
        output = "bytes=1000000 queued-bytes=2000"
        result = extract_queue_stats(output, logger=logger)

        assert result['bytes'] == 1000000
        assert result['queued_bytes'] == 2000

    def test_large_numbers(self, logger):
        """Test with large numbers (realistic values)."""
        output = "packets=184614358 bytes=272603902153 dropped=0 queued-packets=0"
        result = extract_queue_stats(output, logger=logger)

        assert result['packets'] == 184614358
        assert result['bytes'] == 272603902153

    def test_empty_output(self, logger):
        """Test with empty output (returns defaults)."""
        result = extract_queue_stats("", logger=logger)

        assert result['packets'] == 0
        assert result['bytes'] == 0
        assert result['dropped'] == 0
        assert result['queued_packets'] == 0
        assert result['queued_bytes'] == 0

    def test_malformed_number(self, logger):
        """Test with malformed number (skips field)."""
        output = "packets=invalid bytes=1000"
        result = extract_queue_stats(output, logger=logger)

        assert result['packets'] == 0  # Failed conversion
        assert result['bytes'] == 1000  # This one succeeded


class TestHandleCommandError:
    """Tests for handle_command_error function."""

    def test_success_rc_zero(self, logger):
        """Test successful command (rc=0)."""
        success, value = handle_command_error(0, "", "/queue tree print", logger=logger)
        assert success is True
        assert value is None

    def test_failure_with_return_value(self, logger):
        """Test failed command with return value."""
        success, value = handle_command_error(
            rc=1,
            err="not found",
            cmd="/queue tree print",
            logger=logger,
            return_value=None
        )
        assert success is False
        assert value is None

    def test_failure_returns_custom_value(self, logger):
        """Test failed command returns custom value."""
        success, value = handle_command_error(
            rc=127,
            err="error",
            cmd="/invalid",
            logger=logger,
            return_value=-1
        )
        assert success is False
        assert value == -1

    def test_success_ignores_return_value(self, logger):
        """Test that success ignores return_value parameter."""
        success, value = handle_command_error(
            rc=0,
            err="",
            cmd="/command",
            logger=logger,
            return_value="should_be_ignored"
        )
        assert success is True
        assert value is None


class TestRouterCommandUtilsIntegration:
    """Integration tests combining multiple utilities."""

    def test_full_queue_operation_success(self, logger):
        """Test complete queue operation flow."""
        # Simulate successful command
        rc = 0
        err = ""
        cmd = "/queue/tree/set [find name=WAN-Download] max-limit=500000000"

        # Check success
        success = check_command_success(rc, cmd, err, logger=logger)
        assert success is True

    def test_queue_stats_retrieval_flow(self, logger):
        """Test complete queue stats retrieval flow."""
        rc = 0
        output = (
            'name="WAN-Download" packets=1000 bytes=5000000 dropped=5 '
            'queued-packets=2 queued-bytes=1000'
        )

        # Check command success
        success = check_command_success(rc, "/queue/tree/print stats", logger=logger)
        assert success is True

        # Parse output
        stats = extract_queue_stats(output, logger=logger)
        assert stats['packets'] == 1000
        assert stats['dropped'] == 5

    def test_rule_enable_verify_flow(self, logger):
        """Test rule enable and verification flow."""
        # Enable rule
        rc = 0
        success = check_command_success(
            rc,
            "/ip/firewall/mangle/enable [find comment=ADAPTIVE]",
            logger=logger
        )
        assert success is True

        # Check status
        rule_output = "0 ;;; ADAPTIVE: Steer latency-sensitive to ATT"
        is_enabled = validate_rule_status(rule_output, logger=logger)
        assert is_enabled is True

    def test_error_handling_with_fallback(self, logger):
        """Test error handling with fallback value."""
        rc = 1
        err = "queue not found"

        # Handle error
        success, fallback_value = handle_command_error(
            rc=rc,
            err=err,
            cmd="/queue/tree/print",
            logger=logger,
            return_value=0  # Default rate
        )

        assert success is False
        assert fallback_value == 0

"""Tests for logging utilities including JSON structured logging."""

import json
import logging
import os
from pathlib import Path
from unittest.mock import patch

from wanctl.logging_utils import (
    JSONFormatter,
    _create_formatter,
    get_log_format,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_basic_format(self):
        """Test basic JSON formatting with standard fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        # Verify timestamp format (ISO 8601 with Z suffix)
        assert data["timestamp"].endswith("Z")
        assert "T" in data["timestamp"]

    def test_format_with_extra_fields(self):
        """Test JSON formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wanctl",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="State change",
            args=(),
            exc_info=None,
        )
        # Add extra fields
        record.wan_name = "spectrum"
        record.state = "GREEN"
        record.rtt_delta = 5.2

        result = formatter.format(record)
        data = json.loads(result)

        assert data["wan_name"] == "spectrum"
        assert data["state"] == "GREEN"
        assert data["rtt_delta"] == 5.2

    def test_format_with_message_args(self):
        """Test JSON formatting with message format args."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wanctl",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Rate changed: %d Mbps",
            args=(100,),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["message"] == "Rate changed: 100 Mbps"

    def test_format_with_exception(self):
        """Test JSON formatting includes exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="wanctl",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="An error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError: Test exception" in data["exception"]

    def test_format_excludes_internal_attrs(self):
        """Test that internal LogRecord attributes are excluded."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wanctl",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        # These should NOT be in the output
        assert "pathname" not in data
        assert "lineno" not in data
        assert "funcName" not in data
        assert "processName" not in data
        assert "threadName" not in data
        assert "created" not in data

    def test_format_non_serializable_extra(self):
        """Test handling of non-JSON-serializable extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wanctl",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )
        # Add a non-serializable object
        record.custom_object = object()

        # Should not raise, should convert to string
        result = formatter.format(record)
        data = json.loads(result)

        # The object should be converted to a string representation
        assert "custom_object" in data
        assert "<object object at" in data["custom_object"]

    def test_format_compact_output(self):
        """Test that JSON output uses compact separators."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="wanctl",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should not have spaces after separators (compact format)
        assert ": " not in result or result.count(": ") == 0
        assert ", " not in result


class TestGetLogFormat:
    """Tests for get_log_format function."""

    def test_default_is_text(self):
        """Test default log format is 'text'."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure WANCTL_LOG_FORMAT is not set
            os.environ.pop("WANCTL_LOG_FORMAT", None)
            assert get_log_format() == "text"

    def test_json_from_env(self):
        """Test JSON format from environment variable."""
        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "json"}):
            assert get_log_format() == "json"

    def test_text_from_env(self):
        """Test text format from environment variable."""
        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "text"}):
            assert get_log_format() == "text"

    def test_case_insensitive(self):
        """Test environment variable is case-insensitive."""
        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "JSON"}):
            assert get_log_format() == "json"

        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "Json"}):
            assert get_log_format() == "json"

    def test_invalid_value_defaults_to_text(self):
        """Test invalid environment value defaults to 'text'."""
        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "invalid"}):
            assert get_log_format() == "text"

        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "xml"}):
            assert get_log_format() == "text"


class TestCreateFormatter:
    """Tests for _create_formatter function."""

    def test_creates_json_formatter(self):
        """Test creating a JSON formatter."""
        formatter = _create_formatter("json", "spectrum")
        assert isinstance(formatter, JSONFormatter)

    def test_creates_text_formatter(self):
        """Test creating a text formatter."""
        formatter = _create_formatter("text", "spectrum")
        assert isinstance(formatter, logging.Formatter)
        assert not isinstance(formatter, JSONFormatter)

    def test_text_formatter_includes_wan_name(self):
        """Test text formatter includes WAN name in format string."""
        formatter = _create_formatter("text", "MyWAN")
        # The format string should contain the WAN name
        assert "MyWAN" in formatter._fmt


class MockConfig:
    """Mock config object for testing setup_logging."""

    def __init__(self, temp_dir: Path, wan_name: str = "TestWAN"):
        self.wan_name = wan_name
        self.main_log = str(temp_dir / "main.log")
        self.debug_log = str(temp_dir / "debug.log")


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_logger(self, temp_dir):
        """Test that setup_logging creates a logger."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_prefix")

        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert "test_prefix" in logger.name

    def test_creates_file_handler(self, temp_dir):
        """Test that setup_logging creates a file handler."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_file")

        # Should have at least one handler (main log)
        assert len(logger.handlers) >= 1
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    def test_reuses_existing_logger(self, temp_dir):
        """Test that setup_logging reuses an existing logger with handlers."""
        config = MockConfig(temp_dir)
        logger1 = setup_logging(config, "test_reuse")
        logger2 = setup_logging(config, "test_reuse")

        assert logger1 is logger2
        # Should not have added duplicate handlers
        assert len(logger1.handlers) == len(logger2.handlers)

    def test_debug_mode_adds_handlers(self, temp_dir):
        """Test that debug mode adds console and debug file handlers."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_debug", debug=True)

        # Should have 3 handlers: main log, debug log, console
        assert len(logger.handlers) == 3

    def test_log_format_parameter(self, temp_dir):
        """Test log_format parameter overrides environment."""
        config = MockConfig(temp_dir)

        # Even with env set to text, parameter should override
        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "text"}):
            logger = setup_logging(config, "test_format", log_format="json")

        # Check that at least one handler uses JSONFormatter
        formatters = [h.formatter for h in logger.handlers]
        assert any(isinstance(f, JSONFormatter) for f in formatters)

    def test_env_variable_json_format(self, temp_dir):
        """Test WANCTL_LOG_FORMAT=json uses JSON formatter."""
        config = MockConfig(temp_dir)

        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "json"}):
            logger = setup_logging(config, "test_env_json")

        formatters = [h.formatter for h in logger.handlers]
        assert all(isinstance(f, JSONFormatter) for f in formatters)

    def test_text_format_output(self, temp_dir):
        """Test that text format produces expected output."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_text_output", log_format="text")

        logger.info("Test message")

        # Read the log file
        log_content = Path(config.main_log).read_text()
        assert "Test message" in log_content
        assert "[TestWAN]" in log_content
        assert "[INFO]" in log_content

    def test_json_format_output(self, temp_dir):
        """Test that JSON format produces valid JSON output."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_json_output", log_format="json")

        logger.info("Test message", extra={"custom_field": "value"})

        # Read and parse the log file
        log_content = Path(config.main_log).read_text().strip()
        data = json.loads(log_content)

        assert data["message"] == "Test message"
        assert data["custom_field"] == "value"
        assert data["level"] == "INFO"

    def test_json_format_with_extra_fields(self, temp_dir):
        """Test JSON format properly captures extra fields."""
        config = MockConfig(temp_dir)
        logger = setup_logging(config, "test_json_extra", log_format="json")

        logger.info(
            "State transition",
            extra={
                "wan_name": "spectrum",
                "state": "GREEN",
                "rtt_delta": 5.2,
                "dl_rate": 750000000,
            },
        )

        log_content = Path(config.main_log).read_text().strip()
        data = json.loads(log_content)

        assert data["wan_name"] == "spectrum"
        assert data["state"] == "GREEN"
        assert data["rtt_delta"] == 5.2
        assert data["dl_rate"] == 750000000


class TestIntegration:
    """Integration tests for logging utilities."""

    def test_full_workflow_text_mode(self, temp_dir):
        """Test complete logging workflow in text mode."""
        config = MockConfig(temp_dir, wan_name="spectrum")

        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "text"}):
            logger = setup_logging(config, "integration_text", debug=True)

        logger.info("Starting autorate")
        logger.debug("Baseline RTT: 24.0ms")
        logger.warning("High RTT detected")

        # Check main log (INFO level)
        main_log = Path(config.main_log).read_text()
        assert "Starting autorate" in main_log
        assert "High RTT detected" in main_log
        assert "Baseline RTT" not in main_log  # DEBUG not in INFO log

        # Check debug log
        debug_log = Path(config.debug_log).read_text()
        assert "Baseline RTT: 24.0ms" in debug_log

    def test_full_workflow_json_mode(self, temp_dir):
        """Test complete logging workflow in JSON mode."""
        config = MockConfig(temp_dir, wan_name="spectrum")

        with patch.dict(os.environ, {"WANCTL_LOG_FORMAT": "json"}):
            logger = setup_logging(config, "integration_json", debug=True)

        logger.info("State change", extra={"old_state": "YELLOW", "new_state": "GREEN"})
        logger.debug("RTT measurement", extra={"rtt_ms": 24.5})

        # Check main log (INFO level)
        main_log_lines = Path(config.main_log).read_text().strip().split("\n")
        assert len(main_log_lines) == 1

        data = json.loads(main_log_lines[0])
        assert data["message"] == "State change"
        assert data["old_state"] == "YELLOW"
        assert data["new_state"] == "GREEN"

        # Check debug log has both entries
        debug_log_lines = Path(config.debug_log).read_text().strip().split("\n")
        assert len(debug_log_lines) == 2

        debug_data = json.loads(debug_log_lines[1])
        assert debug_data["rtt_ms"] == 24.5

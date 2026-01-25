"""Unit tests for error handling utilities."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from wanctl.error_handling import (
    handle_errors,
    safe_call,
    safe_operation,
)


class TestHandleErrorsDecorator:
    """Tests for handle_errors decorator."""

    def test_returns_function_result_on_success(self):
        """Test that successful execution returns the function result."""

        @handle_errors(default_return=None)
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_returns_default_on_exception(self):
        """Test that default_return is returned on exception."""

        @handle_errors(default_return="default")
        def failing_func():
            raise ValueError("test error")

        result = failing_func()
        assert result == "default"

    def test_logs_at_specified_level(self, caplog):
        """Test that errors are logged at the specified level."""

        @handle_errors(default_return=None, log_level=logging.ERROR)
        def failing_func():
            raise ValueError("test error")

        with caplog.at_level(logging.ERROR):
            failing_func()

        assert "failing_func failed: test error" in caplog.text

    def test_logs_at_warning_by_default(self, caplog):
        """Test default log level is WARNING."""

        @handle_errors(default_return=None)
        def failing_func():
            raise ValueError("warning error")

        with caplog.at_level(logging.WARNING):
            failing_func()

        assert "failing_func failed: warning error" in caplog.text

    def test_finds_logger_from_self_logger_attribute(self, caplog):
        """Test logger discovery from self.logger attribute."""
        test_logger = logging.getLogger("test.custom")

        class MockObject:
            def __init__(self):
                self.logger = test_logger

            @handle_errors(default_return=None)
            def method_that_fails(self):
                raise ValueError("method error")

        obj = MockObject()
        with caplog.at_level(logging.WARNING, logger="test.custom"):
            obj.method_that_fails()

        # Verify the custom logger received the message
        assert any("method_that_fails failed" in r.message for r in caplog.records if r.name == "test.custom")

    def test_fallback_to_module_logger_when_no_self_logger(self, caplog):
        """Test fallback to module logger when object has no logger."""

        class NoLoggerObject:
            @handle_errors(default_return=None)
            def method_that_fails(self):
                raise ValueError("no logger error")

        obj = NoLoggerObject()
        with caplog.at_level(logging.WARNING):
            obj.method_that_fails()

        assert "method_that_fails failed: no logger error" in caplog.text

    def test_finds_logger_named_log(self, caplog):
        """Test logger discovery from self.log attribute."""
        test_logger = logging.getLogger("test.log_attr")

        class ObjectWithLogAttr:
            def __init__(self):
                self.log = test_logger

            @handle_errors(default_return=None)
            def method_that_fails(self):
                raise ValueError("log attr error")

        obj = ObjectWithLogAttr()
        with caplog.at_level(logging.WARNING, logger="test.log_attr"):
            obj.method_that_fails()

        assert any("method_that_fails failed" in r.message for r in caplog.records if r.name == "test.log_attr")

    def test_custom_error_msg_used(self, caplog):
        """Test that custom error_msg is used when provided."""

        @handle_errors(default_return=None, error_msg="Custom failure message")
        def failing_func():
            raise ValueError("original error")

        with caplog.at_level(logging.WARNING):
            failing_func()

        assert "Custom failure message" in caplog.text

    def test_exception_placeholder_replaced(self, caplog):
        """Test {exception} placeholder is replaced."""

        @handle_errors(default_return=None, error_msg="Operation failed: {exception}")
        def failing_func():
            raise ValueError("specific error")

        with caplog.at_level(logging.WARNING):
            failing_func()

        assert "Operation failed: specific error" in caplog.text

    def test_self_attr_placeholder_replaced(self, caplog):
        """Test {self.attr} placeholder is replaced from first arg."""

        class MockObject:
            def __init__(self):
                self.name = "test_instance"
                self.logger = logging.getLogger("test.selfattr")

            @handle_errors(default_return=None, error_msg="Failed for {self.name}: {exception}")
            def method_that_fails(self):
                raise ValueError("attr error")

        obj = MockObject()
        with caplog.at_level(logging.WARNING):
            obj.method_that_fails()

        assert "Failed for test_instance: attr error" in caplog.text

    def test_format_failure_falls_back_to_default_message(self, caplog):
        """Test format failure falls back to default message."""

        @handle_errors(default_return=None, error_msg="Bad format {undefined_key}")
        def failing_func():
            raise ValueError("format test error")

        with caplog.at_level(logging.WARNING):
            failing_func()

        # Should fall back to default format
        assert "failing_func failed: format test error" in caplog.text

    def test_log_traceback_logs_at_debug(self, caplog):
        """Test log_traceback=True logs traceback at DEBUG level."""

        @handle_errors(default_return=None, log_traceback=True)
        def failing_func():
            raise ValueError("traceback error")

        with caplog.at_level(logging.DEBUG):
            failing_func()

        # Should have both the warning and the traceback
        assert "failing_func failed: traceback error" in caplog.text
        assert "Traceback" in caplog.text or "ValueError: traceback error" in caplog.text

    def test_callable_default_return_invoked(self):
        """Test callable default_return is invoked on exception."""
        call_tracker = MagicMock(return_value="computed_default")

        @handle_errors(default_return=call_tracker)
        def failing_func():
            raise ValueError("callable test")

        result = failing_func()
        assert result == "computed_default"
        call_tracker.assert_called_once()

    def test_exception_types_filtering_catches_specified(self):
        """Test exception_types catches only specified exceptions."""

        @handle_errors(default_return="caught", exception_types=(ValueError,))
        def failing_func():
            raise ValueError("should be caught")

        result = failing_func()
        assert result == "caught"

    def test_exception_types_filtering_lets_others_through(self):
        """Test exception_types lets unspecified exceptions through."""

        @handle_errors(default_return="caught", exception_types=(ValueError,))
        def failing_func():
            raise TypeError("should not be caught")

        with pytest.raises(TypeError, match="should not be caught"):
            failing_func()

    def test_reraise_reraices_after_logging(self, caplog):
        """Test reraise=True re-raises after logging."""

        @handle_errors(default_return=None, reraise=True)
        def failing_func():
            raise ValueError("reraise error")

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ValueError, match="reraise error"):
                failing_func()

        # Verify it was logged before reraising
        assert "failing_func failed: reraise error" in caplog.text

    def test_on_error_callback_invoked(self):
        """Test on_error callback is invoked with exception."""
        callback = MagicMock()

        @handle_errors(default_return=None, on_error=callback)
        def failing_func():
            raise ValueError("callback error")

        failing_func()
        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], ValueError)

    def test_on_error_callback_errors_caught(self, caplog):
        """Test on_error callback errors are caught and logged."""

        def failing_callback(exc):
            raise RuntimeError("callback failed")

        @handle_errors(default_return=None, on_error=failing_callback, log_traceback=False)
        def failing_func():
            raise ValueError("original error")

        with caplog.at_level(logging.DEBUG):
            result = failing_func()

        # Should still return default
        assert result is None
        # Callback error should be logged at debug
        assert "Error in error callback" in caplog.text

    def test_standalone_function_no_self(self, caplog):
        """Test decorator works with standalone functions (no self)."""

        @handle_errors(default_return="fallback")
        def standalone():
            raise ValueError("standalone error")

        with caplog.at_level(logging.WARNING):
            result = standalone()

        assert result == "fallback"
        assert "standalone failed: standalone error" in caplog.text

    def test_method_with_args_and_kwargs(self):
        """Test decorator preserves args and kwargs."""

        @handle_errors(default_return=None)
        def func_with_args(a, b, c=None):
            return (a, b, c)

        result = func_with_args(1, 2, c=3)
        assert result == (1, 2, 3)


class TestSafeOperationContextManager:
    """Tests for safe_operation context manager."""

    def test_yields_on_no_exception(self):
        """Test context manager yields successfully when no exception."""
        logger = logging.getLogger("test.safe_op")
        executed = False

        with safe_operation(logger, operation="test op"):
            executed = True

        assert executed

    def test_catches_exception_and_logs(self, caplog):
        """Test exception is caught and logged."""
        logger = logging.getLogger("test.safe_op")

        with caplog.at_level(logging.WARNING):
            with safe_operation(logger, operation="database query"):
                raise ValueError("query failed")

        # Should not re-raise
        assert "database query failed: query failed" in caplog.text

    def test_logs_at_specified_level(self, caplog):
        """Test logging at custom log level."""
        logger = logging.getLogger("test.safe_op_level")

        with caplog.at_level(logging.ERROR):
            with safe_operation(logger, operation="critical op", log_level=logging.ERROR):
                raise ValueError("critical error")

        assert "critical op failed: critical error" in caplog.text
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_log_traceback_logs_at_debug(self, caplog):
        """Test log_traceback logs traceback at DEBUG."""
        logger = logging.getLogger("test.safe_op_tb")

        with caplog.at_level(logging.DEBUG):
            with safe_operation(logger, operation="traced op", log_traceback=True):
                raise ValueError("traced error")

        assert "traced op failed: traced error" in caplog.text
        assert "Traceback" in caplog.text or "ValueError: traced error" in caplog.text

    def test_exception_types_filtering(self):
        """Test exception_types filtering works."""
        logger = logging.getLogger("test.safe_op_filter")

        # Should catch ValueError
        with safe_operation(logger, operation="op", exception_types=(ValueError,)):
            raise ValueError("caught")

        # Should not catch TypeError
        with pytest.raises(TypeError):
            with safe_operation(logger, operation="op", exception_types=(ValueError,)):
                raise TypeError("not caught")


class TestSafeCallFunction:
    """Tests for safe_call function."""

    def test_returns_function_result_on_success(self):
        """Test successful call returns function result."""

        def add(a, b):
            return a + b

        result = safe_call(add, 1, 2)
        assert result == 3

    def test_returns_default_on_exception(self):
        """Test returns default value on exception."""

        def failing():
            raise ValueError("fail")

        result = safe_call(failing, default="fallback")
        assert result == "fallback"

    def test_uses_module_logger_when_none_provided(self, caplog):
        """Test uses module logger when none provided."""

        def failing():
            raise ValueError("module logger test")

        with caplog.at_level(logging.WARNING):
            safe_call(failing)

        assert "failing failed: module logger test" in caplog.text

    def test_uses_provided_logger(self, caplog):
        """Test uses provided logger."""
        custom_logger = logging.getLogger("test.custom_safe_call")

        def failing():
            raise ValueError("custom logger test")

        with caplog.at_level(logging.WARNING, logger="test.custom_safe_call"):
            safe_call(failing, logger=custom_logger)

        assert any("failing failed" in r.message for r in caplog.records if r.name == "test.custom_safe_call")

    def test_log_traceback_logs_at_debug(self, caplog):
        """Test log_traceback logs traceback at DEBUG."""

        def failing():
            raise ValueError("traceback test")

        with caplog.at_level(logging.DEBUG):
            safe_call(failing, log_traceback=True)

        assert "failing failed: traceback test" in caplog.text
        assert "Traceback" in caplog.text or "ValueError: traceback test" in caplog.text

    def test_logs_function_name_in_error(self, caplog):
        """Test function name is included in error message."""

        def my_special_function():
            raise ValueError("error")

        with caplog.at_level(logging.WARNING):
            safe_call(my_special_function)

        assert "my_special_function failed" in caplog.text

    def test_passes_args_and_kwargs(self):
        """Test args and kwargs are passed to function."""

        def func(a, b, c=None, d=None):
            return {"a": a, "b": b, "c": c, "d": d}

        result = safe_call(func, 1, 2, c=3, d=4)
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_custom_log_level(self, caplog):
        """Test custom log level is used."""

        def failing():
            raise ValueError("error level test")

        with caplog.at_level(logging.ERROR):
            safe_call(failing, log_level=logging.ERROR)

        assert any(r.levelno == logging.ERROR for r in caplog.records)
        assert "failing failed" in caplog.text

    def test_default_none_when_not_specified(self):
        """Test default is None when not specified."""

        def failing():
            raise ValueError("error")

        result = safe_call(failing)
        assert result is None

"""
Error handling utilities for wanctl.

Provides decorators and context managers to consolidate repetitive try/except/log patterns
used throughout the codebase (73+ instances).

Usage:
    # Simple decorator with default return value
    @handle_errors(default_return=None, log_level='warning')
    def my_method(self):
        ...

    # With traceback logging
    @handle_errors(default_return=False, log_traceback=True)
    def another_method(self):
        ...

    # With custom error message
    @handle_errors(default_return={}, error_msg="Failed to load state")
    def load_state(self):
        ...

    # Context manager
    with safe_operation(logger, operation="database query", default=None):
        result = expensive_operation()
"""

import functools
import logging
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

F = TypeVar('F', bound=Callable[..., Any])

# Log level constants
LOG_DEBUG = logging.DEBUG
LOG_INFO = logging.INFO
LOG_WARNING = logging.WARNING
LOG_ERROR = logging.ERROR
LOG_CRITICAL = logging.CRITICAL


def handle_errors(
    default_return: Any = None,
    log_level: int = logging.WARNING,
    log_traceback: bool = False,
    error_msg: str | None = None,
    exception_types: tuple = (Exception,),
    reraise: bool = False,
    on_error: Callable[[Exception], None] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to wrap methods with try/except and automatic logging.

    Consolidates repetitive error handling pattern:
    ```python
    try:
        ...
    except Exception as e:
        logger.warning(f"Operation failed: {e}")
        return default_value
    ```

    Args:
        default_return: Value to return if exception occurs. If None and reraise=False,
                       returns None. Use a callable to invoke it: lambda: compute_default()
        log_level: Logging level (logging.WARNING, logging.ERROR, etc.)
        log_traceback: If True, also log full traceback at DEBUG level
        error_msg: Custom error message prefix. If not provided, uses function name.
                   Can use {exception} placeholder: "Operation failed: {exception}"
        exception_types: Tuple of exception types to catch. Default: (Exception,)
        reraise: If True, re-raise exception after logging
        on_error: Optional callback invoked if exception occurs: on_error(exception)

    Returns:
        Decorated function that handles exceptions transparently

    Examples:
        # Simple with default None
        @handle_errors()
        def might_fail(self):
            return self.risky_operation()

        # Return False on error
        @handle_errors(default_return=False)
        def verify_state(self):
            return self.check_state()

        # Return computed value
        @handle_errors(default_return=lambda: {"status": "error"})
        def get_config(self):
            return self.load_config()

        # With custom message and traceback
        @handle_errors(
            default_return=None,
            log_level=logging.ERROR,
            log_traceback=True,
            error_msg="Failed to ping {exception}"
        )
        def ping_host(self, host: str):
            return subprocess.run(...)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                # Get logger from self (for methods)
                logger = None
                if args and hasattr(args[0], 'logger'):
                    logger = args[0].logger
                elif args and hasattr(args[0], '__dict__'):
                    # Try to find a logger in the object
                    for attr in ['logger', '_logger', 'log']:
                        if hasattr(args[0], attr):
                            potential_logger = getattr(args[0], attr)
                            if isinstance(potential_logger, logging.Logger):
                                logger = potential_logger
                                break

                # Fall back to module logger
                if logger is None:
                    logger = logging.getLogger(__name__)

                # Format error message
                if error_msg:
                    # Handle error message with optional self references
                    try:
                        if '{self' in error_msg and args and hasattr(args[0], '__dict__'):
                            # For messages like "{self.wan_name}: ...", replace with actual values
                            obj = args[0]
                            message = error_msg
                            # Find all {self.attr} patterns and replace
                            import re
                            for match in re.finditer(r'\{self\.(\w+)\}', error_msg):
                                attr_name = match.group(1)
                                if hasattr(obj, attr_name):
                                    attr_value = getattr(obj, attr_name)
                                    message = message.replace(
                                        f'{{self.{attr_name}}}',
                                        str(attr_value)
                                    )
                            # Now format with remaining placeholders
                            message = message.format(exception=str(e), func=func.__name__)
                        else:
                            message = error_msg.format(exception=str(e), func=func.__name__)
                    except (KeyError, ValueError, AttributeError, TypeError) as fmt_err:
                        # If formatting fails, fall back to simple message
                        logger.debug(f"Could not format error message: {fmt_err}")
                        message = f"{func.__name__} failed: {e}"
                else:
                    message = f"{func.__name__} failed: {e}"

                # Log the error
                logger.log(log_level, message)

                # Log traceback if requested
                if log_traceback:
                    logger.debug(traceback.format_exc())

                # Invoke callback if provided
                if on_error:
                    try:
                        on_error(e)
                    except Exception as callback_err:
                        logger.debug(f"Error in error callback: {callback_err}")

                # Re-raise if requested
                if reraise:
                    raise

                # Return default value
                if callable(default_return):
                    return default_return()
                return default_return

        return wrapper  # type: ignore

    return decorator


@contextmanager
def safe_operation(
    logger: logging.Logger,
    operation: str = "operation",
    default: Any = None,
    log_level: int = logging.WARNING,
    log_traceback: bool = False,
    exception_types: tuple = (Exception,),
):
    """
    Context manager for safe operations with error handling.

    Consolidates repetitive error handling pattern in context form:
    ```python
    try:
        result = operation()
    except Exception as e:
        logger.warning(f"Operation failed: {e}")
        return default
    ```

    Args:
        logger: Logger instance to use for error messages
        operation: Description of operation (e.g., "database query", "file write")
        default: Value to return if exception occurs
        log_level: Logging level for errors
        log_traceback: If True, log full traceback at DEBUG level
        exception_types: Tuple of exception types to catch

    Yields:
        Generator that yields control to the with block

    Examples:
        with safe_operation(logger, "loading config") as result:
            config = load_config()
            if config is None:
                result = default_config

        # With traceback logging
        with safe_operation(
            logger,
            operation="database query",
            log_traceback=True,
            exception_types=(IOError, json.JSONDecodeError)
        ):
            data = read_data()
    """
    try:
        yield
    except exception_types as e:
        message = f"{operation} failed: {e}"
        logger.log(log_level, message)

        if log_traceback:
            logger.debug(traceback.format_exc())


def safe_call(
    func: Callable[..., Any],
    *args,
    logger: logging.Logger | None = None,
    default: Any = None,
    log_level: int = logging.WARNING,
    log_traceback: bool = False,
    **kwargs
) -> Any:
    """
    Safely invoke a function with error handling and logging.

    Provides a functional approach to error handling without decorators.

    Args:
        func: Callable to invoke
        *args: Positional arguments to pass to func
        logger: Logger instance (uses module logger if not provided)
        default: Value to return if exception occurs
        log_level: Logging level for errors
        log_traceback: If True, log full traceback
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of func(*args, **kwargs), or default if exception occurs

    Examples:
        result = safe_call(
            load_config,
            config_path,
            logger=self.logger,
            default={},
            log_level=logging.ERROR
        )
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        return func(*args, **kwargs)
    except Exception as e:
        message = f"{func.__name__} failed: {e}"
        logger.log(log_level, message)

        if log_traceback:
            logger.debug(traceback.format_exc())

        return default

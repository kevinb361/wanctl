"""Router command error handling utilities.

Consolidates common error handling patterns for router command execution,
eliminating duplication across backends and command handlers.

Provides:
- CommandResult - Result type for command execution (success/failure with value/error)
- check_command_success() - Execute command and validate success/failure
- safe_parse_output() - Parse router output with error context
- validate_rule_status() - Check if rule is enabled/disabled
- extract_field_value() - Extract field value from router output using regex

Common patterns consolidated:
- Error logging with context
- Return code validation (rc != 0)
- Output parsing with fallbacks
- Rule status checking (enabled vs disabled)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandResult[T]:
    """Result type for router command execution.

    Provides a type-safe alternative to Tuple[bool, Any] returns.
    Encapsulates success/failure state with associated value or error.

    Attributes:
        success: True if command succeeded, False otherwise
        value: Result value on success (None on failure)
        error: Error message on failure (None on success)

    Example:
        >>> result = CommandResult.ok(42)
        >>> result.success
        True
        >>> result.unwrap()
        42

        >>> result = CommandResult.err("Connection failed")
        >>> result.success
        False
        >>> result.unwrap_or(0)
        0
    """

    success: bool
    value: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, value: T) -> CommandResult[T]:
        """Create a successful result with a value.

        Args:
            value: The success value

        Returns:
            CommandResult with success=True and the value
        """
        return cls(success=True, value=value, error=None)

    @classmethod
    def err(cls, error: str, value: T | None = None) -> CommandResult[T]:
        """Create a failed result with an error message.

        Args:
            error: Error message describing the failure
            value: Optional value to include (e.g., partial result)

        Returns:
            CommandResult with success=False and the error
        """
        return cls(success=False, value=value, error=error)

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self.success

    def is_err(self) -> bool:
        """Check if result is a failure."""
        return not self.success

    def unwrap(self) -> T:
        """Get the value, raising if result is an error.

        Returns:
            The success value

        Raises:
            ValueError: If result is an error
        """
        if not self.success:
            raise ValueError(f"Called unwrap() on error result: {self.error}")
        return self.value  # type: ignore[return-value]

    def unwrap_or(self, default: T) -> T:
        """Get the value or a default if result is an error.

        Args:
            default: Value to return if result is an error

        Returns:
            The success value or the default
        """
        if self.success:
            return self.value  # type: ignore[return-value]
        return default

    def unwrap_or_else(self, func: Callable[[], T]) -> T:
        """Get the value or compute a default if result is an error.

        Args:
            func: Function to call to get default value

        Returns:
            The success value or the computed default
        """
        if self.success:
            return self.value  # type: ignore[return-value]
        return func()

    def map(self, func: Callable[[T], Any]) -> CommandResult[Any]:
        """Transform the success value with a function.

        Args:
            func: Function to apply to the value

        Returns:
            New CommandResult with transformed value (or same error)
        """
        if self.success:
            return CommandResult.ok(func(self.value))  # type: ignore[arg-type]
        return CommandResult.err(self.error or "Unknown error")

    def __bool__(self) -> bool:
        """Allow using result in boolean context (if result: ...)."""
        return self.success

    def __iter__(self):
        """Support tuple unpacking for backward compatibility.

        Allows: success, value = result

        On success: yields (True, value)
        On failure: yields (False, value) - note: value, not error message
        """
        return iter((self.success, self.value))


def check_command_success(
    rc: int,
    cmd: str,
    err: str = "",
    logger: logging.Logger | None = None,
    operation: str = "command execution"
) -> bool:
    """Validate router command execution result.

    Consolidated error handling pattern for checking if a router command
    succeeded. Logs appropriate error messages and returns success/failure.

    Args:
        rc: Return code from router command (0 = success)
        cmd: The command that was executed (for logging)
        err: Error message from router (if any)
        logger: Logger instance (optional)
        operation: Description of the operation (for logging)

    Returns:
        True if rc == 0, False if rc != 0
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if rc == 0:
        logger.debug(f"{operation} succeeded: {cmd}")
        return True
    else:
        logger.error(f"Failed {operation}: {cmd} -> {err}")
        return False


def safe_parse_output(
    output: str,
    parse_func: Callable[[str], Any | None],
    logger: logging.Logger | None = None,
    operation: str = "output parsing",
    default: Any = None
) -> Any:
    """Safely parse router command output with error handling.

    Wraps a parsing function with exception handling and logging.
    Returns default value on any parse error.

    Args:
        output: Router command output to parse
        parse_func: Function that parses the output (takes str, returns value or None)
        logger: Logger instance (optional)
        operation: Description of the operation (for logging)
        default: Default value to return on parse error

    Returns:
        Parsed value from parse_func, or default if parsing fails
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if not output or not output.strip():
        logger.warning(f"{operation}: empty output")
        return default

    try:
        result = parse_func(output)
        if result is None:
            logger.warning(f"{operation}: parse function returned None")
            return default
        return result
    except Exception as e:
        logger.error(f"{operation} failed: {e}")
        return default


def validate_rule_status(
    output: str,
    logger: logging.Logger | None = None
) -> bool | None:
    """Check if a RouterOS mangle rule is enabled or disabled.

    Parses RouterOS output to determine rule status:
    - If 'X' flag appears in first line = disabled (False)
    - If no 'X' flag = enabled (True)
    - If no output or error = None

    This consolidates the pattern from:
    - backends/routeros.py::is_rule_enabled()
    - steering/daemon.py::RouterOSController.get_rule_status()

    Args:
        output: RouterOS rule print output
        logger: Logger instance (optional)

    Returns:
        True if enabled, False if disabled, None if not found/error
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if not output or not output.strip():
        logger.warning("Rule status output empty")
        return None

    try:
        # First line contains rule status
        first_line = output.split('\n')[0]
        # RouterOS shows 'X' flag for disabled rules
        # Example: "0 X ;;; ADAPTIVE: Steer..."
        is_disabled = 'X' in first_line
        return not is_disabled  # Return True if enabled, False if disabled
    except Exception as e:
        logger.error(f"Failed to parse rule status: {e}")
        return None


def extract_field_value(
    output: str,
    field_name: str,
    field_type: type = int,
    logger: logging.Logger | None = None
) -> Any | None:
    """Extract a field value from router output using regex.

    Consolidates pattern: regex search for field_name=value, convert to type.

    Supports common RouterOS output formats:
    - field_name=value (for integers, identifiers)
    - field-name=value (for hyphenated field names)

    Args:
        output: Router command output
        field_name: Name of field to extract (e.g., "packets", "max-limit")
        field_type: Type to convert value to (int, str, float)
        logger: Logger instance (optional)

    Returns:
        Extracted field value converted to field_type, or None on error
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if not output:
        logger.warning(f"Empty output when extracting {field_name}")
        return None

    try:
        # Support both hyphenated and non-hyphenated field names
        # This handles both field_name and field-name variants
        pattern = rf'(?:{field_name}|{field_name.replace("_", "-")})=([^\s\n]+)'
        match = re.search(pattern, output)

        if not match:
            logger.warning(f"Field {field_name} not found in output")
            return None

        value_str = match.group(1)

        # Convert to requested type
        if field_type is int:
            return int(value_str)
        elif field_type is float:
            return float(value_str)
        elif field_type is str:
            return value_str
        else:
            return field_type(value_str)

    except (ValueError, TypeError) as e:
        logger.error(f"Failed to convert {field_name}={match.group(1) if match else '?'} to {field_type.__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error extracting {field_name}: {e}")
        return None


def extract_queue_stats(
    output: str,
    logger: logging.Logger | None = None
) -> dict | None:
    """Extract queue statistics from RouterOS output.

    Consolidates pattern: extract packets, bytes, dropped, queued-packets, queued-bytes.

    Used by:
    - backends/routeros.py::get_queue_stats()
    - steering/cake_stats.py::read_stats()

    Args:
        output: RouterOS queue stats output
        logger: Logger instance (optional)

    Returns:
        Dict with keys: packets, bytes, dropped, queued_packets, queued_bytes
        Returns empty dict with 0 values if fields not found.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    stats = {
        'packets': 0,
        'bytes': 0,
        'dropped': 0,
        'queued_packets': 0,
        'queued_bytes': 0
    }

    if not output:
        logger.warning("Empty output when extracting queue stats")
        return stats

    try:
        # Extract each stat field
        patterns = {
            'packets': r'packets=(\d+)',
            'bytes': r'(?<!queued-)bytes=(\d+)',  # Don't match queued-bytes
            'dropped': r'dropped=(\d+)',
            'queued_packets': r'queued-packets=(\d+)',
            'queued_bytes': r'queued-bytes=(\d+)'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                stats[key] = int(match.group(1))

        return stats

    except Exception as e:
        logger.error(f"Failed to extract queue stats: {e}")
        return stats


def handle_command_error[T](
    rc: int,
    err: str,
    cmd: str,
    logger: logging.Logger | None = None,
    return_value: T | None = None
) -> CommandResult[T]:
    """Handle command execution error and return a CommandResult.

    Consolidated error handling: logs error and returns typed result.

    Args:
        rc: Return code (0 = success)
        err: Error message from command
        cmd: Command executed (for logging)
        logger: Logger instance (optional)
        return_value: Value to return on failure (ignored on success)

    Returns:
        CommandResult with:
        - On success (rc=0): success=True, value=None, error=None
        - On failure (rc!=0): success=False, value=return_value, error=message

    Example:
        >>> result = handle_command_error(0, "", "get queue")
        >>> result.is_ok()
        True
        >>> result.value is None
        True

        >>> result = handle_command_error(1, "timeout", "set limit", return_value=-1)
        >>> result.is_err()
        True
        >>> result.value
        -1
        >>> result.error
        'Command failed: set limit -> timeout'

        # Backward compatible tuple unpacking still works:
        >>> success, value = handle_command_error(0, "", "cmd")
        >>> success, value
        (True, None)
        >>> success, value = handle_command_error(1, "err", "cmd", return_value=-1)
        >>> success, value
        (False, -1)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if rc == 0:
        return CommandResult.ok(None)  # type: ignore[arg-type]

    error_msg = f"Command failed: {cmd} -> {err}"
    logger.error(error_msg)
    return CommandResult.err(error_msg, return_value)

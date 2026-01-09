"""Router command error handling utilities.

Consolidates common error handling patterns for router command execution,
eliminating duplication across backends and command handlers.

Provides:
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

import logging
import re
from typing import Any, Callable, Optional, Tuple


def check_command_success(
    rc: int,
    cmd: str,
    err: str = "",
    logger: logging.Logger = None,
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
    parse_func: Callable[[str], Optional[Any]],
    logger: logging.Logger = None,
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
    logger: logging.Logger = None
) -> Optional[bool]:
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
    logger: logging.Logger = None
) -> Optional[Any]:
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
        if field_type == int:
            return int(value_str)
        elif field_type == float:
            return float(value_str)
        elif field_type == str:
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
    logger: logging.Logger = None
) -> Optional[dict]:
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


def handle_command_error(
    rc: int,
    err: str,
    cmd: str,
    logger: logging.Logger = None,
    return_value: Any = None
) -> Tuple[bool, Any]:
    """Handle command execution error and return appropriate values.

    Consolidated error handling: logs error and returns (success, value) tuple.

    Args:
        rc: Return code (0 = success)
        err: Error message
        cmd: Command executed (for logging)
        logger: Logger instance (optional)
        return_value: Value to return on failure

    Returns:
        Tuple of (success: bool, value: return_value on failure or None on success)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if rc == 0:
        return (True, None)
    else:
        logger.error(f"Command failed: {cmd} -> {err}")
        return (False, return_value)

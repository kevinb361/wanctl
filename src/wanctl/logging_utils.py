"""Shared logging utilities for CAKE system components."""

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from wanctl.path_utils import ensure_file_directory

# =============================================================================
# JSON STRUCTURED LOGGING
# =============================================================================


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Produces JSON log lines suitable for log aggregation tools like
    Loki, ELK, Splunk, or CloudWatch.

    Fields always included:
        - timestamp: ISO 8601 format with timezone (UTC)
        - level: Log level name (INFO, DEBUG, WARNING, ERROR, CRITICAL)
        - logger: Logger name
        - message: Formatted log message

    Extra fields are automatically included if passed via the `extra`
    parameter to logging calls. Common extras in wanctl:
        - wan_name: WAN identifier (e.g., "spectrum", "att")
        - state: Current state (e.g., "GREEN", "YELLOW", "RED")
        - rtt_delta: RTT delta in milliseconds
        - dl_rate, ul_rate: Bandwidth rates

    Example:
        logger.info("State change", extra={"state": "GREEN", "rtt_delta": 5.2})

        Output:
        {"timestamp":"2026-01-10T12:00:00.000000Z","level":"INFO",
         "logger":"wanctl","message":"State change","state":"GREEN",
         "rtt_delta":5.2}
    """

    # Standard LogRecord attributes to exclude from extra fields
    # These are internal to the logging module and not useful in JSON output
    _EXCLUDE_ATTRS = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields from the record
        # These come from the `extra` parameter in logging calls
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in self._EXCLUDE_ATTRS:
                continue
            # Ensure the value is JSON-serializable
            try:
                json.dumps(value)
                log_data[key] = value
            except (TypeError, ValueError):
                # Convert non-serializable values to strings
                log_data[key] = str(value)

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, separators=(",", ":"))


def get_log_format() -> str:
    """Determine the log format from environment or default.

    Checks the WANCTL_LOG_FORMAT environment variable.
    Valid values: "json", "text"
    Default: "text" (for backward compatibility)

    Returns:
        "json" or "text"
    """
    fmt = os.environ.get("WANCTL_LOG_FORMAT", "text").lower()
    if fmt in ("json", "text"):
        return fmt
    # Invalid value, fall back to text
    return "text"


def _create_formatter(log_format: str, wan_name: str) -> logging.Formatter:
    """Create a formatter based on the specified format.

    Args:
        log_format: Either "json" or "text"
        wan_name: WAN name for text format prefix

    Returns:
        Configured formatter instance
    """
    if log_format == "json":
        return JSONFormatter()
    else:
        return logging.Formatter(f"%(asctime)s [{wan_name}] [%(levelname)s] %(message)s")


def setup_logging(
    config: Any, logger_prefix: str, debug: bool = False, log_format: str | None = None
) -> logging.Logger:
    """Setup logging with rotating file and console output.

    Creates a logger with:
    - INFO-level RotatingFileHandler (main_log, rotated at max_bytes)
    - INFO-level console handler (for systemd journal visibility)
    - DEBUG-level RotatingFileHandler (debug_log, if debug=True)
    - DEBUG-level console handler (if debug=True, upgrades from INFO)

    Log rotation is configured via config.max_bytes (default 10MB) and
    config.backup_count (default 3). Uses getattr() for backward compatibility
    with config objects that lack rotation attributes.

    Log format can be controlled via:
    1. The `log_format` parameter (takes precedence)
    2. The WANCTL_LOG_FORMAT environment variable
    3. Default: "text" (backward compatible)

    Args:
        config: Config object with main_log, debug_log, and optional
                max_bytes/backup_count attributes for log rotation
        logger_prefix: Logger name prefix (e.g., "cake_continuous", "wan_steering")
        debug: Enable debug logging to file and console
        log_format: Log format ("json" or "text"). If None, uses environment
                    variable WANCTL_LOG_FORMAT or defaults to "text".

    Returns:
        Configured logger instance

    Example:
        config = Config('config.yaml')
        logger = setup_logging(config, 'cake_continuous', debug=True)
        logger.info("System started")

        # With JSON logging
        logger = setup_logging(config, 'cake_continuous', log_format='json')
        logger.info("State change", extra={"state": "GREEN", "rtt_delta": 5.2})
    """
    logger = logging.getLogger(f"{logger_prefix}_{config.wan_name.lower()}")

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Determine log format
    effective_format = log_format if log_format else get_log_format()

    # Ensure log directories exist
    for path in (config.main_log, getattr(config, "debug_log", None)):
        if path:
            ensure_file_directory(path, logger=logger)

    # Create formatter based on format selection
    formatter = _create_formatter(effective_format, config.wan_name)

    # Log rotation parameters (backward compatible with getattr defaults)
    max_bytes = getattr(config, "max_bytes", 10_485_760)
    backup_count = getattr(config, "backup_count", 3)

    # Main log - INFO level (rotating to prevent unbounded growth)
    fh = RotatingFileHandler(config.main_log, maxBytes=max_bytes, backupCount=backup_count)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler - always present for journal visibility
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    if debug and hasattr(config, "debug_log"):
        # Debug mode: debug file + DEBUG-level console
        dfh = RotatingFileHandler(
            config.debug_log, maxBytes=max_bytes, backupCount=backup_count
        )
        dfh.setLevel(logging.DEBUG)
        dfh.setFormatter(formatter)
        logger.addHandler(dfh)

        ch.setLevel(logging.DEBUG)
    else:
        # Normal mode: INFO-level console only (for journal)
        ch.setLevel(logging.INFO)

    logger.addHandler(ch)

    return logger

"""Atomic state file utilities for safe concurrent access.

This module provides atomic file operations to prevent race conditions
when multiple processes might read/write state files simultaneously.

Also includes safe JSON parsing helpers that consolidate error handling
patterns used throughout the codebase.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from wanctl.path_utils import ensure_file_directory


def atomic_write_json(file_path: Path, data: dict[str, Any], indent: int = 2) -> None:
    """Atomically write JSON data to a file.

    Uses write-to-temp-then-rename pattern to ensure the file is never
    in a partial/corrupt state. The rename operation is atomic on POSIX
    systems when source and destination are on the same filesystem.

    Args:
        file_path: Path to the target file
        data: Dictionary to serialize as JSON
        indent: JSON indentation level (default: 2)

    Raises:
        OSError: If the write or rename operation fails
        TypeError: If data is not JSON-serializable
    """
    # Ensure parent directory exists
    ensure_file_directory(file_path)

    # Write to temporary file in the same directory (ensures same filesystem)
    # Using delete=False so we can rename it
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=file_path.name + ".", dir=file_path.parent
    )

    # Set restrictive permissions immediately (before writing sensitive data)
    # This prevents potential exposure via world-readable umask defaults
    os.chmod(tmp_path, 0o600)

    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk

        # Atomic rename (POSIX guarantees this is atomic on same filesystem)
        os.replace(tmp_path, file_path)

    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def safe_read_json(file_path: Path, default: dict[str, Any] = None) -> dict[str, Any]:
    """Safely read JSON data from a file.

    Handles missing files and JSON decode errors gracefully.

    Args:
        file_path: Path to the JSON file
        default: Default value to return if file doesn't exist or is invalid

    Returns:
        Parsed JSON data or default value
    """
    if default is None:
        default = {}

    if not file_path.exists():
        return default

    try:
        with open(file_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def safe_json_loads(
    text: str,
    logger: logging.Logger | None = None,
    default: Any | None = None,
    error_context: str = "JSON parsing",
    log_content_preview: bool = False,
    preview_length: int = 200,
) -> Any | None:
    """Safely parse JSON from a string with error logging.

    Args:
        text: JSON string to parse
        logger: Optional logger instance for error messages
        default: Value to return if parsing fails (default: None)
        error_context: Description for error message (e.g., "CAKE stats JSON")
        log_content_preview: If True, logs first N chars of invalid JSON at DEBUG
        preview_length: Number of characters to log from invalid JSON

    Returns:
        Parsed JSON data or default value if parsing fails
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if logger:
            logger.error(f"Failed to parse {error_context} JSON: {e}")
            if log_content_preview and text:
                preview = text[:preview_length]
                if len(text) > preview_length:
                    preview += "..."
                logger.debug(f"Invalid JSON content: {preview}")
        return default
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error parsing {error_context} JSON: {e}")
        return default


def safe_json_load_file(
    file_path: Path,
    logger: logging.Logger | None = None,
    default: Any | None = None,
    error_context: str = "JSON file",
) -> Any | None:
    """Safely read and parse JSON from a file with error logging.

    Consolidates repetitive try/except/log pattern for json.load() calls
    used in steering/daemon.py and autorate_continuous.py.

    Args:
        file_path: Path to the JSON file
        logger: Optional logger instance for error messages
        default: Value to return if file doesn't exist or parsing fails
        error_context: Description for error message (e.g., "state file")

    Returns:
        Parsed JSON data or default value if operation fails

    Examples:
        >>> data = safe_json_load_file(Path('state.json'))
        >>> data = safe_json_load_file(
        ...     Path('state.json'),
        ...     logger=logger,
        ...     default={},
        ...     error_context="steering state"
        ... )
    """
    if not file_path.exists():
        return default

    try:
        with open(file_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        if logger:
            logger.error(f"Failed to parse {error_context} JSON from {file_path}: {e}")
        return default
    except OSError as e:
        if logger:
            logger.error(f"Failed to read {error_context} file {file_path}: {e}")
        return default
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error reading {error_context} from {file_path}: {e}")
        return default

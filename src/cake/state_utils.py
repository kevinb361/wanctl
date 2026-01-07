"""Atomic state file utilities for safe concurrent access.

This module provides atomic file operations to prevent race conditions
when multiple processes might read/write state files simultaneously.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


def atomic_write_json(file_path: Path, data: Dict[str, Any], indent: int = 2) -> None:
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
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file in the same directory (ensures same filesystem)
    # Using delete=False so we can rename it
    fd, tmp_path = tempfile.mkstemp(
        suffix='.tmp',
        prefix=file_path.name + '.',
        dir=file_path.parent
    )

    # Set restrictive permissions immediately (before writing sensitive data)
    # This prevents potential exposure via world-readable umask defaults
    os.chmod(tmp_path, 0o600)

    try:
        with os.fdopen(fd, 'w') as f:
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


def safe_read_json(file_path: Path, default: Dict[str, Any] = None) -> Dict[str, Any]:
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
        with open(file_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default

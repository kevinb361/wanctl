"""Path and file system utilities for wanctl.

Consolidates common path handling patterns:
- Safe directory creation with error handling
- Path normalization and validation
- File existence checks with proper error messages
"""

import logging
from pathlib import Path
from typing import Optional, Union


def ensure_directory_exists(
    path: Union[str, Path],
    logger: Optional[logging.Logger] = None,
    mode: int = 0o755
) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Creates parent directories as needed with proper error handling.

    Args:
        path: Path to directory (str or Path object)
        logger: Optional logger for debug/error messages
        mode: Directory permissions (default: 0o755)

    Returns:
        Path object for the directory

    Raises:
        OSError: If directory cannot be created
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    path_obj = Path(path)

    # If directory already exists, just return it
    if path_obj.exists():
        return path_obj

    # Create the directory with all parents
    try:
        path_obj.mkdir(parents=True, exist_ok=True, mode=mode)
        logger.debug(f"Created directory: {path_obj}")
    except OSError as e:
        logger.error(f"Failed to create directory {path_obj}: {e}")
        raise

    return path_obj


def ensure_file_directory(
    file_path: Union[str, Path],
    logger: Optional[logging.Logger] = None,
    mode: int = 0o755
) -> Path:
    """Ensure the directory containing a file exists.

    Creates parent directories of a file path if necessary.

    Args:
        file_path: Path to file
        logger: Optional logger for debug/error messages
        mode: Directory permissions (default: 0o755)

    Returns:
        Path object for the directory

    Raises:
        OSError: If directory cannot be created
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    path_obj = Path(file_path)
    return ensure_directory_exists(path_obj.parent, logger=logger, mode=mode)


def safe_file_path(
    file_path: Union[str, Path],
    create_parent: bool = False,
    logger: Optional[logging.Logger] = None
) -> Path:
    """Validate and optionally prepare a file path for use.

    Args:
        file_path: Path to file
        create_parent: If True, create parent directory if it doesn't exist
        logger: Optional logger for debug/error messages

    Returns:
        Validated Path object

    Raises:
        OSError: If parent directory cannot be created (if create_parent=True)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    path_obj = Path(file_path)

    if create_parent:
        ensure_file_directory(path_obj, logger=logger)
        logger.debug(f"File path ready: {path_obj}")

    return path_obj

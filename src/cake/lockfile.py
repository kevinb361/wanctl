"""Lock file management for preventing concurrent execution.

This module provides a context manager for acquiring and releasing lock files,
ensuring only one instance of a script runs at a time.
"""

import sys
import time
import logging
from pathlib import Path


class LockFile:
    """Context manager for lock file to prevent concurrent execution.

    Acquires a lock file on entry and releases it on exit. If a recent lock
    file exists (age < timeout), exits the process to prevent concurrent runs.
    Stale lock files (age >= timeout) are automatically cleaned up.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum age (seconds) before lock is considered stale
        logger: Logger instance for debug/warning messages

    Example:
        with LockFile(Path("/tmp/myapp.lock"), timeout=300, logger=logger):
            # Critical section - only one instance runs
            do_work()
    """

    def __init__(self, lock_path: Path, timeout: int, logger: logging.Logger):
        self.lock_path = lock_path
        self.timeout = timeout
        self.logger = logger

    def __enter__(self):
        if self.lock_path.exists():
            age = time.time() - self.lock_path.stat().st_mtime
            if age < self.timeout:
                self.logger.warning(
                    f"Lock file exists and is recent ({age:.1f}s old). "
                    "Another instance may be running. Exiting."
                )
                sys.exit(0)
            else:
                self.logger.warning(
                    f"Stale lock file found ({age:.1f}s old). Removing."
                )
                self.lock_path.unlink()

        self.lock_path.touch()
        self.logger.debug(f"Lock acquired: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_path.exists():
            self.lock_path.unlink()
            self.logger.debug(f"Lock released: {self.lock_path}")

"""Lock file management for preventing concurrent execution.

This module provides a context manager for acquiring and releasing lock files,
ensuring only one instance of a script runs at a time.
"""

import errno
import os
import time
import logging
from pathlib import Path
from typing import Optional


class LockAcquisitionError(Exception):
    """Raised when a lock file cannot be acquired due to an existing lock.

    This exception indicates another instance is likely running and the caller
    should exit gracefully rather than proceeding with duplicate execution.

    Attributes:
        lock_path: Path to the lock file that couldn't be acquired
        age: Age of the existing lock file in seconds
    """

    def __init__(self, lock_path: Path, age: float):
        self.lock_path = lock_path
        self.age = age
        super().__init__(
            f"Lock file {lock_path} exists and is recent ({age:.1f}s old). "
            "Another instance may be running."
        )


class LockFile:
    """Context manager for lock file to prevent concurrent execution.

    Acquires a lock file on entry and releases it on exit. If a recent lock
    file exists (age < timeout), raises LockAcquisitionError.
    Stale lock files (age >= timeout) are automatically cleaned up.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum age (seconds) before lock is considered stale
        logger: Logger instance for debug/warning messages

    Raises:
        LockAcquisitionError: If a recent lock file exists (another instance running)

    Example:
        try:
            with LockFile(Path("/tmp/myapp.lock"), timeout=300, logger=logger):
                # Critical section - only one instance runs
                do_work()
        except LockAcquisitionError:
            # Another instance is running, exit gracefully
            return 0
    """

    def __init__(self, lock_path: Path, timeout: int, logger: logging.Logger):
        self.lock_path = lock_path
        self.timeout = timeout
        self.logger = logger

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        """Check if process with given PID is alive.

        Uses os.kill(pid, 0) to check existence without sending signal.
        Handles PID reuse by checking process state if /proc is available.

        Args:
            pid: Process ID to check

        Returns:
            True if process exists and is likely alive
            False if process is definitely dead
        """
        if pid <= 0:
            return False

        try:
            os.kill(pid, 0)
        except OSError as e:
            if e.errno == errno.ESRCH:
                # No such process - definitely dead
                return False
            elif e.errno == errno.EPERM:
                # Permission denied - process exists but not ours (conservative)
                return True
            else:
                # Unexpected error - conservative: treat as alive
                return True

        # os.kill succeeded - process exists
        # Additional check: is it a zombie?
        try:
            with open(f'/proc/{pid}/stat', 'r') as f:
                stat = f.read()
                # Third field is state: Z = zombie
                if ') Z ' in stat or stat.endswith(' Z'):
                    return False  # Zombie - treat as dead
        except (FileNotFoundError, PermissionError, OSError):
            # /proc not available or not accessible - can't determine
            pass

        return True

    def _read_lock_pid(self) -> Optional[int]:
        """Read PID from lock file.

        Returns:
            PID as integer, or None if file doesn't exist or invalid format
        """
        try:
            content = self.lock_path.read_text().strip()
            return int(content)
        except (FileNotFoundError, ValueError, OSError):
            return None

    def __enter__(self):
        # Atomic lock acquisition using O_EXCL to prevent race conditions.
        # O_EXCL fails if file exists, making check-and-create atomic.
        try:
            fd = os.open(
                str(self.lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644
            )
            # Write current PID to lock file
            pid_bytes = f"{os.getpid()}\n".encode('utf-8')
            os.write(fd, pid_bytes)
            os.close(fd)
            self.logger.debug(f"Lock acquired: {self.lock_path} (PID {os.getpid()})")
            return self
        except FileExistsError:
            # Lock file exists - check if holder is still alive
            try:
                existing_pid = self._read_lock_pid()

                if existing_pid is None:
                    # Legacy lock (no PID) - fall back to time-based check
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age < self.timeout:
                        self.logger.warning(
                            f"Lock file exists with no PID (age {age:.1f}s). "
                            "Assuming recent - another instance may be running."
                        )
                        raise LockAcquisitionError(self.lock_path, age)
                    else:
                        self.logger.warning(
                            f"Stale lock file with no PID (age {age:.1f}s). Removing."
                        )
                        self.lock_path.unlink()
                        return self.__enter__()  # Retry

                # PID found - check if process is alive
                if self._is_process_alive(existing_pid):
                    age = time.time() - self.lock_path.stat().st_mtime
                    self.logger.warning(
                        f"Lock file exists and holder (PID {existing_pid}) is alive "
                        f"(age {age:.1f}s). Another instance is running."
                    )
                    raise LockAcquisitionError(self.lock_path, age)
                else:
                    # Process is dead - safe to remove lock
                    age = time.time() - self.lock_path.stat().st_mtime
                    self.logger.warning(
                        f"Stale lock file from dead process (PID {existing_pid}, age {age:.1f}s). Removing."
                    )
                    self.lock_path.unlink()
                    return self.__enter__()  # Retry

            except FileNotFoundError:
                # Lock was removed between check and stat - retry
                return self.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_path.exists():
            self.lock_path.unlink()
            self.logger.debug(f"Lock released: {self.lock_path}")

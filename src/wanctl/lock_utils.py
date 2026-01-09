"""Unified lock file validation and acquisition utilities.

Consolidates PID-based lock validation logic used in both lockfile.py and
autorate_continuous.py. Provides reusable functions for checking process liveness,
reading lock file PIDs, and validating/acquiring locks with stale lock cleanup.
"""

import errno
import os
import time
import logging
from pathlib import Path
from typing import Optional


def is_process_alive(pid: int) -> bool:
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


def read_lock_pid(lock_path: Path) -> Optional[int]:
    """Read PID from lock file.

    Args:
        lock_path: Path to the lock file

    Returns:
        PID as integer, or None if file doesn't exist or invalid format
    """
    try:
        content = lock_path.read_text().strip()
        return int(content)
    except (FileNotFoundError, ValueError, OSError):
        return None


def validate_lock(lock_path: Path, timeout: int, logger: logging.Logger) -> bool:
    """Validate existing lock file and determine if it's safe to proceed.

    Checks if a lock file exists and whether its holder is still alive.
    Removes stale locks from dead processes.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum age (seconds) before lock is considered stale
        logger: Logger instance for messages

    Returns:
        True if lock is stale and was removed (safe to continue)
        False if lock is held by alive process (must exit)

    Raises:
        RuntimeError: If lock validation fails unexpectedly
    """
    if not lock_path.exists():
        return True  # No lock exists, safe to continue

    try:
        existing_pid = read_lock_pid(lock_path)

        if existing_pid is None:
            # Legacy lock (no PID) - fall back to time-based check
            age = time.time() - lock_path.stat().st_mtime
            if age < timeout:
                logger.warning(
                    f"Lock file exists with no PID (age {age:.1f}s). "
                    "Assuming recent - another instance may be running."
                )
                return False  # Lock is recent, must exit
            else:
                logger.info(f"Removing stale lock file (age {age:.1f}s): {lock_path}")
                lock_path.unlink()
                return True  # Stale lock removed, safe to continue

        # PID found - check if process is alive
        if is_process_alive(existing_pid):
            age = time.time() - lock_path.stat().st_mtime
            logger.error(
                f"Lock file exists and holder (PID {existing_pid}) is alive "
                f"(age {age:.1f}s). Another instance is running: {lock_path}"
            )
            return False  # Lock holder is alive, must exit

        # Process is dead - safe to remove lock
        age = time.time() - lock_path.stat().st_mtime
        logger.info(
            f"Removing stale lock from dead process "
            f"(PID {existing_pid}, age {age:.1f}s): {lock_path}"
        )
        lock_path.unlink()
        return True  # Stale lock removed, safe to continue

    except FileNotFoundError:
        # Lock was removed between check and read - race condition, safe to continue
        return True
    except Exception as e:
        logger.warning(f"Unexpected error validating lock {lock_path}: {e}")
        raise RuntimeError(f"Failed to validate lock {lock_path}: {e}")


def acquire_lock(lock_path: Path, logger: logging.Logger) -> bool:
    """Acquire a lock file with atomic O_EXCL creation.

    Uses O_EXCL flag for atomic creation - fails if file exists.
    Writes current process PID to lock file for validation.

    Args:
        lock_path: Path to the lock file
        logger: Logger instance for messages

    Returns:
        True if lock was successfully acquired
        False if lock already exists (race condition)

    Raises:
        OSError: If file creation fails for reasons other than FileExistsError
    """
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        pid_bytes = f"{os.getpid()}\n".encode('utf-8')
        os.write(fd, pid_bytes)
        os.close(fd)
        logger.debug(f"Lock acquired: {lock_path} (PID {os.getpid()})")
        return True
    except FileExistsError:
        # Race condition - another process created lock between our check and creation
        logger.warning(f"Failed to acquire lock (race condition): {lock_path}")
        return False


def validate_and_acquire_lock(lock_path: Path, timeout: int, logger: logging.Logger) -> bool:
    """Validate existing lock and acquire new lock if safe to do so.

    Checks for existing lock (removes stale locks), then attempts to acquire
    new lock. Handles race conditions gracefully.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum age (seconds) before lock is considered stale
        logger: Logger instance for messages

    Returns:
        True if lock was successfully acquired
        False if lock is held by another instance (must exit)

    Raises:
        RuntimeError: If validation or acquisition fails unexpectedly
    """
    # First validate - checks for existing lock and removes stale ones
    if not validate_lock(lock_path, timeout, logger):
        return False  # Existing lock held by alive process

    # Validation passed - acquire new lock
    if not acquire_lock(lock_path, logger):
        # Race condition - try validation again in case another instance started
        if not validate_lock(lock_path, timeout, logger):
            return False
        # If validation passed, something else went wrong
        raise RuntimeError(f"Failed to acquire lock after validation: {lock_path}")

    return True

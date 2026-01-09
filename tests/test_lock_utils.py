"""Unit tests for lock_utils module."""

import os
import tempfile
import logging
import time
from pathlib import Path
import pytest

from wanctl.lock_utils import (
    is_process_alive,
    read_lock_pid,
    validate_lock,
    acquire_lock,
    validate_and_acquire_lock,
)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_lock_utils")


@pytest.fixture
def temp_lock():
    """Provide a temporary lock file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "test.lock"
        yield lock_path


class TestIsProcessAlive:
    """Tests for is_process_alive function."""

    def test_current_process_is_alive(self):
        """Test that current process is detected as alive."""
        assert is_process_alive(os.getpid()) is True

    def test_invalid_pid_is_dead(self):
        """Test that invalid PIDs are detected as dead."""
        assert is_process_alive(-1) is False
        assert is_process_alive(0) is False

    def test_nonexistent_pid_is_dead(self):
        """Test that nonexistent PID is detected as dead."""
        # Use a very high PID that's unlikely to exist
        assert is_process_alive(999999) is False


class TestReadLockPid:
    """Tests for read_lock_pid function."""

    def test_read_valid_pid(self, temp_lock):
        """Test reading valid PID from lock file."""
        temp_lock.write_text(f"{os.getpid()}\n")
        pid = read_lock_pid(temp_lock)
        assert pid == os.getpid()

    def test_read_nonexistent_file(self, temp_lock):
        """Test reading from nonexistent file returns None."""
        pid = read_lock_pid(temp_lock)
        assert pid is None

    def test_read_invalid_pid_format(self, temp_lock):
        """Test reading invalid PID format returns None."""
        temp_lock.write_text("not_a_number\n")
        pid = read_lock_pid(temp_lock)
        assert pid is None

    def test_read_pid_with_whitespace(self, temp_lock):
        """Test reading PID with surrounding whitespace."""
        temp_lock.write_text(f"  {os.getpid()}  \n")
        pid = read_lock_pid(temp_lock)
        assert pid == os.getpid()


class TestValidateLock:
    """Tests for validate_lock function."""

    def test_no_lock_file_returns_true(self, temp_lock, logger):
        """Test that no lock file means safe to proceed."""
        result = validate_lock(temp_lock, timeout=300, logger=logger)
        assert result is True

    def test_recent_lock_with_dead_pid_returns_true(self, temp_lock, logger):
        """Test that recent lock with dead PID is removed."""
        # Use a PID that's definitely not alive
        dead_pid = 999999
        temp_lock.write_text(f"{dead_pid}\n")
        # Make it look recent (current time)
        os.utime(str(temp_lock), None)

        result = validate_lock(temp_lock, timeout=300, logger=logger)
        assert result is True
        assert not temp_lock.exists()  # Lock was removed

    def test_current_process_lock_returns_false(self, temp_lock, logger):
        """Test that lock held by current process returns False."""
        temp_lock.write_text(f"{os.getpid()}\n")
        os.utime(str(temp_lock), None)

        result = validate_lock(temp_lock, timeout=300, logger=logger)
        assert result is False
        assert temp_lock.exists()  # Lock was NOT removed

    def test_old_lock_no_pid_returns_true(self, temp_lock, logger):
        """Test that old lock file with no valid PID is removed."""
        temp_lock.write_text("invalid_pid\n")
        # Make it look old (older than timeout)
        old_time = time.time() - 400
        os.utime(str(temp_lock), (old_time, old_time))

        result = validate_lock(temp_lock, timeout=300, logger=logger)
        assert result is True
        assert not temp_lock.exists()  # Lock was removed

    def test_recent_lock_no_pid_returns_false(self, temp_lock, logger):
        """Test that recent lock file with no valid PID means cannot proceed."""
        temp_lock.write_text("no_pid\n")
        # Make it look recent
        os.utime(str(temp_lock), None)

        result = validate_lock(temp_lock, timeout=300, logger=logger)
        assert result is False
        assert temp_lock.exists()  # Lock was NOT removed


class TestAcquireLock:
    """Tests for acquire_lock function."""

    def test_acquire_new_lock_succeeds(self, temp_lock, logger):
        """Test acquiring a new lock succeeds."""
        result = acquire_lock(temp_lock, logger)
        assert result is True
        assert temp_lock.exists()

        # Verify PID was written correctly
        pid = read_lock_pid(temp_lock)
        assert pid == os.getpid()

    def test_acquire_existing_lock_fails(self, temp_lock, logger):
        """Test acquiring lock when file exists returns False."""
        # Create lock file first
        temp_lock.write_text(f"{os.getpid()}\n")

        # Try to acquire - should fail
        result = acquire_lock(temp_lock, logger)
        assert result is False

    def test_lock_has_correct_permissions(self, temp_lock, logger):
        """Test that acquired lock has correct permissions."""
        acquire_lock(temp_lock, logger)
        # Check that file has restricted permissions (0o644)
        stat_info = temp_lock.stat()
        perms = stat_info.st_mode & 0o777
        assert perms == 0o644


class TestValidateAndAcquireLock:
    """Tests for validate_and_acquire_lock function."""

    def test_acquire_new_lock_succeeds(self, temp_lock, logger):
        """Test acquiring new lock when no existing lock."""
        result = validate_and_acquire_lock(temp_lock, timeout=300, logger=logger)
        assert result is True
        assert temp_lock.exists()
        pid = read_lock_pid(temp_lock)
        assert pid == os.getpid()

    def test_remove_stale_lock_and_acquire_new(self, temp_lock, logger):
        """Test removing stale lock and acquiring new one."""
        # Create old lock from dead process
        dead_pid = 999999
        temp_lock.write_text(f"{dead_pid}\n")
        old_time = time.time() - 400
        os.utime(str(temp_lock), (old_time, old_time))

        result = validate_and_acquire_lock(temp_lock, timeout=300, logger=logger)
        assert result is True
        # New lock should be acquired
        pid = read_lock_pid(temp_lock)
        assert pid == os.getpid()

    def test_current_process_lock_returns_false(self, temp_lock, logger):
        """Test that lock held by current process prevents acquisition."""
        # Write current PID to lock file
        temp_lock.write_text(f"{os.getpid()}\n")
        os.utime(str(temp_lock), None)

        result = validate_and_acquire_lock(temp_lock, timeout=300, logger=logger)
        assert result is False

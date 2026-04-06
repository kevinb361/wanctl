"""Unit tests for lock_utils module."""

import logging
import os
import tempfile
import time
from pathlib import Path

import pytest

from wanctl.lock_utils import (
    LockAcquisitionError,
    LockFile,
    acquire_lock,
    is_process_alive,
    read_lock_pid,
    validate_and_acquire_lock,
    validate_lock,
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


# =============================================================================
# MERGED FROM test_lockfile.py
# =============================================================================


class TestLockAcquisitionError:
    """Tests for LockAcquisitionError exception."""

    def test_exception_attributes(self):
        """Test exception stores lock_path and age."""
        lock_path = Path("/tmp/test.lock")
        age = 123.45

        error = LockAcquisitionError(lock_path, age)

        assert error.lock_path == lock_path
        assert error.age == age

    def test_exception_message(self):
        """Test exception message format."""
        lock_path = Path("/tmp/test.lock")
        age = 50.5

        error = LockAcquisitionError(lock_path, age)

        assert str(lock_path) in str(error)
        assert "50.5" in str(error)
        assert "Another instance may be running" in str(error)


class TestLockFile:
    """Tests for LockFile context manager."""

    def test_acquires_lock_when_no_existing(self, temp_dir, logger):
        """Test lock is acquired when no existing lock file."""
        lock_path = temp_dir / "test.lock"

        with LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()

    def test_releases_lock_on_exit(self, temp_dir, logger):
        """Test lock file is removed on context exit."""
        lock_path = temp_dir / "test.lock"

        with LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()

        assert not lock_path.exists()

    def test_releases_lock_on_exception(self, temp_dir, logger):
        """Test lock file is removed even if exception occurs."""
        lock_path = temp_dir / "test.lock"

        with pytest.raises(ValueError), LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()
            raise ValueError("Test exception")

        assert not lock_path.exists()

    def test_raises_on_recent_lock(self, temp_dir, logger):
        """Test raises LockAcquisitionError when recent lock exists."""
        lock_path = temp_dir / "test.lock"

        # Create existing lock file
        lock_path.touch()

        with pytest.raises(LockAcquisitionError) as exc_info:
            with LockFile(lock_path, timeout=300, logger=logger):
                pass

        assert exc_info.value.lock_path == lock_path
        assert exc_info.value.age < 1.0  # Should be very recent

    def test_removes_stale_lock(self, temp_dir, logger):
        """Test stale lock file is removed and new lock acquired."""
        lock_path = temp_dir / "test.lock"

        # Create lock file with old modification time
        lock_path.touch()
        old_time = time.time() - 400  # 400 seconds ago
        import os

        os.utime(lock_path, (old_time, old_time))

        # Should succeed - stale lock removed
        with LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()

        assert not lock_path.exists()

    def test_timeout_boundary_recent(self, temp_dir, logger):
        """Test lock just under timeout is considered recent."""
        lock_path = temp_dir / "test.lock"
        timeout = 10

        # Create lock file just under timeout
        lock_path.touch()
        recent_time = time.time() - (timeout - 1)  # 1 second under timeout
        import os

        os.utime(lock_path, (recent_time, recent_time))

        with pytest.raises(LockAcquisitionError):
            with LockFile(lock_path, timeout=timeout, logger=logger):
                pass

    def test_timeout_boundary_stale(self, temp_dir, logger):
        """Test lock at timeout boundary is considered stale."""
        lock_path = temp_dir / "test.lock"
        timeout = 10

        # Create lock file at exactly timeout + a bit
        lock_path.touch()
        stale_time = time.time() - (timeout + 1)  # 1 second over timeout
        import os

        os.utime(lock_path, (stale_time, stale_time))

        # Should succeed - lock is stale
        with LockFile(lock_path, timeout=timeout, logger=logger):
            assert lock_path.exists()

    def test_context_manager_returns_self(self, temp_dir, logger):
        """Test context manager returns the LockFile instance."""
        lock_path = temp_dir / "test.lock"

        with LockFile(lock_path, timeout=300, logger=logger) as lock:
            assert isinstance(lock, LockFile)
            assert lock.lock_path == lock_path

    def test_creates_parent_directory_not_required(self, temp_dir, logger):
        """Test that parent directory must exist (touch doesn't create dirs)."""
        lock_path = temp_dir / "nonexistent" / "test.lock"

        # This should raise because parent dir doesn't exist
        with pytest.raises(FileNotFoundError):
            with LockFile(lock_path, timeout=300, logger=logger):
                pass

    def test_sequential_locks_work(self, temp_dir, logger):
        """Test that sequential lock acquisitions work correctly."""
        lock_path = temp_dir / "test.lock"

        # First lock
        with LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()

        assert not lock_path.exists()

        # Second lock (should work after first is released)
        with LockFile(lock_path, timeout=300, logger=logger):
            assert lock_path.exists()

        assert not lock_path.exists()


class TestLockFileIntegration:
    """Integration tests for lock file behavior."""

    def test_exception_in_lock_context_preserves_info(self, temp_dir, logger):
        """Test that exceptions inside lock context are preserved."""
        lock_path = temp_dir / "test.lock"

        class CustomError(Exception):
            pass

        with pytest.raises(CustomError) as exc_info:
            with LockFile(lock_path, timeout=300, logger=logger):
                raise CustomError("Original error message")

        assert "Original error message" in str(exc_info.value)
        # Lock should still be released
        assert not lock_path.exists()


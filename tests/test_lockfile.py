"""Tests for LockFile class in lock_utils module - lock file management."""

import logging
import time
from pathlib import Path

import pytest

from wanctl.lock_utils import LockAcquisitionError, LockFile


@pytest.fixture
def logger():
    """Create a logger for testing."""
    return logging.getLogger("test_lockfile")


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

        with pytest.raises(ValueError):
            with LockFile(lock_path, timeout=300, logger=logger):
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

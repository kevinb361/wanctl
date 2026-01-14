"""Unit tests for path utilities."""

import logging
import tempfile
from pathlib import Path

import pytest

from wanctl.path_utils import (
    ensure_directory_exists,
    ensure_file_directory,
    safe_file_path,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_path_utils")


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function."""

    def test_creates_single_level_directory(self, temp_dir, logger):
        """Test creating a single-level directory."""
        new_dir = temp_dir / "new_directory"
        assert not new_dir.exists()

        result = ensure_directory_exists(new_dir, logger=logger)

        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_creates_nested_directories(self, temp_dir, logger):
        """Test creating nested directories."""
        nested_dir = temp_dir / "level1" / "level2" / "level3"
        assert not nested_dir.exists()

        result = ensure_directory_exists(nested_dir, logger=logger)

        assert nested_dir.exists()
        assert nested_dir.is_dir()
        assert result == nested_dir

    def test_returns_path_object(self, temp_dir, logger):
        """Test that return value is a Path object."""
        result = ensure_directory_exists(temp_dir / "test", logger=logger)
        assert isinstance(result, Path)

    def test_string_path_input(self, temp_dir, logger):
        """Test that string paths are accepted."""
        str_path = str(temp_dir / "test")
        result = ensure_directory_exists(str_path, logger=logger)
        assert isinstance(result, Path)
        assert Path(str_path).exists()

    def test_existing_directory_is_idempotent(self, temp_dir, logger):
        """Test that calling on existing directory is safe."""
        result = ensure_directory_exists(temp_dir, logger=logger)
        assert result == temp_dir
        assert temp_dir.exists()

    def test_empty_path_returns_path_object(self, logger):
        """Test handling of empty/root-like paths."""
        # Empty or just filename should handle gracefully
        result = ensure_directory_exists("", logger=logger)
        assert isinstance(result, Path)

    def test_custom_mode_respected(self, temp_dir, logger):
        """Test that custom directory mode is set."""
        new_dir = temp_dir / "custom_mode"
        ensure_directory_exists(new_dir, logger=logger, mode=0o700)

        # Check permissions (mode 0o700 = rwx------)
        stat_info = new_dir.stat()
        # Extract permission bits
        perms = stat_info.st_mode & 0o777
        assert perms == 0o700

    def test_returns_same_path_on_second_call(self, temp_dir, logger):
        """Test idempotent behavior on repeated calls."""
        path = temp_dir / "test_dir"
        result1 = ensure_directory_exists(path, logger=logger)
        result2 = ensure_directory_exists(path, logger=logger)
        assert result1 == result2


class TestEnsureFileDirectory:
    """Tests for ensure_file_directory function."""

    def test_creates_parent_directory(self, temp_dir, logger):
        """Test creating parent directory for a file."""
        file_path = temp_dir / "subdir" / "file.txt"
        parent = file_path.parent

        assert not parent.exists()

        result = ensure_file_directory(file_path, logger=logger)

        assert parent.exists()
        assert result == parent

    def test_handles_deeply_nested_file(self, temp_dir, logger):
        """Test creating deep parent directories."""
        file_path = temp_dir / "a" / "b" / "c" / "d" / "file.txt"
        parent = file_path.parent

        result = ensure_file_directory(file_path, logger=logger)

        assert parent.exists()
        assert result == parent

    def test_returns_parent_path(self, temp_dir, logger):
        """Test that function returns parent directory path."""
        file_path = temp_dir / "subdir" / "file.txt"
        result = ensure_file_directory(file_path, logger=logger)
        assert result == file_path.parent

    def test_string_path_input(self, temp_dir, logger):
        """Test with string path input."""
        file_path = str(temp_dir / "subdir" / "file.txt")
        result = ensure_file_directory(file_path, logger=logger)
        assert result.exists()
        assert Path(file_path).parent.exists()

    def test_idempotent_on_existing_parent(self, temp_dir, logger):
        """Test that calling on existing parent directory is safe."""
        existing_file = temp_dir / "file.txt"
        existing_file.write_text("test")

        result = ensure_file_directory(existing_file, logger=logger)

        assert result == temp_dir
        assert existing_file.read_text() == "test"  # File unchanged


class TestSafeFilePath:
    """Tests for safe_file_path function."""

    def test_returns_path_object(self, temp_dir, logger):
        """Test that return value is a Path object."""
        file_path = temp_dir / "file.txt"
        result = safe_file_path(file_path, logger=logger)
        assert isinstance(result, Path)

    def test_without_create_parent_no_creation(self, temp_dir, logger):
        """Test that directories are not created when create_parent=False."""
        file_path = temp_dir / "new_dir" / "file.txt"
        result = safe_file_path(file_path, create_parent=False, logger=logger)

        assert result == file_path
        assert not file_path.parent.exists()

    def test_with_create_parent_creates_directory(self, temp_dir, logger):
        """Test that directories are created when create_parent=True."""
        file_path = temp_dir / "new_dir" / "file.txt"
        result = safe_file_path(file_path, create_parent=True, logger=logger)

        assert result == file_path
        assert file_path.parent.exists()

    def test_string_path_input(self, temp_dir, logger):
        """Test with string path input."""
        str_path = str(temp_dir / "subdir" / "file.txt")
        result = safe_file_path(str_path, create_parent=True, logger=logger)
        assert isinstance(result, Path)
        assert Path(str_path).parent.exists()

    def test_existing_file_path_unchanged(self, temp_dir, logger):
        """Test that existing file paths are not modified."""
        existing_file = temp_dir / "file.txt"
        existing_file.write_text("content")

        result = safe_file_path(existing_file, create_parent=False, logger=logger)

        assert result == existing_file
        assert existing_file.read_text() == "content"

    def test_deep_nesting_with_create_parent(self, temp_dir, logger):
        """Test creating deep nested directory structure."""
        deep_path = temp_dir / "a" / "b" / "c" / "d" / "e" / "file.txt"
        result = safe_file_path(deep_path, create_parent=True, logger=logger)

        assert deep_path.parent.exists()
        assert result == deep_path


class TestPathUtilsIntegration:
    """Integration tests for path utilities."""

    def test_create_and_write_file(self, temp_dir, logger):
        """Test creating directories and writing a file."""
        file_path = temp_dir / "logs" / "subdir" / "output.log"

        # Ensure parent directory exists
        ensure_file_directory(file_path, logger=logger)

        # Write file
        file_path.write_text("test log content")

        assert file_path.exists()
        assert file_path.read_text() == "test log content"

    def test_multiple_files_same_directory(self, temp_dir, logger):
        """Test creating multiple files in same directory."""
        dir_path = temp_dir / "multi_files" / "subdir"
        file1 = dir_path / "file1.txt"
        file2 = dir_path / "file2.txt"

        ensure_file_directory(file1, logger=logger)
        ensure_file_directory(file2, logger=logger)

        file1.write_text("content1")
        file2.write_text("content2")

        assert file1.read_text() == "content1"
        assert file2.read_text() == "content2"

    def test_safe_file_path_workflow(self, temp_dir, logger):
        """Test typical workflow using safe_file_path."""
        log_file = safe_file_path(temp_dir / "logs" / "app.log", create_parent=True, logger=logger)

        log_file.write_text("application started")
        assert log_file.exists()

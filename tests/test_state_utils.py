"""Tests for state_utils module - atomic file operations."""

import json
from pathlib import Path

import pytest

from wanctl.state_utils import atomic_write_json, safe_read_json


class TestAtomicWriteJson:
    """Tests for atomic_write_json function."""

    def test_basic_write(self, temp_dir):
        """Test basic JSON write operation."""
        file_path = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        atomic_write_json(file_path, data)

        assert file_path.exists()
        with open(file_path) as f:
            result = json.load(f)
        assert result == data

    def test_creates_parent_directories(self, temp_dir):
        """Test that parent directories are created if they don't exist."""
        file_path = temp_dir / "subdir" / "deep" / "test.json"
        data = {"key": "value"}

        atomic_write_json(file_path, data)

        assert file_path.exists()
        with open(file_path) as f:
            result = json.load(f)
        assert result == data

    def test_overwrites_existing_file(self, temp_dir):
        """Test that existing file is overwritten."""
        file_path = temp_dir / "test.json"

        # Write initial data
        atomic_write_json(file_path, {"old": "data"})

        # Overwrite with new data
        new_data = {"new": "data", "extra": 123}
        atomic_write_json(file_path, new_data)

        with open(file_path) as f:
            result = json.load(f)
        assert result == new_data

    def test_compact_json_format(self, temp_dir):
        """Test that JSON is written in compact format (no whitespace)."""
        file_path = temp_dir / "test.json"
        data = {"key": "value", "nested": {"inner": 1}}

        atomic_write_json(file_path, data)

        with open(file_path) as f:
            content = f.read()
        # Compact format should have no spaces after colons or commas
        assert content == '{"key":"value","nested":{"inner":1}}'

    def test_no_temp_file_left_on_success(self, temp_dir):
        """Test that no temporary files are left after successful write."""
        file_path = temp_dir / "test.json"
        atomic_write_json(file_path, {"key": "value"})

        # List all files in directory
        files = list(temp_dir.iterdir())
        assert len(files) == 1
        assert files[0].name == "test.json"

    def test_complex_data_structure(self, temp_dir):
        """Test writing complex nested data structures."""
        file_path = temp_dir / "test.json"
        data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"deep": {"value": "found"}},
        }

        atomic_write_json(file_path, data)

        with open(file_path) as f:
            result = json.load(f)
        assert result == data

    def test_non_serializable_data_raises(self, temp_dir):
        """Test that non-JSON-serializable data raises TypeError."""
        file_path = temp_dir / "test.json"
        data = {"function": lambda x: x}  # Functions are not JSON serializable

        with pytest.raises(TypeError):
            atomic_write_json(file_path, data)

        # File should not exist after failed write
        assert not file_path.exists()


class TestSafeReadJson:
    """Tests for safe_read_json function."""

    def test_read_existing_file(self, temp_dir):
        """Test reading an existing JSON file."""
        file_path = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        with open(file_path, "w") as f:
            json.dump(data, f)

        result = safe_read_json(file_path)
        assert result == data

    def test_missing_file_returns_default(self, temp_dir):
        """Test that missing file returns default value."""
        file_path = temp_dir / "nonexistent.json"

        result = safe_read_json(file_path)
        assert result == {}

    def test_missing_file_returns_custom_default(self, temp_dir):
        """Test that missing file returns custom default value."""
        file_path = temp_dir / "nonexistent.json"
        default = {"status": "initialized"}

        result = safe_read_json(file_path, default=default)
        assert result == default

    def test_invalid_json_returns_default(self, temp_dir):
        """Test that invalid JSON file returns default."""
        file_path = temp_dir / "invalid.json"

        with open(file_path, "w") as f:
            f.write("not valid json {{{")

        result = safe_read_json(file_path)
        assert result == {}

    def test_invalid_json_returns_custom_default(self, temp_dir):
        """Test that invalid JSON returns custom default."""
        file_path = temp_dir / "invalid.json"
        default = {"fallback": True}

        with open(file_path, "w") as f:
            f.write("not valid json")

        result = safe_read_json(file_path, default=default)
        assert result == default

    def test_empty_file_returns_default(self, temp_dir):
        """Test that empty file returns default."""
        file_path = temp_dir / "empty.json"

        file_path.touch()  # Create empty file

        result = safe_read_json(file_path)
        assert result == {}


class TestAtomicityGuarantees:
    """Tests for atomicity guarantees of file operations."""

    def test_read_during_write_sees_old_or_new(self, temp_dir):
        """Test that readers see either old or new data, never partial."""
        file_path = temp_dir / "test.json"

        # Write initial data
        old_data = {"version": 1, "data": "old"}
        atomic_write_json(file_path, old_data)

        # Write new data
        new_data = {"version": 2, "data": "new", "extra": "field"}
        atomic_write_json(file_path, new_data)

        # Read should see new data
        result = safe_read_json(file_path)
        assert result == new_data

    def test_write_to_path_object(self, temp_dir):
        """Test that Path objects work correctly."""
        file_path = Path(temp_dir) / "test.json"
        data = {"key": "value"}

        atomic_write_json(file_path, data)
        result = safe_read_json(file_path)

        assert result == data

"""Tests for state_utils module - atomic file operations."""

import json
import logging
from pathlib import Path

import pytest

from wanctl.state_utils import atomic_write_json, safe_json_load_file, safe_read_json


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


class TestStateCorruptionRecovery:
    """Tests proving graceful recovery from state file corruption.

    SAFETY INVARIANT: Corrupted state files must return defaults, not crash.
    This prevents daemon failures during interrupted writes or disk corruption.

    These tests validate the defensive error handling in safe_json_load_file()
    which is used throughout the codebase for state file loading.
    """

    def test_partial_json_returns_default(self, temp_dir):
        """Truncated JSON (interrupted write) returns default, not crash.

        Simulates an interrupted atomic write where the temp file was renamed
        but the JSON content was only partially written.
        """
        file_path = temp_dir / "state.json"

        # Simulate interrupted write - missing closing braces
        with open(file_path, "w") as f:
            f.write('{"ewma": {"baseline_rtt": 30.0')  # Truncated

        result = safe_json_load_file(file_path, default={"initialized": True})
        assert result == {"initialized": True}  # Graceful recovery

    def test_truncated_json_logs_error(self, temp_dir, caplog):
        """Truncated JSON should log error message with context."""
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write('{"key": "value"')  # Missing closing brace

        logger = logging.getLogger("test_state_corruption")
        caplog.set_level(logging.ERROR)

        result = safe_json_load_file(
            file_path,
            logger=logger,
            default={},
            error_context="test state",
        )

        assert result == {}
        # Verify error was logged
        assert any(
            "Failed to parse" in record.message and "test state" in record.message
            for record in caplog.records
        ), "Expected error log with context not found"

    def test_binary_garbage_returns_default(self, temp_dir):
        """Non-JSON binary content returns default gracefully.

        Simulates complete file corruption or accidental overwrite with binary data.
        """
        file_path = temp_dir / "state.json"

        # Write binary garbage (non-UTF-8 compatible)
        with open(file_path, "wb") as f:
            f.write(b"\x00\x01\x02\xff\xfe\xfd\x80\x81\x82")

        logger = logging.getLogger("test_binary")
        result = safe_json_load_file(
            file_path,
            logger=logger,
            default={"fallback": True},
            error_context="corrupted state",
        )

        assert result == {"fallback": True}

    def test_utf8_decode_error_returns_default(self, temp_dir):
        """Invalid UTF-8 bytes return default gracefully.

        JSON files should be valid UTF-8. Invalid encoding should not crash.
        """
        file_path = temp_dir / "state.json"

        # Write invalid UTF-8 sequence embedded in otherwise valid-looking JSON start
        with open(file_path, "wb") as f:
            f.write(b'{"key": "\xff\xfe invalid"}')

        result = safe_json_load_file(file_path, default={"recovered": True})
        # Should return default due to JSON decode error (invalid escape or encoding)
        assert result == {"recovered": True}

    def test_empty_object_is_valid(self, temp_dir):
        """Empty JSON object {} is valid and should be returned as-is."""
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write("{}")

        result = safe_json_load_file(file_path, default={"should_not_return": True})
        assert result == {}  # Valid empty object, not default

    def test_null_content_returns_null(self, temp_dir):
        """File containing only 'null' returns None (valid JSON null)."""
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write("null")

        result = safe_json_load_file(file_path, default={"fallback": True})
        assert result is None  # JSON null is valid, returns None

    def test_empty_file_returns_default(self, temp_dir):
        """Completely empty file (0 bytes) returns default."""
        file_path = temp_dir / "state.json"
        file_path.touch()  # Create empty file

        result = safe_json_load_file(file_path, default={"initialized": False})
        assert result == {"initialized": False}

    def test_whitespace_only_returns_default(self, temp_dir):
        """File with only whitespace returns default."""
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write("   \n\t  \n  ")

        result = safe_json_load_file(file_path, default={"empty": True})
        assert result == {"empty": True}

    def test_array_instead_of_object_is_valid(self, temp_dir):
        """JSON array is valid JSON and should be returned."""
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write("[1, 2, 3]")

        result = safe_json_load_file(file_path, default={"fallback": True})
        assert result == [1, 2, 3]  # Valid JSON array

    def test_nested_truncation_returns_default(self, temp_dir):
        """Deeply nested truncated JSON returns default.

        Simulates partial write of complex autorate state structure.
        """
        file_path = temp_dir / "state.json"

        # Simulate truncated autorate state file
        truncated_state = '{"ewma": {"baseline_rtt": 25.5, "load_rtt": 30.2}, "rates": {"download":'
        with open(file_path, "w") as f:
            f.write(truncated_state)

        result = safe_json_load_file(
            file_path,
            default={"reset": True, "baseline_rtt": 20.0},
            error_context="autorate state",
        )
        assert result == {"reset": True, "baseline_rtt": 20.0}

    def test_missing_file_returns_default(self, temp_dir):
        """Non-existent file returns default without error."""
        file_path = temp_dir / "nonexistent.json"

        logger = logging.getLogger("test_missing")
        result = safe_json_load_file(
            file_path,
            logger=logger,
            default={"new_state": True},
        )

        assert result == {"new_state": True}

    def test_corruption_recovery_multiple_attempts(self, temp_dir):
        """Multiple load attempts with corruption always return default.

        Verifies consistent behavior across repeated loads of corrupted file.
        """
        file_path = temp_dir / "state.json"

        with open(file_path, "w") as f:
            f.write('{"incomplete":')

        default = {"consistent": True}

        # Load multiple times - should always return same default
        for _ in range(5):
            result = safe_json_load_file(file_path, default=default)
            assert result == default

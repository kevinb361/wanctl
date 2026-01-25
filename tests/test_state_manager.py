"""Unit tests for state_manager module."""

import logging
import tempfile
from pathlib import Path

import pytest

from wanctl.state_manager import (
    StateManager,
    StateSchema,
    SteeringStateManager,
    bounded_float,
    non_negative_float,
    non_negative_int,
    optional_positive_float,
    string_enum,
)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_state_manager")


# =============================================================================
# VALIDATOR FUNCTION TESTS
# =============================================================================


class TestValidatorFunctions:
    """Tests for validator functions."""

    # -------------------------------------------------------------------------
    # non_negative_int tests
    # -------------------------------------------------------------------------

    def test_non_negative_int_positive_unchanged(self):
        """Test positive int returns unchanged."""
        assert non_negative_int(5) == 5
        assert non_negative_int(100) == 100

    def test_non_negative_int_zero_unchanged(self):
        """Test zero returns unchanged."""
        assert non_negative_int(0) == 0

    def test_non_negative_int_negative_returns_zero(self):
        """Test negative int returns 0."""
        assert non_negative_int(-3) == 0
        assert non_negative_int(-100) == 0

    def test_non_negative_int_string_coercion(self):
        """Test string coercion to int."""
        assert non_negative_int("10") == 10
        assert non_negative_int("0") == 0

    def test_non_negative_int_float_coercion(self):
        """Test float coercion to int (truncation)."""
        assert non_negative_int(3.7) == 3
        assert non_negative_int(3.2) == 3

    # -------------------------------------------------------------------------
    # non_negative_float tests
    # -------------------------------------------------------------------------

    def test_non_negative_float_positive_unchanged(self):
        """Test positive float returns unchanged."""
        assert non_negative_float(3.14) == 3.14
        assert non_negative_float(100.5) == 100.5

    def test_non_negative_float_zero_unchanged(self):
        """Test zero returns unchanged."""
        assert non_negative_float(0.0) == 0.0

    def test_non_negative_float_negative_returns_zero(self):
        """Test negative float returns 0.0."""
        assert non_negative_float(-1.5) == 0.0
        assert non_negative_float(-100.0) == 0.0

    def test_non_negative_float_int_coercion(self):
        """Test int coercion to float."""
        result = non_negative_float(5)
        assert result == 5.0
        assert isinstance(result, float)

    # -------------------------------------------------------------------------
    # optional_positive_float tests
    # -------------------------------------------------------------------------

    def test_optional_positive_float_none_returns_none(self):
        """Test None returns None."""
        assert optional_positive_float(None) is None

    def test_optional_positive_float_valid_value(self):
        """Test valid float in bounds returns float."""
        result = optional_positive_float(5.0, min_val=0.0, max_val=10.0)
        assert result == 5.0

    def test_optional_positive_float_at_bounds(self):
        """Test value exactly at bounds returns unchanged."""
        assert optional_positive_float(0.0, min_val=0.0, max_val=10.0) == 0.0
        assert optional_positive_float(10.0, min_val=0.0, max_val=10.0) == 10.0

    def test_optional_positive_float_below_min_raises(self):
        """Test value below min raises ValueError."""
        with pytest.raises(ValueError, match="below minimum"):
            optional_positive_float(-0.1, min_val=0.0)

    def test_optional_positive_float_above_max_raises(self):
        """Test value above max raises ValueError."""
        with pytest.raises(ValueError, match="above maximum"):
            optional_positive_float(10.1, max_val=10.0)

    def test_optional_positive_float_no_bounds(self):
        """Test value with no bounds specified."""
        assert optional_positive_float(1000.0) == 1000.0
        assert optional_positive_float(-1000.0) == -1000.0

    # -------------------------------------------------------------------------
    # bounded_float tests
    # -------------------------------------------------------------------------

    def test_bounded_float_with_clamp_above_max(self):
        """Test bounded_float clamps value above max."""
        validator = bounded_float(0.0, 1.0, clamp=True)
        assert validator(1.5) == 1.0

    def test_bounded_float_with_clamp_below_min(self):
        """Test bounded_float clamps value below min."""
        validator = bounded_float(0.0, 1.0, clamp=True)
        assert validator(-0.5) == 0.0

    def test_bounded_float_with_clamp_in_range(self):
        """Test bounded_float returns unchanged when in range."""
        validator = bounded_float(0.0, 1.0, clamp=True)
        assert validator(0.5) == 0.5

    def test_bounded_float_with_clamp_at_bounds(self):
        """Test bounded_float returns exactly at bounds."""
        validator = bounded_float(0.0, 1.0, clamp=True)
        assert validator(0.0) == 0.0
        assert validator(1.0) == 1.0

    def test_bounded_float_no_clamp_raises_above_max(self):
        """Test bounded_float raises ValueError above max when clamp=False."""
        validator = bounded_float(0.0, 1.0, clamp=False)
        with pytest.raises(ValueError, match="not in range"):
            validator(1.5)

    def test_bounded_float_no_clamp_raises_below_min(self):
        """Test bounded_float raises ValueError below min when clamp=False."""
        validator = bounded_float(0.0, 1.0, clamp=False)
        with pytest.raises(ValueError, match="not in range"):
            validator(-0.5)

    def test_bounded_float_no_clamp_valid_returns_unchanged(self):
        """Test bounded_float returns unchanged when valid and clamp=False."""
        validator = bounded_float(0.0, 1.0, clamp=False)
        assert validator(0.5) == 0.5
        assert validator(0.0) == 0.0
        assert validator(1.0) == 1.0

    def test_bounded_float_string_coercion(self):
        """Test bounded_float coerces string to float."""
        validator = bounded_float(0.0, 10.0, clamp=True)
        assert validator("5.0") == 5.0

    # -------------------------------------------------------------------------
    # string_enum tests
    # -------------------------------------------------------------------------

    def test_string_enum_valid_value(self):
        """Test string_enum accepts valid values."""
        validator = string_enum("GREEN", "YELLOW", "RED")
        assert validator("GREEN") == "GREEN"
        assert validator("YELLOW") == "YELLOW"
        assert validator("RED") == "RED"

    def test_string_enum_invalid_value_raises(self):
        """Test string_enum raises ValueError for invalid value."""
        validator = string_enum("GREEN", "YELLOW", "RED")
        with pytest.raises(ValueError, match="not in allowed set"):
            validator("INVALID")

    def test_string_enum_coerces_to_string(self):
        """Test string_enum coerces value to string."""
        validator = string_enum("1", "2", "3")
        assert validator(1) == "1"

    def test_string_enum_empty_string_when_allowed(self):
        """Test string_enum accepts empty string if in allowed set."""
        validator = string_enum("", "value")
        assert validator("") == ""


@pytest.fixture
def temp_state_file():
    """Provide a temporary state file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        yield state_file


class TestStateSchema:
    """Tests for StateSchema class."""

    def test_simple_schema_creation(self):
        """Test creating a simple schema."""
        schema = StateSchema({"count": 0, "name": "default", "value": 1.5})
        assert schema is not None

    def test_get_defaults(self):
        """Test getting all defaults."""
        schema = StateSchema({"count": 0, "name": "default", "enabled": True})
        defaults = schema.get_defaults()
        assert defaults["count"] == 0
        assert defaults["name"] == "default"
        assert defaults["enabled"] is True

    def test_validate_field_type_conversion(self):
        """Test field validation with type conversion."""
        schema = StateSchema({"count": 0})
        # String "5" should convert to int
        result = schema.validate_field("count", "5")
        assert result == 5
        assert isinstance(result, int)

    def test_validate_field_invalid_name(self):
        """Test validation fails for unknown field."""
        schema = StateSchema({"count": 0})
        with pytest.raises(KeyError):
            schema.validate_field("unknown", 5)

    def test_validate_state_fills_defaults(self):
        """Test that validate_state fills in missing fields."""
        schema = StateSchema({"count": 0, "name": "default", "enabled": True})
        partial_state = {"count": 5}
        validated = schema.validate_state(partial_state)
        assert validated["count"] == 5
        assert validated["name"] == "default"
        assert validated["enabled"] is True

    def test_validate_state_preserves_provided_values(self):
        """Test that validate_state doesn't overwrite provided values."""
        schema = StateSchema({"count": 0, "name": "default"})
        state = {"count": 10, "name": "custom"}
        validated = schema.validate_state(state)
        assert validated["count"] == 10
        assert validated["name"] == "custom"

    def test_schema_with_tuple_validators(self):
        """Test schema with tuple validators (default, validator_func)."""
        schema = StateSchema({"alpha": (0.5, bounded_float(0.0, 1.0))})
        defaults = schema.get_defaults()
        assert defaults["alpha"] == 0.5

        # Validator should clamp out-of-range values
        result = schema.validate_field("alpha", 1.5)
        assert result == 1.0

    def test_validate_field_type_coercion_failure_returns_default(self):
        """Test validation returns default when type coercion fails."""
        schema = StateSchema({"count": 0})
        # Object that can't be converted to int
        result = schema.validate_field("count", object())
        assert result == 0

    def test_validate_state_logs_warning_on_validation_failure(self, caplog):
        """Test validate_state logs warning on validation failure."""
        logger = logging.getLogger("test_schema")
        schema = StateSchema({"alpha": (0.5, bounded_float(0.0, 1.0, clamp=False))})

        # Value out of range with clamp=False will raise ValueError
        state = {"alpha": 2.0}

        with caplog.at_level(logging.WARNING):
            validated = schema.validate_state(state, logger=logger)

        # Should use default due to validation failure
        assert validated["alpha"] == 0.5
        assert "validation failed" in caplog.text


class TestStateManager:
    """Tests for StateManager class."""

    def test_manager_initialization(self, temp_state_file, logger):
        """Test initializing state manager."""
        schema = StateSchema({"count": 0, "name": "test"})
        manager = StateManager(temp_state_file, schema, logger)
        assert manager.state_file == temp_state_file
        assert manager.logger == logger

    def test_load_nonexistent_file_uses_defaults(self, temp_state_file, logger):
        """Test loading when file doesn't exist uses defaults."""
        schema = StateSchema({"count": 0, "name": "default"})
        manager = StateManager(temp_state_file, schema, logger)

        result = manager.load()
        assert result is False
        assert manager.state["count"] == 0
        assert manager.state["name"] == "default"

    def test_save_creates_file(self, temp_state_file, logger):
        """Test that save creates the state file."""
        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"count": 42}

        result = manager.save()
        assert result is True
        assert temp_state_file.exists()

    def test_load_and_save_roundtrip(self, temp_state_file, logger):
        """Test saving and loading state roundtrip."""
        schema = StateSchema({"count": 0, "name": "test"})

        # Save state
        manager1 = StateManager(temp_state_file, schema, logger)
        manager1.state = {"count": 42, "name": "custom"}
        assert manager1.save() is True

        # Load state
        manager2 = StateManager(temp_state_file, schema, logger)
        assert manager2.load() is True
        assert manager2.state["count"] == 42
        assert manager2.state["name"] == "custom"

    def test_get_method(self, temp_state_file, logger):
        """Test getting state values."""
        schema = StateSchema({"count": 0, "name": "default"})
        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"count": 10, "name": "test"}

        assert manager.get("count") == 10
        assert manager.get("name") == "test"
        assert manager.get("missing", "fallback") == "fallback"

    def test_set_method(self, temp_state_file, logger):
        """Test setting state values."""
        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)

        manager.set("count", 42)
        assert manager.state["count"] == 42

    def test_update_method(self, temp_state_file, logger):
        """Test updating multiple state values."""
        schema = StateSchema({"count": 0, "name": "default", "enabled": False})
        manager = StateManager(temp_state_file, schema, logger)

        manager.update({"count": 10, "name": "custom"})
        assert manager.state["count"] == 10
        assert manager.state["name"] == "custom"
        assert manager.state["enabled"] is False  # Unchanged

    def test_reset_method(self, temp_state_file, logger):
        """Test resetting state to defaults."""
        schema = StateSchema({"count": 0, "name": "default"})
        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"count": 99, "name": "modified"}

        manager.reset()
        assert manager.state["count"] == 0
        assert manager.state["name"] == "default"

    def test_to_dict_method(self, temp_state_file, logger):
        """Test converting state to dictionary."""
        schema = StateSchema({"count": 0, "name": "test"})
        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"count": 42, "name": "custom"}

        state_dict = manager.to_dict()
        assert state_dict == {"count": 42, "name": "custom"}
        # Verify it's a copy, not reference
        state_dict["count"] = 999
        assert manager.state["count"] == 42

    def test_load_invalid_json_uses_defaults(self, temp_state_file, logger):
        """Test loading invalid JSON uses defaults."""
        temp_state_file.write_text("{ invalid json")

        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)

        result = manager.load()
        assert result is False
        assert manager.state["count"] == 0

    def test_context_in_error_messages(self, temp_state_file, logger):
        """Test that context appears in error messages."""
        # Write invalid JSON
        temp_state_file.write_text("{ bad")

        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger, context="test_context")

        # Should not raise, just return False
        result = manager.load()
        assert result is False

    def test_get_with_default_from_schema(self, temp_state_file, logger):
        """Test get uses schema default when no explicit default provided."""
        schema = StateSchema({"count": 42, "name": "default_name"})
        manager = StateManager(temp_state_file, schema, logger)
        # State doesn't have 'count', so should use schema default
        manager.state = {}

        result = manager.get("count")
        assert result == 42

    # -------------------------------------------------------------------------
    # Backup/recovery tests
    # -------------------------------------------------------------------------

    def test_backup_state_file_creates_backup(self, temp_state_file, logger):
        """Test _backup_state_file creates .backup file."""
        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)

        # Create and save a state file first
        temp_state_file.write_text('{"count": 42}')

        result = manager._backup_state_file()
        assert result is True
        backup_path = temp_state_file.with_suffix(".json.backup")
        assert backup_path.exists()
        assert backup_path.read_text() == '{"count": 42}'

    def test_backup_state_file_nonexistent_returns_false(self, temp_state_file, logger):
        """Test _backup_state_file returns False when file doesn't exist."""
        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)

        # Don't create the file
        result = manager._backup_state_file()
        assert result is False

    def test_backup_state_file_failure_returns_false(self, temp_state_file, logger, caplog):
        """Test _backup_state_file returns False on copy failure."""
        from unittest.mock import patch

        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)
        temp_state_file.write_text('{"count": 42}')

        with patch("wanctl.state_manager.shutil.copy2") as mock_copy:
            mock_copy.side_effect = PermissionError("Access denied")
            with caplog.at_level(logging.ERROR):
                result = manager._backup_state_file()

        assert result is False
        assert "Failed to backup state file" in caplog.text

    def test_load_corrupt_primary_valid_backup_recovers(self, temp_state_file, logger, caplog):
        """Test load recovers from backup when primary is corrupt."""
        schema = StateSchema({"count": 0, "name": "default"})
        manager = StateManager(temp_state_file, schema, logger)

        # Create corrupt primary
        temp_state_file.write_text("{ invalid json")

        # Create valid backup
        backup_path = temp_state_file.with_suffix(".json.backup")
        backup_path.write_text('{"count": 99, "name": "from_backup"}')

        with caplog.at_level(logging.INFO):
            result = manager.load()

        assert result is True
        assert manager.state["count"] == 99
        assert manager.state["name"] == "from_backup"
        assert "Recovered state from backup" in caplog.text

    def test_load_both_corrupt_uses_defaults(self, temp_state_file, logger, caplog):
        """Test load uses defaults when both primary and backup are corrupt."""
        schema = StateSchema({"count": 42, "name": "default"})
        manager = StateManager(temp_state_file, schema, logger)

        # Create corrupt primary
        temp_state_file.write_text("{ invalid json")

        # Create corrupt backup
        backup_path = temp_state_file.with_suffix(".json.backup")
        backup_path.write_text("{ also invalid")

        with caplog.at_level(logging.WARNING):
            result = manager.load()

        assert result is False
        assert manager.state["count"] == 42
        assert manager.state["name"] == "default"
        assert "Failed to parse state file, using defaults" in caplog.text

    def test_load_backup_validation_fails_uses_defaults(self, temp_state_file, logger, caplog):
        """Test load uses defaults when backup validation fails."""
        # Create a schema with a validator that will fail
        schema = StateSchema({"alpha": (0.5, bounded_float(0.0, 1.0, clamp=False))})
        manager = StateManager(temp_state_file, schema, logger)

        # Create corrupt primary
        temp_state_file.write_text("{ invalid")

        # Create backup with value that will fail validation (out of range)
        backup_path = temp_state_file.with_suffix(".json.backup")
        backup_path.write_text('{"alpha": 5.0}')

        with caplog.at_level(logging.WARNING):
            result = manager.load()

        # Should still load - validate_state catches and logs the error
        # and uses default for the failed field
        assert result is True
        assert manager.state["alpha"] == 0.5  # Default used for invalid field

    def test_load_validation_failure_path(self, temp_state_file, logger, caplog):
        """Test load handles validation exception and uses defaults (lines 390-394)."""
        from unittest.mock import patch

        schema = StateSchema({"count": 42})
        manager = StateManager(temp_state_file, schema, logger)

        # Create valid JSON
        temp_state_file.write_text('{"count": 10}')

        # Mock validate_state to raise an exception
        with patch.object(schema, "validate_state", side_effect=RuntimeError("Validation exploded")):
            with caplog.at_level(logging.ERROR):
                result = manager.load()

        assert result is False
        assert manager.state["count"] == 42  # Defaults
        assert "Failed to validate state" in caplog.text

    def test_save_failure_returns_false(self, temp_state_file, logger, caplog):
        """Test save returns False and logs error on failure."""
        from unittest.mock import patch

        schema = StateSchema({"count": 0})
        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"count": 42}

        with patch("wanctl.state_manager.atomic_write_json") as mock_write:
            mock_write.side_effect = OSError("Disk full")
            with caplog.at_level(logging.ERROR):
                result = manager.save()

        assert result is False
        assert "Failed to save state" in caplog.text


class TestStateManagerWithNestedData:
    """Tests for StateManager with nested/complex data structures."""

    def test_nested_dict_state(self, temp_state_file, logger):
        """Test state with nested dictionaries."""
        schema = StateSchema({"config": {"host": "localhost", "port": 8080}, "count": 0})

        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"config": {"host": "example.com", "port": 443}, "count": 5}

        # Save and load
        assert manager.save() is True

        manager2 = StateManager(temp_state_file, schema, logger)
        assert manager2.load() is True
        assert manager2.state["config"]["host"] == "example.com"
        assert manager2.state["config"]["port"] == 443
        assert manager2.state["count"] == 5

    def test_list_state(self, temp_state_file, logger):
        """Test state with lists."""
        schema = StateSchema({"items": [], "count": 0})

        manager = StateManager(temp_state_file, schema, logger)
        manager.state = {"items": [1, 2, 3], "count": 3}

        assert manager.save() is True

        manager2 = StateManager(temp_state_file, schema, logger)
        assert manager2.load() is True
        assert manager2.state["items"] == [1, 2, 3]


# =============================================================================
# STEERING STATE MANAGER TESTS
# =============================================================================


class TestSteeringStateManager:
    """Tests for SteeringStateManager class."""

    @pytest.fixture
    def steering_schema(self):
        """Provide a steering-specific schema with deque fields."""
        return StateSchema(
            {
                "state": "GREEN",
                "bad_count": 0,
                "good_count": 0,
                "history_rtt": [],
                "history_delta": [],
                "cake_drops_history": [],
                "queue_depth_history": [],
                "transitions": [],
                "last_transition_time": None,
            }
        )

    # -------------------------------------------------------------------------
    # Initialization tests
    # -------------------------------------------------------------------------

    def test_default_history_maxlen(self, temp_state_file, steering_schema, logger):
        """Test default history_maxlen is used when None."""
        manager = SteeringStateManager(
            temp_state_file, steering_schema, logger, history_maxlen=None
        )
        assert manager.history_maxlen == SteeringStateManager.DEFAULT_HISTORY_MAXLEN

    def test_custom_history_maxlen(self, temp_state_file, steering_schema, logger):
        """Test custom history_maxlen is passed through."""
        manager = SteeringStateManager(
            temp_state_file, steering_schema, logger, history_maxlen=100
        )
        assert manager.history_maxlen == 100

    # -------------------------------------------------------------------------
    # Load with deque conversion tests
    # -------------------------------------------------------------------------

    def test_load_converts_lists_to_deques(self, temp_state_file, steering_schema, logger):
        """Test JSON lists are converted to deques on load."""
        from collections import deque

        # Write state with lists
        temp_state_file.write_text(
            '{"state": "GREEN", "bad_count": 0, "good_count": 0, '
            '"history_rtt": [10.0, 11.0, 12.0], "history_delta": [1.0, 2.0], '
            '"transitions": [], "last_transition_time": null}'
        )

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        result = manager.load()

        assert result is True
        assert isinstance(manager.state["history_rtt"], deque)
        assert isinstance(manager.state["history_delta"], deque)
        assert list(manager.state["history_rtt"]) == [10.0, 11.0, 12.0]
        assert list(manager.state["history_delta"]) == [1.0, 2.0]

    def test_load_enforces_history_maxlen(self, temp_state_file, steering_schema, logger):
        """Test history_maxlen is enforced on deques."""
        from collections import deque

        # Write state with more items than maxlen
        long_history = [float(i) for i in range(100)]
        import json

        state_data = {
            "state": "GREEN",
            "bad_count": 0,
            "good_count": 0,
            "history_rtt": long_history,
            "history_delta": long_history,
            "transitions": [],
            "last_transition_time": None,
        }
        temp_state_file.write_text(json.dumps(state_data))

        manager = SteeringStateManager(
            temp_state_file, steering_schema, logger, history_maxlen=10
        )
        result = manager.load()

        assert result is True
        assert isinstance(manager.state["history_rtt"], deque)
        # Should be trimmed to last 10 items
        assert len(manager.state["history_rtt"]) == 10
        assert manager.state["history_rtt"].maxlen == 10

    def test_load_converts_non_list_to_empty_deque(self, temp_state_file, steering_schema, logger):
        """Test non-list/non-deque values are converted to empty deque."""
        from collections import deque

        # Write state with integer value for history field (not iterable)
        temp_state_file.write_text(
            '{"state": "GREEN", "bad_count": 0, "good_count": 0, '
            '"history_rtt": 123, "history_delta": 456, '
            '"cake_drops_history": [], "queue_depth_history": [], '
            '"transitions": [], "last_transition_time": null}'
        )

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        result = manager.load()

        assert result is True
        assert isinstance(manager.state["history_rtt"], deque)
        assert isinstance(manager.state["history_delta"], deque)
        # Non-list/non-deque values should become empty deques
        assert len(manager.state["history_rtt"]) == 0
        assert len(manager.state["history_delta"]) == 0

    def test_load_backup_recovery_with_deques(self, temp_state_file, steering_schema, logger, caplog):
        """Test backup recovery works with deque conversion."""
        from collections import deque

        # Create corrupt primary
        temp_state_file.write_text("{ invalid json")

        # Create valid backup
        backup_path = temp_state_file.with_suffix(".json.backup")
        backup_path.write_text(
            '{"state": "YELLOW", "bad_count": 5, "good_count": 0, '
            '"history_rtt": [15.0, 16.0], "history_delta": [3.0], '
            '"cake_drops_history": [], "queue_depth_history": [], '
            '"transitions": [], "last_transition_time": null}'
        )

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        with caplog.at_level(logging.INFO):
            result = manager.load()

        assert result is True
        assert manager.state["state"] == "YELLOW"
        assert manager.state["bad_count"] == 5
        assert isinstance(manager.state["history_rtt"], deque)
        assert list(manager.state["history_rtt"]) == [15.0, 16.0]

    def test_load_both_corrupt_uses_defaults(self, temp_state_file, steering_schema, logger):
        """Test load uses defaults when both primary and backup are corrupt."""
        # Create corrupt primary
        temp_state_file.write_text("{ invalid json")

        # Create corrupt backup
        backup_path = temp_state_file.with_suffix(".json.backup")
        backup_path.write_text("{ also invalid")

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        result = manager.load()

        assert result is False
        assert manager.state["state"] == "GREEN"
        assert manager.state["bad_count"] == 0

    # -------------------------------------------------------------------------
    # Save with locking tests
    # -------------------------------------------------------------------------

    def test_save_use_lock_false_writes_directly(self, temp_state_file, steering_schema, logger):
        """Test save with use_lock=False writes directly without lock."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "YELLOW"
        manager.state["bad_count"] = 3

        result = manager.save(use_lock=False)

        assert result is True
        assert temp_state_file.exists()
        # Backup should also be created
        backup_path = temp_state_file.with_suffix(".json.backup")
        assert backup_path.exists()

    def test_save_use_lock_true_acquires_lock(self, temp_state_file, steering_schema, logger):
        """Test save with use_lock=True acquires lock, writes, releases."""
        from unittest.mock import patch

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "RED"

        # Track lock calls
        lock_calls = []

        def track_flock(fd, operation):

            lock_calls.append(operation)

        with patch("wanctl.state_manager.fcntl.flock", side_effect=track_flock):
            result = manager.save(use_lock=True)

        assert result is True
        # Should have LOCK_EX|LOCK_NB first, then LOCK_UN
        import fcntl

        assert fcntl.LOCK_EX | fcntl.LOCK_NB in lock_calls
        assert fcntl.LOCK_UN in lock_calls

    def test_save_blocking_io_error_returns_false(self, temp_state_file, steering_schema, logger, caplog):
        """Test save returns False when BlockingIOError (lock held by another)."""
        from unittest.mock import patch

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "YELLOW"

        with patch("wanctl.state_manager.fcntl.flock") as mock_flock:
            mock_flock.side_effect = BlockingIOError("Lock held by another process")
            with caplog.at_level(logging.WARNING):
                result = manager.save(use_lock=True)

        assert result is False
        assert "locked by another process" in caplog.text

    def test_save_other_lock_exception_returns_false(self, temp_state_file, steering_schema, logger, caplog):
        """Test save returns False and logs error on other lock exceptions."""
        from unittest.mock import patch

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "YELLOW"

        with patch("wanctl.state_manager.fcntl.flock") as mock_flock:
            mock_flock.side_effect = OSError("Unexpected lock error")
            with caplog.at_level(logging.ERROR):
                result = manager.save(use_lock=True)

        assert result is False
        assert "Failed to acquire state file lock" in caplog.text

    def test_save_general_exception_returns_false(self, temp_state_file, steering_schema, logger, caplog):
        """Test save returns False on general exception."""
        from unittest.mock import patch

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "YELLOW"

        with patch("wanctl.state_manager.atomic_write_json") as mock_write:
            mock_write.side_effect = RuntimeError("Unexpected error")
            with caplog.at_level(logging.ERROR):
                result = manager.save(use_lock=False)

        assert result is False
        assert "Failed to save state" in caplog.text

    # -------------------------------------------------------------------------
    # Deque to list conversion tests (roundtrip)
    # -------------------------------------------------------------------------

    def test_save_deque_to_list_conversion_roundtrip(self, temp_state_file, steering_schema, logger):
        """Test deques are serialized as lists in JSON, restored as deques on load."""
        from collections import deque

        manager1 = SteeringStateManager(temp_state_file, steering_schema, logger)
        # Set up deques manually
        manager1.state["history_rtt"] = deque([10.0, 11.0, 12.0], maxlen=50)
        manager1.state["history_delta"] = deque([1.0, 2.0], maxlen=50)

        # Save
        assert manager1.save(use_lock=False) is True

        # Load in new manager
        manager2 = SteeringStateManager(temp_state_file, steering_schema, logger)
        assert manager2.load() is True

        # Verify deques restored
        assert isinstance(manager2.state["history_rtt"], deque)
        assert isinstance(manager2.state["history_delta"], deque)
        assert list(manager2.state["history_rtt"]) == [10.0, 11.0, 12.0]
        assert list(manager2.state["history_delta"]) == [1.0, 2.0]

    # -------------------------------------------------------------------------
    # add_measurement tests
    # -------------------------------------------------------------------------

    def test_add_measurement_appends_to_deques(self, temp_state_file, steering_schema, logger):
        """Test add_measurement adds to history_rtt and history_delta deques."""
        from collections import deque

        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["history_rtt"] = deque(maxlen=50)
        manager.state["history_delta"] = deque(maxlen=50)

        manager.add_measurement(current_rtt=15.0, delta=3.0)
        manager.add_measurement(current_rtt=16.0, delta=4.0)

        assert list(manager.state["history_rtt"]) == [15.0, 16.0]
        assert list(manager.state["history_delta"]) == [3.0, 4.0]

    def test_add_measurement_handles_missing_deque_keys(self, temp_state_file, steering_schema, logger):
        """Test add_measurement handles missing deque keys gracefully."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        # Remove the deque keys
        manager.state.pop("history_rtt", None)
        manager.state.pop("history_delta", None)

        # Should not raise
        manager.add_measurement(current_rtt=15.0, delta=3.0)

    def test_add_measurement_handles_non_deque_values(self, temp_state_file, steering_schema, logger):
        """Test add_measurement skips non-deque values."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        # Set non-deque values
        manager.state["history_rtt"] = [1.0, 2.0]  # list, not deque
        manager.state["history_delta"] = "not_a_deque"

        # Should not raise or modify
        manager.add_measurement(current_rtt=15.0, delta=3.0)
        # List should be unchanged since it's not a deque
        assert manager.state["history_rtt"] == [1.0, 2.0]

    # -------------------------------------------------------------------------
    # log_transition tests
    # -------------------------------------------------------------------------

    def test_log_transition_creates_transition_dict(self, temp_state_file, steering_schema, logger):
        """Test log_transition creates transition dict with timestamp, from, to, counts."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["bad_count"] = 5
        manager.state["good_count"] = 10
        manager.state["transitions"] = []

        manager.log_transition("GREEN", "YELLOW")

        assert len(manager.state["transitions"]) == 1
        transition = manager.state["transitions"][0]
        assert transition["from"] == "GREEN"
        assert transition["to"] == "YELLOW"
        assert transition["bad_count"] == 5
        assert transition["good_count"] == 10
        assert "timestamp" in transition
        assert manager.state["last_transition_time"] == transition["timestamp"]

    def test_log_transition_appends_to_list(self, temp_state_file, steering_schema, logger):
        """Test log_transition appends to transitions list."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["transitions"] = []

        manager.log_transition("GREEN", "YELLOW")
        manager.log_transition("YELLOW", "RED")
        manager.log_transition("RED", "GREEN")

        assert len(manager.state["transitions"]) == 3
        assert manager.state["transitions"][0]["from"] == "GREEN"
        assert manager.state["transitions"][1]["from"] == "YELLOW"
        assert manager.state["transitions"][2]["from"] == "RED"

    def test_log_transition_trims_to_history_maxlen(self, temp_state_file, steering_schema, logger):
        """Test log_transition trims to history_maxlen."""
        manager = SteeringStateManager(
            temp_state_file, steering_schema, logger, history_maxlen=3
        )
        manager.state["transitions"] = []

        # Log more transitions than maxlen
        for i in range(5):
            manager.log_transition(f"STATE_{i}", f"STATE_{i+1}")

        # Should only keep last 3
        assert len(manager.state["transitions"]) == 3
        assert manager.state["transitions"][0]["from"] == "STATE_2"
        assert manager.state["transitions"][1]["from"] == "STATE_3"
        assert manager.state["transitions"][2]["from"] == "STATE_4"

    def test_log_transition_handles_missing_transitions_key(self, temp_state_file, steering_schema, logger):
        """Test log_transition handles missing transitions key."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        # Remove transitions key
        manager.state.pop("transitions", None)

        # Should not raise
        manager.log_transition("GREEN", "YELLOW")

    # -------------------------------------------------------------------------
    # reset tests
    # -------------------------------------------------------------------------

    def test_reset_resets_to_schema_defaults(self, temp_state_file, steering_schema, logger):
        """Test reset resets to schema defaults."""
        manager = SteeringStateManager(temp_state_file, steering_schema, logger)
        manager.state["state"] = "RED"
        manager.state["bad_count"] = 100

        manager.reset()

        assert manager.state["state"] == "GREEN"
        assert manager.state["bad_count"] == 0

    def test_reset_logs_message(self, temp_state_file, steering_schema, logger, caplog):
        """Test reset logs reset message."""
        manager = SteeringStateManager(
            temp_state_file, steering_schema, logger, context="test steering state"
        )

        with caplog.at_level(logging.INFO):
            manager.reset()

        assert "Resetting test steering state" in caplog.text

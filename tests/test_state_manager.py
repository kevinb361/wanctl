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

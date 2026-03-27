"""Unit tests for configuration validation utilities."""

import logging

import pytest

from wanctl.config_base import ConfigValidationError
from wanctl.config_validation_utils import (
    MAX_SANE_BASELINE_RTT,
    MIN_SANE_BASELINE_RTT,
    deprecate_param,
    validate_alpha,
    validate_bandwidth_order,
    validate_baseline_rtt,
    validate_rtt_thresholds,
    validate_sample_counts,
    validate_threshold_order,
)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_config_validation_utils")


# =============================================================================
# Tests for validate_bandwidth_order
# =============================================================================


class TestValidateBandwidthOrder:
    """Tests for validate_bandwidth_order function."""

    def test_three_state_valid_ordering(self, logger):
        """Test valid 3-state bandwidth ordering (RED/YELLOW/GREEN/CEILING)."""
        result = validate_bandwidth_order(
            name="download",
            floor_red=5000000,
            floor_yellow=10000000,
            floor_green=50000000,
            ceiling=100000000,
            logger=logger,
        )
        assert result is True

    def test_four_state_valid_ordering(self, logger):
        """Test valid 4-state bandwidth ordering (RED/SOFT_RED/YELLOW/GREEN/CEILING)."""
        result = validate_bandwidth_order(
            name="download",
            floor_red=5000000,
            floor_soft_red=7500000,
            floor_yellow=10000000,
            floor_green=50000000,
            ceiling=100000000,
            logger=logger,
        )
        assert result is True

    def test_equal_floors_valid(self, logger):
        """Test that equal floor values are valid."""
        result = validate_bandwidth_order(
            name="upload",
            floor_red=2000000,
            floor_yellow=2000000,
            floor_green=2000000,
            ceiling=10000000,
            logger=logger,
        )
        assert result is True

    def test_red_greater_than_yellow_invalid(self, logger):
        """Test that floor_red > floor_yellow is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_bandwidth_order(
                name="download",
                floor_red=20000000,
                floor_yellow=10000000,
                floor_green=50000000,
                ceiling=100000000,
                logger=logger,
            )
        assert "floor ordering violation" in str(exc_info.value)

    def test_yellow_greater_than_green_invalid(self, logger):
        """Test that floor_yellow > floor_green is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_bandwidth_order(
                name="download",
                floor_red=5000000,
                floor_yellow=50000000,
                floor_green=10000000,
                ceiling=100000000,
                logger=logger,
            )
        assert "floor ordering violation" in str(exc_info.value)

    def test_green_greater_than_ceiling_invalid(self, logger):
        """Test that floor_green > ceiling is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_bandwidth_order(
                name="download",
                floor_red=5000000,
                floor_yellow=10000000,
                floor_green=100000000,
                ceiling=50000000,
                logger=logger,
            )
        assert "floor ordering violation" in str(exc_info.value)

    def test_soft_red_violation(self, logger):
        """Test that floor_soft_red > floor_yellow is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_bandwidth_order(
                name="download",
                floor_red=5000000,
                floor_soft_red=20000000,
                floor_yellow=10000000,
                floor_green=50000000,
                ceiling=100000000,
                logger=logger,
            )
        assert "floor ordering violation" in str(exc_info.value)

    def test_default_floors(self, logger):
        """Test that unspecified floors default correctly."""
        result = validate_bandwidth_order(
            name="upload",
            floor_red=5000000,
            floor_yellow=None,  # Should default to floor_red
            floor_soft_red=None,
            floor_green=None,  # Should default to ceiling
            ceiling=10000000,
            logger=logger,
        )
        assert result is True

    def test_convert_to_mbps_display(self, logger):
        """Test that convert_to_mbps shows Mbps in error messages."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_bandwidth_order(
                name="download",
                floor_red=50000000,  # 50 Mbps
                floor_yellow=10000000,  # 10 Mbps
                floor_green=100000000,
                ceiling=1000000000,
                convert_to_mbps=True,
                logger=logger,
            )
        error_msg = str(exc_info.value)
        assert "50.0M" in error_msg  # Should show Mbps
        assert "10.0M" in error_msg


# =============================================================================
# Tests for validate_threshold_order
# =============================================================================


class TestValidateThresholdOrder:
    """Tests for validate_threshold_order function."""

    def test_valid_threshold_ordering(self, logger):
        """Test valid threshold ordering (target < warn < hard_red)."""
        result = validate_threshold_order(
            target_bloat_ms=15.0,
            warn_bloat_ms=45.0,
            hard_red_bloat_ms=80.0,
            logger=logger,
        )
        assert result is True

    def test_target_equals_warn_invalid(self, logger):
        """Test that target_bloat_ms = warn_bloat_ms is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_threshold_order(
                target_bloat_ms=15.0,
                warn_bloat_ms=15.0,
                hard_red_bloat_ms=80.0,
                logger=logger,
            )
        assert "target_bloat_ms" in str(exc_info.value)

    def test_target_greater_than_warn_invalid(self, logger):
        """Test that target_bloat_ms > warn_bloat_ms is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_threshold_order(
                target_bloat_ms=50.0,
                warn_bloat_ms=45.0,
                hard_red_bloat_ms=80.0,
                logger=logger,
            )
        assert "target_bloat_ms" in str(exc_info.value)

    def test_warn_equals_hard_red_invalid(self, logger):
        """Test that warn_bloat_ms = hard_red_bloat_ms is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_threshold_order(
                target_bloat_ms=15.0,
                warn_bloat_ms=80.0,
                hard_red_bloat_ms=80.0,
                logger=logger,
            )
        assert "warn_bloat_ms" in str(exc_info.value)

    def test_warn_greater_than_hard_red_invalid(self, logger):
        """Test that warn_bloat_ms > hard_red_bloat_ms is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_threshold_order(
                target_bloat_ms=15.0,
                warn_bloat_ms=100.0,
                hard_red_bloat_ms=80.0,
                logger=logger,
            )
        assert "warn_bloat_ms" in str(exc_info.value)

    def test_small_thresholds_valid(self, logger):
        """Test very small threshold values."""
        result = validate_threshold_order(
            target_bloat_ms=1.0,
            warn_bloat_ms=2.0,
            hard_red_bloat_ms=3.0,
            logger=logger,
        )
        assert result is True

    def test_large_thresholds_valid(self, logger):
        """Test large threshold values."""
        result = validate_threshold_order(
            target_bloat_ms=100.0,
            warn_bloat_ms=200.0,
            hard_red_bloat_ms=300.0,
            logger=logger,
        )
        assert result is True


# =============================================================================
# Tests for validate_alpha
# =============================================================================


class TestValidateAlpha:
    """Tests for validate_alpha function."""

    def test_valid_alpha_middle_range(self, logger):
        """Test valid alpha in middle of range."""
        result = validate_alpha(0.35, "rtt_ewma_alpha", logger=logger)
        assert result == 0.35

    def test_valid_alpha_min_boundary(self, logger):
        """Test alpha at minimum boundary (0.0)."""
        result = validate_alpha(0.0, "alpha", logger=logger)
        assert result == 0.0

    def test_valid_alpha_max_boundary(self, logger):
        """Test alpha at maximum boundary (1.0)."""
        result = validate_alpha(1.0, "alpha", logger=logger)
        assert result == 1.0

    def test_valid_alpha_small_smoothing(self, logger):
        """Test alpha with small smoothing (fast response)."""
        result = validate_alpha(0.1, "alpha", logger=logger)
        assert result == 0.1

    def test_valid_alpha_large_smoothing(self, logger):
        """Test alpha with large smoothing (slow response)."""
        result = validate_alpha(0.9, "alpha", logger=logger)
        assert result == 0.9

    def test_alpha_below_minimum_invalid(self, logger):
        """Test alpha below 0.0 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(-0.1, "alpha", logger=logger)
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_above_maximum_invalid(self, logger):
        """Test alpha above 1.0 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(1.5, "alpha", logger=logger)
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_int_to_float_conversion(self, logger):
        """Test that integer alpha values are converted to float."""
        result = validate_alpha(0, "alpha", logger=logger)
        assert isinstance(result, float)
        assert result == 0.0

    def test_alpha_invalid_string_raises_error(self, logger):
        """Test that non-numeric strings raise ConfigValidationError."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha("not_a_number", "alpha", logger=logger)
        assert "could not convert to float" in str(exc_info.value)

    def test_alpha_custom_bounds(self, logger):
        """Test alpha validation with custom min/max bounds."""
        result = validate_alpha(0.5, "alpha", min_val=0.1, max_val=0.9, logger=logger)
        assert result == 0.5

    def test_alpha_outside_custom_bounds(self, logger):
        """Test alpha outside custom bounds is invalid."""
        with pytest.raises(ConfigValidationError):
            validate_alpha(0.95, "alpha", min_val=0.1, max_val=0.9, logger=logger)

    def test_alpha_nan_invalid(self, logger):
        """Test that NaN alpha value is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(float("nan"), "alpha", logger=logger)
        # NaN comparisons always return False, so it will fail the range check
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_positive_infinity_invalid(self, logger):
        """Test that positive infinity alpha is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(float("inf"), "alpha", logger=logger)
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_negative_infinity_invalid(self, logger):
        """Test that negative infinity alpha is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(float("-inf"), "alpha", logger=logger)
        assert "not in valid range" in str(exc_info.value)

    def test_alpha_none_invalid(self, logger):
        """Test that None alpha value raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_alpha(None, "alpha", logger=logger)
        assert "could not convert to float" in str(exc_info.value)


# =============================================================================
# Tests for validate_baseline_rtt
# =============================================================================


class TestValidateBaselineRTT:
    """Tests for validate_baseline_rtt function."""

    def test_valid_baseline_rtt_typical(self, logger):
        """Test typical baseline RTT value."""
        result = validate_baseline_rtt(30.0, logger=logger)
        assert result == 30.0

    def test_valid_baseline_rtt_minimum(self, logger):
        """Test baseline RTT at minimum boundary."""
        result = validate_baseline_rtt(float(MIN_SANE_BASELINE_RTT), logger=logger)
        assert result == float(MIN_SANE_BASELINE_RTT)

    def test_valid_baseline_rtt_maximum(self, logger):
        """Test baseline RTT at maximum boundary."""
        result = validate_baseline_rtt(float(MAX_SANE_BASELINE_RTT), logger=logger)
        assert result == float(MAX_SANE_BASELINE_RTT)

    def test_baseline_rtt_below_minimum_invalid(self, logger):
        """Test baseline RTT below minimum is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_baseline_rtt(5.0, logger=logger)
        assert "below minimum" in str(exc_info.value)

    def test_baseline_rtt_above_maximum_invalid(self, logger):
        """Test baseline RTT above maximum is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_baseline_rtt(100.0, logger=logger)
        assert "exceeds maximum" in str(exc_info.value)

    def test_baseline_rtt_custom_bounds(self, logger):
        """Test baseline RTT validation with custom bounds."""
        result = validate_baseline_rtt(50.0, min_ms=20, max_ms=100, logger=logger)
        assert result == 50.0

    def test_baseline_rtt_int_to_float_conversion(self, logger):
        """Test that integer baseline RTT values are converted to float."""
        result = validate_baseline_rtt(30, logger=logger)
        assert isinstance(result, float)
        assert result == 30.0

    def test_baseline_rtt_very_low_invalid(self, logger):
        """Test extremely low baseline RTT (0ms)."""
        with pytest.raises(ConfigValidationError):
            validate_baseline_rtt(0.0, logger=logger)

    def test_baseline_rtt_very_high_invalid(self, logger):
        """Test extremely high baseline RTT (1000ms)."""
        with pytest.raises(ConfigValidationError):
            validate_baseline_rtt(1000.0, logger=logger)


# =============================================================================
# Tests for validate_rtt_thresholds
# =============================================================================


class TestValidateRTTThresholds:
    """Tests for validate_rtt_thresholds function."""

    def test_valid_rtt_thresholds_explicit(self, logger):
        """Test valid RTT thresholds with explicit values."""
        green, yellow, red = validate_rtt_thresholds(5.0, 10.0, 15.0, logger=logger)
        assert green == 5.0
        assert yellow == 10.0
        assert red == 15.0

    def test_valid_rtt_thresholds_with_defaults(self, logger):
        """Test RTT thresholds with automatic defaults."""
        green, yellow, red = validate_rtt_thresholds(5.0, logger=logger)
        assert green == 5.0
        assert yellow == 10.0  # Default: green * 2
        assert red == 15.0  # Default: green * 3

    def test_valid_rtt_thresholds_equal_allowed(self, logger):
        """Test that equal thresholds are allowed."""
        green, yellow, red = validate_rtt_thresholds(10.0, 10.0, 10.0, logger=logger)
        assert green == 10.0
        assert yellow == 10.0
        assert red == 10.0

    def test_rtt_yellow_less_than_green_invalid(self, logger):
        """Test that yellow_rtt < green_rtt is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_rtt_thresholds(10.0, 5.0, 15.0, logger=logger)
        assert "ordering violation" in str(exc_info.value)

    def test_rtt_red_less_than_yellow_invalid(self, logger):
        """Test that red_rtt < yellow_rtt is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_rtt_thresholds(5.0, 15.0, 10.0, logger=logger)
        assert "ordering violation" in str(exc_info.value)

    def test_rtt_thresholds_with_none_yellow(self, logger):
        """Test thresholds with yellow=None (auto-default)."""
        green, yellow, red = validate_rtt_thresholds(10.0, None, 30.0, logger=logger)
        assert green == 10.0
        assert yellow == 20.0  # Default: green * 2
        assert red == 30.0

    def test_rtt_thresholds_with_none_red(self, logger):
        """Test thresholds with red=None (auto-default)."""
        green, yellow, red = validate_rtt_thresholds(10.0, 20.0, None, logger=logger)
        assert green == 10.0
        assert yellow == 20.0
        assert red == 30.0  # Default: green * 3

    def test_rtt_thresholds_small_values(self, logger):
        """Test very small RTT thresholds."""
        green, yellow, red = validate_rtt_thresholds(1.0, 2.0, 3.0, logger=logger)
        assert green == 1.0
        assert yellow == 2.0
        assert red == 3.0

    def test_rtt_thresholds_large_values(self, logger):
        """Test large RTT thresholds."""
        green, yellow, red = validate_rtt_thresholds(100.0, 200.0, 300.0, logger=logger)
        assert green == 100.0
        assert yellow == 200.0
        assert red == 300.0


# =============================================================================
# Tests for validate_sample_counts
# =============================================================================


class TestValidateSampleCounts:
    """Tests for validate_sample_counts function.

    validate_sample_counts accepts only red_samples_required and
    green_samples_required (no bad_samples/good_samples) and returns a 2-tuple.
    """

    def test_valid_sample_counts_defaults(self, logger):
        """Test valid sample counts with typical defaults."""
        red_req, green_req = validate_sample_counts(
            red_samples_required=2,
            green_samples_required=15,
            logger=logger,
        )
        assert red_req == 2
        assert green_req == 15

    def test_valid_sample_counts_all_one(self, logger):
        """Test minimum valid sample counts (all 1)."""
        red_req, green_req = validate_sample_counts(
            red_samples_required=1,
            green_samples_required=1,
            logger=logger,
        )
        assert red_req == 1
        assert green_req == 1

    def test_valid_sample_counts_large_values(self, logger):
        """Test large but reasonable sample counts."""
        red_req, green_req = validate_sample_counts(
            red_samples_required=50,
            green_samples_required=50,
            logger=logger,
        )
        assert red_req == 50
        assert green_req == 50

    def test_no_bad_samples_param(self, logger):
        """Test that bad_samples is no longer accepted as a parameter."""
        with pytest.raises(TypeError):
            validate_sample_counts(bad_samples=8, logger=logger)

    def test_no_good_samples_param(self, logger):
        """Test that good_samples is no longer accepted as a parameter."""
        with pytest.raises(TypeError):
            validate_sample_counts(good_samples=15, logger=logger)

    def test_red_samples_required_zero_invalid(self, logger):
        """Test that red_samples_required=0 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_sample_counts(red_samples_required=0, logger=logger)
        assert "red_samples_required" in str(exc_info.value)

    def test_green_samples_required_negative_invalid(self, logger):
        """Test that negative green_samples_required is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_sample_counts(green_samples_required=-10, logger=logger)
        assert "green_samples_required" in str(exc_info.value)

    def test_red_samples_required_too_high_invalid(self, logger):
        """Test that red_samples_required > 100 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_sample_counts(red_samples_required=500, logger=logger)
        assert "unreasonably high" in str(exc_info.value)

    def test_green_samples_required_too_high_invalid(self, logger):
        """Test that green_samples_required > 100 is invalid."""
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_sample_counts(green_samples_required=200, logger=logger)
        assert "unreasonably high" in str(exc_info.value)

    def test_returns_two_tuple(self, logger):
        """Test that return type is a 2-tuple (not 4-tuple)."""
        result = validate_sample_counts(logger=logger)
        assert isinstance(result, tuple)
        assert len(result) == 2


# =============================================================================
# Integration tests
# =============================================================================


class TestConfigValidationIntegration:
    """Integration tests combining multiple validation functions."""

    def test_full_autorate_config_validation(self, logger):
        """Test validation of typical autorate configuration."""
        # Download bandwidth validation
        validate_bandwidth_order(
            name="download",
            floor_red=5000000,
            floor_soft_red=10000000,
            floor_yellow=20000000,
            floor_green=50000000,
            ceiling=940000000,
            logger=logger,
        )

        # Thresholds validation
        validate_threshold_order(15.0, 45.0, 80.0, logger=logger)

        # EWMA alphas validation
        alpha_baseline = validate_alpha(0.001, "alpha_baseline", logger=logger)
        alpha_load = validate_alpha(0.35, "alpha_load", logger=logger)

        assert alpha_baseline == 0.001
        assert alpha_load == 0.35

    def test_full_steering_config_validation(self, logger):
        """Test validation of typical steering configuration."""
        # RTT thresholds
        green, yellow, red = validate_rtt_thresholds(5.0, 15.0, 30.0, logger=logger)

        # EWMA alphas
        rtt_alpha = validate_alpha(0.3, "rtt_ewma_alpha", logger=logger)
        queue_alpha = validate_alpha(0.2, "queue_ewma_alpha", logger=logger)

        # Baseline RTT (from state file)
        baseline = validate_baseline_rtt(24.0, logger=logger)

        # Sample counts
        red_req, green_req = validate_sample_counts(
            red_samples_required=2,
            green_samples_required=15,
            logger=logger,
        )

        assert green == 5.0
        assert rtt_alpha == 0.3
        assert queue_alpha == 0.2
        assert baseline == 24.0
        assert red_req == 2

    def test_configuration_validation_error_accumulation(self, logger):
        """Test that multiple validation errors are reported."""
        # Test bandwidth ordering error
        with pytest.raises(ConfigValidationError):
            validate_bandwidth_order(
                name="download",
                floor_red=100000000,
                floor_yellow=10000000,
                floor_green=50000000,
                ceiling=940000000,
                logger=logger,
            )

        # Test threshold ordering error
        with pytest.raises(ConfigValidationError):
            validate_threshold_order(50.0, 45.0, 80.0, logger=logger)

        # Test alpha bounds error
        with pytest.raises(ConfigValidationError):
            validate_alpha(1.5, "alpha", logger=logger)


# =============================================================================
# Tests for deprecate_param
# =============================================================================


class TestDeprecateParam:
    """Tests for deprecate_param helper function."""

    def test_old_key_absent_returns_none(self, logger):
        """deprecate_param returns None when old_key is not in config."""
        config = {"new_key": "value"}
        result = deprecate_param(config, "old_key", "new_key", logger)
        assert result is None

    def test_old_key_present_new_absent_returns_value(self, logger):
        """deprecate_param returns old value when old_key present and new_key absent."""
        config = {"old_key": "legacy_value"}
        result = deprecate_param(config, "old_key", "new_key", logger)
        assert result == "legacy_value"

    def test_both_keys_present_returns_none(self, logger):
        """deprecate_param returns None when both old and new keys present (modern wins)."""
        config = {"old_key": "legacy", "new_key": "modern"}
        result = deprecate_param(config, "old_key", "new_key", logger)
        assert result is None

    def test_logs_warning_with_old_and_new_names(self, logger, caplog):
        """deprecate_param logs warning containing old and new param names."""
        config = {"old_key": "legacy_value"}
        with caplog.at_level(logging.WARNING):
            deprecate_param(config, "old_key", "new_key", logger)
        assert any("old_key" in msg and "new_key" in msg for msg in caplog.messages)

    def test_no_warning_when_old_key_absent(self, logger, caplog):
        """deprecate_param does not log warning when old_key absent."""
        config = {"new_key": "value"}
        with caplog.at_level(logging.WARNING):
            deprecate_param(config, "old_key", "new_key", logger)
        assert not any("old_key" in msg for msg in caplog.messages)

    def test_no_warning_when_both_keys_present(self, logger, caplog):
        """deprecate_param does not log warning when both keys present."""
        config = {"old_key": "legacy", "new_key": "modern"}
        with caplog.at_level(logging.WARNING):
            deprecate_param(config, "old_key", "new_key", logger)
        assert not any("Deprecated" in msg for msg in caplog.messages)

    def test_transform_fn_applied(self, logger):
        """deprecate_param applies transform_fn to old value."""
        config = {"alpha_baseline": 0.001}
        result = deprecate_param(
            config,
            "alpha_baseline",
            "baseline_time_constant_sec",
            logger,
            transform_fn=lambda v: 0.05 / v,  # cycle_interval / alpha
        )
        assert result == pytest.approx(50.0)

    def test_transform_fn_not_called_when_absent(self, logger):
        """transform_fn is not called when old_key is absent."""
        called = []
        config = {"new_key": "value"}
        deprecate_param(
            config,
            "old_key",
            "new_key",
            logger,
            transform_fn=lambda v: called.append(v) or v,
        )
        assert called == []

    def test_warning_contains_translated_value(self, logger, caplog):
        """deprecate_param warning includes the translated value."""
        config = {"alpha_baseline": 0.001}
        with caplog.at_level(logging.WARNING):
            deprecate_param(
                config,
                "alpha_baseline",
                "baseline_time_constant_sec",
                logger,
                transform_fn=lambda v: 0.05 / v,
            )
        assert any("50.0" in msg for msg in caplog.messages)

    @pytest.mark.parametrize(
        "old_key,new_key,old_val,expected",
        [
            ("spectrum_download", "primary_download", "WAN-DL-Spectrum", "WAN-DL-Spectrum"),
            ("spectrum_upload", "primary_upload", "WAN-UL-Spectrum", "WAN-UL-Spectrum"),
            ("spectrum", "primary", "/run/spectrum.json", "/run/spectrum.json"),
        ],
    )
    def test_identity_transform_passthrough(self, logger, old_key, new_key, old_val, expected):
        """deprecate_param passes through value unchanged when no transform_fn."""
        config = {old_key: old_val}
        result = deprecate_param(config, old_key, new_key, logger)
        assert result == expected


# =============================================================================
# Tests for validate_retention_tuner_compat
# =============================================================================


class TestValidateRetentionTunerCompat:
    """Tests for retention-tuner cross-section validation."""

    def test_valid_equal_age_and_lookback(self, logger):
        """Config accepted when 1m age == lookback_hours * 3600 (equal is OK)."""
        from wanctl.config_validation_utils import validate_retention_tuner_compat

        validate_retention_tuner_compat(
            {"aggregate_1m_age_seconds": 86400},
            {"enabled": True, "lookback_hours": 24},
            logger=logger,
        )

    def test_rejects_insufficient_retention(self, logger):
        """Config rejected when 1m age < lookback_hours * 3600."""
        from wanctl.config_validation_utils import validate_retention_tuner_compat

        with pytest.raises(ConfigValidationError) as exc_info:
            validate_retention_tuner_compat(
                {"aggregate_1m_age_seconds": 43200},
                {"enabled": True, "lookback_hours": 24},
                logger=logger,
            )
        error_msg = str(exc_info.value)
        assert "aggregate_1m_age_seconds" in error_msg
        assert "lookback_hours" in error_msg

    def test_skips_when_tuning_disabled(self, logger):
        """Config accepted when tuning.enabled is False (no constraint)."""
        from wanctl.config_validation_utils import validate_retention_tuner_compat

        # Should not raise even though retention is too short
        validate_retention_tuner_compat(
            {"aggregate_1m_age_seconds": 43200},
            {"enabled": False, "lookback_hours": 24},
            logger=logger,
        )

    def test_skips_when_tuning_none(self, logger):
        """Config accepted when tuning_config is None."""
        from wanctl.config_validation_utils import validate_retention_tuner_compat

        validate_retention_tuner_compat(
            {"aggregate_1m_age_seconds": 43200},
            None,
            logger=logger,
        )

    def test_prometheus_compensated_warns_instead_of_raising(self, logger):
        """prometheus_compensated=True downgrades validation error to warning."""
        from unittest.mock import MagicMock

        from wanctl.config_validation_utils import validate_retention_tuner_compat

        mock_logger = MagicMock()
        # Should NOT raise despite insufficient retention
        validate_retention_tuner_compat(
            {"aggregate_1m_age_seconds": 43200, "prometheus_compensated": True},
            {"enabled": True, "lookback_hours": 24},
            logger=mock_logger,
        )
        assert mock_logger.warning.called

    def test_default_lookback_hours_used_when_absent(self, logger):
        """Defaults to lookback_hours=24 when key absent from tuning_config."""
        from wanctl.config_validation_utils import validate_retention_tuner_compat

        # 86400 == 24 * 3600, so equal is OK with default lookback
        validate_retention_tuner_compat(
            {"aggregate_1m_age_seconds": 86400},
            {"enabled": True},
            logger=logger,
        )

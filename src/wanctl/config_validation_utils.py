"""Configuration validation utilities for wanctl.

Consolidates common validation patterns used across the system:
- Bandwidth constraint validation (floor/ceiling ordering)
- Threshold ordering validation (target < warn < hard_red)
- EWMA alpha parameter validation (0.0 to 1.0)
- Baseline RTT bounds validation
- Queue/threshold state ordering
"""

import logging
from typing import Optional, Tuple

from wanctl.config_base import ConfigValidationError


# Default constants for baseline RTT validation
MIN_SANE_BASELINE_RTT = 10  # milliseconds - minimum sane baseline
MAX_SANE_BASELINE_RTT = 60  # milliseconds - maximum sane baseline


def validate_bandwidth_order(
    name: str,
    floor_red: int,
    floor_yellow: Optional[int] = None,
    floor_soft_red: Optional[int] = None,
    floor_green: Optional[int] = None,
    ceiling: Optional[int] = None,
    convert_to_mbps: bool = False,
    logger: logging.Logger = None
) -> bool:
    """Validate bandwidth floor and ceiling constraints.

    Ensures that bandwidth constraints are properly ordered:
    - For 3-state (GREEN/YELLOW/RED):
      floor_red <= floor_yellow <= floor_green <= ceiling
    - For 4-state (GREEN/YELLOW/SOFT_RED/RED):
      floor_red <= floor_soft_red <= floor_yellow <= floor_green <= ceiling

    Args:
        name: Name of bandwidth (e.g., "download", "upload") for error messages
        floor_red: RED state floor (required)
        floor_yellow: YELLOW state floor (optional, default: floor_red)
        floor_soft_red: SOFT_RED state floor (optional, for 4-state, default: floor_yellow)
        floor_green: GREEN state floor (optional, default: ceiling)
        ceiling: Maximum bandwidth (required for validation)
        convert_to_mbps: If True, convert values to Mbps for error messages
        logger: Logger instance (optional)

    Returns:
        True if ordering is valid

    Raises:
        ConfigValidationError: If ordering is violated
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Provide sensible defaults
    if floor_yellow is None:
        floor_yellow = floor_red
    if floor_soft_red is None:
        floor_soft_red = floor_yellow
    if floor_green is None:
        floor_green = ceiling

    # Validate ordering
    if not (floor_red <= floor_soft_red <= floor_yellow <= floor_green <= ceiling):
        if convert_to_mbps:
            # Convert to Mbps for display
            MBPS_TO_BPS = 1_000_000
            msg = (
                f"{name.capitalize()} floor ordering violation: expected "
                f"floor_red ({floor_red / MBPS_TO_BPS:.1f}M) <= "
                f"floor_soft_red ({floor_soft_red / MBPS_TO_BPS:.1f}M) <= "
                f"floor_yellow ({floor_yellow / MBPS_TO_BPS:.1f}M) <= "
                f"floor_green ({floor_green / MBPS_TO_BPS:.1f}M) <= "
                f"ceiling ({ceiling / MBPS_TO_BPS:.1f}M)"
            )
        else:
            msg = (
                f"{name.capitalize()} floor ordering violation: expected "
                f"floor_red ({floor_red}) <= "
                f"floor_soft_red ({floor_soft_red}) <= "
                f"floor_yellow ({floor_yellow}) <= "
                f"floor_green ({floor_green}) <= "
                f"ceiling ({ceiling})"
            )
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug(f"{name.capitalize()} bandwidth ordering valid")
    return True


def validate_threshold_order(
    target_bloat_ms: float,
    warn_bloat_ms: float,
    hard_red_bloat_ms: float,
    logger: logging.Logger = None
) -> bool:
    """Validate threshold ordering for congestion detection.

    Ensures thresholds are properly ordered:
    target_bloat_ms < warn_bloat_ms < hard_red_bloat_ms

    This ordering ensures correct state transitions:
    - GREEN: delta <= target_bloat_ms
    - YELLOW: target_bloat_ms < delta <= warn_bloat_ms
    - SOFT_RED/RED: delta > warn_bloat_ms

    Args:
        target_bloat_ms: GREEN->YELLOW threshold (milliseconds)
        warn_bloat_ms: YELLOW->RED threshold (milliseconds)
        hard_red_bloat_ms: Hard RED threshold (milliseconds)
        logger: Logger instance (optional)

    Returns:
        True if ordering is valid

    Raises:
        ConfigValidationError: If ordering is violated
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Validate target < warn
    if not (target_bloat_ms < warn_bloat_ms):
        msg = (
            f"Threshold ordering violation: target_bloat_ms ({target_bloat_ms}) "
            f"must be less than warn_bloat_ms ({warn_bloat_ms})"
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    # Validate warn < hard_red
    if not (warn_bloat_ms < hard_red_bloat_ms):
        msg = (
            f"Threshold ordering violation: warn_bloat_ms ({warn_bloat_ms}) "
            f"must be less than hard_red_bloat_ms ({hard_red_bloat_ms})"
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug("Bloat thresholds ordering valid")
    return True


def validate_alpha(
    value: float,
    field_name: str,
    min_val: float = 0.0,
    max_val: float = 1.0,
    logger: logging.Logger = None
) -> float:
    """Validate EWMA smoothing factor (alpha) is in valid range.

    EWMA alpha controls exponential weighted moving average:
    - alpha = 0.0: No smoothing (instant response to changes)
    - alpha = 0.5: Balanced smoothing
    - alpha = 1.0: Full smoothing (ignores new measurements)

    Typical values: 0.2 to 0.4

    Args:
        value: Alpha value to validate
        field_name: Name of field for error messages
        min_val: Minimum allowed value (default: 0.0)
        max_val: Maximum allowed value (default: 1.0)
        logger: Logger instance (optional)

    Returns:
        The validated float value

    Raises:
        ConfigValidationError: If alpha not in valid range
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        alpha = float(value)
    except (ValueError, TypeError) as e:
        msg = f"{field_name}: could not convert to float: {value} ({e})"
        logger.error(msg)
        raise ConfigValidationError(msg)

    if not (min_val <= alpha <= max_val):
        msg = (
            f"{field_name}: value {alpha} not in valid range [{min_val}, {max_val}]. "
            f"EWMA alpha must be between 0.0 (no smoothing) and 1.0 (full smoothing)"
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug(f"{field_name} alpha validation passed: {alpha}")
    return alpha


def validate_baseline_rtt(
    baseline_rtt_ms: float,
    min_ms: int = MIN_SANE_BASELINE_RTT,
    max_ms: int = MAX_SANE_BASELINE_RTT,
    logger: logging.Logger = None
) -> float:
    """Validate baseline RTT is within sane bounds.

    Baseline RTT represents latency when the line is unloaded. Extreme values
    indicate either:
    - Measurement errors
    - Corrupted state files
    - Network path changes

    Security fix C4: Validates baseline RTT to prevent malicious or corrupted
    values from destabilizing the steering system.

    Args:
        baseline_rtt_ms: Baseline RTT value in milliseconds
        min_ms: Minimum sane baseline (default: 10ms for typical ISP latency)
        max_ms: Maximum sane baseline (default: 60ms for extreme cases)
        logger: Logger instance (optional)

    Returns:
        The validated baseline RTT value

    Raises:
        ConfigValidationError: If baseline RTT out of sane bounds
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    baseline = float(baseline_rtt_ms)

    if baseline < min_ms:
        msg = (
            f"Baseline RTT {baseline:.1f}ms below minimum sane value {min_ms}ms. "
            f"This suggests measurement error or corrupted state."
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    if baseline > max_ms:
        msg = (
            f"Baseline RTT {baseline:.1f}ms exceeds maximum sane value {max_ms}ms. "
            f"This suggests network path change or corrupted state."
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug(f"Baseline RTT validation passed: {baseline:.1f}ms")
    return baseline


def validate_rtt_thresholds(
    green_rtt_ms: float,
    yellow_rtt_ms: Optional[float] = None,
    red_rtt_ms: Optional[float] = None,
    logger: logging.Logger = None
) -> Tuple[float, float, float]:
    """Validate RTT thresholds are properly ordered.

    Ensures RTT state transition thresholds are ordered:
    green_rtt_ms <= yellow_rtt_ms <= red_rtt_ms

    Used by steering daemon to determine congestion state based on RTT:
    - GREEN: delta < green_rtt_ms (healthy)
    - YELLOW: green_rtt_ms <= delta < yellow_rtt_ms (early warning)
    - RED: delta >= red_rtt_ms (confirmed congestion)

    Args:
        green_rtt_ms: GREEN state threshold (milliseconds)
        yellow_rtt_ms: YELLOW state threshold (default: green_rtt_ms * 2)
        red_rtt_ms: RED state threshold (default: green_rtt_ms * 3)
        logger: Logger instance (optional)

    Returns:
        Tuple of (green_rtt_ms, yellow_rtt_ms, red_rtt_ms)

    Raises:
        ConfigValidationError: If thresholds not properly ordered
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Provide defaults based on green threshold
    if yellow_rtt_ms is None:
        yellow_rtt_ms = green_rtt_ms * 2
    if red_rtt_ms is None:
        red_rtt_ms = green_rtt_ms * 3

    # Validate ordering
    if not (green_rtt_ms <= yellow_rtt_ms <= red_rtt_ms):
        msg = (
            f"RTT threshold ordering violation: expected "
            f"green_rtt_ms ({green_rtt_ms:.1f}ms) <= "
            f"yellow_rtt_ms ({yellow_rtt_ms:.1f}ms) <= "
            f"red_rtt_ms ({red_rtt_ms:.1f}ms)"
        )
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug(
        f"RTT thresholds valid: GREEN={green_rtt_ms:.1f}ms, "
        f"YELLOW={yellow_rtt_ms:.1f}ms, RED={red_rtt_ms:.1f}ms"
    )
    return (float(green_rtt_ms), float(yellow_rtt_ms), float(red_rtt_ms))


def validate_sample_counts(
    bad_samples: int = 8,
    good_samples: int = 15,
    red_samples_required: int = 2,
    green_samples_required: int = 15,
    logger: logging.Logger = None
) -> Tuple[int, int, int, int]:
    """Validate state confirmation sample requirements are reasonable.

    Sample counts determine how many consecutive measurements with the same
    characteristic are needed to confirm a state transition.

    Args:
        bad_samples: Legacy - samples needed to confirm bad state (deprecated)
        good_samples: Legacy - samples needed to confirm recovery
        red_samples_required: Samples needed to confirm RED state (new)
        green_samples_required: Samples needed to confirm GREEN state (new)
        logger: Logger instance (optional)

    Returns:
        Tuple of (bad_samples, good_samples, red_samples_required, green_samples_required)

    Raises:
        ConfigValidationError: If sample counts are unreasonable
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    errors = []

    if bad_samples < 1:
        errors.append(f"bad_samples ({bad_samples}) must be >= 1")
    if good_samples < 1:
        errors.append(f"good_samples ({good_samples}) must be >= 1")
    if red_samples_required < 1:
        errors.append(f"red_samples_required ({red_samples_required}) must be >= 1")
    if green_samples_required < 1:
        errors.append(f"green_samples_required ({green_samples_required}) must be >= 1")

    # Check reasonableness (not too extreme)
    if bad_samples > 1000:
        errors.append(f"bad_samples ({bad_samples}) unreasonably high (max 1000)")
    if good_samples > 1000:
        errors.append(f"good_samples ({good_samples}) unreasonably high (max 1000)")
    if red_samples_required > 100:
        errors.append(f"red_samples_required ({red_samples_required}) unreasonably high (max 100)")
    if green_samples_required > 100:
        errors.append(f"green_samples_required ({green_samples_required}) unreasonably high (max 100)")

    if errors:
        msg = "Sample count validation failed:\n  - " + "\n  - ".join(errors)
        logger.error(msg)
        raise ConfigValidationError(msg)

    logger.debug(
        f"Sample counts valid: bad={bad_samples}, good={good_samples}, "
        f"red_required={red_samples_required}, green_required={green_samples_required}"
    )
    return (bad_samples, good_samples, red_samples_required, green_samples_required)

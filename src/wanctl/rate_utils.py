"""
Rate bounds enforcement utilities.

Consolidates repeated rate limiting and bounding logic used throughout
autorate_continuous.py (5+ instances).

Handles enforcement of floor (minimum) and ceiling (maximum) constraints
on bandwidth rates.
"""

from typing import Optional


def enforce_rate_bounds(
    rate: float,
    floor: Optional[float] = None,
    ceiling: Optional[float] = None,
) -> int:
    """
    Enforce floor and ceiling constraints on a bandwidth rate.

    Applies boundary constraints in order: floor first, then ceiling.
    Ensures rate >= floor and rate <= ceiling when boundaries are specified.

    Args:
        rate: The current rate to constrain (in bps)
        floor: Minimum allowed rate (None = no floor constraint). Typically
               represents minimum acceptable bandwidth during congestion.
        ceiling: Maximum allowed rate (None = no ceiling constraint). Typically
                represents maximum link capacity.

    Returns:
        Bounded rate as integer (in bps) within specified constraints.
        If both floor and ceiling are None, returns rate as-is.

    Raises:
        ValueError: If floor > ceiling (inconsistent constraints)

    Examples:
        >>> enforce_rate_bounds(50_000_000, floor=20_000_000, ceiling=100_000_000)
        50000000  # Within bounds

        >>> enforce_rate_bounds(10_000_000, floor=20_000_000, ceiling=100_000_000)
        20000000  # Below floor, clamped up

        >>> enforce_rate_bounds(150_000_000, floor=20_000_000, ceiling=100_000_000)
        100000000  # Above ceiling, clamped down

        >>> enforce_rate_bounds(50_000_000, floor=None, ceiling=100_000_000)
        50000000  # No floor, respects ceiling

        >>> enforce_rate_bounds(50_000_000, floor=20_000_000, ceiling=None)
        50000000  # No ceiling, respects floor
    """
    result = float(rate)

    # Apply floor constraint (minimum)
    if floor is not None:
        result = max(result, floor)

    # Apply ceiling constraint (maximum)
    if ceiling is not None:
        result = min(result, ceiling)

    # Validate constraint consistency
    if floor is not None and ceiling is not None and floor > ceiling:
        raise ValueError(
            f"Invalid rate bounds: floor ({floor}) cannot exceed ceiling ({ceiling})"
        )

    return int(result)


def enforce_floor(rate: float, floor: Optional[float] = None) -> int:
    """
    Enforce minimum floor constraint on a bandwidth rate.

    Ensures rate >= floor when floor is specified.
    Convenience function when only floor constraint is needed.

    Args:
        rate: The current rate to constrain (in bps)
        floor: Minimum allowed rate (None = no constraint)

    Returns:
        Rate as integer, at least floor if specified.

    Examples:
        >>> enforce_floor(50_000_000, floor=20_000_000)
        50000000

        >>> enforce_floor(10_000_000, floor=20_000_000)
        20000000

        >>> enforce_floor(50_000_000, floor=None)
        50000000
    """
    return enforce_rate_bounds(rate, floor=floor, ceiling=None)


def enforce_ceiling(rate: float, ceiling: Optional[float] = None) -> int:
    """
    Enforce maximum ceiling constraint on a bandwidth rate.

    Ensures rate <= ceiling when ceiling is specified.
    Convenience function when only ceiling constraint is needed.

    Args:
        rate: The current rate to constrain (in bps)
        ceiling: Maximum allowed rate (None = no constraint)

    Returns:
        Rate as integer, at most ceiling if specified.

    Examples:
        >>> enforce_ceiling(150_000_000, ceiling=100_000_000)
        100000000

        >>> enforce_ceiling(50_000_000, ceiling=100_000_000)
        50000000

        >>> enforce_ceiling(50_000_000, ceiling=None)
        50000000
    """
    return enforce_rate_bounds(rate, floor=None, ceiling=ceiling)

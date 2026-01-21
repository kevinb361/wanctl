"""
Rate utilities: bounds enforcement and rate limiting.

Consolidates rate-related utilities used throughout autorate_continuous.py:
- Rate bounds enforcement (floor/ceiling constraints on bandwidth)
- Rate limiting for configuration changes (sliding window approach)

Handles enforcement of floor (minimum) and ceiling (maximum) constraints
on bandwidth rates, plus protection against rapid configuration changes.
"""

import time
from collections import deque


def enforce_rate_bounds(
    rate: float,
    floor: float | None = None,
    ceiling: float | None = None,
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
    # Validate constraint consistency FIRST (before applying bounds)
    if floor is not None and ceiling is not None and floor > ceiling:
        raise ValueError(f"Invalid rate bounds: floor ({floor}) cannot exceed ceiling ({ceiling})")

    result = float(rate)

    # Apply floor constraint (minimum)
    if floor is not None:
        result = max(result, floor)

    # Apply ceiling constraint (maximum)
    if ceiling is not None:
        result = min(result, ceiling)

    return int(result)


def enforce_floor(rate: float, floor: float | None = None) -> int:
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


def enforce_ceiling(rate: float, ceiling: float | None = None) -> int:
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


class RateLimiter:
    """Limit rate of configuration changes using sliding window.

    Prevents overloading the router API during instability by limiting
    the number of configuration changes allowed within a time window.

    Attributes:
        max_changes: Maximum number of changes allowed in the window.
        window_seconds: Time window in seconds for rate limiting.

    Example:
        >>> limiter = RateLimiter(max_changes=10, window_seconds=60)
        >>> if limiter.can_change():
        ...     # Make the change
        ...     limiter.record_change()
        ... else:
        ...     # Rate limited, skip this update
        ...     pass
    """

    def __init__(self, max_changes: int = 10, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_changes: Maximum allowed changes within window (default: 10).
            window_seconds: Sliding window duration in seconds (default: 60).

        Raises:
            ValueError: If max_changes or window_seconds are not positive.
        """
        if max_changes <= 0:
            raise ValueError(f"max_changes must be positive, got {max_changes}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")

        self.max_changes = max_changes
        self.window_seconds = window_seconds
        # Use deque with maxlen for automatic old entry removal
        self.change_times: deque[float] = deque(maxlen=max_changes)

    def can_change(self) -> bool:
        """Check if a change is allowed under current rate limits.

        Removes stale entries outside the time window before checking.

        Returns:
            True if change is allowed, False if rate limited.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Remove changes outside the window (from the front of deque)
        while self.change_times and self.change_times[0] < cutoff:
            self.change_times.popleft()

        return len(self.change_times) < self.max_changes

    def record_change(self) -> None:
        """Record that a configuration change was made.

        Should be called after a successful change is applied.
        Uses monotonic time to avoid issues with system clock changes.
        """
        self.change_times.append(time.monotonic())

    def changes_remaining(self) -> int:
        """Return number of changes still allowed in current window.

        Useful for logging/debugging the rate limiter state.

        Returns:
            Number of additional changes allowed before rate limiting.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Count only changes within the window
        while self.change_times and self.change_times[0] < cutoff:
            self.change_times.popleft()

        return max(0, self.max_changes - len(self.change_times))

    def time_until_available(self) -> float:
        """Return seconds until next change is allowed (0 if available now).

        Useful for logging when rate limited.

        Returns:
            Seconds until a change slot becomes available, or 0.0 if available.
        """
        if self.can_change():
            return 0.0

        # Calculate when the oldest change will expire from the window
        if self.change_times:
            now = time.monotonic()
            oldest = self.change_times[0]
            return max(0.0, (oldest + self.window_seconds) - now)

        return 0.0

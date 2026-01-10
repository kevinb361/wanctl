"""
Rate limiter for configuration changes.

Protects against rapid configuration changes during instability,
which could cause router API overload or excessive flash wear.

Uses a sliding window approach to limit changes per time period.
"""

import time
from collections import deque


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

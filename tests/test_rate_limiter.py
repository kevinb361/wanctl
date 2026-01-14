"""Tests for rate_limiter module - rate limiting for configuration changes."""

import time
from unittest.mock import patch

import pytest

from wanctl.rate_utils import RateLimiter


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    def test_default_values(self):
        """Test that default values are applied correctly."""
        limiter = RateLimiter()
        assert limiter.max_changes == 10
        assert limiter.window_seconds == 60

    def test_custom_values(self):
        """Test that custom values are applied correctly."""
        limiter = RateLimiter(max_changes=5, window_seconds=30)
        assert limiter.max_changes == 5
        assert limiter.window_seconds == 30

    def test_invalid_max_changes_zero(self):
        """Test that max_changes=0 raises ValueError."""
        with pytest.raises(ValueError, match="max_changes must be positive"):
            RateLimiter(max_changes=0)

    def test_invalid_max_changes_negative(self):
        """Test that negative max_changes raises ValueError."""
        with pytest.raises(ValueError, match="max_changes must be positive"):
            RateLimiter(max_changes=-1)

    def test_invalid_window_seconds_zero(self):
        """Test that window_seconds=0 raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be positive"):
            RateLimiter(window_seconds=0)

    def test_invalid_window_seconds_negative(self):
        """Test that negative window_seconds raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be positive"):
            RateLimiter(window_seconds=-1)

    def test_initial_deque_empty(self):
        """Test that change_times deque starts empty."""
        limiter = RateLimiter()
        assert len(limiter.change_times) == 0


class TestCanChange:
    """Tests for can_change method."""

    def test_can_change_when_empty(self):
        """Test that changes are allowed when no prior changes."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        assert limiter.can_change() is True

    def test_can_change_under_limit(self):
        """Test that changes are allowed when under limit."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        for _ in range(4):
            limiter.record_change()
        assert limiter.can_change() is True

    def test_cannot_change_at_limit(self):
        """Test that changes are blocked when at limit."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        for _ in range(5):
            limiter.record_change()
        assert limiter.can_change() is False

    def test_old_changes_expire(self):
        """Test that old changes expire from the window."""
        limiter = RateLimiter(max_changes=2, window_seconds=1)

        # Record 2 changes (at limit)
        limiter.record_change()
        limiter.record_change()
        assert limiter.can_change() is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.can_change() is True

    def test_partial_expiration(self):
        """Test that only old changes expire, not new ones."""
        limiter = RateLimiter(max_changes=2, window_seconds=1)

        # Record first change
        limiter.record_change()
        time.sleep(0.6)

        # Record second change (at limit)
        limiter.record_change()
        assert limiter.can_change() is False

        # Wait for first to expire, second still valid
        time.sleep(0.5)

        # Should be allowed (first expired, second still valid)
        assert limiter.can_change() is True


class TestRecordChange:
    """Tests for record_change method."""

    def test_record_change_adds_entry(self):
        """Test that record_change adds an entry."""
        limiter = RateLimiter(max_changes=10, window_seconds=60)
        assert len(limiter.change_times) == 0

        limiter.record_change()
        assert len(limiter.change_times) == 1

    def test_multiple_records(self):
        """Test multiple record_change calls."""
        limiter = RateLimiter(max_changes=10, window_seconds=60)

        for i in range(5):
            limiter.record_change()
            assert len(limiter.change_times) == i + 1

    def test_deque_maxlen_enforced(self):
        """Test that deque maxlen prevents overflow."""
        limiter = RateLimiter(max_changes=3, window_seconds=60)

        # Record more than max_changes
        for _ in range(5):
            limiter.record_change()

        # Deque maxlen should limit to max_changes
        assert len(limiter.change_times) == 3


class TestChangesRemaining:
    """Tests for changes_remaining method."""

    def test_changes_remaining_when_empty(self):
        """Test changes_remaining when no prior changes."""
        limiter = RateLimiter(max_changes=10, window_seconds=60)
        assert limiter.changes_remaining() == 10

    def test_changes_remaining_after_some_changes(self):
        """Test changes_remaining after some changes."""
        limiter = RateLimiter(max_changes=10, window_seconds=60)
        for _ in range(3):
            limiter.record_change()
        assert limiter.changes_remaining() == 7

    def test_changes_remaining_at_limit(self):
        """Test changes_remaining when at limit."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        for _ in range(5):
            limiter.record_change()
        assert limiter.changes_remaining() == 0

    def test_changes_remaining_after_expiration(self):
        """Test changes_remaining after some changes expire."""
        limiter = RateLimiter(max_changes=5, window_seconds=1)
        for _ in range(5):
            limiter.record_change()
        assert limiter.changes_remaining() == 0

        time.sleep(1.1)
        assert limiter.changes_remaining() == 5


class TestTimeUntilAvailable:
    """Tests for time_until_available method."""

    def test_time_until_available_when_available(self):
        """Test time_until_available returns 0 when available."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        assert limiter.time_until_available() == 0.0

    def test_time_until_available_when_under_limit(self):
        """Test time_until_available returns 0 when under limit."""
        limiter = RateLimiter(max_changes=5, window_seconds=60)
        for _ in range(3):
            limiter.record_change()
        assert limiter.time_until_available() == 0.0

    def test_time_until_available_when_limited(self):
        """Test time_until_available returns positive when limited."""
        limiter = RateLimiter(max_changes=2, window_seconds=10)
        limiter.record_change()
        limiter.record_change()

        wait_time = limiter.time_until_available()

        # Should be approximately 10 seconds (window_seconds)
        assert 9.0 <= wait_time <= 10.0

    def test_time_until_available_decreases(self):
        """Test time_until_available decreases over time."""
        limiter = RateLimiter(max_changes=1, window_seconds=2)
        limiter.record_change()

        wait1 = limiter.time_until_available()
        time.sleep(0.5)
        wait2 = limiter.time_until_available()

        # Second wait should be ~0.5s less
        assert wait2 < wait1
        assert (wait1 - wait2) > 0.4


class TestMonotonicTime:
    """Tests verifying monotonic time is used (not wall clock)."""

    def test_uses_monotonic_time(self):
        """Test that monotonic time is used, not wall clock."""
        limiter = RateLimiter(max_changes=2, window_seconds=60)

        # Mock time.monotonic to control time
        with patch("wanctl.rate_utils.time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            limiter.record_change()

            mock_time.return_value = 101.0
            limiter.record_change()

            # At limit
            assert limiter.can_change() is False

            # Advance time past window
            mock_time.return_value = 161.0
            assert limiter.can_change() is True


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_change_limit(self):
        """Test rate limiter with max_changes=1."""
        limiter = RateLimiter(max_changes=1, window_seconds=60)

        assert limiter.can_change() is True
        limiter.record_change()
        assert limiter.can_change() is False

    def test_very_short_window(self):
        """Test rate limiter with very short window."""
        limiter = RateLimiter(max_changes=10, window_seconds=1)

        for _ in range(10):
            limiter.record_change()
        assert limiter.can_change() is False

        time.sleep(1.1)
        assert limiter.can_change() is True

    def test_concurrent_like_behavior(self):
        """Test rapid sequential calls (simulating concurrent access)."""
        limiter = RateLimiter(max_changes=100, window_seconds=60)

        # Rapid fire 100 changes
        for _ in range(100):
            assert limiter.can_change() is True
            limiter.record_change()

        # 101st should be blocked
        assert limiter.can_change() is False

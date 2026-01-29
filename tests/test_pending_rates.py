"""Tests for PendingRateChange class.

Verifies rate change queuing, clearing, staleness detection, and
overwrite behavior for router outage resilience (ERRR-03).
"""

from unittest.mock import patch

from wanctl.pending_rates import PendingRateChange


class TestPendingRateChange:
    """Tests for PendingRateChange queue/clear/has_pending/is_stale."""

    def test_has_pending_false_initially(self):
        """New instance should have no pending changes."""
        pending = PendingRateChange()
        assert pending.has_pending() is False

    def test_queue_stores_rates(self):
        """queue() should store download and upload rates."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)

        assert pending.pending_dl_rate == 800_000_000
        assert pending.pending_ul_rate == 35_000_000
        assert pending.queued_at is not None

    def test_has_pending_true_after_queue(self):
        """has_pending() should return True after queuing rates."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)
        assert pending.has_pending() is True

    def test_queue_overwrites_previous(self):
        """Queuing new rates should overwrite previous pending rates."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)
        pending.queue(dl_rate=700_000_000, ul_rate=30_000_000)

        assert pending.pending_dl_rate == 700_000_000
        assert pending.pending_ul_rate == 30_000_000

    def test_clear_resets_state(self):
        """clear() should reset all pending state to None."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)
        pending.clear()

        assert pending.pending_dl_rate is None
        assert pending.pending_ul_rate is None
        assert pending.queued_at is None
        assert pending.has_pending() is False

    def test_is_stale_false_when_no_pending(self):
        """is_stale() should return False when no rates are queued."""
        pending = PendingRateChange()
        assert pending.is_stale() is False

    def test_is_stale_false_when_recent(self):
        """is_stale() should return False for recently queued rates."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)
        assert pending.is_stale(max_age_seconds=60.0) is False

    def test_is_stale_true_after_threshold(self):
        """is_stale() should return True when rate is older than threshold."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)

        # Simulate time passing by setting queued_at to the past
        with patch("wanctl.pending_rates.time") as mock_time:
            # First call for queue sets timestamp at 1000.0
            # Second call for is_stale returns 1061.0 (61 seconds later)
            mock_time.monotonic.return_value = 1061.0
            pending.queued_at = 1000.0  # Set directly for deterministic test
            assert pending.is_stale(max_age_seconds=60.0) is True

    def test_is_stale_custom_threshold(self):
        """is_stale() should respect custom max_age_seconds."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)

        with patch("wanctl.pending_rates.time") as mock_time:
            mock_time.monotonic.return_value = 1011.0
            pending.queued_at = 1000.0
            # 11 seconds old, 10 second threshold
            assert pending.is_stale(max_age_seconds=10.0) is True
            # 11 seconds old, 30 second threshold
            assert pending.is_stale(max_age_seconds=30.0) is False

    def test_queue_updates_timestamp(self):
        """Each queue() call should update the queued_at timestamp."""
        pending = PendingRateChange()
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)
        first_time = pending.queued_at

        pending.queue(dl_rate=700_000_000, ul_rate=30_000_000)
        second_time = pending.queued_at

        # Second timestamp should be >= first (monotonic)
        assert second_time is not None
        assert first_time is not None
        assert second_time >= first_time

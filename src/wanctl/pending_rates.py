"""Pending rate change tracking for router outage resilience.

When the router is unreachable, calculated rate changes are queued here
instead of being discarded. When connectivity is restored, the most recent
queued rate can be applied immediately.

This implements ERRR-03: Rate limits are never removed on error.
"""

import time


class PendingRateChange:
    """Track rate changes during router outage for later application.

    Maintains the most recent calculated rate change with a monotonic timestamp.
    Older rates are overwritten since only the latest calculation is relevant.
    Stale rates (older than max_age_seconds) are discarded on reconnection
    to avoid applying outdated bandwidth limits.

    Example:
        pending = PendingRateChange()

        # Router unreachable - queue the rate
        pending.queue(dl_rate=800_000_000, ul_rate=35_000_000)

        # Later, when router reconnects
        if pending.has_pending() and not pending.is_stale():
            apply(pending.pending_dl_rate, pending.pending_ul_rate)
            pending.clear()
    """

    def __init__(self) -> None:
        self.pending_dl_rate: int | None = None
        self.pending_ul_rate: int | None = None
        self.queued_at: float | None = None  # monotonic timestamp

    def queue(self, dl_rate: int, ul_rate: int) -> None:
        """Queue a rate change (overwrites previous pending).

        Args:
            dl_rate: Download rate in bits per second
            ul_rate: Upload rate in bits per second
        """
        self.pending_dl_rate = dl_rate
        self.pending_ul_rate = ul_rate
        self.queued_at = time.monotonic()

    def clear(self) -> None:
        """Clear pending changes after successful application."""
        self.pending_dl_rate = None
        self.pending_ul_rate = None
        self.queued_at = None

    def has_pending(self) -> bool:
        """Check if there are pending changes."""
        return self.pending_dl_rate is not None and self.pending_ul_rate is not None

    def is_stale(self, max_age_seconds: float = 60.0) -> bool:
        """Check if pending rate is older than threshold.

        Stale rates should be discarded rather than applied, since the
        network conditions may have changed significantly.

        Args:
            max_age_seconds: Maximum age in seconds before rates are
                considered stale. Default 60.0 seconds.

        Returns:
            True if pending rate exists and is older than max_age_seconds.
            False if no pending rate or rate is recent enough.
        """
        if self.queued_at is None:
            return False
        age = time.monotonic() - self.queued_at
        return age > max_age_seconds

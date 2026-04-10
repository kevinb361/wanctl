"""Background thread for CAKE qdisc stats collection.

Offloads netlink tc("dump") calls from the main control loop to a dedicated
daemon thread with its own IPRoute connection (thread-safe by isolation).

The main loop reads cached stats via get_latest() (GIL-protected pointer
swap, lock-free) instead of blocking on 7-20ms netlink I/O per cycle.

Pattern follows BackgroundRTTThread from rtt_measurement.py.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CakeStatsSnapshot:
    """Immutable snapshot of CAKE stats for both directions."""

    dl_stats: dict[str, Any] | None
    ul_stats: dict[str, Any] | None
    timestamp: float  # time.monotonic()
    measurement_ms: float


class BackgroundCakeStatsThread:
    """Dedicated background thread for CAKE qdisc stats reads.

    Creates its own NetlinkCakeBackend instances with independent IPRoute
    connections so there's no thread-safety issue with the main thread's
    backends (which handle set_bandwidth).

    Args:
        dl_interface: Download interface name (e.g. "ens17")
        ul_interface: Upload interface name (e.g. "ens16")
        shutdown_event: threading.Event signaling graceful shutdown
        cadence_sec: Seconds between reads (default 0.05 = 20Hz, matching cycle)
    """

    def __init__(
        self,
        dl_interface: str,
        ul_interface: str,
        shutdown_event: threading.Event,
        cadence_sec: float = 0.05,
    ) -> None:
        self._dl_interface = dl_interface
        self._ul_interface = ul_interface
        self._shutdown_event = shutdown_event
        self._cadence_sec = cadence_sec
        self._cached: CakeStatsSnapshot | None = None
        self._thread: threading.Thread | None = None

    def get_latest(self) -> CakeStatsSnapshot | None:
        """Return the most recent stats snapshot, or None if not yet available."""
        return self._cached

    def start(self) -> None:
        """Create and start the background daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-cake-stats-bg",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Background CAKE stats thread started (DL=%s, UL=%s, cadence=%.0fms)",
            self._dl_interface,
            self._ul_interface,
            self._cadence_sec * 1000,
        )

    def stop(self) -> None:
        """Join the background thread (up to 5s timeout)."""
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            logger.info("Background CAKE stats thread stopped")

    def _run(self) -> None:
        """Stats collection loop — runs until shutdown_event is set."""
        from wanctl.backends.netlink_cake import NetlinkCakeBackend

        # Create dedicated backends with their own IPRoute connections
        dl_backend = NetlinkCakeBackend(interface=self._dl_interface)
        ul_backend = NetlinkCakeBackend(interface=self._ul_interface)

        while not self._shutdown_event.is_set():
            elapsed_s = 0.0
            try:
                t0 = time.perf_counter()
                dl_stats = dl_backend.get_queue_stats("")
                ul_stats = ul_backend.get_queue_stats("")
                elapsed_s = time.perf_counter() - t0

                self._cached = CakeStatsSnapshot(
                    dl_stats=dl_stats,
                    ul_stats=ul_stats,
                    timestamp=time.monotonic(),
                    measurement_ms=elapsed_s * 1000.0,
                )
            except Exception:
                logger.debug("Background CAKE stats error", exc_info=True)

            sleep_s = max(0.0, self._cadence_sec - elapsed_s)
            self._shutdown_event.wait(timeout=sleep_s)

        # Cleanup IPRoute connections
        dl_backend._reset_ipr()
        ul_backend._reset_ipr()

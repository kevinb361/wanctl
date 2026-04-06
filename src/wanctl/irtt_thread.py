"""Background IRTT measurement thread.

Runs :meth:`IRTTMeasurement.measure` on a configurable cadence (default 10 s)
in a daemon thread, caching the latest result for lock-free reads via
:meth:`get_latest`.  Assignment of a frozen dataclass to ``self._cached_result``
is atomic at the Python level (GIL-protected pointer swap), so no explicit
lock is needed.
"""

from __future__ import annotations

import logging
import threading

from wanctl.irtt_measurement import IRTTMeasurement, IRTTResult


class IRTTThread:
    """Coordinate background IRTT measurements on a fixed cadence.

    Args:
        measurement: Configured :class:`IRTTMeasurement` instance.
        cadence_sec: Seconds between measurement bursts.
        shutdown_event: :class:`threading.Event` that signals graceful shutdown.
        logger: Logger for lifecycle and error messages.
    """

    def __init__(
        self,
        measurement: IRTTMeasurement,
        cadence_sec: float,
        shutdown_event: threading.Event,
        logger: logging.Logger,
    ) -> None:
        self._measurement = measurement
        self._cadence_sec = cadence_sec
        self._shutdown_event = shutdown_event
        self._logger = logger
        self._cached_result: IRTTResult | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cadence_sec(self) -> float:
        """IRTT measurement cadence in seconds."""
        return self._cadence_sec

    def get_latest(self) -> IRTTResult | None:
        """Return the most recent successful measurement, or ``None``."""
        return self._cached_result

    def start(self) -> None:
        """Create and start the background daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-irtt",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(f"IRTT thread started (cadence={self._cadence_sec}s)")

    def stop(self) -> None:
        """Join the background thread (up to 5 s timeout)."""
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._logger.info("IRTT thread stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Measurement loop -- runs until *shutdown_event* is set."""
        while not self._shutdown_event.is_set():
            try:
                result = self._measurement.measure()
                if result is not None:
                    self._cached_result = result
            except Exception:
                self._logger.debug("IRTT measurement error", exc_info=True)
            self._shutdown_event.wait(timeout=self._cadence_sec)

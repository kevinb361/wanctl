"""Background I/O worker for deferred SQLite metrics writes.

Offloads MetricsWriter calls to a daemon thread via queue.SimpleQueue,
removing variable-latency disk I/O from the 50ms control loop hot path.

Pattern: Follows BackgroundRTTThread (rtt_measurement.py) -- daemon thread,
shutdown_event, sentinel-based drain, join with timeout.
"""

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any

_SENTINEL = object()


@dataclass(frozen=True, slots=True)
class _BatchWrite:
    metrics: tuple[tuple[int, str, str, float, dict[str, Any] | None, str], ...]


@dataclass(frozen=True, slots=True)
class _SingleWrite:
    timestamp: int
    wan_name: str
    metric_name: str
    value: float
    labels: dict[str, Any] | None
    granularity: str


@dataclass(frozen=True, slots=True)
class _AlertWrite:
    timestamp: int
    alert_type: str
    severity: str
    wan_name: str
    details_json: str


@dataclass(frozen=True, slots=True)
class _ReflectorEventWrite:
    timestamp: int
    event_type: str
    host: str
    wan_name: str
    score: float
    details_json: str


class DeferredIOWorker:
    """Background thread consuming MetricsWriter requests from a queue.

    The control loop enqueues write payloads (dataclass instances) into a
    :class:`queue.SimpleQueue` and returns immediately.  A daemon thread
    drains the queue, dispatching each item to the appropriate
    :class:`MetricsWriter` method.

    Lifecycle::

        worker = DeferredIOWorker(writer, shutdown_event, logger)
        worker.start()          # spawns daemon thread
        worker.enqueue_batch(…) # non-blocking, called from hot path
        worker.stop()           # sentinel + join, drains remaining items
    """

    def __init__(
        self,
        writer: Any,  # MetricsWriter (use Any to avoid circular import)
        shutdown_event: threading.Event,
        logger: logging.Logger,
    ) -> None:
        self._writer = writer
        self._shutdown_event = shutdown_event
        self._logger = logger
        self._queue: queue.SimpleQueue[Any] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._pending_count: int = 0
        self._count_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API (called from hot path -- must never block)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create and start the background daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-io-worker",
            daemon=True,
        )
        self._thread.start()
        self._logger.info("Deferred I/O worker started")

    def stop(self) -> None:
        """Send sentinel and join background thread (up to 5s timeout)."""
        self._queue.put(_SENTINEL)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._logger.info("Deferred I/O worker stopped")

    def enqueue_batch(
        self,
        metrics: list[tuple[int, str, str, float, dict[str, Any] | None, str]],
    ) -> None:
        """Enqueue a batch of metrics for background write."""
        self._queue.put(_BatchWrite(metrics=tuple(metrics)))
        with self._count_lock:
            self._pending_count += 1

    def enqueue_write(
        self,
        *,
        timestamp: int,
        wan_name: str,
        metric_name: str,
        value: float,
        labels: dict[str, Any] | None = None,
        granularity: str = "raw",
    ) -> None:
        """Enqueue a single metric write."""
        self._queue.put(
            _SingleWrite(
                timestamp=timestamp,
                wan_name=wan_name,
                metric_name=metric_name,
                value=value,
                labels=labels,
                granularity=granularity,
            )
        )
        with self._count_lock:
            self._pending_count += 1

    def enqueue_alert(
        self,
        *,
        timestamp: int,
        alert_type: str,
        severity: str,
        wan_name: str,
        details_json: str,
    ) -> None:
        """Enqueue an alert write."""
        self._queue.put(
            _AlertWrite(
                timestamp=timestamp,
                alert_type=alert_type,
                severity=severity,
                wan_name=wan_name,
                details_json=details_json,
            )
        )
        with self._count_lock:
            self._pending_count += 1

    def enqueue_reflector_event(
        self,
        *,
        timestamp: int,
        event_type: str,
        host: str,
        wan_name: str,
        score: float,
        details_json: str,
    ) -> None:
        """Enqueue a reflector event write."""
        self._queue.put(
            _ReflectorEventWrite(
                timestamp=timestamp,
                event_type=event_type,
                host=host,
                wan_name=wan_name,
                score=score,
                details_json=details_json,
            )
        )
        with self._count_lock:
            self._pending_count += 1

    @property
    def pending_count(self) -> int:
        """Number of items queued but not yet processed."""
        with self._count_lock:
            return self._pending_count

    @property
    def is_alive(self) -> bool:
        """Whether the background thread is currently running."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal consumer loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Consumer loop -- runs until sentinel or shutdown_event."""
        while True:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._shutdown_event.is_set():
                    break
                continue
            if item is _SENTINEL:
                self._drain_remaining()
                break
            self._process_item(item)

    def _drain_remaining(self) -> None:
        """Process all items remaining in the queue after sentinel."""
        while True:
            try:
                item = self._queue.get_nowait()
                if item is not _SENTINEL:
                    self._process_item(item)
            except queue.Empty:
                break

    def _process_item(self, item: Any) -> None:
        """Dispatch a queued item to the appropriate writer method."""
        try:
            if isinstance(item, _BatchWrite):
                self._writer.write_metrics_batch(list(item.metrics))
            elif isinstance(item, _SingleWrite):
                self._writer.write_metric(
                    timestamp=item.timestamp,
                    wan_name=item.wan_name,
                    metric_name=item.metric_name,
                    value=item.value,
                    labels=item.labels,
                    granularity=item.granularity,
                )
            elif isinstance(item, _AlertWrite):
                self._writer.write_alert(
                    timestamp=item.timestamp,
                    alert_type=item.alert_type,
                    severity=item.severity,
                    wan_name=item.wan_name,
                    details_json=item.details_json,
                )
            elif isinstance(item, _ReflectorEventWrite):
                self._writer.write_reflector_event(
                    timestamp=item.timestamp,
                    event_type=item.event_type,
                    host=item.host,
                    wan_name=item.wan_name,
                    score=item.score,
                    details_json=item.details_json,
                )
        except Exception:
            self._logger.debug("Deferred write failed", exc_info=True)
        finally:
            with self._count_lock:
                self._pending_count = max(0, self._pending_count - 1)

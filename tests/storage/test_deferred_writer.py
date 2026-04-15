"""Tests for DeferredIOWorker -- background I/O worker for deferred SQLite metrics writes."""

import logging
import threading
import time
from unittest.mock import MagicMock

from wanctl.metrics import metrics
from wanctl.storage.deferred_writer import DeferredIOWorker


class TestDeferredIOWorker:
    """Test enqueue methods dispatch to correct MetricsWriter methods."""

    def _make_worker(self) -> tuple[DeferredIOWorker, MagicMock, threading.Event]:
        writer = MagicMock()
        shutdown = threading.Event()
        logger = logging.getLogger("test.io_worker")
        worker = DeferredIOWorker(writer=writer, shutdown_event=shutdown, logger=logger)
        return worker, writer, shutdown

    def test_enqueue_batch_returns_immediately(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        try:
            t0 = time.monotonic()
            worker.enqueue_batch([
                (1000, "spectrum", "wanctl_dl_rate", 500.0, None, "raw"),
            ])
            elapsed = time.monotonic() - t0
            assert elapsed < 0.05, f"enqueue_batch took {elapsed:.3f}s -- should be non-blocking"
        finally:
            worker.stop()

    def test_enqueue_batch_dispatches_to_writer(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        try:
            batch = [
                (1000, "spectrum", "wanctl_dl_rate", 500.0, None, "raw"),
                (1000, "spectrum", "wanctl_ul_rate", 30.0, None, "raw"),
            ]
            worker.enqueue_batch(batch)
            time.sleep(0.2)
            writer.write_metrics_batch.assert_called_once_with(batch)
        finally:
            worker.stop()

    def test_enqueue_write_dispatches_single_metric(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        try:
            worker.enqueue_write(
                timestamp=2000,
                wan_name="att",
                metric_name="wanctl_state",
                value=1.0,
                labels={"direction": "download", "reason": "rtt_increase"},
                granularity="raw",
            )
            time.sleep(0.2)
            writer.write_metric.assert_called_once_with(
                timestamp=2000,
                wan_name="att",
                metric_name="wanctl_state",
                value=1.0,
                labels={"direction": "download", "reason": "rtt_increase"},
                granularity="raw",
            )
        finally:
            worker.stop()

    def test_enqueue_alert_dispatches_to_writer(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        try:
            worker.enqueue_alert(
                timestamp=3000,
                alert_type="high_latency",
                severity="warning",
                wan_name="spectrum",
                details_json='{"rtt": 50}',
            )
            time.sleep(0.2)
            writer.write_alert.assert_called_once_with(
                timestamp=3000,
                alert_type="high_latency",
                severity="warning",
                wan_name="spectrum",
                details_json='{"rtt": 50}',
            )
        finally:
            worker.stop()

    def test_enqueue_reflector_event_dispatches_to_writer(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        try:
            worker.enqueue_reflector_event(
                timestamp=4000,
                event_type="score_change",
                host="1.1.1.1",
                wan_name="spectrum",
                score=0.8,
                details_json='{"old": 0.9}',
            )
            time.sleep(0.2)
            writer.write_reflector_event.assert_called_once_with(
                timestamp=4000,
                event_type="score_change",
                host="1.1.1.1",
                wan_name="spectrum",
                score=0.8,
                details_json='{"old": 0.9}',
            )
        finally:
            worker.stop()


class TestShutdownDrain:
    """Test stop() drains queue and returns within timeout."""

    def _make_worker(self) -> tuple[DeferredIOWorker, MagicMock, threading.Event]:
        writer = MagicMock()
        shutdown = threading.Event()
        logger = logging.getLogger("test.io_worker")
        worker = DeferredIOWorker(writer=writer, shutdown_event=shutdown, logger=logger)
        return worker, writer, shutdown

    def test_stop_drains_all_remaining_items(self) -> None:
        worker, writer, shutdown = self._make_worker()
        # Slow down writer to let items accumulate
        writer.write_metrics_batch.side_effect = lambda x: time.sleep(0.05)
        worker.start()
        for i in range(5):
            worker.enqueue_batch([(i, "spectrum", "m", float(i), None, "raw")])
        worker.stop()
        assert writer.write_metrics_batch.call_count == 5

    def test_stop_returns_within_timeout(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        t0 = time.monotonic()
        worker.stop()
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"stop() took {elapsed:.2f}s -- should be under 5s"

    def test_items_enqueued_before_sentinel_all_processed(self) -> None:
        worker, writer, shutdown = self._make_worker()
        worker.start()
        worker.enqueue_write(
            timestamp=100, wan_name="att", metric_name="m1", value=1.0,
        )
        worker.enqueue_write(
            timestamp=200, wan_name="att", metric_name="m2", value=2.0,
        )
        worker.stop()
        assert writer.write_metric.call_count == 2


class TestErrorHandling:
    """Test exception resilience of the background worker."""

    def _make_worker(self) -> tuple[DeferredIOWorker, MagicMock, threading.Event]:
        writer = MagicMock()
        shutdown = threading.Event()
        logger = logging.getLogger("test.io_worker")
        worker = DeferredIOWorker(writer=writer, shutdown_event=shutdown, logger=logger)
        return worker, writer, shutdown

    def test_exception_in_writer_doesnt_crash_thread(self) -> None:
        worker, writer, shutdown = self._make_worker()
        writer.write_metrics_batch.side_effect = RuntimeError("disk full")
        worker.start()
        worker.enqueue_batch([(1, "s", "m", 1.0, None, "raw")])
        time.sleep(0.2)
        assert worker.is_alive, "Thread should survive writer exceptions"
        worker.stop()

    def test_subsequent_enqueues_processed_after_exception(self) -> None:
        worker, writer, shutdown = self._make_worker()
        call_count = 0

        def side_effect(batch: list) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("disk full")

        writer.write_metrics_batch.side_effect = side_effect
        worker.start()
        worker.enqueue_batch([(1, "s", "m", 1.0, None, "raw")])
        time.sleep(0.2)
        worker.enqueue_batch([(2, "s", "m", 2.0, None, "raw")])
        time.sleep(0.2)
        assert writer.write_metrics_batch.call_count == 2
        worker.stop()


class TestHealth:
    """Test health observability properties."""

    def _make_worker(self) -> tuple[DeferredIOWorker, MagicMock, threading.Event]:
        writer = MagicMock()
        shutdown = threading.Event()
        logger = logging.getLogger("test.io_worker")
        worker = DeferredIOWorker(writer=writer, shutdown_event=shutdown, logger=logger)
        return worker, writer, shutdown

    def test_pending_count_starts_at_zero(self) -> None:
        worker, writer, shutdown = self._make_worker()
        assert worker.pending_count == 0

    def test_pending_count_tracks_enqueue_and_processing(self) -> None:
        worker, writer, shutdown = self._make_worker()
        # Block the writer so items stay pending
        gate = threading.Event()
        writer.write_metrics_batch.side_effect = lambda x: gate.wait(timeout=2.0)
        worker.start()
        worker.enqueue_batch([(1, "s", "m", 1.0, None, "raw")])
        time.sleep(0.05)
        # Item is being processed (gate is blocking), so pending_count should be >= 0
        # After gate releases, count should go to 0
        gate.set()
        time.sleep(0.2)
        assert worker.pending_count == 0
        worker.stop()

    def test_queue_metrics_are_distinct_from_sqlite_duration(self) -> None:
        worker, writer, shutdown = self._make_worker()
        gate = threading.Event()
        writer.write_metrics_batch.side_effect = lambda x: gate.wait(timeout=2.0)
        worker.start()
        try:
            worker.enqueue_batch([(1, "s", "m", 1.0, None, "raw")])
            time.sleep(0.05)
            assert worker.pending_count >= 1
            assert metrics.get_gauge(
                "wanctl_storage_write_last_duration_ms", {"process": "autorate"}
            ) is None
        finally:
            gate.set()
            worker.stop()

    def test_pending_writes_gauge_publishes_on_scrape(self) -> None:
        worker, writer, shutdown = self._make_worker()
        gate = threading.Event()
        writer.write_metrics_batch.side_effect = lambda x: gate.wait(timeout=2.0)
        worker.start()
        try:
            worker.enqueue_batch([(1, "s", "m", 1.0, None, "raw")])
            time.sleep(0.05)
            content = metrics.exposition()
            assert 'wanctl_storage_pending_writes{process="autorate"}' in content
            assert 'wanctl_storage_pending_writes{process="autorate"} 1.0' in content
        finally:
            gate.set()
            worker.stop()

    def test_is_alive_when_running(self) -> None:
        worker, writer, shutdown = self._make_worker()
        assert not worker.is_alive
        worker.start()
        assert worker.is_alive
        worker.stop()
        time.sleep(0.1)
        assert not worker.is_alive

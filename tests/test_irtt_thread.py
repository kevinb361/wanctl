"""Tests for IRTTThread background measurement coordinator."""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.irtt_measurement import IRTTResult
from wanctl.irtt_thread import IRTTThread


def _make_result(**overrides: object) -> IRTTResult:
    """Create an IRTTResult with sensible defaults."""
    defaults = dict(
        rtt_mean_ms=25.0,
        rtt_median_ms=24.0,
        ipdv_mean_ms=1.5,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=10,
        packets_received=10,
        server="1.2.3.4",
        port=2112,
        timestamp=100.0,
        success=True,
    )
    defaults.update(overrides)
    return IRTTResult(**defaults)


class TestIRTTThreadCache:
    """get_latest() caching behavior."""

    def test_get_latest_returns_none_before_measurement(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)
        assert thread.get_latest() is None

    def test_get_latest_returns_result_after_measurement(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        result = _make_result()
        measurement.measure.return_value = result
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        # Simulate one loop iteration: measure -> cache -> shutdown
        def side_effect(timeout: float) -> bool:
            shutdown.set()
            return True

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        assert thread.get_latest() is result

    def test_get_latest_retains_last_on_failure(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        good_result = _make_result(rtt_mean_ms=30.0)
        # First call returns good result, second returns None (failure)
        measurement.measure.side_effect = [good_result, None]
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        call_count = 0

        def side_effect(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.set()
                return True
            return False

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        assert thread.get_latest() is good_result


class TestIRTTThreadLifecycle:
    """start() / stop() thread management."""

    def test_start_creates_daemon_thread(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=0.01, shutdown_event=shutdown, logger=logger)

        thread.start()
        try:
            assert thread._thread is not None
            assert thread._thread.daemon is True
            assert thread._thread.name == "wanctl-irtt"
            assert thread._thread.is_alive()
        finally:
            shutdown.set()
            thread.stop()

    def test_stop_joins_thread(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=0.01, shutdown_event=shutdown, logger=logger)

        thread.start()
        shutdown.set()
        thread.stop()
        assert not thread._thread.is_alive()

    def test_run_exits_on_shutdown(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        # Shutdown immediately on first wait
        def side_effect(timeout: float) -> bool:
            shutdown.set()
            return True

        shutdown.wait = MagicMock(side_effect=side_effect)
        # _run() should return without hanging
        thread._run()
        assert measurement.measure.call_count == 1


class TestIRTTThreadLoop:
    """_run() loop scheduling and error handling."""

    def test_measure_called_each_iteration(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        call_count = 0

        def side_effect(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                shutdown.set()
                return True
            return False

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        assert measurement.measure.call_count == 3

    def test_exception_caught_and_logged_at_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.side_effect = [RuntimeError("network timeout"), None]
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        call_count = 0

        def side_effect(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.set()
                return True
            return False

        shutdown.wait = MagicMock(side_effect=side_effect)
        with caplog.at_level(logging.DEBUG, logger="test_irtt_thread"):
            thread._run()

        assert measurement.measure.call_count == 2
        assert "IRTT measurement error" in caplog.text
        assert "network timeout" in caplog.text

    def test_loop_continues_after_exception(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        result = _make_result()
        measurement.measure.side_effect = [RuntimeError("boom"), result]
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        call_count = 0

        def side_effect(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.set()
                return True
            return False

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        assert thread.get_latest() is result


class TestIRTTThreadLossDirection:
    """Cached result exposes send_loss and receive_loss (IRTT-06)."""

    def test_send_loss_accessible_from_cached_result(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        result = _make_result(send_loss=2.5)
        measurement.measure.return_value = result
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        def side_effect(timeout: float) -> bool:
            shutdown.set()
            return True

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        cached = thread.get_latest()
        assert cached is not None
        assert cached.send_loss == 2.5

    def test_receive_loss_accessible_from_cached_result(self) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        result = _make_result(receive_loss=1.0)
        measurement.measure.return_value = result
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        def side_effect(timeout: float) -> bool:
            shutdown.set()
            return True

        shutdown.wait = MagicMock(side_effect=side_effect)
        thread._run()
        cached = thread.get_latest()
        assert cached is not None
        assert cached.receive_loss == 1.0


class TestIRTTThreadLogging:
    """Start and stop log messages."""

    def test_start_logs_info_with_cadence(self, caplog: pytest.LogCaptureFixture) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)

        with caplog.at_level(logging.INFO, logger="test_irtt_thread"):
            thread.start()
        try:
            assert "IRTT thread started" in caplog.text
            assert "cadence=10.0s" in caplog.text
        finally:
            shutdown.set()
            thread.stop()

    def test_stop_logs_info(self, caplog: pytest.LogCaptureFixture) -> None:
        shutdown = threading.Event()
        measurement = MagicMock()
        measurement.measure.return_value = None
        logger = logging.getLogger("test_irtt_thread")
        thread = IRTTThread(measurement, cadence_sec=0.01, shutdown_event=shutdown, logger=logger)

        thread.start()
        shutdown.set()
        with caplog.at_level(logging.INFO, logger="test_irtt_thread"):
            thread.stop()
        assert "IRTT thread stopped" in caplog.text

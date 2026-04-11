"""Comprehensive tests for metrics.py module.

Tests for MetricsRegistry, MetricsServer, MetricsHandler, and record_* functions.
Covers thread safety, HTTP endpoints, and Prometheus exposition format.
"""

import json
import logging
import sqlite3
import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import find_free_port
from wanctl.irtt_measurement import IRTTResult
from wanctl.metrics import (
    METRIC_BANDWIDTH_MBPS,
    METRIC_CONGESTION_STATE,
    METRIC_CYCLE_DURATION_SECONDS,
    METRIC_CYCLES_TOTAL,
    METRIC_PING_FAILURES,
    METRIC_RATE_LIMIT_EVENTS,
    METRIC_ROUTER_UPDATES,
    METRIC_RTT_BASELINE_MS,
    METRIC_RTT_DELTA_MS,
    METRIC_RTT_LOAD_MS,
    METRIC_STATE,
    METRIC_STEERING_ENABLED,
    METRIC_STEERING_TRANSITIONS,
    MetricsRegistry,
    MetricsServer,
    metrics,
    record_autorate_cycle,
    record_ping_failure,
    record_rate_limit_event,
    record_router_update,
    record_steering_state,
    record_steering_transition,
    record_storage_checkpoint,
    record_storage_pending_writes,
    record_storage_write_success,
    start_metrics_server,
)
from wanctl.signal_processing import SignalResult
from wanctl.storage.reader import (
    compute_summary,
    count_metrics,
    query_metrics,
    select_granularity,
)
from wanctl.storage.writer import MetricsWriter


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset global metrics registry before and after each test."""
    metrics.reset()
    yield
    metrics.reset()


# =============================================================================
# MetricsRegistry Tests
# =============================================================================


class TestMetricsRegistryGauges:
    """Tests for gauge operations in MetricsRegistry."""

    def test_set_gauge_stores_value(self):
        """Test set_gauge stores and get_gauge retrieves value."""
        registry = MetricsRegistry()
        registry.set_gauge("test_gauge", 42.5)
        assert registry.get_gauge("test_gauge") == 42.5

    def test_set_gauge_with_labels(self):
        """Test set_gauge with labels dict creates correct key format."""
        registry = MetricsRegistry()
        registry.set_gauge("http_requests", 100, labels={"method": "GET", "status": "200"})
        # Labels are sorted, so method comes before status
        assert registry.get_gauge("http_requests", labels={"method": "GET", "status": "200"}) == 100

    def test_set_gauge_with_help_text(self):
        """Test set_gauge with help_text stores it."""
        registry = MetricsRegistry()
        registry.set_gauge("my_gauge", 1.0, help_text="This is my gauge")
        # Verify help text is stored (via exposition output)
        output = registry.exposition()
        assert "# HELP my_gauge This is my gauge" in output

    def test_set_gauge_help_text_only_stored_once(self):
        """Test help_text is only stored on first set."""
        registry = MetricsRegistry()
        registry.set_gauge("my_gauge", 1.0, help_text="First help")
        registry.set_gauge("my_gauge", 2.0, help_text="Second help")
        output = registry.exposition()
        assert "First help" in output
        assert "Second help" not in output

    def test_get_gauge_returns_none_for_missing(self):
        """Test get_gauge returns None for non-existent gauge."""
        registry = MetricsRegistry()
        assert registry.get_gauge("nonexistent") is None

    def test_set_gauge_overwrites_value(self):
        """Test set_gauge overwrites previous value."""
        registry = MetricsRegistry()
        registry.set_gauge("test_gauge", 10.0)
        registry.set_gauge("test_gauge", 20.0)
        assert registry.get_gauge("test_gauge") == 20.0


class TestMetricsRegistryCounters:
    """Tests for counter operations in MetricsRegistry."""

    def test_inc_counter_increments(self):
        """Test inc_counter increments by default value of 1."""
        registry = MetricsRegistry()
        registry.inc_counter("test_counter")
        assert registry.get_counter("test_counter") == 1
        registry.inc_counter("test_counter")
        assert registry.get_counter("test_counter") == 2

    def test_inc_counter_with_value(self):
        """Test inc_counter with custom value."""
        registry = MetricsRegistry()
        registry.inc_counter("test_counter", value=5)
        assert registry.get_counter("test_counter") == 5
        registry.inc_counter("test_counter", value=3)
        assert registry.get_counter("test_counter") == 8

    def test_inc_counter_with_labels(self):
        """Test inc_counter with labels."""
        registry = MetricsRegistry()
        registry.inc_counter("http_requests_total", labels={"method": "POST"})
        registry.inc_counter("http_requests_total", labels={"method": "GET"})
        registry.inc_counter("http_requests_total", labels={"method": "POST"})

        assert registry.get_counter("http_requests_total", labels={"method": "POST"}) == 2
        assert registry.get_counter("http_requests_total", labels={"method": "GET"}) == 1

    def test_inc_counter_with_help_text(self):
        """Test inc_counter with help_text stores it."""
        registry = MetricsRegistry()
        registry.inc_counter("my_counter", help_text="This is my counter")
        output = registry.exposition()
        assert "# HELP my_counter This is my counter" in output

    def test_get_counter_returns_none_for_missing(self):
        """Test get_counter returns None for non-existent counter."""
        registry = MetricsRegistry()
        assert registry.get_counter("nonexistent") is None


class TestMetricsRegistryKeyFormatting:
    """Tests for key formatting methods."""

    def test_make_key_without_labels(self):
        """Test _make_key returns just name when no labels."""
        registry = MetricsRegistry()
        key = registry._make_key("test_metric", None)
        assert key == "test_metric"

    def test_make_key_with_labels(self):
        """Test _make_key returns name{label="value"} format."""
        registry = MetricsRegistry()
        key = registry._make_key("test_metric", {"env": "prod", "app": "test"})
        # Labels are sorted alphabetically
        assert key == 'test_metric{app="test",env="prod"}'

    def test_make_key_with_empty_labels(self):
        """Test _make_key with empty labels dict returns just name."""
        registry = MetricsRegistry()
        key = registry._make_key("test_metric", {})
        assert key == "test_metric"

    def test_extract_base_name_with_labels(self):
        """Test _extract_base_name strips labels from key."""
        registry = MetricsRegistry()
        base = registry._extract_base_name('test_metric{label="value"}')
        assert base == "test_metric"

    def test_extract_base_name_without_labels(self):
        """Test _extract_base_name returns name unchanged when no labels."""
        registry = MetricsRegistry()
        base = registry._extract_base_name("test_metric")
        assert base == "test_metric"


class TestMetricsRegistryExposition:
    """Tests for Prometheus exposition format output."""

    def test_exposition_empty_registry(self):
        """Test exposition returns empty string for empty registry."""
        registry = MetricsRegistry()
        assert registry.exposition() == ""

    def test_exposition_with_gauges(self):
        """Test exposition with gauges includes TYPE gauge."""
        registry = MetricsRegistry()
        registry.set_gauge("test_gauge", 42.5)
        output = registry.exposition()
        assert "# TYPE test_gauge gauge" in output
        assert "test_gauge 42.5" in output

    def test_exposition_with_counters(self):
        """Test exposition with counters includes TYPE counter."""
        registry = MetricsRegistry()
        registry.inc_counter("test_counter", value=10)
        output = registry.exposition()
        assert "# TYPE test_counter counter" in output
        assert "test_counter 10" in output

    def test_exposition_with_help_text(self):
        """Test exposition includes HELP line when help_text provided."""
        registry = MetricsRegistry()
        registry.set_gauge("my_gauge", 1.0, help_text="Gauge description")
        registry.inc_counter("my_counter", help_text="Counter description")
        output = registry.exposition()
        assert "# HELP my_gauge Gauge description" in output
        assert "# HELP my_counter Counter description" in output

    def test_exposition_sorted_output(self):
        """Test metrics are emitted in sorted order."""
        registry = MetricsRegistry()
        registry.set_gauge("z_metric", 1.0)
        registry.set_gauge("a_metric", 2.0)
        registry.set_gauge("m_metric", 3.0)
        output = registry.exposition()
        lines = [line for line in output.split("\n") if line and not line.startswith("#")]
        assert lines == ["a_metric 2.0", "m_metric 3.0", "z_metric 1.0"]

    def test_exposition_same_base_name_multiple_labels(self):
        """Test exposition groups same base name metrics together."""
        registry = MetricsRegistry()
        registry.set_gauge("http_requests", 10, labels={"method": "GET"})
        registry.set_gauge("http_requests", 5, labels={"method": "POST"})
        output = registry.exposition()
        # TYPE line should only appear once
        assert output.count("# TYPE http_requests gauge") == 1


class TestMetricsRegistryReset:
    """Tests for reset functionality."""

    def test_reset_clears_all(self):
        """Test reset clears all gauges and counters."""
        registry = MetricsRegistry()
        registry.set_gauge("test_gauge", 42.5)
        registry.inc_counter("test_counter", value=10)

        registry.reset()

        assert registry.get_gauge("test_gauge") is None
        assert registry.get_counter("test_counter") is None
        assert registry.exposition() == ""


class TestMetricsRegistryThreadSafety:
    """Tests for thread safety of MetricsRegistry."""

    def test_thread_safety_concurrent_gauge(self):
        """Test 10 threads updating same gauge concurrently without errors."""
        registry = MetricsRegistry()
        errors = []
        iterations = 100

        def update_gauge(thread_id: int):
            try:
                for i in range(iterations):
                    registry.set_gauge("concurrent_gauge", float(thread_id * iterations + i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_gauge, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Final value should be set (non-deterministic which thread wins)
        assert registry.get_gauge("concurrent_gauge") is not None

    def test_thread_safety_concurrent_counter(self):
        """Test 10 threads incrementing same counter concurrently."""
        registry = MetricsRegistry()
        errors = []
        iterations = 100

        def increment_counter(thread_id: int):
            try:
                for _ in range(iterations):
                    registry.inc_counter("concurrent_counter")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment_counter, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All increments should be counted
        assert registry.get_counter("concurrent_counter") == 10 * iterations


# =============================================================================
# MetricsServer Tests
# =============================================================================


@pytest.mark.timeout(5)
class TestMetricsServer:
    """Tests for MetricsServer class."""

    def test_server_start_returns_true(self):
        """Test fresh start returns True."""
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)
        try:
            result = server.start()
            assert result is True
            assert server.is_running is True
        finally:
            server.stop()

    def test_server_start_already_running(self):
        """Test double start returns False."""
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)
        try:
            assert server.start() is True
            assert server.start() is False
        finally:
            server.stop()

    def test_server_stop_graceful(self):
        """Test stop() shuts down cleanly."""
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)
        server.start()
        time.sleep(0.05)  # Let server fully start

        server.stop()

        assert server.is_running is False

    def test_server_is_running_property(self):
        """Test is_running reflects state correctly."""
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)

        assert server.is_running is False
        server.start()
        assert server.is_running is True
        server.stop()
        assert server.is_running is False

    def test_server_port_in_use(self, caplog):
        """Test OSError logged when port unavailable."""
        port = find_free_port()
        server1 = MetricsServer(host="127.0.0.1", port=port)
        server2 = MetricsServer(host="127.0.0.1", port=port)

        try:
            server1.start()
            time.sleep(0.05)

            with caplog.at_level(logging.ERROR):
                result = server2.start()

            assert result is False
            assert "Failed to start metrics server" in caplog.text
        finally:
            server1.stop()

    def test_start_metrics_server_convenience(self):
        """Test start_metrics_server convenience function works."""
        port = find_free_port()
        server = start_metrics_server(host="127.0.0.1", port=port)
        try:
            assert isinstance(server, MetricsServer)
            assert server.is_running is True
        finally:
            server.stop()


# =============================================================================
# MetricsHandler HTTP Endpoint Tests
# =============================================================================


@pytest.mark.timeout(5)
class TestMetricsHandler:
    """Tests for MetricsHandler HTTP request handling."""

    @pytest.fixture
    def running_server(self):
        """Provide a running metrics server for testing."""
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)
        server.start()
        time.sleep(0.05)  # Give server time to start
        yield server, port
        server.stop()

    def test_metrics_endpoint_returns_200(self, running_server):
        """Test GET /metrics returns 200."""
        server, port = running_server
        url = f"http://127.0.0.1:{port}/metrics"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200

    def test_metrics_endpoint_content_type(self, running_server):
        """Test /metrics response has text/plain content type."""
        server, port = running_server
        url = f"http://127.0.0.1:{port}/metrics"
        with urllib.request.urlopen(url, timeout=5) as response:
            content_type = response.headers.get("Content-Type", "")
            assert "text/plain" in content_type

    def test_metrics_endpoint_contains_metrics(self, running_server):
        """Test /metrics response contains set metrics."""
        server, port = running_server
        # Set a metric
        metrics.set_gauge("test_http_gauge", 123.45)

        url = f"http://127.0.0.1:{port}/metrics"
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode("utf-8")

        assert "test_http_gauge 123.45" in content

    def test_health_endpoint_returns_ok(self, running_server):
        """Test GET /health returns 200 with 'OK'."""
        server, port = running_server
        url = f"http://127.0.0.1:{port}/health"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            content = response.read().decode("utf-8")
            assert content.strip() == "OK"

    def test_unknown_path_returns_404(self, running_server):
        """Test GET /unknown returns 404."""
        server, port = running_server
        url = f"http://127.0.0.1:{port}/unknown"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url, timeout=5)
        assert exc_info.value.code == 404
        exc_info.value.close()


# =============================================================================
# record_* Function Tests
# =============================================================================


class TestRecordAutorateCycle:
    """Tests for record_autorate_cycle function."""

    def test_record_autorate_cycle_sets_all_metrics(self):
        """Test record_autorate_cycle sets all expected gauges and counters."""
        record_autorate_cycle(
            wan_name="Spectrum",
            dl_rate_mbps=750.5,
            ul_rate_mbps=35.2,
            baseline_rtt=24.5,
            load_rtt=28.3,
            dl_state="GREEN",
            ul_state="YELLOW",
            cycle_duration=0.045,
        )

        # Check bandwidth gauges
        assert (
            metrics.get_gauge(METRIC_BANDWIDTH_MBPS, {"wan": "spectrum", "direction": "download"})
            == 750.5
        )
        assert (
            metrics.get_gauge(METRIC_BANDWIDTH_MBPS, {"wan": "spectrum", "direction": "upload"})
            == 35.2
        )

        # Check RTT gauges
        assert metrics.get_gauge(METRIC_RTT_BASELINE_MS, {"wan": "spectrum"}) == 24.5
        assert metrics.get_gauge(METRIC_RTT_LOAD_MS, {"wan": "spectrum"}) == 28.3
        assert metrics.get_gauge(METRIC_RTT_DELTA_MS, {"wan": "spectrum"}) == pytest.approx(
            3.8
        )  # 28.3 - 24.5

        # Check state gauges (1=GREEN, 2=YELLOW)
        assert metrics.get_gauge(METRIC_STATE, {"wan": "spectrum", "direction": "download"}) == 1
        assert metrics.get_gauge(METRIC_STATE, {"wan": "spectrum", "direction": "upload"}) == 2

        # Check cycle duration
        assert metrics.get_gauge(METRIC_CYCLE_DURATION_SECONDS, {"wan": "spectrum"}) == 0.045

        # Check cycle counter
        assert metrics.get_counter(METRIC_CYCLES_TOTAL, {"wan": "spectrum"}) == 1

    def test_record_autorate_cycle_rtt_delta_clamps_to_zero(self):
        """Test RTT delta is clamped to 0 when load < baseline."""
        record_autorate_cycle(
            wan_name="ATT",
            dl_rate_mbps=100.0,
            ul_rate_mbps=20.0,
            baseline_rtt=30.0,
            load_rtt=25.0,  # Less than baseline
            dl_state="GREEN",
            ul_state="GREEN",
            cycle_duration=0.05,
        )

        assert metrics.get_gauge(METRIC_RTT_DELTA_MS, {"wan": "att"}) == 0.0

    def test_record_autorate_cycle_state_mapping(self):
        """Test all state values map correctly."""
        # Test RED and SOFT_RED
        record_autorate_cycle(
            wan_name="test",
            dl_rate_mbps=100.0,
            ul_rate_mbps=20.0,
            baseline_rtt=25.0,
            load_rtt=35.0,
            dl_state="RED",
            ul_state="SOFT_RED",
            cycle_duration=0.05,
        )

        assert metrics.get_gauge(METRIC_STATE, {"wan": "test", "direction": "download"}) == 4  # RED
        assert (
            metrics.get_gauge(METRIC_STATE, {"wan": "test", "direction": "upload"}) == 3
        )  # SOFT_RED

    def test_record_autorate_cycle_unknown_state(self):
        """Test unknown state maps to 0."""
        record_autorate_cycle(
            wan_name="test",
            dl_rate_mbps=100.0,
            ul_rate_mbps=20.0,
            baseline_rtt=25.0,
            load_rtt=30.0,
            dl_state="UNKNOWN",
            ul_state="INVALID",
            cycle_duration=0.05,
        )

        assert metrics.get_gauge(METRIC_STATE, {"wan": "test", "direction": "download"}) == 0
        assert metrics.get_gauge(METRIC_STATE, {"wan": "test", "direction": "upload"}) == 0


class TestRecordRateLimitEvent:
    """Tests for record_rate_limit_event function."""

    def test_record_rate_limit_event(self):
        """Test record_rate_limit_event increments counter with correct labels."""
        record_rate_limit_event("Spectrum")
        record_rate_limit_event("Spectrum")
        record_rate_limit_event("ATT")

        assert metrics.get_counter(METRIC_RATE_LIMIT_EVENTS, {"wan": "spectrum"}) == 2
        assert metrics.get_counter(METRIC_RATE_LIMIT_EVENTS, {"wan": "att"}) == 1


class TestRecordRouterUpdate:
    """Tests for record_router_update function."""

    def test_record_router_update(self):
        """Test record_router_update increments counter."""
        record_router_update("Spectrum")
        record_router_update("Spectrum")

        assert metrics.get_counter(METRIC_ROUTER_UPDATES, {"wan": "spectrum"}) == 2


class TestRecordPingFailure:
    """Tests for record_ping_failure function."""

    def test_record_ping_failure(self):
        """Test record_ping_failure increments counter."""
        record_ping_failure("ATT")
        record_ping_failure("ATT")
        record_ping_failure("ATT")

        assert metrics.get_counter(METRIC_PING_FAILURES, {"wan": "att"}) == 3


class TestRecordSteeringState:
    """Tests for record_steering_state function."""

    def test_record_steering_state(self):
        """Test record_steering_state sets gauges correctly."""
        record_steering_state(
            primary_wan="Spectrum",
            steering_enabled=True,
            congestion_state="YELLOW",
        )

        assert metrics.get_gauge(METRIC_STEERING_ENABLED, {"wan": "spectrum"}) == 1.0
        assert metrics.get_gauge(METRIC_CONGESTION_STATE, {"wan": "spectrum"}) == 2  # YELLOW

    def test_record_steering_state_disabled(self):
        """Test record_steering_state with disabled steering."""
        record_steering_state(
            primary_wan="Spectrum",
            steering_enabled=False,
            congestion_state="GREEN",
        )

        assert metrics.get_gauge(METRIC_STEERING_ENABLED, {"wan": "spectrum"}) == 0.0
        assert metrics.get_gauge(METRIC_CONGESTION_STATE, {"wan": "spectrum"}) == 1  # GREEN

    def test_record_steering_state_red(self):
        """Test record_steering_state with RED congestion."""
        record_steering_state(
            primary_wan="Spectrum",
            steering_enabled=True,
            congestion_state="RED",
        )

        assert metrics.get_gauge(METRIC_CONGESTION_STATE, {"wan": "spectrum"}) == 4  # RED


class TestRecordSteeringTransition:
    """Tests for record_steering_transition function."""

    def test_record_steering_transition(self):
        """Test record_steering_transition increments counter with from/to labels."""
        record_steering_transition("Spectrum", "GREEN", "YELLOW")
        record_steering_transition("Spectrum", "YELLOW", "RED")
        record_steering_transition("Spectrum", "GREEN", "YELLOW")

        assert (
            metrics.get_counter(
                METRIC_STEERING_TRANSITIONS, {"wan": "spectrum", "from": "green", "to": "yellow"}
            )
            == 2
        )
        assert (
            metrics.get_counter(
                METRIC_STEERING_TRANSITIONS, {"wan": "spectrum", "from": "yellow", "to": "red"}
            )
            == 1
        )


# =============================================================================
# MERGED FROM test_metrics_observability.py
# =============================================================================


class TestSignalQualityMetrics:
    """Test signal quality metrics persistence to SQLite."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "signal_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    @pytest.fixture
    def sample_signal_result(self) -> SignalResult:
        """Create a typical SignalResult for testing."""
        return SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.45,
            variance_ms2=3.72,
            confidence=0.87,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=12,
            consecutive_outliers=0,
            warming_up=False,
        )

    def test_signal_quality_metrics_written_when_signal_result_present(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_signal_result: SignalResult,
    ) -> None:
        """When _last_signal_result is not None, 4 signal quality tuples are in the batch."""
        db_path, writer = temp_db
        ts = int(time.time())
        sr = sample_signal_result

        # Simulate what run_cycle() does: base metrics + signal quality extension
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_rate_download_mbps", 850.0, None, "raw"),
            (ts, "spectrum", "wanctl_rate_upload_mbps", 35.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, {"direction": "download"}, "raw"),
        ]

        # Signal quality extension (OBSV-03)
        metrics_batch.extend(
            [
                (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
                (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
                (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
                (
                    ts,
                    "spectrum",
                    "wanctl_signal_outlier_count",
                    float(sr.total_outliers),
                    None,
                    "raw",
                ),
            ]
        )

        writer.write_metrics_batch(metrics_batch)

        # Verify all 10 metrics written
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        assert len(rows) == 10
        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_signal_jitter_ms"] == 1.45
        assert metrics["wanctl_signal_variance_ms2"] == 3.72
        assert metrics["wanctl_signal_confidence"] == 0.87
        assert metrics["wanctl_signal_outlier_count"] == 12.0

    def test_signal_quality_metric_names_exact(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_signal_result: SignalResult,
    ) -> None:
        """Signal quality metric names match STORED_METRICS exactly."""
        db_path, writer = temp_db
        ts = int(time.time())
        sr = sample_signal_result

        signal_metrics = [
            (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
            (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
            (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
            (ts, "spectrum", "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
        ]
        writer.write_metrics_batch(signal_metrics)

        conn = sqlite3.connect(db_path)
        names = {r[0] for r in conn.execute("SELECT DISTINCT metric_name FROM metrics").fetchall()}
        conn.close()

        expected = {
            "wanctl_signal_jitter_ms",
            "wanctl_signal_variance_ms2",
            "wanctl_signal_confidence",
            "wanctl_signal_outlier_count",
        }
        assert names == expected

    def test_signal_quality_values_full_precision(
        self,
        temp_db: tuple[Path, MetricsWriter],
    ) -> None:
        """Signal quality values are stored at full precision, outlier_count cast to float."""
        db_path, writer = temp_db
        ts = int(time.time())

        sr = SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.456789012345,
            variance_ms2=3.7200000001,
            confidence=0.8712345678,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=999,
            consecutive_outliers=0,
            warming_up=False,
        )

        signal_metrics = [
            (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
            (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
            (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
            (ts, "spectrum", "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
        ]
        writer.write_metrics_batch(signal_metrics)

        conn = sqlite3.connect(db_path)
        metrics = {
            r[0]: r[1] for r in conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        }
        conn.close()

        assert metrics["wanctl_signal_jitter_ms"] == 1.456789012345
        assert metrics["wanctl_signal_variance_ms2"] == 3.7200000001
        assert metrics["wanctl_signal_confidence"] == 0.8712345678
        assert metrics["wanctl_signal_outlier_count"] == 999.0
        assert isinstance(metrics["wanctl_signal_outlier_count"], float)

    def test_no_signal_metrics_when_signal_result_none(
        self,
        temp_db: tuple[Path, MetricsWriter],
    ) -> None:
        """When _last_signal_result is None, no signal quality metrics are written."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Only base metrics, no signal quality extension
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
        ]
        # Simulate: if _last_signal_result is None, don't extend
        signal_result = None
        if signal_result is not None:
            metrics_batch.extend(
                [
                    (ts, "spectrum", "wanctl_signal_jitter_ms", 0.0, None, "raw"),
                ]
            )

        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        signal_rows = conn.execute(
            "SELECT * FROM metrics WHERE metric_name LIKE 'wanctl_signal_%'"
        ).fetchall()
        conn.close()

        assert len(signal_rows) == 0


class TestIRTTMetricsPersistence:
    """Test IRTT metrics persistence with timestamp-based deduplication."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "irtt_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    @pytest.fixture
    def sample_irtt_result(self) -> IRTTResult:
        """Create a typical IRTTResult for testing."""
        return IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=1000.0,  # time.monotonic()
            success=True,
        )

    def test_irtt_metrics_written_on_new_measurement(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """When irtt_result timestamp differs from _last_irtt_write_ts, 4 IRTT tuples in batch."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Simulate deduplication state
        last_irtt_write_ts: float | None = 900.0  # different from irtt_result.timestamp (1000.0)

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend(
                [
                    (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                    (
                        ts,
                        "spectrum",
                        "wanctl_irtt_loss_down_pct",
                        irtt_result.receive_loss,
                        None,
                        "raw",
                    ),
                ]
            )
            last_irtt_write_ts = irtt_result.timestamp

        assert len(metrics_batch) == 4
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_irtt_rtt_ms"] == 28.5
        assert metrics["wanctl_irtt_ipdv_ms"] == 2.3
        assert metrics["wanctl_irtt_loss_up_pct"] == 0.5
        assert metrics["wanctl_irtt_loss_down_pct"] == 1.0
        assert last_irtt_write_ts == 1000.0

    def test_irtt_metric_names_exact(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """IRTT metric names match STORED_METRICS exactly."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        irtt_metrics = [
            (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
        ]
        writer.write_metrics_batch(irtt_metrics)

        conn = sqlite3.connect(db_path)
        names = {r[0] for r in conn.execute("SELECT DISTINCT metric_name FROM metrics").fetchall()}
        conn.close()

        expected = {
            "wanctl_irtt_rtt_ms",
            "wanctl_irtt_ipdv_ms",
            "wanctl_irtt_loss_up_pct",
            "wanctl_irtt_loss_down_pct",
        }
        assert names == expected

    def test_last_irtt_write_ts_updated_after_writing(
        self,
        sample_irtt_result: IRTTResult,
    ) -> None:
        """_last_irtt_write_ts is updated to irtt_result.timestamp after writing."""
        irtt_result = sample_irtt_result
        last_irtt_write_ts: float | None = None

        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            last_irtt_write_ts = irtt_result.timestamp

        assert last_irtt_write_ts == 1000.0

    def test_duplicate_irtt_not_written(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """When irtt_result.timestamp equals _last_irtt_write_ts, NO IRTT metrics written."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Same timestamp = duplicate
        last_irtt_write_ts: float | None = irtt_result.timestamp  # 1000.0

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend(
                [
                    (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                    (
                        ts,
                        "spectrum",
                        "wanctl_irtt_loss_down_pct",
                        irtt_result.receive_loss,
                        None,
                        "raw",
                    ),
                ]
            )

        # No IRTT metrics should be in the batch
        assert len(metrics_batch) == 0

    def test_irtt_not_written_when_result_none(self) -> None:
        """When irtt_result is None, no IRTT metrics are written."""
        irtt_result = None
        last_irtt_write_ts: float | None = None

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend([])

        assert len(metrics_batch) == 0

    def test_first_irtt_always_writes(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """First IRTT measurement always writes (_last_irtt_write_ts starts as None)."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Initial state: never written before
        last_irtt_write_ts: float | None = None

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend(
                [
                    (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                    (
                        ts,
                        "spectrum",
                        "wanctl_irtt_loss_down_pct",
                        irtt_result.receive_loss,
                        None,
                        "raw",
                    ),
                ]
            )
            last_irtt_write_ts = irtt_result.timestamp

        # Should have written 4 IRTT metrics
        assert len(metrics_batch) == 4
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        irtt_rows = conn.execute(
            "SELECT * FROM metrics WHERE metric_name LIKE 'wanctl_irtt_%'"
        ).fetchall()
        conn.close()

        assert len(irtt_rows) == 4
        assert last_irtt_write_ts == 1000.0

    def test_irtt_deduplication_prevents_200x_duplication(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """Simulate 200 cycles with same IRTT result -- only 1 write should occur."""
        db_path, writer = temp_db
        irtt_result = sample_irtt_result
        last_irtt_write_ts: float | None = None

        for cycle in range(200):
            ts = int(time.time()) + cycle
            metrics_batch = []

            if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
                metrics_batch.extend(
                    [
                        (
                            ts,
                            "spectrum",
                            "wanctl_irtt_rtt_ms",
                            irtt_result.rtt_mean_ms,
                            None,
                            "raw",
                        ),
                        (
                            ts,
                            "spectrum",
                            "wanctl_irtt_ipdv_ms",
                            irtt_result.ipdv_mean_ms,
                            None,
                            "raw",
                        ),
                        (
                            ts,
                            "spectrum",
                            "wanctl_irtt_loss_up_pct",
                            irtt_result.send_loss,
                            None,
                            "raw",
                        ),
                        (
                            ts,
                            "spectrum",
                            "wanctl_irtt_loss_down_pct",
                            irtt_result.receive_loss,
                            None,
                            "raw",
                        ),
                    ]
                )
                last_irtt_write_ts = irtt_result.timestamp

            if metrics_batch:
                writer.write_metrics_batch(metrics_batch)

        # Only first cycle should have written IRTT metrics
        conn = sqlite3.connect(db_path)
        irtt_count = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE metric_name LIKE 'wanctl_irtt_%'"
        ).fetchone()[0]
        conn.close()

        assert irtt_count == 4, f"Expected 4 IRTT rows (1 write x 4 metrics), got {irtt_count}"


class TestWANControllerIRTTWriteTs:
    """Test _last_irtt_write_ts attribute on WANController."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    def test_last_irtt_write_ts_initialized_to_none(self, mock_config) -> None:
        """WANController._last_irtt_write_ts starts as None."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(needs_rate_limiting=False),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        assert controller._last_irtt_write_ts is None


class TestSignalQualityInRunCycle:
    """Test signal quality metrics batch extension in run_cycle (integration-like)."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def controller(self, mock_config):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(needs_rate_limiting=False),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        return ctrl

    def test_metrics_batch_includes_signal_quality_when_present(
        self,
        controller,
    ) -> None:
        """Verify run_cycle extends metrics_batch with signal quality when available."""
        # Set up signal result
        controller._last_signal_result = SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.45,
            variance_ms2=3.72,
            confidence=0.87,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=12,
            consecutive_outliers=0,
            warming_up=False,
        )

        # Mock the metrics_writer and capture batch
        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        # Run a cycle with all the necessary mocks
        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        # Verify write_metrics_batch was called
        assert mock_writer.write_metrics_batch.called
        batch = mock_writer.write_metrics_batch.call_args[0][0]

        # Extract metric names from the batch
        metric_names = [item[2] for item in batch]
        assert "wanctl_signal_jitter_ms" in metric_names
        assert "wanctl_signal_variance_ms2" in metric_names
        assert "wanctl_signal_confidence" in metric_names
        assert "wanctl_signal_outlier_count" in metric_names

    def test_signal_quality_values_from_run_cycle_match_signal_result(
        self,
        controller,
    ) -> None:
        """Verify signal quality values in metrics batch match the SignalResult fields."""
        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        assert mock_writer.write_metrics_batch.called
        batch = mock_writer.write_metrics_batch.call_args[0][0]
        batch_dict = {item[2]: item[3] for item in batch}

        # Values should match the SignalResult produced by signal_processor.process()
        sr = controller._last_signal_result
        assert sr is not None
        assert batch_dict["wanctl_signal_jitter_ms"] == sr.jitter_ms
        assert batch_dict["wanctl_signal_variance_ms2"] == sr.variance_ms2
        assert batch_dict["wanctl_signal_confidence"] == sr.confidence
        assert batch_dict["wanctl_signal_outlier_count"] == float(sr.total_outliers)


class TestIRTTInRunCycle:
    """Test IRTT metrics batch extension and deduplication in run_cycle."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def controller(self, mock_config):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(needs_rate_limiting=False),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        return ctrl

    def test_irtt_metrics_written_when_new_result_available(
        self,
        controller,
    ) -> None:
        """Verify run_cycle includes IRTT metrics when irtt_result has new timestamp."""
        # Set up IRTT thread with a result
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=time.monotonic(),
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        controller._last_irtt_write_ts = None  # First measurement

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        assert mock_writer.write_metrics_batch.called
        batch = mock_writer.write_metrics_batch.call_args[0][0]
        metric_names = [item[2] for item in batch]
        assert "wanctl_irtt_rtt_ms" in metric_names
        assert "wanctl_irtt_ipdv_ms" in metric_names
        assert "wanctl_irtt_loss_up_pct" in metric_names
        assert "wanctl_irtt_loss_down_pct" in metric_names

    def test_irtt_metrics_not_written_when_duplicate_timestamp(
        self,
        controller,
    ) -> None:
        """Verify run_cycle skips IRTT metrics when timestamp matches _last_irtt_write_ts."""
        # Set up IRTT thread with a result
        irtt_ts = time.monotonic()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=irtt_ts,
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        # Same timestamp = already written
        controller._last_irtt_write_ts = irtt_ts

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        if mock_writer.write_metrics_batch.called:
            batch = mock_writer.write_metrics_batch.call_args[0][0]
            metric_names = [item[2] for item in batch]
            assert "wanctl_irtt_rtt_ms" not in metric_names
            assert "wanctl_irtt_ipdv_ms" not in metric_names
            assert "wanctl_irtt_loss_up_pct" not in metric_names
            assert "wanctl_irtt_loss_down_pct" not in metric_names

    def test_last_irtt_write_ts_updated_after_cycle(
        self,
        controller,
    ) -> None:
        """Verify _last_irtt_write_ts is updated after writing IRTT metrics in run_cycle."""
        irtt_ts = time.monotonic()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=irtt_ts,
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        controller._last_irtt_write_ts = None

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        assert controller._last_irtt_write_ts == irtt_ts


# =============================================================================
# MERGED FROM test_metrics_reader.py
# =============================================================================


@pytest.fixture
def reset_singleton():
    """Reset the singleton before and after each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test_metrics.db"


@pytest.fixture
def populated_db(reset_singleton, test_db_path: Path) -> Path:
    """Create a database with test data for query tests."""
    writer = MetricsWriter(test_db_path)

    # Create test data spanning multiple timestamps, WANs, and metrics
    base_ts = 1706200000  # Fixed base timestamp for predictable tests

    test_data = [
        # Spectrum WAN - RTT metrics
        (base_ts, "spectrum", "wanctl_rtt_ms", 25.0, {"state": "GREEN"}, "raw"),
        (base_ts + 1, "spectrum", "wanctl_rtt_ms", 26.0, {"state": "GREEN"}, "raw"),
        (base_ts + 2, "spectrum", "wanctl_rtt_ms", 28.0, {"state": "YELLOW"}, "raw"),
        (base_ts + 60, "spectrum", "wanctl_rtt_ms", 24.0, None, "1m"),
        (base_ts + 120, "spectrum", "wanctl_rtt_ms", 25.5, None, "1m"),
        # Spectrum WAN - Rate metrics
        (base_ts, "spectrum", "wanctl_rate_download_mbps", 750.0, None, "raw"),
        (base_ts + 1, "spectrum", "wanctl_rate_download_mbps", 720.0, None, "raw"),
        (base_ts + 2, "spectrum", "wanctl_rate_download_mbps", 680.0, None, "raw"),
        # Spectrum WAN - State metrics
        (base_ts, "spectrum", "wanctl_state", 0.0, {"state": "GREEN"}, "raw"),
        (base_ts + 2, "spectrum", "wanctl_state", 1.0, {"state": "YELLOW"}, "raw"),
        # ATT WAN - RTT metrics
        (base_ts, "att", "wanctl_rtt_ms", 35.0, {"state": "GREEN"}, "raw"),
        (base_ts + 1, "att", "wanctl_rtt_ms", 36.0, {"state": "GREEN"}, "raw"),
        (base_ts + 60, "att", "wanctl_rtt_ms", 34.0, None, "1m"),
        # ATT WAN - Rate metrics
        (base_ts, "att", "wanctl_rate_download_mbps", 18.0, None, "raw"),
        (base_ts + 1, "att", "wanctl_rate_download_mbps", 17.5, None, "raw"),
    ]

    writer.write_metrics_batch(test_data)

    return test_db_path


# =============================================================================
# query_metrics Tests
# =============================================================================


class TestQueryMetricsEmptyCases:
    """Tests for query_metrics with empty/missing data."""

    def test_query_returns_empty_list_when_db_missing(self, tmp_path):
        """Test query returns empty list when database file doesn't exist."""
        nonexistent_db = tmp_path / "nonexistent.db"
        result = query_metrics(db_path=nonexistent_db)
        assert result == []

    def test_query_returns_empty_list_when_no_data_in_range(self, populated_db):
        """Test query returns empty list when no data matches time range."""
        # Query for timestamps way in the future
        result = query_metrics(
            db_path=populated_db,
            start_ts=2000000000,
            end_ts=2000000100,
        )
        assert result == []

    def test_query_returns_empty_list_when_table_missing(self, tmp_path):
        """Test query returns empty list when metrics table doesn't exist."""
        empty_db = tmp_path / "empty.db"
        # Create database without schema
        conn = sqlite3.connect(empty_db)
        conn.close()

        result = query_metrics(db_path=empty_db)
        assert result == []


class TestQueryMetricsTimeFilter:
    """Tests for query_metrics time range filtering."""

    def test_query_filters_by_time_range(self, populated_db):
        """Test query filters results by start_ts and end_ts."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts,
            end_ts=base_ts + 1,  # Only include first 2 seconds
        )

        # Should include all metrics from ts 1706200000 and 1706200001
        timestamps = [r["timestamp"] for r in result]
        assert all(base_ts <= ts <= base_ts + 1 for ts in timestamps)

    def test_query_with_only_start_ts(self, populated_db):
        """Test query with only start_ts filters correctly."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts + 60,  # Only 1m aggregates and later
        )

        # All results should be >= start_ts
        timestamps = [r["timestamp"] for r in result]
        assert all(ts >= base_ts + 60 for ts in timestamps)

    def test_query_with_only_end_ts(self, populated_db):
        """Test query with only end_ts filters correctly."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            end_ts=base_ts + 1,  # Only first 2 timestamps
        )

        # All results should be <= end_ts
        timestamps = [r["timestamp"] for r in result]
        assert all(ts <= base_ts + 1 for ts in timestamps)


class TestQueryMetricsNameFilter:
    """Tests for query_metrics metric name filtering."""

    def test_query_filters_by_metric_names(self, populated_db):
        """Test query filters by list of metric names."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms"],
        )

        # All results should be rtt_ms only
        metric_names = set(r["metric_name"] for r in result)
        assert metric_names == {"wanctl_rtt_ms"}

    def test_query_filters_by_multiple_metric_names(self, populated_db):
        """Test query filters by multiple metric names."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms", "wanctl_state"],
        )

        metric_names = set(r["metric_name"] for r in result)
        assert metric_names == {"wanctl_rtt_ms", "wanctl_state"}

    def test_query_with_nonexistent_metric_returns_empty(self, populated_db):
        """Test query with nonexistent metric name returns empty list."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["nonexistent_metric"],
        )
        assert result == []


class TestQueryMetricsWanFilter:
    """Tests for query_metrics WAN name filtering."""

    def test_query_filters_by_wan_name(self, populated_db):
        """Test query filters by WAN name."""
        result = query_metrics(
            db_path=populated_db,
            wan="spectrum",
        )

        wan_names = set(r["wan_name"] for r in result)
        assert wan_names == {"spectrum"}

    def test_query_filters_by_different_wan(self, populated_db):
        """Test query filters by different WAN name."""
        result = query_metrics(
            db_path=populated_db,
            wan="att",
        )

        wan_names = set(r["wan_name"] for r in result)
        assert wan_names == {"att"}

    def test_query_with_nonexistent_wan_returns_empty(self, populated_db):
        """Test query with nonexistent WAN returns empty list."""
        result = query_metrics(
            db_path=populated_db,
            wan="nonexistent_wan",
        )
        assert result == []


class TestQueryMetricsGranularityFilter:
    """Tests for query_metrics granularity filtering."""

    def test_query_filters_by_granularity(self, populated_db):
        """Test query filters by granularity."""
        result = query_metrics(
            db_path=populated_db,
            granularity="raw",
        )

        granularities = set(r["granularity"] for r in result)
        assert granularities == {"raw"}

    def test_query_filters_by_1m_granularity(self, populated_db):
        """Test query filters by 1m granularity."""
        result = query_metrics(
            db_path=populated_db,
            granularity="1m",
        )

        granularities = set(r["granularity"] for r in result)
        assert granularities == {"1m"}
        assert len(result) > 0


class TestQueryMetricsCombinedFilters:
    """Tests for query_metrics with multiple filters."""

    def test_query_combined_filters(self, populated_db):
        """Test query with time + metric + wan filters combined."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts,
            end_ts=base_ts + 2,
            metrics=["wanctl_rtt_ms"],
            wan="spectrum",
        )

        # Verify all filters applied
        for row in result:
            assert base_ts <= row["timestamp"] <= base_ts + 2
            assert row["metric_name"] == "wanctl_rtt_ms"
            assert row["wan_name"] == "spectrum"

        # Should have exactly 3 raw RTT readings for spectrum in this range
        assert len(result) == 3


class TestQueryMetricsPagination:
    """Tests for query_metrics limit/offset pagination."""

    def test_query_limit_applies_in_sql(self, populated_db):
        """Test query_metrics limit restricts returned rows."""
        result = query_metrics(db_path=populated_db, limit=5)
        assert len(result) == 5

    def test_query_offset_skips_rows(self, populated_db):
        """Test query_metrics offset skips the most recent rows."""
        full_result = query_metrics(db_path=populated_db)
        offset_result = query_metrics(db_path=populated_db, limit=5, offset=5)
        assert offset_result == full_result[5:10]


class TestCountMetrics:
    """Tests for count_metrics SQL-side counting."""

    def test_count_matches_unpaginated_query(self, populated_db):
        """Count should match the equivalent unpaginated query size."""
        full_result = query_metrics(db_path=populated_db, wan="spectrum", metrics=["wanctl_rtt_ms"])
        total = count_metrics(db_path=populated_db, wan="spectrum", metrics=["wanctl_rtt_ms"])
        assert total == len(full_result)

    def test_count_ignores_pagination_window(self, populated_db):
        """Count should reflect all matching rows, not just one page."""
        paged = query_metrics(db_path=populated_db, limit=5, offset=5)
        total = count_metrics(db_path=populated_db)
        assert total >= len(paged)
        assert total == len(query_metrics(db_path=populated_db))


class TestQueryMetricsResultFormat:
    """Tests for query_metrics result format."""

    def test_query_returns_all_columns(self, populated_db):
        """Test query returns all expected columns."""
        result = query_metrics(db_path=populated_db)

        assert len(result) > 0

        # Check first row has all columns
        row = result[0]
        expected_columns = {
            "timestamp",
            "wan_name",
            "metric_name",
            "value",
            "labels",
            "granularity",
        }
        assert set(row.keys()) == expected_columns

    def test_query_labels_are_json_strings(self, populated_db):
        """Test labels column contains JSON strings or None."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms"],
            granularity="raw",
        )

        # Some should have labels, some None
        labeled_rows = [r for r in result if r["labels"] is not None]
        assert len(labeled_rows) > 0

        # Labels should be valid JSON
        for row in labeled_rows:
            labels = json.loads(row["labels"])
            assert isinstance(labels, dict)

    def test_query_results_ordered_by_timestamp_desc(self, populated_db):
        """Test results are ordered by timestamp descending."""
        result = query_metrics(db_path=populated_db)

        timestamps = [r["timestamp"] for r in result]
        assert timestamps == sorted(timestamps, reverse=True)


# =============================================================================
# compute_summary Tests
# =============================================================================


class TestComputeSummaryEmptyCases:
    """Tests for compute_summary with empty/edge case inputs."""

    def test_summary_empty_list_returns_empty_dict(self):
        """Test compute_summary returns empty dict for empty list."""
        result = compute_summary([])
        assert result == {}

    def test_summary_single_value(self):
        """Test compute_summary with single value returns that value for all stats."""
        result = compute_summary([42.5])

        assert result["min"] == 42.5
        assert result["max"] == 42.5
        assert result["avg"] == 42.5
        assert result["p50"] == 42.5
        assert result["p95"] == 42.5
        assert result["p99"] == 42.5


class TestComputeSummarySmallLists:
    """Tests for compute_summary with small lists."""

    def test_summary_two_values(self):
        """Test compute_summary with two values (edge case for quantiles)."""
        result = compute_summary([10.0, 20.0])

        assert result["min"] == 10.0
        assert result["max"] == 20.0
        assert result["avg"] == 15.0
        # Percentiles should be computed (interpolated between the two values)
        assert "p50" in result
        assert "p95" in result
        assert "p99" in result

    def test_summary_three_values(self):
        """Test compute_summary with three values."""
        result = compute_summary([10.0, 20.0, 30.0])

        assert result["min"] == 10.0
        assert result["max"] == 30.0
        assert result["avg"] == 20.0


class TestComputeSummaryManyValues:
    """Tests for compute_summary with larger datasets."""

    def test_summary_many_values_correct_stats(self):
        """Test compute_summary with many values produces correct statistics."""
        # Generate 100 values: 1, 2, 3, ..., 100
        values = list(range(1, 101))
        result = compute_summary([float(v) for v in values])

        assert result["min"] == 1.0
        assert result["max"] == 100.0
        assert result["avg"] == 50.5  # Mean of 1-100
        # p50 should be around 50
        assert 49 <= result["p50"] <= 51
        # p95 should be around 95
        assert 94 <= result["p95"] <= 96
        # p99 should be around 99
        assert 98 <= result["p99"] <= 100

    def test_summary_includes_all_keys(self):
        """Test compute_summary includes all expected keys."""
        result = compute_summary([1.0, 2.0, 3.0, 4.0, 5.0])

        expected_keys = {"min", "max", "avg", "p50", "p95", "p99"}
        assert set(result.keys()) == expected_keys

    def test_summary_with_floats(self):
        """Test compute_summary handles float values correctly."""
        values = [25.5, 26.3, 24.8, 27.1, 25.0]
        result = compute_summary(values)

        assert result["min"] == 24.8
        assert result["max"] == 27.1
        assert 25.5 <= result["avg"] <= 25.8  # Approximate

    def test_summary_with_identical_values(self):
        """Test compute_summary with all identical values."""
        values = [15.0] * 10
        result = compute_summary(values)

        assert result["min"] == 15.0
        assert result["max"] == 15.0
        assert result["avg"] == 15.0
        assert result["p50"] == 15.0
        assert result["p95"] == 15.0
        assert result["p99"] == 15.0


# =============================================================================
# select_granularity Tests
# =============================================================================


class TestSelectGranularity:
    """Tests for select_granularity auto-selection."""

    def test_granularity_under_6h_returns_raw(self):
        """Test time range under 6 hours returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts + (5 * 60 * 60)  # 5 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"

    def test_granularity_exactly_6h_returns_1m(self):
        """Test time range of exactly 6 hours returns '1m'."""
        start_ts = 1706200000
        end_ts = start_ts + (6 * 60 * 60)  # Exactly 6 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "1m"

    def test_granularity_under_24h_returns_1m(self):
        """Test time range under 24 hours (but >= 6h) returns '1m'."""
        start_ts = 1706200000
        end_ts = start_ts + (12 * 60 * 60)  # 12 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "1m"

    def test_granularity_exactly_24h_returns_5m(self):
        """Test time range of exactly 24 hours returns '5m'."""
        start_ts = 1706200000
        end_ts = start_ts + (24 * 60 * 60)  # 24 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "5m"

    def test_granularity_under_7d_returns_5m(self):
        """Test time range under 7 days (but >= 24h) returns '5m'."""
        start_ts = 1706200000
        end_ts = start_ts + (3 * 24 * 60 * 60)  # 3 days

        result = select_granularity(start_ts, end_ts)
        assert result == "5m"

    def test_granularity_exactly_7d_returns_1h(self):
        """Test time range of exactly 7 days returns '1h'."""
        start_ts = 1706200000
        end_ts = start_ts + (7 * 24 * 60 * 60)  # 7 days

        result = select_granularity(start_ts, end_ts)
        assert result == "1h"

    def test_granularity_over_7d_returns_1h(self):
        """Test time range over 7 days returns '1h'."""
        start_ts = 1706200000
        end_ts = start_ts + (30 * 24 * 60 * 60)  # 30 days

        result = select_granularity(start_ts, end_ts)
        assert result == "1h"

    def test_granularity_very_short_range(self):
        """Test very short time range (seconds) returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts + 60  # 1 minute

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"

    def test_granularity_zero_range(self):
        """Test zero time range returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts  # Same timestamp

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"




class TestStorageObservabilityMetrics:
    """Tests for Phase 165 storage observability metric exports."""

    def test_storage_metrics_exposed_via_prometheus_handler(self):
        port = find_free_port()
        server = MetricsServer(host="127.0.0.1", port=port)
        server.start()
        time.sleep(0.05)
        try:
            record_storage_pending_writes("autorate", 3)
            record_storage_write_success("autorate", 4.5, 12)
            record_storage_checkpoint("autorate", busy=0, wal_pages=7, checkpointed_pages=7)

            url = f"http://127.0.0.1:{port}/metrics"
            with urllib.request.urlopen(url, timeout=5) as response:
                content = response.read().decode("utf-8")

            assert '# HELP wanctl_storage_pending_writes Queued SQLite write operations not yet processed' in content
            assert 'wanctl_storage_pending_writes{process="autorate"} 3.0' in content
            assert 'wanctl_storage_write_success_total{process="autorate"} 1' in content
            assert 'wanctl_storage_checkpointed_pages{process="autorate"} 7.0' in content
        finally:
            server.stop()

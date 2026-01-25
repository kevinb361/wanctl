"""Comprehensive tests for metrics.py module.

Tests for MetricsRegistry, MetricsServer, MetricsHandler, and record_* functions.
Covers thread safety, HTTP endpoints, and Prometheus exposition format.
"""

import logging
import socket
import threading
import time
import urllib.request

import pytest

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
    start_metrics_server,
)


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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
        assert metrics.get_gauge(METRIC_BANDWIDTH_MBPS, {"wan": "spectrum", "direction": "download"}) == 750.5
        assert metrics.get_gauge(METRIC_BANDWIDTH_MBPS, {"wan": "spectrum", "direction": "upload"}) == 35.2

        # Check RTT gauges
        assert metrics.get_gauge(METRIC_RTT_BASELINE_MS, {"wan": "spectrum"}) == 24.5
        assert metrics.get_gauge(METRIC_RTT_LOAD_MS, {"wan": "spectrum"}) == 28.3
        assert metrics.get_gauge(METRIC_RTT_DELTA_MS, {"wan": "spectrum"}) == pytest.approx(3.8)  # 28.3 - 24.5

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
        assert metrics.get_gauge(METRIC_STATE, {"wan": "test", "direction": "upload"}) == 3  # SOFT_RED

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

        assert metrics.get_counter(
            METRIC_STEERING_TRANSITIONS,
            {"wan": "spectrum", "from": "green", "to": "yellow"}
        ) == 2
        assert metrics.get_counter(
            METRIC_STEERING_TRANSITIONS,
            {"wan": "spectrum", "from": "yellow", "to": "red"}
        ) == 1

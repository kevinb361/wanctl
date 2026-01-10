"""
Simple Prometheus-compatible metrics exporter.

Provides a lightweight HTTP endpoint for Prometheus scraping without
requiring the prometheus_client library. Follows the Prometheus text
exposition format (v0.0.4).

Usage:
    from wanctl.metrics import metrics, start_metrics_server

    # Start the metrics server (usually in daemon mode)
    server = start_metrics_server(host='127.0.0.1', port=9100)

    # Record metrics
    metrics.set_gauge('wanctl_bandwidth_mbps', 750.5, labels={'wan': 'spectrum', 'direction': 'download'})
    metrics.inc_counter('wanctl_cycles_total', labels={'wan': 'spectrum'})

    # Metrics are automatically exposed at http://127.0.0.1:9100/metrics
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """
    Thread-safe metrics registry supporting Prometheus-style gauges and counters.

    Gauges represent point-in-time values that can go up or down.
    Counters represent monotonically increasing values (e.g., total events).

    All methods are thread-safe for concurrent access from multiple threads.
    """

    def __init__(self) -> None:
        """Initialize empty metrics registry with thread lock."""
        self._gauges: dict[str, float] = {}
        self._counters: dict[str, int] = {}
        self._gauge_help: dict[str, str] = {}
        self._counter_help: dict[str, str] = {}
        self._lock = threading.Lock()

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str | None = None,
    ) -> None:
        """
        Set a gauge metric value.

        Args:
            name: Metric name (e.g., 'wanctl_bandwidth_mbps')
            value: Current value
            labels: Optional label dict (e.g., {'wan': 'spectrum', 'direction': 'download'})
            help_text: Optional HELP description for the metric
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            if help_text and name not in self._gauge_help:
                self._gauge_help[name] = help_text

    def inc_counter(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        value: int = 1,
        help_text: str | None = None,
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name (e.g., 'wanctl_cycles_total')
            labels: Optional label dict
            value: Amount to increment (default: 1)
            help_text: Optional HELP description for the metric
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value
            if help_text and name not in self._counter_help:
                self._counter_help[name] = help_text

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """
        Get current gauge value.

        Args:
            name: Metric name
            labels: Optional label dict

        Returns:
            Current value or None if not set
        """
        key = self._make_key(name, labels)
        with self._lock:
            return self._gauges.get(key)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int | None:
        """
        Get current counter value.

        Args:
            name: Metric name
            labels: Optional label dict

        Returns:
            Current value or None if not set
        """
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key)

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        """Create metric key with optional labels in Prometheus format."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _extract_base_name(self, key: str) -> str:
        """Extract base metric name from key (strips labels)."""
        if "{" in key:
            return key.split("{")[0]
        return key

    def exposition(self) -> str:
        """
        Generate Prometheus text exposition format output.

        Returns:
            String in Prometheus exposition format (v0.0.4)
        """
        lines: list[str] = []
        emitted_help: set[str] = set()

        with self._lock:
            # Emit gauges
            for key, value in sorted(self._gauges.items()):
                base_name = self._extract_base_name(key)
                if base_name not in emitted_help:
                    if base_name in self._gauge_help:
                        lines.append(f"# HELP {base_name} {self._gauge_help[base_name]}")
                    lines.append(f"# TYPE {base_name} gauge")
                    emitted_help.add(base_name)
                lines.append(f"{key} {value}")

            # Emit counters
            for key, value in sorted(self._counters.items()):
                base_name = self._extract_base_name(key)
                if base_name not in emitted_help:
                    if base_name in self._counter_help:
                        lines.append(f"# HELP {base_name} {self._counter_help[base_name]}")
                    lines.append(f"# TYPE {base_name} counter")
                    emitted_help.add(base_name)
                lines.append(f"{key} {value}")

        return "\n".join(lines) + "\n" if lines else ""

    def reset(self) -> None:
        """Clear all metrics (mainly for testing)."""
        with self._lock:
            self._gauges.clear()
            self._counters.clear()


# Global registry instance
metrics = MetricsRegistry()


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for /metrics endpoint."""

    # Suppress access logging (too noisy for Prometheus scraping)
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests to /metrics endpoint."""
        if self.path == "/metrics":
            content = metrics.exposition()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        elif self.path == "/health":
            # Simple health check endpoint
            content = "OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found\n")


class MetricsServer:
    """
    HTTP server for Prometheus metrics endpoint.

    Runs in a background daemon thread and exposes metrics at /metrics.
    The server is automatically stopped when the main process exits.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9100) -> None:
        """
        Initialize metrics server.

        Args:
            host: Bind address (default: 127.0.0.1 for local-only access)
            port: Listen port (default: 9100, Prometheus node_exporter convention)
        """
        self.host = host
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._started = False

    def start(self) -> bool:
        """
        Start the metrics server in a background thread.

        Returns:
            True if started successfully, False if already running or on error
        """
        if self._started:
            logger.debug("Metrics server already running")
            return False

        try:
            self._server = HTTPServer((self.host, self.port), MetricsHandler)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="wanctl-metrics-server",
                daemon=True,  # Daemon thread - exits when main process exits
            )
            self._thread.start()
            self._started = True
            logger.info(f"Metrics server started on http://{self.host}:{self.port}/metrics")
            return True
        except OSError as e:
            logger.error(f"Failed to start metrics server on {self.host}:{self.port}: {e}")
            return False

    def stop(self) -> None:
        """Stop the metrics server gracefully."""
        if self._server and self._started:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=5.0)
            self._started = False
            logger.info("Metrics server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._started


def start_metrics_server(host: str = "127.0.0.1", port: int = 9100) -> MetricsServer:
    """
    Start a metrics server in the background.

    Convenience function that creates and starts a MetricsServer.

    Args:
        host: Bind address (default: 127.0.0.1 for local-only access)
        port: Listen port (default: 9100)

    Returns:
        MetricsServer instance (can be used to stop the server later)
    """
    server = MetricsServer(host, port)
    server.start()
    return server


# =============================================================================
# WANCTL METRIC DEFINITIONS
# =============================================================================
# Pre-defined metric names and helpers for consistent naming across components

# Metric name constants
METRIC_BANDWIDTH_MBPS = "wanctl_bandwidth_mbps"
METRIC_RTT_BASELINE_MS = "wanctl_rtt_baseline_ms"
METRIC_RTT_LOAD_MS = "wanctl_rtt_load_ms"
METRIC_RTT_DELTA_MS = "wanctl_rtt_delta_ms"
METRIC_STATE = "wanctl_state"
METRIC_CYCLES_TOTAL = "wanctl_cycles_total"
METRIC_CYCLE_DURATION_SECONDS = "wanctl_cycle_duration_seconds"
METRIC_RATE_LIMIT_EVENTS = "wanctl_rate_limit_events_total"
METRIC_ROUTER_UPDATES = "wanctl_router_updates_total"
METRIC_PING_FAILURES = "wanctl_ping_failures_total"
METRIC_STEERING_ENABLED = "wanctl_steering_enabled"
METRIC_STEERING_TRANSITIONS = "wanctl_steering_transitions_total"
METRIC_CONGESTION_STATE = "wanctl_congestion_state"

# State value mappings for numeric representation
STATE_VALUES = {
    "GREEN": 1,
    "YELLOW": 2,
    "SOFT_RED": 3,
    "RED": 4,
}


def record_autorate_cycle(
    wan_name: str,
    dl_rate_mbps: float,
    ul_rate_mbps: float,
    baseline_rtt: float,
    load_rtt: float,
    dl_state: str,
    ul_state: str,
    cycle_duration: float,
) -> None:
    """
    Record metrics for an autorate cycle.

    Args:
        wan_name: WAN identifier (e.g., 'spectrum', 'att')
        dl_rate_mbps: Download rate in Mbps
        ul_rate_mbps: Upload rate in Mbps
        baseline_rtt: Baseline RTT in ms
        load_rtt: Load RTT in ms
        dl_state: Download state (GREEN/YELLOW/SOFT_RED/RED)
        ul_state: Upload state (GREEN/YELLOW/RED)
        cycle_duration: Cycle duration in seconds
    """
    wan = wan_name.lower()

    # Bandwidth gauges
    metrics.set_gauge(
        METRIC_BANDWIDTH_MBPS,
        dl_rate_mbps,
        labels={"wan": wan, "direction": "download"},
        help_text="Current bandwidth limit in Mbps",
    )
    metrics.set_gauge(
        METRIC_BANDWIDTH_MBPS,
        ul_rate_mbps,
        labels={"wan": wan, "direction": "upload"},
        help_text="Current bandwidth limit in Mbps",
    )

    # RTT gauges
    metrics.set_gauge(
        METRIC_RTT_BASELINE_MS,
        baseline_rtt,
        labels={"wan": wan},
        help_text="Baseline RTT in milliseconds",
    )
    metrics.set_gauge(
        METRIC_RTT_LOAD_MS,
        load_rtt,
        labels={"wan": wan},
        help_text="Load RTT (EWMA smoothed) in milliseconds",
    )
    metrics.set_gauge(
        METRIC_RTT_DELTA_MS,
        max(0.0, load_rtt - baseline_rtt),
        labels={"wan": wan},
        help_text="RTT delta (load - baseline) in milliseconds",
    )

    # State gauges (numeric for alerting)
    dl_state_value = STATE_VALUES.get(dl_state, 0)
    ul_state_value = STATE_VALUES.get(ul_state, 0)
    metrics.set_gauge(
        METRIC_STATE,
        dl_state_value,
        labels={"wan": wan, "direction": "download"},
        help_text="Current state (1=GREEN, 2=YELLOW, 3=SOFT_RED, 4=RED)",
    )
    metrics.set_gauge(
        METRIC_STATE,
        ul_state_value,
        labels={"wan": wan, "direction": "upload"},
        help_text="Current state (1=GREEN, 2=YELLOW, 3=SOFT_RED, 4=RED)",
    )

    # Cycle counter and duration
    metrics.inc_counter(
        METRIC_CYCLES_TOTAL,
        labels={"wan": wan},
        help_text="Total number of autorate cycles",
    )
    metrics.set_gauge(
        METRIC_CYCLE_DURATION_SECONDS,
        cycle_duration,
        labels={"wan": wan},
        help_text="Duration of last autorate cycle in seconds",
    )


def record_rate_limit_event(wan_name: str) -> None:
    """Record a rate limit throttling event."""
    metrics.inc_counter(
        METRIC_RATE_LIMIT_EVENTS,
        labels={"wan": wan_name.lower()},
        help_text="Total rate limit throttling events",
    )


def record_router_update(wan_name: str) -> None:
    """Record a successful router configuration update."""
    metrics.inc_counter(
        METRIC_ROUTER_UPDATES,
        labels={"wan": wan_name.lower()},
        help_text="Total router configuration updates",
    )


def record_ping_failure(wan_name: str) -> None:
    """Record a ping measurement failure."""
    metrics.inc_counter(
        METRIC_PING_FAILURES,
        labels={"wan": wan_name.lower()},
        help_text="Total ping measurement failures",
    )


def record_steering_state(
    primary_wan: str,
    steering_enabled: bool,
    congestion_state: str,
) -> None:
    """
    Record steering daemon metrics.

    Args:
        primary_wan: Primary WAN name (e.g., 'spectrum')
        steering_enabled: Whether steering is currently enabled
        congestion_state: Current congestion state (GREEN/YELLOW/RED)
    """
    wan = primary_wan.lower()

    metrics.set_gauge(
        METRIC_STEERING_ENABLED,
        1.0 if steering_enabled else 0.0,
        labels={"wan": wan},
        help_text="Whether steering is enabled (1) or disabled (0)",
    )

    state_value = STATE_VALUES.get(congestion_state, 0)
    metrics.set_gauge(
        METRIC_CONGESTION_STATE,
        state_value,
        labels={"wan": wan},
        help_text="Congestion state (1=GREEN, 2=YELLOW, 4=RED)",
    )


def record_steering_transition(primary_wan: str, from_state: str, to_state: str) -> None:
    """Record a steering state transition."""
    metrics.inc_counter(
        METRIC_STEERING_TRANSITIONS,
        labels={
            "wan": primary_wan.lower(),
            "from": from_state.lower(),
            "to": to_state.lower(),
        },
        help_text="Total steering state transitions",
    )

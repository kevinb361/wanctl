"""
Health Check HTTP Endpoint for wanctl autorate daemon.

Provides a simple HTTP endpoint for monitoring systems to query daemon health.
Designed for container orchestration (Kubernetes liveness/readiness probes)
and external monitoring tools.

Usage:
    server = start_health_server(host='127.0.0.1', port=9101, controller=controller)
    # ... run daemon ...
    server.shutdown()  # in finally block
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

from wanctl import __version__

if TYPE_CHECKING:
    from wanctl.autorate_continuous import ContinuousAutoRate

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint.

    Responds to GET requests on / and /health with JSON health status.
    All other paths return 404.
    """

    # Class-level references set by start_health_server()
    controller: "ContinuousAutoRate | None" = None
    start_time: float | None = None
    consecutive_failures: int = 0

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging to avoid log spam."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health" or self.path == "/":
            health = self._get_health_status()
            status_code = 200 if health["status"] == "healthy" else 503

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _get_health_status(self) -> dict[str, Any]:
        """Build health status response."""
        uptime = time.monotonic() - self.start_time if self.start_time else 0

        # Determine overall health status
        # Healthy if consecutive failures < threshold
        # Controller being None just means no WANs configured yet (still healthy)
        is_healthy = self.consecutive_failures < 3  # MAX_CONSECUTIVE_FAILURES

        health: dict[str, Any] = {
            "status": "healthy" if is_healthy else "degraded",
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
            "consecutive_failures": self.consecutive_failures,
        }

        if self.controller:
            # Add controller-specific health info
            health["wan_count"] = len(self.controller.wan_controllers)
            health["wans"] = []
            for wan_info in self.controller.wan_controllers:
                wan_controller = wan_info["controller"]
                config = wan_info["config"]

                wan_health: dict[str, Any] = {
                    "name": config.wan_name,
                    "baseline_rtt_ms": round(wan_controller.baseline_rtt, 2),
                    "load_rtt_ms": round(wan_controller.load_rtt, 2),
                    "download": {
                        "current_rate_mbps": round(wan_controller.download.current_rate / 1e6, 1),
                        "state": _get_current_state(wan_controller.download),
                    },
                    "upload": {
                        "current_rate_mbps": round(wan_controller.upload.current_rate / 1e6, 1),
                        "state": _get_current_state(wan_controller.upload),
                    },
                }
                health["wans"].append(wan_health)

        return health


def _get_current_state(queue_controller: Any) -> str:
    """Determine current state from queue controller streaks.

    Returns the most likely current state based on streak counters.
    """
    if queue_controller.red_streak > 0:
        return "RED"
    elif queue_controller.soft_red_streak >= queue_controller.soft_red_required:
        return "SOFT_RED"
    elif queue_controller.green_streak >= queue_controller.green_required:
        return "GREEN"
    elif queue_controller.green_streak > 0:
        return "GREEN"  # Building towards sustained GREEN
    else:
        return "YELLOW"


class HealthCheckServer:
    """Wrapper for HTTPServer with clean shutdown support."""

    def __init__(self, server: HTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self) -> None:
        """Cleanly shut down the health check server."""
        self.server.shutdown()
        self.thread.join(timeout=5.0)


def start_health_server(
    host: str = "127.0.0.1",
    port: int = 9101,
    controller: "ContinuousAutoRate | None" = None,
) -> HealthCheckServer:
    """Start health check HTTP server in background thread.

    Args:
        host: Bind address (default: 127.0.0.1 for local-only access)
        port: Port to listen on (default: 9101)
        controller: ContinuousAutoRate instance for health data

    Returns:
        HealthCheckServer wrapper for shutdown support
    """
    # Set class-level references
    HealthCheckHandler.controller = controller
    HealthCheckHandler.start_time = time.monotonic()
    HealthCheckHandler.consecutive_failures = 0

    server = HTTPServer((host, port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health-check")
    thread.start()

    logger.info(f"Health check server started on http://{host}:{port}/health")

    return HealthCheckServer(server, thread)


def update_health_status(consecutive_failures: int) -> None:
    """Update the health status with current failure count.

    Called by the main loop to keep health endpoint in sync with daemon state.
    """
    HealthCheckHandler.consecutive_failures = consecutive_failures

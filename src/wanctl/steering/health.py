"""
Health Check HTTP Endpoint for wanctl steering daemon.

Provides a simple HTTP endpoint for monitoring systems to query steering daemon health.
Designed for container orchestration (Kubernetes liveness/readiness probes)
and external monitoring tools.

Usage:
    server = start_steering_health_server(host='127.0.0.1', port=9102, daemon=None)
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
    from wanctl.steering.daemon import SteeringDaemon

logger = logging.getLogger(__name__)


class SteeringHealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for steering daemon health check endpoint.

    Responds to GET requests on / and /health with JSON health status.
    All other paths return 404.
    """

    # Class-level references set by start_steering_health_server()
    daemon: "SteeringDaemon | None" = None
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
        is_healthy = self.consecutive_failures < 3

        health: dict[str, Any] = {
            "status": "healthy" if is_healthy else "degraded",
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
        }

        return health


class SteeringHealthServer:
    """Wrapper for HTTPServer with clean shutdown support."""

    def __init__(self, server: HTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self) -> None:
        """Cleanly shut down the health check server."""
        self.server.shutdown()
        self.thread.join(timeout=5.0)


def start_steering_health_server(
    host: str = "127.0.0.1",
    port: int = 9102,
    daemon: "SteeringDaemon | None" = None,
) -> SteeringHealthServer:
    """Start steering health check HTTP server in background thread.

    Args:
        host: Bind address (default: 127.0.0.1 for local-only access)
        port: Port to listen on (default: 9102)
        daemon: SteeringDaemon instance for health data

    Returns:
        SteeringHealthServer wrapper for shutdown support
    """
    # Set class-level references
    SteeringHealthHandler.daemon = daemon
    SteeringHealthHandler.start_time = time.monotonic()
    SteeringHealthHandler.consecutive_failures = 0

    server = HTTPServer((host, port), SteeringHealthHandler)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="steering-health"
    )
    thread.start()

    logger.info(f"Steering health server started on http://{host}:{port}/health")

    return SteeringHealthServer(server, thread)


def update_steering_health_status(consecutive_failures: int) -> None:
    """Update the health status with current failure count.

    Called by the steering daemon to keep health endpoint in sync with daemon state.
    """
    SteeringHealthHandler.consecutive_failures = consecutive_failures

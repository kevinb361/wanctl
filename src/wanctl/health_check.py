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
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from wanctl import __version__
from wanctl.storage.reader import query_metrics, select_granularity
from wanctl.storage.writer import DEFAULT_DB_PATH

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
        elif self.path.startswith("/metrics/history"):
            self._handle_metrics_history()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _get_health_status(self) -> dict[str, Any]:
        """Build health status response."""
        uptime = time.monotonic() - self.start_time if self.start_time else 0

        # Default: assume all routers reachable (startup or no controller)
        all_routers_reachable = True

        health: dict[str, Any] = {
            "status": "healthy",  # Will be updated below
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
            "consecutive_failures": self.consecutive_failures,
        }

        if self.controller:
            # Add controller-specific health info
            health["wan_count"] = len(self.controller.wan_controllers)
            health["wans"] = []

            # Check router connectivity across all WANs
            all_routers_reachable = all(
                wan_info["controller"].router_connectivity.is_reachable
                for wan_info in self.controller.wan_controllers
            )

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
                    "router_connectivity": wan_controller.router_connectivity.to_dict(),
                }
                health["wans"].append(wan_health)

        # Top-level router reachability aggregate
        health["router_reachable"] = all_routers_reachable

        # Determine overall health status
        # Healthy if consecutive failures < threshold AND all routers reachable
        is_healthy = self.consecutive_failures < 3 and all_routers_reachable
        health["status"] = "healthy" if is_healthy else "degraded"

        return health

    def _handle_metrics_history(self) -> None:
        """Handle /metrics/history requests.

        Query stored metrics with optional filters and pagination.
        Returns JSON response with data and metadata.
        """
        try:
            params = self._parse_history_params()
        except ValueError as e:
            self._send_json_error(400, str(e))
            return

        # Resolve time range
        start_ts, end_ts = self._resolve_time_range(
            range_duration=params.get("range"),
            from_ts=params.get("from"),
            to_ts=params.get("to"),
        )

        # Select granularity automatically
        granularity = select_granularity(start_ts, end_ts)

        # Query metrics from database
        results = query_metrics(
            db_path=DEFAULT_DB_PATH,
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=params.get("metrics"),
            wan=params.get("wan"),
            granularity=granularity,
        )

        # Apply pagination in Python (database returns all matching records)
        total_count = len(results)
        offset = params.get("offset", 0)
        limit = params.get("limit", 1000)
        paginated = results[offset : offset + limit]

        # Format each metric record
        formatted_data = [self._format_metric(row) for row in paginated]

        # Build response
        response = {
            "data": formatted_data,
            "metadata": {
                "total_count": total_count,
                "returned_count": len(formatted_data),
                "granularity": granularity,
                "limit": limit,
                "offset": offset,
                "query": {
                    "start": datetime.fromtimestamp(start_ts, tz=UTC).isoformat(),
                    "end": datetime.fromtimestamp(end_ts, tz=UTC).isoformat(),
                    "metrics": params.get("metrics"),
                    "wan": params.get("wan"),
                },
            },
        }

        self._send_json_response(response)

    def _parse_history_params(self) -> dict[str, Any]:
        """Parse and validate query parameters from URL.

        Returns:
            Dict with parsed parameters (range, from, to, metrics, wan, limit, offset)

        Raises:
            ValueError: If any parameter is invalid
        """
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        result: dict[str, Any] = {}

        # Parse 'range' param (e.g., "1h", "30m", "7d")
        if "range" in query_params:
            range_str = query_params["range"][0]
            result["range"] = self._parse_duration(range_str)

        # Parse 'from' param (ISO 8601 timestamp)
        if "from" in query_params:
            from_str = query_params["from"][0]
            result["from"] = self._parse_iso_timestamp(from_str)

        # Parse 'to' param (ISO 8601 timestamp)
        if "to" in query_params:
            to_str = query_params["to"][0]
            result["to"] = self._parse_iso_timestamp(to_str)

        # Parse 'metrics' param (comma-separated list)
        if "metrics" in query_params:
            metrics_str = query_params["metrics"][0]
            result["metrics"] = [m.strip() for m in metrics_str.split(",") if m.strip()]

        # Parse 'wan' param (string)
        if "wan" in query_params:
            result["wan"] = query_params["wan"][0]

        # Parse 'limit' param (int, default 1000, max 10000)
        if "limit" in query_params:
            try:
                limit = int(query_params["limit"][0])
                if limit < 1 or limit > 10000:
                    raise ValueError("limit must be between 1 and 10000")
                result["limit"] = limit
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid limit value: '{query_params['limit'][0]}'") from None
                raise

        # Parse 'offset' param (int, default 0)
        if "offset" in query_params:
            try:
                offset = int(query_params["offset"][0])
                if offset < 0:
                    raise ValueError("offset must be non-negative")
                result["offset"] = offset
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid offset value: '{query_params['offset'][0]}'") from None
                raise

        return result

    def _parse_duration(self, value: str) -> timedelta:
        """Parse duration string like '1h', '30m', '7d' into timedelta.

        Args:
            value: Duration string with format '<number><unit>'
                   Units: s=seconds, m=minutes, h=hours, d=days, w=weeks

        Returns:
            timedelta representing the duration

        Raises:
            ValueError: If duration format is invalid
        """
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        match = re.match(r"^(\d+)([smhdw])$", value.lower())
        if not match:
            raise ValueError(f"Invalid duration format: '{value}'. Use format like '1h', '30m', '7d'")
        return timedelta(seconds=int(match.group(1)) * units[match.group(2)])

    def _parse_iso_timestamp(self, value: str) -> int:
        """Parse ISO 8601 timestamp string into Unix timestamp.

        Args:
            value: ISO 8601 timestamp string

        Returns:
            Unix timestamp (seconds since epoch)

        Raises:
            ValueError: If timestamp format is invalid
        """
        try:
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp())
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{value}'. Use ISO 8601 format") from None

    def _resolve_time_range(
        self,
        range_duration: timedelta | None,
        from_ts: int | None,
        to_ts: int | None,
    ) -> tuple[int, int]:
        """Resolve time range from parameters.

        Args:
            range_duration: Relative duration (e.g., last 1h)
            from_ts: Absolute start timestamp
            to_ts: Absolute end timestamp

        Returns:
            Tuple of (start_ts, end_ts) as Unix timestamps
        """
        now = int(datetime.now(tz=UTC).timestamp())

        if range_duration:
            # Relative time range: end = now, start = now - duration
            end_ts_resolved = now
            start_ts_resolved = now - int(range_duration.total_seconds())
        elif from_ts is not None:
            # Absolute time range
            start_ts_resolved = from_ts
            end_ts_resolved = to_ts if to_ts is not None else now
        else:
            # Default: last 1 hour
            end_ts_resolved = now
            start_ts_resolved = now - 3600

        return start_ts_resolved, end_ts_resolved

    def _format_metric(self, row: dict) -> dict[str, Any]:
        """Format a metric row for JSON response.

        Converts Unix timestamp to ISO 8601 string.

        Args:
            row: Dict from query_metrics()

        Returns:
            Formatted dict with ISO 8601 timestamp
        """
        return {
            "timestamp": datetime.fromtimestamp(row["timestamp"], tz=UTC).isoformat(),
            "wan_name": row["wan_name"],
            "metric_name": row["metric_name"],
            "value": row["value"],
            "labels": row["labels"],
            "granularity": row["granularity"],
        }

    def _send_json_response(self, data: Any, status_code: int = 200) -> None:
        """Send a JSON response.

        Args:
            data: Data to serialize to JSON
            status_code: HTTP status code (default 200)
        """
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _send_json_error(self, status_code: int, message: str) -> None:
        """Send a JSON error response.

        Args:
            status_code: HTTP status code
            message: Error message
        """
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())


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
        self.server.server_close()
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

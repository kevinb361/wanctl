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
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

from wanctl import __version__
from wanctl.health_check import _build_cycle_budget, _get_disk_space_status

if TYPE_CHECKING:
    from wanctl.steering.daemon import SteeringDaemon

logger = logging.getLogger(__name__)


def _congestion_state_code(state: str) -> int:
    """Convert congestion state string to numeric code.

    Args:
        state: Congestion state string (GREEN, YELLOW, RED, or other)

    Returns:
        Numeric code: GREEN=0, YELLOW=1, RED=2, UNKNOWN=3
    """
    codes = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    return codes.get(state, 3)


def _format_iso_timestamp(
    monotonic_ts: float | None, server_start_time: float | None
) -> str | None:
    """Convert monotonic timestamp to ISO 8601 string.

    Calculates wall-clock time by computing the offset from server start time.

    Args:
        monotonic_ts: Monotonic timestamp (from time.monotonic())
        server_start_time: Server start monotonic time for offset calculation

    Returns:
        ISO 8601 formatted timestamp string, or None if timestamp unavailable
    """
    if monotonic_ts is None or server_start_time is None:
        return None

    # Calculate how long ago the event occurred relative to server start
    now_monotonic = time.monotonic()
    elapsed_since_event = now_monotonic - monotonic_ts

    # Convert to wall-clock time
    event_time = datetime.now(UTC) - timedelta(seconds=elapsed_since_event)
    return event_time.isoformat()


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
        """Build health status response.

        Returns core health fields (status, uptime, version) always.
        When daemon is attached, includes steering-specific fields:
        - steering: enabled, state, mode
        - congestion: primary state and code
        - decision: last_transition_time, time_in_state_seconds
        - counters: red_count, good_count, cake_read_failures
        - confidence: primary (when enabled)
        - errors: consecutive_failures, cake_read_failures
        - thresholds: config values
        - router_connectivity: router reachability state
        - pid: process ID
        """
        uptime = time.monotonic() - self.start_time if self.start_time else 0

        # Default: assume router reachable (startup or no daemon)
        router_reachable = True

        health: dict[str, Any] = {
            "status": "healthy",  # Will be updated below
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
        }

        # Add steering-specific fields when daemon is attached
        if self.daemon is not None:
            state = self.daemon.state_mgr.state

            # Handle cold start gracefully - check if state has required fields
            if not state or "current_state" not in state:
                health["status"] = "starting"
                return health

            # Core steering state (STEER-01, STEER-02)
            current_state = state.get("current_state", self.daemon.config.state_good)
            steering_enabled = current_state != self.daemon.config.state_good

            # Determine mode (dry_run or active)
            mode = "active"
            if self.daemon.config.confidence_config and self.daemon.config.confidence_config.get(
                "dry_run", {}
            ).get("enabled", False):
                mode = "dry_run"

            health["steering"] = {
                "enabled": steering_enabled,
                "state": current_state,
                "mode": mode,
            }

            # Congestion states (STEER-03, STEER-04)
            congestion_state = state.get("congestion_state", "UNKNOWN")
            health["congestion"] = {
                "primary": {
                    "state": congestion_state,
                    "state_code": _congestion_state_code(congestion_state),
                }
            }

            # Per-tin CAKE statistics (CAKE-07, D-05/D-06/D-07)
            # Only available when linux-cake transport is active
            raw_tin_stats: list[dict[str, Any]] | None = (
                getattr(self.daemon.cake_reader, "last_tin_stats", None)
                if hasattr(self.daemon, "cake_reader")
                else None
            )
            if raw_tin_stats and getattr(self.daemon.cake_reader, "_is_linux_cake", False):
                from wanctl.backends.linux_cake import TIN_NAMES

                tins_list = []
                for i, tin in enumerate(raw_tin_stats):
                    tin_name = TIN_NAMES[i] if i < len(TIN_NAMES) else f"tin_{i}"
                    tins_list.append(
                        {
                            "tin_name": tin_name,
                            "dropped_packets": tin.get("dropped_packets", 0),
                            "ecn_marked_packets": tin.get("ecn_marked_packets", 0),
                            "avg_delay_us": tin.get("avg_delay_us", 0),
                            "peak_delay_us": tin.get("peak_delay_us", 0),
                            "backlog_bytes": tin.get("backlog_bytes", 0),
                            "sparse_flows": tin.get("sparse_flows", 0),
                            "bulk_flows": tin.get("bulk_flows", 0),
                            "unresponsive_flows": tin.get("unresponsive_flows", 0),
                        }
                    )
                health["congestion"]["primary"]["tins"] = tins_list

            # Decision info (STEER-05)
            last_transition = state.get("last_transition_time")
            time_in_state = 0.0
            if last_transition is not None and self.start_time is not None:
                time_in_state = round(time.monotonic() - last_transition, 1)
            elif self.start_time is not None:
                # No transition yet - time in state equals uptime
                time_in_state = round(uptime, 1)

            health["decision"] = {
                "last_transition_time": _format_iso_timestamp(last_transition, self.start_time),
                "time_in_state_seconds": time_in_state,
            }

            # Timers and counters
            health["counters"] = {
                "red_count": state.get("red_count", 0),
                "good_count": state.get("good_count", 0),
                "cake_read_failures": state.get("cake_read_failures", 0),
            }

            # Confidence scores (STEER-02, when enabled)
            if self.daemon.confidence_controller:
                health["confidence"] = {
                    "primary": round(
                        self.daemon.confidence_controller.timer_state.confidence_score,
                        1,
                    ),
                }

            # Error counts
            health["errors"] = {
                "consecutive_failures": self.consecutive_failures,
                "cake_read_failures": state.get("cake_read_failures", 0),
            }

            # Config thresholds
            health["thresholds"] = {
                "green_rtt_ms": self.daemon.config.green_rtt_ms,
                "yellow_rtt_ms": self.daemon.config.yellow_rtt_ms,
                "red_rtt_ms": self.daemon.config.red_rtt_ms,
                "red_samples_required": self.daemon.config.red_samples_required,
                "green_samples_required": self.daemon.config.green_samples_required,
            }

            # Router connectivity state
            router_reachable = self.daemon.router_connectivity.is_reachable
            health["router_connectivity"] = self.daemon.router_connectivity.to_dict()

            # System info
            health["pid"] = os.getpid()

            # Add cycle budget telemetry if profiler has data
            cycle_budget = _build_cycle_budget(
                self.daemon._profiler,
                self.daemon._overrun_count,
                self.daemon._cycle_interval_ms,
                "steering_cycle_total",
            )
            if cycle_budget is not None:
                health["cycle_budget"] = cycle_budget

            # WAN awareness (OBSV-01)
            wan_awareness: dict[str, Any] = {
                "enabled": self.daemon._wan_state_enabled,
            }
            if self.daemon._wan_state_enabled:
                wan_awareness["zone"] = self.daemon._wan_zone
                wan_awareness["effective_zone"] = self.daemon._get_effective_wan_zone()
                wan_awareness["grace_period_active"] = self.daemon._is_wan_grace_period_active()
                zone_age = self.daemon.baseline_loader._get_wan_zone_age()
                wan_awareness["staleness_age_sec"] = (
                    round(zone_age, 1) if zone_age is not None else None
                )
                wan_awareness["stale"] = self.daemon.baseline_loader._is_wan_zone_stale()
                # Confidence contribution: actual weight applied for current effective zone
                effective = self.daemon._get_effective_wan_zone()
                if effective == "RED":
                    from wanctl.steering.steering_confidence import ConfidenceWeights

                    wan_awareness["confidence_contribution"] = (
                        self.daemon._wan_red_weight
                        if self.daemon._wan_red_weight is not None
                        else ConfidenceWeights.WAN_RED
                    )
                elif effective == "SOFT_RED":
                    from wanctl.steering.steering_confidence import ConfidenceWeights

                    wan_awareness["confidence_contribution"] = (
                        self.daemon._wan_soft_red_weight
                        if self.daemon._wan_soft_red_weight is not None
                        else ConfidenceWeights.WAN_SOFT_RED
                    )
                else:
                    wan_awareness["confidence_contribution"] = 0
                # Sustained cycle indicator: degrade_timer countdown (OBSV-01 gap closure)
                if self.daemon.confidence_controller:
                    ts = self.daemon.confidence_controller.timer_state
                    wan_awareness["degrade_timer_remaining"] = (
                        round(ts.degrade_timer, 2) if ts.degrade_timer is not None else None
                    )
                else:
                    wan_awareness["degrade_timer_remaining"] = None
            else:
                # Disabled mode: show raw zone for staged rollout verification (Phase 60 decision)
                wan_awareness["zone"] = self.daemon._wan_zone
            health["wan_awareness"] = wan_awareness

            # Alerting state
            from wanctl.alert_engine import AlertEngine

            ae = self.daemon.alert_engine
            if isinstance(ae, AlertEngine):
                cooldowns = ae.get_active_cooldowns()
                health["alerting"] = {
                    "enabled": ae._enabled,
                    "fire_count": ae.fire_count,
                    "active_cooldowns": [
                        {"type": k[0], "wan": k[1], "remaining_sec": round(v, 1)}
                        for k, v in cooldowns.items()
                    ],
                }

        # Top-level router reachability
        health["router_reachable"] = router_reachable

        # Disk space status
        health["disk_space"] = _get_disk_space_status()

        # Determine overall health status
        # Healthy if consecutive failures < threshold AND router reachable
        # AND disk space is not in warning state
        disk_warning = health["disk_space"]["status"] == "warning"
        is_healthy = self.consecutive_failures < 3 and router_reachable and not disk_warning
        health["status"] = "healthy" if is_healthy else "degraded"

        return health


class SteeringHealthServer:
    """Wrapper for HTTPServer with clean shutdown support."""

    def __init__(self, server: HTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self) -> None:
        """Cleanly shut down the health check server."""
        self.server.shutdown()
        self.server.server_close()
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
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="steering-health")
    thread.start()

    logger.info(f"Steering health server started on http://{host}:{port}/health")

    return SteeringHealthServer(server, thread)


def update_steering_health_status(consecutive_failures: int) -> None:
    """Update the health status with current failure count.

    Called by the steering daemon to keep health endpoint in sync with daemon state.
    """
    SteeringHealthHandler.consecutive_failures = consecutive_failures

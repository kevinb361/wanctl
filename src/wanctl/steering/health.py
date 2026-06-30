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
from wanctl.runtime_pressure import (
    build_runtime_section as build_runtime_status_section,
)
from wanctl.runtime_pressure import (
    build_storage_section as build_storage_status_section,
)

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


def _parse_transition_timestamp(value: Any) -> datetime | None:
    """Parse persisted transition timestamps into UTC datetimes.

    Steering state may contain either a monotonic timestamp from the current
    process or a wall-clock ISO 8601 string restored from persisted state.
    """
    if not isinstance(value, str):
        return None

    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_iso_timestamp(
    monotonic_ts: float | str | None, server_start_time: float | None
) -> str | None:
    """Convert monotonic or persisted wall-clock timestamps to ISO 8601."""
    if monotonic_ts is None:
        return None

    persisted_ts = _parse_transition_timestamp(monotonic_ts)
    if persisted_ts is not None:
        return persisted_ts.isoformat()

    if not isinstance(monotonic_ts, (int, float)) or server_start_time is None:
        return None

    # Calculate how long ago the event occurred relative to server start
    now_monotonic = time.monotonic()
    elapsed_since_event = now_monotonic - float(monotonic_ts)

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
            try:
                health = self._get_health_status()
            except Exception:
                health = {"status": "degraded", "error": "health check failed", "version": __version__}
                logging.getLogger(__name__).warning("Health endpoint failed", exc_info=True)
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

        Assembles response from section builders. Each builder returns a dict
        for its section of the steering health response.
        """
        uptime = time.monotonic() - self.start_time if self.start_time else 0
        router_reachable = True

        health: dict[str, Any] = {
            "status": "healthy",
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
        }

        if self.daemon is not None:
            state = self.daemon.state_mgr.state
            if not state or "current_state" not in state:
                health["status"] = "starting"
                return health
            router_reachable = self._populate_daemon_health(health, state, uptime)

        health["router_reachable"] = router_reachable
        health["disk_space"] = _get_disk_space_status()

        disk_warning = health["disk_space"]["status"] == "warning"
        is_healthy = self.consecutive_failures < 3 and router_reachable and not disk_warning
        health["status"] = "healthy" if is_healthy else "degraded"
        health["summary"] = self._build_summary_section(health)

        return health

    def _populate_daemon_health(self, health: dict[str, Any], state: dict, uptime: float) -> bool:
        """Populate daemon-specific health sections. Returns router_reachable."""
        assert self.daemon is not None

        health["steering"] = self._build_steering_status_section(state)
        health["congestion"] = self._build_congestion_section(state)
        health["decision"] = self._build_decision_section(state, uptime)
        health["counters"] = self._build_counters_section(state)

        if self.daemon.confidence_controller:
            health["confidence"] = {
                "primary": round(
                    self.daemon.confidence_controller.timer_state.confidence_score,
                    1,
                ),
            }

        health["errors"] = {
            "consecutive_failures": self.consecutive_failures,
            "cake_read_failures": state.get("cake_read_failures", 0),
        }
        health["thresholds"] = self._build_thresholds_section()
        health["router_connectivity"] = self.daemon.router_connectivity.to_dict()
        health["pid"] = os.getpid()

        health_data = self.daemon.get_health_data()
        cb = health_data["cycle_budget"]
        cycle_budget = _build_cycle_budget(
            cb["profiler"],
            cb["overrun_count"],
            cb["cycle_interval_ms"],
            "steering_cycle_total",
        )
        if cycle_budget is not None:
            health["cycle_budget"] = cycle_budget

        health["rtt_source"] = self._build_rtt_source_section(health_data)
        health["wan_awareness"] = self._build_wan_awareness_section(health_data)
        health["route_management"] = self._build_route_management_section(health_data)
        health["failover"] = self._build_failover_section(health_data)
        health["ownership_inspection"] = self._build_ownership_inspection_section(health_data)
        health["storage"] = self._build_storage_section(health_data)
        health["runtime"] = self._build_runtime_section(health_data, health.get("cycle_budget"))
        self._add_alerting_section(health)

        return self.daemon.router_connectivity.is_reachable

    def _build_steering_status_section(self, state: dict) -> dict[str, Any]:
        """Build core steering state section (STEER-01, STEER-02)."""
        assert self.daemon is not None
        current_state = state.get("current_state", self.daemon.config.state_good)
        steering_enabled = current_state != self.daemon.config.state_good

        mode = "active"
        if self.daemon.config.confidence_config and self.daemon.config.confidence_config.get(
            "dry_run", {}
        ).get("enabled", False):
            mode = "dry_run"

        return {
            "enabled": steering_enabled,
            "state": current_state,
            "mode": mode,
        }

    def _build_congestion_section(self, state: dict) -> dict[str, Any]:
        """Build congestion state section with optional CAKE tin stats."""
        assert self.daemon is not None
        congestion_state = state.get("congestion_state", "UNKNOWN")
        congestion: dict[str, Any] = {
            "primary": {
                "state": congestion_state,
                "state_code": _congestion_state_code(congestion_state),
            }
        }

        # Per-tin CAKE statistics (CAKE-07, D-05/D-06/D-07)
        raw_tin_stats: list[dict[str, Any]] | None = (
            getattr(self.daemon.cake_reader, "last_tin_stats", None)
            if hasattr(self.daemon, "cake_reader")
            else None
        )
        if raw_tin_stats and getattr(self.daemon.cake_reader, "is_linux_cake", False):
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
            congestion["primary"]["tins"] = tins_list

        return congestion

    def _build_decision_section(self, state: dict, uptime: float) -> dict[str, Any]:
        """Build decision info section (STEER-05)."""
        last_transition = state.get("last_transition_time")
        time_in_state = 0.0
        persisted_ts = _parse_transition_timestamp(last_transition)
        if persisted_ts is not None:
            time_in_state = round(max(0.0, (datetime.now(UTC) - persisted_ts).total_seconds()), 1)
        elif (
            last_transition is not None
            and self.start_time is not None
            and isinstance(last_transition, (int, float))
        ):
            time_in_state = round(max(0.0, time.monotonic() - float(last_transition)), 1)
        elif self.start_time is not None:
            time_in_state = round(uptime, 1)

        return {
            "last_transition_time": _format_iso_timestamp(last_transition, self.start_time),
            "time_in_state_seconds": time_in_state,
        }

    def _build_counters_section(self, state: dict) -> dict[str, Any]:
        """Build timers and counters section."""
        return {
            "red_count": state.get("red_count", 0),
            "good_count": state.get("good_count", 0),
            "cake_read_failures": state.get("cake_read_failures", 0),
        }

    def _build_thresholds_section(self) -> dict[str, Any]:
        """Build config thresholds section."""
        assert self.daemon is not None
        return {
            "green_rtt_ms": self.daemon.config.green_rtt_ms,
            "yellow_rtt_ms": self.daemon.config.yellow_rtt_ms,
            "red_rtt_ms": self.daemon.config.red_rtt_ms,
            "red_samples_required": self.daemon.config.red_samples_required,
            "green_samples_required": self.daemon.config.green_samples_required,
        }

    def _build_storage_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build bounded steering storage status from in-memory telemetry."""
        return build_storage_status_section(
            health_data.get("storage"),
            health_data.get("storage_files", {}),
        )

    def _build_runtime_section(
        self, health_data: dict[str, Any], cycle_budget: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Build bounded steering runtime pressure section."""
        raw_runtime = health_data.get("runtime")
        runtime: dict[str, Any] = raw_runtime if isinstance(raw_runtime, dict) else {}
        cycle_status = cycle_budget.get("status") if isinstance(cycle_budget, dict) else None
        process_role = str(runtime.get("process", "steering"))
        return build_runtime_status_section(
            process_role=process_role,
            rss_bytes=runtime.get("rss_bytes"),
            swap_bytes=runtime.get("swap_bytes"),
            cycle_status=cycle_status,
        )

    def _build_wan_awareness_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build WAN awareness section (OBSV-01) using get_health_data() facade."""
        assert self.daemon is not None
        wa = health_data["wan_awareness"]
        wan_awareness: dict[str, Any] = {
            "enabled": wa["enabled"],
        }
        if wa["enabled"]:
            wan_awareness["zone"] = wa["zone"]
            wan_awareness["effective_zone"] = wa["effective_zone"]
            wan_awareness["grace_period_active"] = wa["grace_period_active"]
            zone_age = wa["zone_age"]
            wan_awareness["staleness_age_sec"] = (
                round(zone_age, 1) if zone_age is not None else None
            )
            wan_awareness["stale"] = wa["stale"]

            wan_awareness["confidence_contribution"] = self._resolve_confidence_contribution(wa)

            if self.daemon.confidence_controller:
                ts = self.daemon.confidence_controller.timer_state
                wan_awareness["degrade_timer_remaining"] = (
                    round(ts.degrade_timer, 2) if ts.degrade_timer is not None else None
                )
            else:
                wan_awareness["degrade_timer_remaining"] = None
        else:
            # Disabled mode: show raw zone for staged rollout verification
            wan_awareness["zone"] = wa["zone"]
        return wan_awareness

    def _build_route_management_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build route ownership / management observability section."""
        raw = health_data.get("route_management")
        route_management: dict[str, Any] = raw if isinstance(raw, dict) else {}
        guard_raw = route_management.get("guard")
        guard = guard_raw if isinstance(guard_raw, dict) else {}
        reconciliation_raw = route_management.get("reconciliation")
        reconciliation = reconciliation_raw if isinstance(reconciliation_raw, dict) else {}
        circuit_raw = route_management.get("circuit_breaker")
        circuit = circuit_raw if isinstance(circuit_raw, dict) else {}
        return {
            "enabled": bool(route_management.get("enabled", False)),
            "mode": str(route_management.get("mode", "off")),
            "active_owner": str(route_management.get("active_owner", "unknown")),
            "active_allowed": bool(route_management.get("active_allowed", False)),
            "blocked_reason": route_management.get("blocked_reason"),
            "guard": {
                "status": str(guard.get("status", "unknown")),
                "active_allowed": bool(guard.get("active_allowed", False)),
                "conflict_count": int(guard.get("conflict_count", 0) or 0),
                "blocked_reason": guard.get("blocked_reason"),
            },
            "reconciliation": {
                "status": str(reconciliation.get("status", "unknown")),
                "error": reconciliation.get("error"),
                "route_count": int(reconciliation.get("route_count", 0) or 0),
                "checked_at": reconciliation.get("checked_at"),
            },
            "circuit_breaker": {
                "open": bool(circuit.get("open", False)),
                "failure_count": int(circuit.get("failure_count", 0) or 0),
                "last_error": circuit.get("last_error"),
            },
            "last_intended_action": route_management.get("last_intended_action"),
            "last_applied_action": route_management.get("last_applied_action"),
            "rollback_ready": bool(route_management.get("rollback_ready", False)),
            "last_abort": route_management.get("last_abort"),
            "last_event": route_management.get("last_event"),
        }

    def _build_failover_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build failover bridge observability section.

        Supports both legacy flat format and new per-WAN group format.
        If per-WAN keys (spectrum/att) are detected, returns the raw
        per-WAN data plus last_decision.
        """
        raw = health_data.get("failover")
        fo: dict[str, Any] = raw if isinstance(raw, dict) else {}
        last_decision_raw = fo.get("last_decision")
        last_decision: dict[str, Any] | None = (
            last_decision_raw if isinstance(last_decision_raw, dict) else None
        )

        # Detect per-WAN group format vs legacy flat format
        if any(k in fo for k in ("spectrum", "att")):
            # Per-WAN group format — pass through as-is with last_decision
            result = dict(fo)
            result["last_decision"] = last_decision
            return result

        # Legacy flat format — backward compat
        return {
            "enabled": bool(fo.get("enabled", False)),
            "red_count": int(fo.get("red_count", 0) or 0),
            "green_count": int(fo.get("green_count", 0) or 0),
            "last_decision": last_decision,
        }

    def _build_ownership_inspection_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build read-only RouterOS route ownership inspection section."""
        raw = health_data.get("ownership_inspection")
        ownership: dict[str, Any] = raw if isinstance(raw, dict) else {}
        netwatch_raw = ownership.get("netwatch")
        netwatch = netwatch_raw if isinstance(netwatch_raw, dict) else {}
        routes_raw = ownership.get("routes")
        routes = routes_raw if isinstance(routes_raw, dict) else {}
        return {
            "observed_owner": str(ownership.get("observed_owner", "unknown")),
            "configured_owner": str(ownership.get("configured_owner", "unknown")),
            "match": bool(ownership.get("match", False)),
            "inspector_status": str(ownership.get("inspector_status", "unknown")),
            "inspector_error": ownership.get("inspector_error"),
            "last_inspected_at": ownership.get("last_inspected_at"),
            "netwatch": {
                "entries_count": int(netwatch.get("entries_count", 0) or 0),
                "route_mutating_active_count": int(
                    netwatch.get("route_mutating_active_count", 0) or 0
                ),
            },
            "routes": {
                "total_route_count": int(routes.get("total_route_count", 0) or 0),
                "default_routes": list(routes.get("default_routes", []) or []),
            },
        }

    def _build_rtt_source_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build RTT source observability section for steering."""
        source = health_data.get("rtt_source", {})
        counts = source.get("counts", {})
        age = source.get("last_measurement_age_sec")
        last_rtt = source.get("last_rtt_ms")
        producer = source.get("producer")
        if producer != "wanctl-backend":
            producer = None
        backend = source.get("backend")
        if backend not in {"icmplib", "fping"}:
            backend = None
        source_ip = source.get("source_ip")
        if not isinstance(source_ip, str) or not source_ip:
            source_ip = None
        return {
            "current": source.get("current", "unknown"),
            "last_successful": source.get("last_successful", "unknown"),
            "last_rtt_ms": round(last_rtt, 2) if isinstance(last_rtt, (int, float)) else None,
            "last_measurement_age_sec": (round(age, 3) if isinstance(age, (int, float)) else None),
            "counts": {
                "wanctl_backend": int(counts.get("wanctl_backend", 0)),
                "autorate_health": int(counts.get("autorate_health", 0)),
                "autorate_irtt": int(counts.get("autorate_irtt", 0)),
                "history_fallback": int(counts.get("history_fallback", 0)),
            },
            "producer": producer,
            "backend": backend,
            "source_ip": source_ip,
        }

    def _resolve_confidence_contribution(self, wa: dict[str, Any]) -> float:
        """Resolve confidence weight for the current effective WAN zone."""
        effective = wa.get("effective_zone")
        if effective == "RED":
            from wanctl.steering.steering_confidence import ConfidenceWeights

            red_weight = wa.get("red_weight")
            return red_weight if red_weight is not None else ConfidenceWeights.WAN_RED
        if effective == "SOFT_RED":
            from wanctl.steering.steering_confidence import ConfidenceWeights

            soft_red_weight = wa.get("soft_red_weight")
            return (
                soft_red_weight if soft_red_weight is not None else ConfidenceWeights.WAN_SOFT_RED
            )
        return 0

    def _add_alerting_section(self, health: dict[str, Any]) -> None:
        """Add alerting state section to health dict if alert engine active."""
        assert self.daemon is not None
        from wanctl.alert_engine import AlertEngine

        ae = self.daemon.alert_engine
        if isinstance(ae, AlertEngine):
            cooldowns = ae.get_active_cooldowns()
            health["alerting"] = {
                "enabled": ae.enabled,
                "fire_count": ae.fire_count,
                "active_cooldowns": [
                    {"type": k[0], "wan": k[1], "remaining_sec": round(v, 1)}
                    for k, v in cooldowns.items()
                ],
            }

    def _build_summary_section(self, health: dict[str, Any]) -> dict[str, Any]:
        """Build compact steering operator summary."""
        steering = health.get("steering", {})
        congestion = health.get("congestion", {}).get("primary", {})
        wan_awareness = health.get("wan_awareness", {})
        storage = health.get("storage", {})
        runtime = health.get("runtime", {})
        router = health.get("router_connectivity", {})
        route_management = health.get("route_management", {})
        router_reachable = bool(router.get("is_reachable", health.get("router_reachable", False)))
        storage_status = str(storage.get("status", "unknown"))
        runtime_status = str(runtime.get("status", "unknown"))
        steering_state = str(steering.get("state", "UNKNOWN"))
        congestion_state = str(congestion.get("state", "UNKNOWN"))
        zone = wan_awareness.get("effective_zone") or wan_awareness.get("zone") or "unknown"
        row = {
            "name": "steering",
            "status": self._classify_summary_status(
                router_reachable=router_reachable,
                storage_status=storage_status,
                runtime_status=runtime_status,
                congestion_state=congestion_state,
            ),
            "state": steering_state,
            "congestion_state": congestion_state,
            "wan_zone": zone,
            "router_reachable": router_reachable,
            "storage_status": storage_status,
            "runtime_status": runtime_status,
            "route_owner": route_management.get("active_owner", "unknown"),
            "route_guard_status": (route_management.get("guard") or {}).get("status", "unknown"),
            "route_circuit_open": (route_management.get("circuit_breaker") or {}).get(
                "open", False
            ),
            "route_mode": route_management.get("mode", "off"),
            "route_active_allowed": route_management.get("active_allowed", False),
        }
        return {
            "service": "steering",
            "status": health.get("status", "unknown"),
            "alerts": self._build_alerting_summary(health.get("alerting")),
            "rows": [row],
        }

    def _build_alerting_summary(self, alerting: Any) -> dict[str, Any]:
        """Build compact alerting summary for operator views."""
        data = alerting if isinstance(alerting, dict) else {}
        cooldowns = data.get("active_cooldowns")
        active_count = len(cooldowns) if isinstance(cooldowns, list) else 0
        enabled = bool(data.get("enabled", False))
        status = "disabled"
        if enabled:
            status = "active" if active_count > 0 else "idle"
        return {
            "enabled": enabled,
            "fire_count": int(data.get("fire_count", 0) or 0),
            "active_cooldowns": active_count,
            "status": status,
        }

    def _classify_summary_status(
        self,
        *,
        router_reachable: bool,
        storage_status: str,
        runtime_status: str,
        congestion_state: str,
    ) -> str:
        """Classify compact steering summary status for operator display."""
        if not router_reachable or storage_status == "critical" or runtime_status == "critical":
            return "degraded"
        if (
            storage_status == "warning"
            or runtime_status == "warning"
            or congestion_state in {"RED", "SOFT_RED"}
        ):
            return "warning"
        return "ok"


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

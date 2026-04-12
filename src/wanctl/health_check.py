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
import shutil
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from wanctl import __version__
from wanctl.runtime_pressure import (
    build_runtime_section as build_runtime_status_section,
)
from wanctl.runtime_pressure import (
    build_storage_section as build_storage_status_section,
)
from wanctl.storage.reader import count_metrics, query_metrics, select_granularity
from wanctl.storage.writer import DEFAULT_DB_PATH

# Default: warn when less than 100MB free on data partition
_DISK_SPACE_WARNING_BYTES = 100 * 1024 * 1024  # 100 MB


def _get_disk_space_status(
    path: str = "/var/lib/wanctl",
    threshold_bytes: int = _DISK_SPACE_WARNING_BYTES,
) -> dict[str, Any]:
    """Check disk space for the given path.

    Returns dict with path, free_bytes, total_bytes, free_pct, status.
    Status is "ok", "warning", or "unknown" (if path inaccessible).
    """
    try:
        usage = shutil.disk_usage(path)
        free_pct = round((usage.free / usage.total) * 100, 1) if usage.total > 0 else 0.0
        status = "ok" if usage.free >= threshold_bytes else "warning"
        return {
            "path": path,
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "free_pct": free_pct,
            "status": status,
        }
    except OSError:
        return {
            "path": path,
            "free_bytes": 0,
            "total_bytes": 0,
            "free_pct": 0.0,
            "status": "unknown",
        }


if TYPE_CHECKING:
    from wanctl.autorate_continuous import ContinuousAutoRate
    from wanctl.perf_profiler import OperationProfiler

logger = logging.getLogger(__name__)


def _build_cycle_budget(
    profiler: "OperationProfiler",
    overrun_count: int,
    cycle_interval_ms: float,
    total_label: str,
    *,
    warning_threshold_pct: float = 80.0,
) -> dict[str, Any] | None:
    """Build cycle budget telemetry dict from profiler stats.

    Returns None when the profiler has no data (cold start, D9).

    Args:
        profiler: OperationProfiler with accumulated cycle timing samples
        overrun_count: Cumulative overrun counter since startup
        cycle_interval_ms: Configured cycle interval in milliseconds
        total_label: Profiler label for total cycle time (e.g. "autorate_cycle_total")
        warning_threshold_pct: Utilization threshold for warning status (default 80.0)

    Returns:
        Dict with cycle_time_ms, utilization_pct, overrun_count, status, warning_threshold_pct
        or None if no data
    """
    stats = profiler.stats(total_label)
    if not isinstance(stats, dict) or "avg_ms" not in stats:
        return None

    utilization = round((stats["avg_ms"] / cycle_interval_ms) * 100, 1)

    if utilization >= 100.0:
        status = "critical"
    elif utilization >= warning_threshold_pct:
        status = "warning"
    else:
        status = "ok"

    result: dict[str, Any] = {
        "cycle_time_ms": {
            "avg": round(stats["avg_ms"], 1),
            "p95": round(stats["p95_ms"], 1),
            "p99": round(stats["p99_ms"], 1),
        },
        "utilization_pct": utilization,
        "overrun_count": overrun_count,
        "status": status,
        "warning_threshold_pct": warning_threshold_pct,
    }

    # Per-subsystem breakdown (Phase 131: PERF-01, per D-08)
    subsystem_labels = [
        "autorate_rtt_measurement",
        "autorate_signal_processing",
        "autorate_ewma_spike",
        "autorate_cake_stats",
        "autorate_congestion_assess",
        "autorate_irtt_observation",
        "autorate_logging_metrics",
        "autorate_router_communication",
        "autorate_post_cycle",
    ]
    subsystems: dict[str, dict[str, float]] = {}
    for label in subsystem_labels:
        sub_stats = profiler.stats(label)
        if isinstance(sub_stats, dict) and "avg_ms" in sub_stats:
            short_name = label.replace("autorate_", "")
            subsystems[short_name] = {
                "avg": round(sub_stats["avg_ms"], 1),
                "p95": round(sub_stats["p95_ms"], 1),
                "p99": round(sub_stats["p99_ms"], 1),
            }
    if subsystems:
        result["subsystems"] = subsystems

    return result


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
        """Build health status response.

        Assembles response from section builders. Each builder returns a dict
        for its section of the health response.
        """
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
            health["wan_count"] = len(self.controller.wan_controllers)
            health["wans"] = []

            all_routers_reachable = all(
                wan_info["controller"].router_connectivity.is_reachable
                for wan_info in self.controller.wan_controllers
            )

            for wan_info in self.controller.wan_controllers:
                wan_health = self._build_wan_status(wan_info)
                health["wans"].append(wan_health)

        health["alerting"] = self._build_alerting_section()

        # Top-level router reachability aggregate
        health["router_reachable"] = all_routers_reachable

        # Disk space status
        health["disk_space"] = _get_disk_space_status()

        # Determine overall health status
        disk_warning = health["disk_space"]["status"] == "warning"
        is_healthy = self.consecutive_failures < 3 and all_routers_reachable and not disk_warning
        health["status"] = "healthy" if is_healthy else "degraded"
        health["summary"] = self._build_summary_section(health)

        return health

    def _build_wan_status(self, wan_info: dict[str, Any]) -> dict[str, Any]:
        """Build per-WAN status dict with all subsections."""
        wan_controller = wan_info["controller"]
        config = wan_info["config"]

        # Get all health data via public facade (replaces ~25 private accesses)
        health_data = wan_controller.get_health_data()

        wan_health: dict[str, Any] = {
            "name": config.wan_name,
            "baseline_rtt_ms": round(wan_controller.baseline_rtt, 2),
            "load_rtt_ms": round(wan_controller.load_rtt, 2),
            "download": self._build_rate_hysteresis_section(
                wan_controller.download, health_data
            ),
            "upload": self._build_rate_hysteresis_section(
                wan_controller.upload, health_data
            ),
            "router_connectivity": wan_controller.router_connectivity.to_dict(),
        }

        # Add cycle budget telemetry if profiler has data
        cb = health_data["cycle_budget"]
        cycle_budget = _build_cycle_budget(
            cb["profiler"],
            cb["overrun_count"],
            cb["cycle_interval_ms"],
            "autorate_cycle_total",
            warning_threshold_pct=cb["warning_threshold_pct"],
        )
        if cycle_budget is not None:
            wan_health["cycle_budget"] = cycle_budget

        # Signal quality section (OBSV-01)
        signal_quality = self._build_signal_quality_section(health_data)
        if signal_quality is not None:
            wan_health["signal_quality"] = signal_quality

        wan_health["irtt"] = self._build_irtt_section(health_data, config)
        wan_health["reflector_quality"] = self._build_reflector_section(health_data)
        wan_health["fusion"] = self._build_fusion_section(health_data)
        wan_health["asymmetry_gate"] = self._build_asymmetry_gate_section(health_data)

        cake_signal = self._build_cake_signal_section(health_data)
        if cake_signal is not None:
            wan_health["cake_signal"] = cake_signal

        wan_health["tuning"] = self._build_tuning_section(health_data, wan_controller)
        wan_health["storage"] = self._build_storage_section(health_data)
        wan_health["runtime"] = self._build_runtime_section(health_data, wan_health.get("cycle_budget"))

        return wan_health

    def _build_rate_hysteresis_section(
        self, qc: Any, health_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build rate and hysteresis status for a queue controller."""
        qc_health = qc.get_health_data()
        hyst = qc_health["hysteresis"]
        return {
            "current_rate_mbps": round(qc.current_rate / 1e6, 1),
            "state": _get_current_state(qc),
            "hysteresis": {
                "dwell_counter": hyst["dwell_counter"],
                "dwell_cycles": hyst["dwell_cycles"],
                "deadband_ms": hyst["deadband_ms"],
                "transitions_suppressed": hyst["transitions_suppressed"],
                "suppressions_per_min": hyst["suppressions_per_min"],
                "window_start_epoch": hyst["window_start_epoch"],
                "alert_threshold_per_min": health_data["suppression_alert"]["threshold"],
            },
        }

    def _build_signal_quality_section(
        self, health_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build signal quality status. Returns None if no signal data."""
        signal_result = health_data["signal_result"]
        if signal_result is None:
            return None
        return {
            "jitter_ms": round(signal_result.jitter_ms, 3),
            "variance_ms2": round(signal_result.variance_ms2, 3),
            "confidence": round(signal_result.confidence, 3),
            "outlier_rate": round(signal_result.outlier_rate, 3),
            "total_outliers": signal_result.total_outliers,
            "warming_up": signal_result.warming_up,
        }

    def _build_irtt_section(
        self, health_data: dict[str, Any], config: Any
    ) -> dict[str, Any]:
        """Build IRTT measurement status (OBSV-02). Always present."""
        irtt_data = health_data["irtt"]
        irtt_thread = irtt_data["thread"]
        if irtt_thread is None:
            irtt_enabled = config.irtt_config.get("enabled", False)
            reason = "disabled" if not irtt_enabled else "binary_not_found"
            return {"available": False, "reason": reason}

        irtt_result = irtt_thread.get_latest()
        if irtt_result is None:
            return {
                "available": True,
                "reason": "awaiting_first_measurement",
                "rtt_mean_ms": None,
                "ipdv_ms": None,
                "loss_up_pct": None,
                "loss_down_pct": None,
                "server": None,
                "staleness_sec": None,
                "protocol_correlation": None,
                "asymmetry_direction": "unknown",
                "asymmetry_ratio": None,
            }

        irtt_correlation = irtt_data["correlation"]
        last_asymmetry_result = irtt_data["last_asymmetry_result"]
        staleness = round(time.monotonic() - irtt_result.timestamp, 1)
        return {
            "available": True,
            "rtt_mean_ms": round(irtt_result.rtt_mean_ms, 2),
            "ipdv_ms": round(irtt_result.ipdv_mean_ms, 2),
            "loss_up_pct": round(irtt_result.send_loss, 1),
            "loss_down_pct": round(irtt_result.receive_loss, 1),
            "server": f"{irtt_result.server}:{irtt_result.port}",
            "staleness_sec": staleness,
            "protocol_correlation": (
                round(irtt_correlation, 2)
                if irtt_correlation is not None
                else None
            ),
            "asymmetry_direction": (
                last_asymmetry_result.direction
                if last_asymmetry_result is not None
                else "unknown"
            ),
            "asymmetry_ratio": (
                round(last_asymmetry_result.ratio, 2)
                if last_asymmetry_result is not None
                else None
            ),
        }

    def _build_reflector_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build reflector quality status (REFL-04). Always present."""
        scorer = health_data["reflector"]["scorer"]
        if scorer is not None:
            statuses = scorer.get_all_statuses()
            return {
                "available": True,
                "hosts": {
                    s.host: {
                        "score": round(s.score, 3),
                        "status": s.status,
                        "measurements": s.measurements,
                    }
                    for s in statuses
                },
            }
        return {"available": True, "hosts": {}}

    def _build_fusion_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build fusion state status (FUSE-05). Always present."""
        fusion_data = health_data["fusion"]
        if not fusion_data["enabled"]:
            healer = fusion_data["healer"]
            return {
                "enabled": False,
                "reason": "disabled",
                "heal_state": healer.state.value if healer is not None else "no_healer",
                "heal_grace_active": healer.is_grace_active if healer is not None else False,
            }

        irtt_rtt_val, active_source = self._resolve_fusion_rtt_sources(health_data)

        icmp_rtt_val = (
            round(fusion_data["icmp_filtered_rtt"], 2)
            if fusion_data["icmp_filtered_rtt"] is not None
            else None
        )
        fused_rtt_val = (
            round(fusion_data["fused_rtt"], 2)
            if fusion_data["fused_rtt"] is not None
            else None
        )
        # If IRTT went stale, trust active_source over cached fused value
        if active_source == "icmp_only":
            fused_rtt_val = None

        fusion: dict[str, Any] = {
            "enabled": True,
            "icmp_weight": fusion_data["icmp_weight"],
            "irtt_weight": round(1.0 - fusion_data["icmp_weight"], 2),
            "active_source": active_source,
            "fused_rtt_ms": fused_rtt_val,
            "icmp_rtt_ms": icmp_rtt_val,
            "irtt_rtt_ms": irtt_rtt_val,
        }

        self._add_fusion_healer_state(fusion, health_data)
        return fusion

    def _resolve_fusion_rtt_sources(
        self, health_data: dict[str, Any]
    ) -> tuple[float | None, str]:
        """Resolve IRTT RTT value and active source for fusion status."""
        irtt_rtt_val: float | None = None
        active_source = "icmp_only"

        irtt_thread = health_data["irtt"]["thread"]
        if irtt_thread is not None:
            _irtt_result = irtt_thread.get_latest()
            if _irtt_result is not None:
                _age = time.monotonic() - _irtt_result.timestamp
                _cadence = irtt_thread.cadence_sec
                if _age <= _cadence * 3 and _irtt_result.rtt_mean_ms > 0:
                    irtt_rtt_val = round(_irtt_result.rtt_mean_ms, 2)
                    active_source = "fused"

        return irtt_rtt_val, active_source

    def _add_fusion_healer_state(
        self, fusion: dict[str, Any], health_data: dict[str, Any]
    ) -> None:
        """Add fusion healer state to fusion dict (Phase 119: FUSE-05)."""
        healer = health_data["fusion"]["healer"]
        if healer is not None:
            fusion["heal_state"] = healer.state.value
            fusion["pearson_correlation"] = (
                round(healer.pearson_r, 4)
                if healer.pearson_r is not None
                else None
            )
            fusion["correlation_window_avg"] = (
                round(healer.window_avg, 4)
                if healer.window_avg is not None
                else None
            )
            fusion["heal_grace_active"] = healer.is_grace_active
        else:
            fusion["heal_state"] = "no_healer"
            fusion["pearson_correlation"] = None
            fusion["correlation_window_avg"] = None
            fusion["heal_grace_active"] = False

    def _build_asymmetry_gate_section(
        self, health_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build asymmetry gate status section (ASYM-01 through ASYM-03)."""
        gate = health_data.get("asymmetry_gate")
        if gate is None:
            return {"enabled": False}
        return {
            "enabled": gate["enabled"],
            "active": gate["active"],
            "downstream_streak": gate["downstream_streak"],
            "damping_factor": gate["damping_factor"],
            "last_result_age_sec": (
                round(gate["last_result_age_sec"], 1)
                if gate["last_result_age_sec"] is not None
                else None
            ),
        }

    def _build_cake_signal_section(
        self, health_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build CAKE signal status section (Phase 159, CAKE-04).

        Returns None if CAKE signal is not supported or not enabled.
        """
        cake_data = health_data.get("cake_signal")
        if cake_data is None:
            return None
        if not cake_data.get("supported", False) or not cake_data.get("enabled", False):
            return None

        def _snap_to_dict(snap: Any) -> dict[str, Any] | None:
            if snap is None:
                return None
            return {
                "drop_rate": round(snap.drop_rate, 1),
                "total_drop_rate": round(snap.total_drop_rate, 1),
                "backlog_bytes": snap.backlog_bytes,
                "peak_delay_us": snap.peak_delay_us,
                "cold_start": snap.cold_start,
                "tins": [
                    {
                        "name": t.name,
                        "drop_delta": t.drop_delta,
                        "backlog_bytes": t.backlog_bytes,
                        "peak_delay_us": t.peak_delay_us,
                    }
                    for t in snap.tins
                ],
            }

        result: dict[str, Any] = {
            "download": _snap_to_dict(cake_data.get("download")),
            "upload": _snap_to_dict(cake_data.get("upload")),
        }

        # Phase 160: Detection state (refractory, bypass/suppression counters)
        detection = cake_data.get("detection")
        if detection is not None and isinstance(detection, dict):
            result["detection"] = detection

        burst = cake_data.get("burst")
        if burst is not None and isinstance(burst, dict):
            result["burst"] = {
                "active": bool(burst.get("active", False)),
                "trigger_count": int(burst.get("trigger_count", 0) or 0),
                "last_reason": burst.get("last_reason"),
                "last_accel_ms": (
                    round(float(burst["last_accel_ms"]), 1)
                    if burst.get("last_accel_ms") is not None
                    else None
                ),
                "last_delta_ms": (
                    round(float(burst["last_delta_ms"]), 1)
                    if burst.get("last_delta_ms") is not None
                    else None
                ),
                "last_trigger_ago_sec": (
                    round(float(burst["last_trigger_ago_sec"]), 1)
                    if burst.get("last_trigger_ago_sec") is not None
                    else None
                ),
            }

        return result

    def _build_tuning_section(
        self, health_data: dict[str, Any], wan_controller: Any
    ) -> dict[str, Any]:
        """Build tuning state status. Always present (MagicMock safe)."""
        tuning_data = health_data["tuning"]
        if tuning_data["enabled"] is not True:
            return {"enabled": False, "reason": "disabled"}

        tuning_state = tuning_data["state"]
        if tuning_state is None or tuning_state.last_run_ts is None:
            return {
                "enabled": True,
                "last_run_ago_sec": None,
                "parameters": {},
                "recent_adjustments": [],
                "reason": "awaiting_data",
            }

        last_run_ago = round(time.monotonic() - tuning_state.last_run_ts, 1)
        params_dict = self._build_tuning_params_dict(wan_controller, tuning_state)

        recent = [
            {
                "parameter": adj.parameter,
                "old_value": adj.old_value,
                "new_value": adj.new_value,
                "confidence": adj.confidence,
                "rationale": adj.rationale,
            }
            for adj in tuning_state.recent_adjustments[-5:]
        ]

        tuning: dict[str, Any] = {
            "enabled": True,
            "last_run_ago_sec": last_run_ago,
            "parameters": params_dict,
            "recent_adjustments": recent,
        }

        tuning["safety"] = self._build_tuning_safety_section(
            health_data, tuning_state
        )

        return tuning

    def _build_tuning_params_dict(
        self, wan_controller: Any, tuning_state: Any
    ) -> dict[str, Any]:
        """Build parameters dict with current tuned values and bounds."""
        params_dict: dict[str, Any] = {}
        for param_name, current_val in tuning_state.parameters.items():
            config = getattr(wan_controller, "config", None)
            if config is not None:
                tc = getattr(config, "tuning_config", None)
                if tc is not None and hasattr(tc, "bounds"):
                    bounds = tc.bounds.get(param_name)
                    if bounds is not None:
                        params_dict[param_name] = {
                            "current_value": current_val,
                            "bounds": {
                                "min": bounds.min_value,
                                "max": bounds.max_value,
                            },
                        }
                        continue
            params_dict[param_name] = {"current_value": current_val}
        return params_dict

    def _build_tuning_safety_section(
        self, health_data: dict[str, Any], tuning_state: Any
    ) -> dict[str, Any]:
        """Build tuning safety subsection (SAFE-01/02/03 visibility)."""
        tuning_data = health_data["tuning"]
        revert_count = sum(
            1
            for adj in tuning_state.recent_adjustments
            if adj.rationale and adj.rationale.startswith("REVERT:")
        )
        locks_dict = tuning_data["parameter_locks"]
        if isinstance(locks_dict, dict):
            now_mono = time.monotonic()
            locked_params = [p for p, exp in locks_dict.items() if now_mono < exp]
        else:
            locked_params = []
        pending = tuning_data["pending_observation"] is not None
        return {
            "revert_count": revert_count,
            "locked_parameters": locked_params,
            "pending_observation": pending,
        }

    def _build_storage_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
        """Build bounded storage contention status from in-memory telemetry."""
        return build_storage_status_section(
            health_data.get("storage"),
            health_data.get("storage_files", {}),
        )

    def _build_runtime_section(
        self, health_data: dict[str, Any], cycle_budget: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Build bounded runtime pressure section."""
        raw_runtime = health_data.get("runtime")
        runtime: dict[str, Any] = raw_runtime if isinstance(raw_runtime, dict) else {}
        cycle_status = cycle_budget.get("status") if isinstance(cycle_budget, dict) else None
        process_role = str(runtime.get("process", "autorate"))
        return build_runtime_status_section(
            process_role=process_role,
            rss_bytes=runtime.get("rss_bytes"),
            cycle_status=cycle_status,
        )

    def _build_alerting_section(self) -> dict[str, Any]:
        """Build alerting state section."""
        alerting: dict[str, Any] = {
            "enabled": False,
            "fire_count": 0,
            "active_cooldowns": [],
        }
        if self.controller and self.controller.wan_controllers:
            from wanctl.alert_engine import AlertEngine

            ae = self.controller.wan_controllers[0]["controller"].alert_engine
            if isinstance(ae, AlertEngine):
                cooldowns = ae.get_active_cooldowns()
                alerting = {
                    "enabled": ae.enabled,
                    "fire_count": ae.fire_count,
                    "active_cooldowns": [
                        {"type": k[0], "wan": k[1], "remaining_sec": round(v, 1)}
                        for k, v in cooldowns.items()
                    ],
                }
        return alerting

    def _build_summary_section(self, health: dict[str, Any]) -> dict[str, Any]:
        """Build compact operator-facing summary without altering detailed sections."""
        rows = [self._build_wan_summary_row(wan) for wan in health.get("wans", [])]
        return {
            "service": "autorate",
            "status": health.get("status", "unknown"),
            "wan_count": len(rows),
            "router_reachable": bool(health.get("router_reachable", False)),
            "alerts": self._build_alerting_summary(health.get("alerting")),
            "rows": rows,
            "degraded_wans": [row["name"] for row in rows if row["status"] == "degraded"],
            "warning_wans": [row["name"] for row in rows if row["status"] == "warning"],
        }

    def _build_wan_summary_row(self, wan: dict[str, Any]) -> dict[str, Any]:
        """Build compact per-WAN operator summary row."""
        router = wan.get("router_connectivity", {})
        storage = wan.get("storage", {})
        runtime = wan.get("runtime", {})
        cake_signal = wan.get("cake_signal", {})
        burst = cake_signal.get("burst") if isinstance(cake_signal, dict) else {}
        download = wan.get("download", {})
        upload = wan.get("upload", {})
        router_reachable = bool(router.get("is_reachable", False))
        storage_status = str(storage.get("status", "unknown"))
        runtime_status = str(runtime.get("status", "unknown"))
        download_state = str(download.get("state", "UNKNOWN"))
        upload_state = str(upload.get("state", "UNKNOWN"))
        return {
            "name": str(wan.get("name", "unknown")),
            "status": self._classify_wan_summary_status(
                router_reachable=router_reachable,
                storage_status=storage_status,
                runtime_status=runtime_status,
                download_state=download_state,
                upload_state=upload_state,
            ),
            "router_reachable": router_reachable,
            "download_state": download_state,
            "upload_state": upload_state,
            "download_rate_mbps": download.get("current_rate_mbps"),
            "upload_rate_mbps": upload.get("current_rate_mbps"),
            "storage_status": storage_status,
            "runtime_status": runtime_status,
            "burst_active": bool((burst or {}).get("active", False)),
            "burst_trigger_count": int((burst or {}).get("trigger_count", 0) or 0),
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

    def _classify_wan_summary_status(
        self,
        *,
        router_reachable: bool,
        storage_status: str,
        runtime_status: str,
        download_state: str,
        upload_state: str,
    ) -> str:
        """Classify compact WAN summary status for operator display."""
        if not router_reachable or storage_status == "critical" or runtime_status == "critical":
            return "degraded"
        if (
            storage_status == "warning"
            or runtime_status == "warning"
            or download_state in {"RED", "SOFT_RED"}
            or upload_state in {"RED", "SOFT_RED"}
        ):
            return "warning"
        return "ok"

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

        offset = params.get("offset", 0)
        limit = params.get("limit", 1000)

        # Query metrics from database with SQL-level pagination.
        paginated = query_metrics(
            db_path=DEFAULT_DB_PATH,
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=params.get("metrics"),
            wan=params.get("wan"),
            granularity=granularity,
            limit=limit,
            offset=offset,
        )
        total_count = count_metrics(
            db_path=DEFAULT_DB_PATH,
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=params.get("metrics"),
            wan=params.get("wan"),
            granularity=granularity,
        )

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
                    raise ValueError(
                        f"Invalid offset value: '{query_params['offset'][0]}'"
                    ) from None
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
            raise ValueError(
                f"Invalid duration format: '{value}'. Use format like '1h', '30m', '7d'"
            )
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
    if queue_controller.soft_red_streak >= queue_controller.soft_red_required:
        return "SOFT_RED"
    if queue_controller.green_streak >= queue_controller.green_required:
        return "GREEN"
    if queue_controller.green_streak > 0:
        return "GREEN"  # Building towards sustained GREEN
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

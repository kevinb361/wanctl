#!/usr/bin/env python3
"""
Continuous CAKE Auto-Tuning System
3-zone controller with EWMA smoothing for responsive congestion control
Expert-tuned for VDSL2, Cable, and Fiber connections

Runs as a persistent daemon with internal 50ms control loop.
"""

import argparse
import atexit
import logging
import os
import socket
import statistics
import sys
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any

from wanctl.alert_engine import AlertEngine
from wanctl.asymmetry_analyzer import DIRECTION_ENCODING, AsymmetryAnalyzer, AsymmetryResult
from wanctl.config_base import BaseConfig, get_storage_config
from wanctl.config_validation_utils import (
    deprecate_param,
    validate_bandwidth_order,
    validate_threshold_order,
)
from wanctl.daemon_utils import check_cleanup_deadline
from wanctl.error_handling import handle_errors
from wanctl.health_check import start_health_server, update_health_status
from wanctl.irtt_measurement import IRTTMeasurement, IRTTResult
from wanctl.irtt_thread import IRTTThread
from wanctl.lock_utils import LockAcquisitionError, LockFile, validate_and_acquire_lock
from wanctl.logging_utils import setup_logging
from wanctl.metrics import (
    record_autorate_cycle,
    record_ping_failure,
    record_rate_limit_event,
    record_router_update,
    start_metrics_server,
)
from wanctl.pending_rates import PendingRateChange
from wanctl.perf_profiler import (
    PROFILE_REPORT_INTERVAL,  # noqa: F401 -- re-exported for test compatibility
    OperationProfiler,
    PerfTimer,
    record_cycle_profiling,
)
from wanctl.rate_utils import RateLimiter, enforce_rate_bounds
from wanctl.reflector_scorer import ReflectorScorer
from wanctl.router_client import clear_router_password, get_router_client_with_failover
from wanctl.router_connectivity import RouterConnectivityState
from wanctl.rtt_measurement import RTTAggregationStrategy, RTTMeasurement
from wanctl.signal_processing import SignalProcessor, SignalResult
from wanctl.signal_utils import (
    SHUTDOWN_TIMEOUT_SECONDS,
    get_shutdown_event,
    is_reload_requested,
    is_shutdown_requested,
    register_signal_handlers,
    reset_reload_state,
)
from wanctl.storage import MetricsWriter
from wanctl.systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_watchdog,
)
from wanctl.timeouts import DEFAULT_AUTORATE_PING_TIMEOUT, DEFAULT_AUTORATE_SSH_TIMEOUT
from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult, TuningState
from wanctl.wan_controller_state import WANControllerState

# =============================================================================
# CONSTANTS
# =============================================================================

# Baseline RTT update threshold - only update baseline when delta is minimal
# This prevents baseline drift under load (architectural invariant)
DEFAULT_BASELINE_UPDATE_THRESHOLD_MS = 3.0

# Daemon cycle interval - target time between cycle starts (seconds)
# Production standard: 0.05s (50ms, 20Hz polling) - validated Phase 2 (2026-01-13)
# - 40x faster than original 2s baseline, sub-second congestion detection
# - Proven stable: 0% router CPU idle, 45% peak under RRUL stress
# - Utilization: 60-80% (30-40ms execution vs 50ms interval)
#
# Time-constant preservation when changing intervals:
# - New EWMA alpha = Old alpha × (New interval / Old interval)
# - New sample counts = Old samples × (Old interval / New interval)
# - Preserves wall-clock smoothing behavior
#
# Conservative alternatives: 100ms (20x speed, 2x headroom) or 250ms (8x speed, 4x headroom)
# See docs/PRODUCTION_INTERVAL.md for validation results and configuration guidance
#
# With 0.05s cycles and 0.85 factor_down, recovery from 920M to floor
# takes ~80 cycles = 4 seconds
CYCLE_INTERVAL_SECONDS = 0.05

# Periodic maintenance interval (seconds) - cleanup/downsample/vacuum every hour
MAINTENANCE_INTERVAL = 3600

# Default bloat thresholds (milliseconds)
DEFAULT_HARD_RED_BLOAT_MS = 80  # SOFT_RED -> RED transition threshold

# Baseline RTT sanity bounds (milliseconds)
# Typical home ISP latencies are 20-50ms. Anything below 10ms indicates local LAN,
# anything above 60ms suggests routing issues or corrupted state.
MIN_SANE_BASELINE_RTT = 10.0
MAX_SANE_BASELINE_RTT = 60.0

# Rate limiter defaults (protects router API during instability)
DEFAULT_RATE_LIMIT_MAX_CHANGES = 10  # Max changes per window
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60  # Window duration
FORCE_SAVE_INTERVAL_CYCLES = 1200  # Force state save every 60s (1200 * 50ms)
# PROFILE_REPORT_INTERVAL imported from perf_profiler (shared with steering)

# Conversion factors
MBPS_TO_BPS = 1_000_000


# =============================================================================
# CONFIGURATION
# =============================================================================


class Config(BaseConfig):
    """Configuration container loaded from YAML"""

    # Schema for autorate_continuous configuration validation
    SCHEMA = [
        # Queue names
        {"path": "queues.download", "type": str, "required": True},
        {"path": "queues.upload", "type": str, "required": True},
        # Continuous monitoring - required structure
        {"path": "continuous_monitoring.enabled", "type": bool, "required": True},
        {
            "path": "continuous_monitoring.baseline_rtt_initial",
            "type": (int, float),
            "required": True,
            "min": 1,
            "max": 500,
        },
        # Download parameters - ceiling is required, floors validated in _load_specific_fields
        {
            "path": "continuous_monitoring.download.ceiling_mbps",
            "type": (int, float),
            "required": True,
            "min": 1,
            "max": 10000,
        },
        {
            "path": "continuous_monitoring.download.step_up_mbps",
            "type": (int, float),
            "required": True,
            "min": 0.1,
            "max": 100,
        },
        {
            "path": "continuous_monitoring.download.factor_down",
            "type": float,
            "required": True,
            "min": 0.1,
            "max": 1.0,
        },
        {
            "path": "continuous_monitoring.download.factor_down_yellow",
            "type": float,
            "required": False,
            "min": 0.8,
            "max": 1.0,
        },
        {
            "path": "continuous_monitoring.download.green_required",
            "type": int,
            "required": False,
            "min": 1,
            "max": 10,
        },
        # Upload parameters
        {
            "path": "continuous_monitoring.upload.ceiling_mbps",
            "type": (int, float),
            "required": True,
            "min": 1,
            "max": 1000,
        },
        {
            "path": "continuous_monitoring.upload.step_up_mbps",
            "type": (int, float),
            "required": True,
            "min": 0.1,
            "max": 100,
        },
        {
            "path": "continuous_monitoring.upload.factor_down",
            "type": float,
            "required": True,
            "min": 0.1,
            "max": 1.0,
        },
        {
            "path": "continuous_monitoring.upload.factor_down_yellow",
            "type": float,
            "required": False,
            "min": 0.9,
            "max": 1.0,
        },
        {
            "path": "continuous_monitoring.upload.green_required",
            "type": int,
            "required": False,
            "min": 1,
            "max": 10,
        },
        # Thresholds
        {
            "path": "continuous_monitoring.thresholds.target_bloat_ms",
            "type": (int, float),
            "required": True,
            "min": 1,
            "max": 100,
        },
        {
            "path": "continuous_monitoring.thresholds.warn_bloat_ms",
            "type": (int, float),
            "required": True,
            "min": 1,
            "max": 200,
        },
        # Alpha values - optional if time_constant_sec is provided
        {
            "path": "continuous_monitoring.thresholds.alpha_baseline",
            "type": float,
            "required": False,
            "min": 0.0001,
            "max": 1.0,
        },
        {
            "path": "continuous_monitoring.thresholds.alpha_load",
            "type": float,
            "required": False,
            "min": 0.001,
            "max": 1.0,
        },
        # Time constants - preferred over raw alpha (auto-calculates alpha from interval)
        {
            "path": "continuous_monitoring.thresholds.baseline_time_constant_sec",
            "type": (int, float),
            "required": False,
            "min": 1,
            "max": 600,
        },
        {
            "path": "continuous_monitoring.thresholds.load_time_constant_sec",
            "type": (int, float),
            "required": False,
            "min": 0.05,
            "max": 10,
        },
        {
            "path": "continuous_monitoring.thresholds.accel_threshold_ms",
            "type": (int, float),
            "required": False,
            "min": 5,
            "max": 50,
        },
        # Baseline RTT bounds (optional - security validation)
        {
            "path": "continuous_monitoring.thresholds.baseline_rtt_bounds.min",
            "type": (int, float),
            "required": False,
            "min": 1,
            "max": 100,
        },
        {
            "path": "continuous_monitoring.thresholds.baseline_rtt_bounds.max",
            "type": (int, float),
            "required": False,
            "min": 10,
            "max": 500,
        },
        # Ping hosts
        {"path": "continuous_monitoring.ping_hosts", "type": list, "required": True},
    ]

    def _load_queue_config(self) -> None:
        """Load queue names with command injection validation."""
        self.queue_down = self.validate_identifier(
            self.data["queues"]["download"], "queues.download"
        )
        self.queue_up = self.validate_identifier(self.data["queues"]["upload"], "queues.upload")

    def _load_download_config(self, cm: dict) -> None:
        """Load download parameters with state-based floors and validation."""
        dl = cm["download"]
        # Support both legacy (single floor) and v2/v3 (state-based floors)
        if "floor_green_mbps" in dl:
            self.download_floor_green = dl["floor_green_mbps"] * MBPS_TO_BPS
            self.download_floor_yellow = dl["floor_yellow_mbps"] * MBPS_TO_BPS
            self.download_floor_soft_red = (
                dl.get("floor_soft_red_mbps", dl["floor_yellow_mbps"]) * MBPS_TO_BPS
            )  # Phase 2A
            self.download_floor_red = dl["floor_red_mbps"] * MBPS_TO_BPS
        else:
            # Legacy: use single floor for all states
            floor = dl["floor_mbps"] * MBPS_TO_BPS
            self.download_floor_green = floor
            self.download_floor_yellow = floor
            self.download_floor_soft_red = floor  # Phase 2A
            self.download_floor_red = floor
        self.download_ceiling = dl["ceiling_mbps"] * MBPS_TO_BPS
        self.download_step_up = dl["step_up_mbps"] * MBPS_TO_BPS
        self.download_factor_down = dl["factor_down"]
        # YELLOW decay factor: gentle 4% per cycle (vs RED's aggressive 15%)
        self.download_factor_down_yellow = dl.get("factor_down_yellow", 0.96)
        # Consecutive GREEN cycles required before stepping up (default 5)
        self.download_green_required = dl.get("green_required", 5)

        # Validate download floor ordering: red <= soft_red <= yellow <= green <= ceiling
        validate_bandwidth_order(
            name="download",
            floor_red=self.download_floor_red,
            floor_soft_red=self.download_floor_soft_red,
            floor_yellow=self.download_floor_yellow,
            floor_green=self.download_floor_green,
            ceiling=self.download_ceiling,
            convert_to_mbps=True,
            logger=logging.getLogger(__name__),
        )

    def _load_upload_config(self, cm: dict) -> None:
        """Load upload parameters with state-based floors and validation."""
        ul = cm["upload"]
        # Support both legacy (single floor) and v2 (state-based floors)
        if "floor_green_mbps" in ul:
            self.upload_floor_green = ul["floor_green_mbps"] * MBPS_TO_BPS
            self.upload_floor_yellow = ul["floor_yellow_mbps"] * MBPS_TO_BPS
            self.upload_floor_red = ul["floor_red_mbps"] * MBPS_TO_BPS
        else:
            # Legacy: use single floor for all states
            floor = ul["floor_mbps"] * MBPS_TO_BPS
            self.upload_floor_green = floor
            self.upload_floor_yellow = floor
            self.upload_floor_red = floor
        self.upload_ceiling = ul["ceiling_mbps"] * MBPS_TO_BPS
        self.upload_step_up = ul["step_up_mbps"] * MBPS_TO_BPS
        self.upload_factor_down = ul["factor_down"]
        # Upload YELLOW decay (gentler than download, default 0.94 = 6% per cycle)
        self.upload_factor_down_yellow = ul.get("factor_down_yellow", 0.94)
        # Consecutive GREEN cycles required before stepping up (default 5)
        self.upload_green_required = ul.get("green_required", 5)

        # Validate upload floor ordering: red <= yellow <= green <= ceiling
        validate_bandwidth_order(
            name="upload",
            floor_red=self.upload_floor_red,
            floor_yellow=self.upload_floor_yellow,
            floor_green=self.upload_floor_green,
            ceiling=self.upload_ceiling,
            convert_to_mbps=True,
            logger=logging.getLogger(__name__),
        )

    def _load_threshold_config(self, cm: dict) -> None:
        """Load threshold settings with ordering validation."""
        thresh = cm["thresholds"]
        self.target_bloat_ms = thresh["target_bloat_ms"]  # GREEN → YELLOW (15ms)
        self.warn_bloat_ms = thresh["warn_bloat_ms"]  # YELLOW → SOFT_RED (45ms)
        self.hard_red_bloat_ms = thresh.get("hard_red_bloat_ms", DEFAULT_HARD_RED_BLOAT_MS)

        # EWMA alpha calculation - prefer time constants (human-readable, interval-independent)
        # Formula: alpha = cycle_interval / time_constant
        logger = logging.getLogger(__name__)
        cycle_interval = CYCLE_INTERVAL_SECONDS

        # Deprecation: translate legacy alpha_baseline -> baseline_time_constant_sec
        _tc_from_baseline = deprecate_param(
            thresh, "alpha_baseline", "baseline_time_constant_sec", logger,
            transform_fn=lambda alpha: cycle_interval / alpha,
        )
        if _tc_from_baseline is not None:
            thresh["baseline_time_constant_sec"] = _tc_from_baseline

        # Deprecation: translate legacy alpha_load -> load_time_constant_sec
        _tc_from_load = deprecate_param(
            thresh, "alpha_load", "load_time_constant_sec", logger,
            transform_fn=lambda alpha: cycle_interval / alpha,
        )
        if _tc_from_load is not None:
            thresh["load_time_constant_sec"] = _tc_from_load

        # Baseline alpha: require either time_constant or raw alpha
        if "baseline_time_constant_sec" in thresh:
            tc = thresh["baseline_time_constant_sec"]
            self.alpha_baseline = cycle_interval / tc
            logger.info(
                f"Calculated alpha_baseline={self.alpha_baseline:.6f} from time_constant={tc}s"
            )
        elif "alpha_baseline" in thresh:
            self.alpha_baseline = thresh["alpha_baseline"]
        else:
            raise ValueError(
                "Config must specify either baseline_time_constant_sec or alpha_baseline"
            )

        # Load alpha: require either time_constant or raw alpha
        if "load_time_constant_sec" in thresh:
            tc = thresh["load_time_constant_sec"]
            self.alpha_load = cycle_interval / tc
            logger.info(f"Calculated alpha_load={self.alpha_load:.4f} from time_constant={tc}s")
        elif "alpha_load" in thresh:
            self.alpha_load = thresh["alpha_load"]
            # Warn if raw alpha seems miscalculated for current interval
            expected_tc = cycle_interval / self.alpha_load
            if expected_tc > 5.0:  # Time constant > 5 seconds is suspiciously slow
                logger.warning(
                    f"alpha_load={self.alpha_load} gives {expected_tc:.1f}s time constant - "
                    f"consider using load_time_constant_sec for clarity"
                )
        else:
            raise ValueError("Config must specify either load_time_constant_sec or alpha_load")
        # Baseline update threshold - only update baseline when delta is below this value
        # Prevents baseline drift under load (architectural invariant)
        self.baseline_update_threshold_ms = thresh.get(
            "baseline_update_threshold_ms", DEFAULT_BASELINE_UPDATE_THRESHOLD_MS
        )

        # Acceleration threshold for rate-of-change detection (Phase 3)
        # Detects sudden RTT spikes and triggers immediate RED state
        self.accel_threshold_ms = thresh.get("accel_threshold_ms", 15.0)

        # Baseline RTT security bounds - reject values outside this range
        bounds = thresh.get("baseline_rtt_bounds", {})
        self.baseline_rtt_min = bounds.get("min", MIN_SANE_BASELINE_RTT)
        self.baseline_rtt_max = bounds.get("max", MAX_SANE_BASELINE_RTT)

        # Validate threshold ordering: target < warn < hard_red
        # This ensures state transitions are logically correct
        validate_threshold_order(
            target_bloat_ms=self.target_bloat_ms,
            warn_bloat_ms=self.warn_bloat_ms,
            hard_red_bloat_ms=self.hard_red_bloat_ms,
            logger=logging.getLogger(__name__),
        )

    def _load_ping_config(self, cm: dict) -> None:
        """Load ping hosts and median setting."""
        self.ping_hosts = cm["ping_hosts"]
        self.use_median_of_three = cm.get("use_median_of_three", False)

    def _load_fallback_config(self, cm: dict) -> None:
        """Load fallback connectivity check settings."""
        fallback = cm.get("fallback_checks", {})
        self.fallback_enabled = fallback.get("enabled", True)  # Enabled by default
        self.fallback_check_gateway = fallback.get("check_gateway", True)
        self.fallback_check_tcp = fallback.get("check_tcp", True)
        self.fallback_gateway_ip = fallback.get("gateway_ip", "")
        self.fallback_tcp_targets = fallback.get(
            "tcp_targets",
            [
                ["1.1.1.1", 443],
                ["8.8.8.8", 443],
            ],
        )
        self.fallback_mode = fallback.get("fallback_mode", "graceful_degradation")
        self.fallback_max_cycles = fallback.get("max_fallback_cycles", 3)

    def _load_timeout_config(self) -> None:
        """Load timeout settings with defaults."""
        timeouts = self.data.get("timeouts", {})
        self.timeout_ssh_command = timeouts.get("ssh_command", DEFAULT_AUTORATE_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get("ping", DEFAULT_AUTORATE_PING_TIMEOUT)
        # Source IP for ICMP pings (multi-WAN VM: different source IPs route through different WANs)
        self.ping_source_ip: str | None = self.data.get("ping_source_ip", None)

    def _load_router_transport_config(self) -> None:
        """Load router transport settings (SSH or REST)."""
        router = self.data.get("router", {})
        self.router_transport = router.get("transport", "rest")  # Default to REST (2x faster than SSH, see docs/TRANSPORT_COMPARISON.md)
        # REST API specific settings (only used if transport=rest)
        self.router_password = router.get("password", "")
        self.router_port = router.get("port", 443)
        self.router_verify_ssl = router.get("verify_ssl", True)

    def _load_state_config(self) -> None:
        """Load state file path from config, falling back to lock-derived path."""
        explicit = self.data.get("state_file")
        if explicit:
            self.state_file = Path(explicit)
        else:
            lock_stem = self.lock_file.stem
            self.state_file = self.lock_file.parent / f"{lock_stem}_state.json"

    def _load_health_check_config(self) -> None:
        """Load health check settings with defaults."""
        health = self.data.get("health_check", {})
        self.health_check_enabled = health.get("enabled", True)
        self.health_check_host = health.get("host", "127.0.0.1")
        self.health_check_port = health.get("port", 9101)

    def _load_metrics_config(self) -> None:
        """Load metrics settings (Prometheus-compatible, disabled by default)."""
        metrics_config = self.data.get("metrics", {})
        self.metrics_enabled = metrics_config.get("enabled", False)
        self.metrics_host = metrics_config.get("host", "127.0.0.1")
        self.metrics_port = metrics_config.get("port", 9100)

    def _load_alerting_config(self) -> None:
        """Load alerting configuration.

        Validates the optional alerting: YAML section. Invalid config warns
        and disables the feature (does not crash). Feature is disabled by
        default per INFRA-05.

        Sets self.alerting_config to a dict with all fields when valid and
        enabled, or None when absent/disabled/invalid.
        """
        logger = logging.getLogger(__name__)
        alerting = self.data.get("alerting", {})

        if not alerting:
            self.alerting_config = None
            logger.info("Alerting: disabled (enable via alerting.enabled)")
            return

        # Validate 'enabled' field type
        enabled = alerting.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"alerting.enabled must be bool, got {type(enabled).__name__}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return

        if not enabled:
            self.alerting_config = None
            logger.info("Alerting: disabled (enable via alerting.enabled)")
            return

        # Validate default_cooldown_sec
        default_cooldown_sec = alerting.get("default_cooldown_sec", 300)
        if not isinstance(default_cooldown_sec, int) or isinstance(default_cooldown_sec, bool):
            logger.warning(
                f"alerting.default_cooldown_sec must be int, got {type(default_cooldown_sec).__name__}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return
        if default_cooldown_sec < 0:
            logger.warning(
                f"alerting.default_cooldown_sec must be >= 0, got {default_cooldown_sec}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return

        # Validate default_sustained_sec (congestion duration threshold)
        default_sustained_sec = alerting.get("default_sustained_sec", 60)
        if not isinstance(default_sustained_sec, int) or isinstance(
            default_sustained_sec, bool
        ):
            logger.warning(
                f"alerting.default_sustained_sec must be int, "
                f"got {type(default_sustained_sec).__name__}; disabling alerting"
            )
            self.alerting_config = None
            return
        if default_sustained_sec < 0:
            logger.warning(
                f"alerting.default_sustained_sec must be >= 0, "
                f"got {default_sustained_sec}; disabling alerting"
            )
            self.alerting_config = None
            return

        # Validate rules
        rules = alerting.get("rules", {})
        if not isinstance(rules, dict):
            logger.warning(
                f"alerting.rules must be a map, got {type(rules).__name__}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return

        # Validate each rule
        valid_severities = {"info", "warning", "critical"}
        for rule_name, rule in rules.items():
            if not isinstance(rule, dict):
                logger.warning(f"alerting.rules.{rule_name} must be a map; disabling alerting")
                self.alerting_config = None
                return
            severity = rule.get("severity")
            if severity is None:
                logger.warning(
                    f"alerting.rules.{rule_name} missing required 'severity'; disabling alerting"
                )
                self.alerting_config = None
                return
            if severity not in valid_severities:
                logger.warning(
                    f"alerting.rules.{rule_name}.severity must be one of {valid_severities}, "
                    f"got '{severity}'; disabling alerting"
                )
                self.alerting_config = None
                return

        webhook_url = alerting.get("webhook_url", "")
        # Expand ${ENV_VAR} references (same pattern as router password)
        if webhook_url and isinstance(webhook_url, str) and webhook_url.startswith("${") and webhook_url.endswith("}"):
            env_var = webhook_url[2:-1]
            webhook_url = os.environ.get(env_var, "")

        # Delivery config fields (Plan 77-02)
        mention_role_id = alerting.get("mention_role_id")
        if mention_role_id is not None and not isinstance(mention_role_id, str):
            logger.warning("alerting.mention_role_id must be string; ignoring")
            mention_role_id = None

        mention_severity = alerting.get("mention_severity", "critical")
        if mention_severity not in ("info", "recovery", "warning", "critical"):
            logger.warning(
                f"alerting.mention_severity invalid: '{mention_severity}'; "
                "defaulting to critical"
            )
            mention_severity = "critical"

        max_webhooks_per_minute = alerting.get("max_webhooks_per_minute", 20)
        if not isinstance(max_webhooks_per_minute, int) or max_webhooks_per_minute <= 0:
            logger.warning("alerting.max_webhooks_per_minute invalid; defaulting to 20")
            max_webhooks_per_minute = 20

        self.alerting_config = {
            "enabled": True,
            "webhook_url": webhook_url,
            "default_cooldown_sec": default_cooldown_sec,
            "default_sustained_sec": default_sustained_sec,
            "rules": rules,
            "mention_role_id": mention_role_id,
            "mention_severity": mention_severity,
            "max_webhooks_per_minute": max_webhooks_per_minute,
        }
        logger.info(f"Alerting: enabled ({len(rules)} rules configured)")

    def _load_signal_processing_config(self) -> None:
        """Load signal processing configuration.

        Validates the optional signal_processing: YAML section. Invalid config
        warns and falls back to defaults (does not crash). Signal processing is
        always active -- there is no enable/disable flag.

        Sets self.signal_processing_config to a dict with all parameters.
        """
        logger = logging.getLogger(__name__)
        sp = self.data.get("signal_processing", {})
        hampel = sp.get("hampel", {}) if isinstance(sp, dict) else {}

        # Validate and extract hampel parameters
        window_size = hampel.get("window_size", 7)
        if (
            not isinstance(window_size, int)
            or isinstance(window_size, bool)
            or window_size < 3
        ):
            logger.warning(
                f"signal_processing.hampel.window_size must be int >= 3, "
                f"got {window_size!r}; defaulting to 7"
            )
            window_size = 7

        sigma_threshold = hampel.get("sigma_threshold", 3.0)
        if (
            not isinstance(sigma_threshold, (int, float))
            or isinstance(sigma_threshold, bool)
            or sigma_threshold <= 0
        ):
            logger.warning(
                f"signal_processing.hampel.sigma_threshold must be positive number, "
                f"got {sigma_threshold!r}; defaulting to 3.0"
            )
            sigma_threshold = 3.0

        # Validate EWMA time constants
        jitter_tc = sp.get("jitter_time_constant_sec", 2.0) if isinstance(sp, dict) else 2.0
        if (
            not isinstance(jitter_tc, (int, float))
            or isinstance(jitter_tc, bool)
            or jitter_tc <= 0
        ):
            logger.warning(
                f"signal_processing.jitter_time_constant_sec must be positive number, "
                f"got {jitter_tc!r}; defaulting to 2.0"
            )
            jitter_tc = 2.0

        variance_tc = (
            sp.get("variance_time_constant_sec", 5.0) if isinstance(sp, dict) else 5.0
        )
        if (
            not isinstance(variance_tc, (int, float))
            or isinstance(variance_tc, bool)
            or variance_tc <= 0
        ):
            logger.warning(
                f"signal_processing.variance_time_constant_sec must be positive number, "
                f"got {variance_tc!r}; defaulting to 5.0"
            )
            variance_tc = 5.0

        self.signal_processing_config = {
            "hampel_window_size": window_size,
            "hampel_sigma_threshold": float(sigma_threshold),
            "jitter_time_constant_sec": float(jitter_tc),
            "variance_time_constant_sec": float(variance_tc),
        }
        logger.info(
            f"Signal processing: hampel(window={window_size}, sigma={sigma_threshold}), "
            f"jitter_tc={jitter_tc}s, variance_tc={variance_tc}s"
        )

    def _load_irtt_config(self) -> None:
        """Load IRTT measurement configuration.

        Validates the optional irtt: YAML section. Invalid config warns and
        falls back to defaults (does not crash). IRTT is disabled by default.

        Sets self.irtt_config to a dict consumed by IRTTMeasurement constructor.
        """
        logger = logging.getLogger(__name__)
        irtt = self.data.get("irtt", {})

        if not isinstance(irtt, dict):
            logger.warning(
                f"irtt config must be dict, got {type(irtt).__name__}; using defaults"
            )
            irtt = {}

        enabled = irtt.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"irtt.enabled must be bool, got {enabled!r}; defaulting to false"
            )
            enabled = False

        server = irtt.get("server", None)
        if server is not None and not isinstance(server, str):
            logger.warning(
                f"irtt.server must be str, got {server!r}; defaulting to None"
            )
            server = None

        port = irtt.get("port", 2112)
        if not isinstance(port, int) or isinstance(port, bool) or port < 1 or port > 65535:
            logger.warning(
                f"irtt.port must be int 1-65535, got {port!r}; defaulting to 2112"
            )
            port = 2112

        duration_sec = irtt.get("duration_sec", 1.0)
        if (
            not isinstance(duration_sec, (int, float))
            or isinstance(duration_sec, bool)
            or duration_sec <= 0
        ):
            logger.warning(
                f"irtt.duration_sec must be positive number, got {duration_sec!r}; "
                f"defaulting to 1.0"
            )
            duration_sec = 1.0

        interval_ms = irtt.get("interval_ms", 100)
        if (
            not isinstance(interval_ms, int)
            or isinstance(interval_ms, bool)
            or interval_ms < 1
        ):
            logger.warning(
                f"irtt.interval_ms must be positive int, got {interval_ms!r}; "
                f"defaulting to 100"
            )
            interval_ms = 100

        cadence_sec = irtt.get("cadence_sec", 10)
        if (
            not isinstance(cadence_sec, (int, float))
            or isinstance(cadence_sec, bool)
            or cadence_sec < 1
        ):
            logger.warning(
                f"irtt.cadence_sec must be number >= 1, got {cadence_sec!r}; "
                f"defaulting to 10"
            )
            cadence_sec = 10

        self.irtt_config = {
            "enabled": enabled,
            "server": server,
            "port": port,
            "duration_sec": float(duration_sec),
            "interval_ms": interval_ms,
            "cadence_sec": float(cadence_sec),
        }

        if enabled and server:
            logger.info(
                f"IRTT: enabled, server={server}:{port}, "
                f"burst={duration_sec}s@{interval_ms}ms, cadence={cadence_sec}s"
            )
        else:
            logger.info("IRTT: disabled (enable via irtt.enabled + irtt.server)")

    def _load_reflector_quality_config(self) -> None:
        """Load reflector quality scoring configuration.

        Validates the optional reflector_quality: YAML section. Invalid config
        warns and falls back to defaults (does not crash).

        Sets self.reflector_quality_config to a dict with all parameters.
        """
        logger = logging.getLogger(__name__)
        rq = self.data.get("reflector_quality", {})

        if not isinstance(rq, dict):
            logger.warning(
                f"reflector_quality config must be dict, got {type(rq).__name__}; "
                "using defaults"
            )
            rq = {}

        min_score = rq.get("min_score", 0.8)
        if not isinstance(min_score, (int, float)) or isinstance(min_score, bool):
            logger.warning(
                f"reflector_quality.min_score must be number, got {min_score!r}; "
                "defaulting to 0.8"
            )
            min_score = 0.8
        min_score = max(0.0, min(1.0, float(min_score)))

        window_size = rq.get("window_size", 50)
        if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 10:
            logger.warning(
                f"reflector_quality.window_size must be int >= 10, got {window_size!r}; "
                "defaulting to 50"
            )
            window_size = 50

        probe_interval_sec = rq.get("probe_interval_sec", 30)
        if (
            not isinstance(probe_interval_sec, (int, float))
            or isinstance(probe_interval_sec, bool)
            or probe_interval_sec < 1
        ):
            logger.warning(
                f"reflector_quality.probe_interval_sec must be number >= 1, "
                f"got {probe_interval_sec!r}; defaulting to 30"
            )
            probe_interval_sec = 30

        recovery_count = rq.get("recovery_count", 3)
        if (
            not isinstance(recovery_count, int)
            or isinstance(recovery_count, bool)
            or recovery_count < 1
        ):
            logger.warning(
                f"reflector_quality.recovery_count must be int >= 1, "
                f"got {recovery_count!r}; defaulting to 3"
            )
            recovery_count = 3

        self.reflector_quality_config = {
            "min_score": float(min_score),
            "window_size": window_size,
            "probe_interval_sec": float(probe_interval_sec),
            "recovery_count": recovery_count,
        }
        logger.info(
            f"Reflector quality: min_score={min_score}, window={window_size}, "
            f"probe_interval={probe_interval_sec}s, recovery_count={recovery_count}"
        )

    def _load_owd_asymmetry_config(self) -> None:
        """Load OWD asymmetry detection configuration.

        Validates the optional owd_asymmetry: YAML section. Invalid config
        warns and falls back to defaults (does not crash).

        Sets self.owd_asymmetry_config to a dict consumed by AsymmetryAnalyzer.
        """
        logger = logging.getLogger(__name__)
        owd = self.data.get("owd_asymmetry", {})

        if not isinstance(owd, dict):
            logger.warning(
                f"owd_asymmetry config must be dict, got {type(owd).__name__}; using defaults"
            )
            owd = {}

        ratio_threshold = owd.get("ratio_threshold", 2.0)
        if (
            not isinstance(ratio_threshold, (int, float))
            or isinstance(ratio_threshold, bool)
            or ratio_threshold < 1.0
        ):
            logger.warning(
                f"owd_asymmetry.ratio_threshold must be number >= 1.0, "
                f"got {ratio_threshold!r}; defaulting to 2.0"
            )
            ratio_threshold = 2.0

        self.owd_asymmetry_config = {"ratio_threshold": float(ratio_threshold)}

    def _load_fusion_config(self) -> None:
        """Load fusion configuration. Validates fusion: YAML section.

        Invalid config warns and falls back to defaults."""
        logger = logging.getLogger(__name__)
        fusion = self.data.get("fusion", {})

        if not isinstance(fusion, dict):
            logger.warning(
                f"fusion config must be dict, got {type(fusion).__name__}; using defaults"
            )
            fusion = {}

        icmp_weight = fusion.get("icmp_weight", 0.7)
        if (
            not isinstance(icmp_weight, (int, float))
            or isinstance(icmp_weight, bool)
            or icmp_weight < 0.0
            or icmp_weight > 1.0
        ):
            logger.warning(
                f"fusion.icmp_weight must be number 0.0-1.0, got {icmp_weight!r}; "
                "defaulting to 0.7"
            )
            icmp_weight = 0.7

        enabled = fusion.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"fusion.enabled must be bool, got {type(enabled).__name__}; "
                "defaulting to false"
            )
            enabled = False

        self.fusion_config = {
            "icmp_weight": float(icmp_weight),
            "enabled": enabled,
        }
        logger.info(
            f"Fusion: enabled={enabled}, icmp_weight={icmp_weight}, "
            f"irtt_weight={1.0 - icmp_weight}"
        )

    def _load_tuning_config(self) -> None:
        """Load adaptive tuning configuration.

        Validates the optional tuning: YAML section. Invalid config warns
        and disables the feature (does not crash). Feature is disabled by
        default per TUNE-01.

        Sets self.tuning_config to a TuningConfig when valid and enabled,
        or None when absent/disabled/invalid.
        """
        logger = logging.getLogger(__name__)
        tuning = self.data.get("tuning", {})

        if not tuning:
            self.tuning_config = None
            logger.info("Tuning: disabled (enable via tuning.enabled)")
            return

        # Validate 'enabled' field type
        enabled = tuning.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"tuning.enabled must be bool, got {type(enabled).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return

        if not enabled:
            self.tuning_config = None
            logger.info("Tuning: disabled (enable via tuning.enabled)")
            return

        # Validate cadence_sec (minimum 600 seconds = 10 minutes)
        cadence_sec = tuning.get("cadence_sec", 3600)
        if not isinstance(cadence_sec, int) or isinstance(cadence_sec, bool):
            logger.warning(
                f"tuning.cadence_sec must be int, got {type(cadence_sec).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return
        if cadence_sec < 600:
            logger.warning(
                f"tuning.cadence_sec must be >= 600 (10 minutes minimum), "
                f"got {cadence_sec}; disabling tuning"
            )
            self.tuning_config = None
            return

        # Validate lookback_hours (1-168)
        lookback_hours = tuning.get("lookback_hours", 24)
        if not isinstance(lookback_hours, int) or isinstance(lookback_hours, bool):
            logger.warning(
                f"tuning.lookback_hours must be int, got {type(lookback_hours).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return
        if lookback_hours < 1 or lookback_hours > 168:
            logger.warning(
                f"tuning.lookback_hours must be 1-168, got {lookback_hours}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return

        # Validate warmup_hours (1-24)
        warmup_hours = tuning.get("warmup_hours", 1)
        if not isinstance(warmup_hours, int) or isinstance(warmup_hours, bool):
            logger.warning(
                f"tuning.warmup_hours must be int, got {type(warmup_hours).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return
        if warmup_hours < 1 or warmup_hours > 24:
            logger.warning(
                f"tuning.warmup_hours must be 1-24, got {warmup_hours}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return

        # Validate max_step_pct (1.0-50.0)
        max_step_pct = tuning.get("max_step_pct", 10.0)
        if not isinstance(max_step_pct, (int, float)) or isinstance(max_step_pct, bool):
            logger.warning(
                f"tuning.max_step_pct must be number, got {type(max_step_pct).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return
        max_step_pct = float(max_step_pct)
        if max_step_pct < 1.0 or max_step_pct > 50.0:
            logger.warning(
                f"tuning.max_step_pct must be 1.0-50.0, got {max_step_pct}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return

        # Parse bounds dict
        raw_bounds = tuning.get("bounds", {})
        if not isinstance(raw_bounds, dict):
            logger.warning(
                f"tuning.bounds must be a dict, got {type(raw_bounds).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return

        bounds: dict[str, SafetyBounds] = {}
        for param_name, bound_spec in raw_bounds.items():
            if not isinstance(bound_spec, dict):
                logger.warning(
                    f"tuning.bounds.{param_name} must be a dict with min/max, "
                    f"got {type(bound_spec).__name__}; disabling tuning"
                )
                self.tuning_config = None
                return

            min_val = bound_spec.get("min")
            max_val = bound_spec.get("max")

            if min_val is None or max_val is None:
                logger.warning(
                    f"tuning.bounds.{param_name} must have 'min' and 'max' keys; "
                    "disabling tuning"
                )
                self.tuning_config = None
                return

            if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
                logger.warning(
                    f"tuning.bounds.{param_name} min/max must be numeric; "
                    "disabling tuning"
                )
                self.tuning_config = None
                return

            if min_val > max_val:
                logger.warning(
                    f"tuning.bounds.{param_name} min ({min_val}) > max ({max_val}); "
                    "disabling tuning"
                )
                self.tuning_config = None
                return

            bounds[param_name] = SafetyBounds(min_value=float(min_val), max_value=float(max_val))

        self.tuning_config = TuningConfig(
            enabled=True,
            cadence_sec=cadence_sec,
            lookback_hours=lookback_hours,
            warmup_hours=warmup_hours,
            max_step_pct=max_step_pct,
            bounds=bounds,
        )
        logger.info(
            f"Tuning: enabled (cadence={cadence_sec}s, lookback={lookback_hours}h, "
            f"{len(bounds)} bounds)"
        )

    def _load_specific_fields(self) -> None:
        """Load autorate-specific configuration fields (orchestration only)."""
        # Queues (validated to prevent command injection)
        self._load_queue_config()

        # Continuous monitoring parameters
        cm = self.data["continuous_monitoring"]
        self.enabled = cm["enabled"]
        self.baseline_rtt_initial = cm["baseline_rtt_initial"]

        # Download parameters (STATE-BASED FLOORS - Phase 2A: 4-state)
        self._load_download_config(cm)

        # Upload parameters (STATE-BASED FLOORS)
        self._load_upload_config(cm)

        # Thresholds (depends on continuous_monitoring section)
        self._load_threshold_config(cm)

        # Ping configuration
        self._load_ping_config(cm)

        # Fallback connectivity checks
        self._load_fallback_config(cm)

        # Timeouts
        self._load_timeout_config()

        # Router transport (SSH or REST)
        self._load_router_transport_config()

        # State file (derived from lock_file set by BaseConfig)
        self._load_state_config()

        # Health check
        self._load_health_check_config()

        # Metrics
        self._load_metrics_config()

        # Alerting (optional, disabled by default per INFRA-05)
        self._load_alerting_config()

        # Signal processing (always active, no enable/disable flag)
        self._load_signal_processing_config()

        # IRTT measurement (optional, disabled by default)
        self._load_irtt_config()

        # Reflector quality scoring (optional, all defaults if absent)
        self._load_reflector_quality_config()

        # OWD asymmetry detection (optional, all defaults if absent)
        self._load_owd_asymmetry_config()

        # Dual-signal fusion (optional, defaults if absent)
        self._load_fusion_config()

        # Adaptive tuning (optional, disabled by default)
        self._load_tuning_config()


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================


class RouterOS:
    """RouterOS interface for setting queue limits.

    Supports multiple transports:
    - ssh: SSH via paramiko - uses SSH keys
    - rest: REST API via HTTPS (default) - uses password authentication

    Transport is selected via config.router_transport field.
    """

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        # Use factory function to get appropriate client (SSH or REST) with failover
        self.client = get_router_client_with_failover(config, logger)

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Set CAKE limits for one WAN using a single batched router command"""
        self.logger.debug(f"{wan}: Setting limits DOWN={down_bps} UP={up_bps}")

        # WAN name for queue type (e.g., "ATT" -> "att", "Spectrum" -> "spectrum")
        wan_lower = self.config.wan_name.lower()

        # Batch both queue commands into a single SSH call for lower latency
        # RouterOS supports semicolon-separated commands
        cmd = (
            f'/queue tree set [find name="{self.config.queue_down}"] '
            f"queue=cake-down-{wan_lower} max-limit={down_bps}; "
            f'/queue tree set [find name="{self.config.queue_up}"] '
            f"queue=cake-up-{wan_lower} max-limit={up_bps}"
        )

        rc, _, _ = self.client.run_cmd(cmd)
        if rc != 0:
            self.logger.error(f"Failed to set queue limits: {cmd}")
            return False

        return True


# Note: RTTMeasurement class is now unified in rtt_measurement.py
# This module imports it from there


# =============================================================================
# QUEUE CONTROLLER (3-ZONE LOGIC)
# =============================================================================


class QueueController:
    """Controls one queue (download or upload) with 3-zone or 4-zone logic"""

    def __init__(
        self,
        name: str,
        floor_green: int,
        floor_yellow: int,
        floor_soft_red: int,
        floor_red: int,
        ceiling: int,
        step_up: int,
        factor_down: float,
        factor_down_yellow: float = 1.0,
        green_required: int = 5,
    ):
        self.name = name
        self.floor_green_bps = floor_green
        self.floor_yellow_bps = floor_yellow
        self.floor_soft_red_bps = floor_soft_red  # Phase 2A
        self.floor_red_bps = floor_red
        self.ceiling_bps = ceiling
        self.step_up_bps = step_up
        self.factor_down = factor_down
        self.factor_down_yellow = (
            factor_down_yellow  # Gentle decay for YELLOW (default 1.0 = no decay)
        )
        self.current_rate = ceiling  # Start at ceiling

        # Hysteresis counters (require consecutive green cycles before stepping up)
        self.green_streak = 0
        self.soft_red_streak = 0  # Phase 2A: Track SOFT_RED sustain
        self.red_streak = 0
        self.green_required = green_required  # Consecutive GREEN cycles before stepping up
        self.soft_red_required = 1  # Reduced from 3 for faster response (50ms vs 150ms)

        # Track previous state for transition detection
        self._last_zone: str = "GREEN"

    def adjust(
        self, baseline_rtt: float, load_rtt: float, target_delta: float, warn_delta: float
    ) -> tuple[str, int, str | None]:
        """
        Apply 3-zone logic with hysteresis and return (zone, new_rate, transition_reason)

        Zones:
        - GREEN: delta <= target_delta -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: target_delta < delta <= warn_delta -> hold steady
        - RED: delta > warn_delta -> aggressively back off (immediate)

        Hysteresis:
        - RED: Immediate step-down on 1 red sample
        - GREEN: Require 5 consecutive green cycles before stepping up (prevents seesaw)

        Returns:
            (zone, new_rate, transition_reason)
            transition_reason is None if no state change, otherwise explains why
        """
        delta = load_rtt - baseline_rtt

        # Update streak counters
        if delta > warn_delta:
            # RED zone
            self.red_streak += 1
            self.green_streak = 0
            zone = "RED"
        elif delta > target_delta:
            # YELLOW zone
            self.green_streak = 0
            self.red_streak = 0
            zone = "YELLOW"
        else:
            # GREEN zone
            self.green_streak += 1
            self.red_streak = 0
            zone = "GREEN"

        # Apply rate adjustments with hysteresis
        new_rate = self.current_rate

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        elif zone == "YELLOW":
            # YELLOW: Gentle decay to prevent congestion buildup
            new_rate = int(self.current_rate * self.factor_down_yellow)
        # else: GREEN but not sustained -> hold steady

        # Enforce floor and ceiling constraints
        new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)

        self.current_rate = new_rate

        # Track state transitions with reason
        transition_reason: str | None = None
        if zone != self._last_zone:
            if zone == "RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded warn threshold {warn_delta}ms"
                )
            elif zone == "YELLOW":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded target threshold {target_delta}ms"
                )
            elif zone == "GREEN":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms fell below target threshold {target_delta}ms"
                )
            self._last_zone = zone

        return zone, new_rate, transition_reason

    def adjust_4state(
        self,
        baseline_rtt: float,
        load_rtt: float,
        green_threshold: float,
        soft_red_threshold: float,
        hard_red_threshold: float,
    ) -> tuple[str, int, str | None]:
        """
        Apply 4-state logic with hysteresis and return (state, new_rate, transition_reason)

        Phase 2A: Download-only (Spectrum download)
        Upload continues to use 3-state adjust() method

        States (based on RTT delta from baseline):
        - GREEN: delta <= 15ms -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: 15ms < delta <= 45ms -> hold steady
        - SOFT_RED: 45ms < delta <= 80ms -> clamp to soft_red floor and HOLD (no steering)
        - RED: delta > 80ms -> aggressive backoff (immediate)

        Hysteresis:
        - RED: Immediate on 1 sample
        - SOFT_RED: Requires 3 consecutive samples (~6 seconds)
        - GREEN: Requires 5 consecutive samples before stepping up
        - YELLOW: Immediate

        Returns:
            (zone, new_rate, transition_reason)
            transition_reason is None if no state change, otherwise explains why
        """
        delta = load_rtt - baseline_rtt

        # Determine raw state based on thresholds
        if delta > hard_red_threshold:
            raw_state = "RED"
        elif delta > soft_red_threshold:
            raw_state = "SOFT_RED"
        elif delta > green_threshold:
            raw_state = "YELLOW"
        else:
            raw_state = "GREEN"

        # Apply sustain logic for SOFT_RED
        # SOFT_RED requires 3 consecutive samples to confirm
        if raw_state == "SOFT_RED":
            self.soft_red_streak += 1
            self.green_streak = 0
            self.red_streak = 0

            if self.soft_red_streak >= self.soft_red_required:
                zone = "SOFT_RED"
            else:
                # Not sustained yet - stay in YELLOW
                zone = "YELLOW"
        elif raw_state == "RED":
            self.red_streak += 1
            self.soft_red_streak = 0
            self.green_streak = 0
            zone = "RED"
        elif raw_state == "YELLOW":
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            zone = "YELLOW"
        else:  # GREEN
            self.green_streak += 1
            self.soft_red_streak = 0
            self.red_streak = 0
            zone = "GREEN"

        # Apply rate adjustments with state-appropriate floors
        new_rate = self.current_rate

        # Determine appropriate floor based on state
        state_floor = self.floor_green_bps  # Default

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
            state_floor = self.floor_red_bps
        elif zone == "SOFT_RED":
            # SOFT_RED: Clamp to soft_red floor and HOLD (no repeated decay)
            # Keep current rate but enforce soft_red floor
            state_floor = self.floor_soft_red_bps
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        elif zone == "YELLOW":
            # YELLOW: Gentle decay to prevent congestion buildup
            # Uses factor_down_yellow (default 0.96 = 4% per cycle)
            new_rate = int(self.current_rate * self.factor_down_yellow)
            state_floor = self.floor_yellow_bps
        # else: GREEN but not sustained -> use default floor_green_bps

        # Enforce floor and ceiling constraints based on current state
        new_rate = enforce_rate_bounds(new_rate, floor=state_floor, ceiling=self.ceiling_bps)

        self.current_rate = new_rate

        # Track state transitions with reason
        transition_reason: str | None = None
        if zone != self._last_zone:
            if zone == "RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded hard_red threshold {hard_red_threshold}ms"
                )
            elif zone == "SOFT_RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded soft_red threshold {soft_red_threshold}ms"
                )
            elif zone == "YELLOW":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded green threshold {green_threshold}ms"
                )
            elif zone == "GREEN":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms fell below green threshold {green_threshold}ms"
                )
            self._last_zone = zone

        return zone, new_rate, transition_reason


# =============================================================================
# ADAPTIVE TUNING HELPERS
# =============================================================================


def _apply_tuning_to_controller(
    wc: "WANController",
    results: list[TuningResult],
) -> None:
    """Apply tuning results to WANController attributes.

    Maps parameter names to controller attributes:
      target_bloat_ms       -> green_threshold + target_delta
      warn_bloat_ms         -> soft_red_threshold + warn_delta
      hard_red_bloat_ms     -> hard_red_threshold
      alpha_load            -> alpha_load
      alpha_baseline        -> alpha_baseline
      hampel_sigma_threshold -> signal_processor._sigma_threshold
      hampel_window_size    -> signal_processor._window_size + deque resize
      load_time_constant_sec -> alpha_load (via alpha = 0.05 / tc)
      fusion_icmp_weight    -> _fusion_icmp_weight
      reflector_min_score   -> _reflector_scorer._min_score
      baseline_rtt_min      -> baseline_rtt_min
      baseline_rtt_max      -> baseline_rtt_max

    Also updates TuningState with recent adjustments (capped at 10).
    """
    for r in results:
        if r.parameter == "target_bloat_ms":
            wc.green_threshold = r.new_value
            wc.target_delta = r.new_value  # Legacy alias
        elif r.parameter == "warn_bloat_ms":
            wc.soft_red_threshold = r.new_value
            wc.warn_delta = r.new_value  # Legacy alias
        elif r.parameter == "hard_red_bloat_ms":
            wc.hard_red_threshold = r.new_value
        elif r.parameter == "alpha_load":
            wc.alpha_load = r.new_value
        elif r.parameter == "alpha_baseline":
            wc.alpha_baseline = r.new_value
        elif r.parameter == "hampel_sigma_threshold":
            wc.signal_processor._sigma_threshold = r.new_value
        elif r.parameter == "hampel_window_size":
            new_size = round(r.new_value)
            wc.signal_processor._window_size = new_size
            wc.signal_processor._window = deque(
                wc.signal_processor._window, maxlen=new_size
            )
            wc.signal_processor._outlier_window = deque(
                wc.signal_processor._outlier_window, maxlen=new_size
            )
        elif r.parameter == "load_time_constant_sec":
            # Convert time constant to alpha: alpha = cycle_interval / tc
            # Using 0.05 (50ms) as the cycle interval constant.
            # Tuning operates in tc domain (0.5-10s range) where
            # clamp_to_step's round(1) and trivial filter work correctly;
            # we convert to alpha only at apply time (Pitfall 3 fix).
            wc.alpha_load = 0.05 / r.new_value
        elif r.parameter == "fusion_icmp_weight":
            wc._fusion_icmp_weight = r.new_value
        elif r.parameter == "reflector_min_score":
            wc._reflector_scorer._min_score = r.new_value
        elif r.parameter == "baseline_rtt_min":
            wc.baseline_rtt_min = r.new_value
        elif r.parameter == "baseline_rtt_max":
            wc.baseline_rtt_max = r.new_value

    # Update TuningState with recent adjustments
    if results and wc._tuning_state is not None:
        params = dict(wc._tuning_state.parameters)
        for r in results:
            params[r.parameter] = r.new_value
        # Keep only last 10 adjustments
        recent = list(wc._tuning_state.recent_adjustments) + list(results)
        recent = recent[-10:]
        wc._tuning_state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic(),
            recent_adjustments=recent,
            parameters=params,
        )


# =============================================================================
# WAN CONTROLLER
# =============================================================================


class WANController:
    """Controls both download and upload for one WAN"""

    def __init__(
        self,
        wan_name: str,
        config: Config,
        router: RouterOS,
        rtt_measurement: RTTMeasurement,
        logger: logging.Logger,
    ):
        self.wan_name = wan_name
        self.config = config
        self.router = router
        self.rtt_measurement = rtt_measurement
        self.logger = logger

        # Router connectivity tracking for cycle-level failure detection
        self.router_connectivity = RouterConnectivityState(self.logger)

        # Pending rate changes for router outage resilience (ERRR-03)
        self.pending_rates = PendingRateChange()

        # Initialize baseline from config (will be measured and updated)
        self.baseline_rtt = config.baseline_rtt_initial
        self.load_rtt = self.baseline_rtt

        # Rate-of-change (acceleration) detection for sudden RTT spikes
        self.previous_load_rtt = self.load_rtt
        self.accel_threshold = config.accel_threshold_ms

        # Create queue controllers
        self.download = QueueController(
            name=f"{wan_name}-Download",
            floor_green=config.download_floor_green,
            floor_yellow=config.download_floor_yellow,
            floor_soft_red=config.download_floor_soft_red,  # Phase 2A
            floor_red=config.download_floor_red,
            ceiling=config.download_ceiling,
            step_up=config.download_step_up,
            factor_down=config.download_factor_down,
            factor_down_yellow=config.download_factor_down_yellow,  # YELLOW decay
            green_required=config.download_green_required,  # Faster recovery
        )

        self.upload = QueueController(
            name=f"{wan_name}-Upload",
            floor_green=config.upload_floor_green,
            floor_yellow=config.upload_floor_yellow,
            floor_soft_red=config.upload_floor_yellow,  # Upload uses yellow for soft_red
            floor_red=config.upload_floor_red,
            ceiling=config.upload_ceiling,
            step_up=config.upload_step_up,
            factor_down=config.upload_factor_down,
            factor_down_yellow=config.upload_factor_down_yellow,  # Upload YELLOW decay
            green_required=config.upload_green_required,  # Faster recovery
        )

        # Thresholds (Phase 2A: 4-state for download, 3-state for upload)
        self.green_threshold = config.target_bloat_ms  # 15ms: GREEN → YELLOW
        self.soft_red_threshold = config.warn_bloat_ms  # 45ms: YELLOW → SOFT_RED
        self.hard_red_threshold = config.hard_red_bloat_ms  # 80ms: SOFT_RED → RED
        # Legacy 3-state thresholds (for upload)
        self.target_delta = config.target_bloat_ms
        self.warn_delta = config.warn_bloat_ms
        self.alpha_baseline = config.alpha_baseline
        self.alpha_load = config.alpha_load
        self.baseline_update_threshold = config.baseline_update_threshold_ms
        self.baseline_rtt_min = config.baseline_rtt_min
        self.baseline_rtt_max = config.baseline_rtt_max

        # Ping configuration
        self.ping_hosts = config.ping_hosts
        self.use_median_of_three = config.use_median_of_three

        # =====================================================================
        # FLASH WEAR PROTECTION - Track last applied rates
        # =====================================================================
        # RouterOS writes queue changes to NAND flash. To prevent excessive
        # flash wear, we only send updates when rates actually change.
        # DO NOT REMOVE THIS - it protects the router's flash memory.
        # =====================================================================
        self.last_applied_dl_rate: int | None = None
        self.last_applied_ul_rate: int | None = None

        # =====================================================================
        # RATE LIMITER - Protect router API during instability
        # =====================================================================
        # Limits configuration changes to prevent API overload during rapid
        # state oscillations. Default: 10 changes per 60 seconds.
        # =====================================================================
        self.rate_limiter = RateLimiter(
            max_changes=DEFAULT_RATE_LIMIT_MAX_CHANGES,
            window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        )
        # Track if we've logged about rate limiting (log once per throttle window)
        self._rate_limit_logged = False

        # =====================================================================
        # FALLBACK CONNECTIVITY TRACKING
        # =====================================================================
        # Track consecutive cycles where ICMP failed but other connectivity exists.
        # Used for graceful degradation when ICMP is filtered but WAN works.
        # =====================================================================
        self.icmp_unavailable_cycles = 0

        # =====================================================================
        # STATE PERSISTENCE MANAGER
        # =====================================================================
        # Separates persistence concerns from business logic
        # =====================================================================
        self.state_manager = WANControllerState(
            state_file=config.state_file, logger=logger, wan_name=wan_name
        )
        # Congestion zone for state file export (read by steering daemon)
        self._dl_zone: str = "GREEN"
        self._ul_zone: str = "GREEN"
        # Periodic force save counter (safety net against crashes)
        self._cycles_since_forced_save = 0

        # =====================================================================
        # METRICS HISTORY STORAGE (optional)
        # =====================================================================
        # SQLite-based storage for historical metrics analysis.
        # Disabled if storage.db_path not configured in YAML.
        # =====================================================================
        storage_config = get_storage_config(config.data)
        self._metrics_writer: MetricsWriter | None = None
        db_path = storage_config.get("db_path")
        if db_path and isinstance(db_path, str):
            self._metrics_writer = MetricsWriter(Path(db_path))
            self.logger.info(f"{wan_name}: Metrics history enabled, db={db_path}")

        # =====================================================================
        # ALERT ENGINE + WEBHOOK DELIVERY
        # =====================================================================
        # AlertEngine for per-event cooldown suppression and persistence.
        # WebhookDelivery for Discord notification dispatch (non-blocking).
        # Instantiated from alerting_config (disabled by default).
        # =====================================================================
        ac = self.config.alerting_config
        if ac:
            # Validate webhook_url
            url = ac["webhook_url"]
            if url and not url.startswith("https://"):
                self.logger.warning(
                    "alerting.webhook_url must start with https://; delivery disabled"
                )
                url = ""
            if not url:
                self.logger.warning(
                    "alerting.webhook_url not set; alerts will fire and persist "
                    "but not deliver"
                )

            from wanctl import __version__
            from wanctl.webhook_delivery import DiscordFormatter, WebhookDelivery

            formatter = DiscordFormatter(version=__version__, container_id=wan_name)
            self._webhook_delivery: WebhookDelivery | None = WebhookDelivery(
                formatter=formatter,
                webhook_url=url,
                max_per_minute=ac["max_webhooks_per_minute"],
                writer=self._metrics_writer,
                mention_role_id=ac["mention_role_id"],
                mention_severity=ac["mention_severity"],
            )
            self.alert_engine = AlertEngine(
                enabled=True,
                default_cooldown_sec=ac["default_cooldown_sec"],
                rules=ac["rules"],
                writer=self._metrics_writer,
                delivery_callback=self._webhook_delivery.deliver,
            )
        else:
            self._webhook_delivery = None
            self.alert_engine = AlertEngine(enabled=False, default_cooldown_sec=300, rules={})

        # =====================================================================
        # SIGNAL PROCESSING (Phase 88: observation mode)
        # =====================================================================
        # Pre-EWMA filter: Hampel outlier detection, jitter/variance tracking,
        # confidence scoring. Always active. Filtered RTT feeds EWMA; other
        # metrics are observational only (no control decisions).
        # =====================================================================
        self.signal_processor = SignalProcessor(
            wan_name=wan_name,
            config=config.signal_processing_config,
            logger=logger,
        )
        # Store last signal result for future Phase 92 metrics/health endpoint
        self._last_signal_result: SignalResult | None = None

        # =====================================================================
        # IRTT OBSERVATION MODE (Phase 90)
        # =====================================================================
        # Background IRTT thread reference (set by main() if IRTT active).
        # Protocol correlation tracks ICMP/UDP RTT ratio for deprioritization
        # detection.  First detection logs at INFO, repeat at DEBUG, recovery
        # at INFO.
        # =====================================================================
        self._irtt_thread: IRTTThread | None = None  # Set by main() if IRTT active
        self._irtt_correlation: float | None = None
        self._irtt_deprioritization_logged: bool = False
        self._last_irtt_write_ts: float | None = None  # IRTT dedup (OBSV-04)

        # =====================================================================
        # OWD ASYMMETRY DETECTION (Phase 94: ASYM-01 through ASYM-03)
        # =====================================================================
        # Directional congestion detection from IRTT send_delay vs receive_delay.
        # Computes ratio-based asymmetry (NTP-independent). Result stored for
        # health endpoint and future Phase 96 fusion consumption.
        # =====================================================================
        owd_config = config.owd_asymmetry_config
        self._asymmetry_analyzer: AsymmetryAnalyzer | None = AsymmetryAnalyzer(
            ratio_threshold=owd_config["ratio_threshold"],
            logger=logger,
            wan_name=wan_name,
        )
        self._last_asymmetry_result: AsymmetryResult | None = None

        # =====================================================================
        # DUAL-SIGNAL FUSION (Phase 96: FUSE-01, FUSE-03, FUSE-04)
        # =====================================================================
        # Weighted combination of ICMP filtered_rtt and IRTT rtt_mean_ms.
        # When IRTT is unavailable, stale, or disabled, fusion is a pure
        # pass-through (filtered_rtt goes to update_ewma unchanged).
        # =====================================================================
        self._fusion_icmp_weight: float = config.fusion_config["icmp_weight"]
        self._fusion_enabled: bool = config.fusion_config["enabled"]
        self._last_fused_rtt: float | None = None
        self._last_icmp_filtered_rtt: float | None = None

        # =====================================================================
        # REFLECTOR QUALITY SCORING (Phase 93: REFL-01 through REFL-03)
        # =====================================================================
        # Per-reflector rolling quality scoring with automatic deprioritization
        # and periodic recovery probing. Low-quality reflectors are excluded
        # from measure_rtt() to improve RTT signal quality.
        # =====================================================================
        rq_config = config.reflector_quality_config
        self._reflector_scorer = ReflectorScorer(
            hosts=config.ping_hosts,
            min_score=rq_config["min_score"],
            window_size=rq_config["window_size"],
            probe_interval_sec=rq_config["probe_interval_sec"],
            recovery_count=rq_config["recovery_count"],
            logger=logger,
            wan_name=wan_name,
        )

        # =====================================================================
        # SUSTAINED CONGESTION TIMERS (ALRT-01)
        # =====================================================================
        # Monotonic timestamps tracking when DL/UL entered RED/SOFT_RED.
        # Fires congestion_sustained_dl/ul after sustained_sec threshold.
        # Fires congestion_recovered_dl/ul when zone clears IF sustained fired.
        # =====================================================================
        self._dl_congestion_start: float | None = None
        self._ul_congestion_start: float | None = None
        self._dl_sustained_fired: bool = False
        self._ul_sustained_fired: bool = False
        self._dl_last_congested_zone: str = "RED"
        self._ul_last_congested_zone: str = "RED"
        self._sustained_sec: int = (
            ac.get("default_sustained_sec", 60) if ac else 60
        )

        # =====================================================================
        # CONNECTIVITY ALERT TIMERS (ALRT-04, ALRT-05)
        # =====================================================================
        # Monotonic timestamp tracking when all ICMP targets became unreachable.
        # Fires wan_offline after sustained_sec threshold (default 30s).
        # Fires wan_recovered when ICMP returns IF wan_offline had fired.
        # =====================================================================
        self._connectivity_offline_start: float | None = None
        self._wan_offline_fired: bool = False

        # =====================================================================
        # IRTT LOSS ALERT TIMERS (ALRT-01, ALRT-02, ALRT-03)
        # =====================================================================
        # Monotonic timestamps tracking when upstream/downstream IRTT loss
        # exceeded threshold. Fires irtt_loss_upstream/downstream after
        # sustained_sec. Fires irtt_loss_recovered when loss clears IF
        # sustained had fired.
        # =====================================================================
        self._irtt_loss_up_start: float | None = None
        self._irtt_loss_down_start: float | None = None
        self._irtt_loss_up_fired: bool = False
        self._irtt_loss_down_fired: bool = False
        self._irtt_loss_threshold_pct: float = 5.0

        # =====================================================================
        # CONGESTION FLAPPING DETECTION (ALRT-07)
        # =====================================================================
        # Sliding window of zone transition timestamps per direction.
        # Fires flapping_dl/flapping_ul when transitions exceed threshold
        # within the configured window. DL and UL tracked independently.
        # =====================================================================
        self._dl_zone_transitions: deque[float] = deque()
        self._ul_zone_transitions: deque[float] = deque()
        self._dl_prev_zone: str | None = None
        self._ul_prev_zone: str | None = None
        self._dl_zone_hold: int = 0  # cycles current DL zone has been held
        self._ul_zone_hold: int = 0  # cycles current UL zone has been held

        # =====================================================================
        # PROFILING INSTRUMENTATION
        # =====================================================================
        # Per-subsystem timing for cycle budget analysis (PROF-01, PROF-02).
        # PerfTimer always runs at DEBUG level (negligible overhead ~0.05ms).
        # OperationProfiler always accumulates (deque append, negligible).
        # Periodic report only emitted when --profile flag is set.
        # =====================================================================
        self._profiler = OperationProfiler(max_samples=1200)
        self._profile_cycle_count = 0
        self._profiling_enabled = False
        self._overrun_count = 0
        self._cycle_interval_ms = CYCLE_INTERVAL_SECONDS * 1000.0

        # =====================================================================
        # ADAPTIVE TUNING STATE
        # =====================================================================
        # Runtime-only parameter tuning driven by metrics analysis.
        # Enabled via tuning.enabled in YAML. Runs during maintenance window.
        # SIGUSR1 reloads enabled state via _reload_tuning_config().
        # =====================================================================
        if config.tuning_config is not None and config.tuning_config.enabled:
            self._tuning_enabled = True
            self._tuning_state: TuningState | None = TuningState(
                enabled=True,
                last_run_ts=None,
                recent_adjustments=[],
                parameters={},
            )
        else:
            self._tuning_enabled = False
            self._tuning_state = None
        self._last_tuning_ts: float | None = None
        # Layer rotation for bottom-up tuning (SIGP-04)
        self._tuning_layer_index: int = 0
        # Safety: revert detection and hysteresis lock state (Plan 100-02)
        self._parameter_locks: dict[str, float] = {}  # param -> monotonic lock expiry
        self._pending_observation = None  # PendingObservation | None (lazy import)

        # Load persisted state (hysteresis counters, current rates, EWMA)
        self.load_state()

        # Restore tuning parameters from SQLite (survives daemon restart)
        if self._tuning_enabled and self._metrics_writer is not None:
            self._restore_tuning_params()

    def _restore_tuning_params(self) -> None:
        """Restore latest tuning parameter values from SQLite.

        Reads the most recent non-reverted adjustment per parameter for this WAN
        from the tuning_params table. Applies values via _apply_tuning_to_controller
        (same path as live tuning). Only called when tuning is enabled and db exists.
        """
        from wanctl.storage.reader import query_tuning_params
        from wanctl.tuning.models import TuningResult

        try:
            if self._metrics_writer is None:
                return
            db_path = self._metrics_writer._db_path
            rows = query_tuning_params(db_path=db_path, wan=self.wan_name)
            if not rows:
                self.logger.info(f"{self.wan_name}: No prior tuning params to restore")
                return

            # Get latest non-reverted value per parameter
            latest: dict[str, dict] = {}
            for row in rows:  # Already ordered by timestamp DESC
                param = row["parameter"]
                if param not in latest and not row.get("reverted", 0):
                    latest[param] = row

            if not latest:
                self.logger.info(
                    f"{self.wan_name}: No non-reverted tuning params to restore"
                )
                return

            # Build TuningResult list for _apply_tuning_to_controller
            results = []
            for param, row in latest.items():
                results.append(
                    TuningResult(
                        parameter=param,
                        old_value=row["old_value"],
                        new_value=row["new_value"],
                        confidence=row["confidence"],
                        rationale=f"Restored from SQLite (ts={row['timestamp']})",
                        data_points=row["data_points"],
                        wan_name=self.wan_name,
                    )
                )

            _apply_tuning_to_controller(self, results)
            param_summary = ", ".join(
                f"{r.parameter}={r.new_value}" for r in results
            )
            self.logger.info(
                f"{self.wan_name}: Restored {len(results)} tuning params: {param_summary}"
            )
        except Exception as e:
            self.logger.warning(
                f"{self.wan_name}: Failed to restore tuning params "
                f"(using defaults): {e}"
            )

    def measure_rtt(self) -> float | None:
        """
        Measure RTT and return value in milliseconds.

        Uses ReflectorScorer to select active (non-deprioritized) hosts, then
        pings them concurrently with per-host attribution for quality tracking.

        Graceful degradation based on active host count:
        - 3+ active: median-of-N (handles reflector variation)
        - 2 active: average-of-2
        - 1 active: single ping value
        - 0 active: impossible (get_active_hosts forces best-scoring)

        Per-host results are recorded back to ReflectorScorer for rolling
        quality scoring, and any deprioritization/recovery events are persisted.
        """
        active_hosts = self._reflector_scorer.get_active_hosts()

        # Ping active hosts with per-host attribution
        results = self.rtt_measurement.ping_hosts_with_results(
            hosts=active_hosts, count=1, timeout=3.0
        )

        # Record per-host results for quality scoring
        for host, rtt_val in results.items():
            self._reflector_scorer.record_result(host, rtt_val is not None)

        # Persist any deprioritization/recovery events
        self._persist_reflector_events()

        # Extract successful RTT values
        rtts = [v for v in results.values() if v is not None]

        if not rtts:
            self.logger.warning(f"{self.wan_name}: All pings failed")
            return None

        # Graceful degradation based on available results
        if len(rtts) >= 3:
            rtt = statistics.median(rtts)
            self.logger.debug(
                f"{self.wan_name}: Median-of-{len(rtts)} RTT = {rtt:.2f}ms"
            )
        elif len(rtts) == 2:
            rtt = statistics.mean(rtts)
            self.logger.debug(
                f"{self.wan_name}: Average-of-2 RTT = {rtt:.2f}ms"
            )
        else:
            rtt = rtts[0]

        return rtt

    def _persist_reflector_events(self) -> None:
        """Persist any pending reflector deprioritization/recovery events to SQLite.

        Drains transition events from ReflectorScorer and writes them to the
        reflector_events table. Never raises -- follows AlertEngine pattern.
        """
        if self._metrics_writer is None:
            return

        events = self._reflector_scorer.drain_events()
        for event in events:
            try:
                import json
                import time as time_mod

                timestamp = int(time_mod.time())
                details = json.dumps({
                    "host": event["host"],
                    "score": round(event["score"], 3),
                    "event": event["event_type"],
                })
                self._metrics_writer.connection.execute(
                    "INSERT INTO reflector_events "
                    "(timestamp, event_type, host, wan_name, score, details) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp, event["event_type"], event["host"],
                     self.wan_name, round(event["score"], 3), details),
                )
            except Exception:
                self.logger.warning(
                    "Failed to persist reflector event %s for %s",
                    event["event_type"], event["host"], exc_info=True,
                )

    def update_ewma(self, measured_rtt: float) -> None:
        """
        Update both EWMAs (fast load, slow baseline).

        Fast EWMA (load_rtt): Responsive to current conditions, always updates.
        Slow EWMA (baseline_rtt): Only updates when line is idle (delta < threshold).
        """
        # Fast EWMA for load_rtt (responsive to current conditions)
        self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt

        # Slow EWMA for baseline_rtt (conditional update via protected logic)
        self._update_baseline_if_idle(measured_rtt)

    def _update_baseline_if_idle(self, icmp_rtt: float) -> None:
        """
        Update baseline RTT ONLY when line is idle (delta < threshold).

        PROTECTED ZONE - ARCHITECTURAL INVARIANT
        =========================================
        This logic prevents baseline drift under load. If baseline tracked load RTT,
        delta would approach zero and bloat detection would fail. The threshold
        (baseline_update_threshold) determines "idle" vs "under load".

        Uses ICMP-only signal (not fused RTT) for both the freeze gate and the
        baseline EWMA. This prevents IRTT path divergence from corrupting baseline
        semantics. Baseline is an ICMP-derived concept representing idle propagation
        delay; fusing a different-path IRTT signal corrupts its meaning.

        DO NOT MODIFY without explicit approval. See docs/CORE-ALGORITHM-ANALYSIS.md.

        Args:
            icmp_rtt: ICMP-only filtered RTT in milliseconds (Hampel-filtered,
                pre-fusion). Must NOT be the fused ICMP+IRTT signal.

        Side Effects:
            Updates self.baseline_rtt if delta < threshold (line is idle).
            Logs debug message when baseline updates (helps debug drift issues).
        """
        delta = icmp_rtt - self.baseline_rtt

        # PROTECTED: Baseline ONLY updates when line is idle
        if delta < self.baseline_update_threshold:
            # Line is idle or nearly idle - safe to update baseline
            old_baseline = self.baseline_rtt
            new_baseline = (
                1 - self.alpha_baseline
            ) * self.baseline_rtt + self.alpha_baseline * icmp_rtt

            # Security bounds check - reject corrupted/invalid baseline values
            if not (self.baseline_rtt_min <= new_baseline <= self.baseline_rtt_max):
                self.logger.warning(
                    f"{self.wan_name}: Baseline RTT {new_baseline:.1f}ms outside bounds "
                    f"[{self.baseline_rtt_min}-{self.baseline_rtt_max}ms], ignoring"
                )
                return

            self.baseline_rtt = new_baseline
            self.logger.debug(
                f"{self.wan_name}: Baseline updated {old_baseline:.2f}ms -> "
                f"{self.baseline_rtt:.2f}ms "
                f"(delta={delta:.1f}ms < threshold={self.baseline_update_threshold}ms)"
            )
        # else: Under load - freeze baseline (no update, no logging to avoid spam)

    def verify_local_connectivity(self) -> bool:
        """
        Check if we can reach local gateway via ICMP.

        Returns:
            True if gateway is reachable (WAN issue, not container networking)
            False if gateway unreachable (container networking problem)
        """
        if not self.config.fallback_check_gateway:
            return False

        gateway_ip = self.config.fallback_gateway_ip
        if not gateway_ip:
            return False
        result = self.rtt_measurement.ping_host(gateway_ip, count=1)
        if result is not None:
            self.logger.warning(
                f"{self.wan_name}: External pings failed but gateway {gateway_ip} reachable - "
                f"likely WAN issue, not container networking"
            )
            return True
        return False

    def verify_tcp_connectivity(self) -> tuple[bool, float | None]:
        """
        Check if we can establish TCP connections (HTTPS) and measure RTT.

        Tests multiple targets using TCP handshake to verify Internet connectivity
        when ICMP is blocked/filtered. Times successful connections to provide
        TCP-based RTT as fallback for ICMP.

        Returns:
            (connected, rtt_ms):
            - connected: True if ANY TCP connection succeeds
            - rtt_ms: Median RTT in milliseconds from successful connections, or None
        """
        if not self.config.fallback_check_tcp:
            return (False, None)

        rtts: list[float] = []
        for host, port in self.config.fallback_tcp_targets:
            try:
                start = time.monotonic()
                sock = socket.create_connection((host, port), timeout=0.5)
                sock.close()
                rtt_ms = (time.monotonic() - start) * 1000
                rtts.append(rtt_ms)
                self.logger.debug(f"TCP to {host}:{port} succeeded, RTT={rtt_ms:.1f}ms")
            except (TimeoutError, OSError, socket.gaierror) as e:
                self.logger.debug(f"TCP to {host}:{port} failed: {e}")
                continue

        if rtts:
            median_rtt = statistics.median(rtts) if len(rtts) > 1 else rtts[0]
            self.logger.info(
                f"{self.wan_name}: TCP connectivity verified, RTT={median_rtt:.1f}ms "
                f"(from {len(rtts)} targets)"
            )
            return (True, median_rtt)

        return (False, None)  # All TCP attempts failed

    def verify_connectivity_fallback(self) -> tuple[bool, float | None]:
        """
        Multi-protocol connectivity verification with TCP RTT measurement.

        When all ICMP pings fail, verify if we have ANY connectivity
        using alternative protocols before declaring total failure.
        Also measures TCP RTT to provide fallback latency data.

        Returns:
            (has_connectivity, tcp_rtt_ms):
            - has_connectivity: True if ANY connectivity detected
            - tcp_rtt_ms: TCP RTT in milliseconds if measured, None otherwise
        """
        if not self.config.fallback_enabled:
            return (False, None)

        self.logger.warning(f"{self.wan_name}: All ICMP pings failed - running fallback checks")

        # Check 1: Local gateway (fastest, ~50ms)
        # Note: Gateway RTT is not useful for WAN latency measurement
        gateway_ok = self.verify_local_connectivity()

        # Check 2: TCP HTTPS (most reliable, measures WAN RTT)
        tcp_ok, tcp_rtt = self.verify_tcp_connectivity()

        if tcp_ok:
            # TCP succeeded - we have connectivity AND RTT measurement
            if gateway_ok:
                self.logger.warning(
                    f"{self.wan_name}: External pings failed but gateway and TCP reachable - "
                    f"ICMP filtering detected"
                )
            return (True, tcp_rtt)

        if gateway_ok:
            # Gateway OK but TCP failed - partial connectivity
            self.logger.warning(
                f"{self.wan_name}: External pings failed but gateway reachable - "
                f"likely WAN issue, not container networking"
            )
            return (True, None)

        # Both fail - total connectivity loss
        self.logger.error(
            f"{self.wan_name}: Both ICMP and TCP connectivity failed - "
            f"confirmed total connectivity loss"
        )
        return (False, None)

    def apply_rate_changes_if_needed(self, dl_rate: int, ul_rate: int) -> bool:
        """
        Apply rate changes to router with flash wear protection and rate limiting.

        Only sends updates to router when rates have actually changed (flash wear
        protection) and within the rate limit window (API overload protection).

        PROTECTED LOGIC - RouterOS writes queue changes to NAND flash. Repeated
        writes accelerate flash wear. See docs/CORE-ALGORITHM-ANALYSIS.md.

        Args:
            dl_rate: Download rate in bits per second
            ul_rate: Upload rate in bits per second

        Returns:
            True if cycle should continue (rates applied or skipped),
            False if router update failed (triggers watchdog restart)

        Side Effects:
            - Updates last_applied_dl_rate/last_applied_ul_rate on success
            - Records rate_limiter change on successful router update
            - Records metrics (router_update, rate_limit_event)
            - Calls save_state() when rate limited
        """
        # =====================================================================
        # FAIL-CLOSED: Queue rates when router unreachable (ERRR-03)
        # Rates are preserved for later application instead of being discarded.
        # =====================================================================
        if not self.router_connectivity.is_reachable:
            self.pending_rates.queue(dl_rate, ul_rate)
            self.logger.debug(
                f"{self.wan_name}: Router unreachable, queuing rate change "
                f"(DL={dl_rate / 1e6:.1f}Mbps, UL={ul_rate / 1e6:.1f}Mbps)"
            )
            return True  # Cycle succeeds - rates queued for later

        # =====================================================================
        # PROTECTED: Flash wear protection - only send queue limits when values change.
        # Router NAND has 100K-1M write cycles. See docs/CORE-ALGORITHM-ANALYSIS.md.
        # =====================================================================
        if dl_rate == self.last_applied_dl_rate and ul_rate == self.last_applied_ul_rate:
            self.logger.debug(
                f"{self.wan_name}: Rates unchanged, skipping router update (flash wear protection)"
            )
            return True  # Success - no update needed

        # =====================================================================
        # PROTECTED: Rate limiting prevents RouterOS API overload (RB5009 limit ~50 req/sec).
        # See docs/CORE-ALGORITHM-ANALYSIS.md.
        # =====================================================================
        if not self.rate_limiter.can_change():
            # Log once when entering throttled state (not every cycle)
            if not self._rate_limit_logged:
                wait_time = self.rate_limiter.time_until_available()
                self.logger.debug(
                    f"{self.wan_name}: Rate limit active (>{DEFAULT_RATE_LIMIT_MAX_CHANGES} "
                    f"changes/{DEFAULT_RATE_LIMIT_WINDOW_SECONDS}s), throttling updates "
                    f"(next slot in {wait_time:.1f}s)"
                )
                self._rate_limit_logged = True
            if self.config.metrics_enabled:
                record_rate_limit_event(self.wan_name)
            # Still return True - cycle completed, just throttled the update
            # Save state to preserve EWMA and streak counters
            self.save_state()
            return True

        # Apply to router
        success = self.router.set_limits(wan=self.wan_name, down_bps=dl_rate, up_bps=ul_rate)

        if not success:
            self.logger.error(f"{self.wan_name}: Failed to apply limits")
            return False

        # Record successful change for rate limiting
        self.rate_limiter.record_change()
        self._rate_limit_logged = False  # Reset so we log next throttle window

        # Record metrics for router update
        if self.config.metrics_enabled:
            record_router_update(self.wan_name)

        # Update tracking after successful write
        self.last_applied_dl_rate = dl_rate
        self.last_applied_ul_rate = ul_rate
        self.pending_rates.clear()
        self.logger.debug(f"{self.wan_name}: Applied new limits to router")
        return True

    def handle_icmp_failure(self) -> tuple[bool, float | None]:
        """
        Handle ICMP ping failure with TCP RTT fallback.

        Called when measure_rtt() returns None. Runs fallback connectivity checks
        (gateway ping, TCP handshake with RTT measurement). If TCP RTT is available,
        uses it directly. Otherwise applies mode-specific degradation behavior.

        Returns:
            (should_continue, measured_rtt):
            - should_continue: True if cycle should proceed, False to trigger restart
            - measured_rtt: RTT value (TCP or last known), or None to freeze rates

        Note:
            TCP RTT is preferred over stale ICMP data when available.
        """
        if self.config.metrics_enabled:
            record_ping_failure(self.wan_name)

        # Run fallback connectivity checks (now includes TCP RTT measurement)
        has_connectivity, tcp_rtt = self.verify_connectivity_fallback()

        if has_connectivity:
            self.icmp_unavailable_cycles += 1

            # If we have TCP RTT, use it directly - no degradation needed
            if tcp_rtt is not None:
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - using TCP RTT={tcp_rtt:.1f}ms as fallback"
                )
                return (True, tcp_rtt)

            # No TCP RTT available (gateway-only connectivity) - use degradation modes
            if self.config.fallback_mode == "graceful_degradation":
                if self.icmp_unavailable_cycles == 1:
                    measured_rtt = self.load_rtt
                    self.logger.warning(
                        f"{self.wan_name}: ICMP unavailable, no TCP RTT (cycle 1/"
                        f"{self.config.fallback_max_cycles}) - using last RTT={measured_rtt:.1f}ms"
                    )
                    return (True, measured_rtt)
                elif self.icmp_unavailable_cycles <= self.config.fallback_max_cycles:
                    self.logger.warning(
                        f"{self.wan_name}: ICMP unavailable, no TCP RTT "
                        f"(cycle {self.icmp_unavailable_cycles}/"
                        f"{self.config.fallback_max_cycles}) - freezing rates"
                    )
                    return (True, None)
                else:
                    self.logger.error(
                        f"{self.wan_name}: ICMP unavailable for "
                        f"{self.icmp_unavailable_cycles} cycles "
                        f"(>{self.config.fallback_max_cycles}) - giving up"
                    )
                    return (False, None)

            elif self.config.fallback_mode == "freeze":
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - freezing rates (mode: freeze)"
                )
                return (True, None)

            elif self.config.fallback_mode == "use_last_rtt":
                measured_rtt = self.load_rtt
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - using last RTT={measured_rtt:.1f}ms "
                    f"(mode: use_last_rtt)"
                )
                return (True, measured_rtt)

            else:
                self.logger.error(
                    f"{self.wan_name}: Unknown fallback_mode: {self.config.fallback_mode}"
                )
                return (False, None)

        else:
            # Total connectivity loss confirmed (both ICMP and TCP failed)
            self.logger.warning(f"{self.wan_name}: Total connectivity loss - skipping cycle")
            return (False, None)

    def _check_protocol_correlation(self, ratio: float) -> None:
        """Check ICMP/UDP RTT ratio for protocol deprioritization (IRTT-07).

        Thresholds:
        - ratio > 1.5: ICMP deprioritized (ISP throttling ICMP)
        - ratio < 0.67: UDP deprioritized (ISP throttling UDP)
        - 0.67-1.5: Normal correlation
        """
        deprioritized = ratio > 1.5 or ratio < 0.67

        if deprioritized:
            if ratio > 1.5:
                interpretation = "ICMP deprioritized"
            else:
                interpretation = "UDP deprioritized"

            if not self._irtt_deprioritization_logged:
                irtt_result = self._irtt_thread.get_latest() if self._irtt_thread else None
                udp_rtt = irtt_result.rtt_mean_ms if irtt_result else 0.0
                self.logger.info(
                    f"{self.wan_name}: Protocol deprioritization detected: "
                    f"ICMP/UDP ratio={ratio:.2f} ({interpretation}), "
                    f"ICMP={self.load_rtt:.1f}ms, UDP={udp_rtt:.1f}ms"
                )
                self._irtt_deprioritization_logged = True
            else:
                self.logger.debug(
                    f"{self.wan_name}: Protocol ratio={ratio:.2f}"
                )
        else:
            if self._irtt_deprioritization_logged:
                self.logger.info(
                    f"{self.wan_name}: Protocol correlation recovered, "
                    f"ratio={ratio:.2f}"
                )
                self._irtt_deprioritization_logged = False

        self._irtt_correlation = ratio

    def _compute_fused_rtt(self, filtered_rtt: float) -> float:
        """Compute fused RTT from ICMP filtered_rtt and cached IRTT rtt_mean_ms.

        Returns filtered_rtt unchanged (pass-through) when:
        - IRTT thread is not running (_irtt_thread is None)
        - No IRTT result available (get_latest() returns None)
        - IRTT result is stale (age > 3x cadence)
        - IRTT rtt_mean_ms is zero or negative (total packet loss)

        Returns weighted average when IRTT is fresh and valid.

        Always stores _last_icmp_filtered_rtt and _last_fused_rtt for
        health endpoint observability (FUSE-05).
        """
        self._last_icmp_filtered_rtt = filtered_rtt
        self._last_fused_rtt = None

        if not self._fusion_enabled:
            return filtered_rtt

        if self._irtt_thread is None:
            return filtered_rtt

        irtt_result = self._irtt_thread.get_latest()
        if irtt_result is None:
            return filtered_rtt

        age = time.monotonic() - irtt_result.timestamp
        cadence = self._irtt_thread._cadence_sec
        if age > cadence * 3:
            return filtered_rtt

        irtt_rtt = irtt_result.rtt_mean_ms
        if irtt_rtt <= 0:
            return filtered_rtt

        fused = self._fusion_icmp_weight * filtered_rtt + (1.0 - self._fusion_icmp_weight) * irtt_rtt
        self._last_fused_rtt = fused
        self.logger.debug(
            f"{self.wan_name}: fused_rtt={fused:.1f}ms "
            f"(icmp={filtered_rtt:.1f}ms, irtt={irtt_rtt:.1f}ms, "
            f"icmp_w={self._fusion_icmp_weight})"
        )
        return fused

    def _reload_fusion_config(self) -> None:
        """Re-read fusion config from YAML (triggered by SIGUSR1).

        Reloads both enabled and icmp_weight. Validates with same rules as
        _load_fusion_config(). Logs old->new transitions at WARNING level.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[FUSION] Config reload failed: {e}")
            return

        fusion = fresh_data.get("fusion", {}) if fresh_data else {}
        if not isinstance(fusion, dict):
            fusion = {}

        # Parse enabled (default False)
        new_enabled = fusion.get("enabled", False)
        if not isinstance(new_enabled, bool):
            self.logger.warning(
                f"[FUSION] Reload: fusion.enabled must be bool, got "
                f"{type(new_enabled).__name__}; defaulting to false"
            )
            new_enabled = False
        old_enabled = self._fusion_enabled

        # Parse icmp_weight with same validation as _load_fusion_config
        new_weight = fusion.get("icmp_weight", 0.7)
        if (
            not isinstance(new_weight, (int, float))
            or isinstance(new_weight, bool)
            or new_weight < 0.0
            or new_weight > 1.0
        ):
            self.logger.warning(
                f"[FUSION] Reload: fusion.icmp_weight invalid ({new_weight!r}); "
                "defaulting to 0.7"
            )
            new_weight = 0.7
        new_weight = float(new_weight)
        old_weight = self._fusion_icmp_weight

        # Log transitions
        enabled_str = (
            f"enabled={old_enabled}->{new_enabled}"
            if old_enabled != new_enabled
            else f"enabled={new_enabled}"
        )
        weight_str = (
            f"icmp_weight={old_weight}->{new_weight}"
            if old_weight != new_weight
            else f"icmp_weight={new_weight} (unchanged)"
        )
        self.logger.warning(f"[FUSION] Config reload: {enabled_str}, {weight_str}")

        self._fusion_enabled = new_enabled
        self._fusion_icmp_weight = new_weight

    def _reload_tuning_config(self) -> None:
        """Re-read tuning config from YAML (triggered by SIGUSR1).

        Reloads enabled state. Validates with same rules as
        _load_tuning_config(). Logs old->new transitions at WARNING level.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[TUNING] Config reload failed: {e}")
            return

        tuning = fresh_data.get("tuning", {}) if fresh_data else {}
        if not isinstance(tuning, dict):
            tuning = {}

        new_enabled = tuning.get("enabled", False)
        if not isinstance(new_enabled, bool):
            self.logger.warning(
                f"[TUNING] Reload: tuning.enabled must be bool, got "
                f"{type(new_enabled).__name__}; defaulting to false"
            )
            new_enabled = False

        old_enabled = self._tuning_enabled

        # Log transition
        if old_enabled != new_enabled:
            self.logger.warning(
                "[TUNING] Config reload: enabled=%s->%s",
                old_enabled,
                new_enabled,
            )
        else:
            self.logger.info(
                "[TUNING] Config reload: enabled=%s (unchanged)",
                new_enabled,
            )

        self._tuning_enabled = new_enabled

        if new_enabled and self._tuning_state is None:
            self._tuning_state = TuningState(
                enabled=True,
                last_run_ts=None,
                recent_adjustments=[],
                parameters={},
            )
        elif not new_enabled:
            self._tuning_state = None
            self._parameter_locks = {}
            self._pending_observation = None

    def _record_profiling(
        self,
        rtt_ms: float,
        state_ms: float,
        router_ms: float,
        cycle_start: float,
    ) -> None:
        """Record subsystem timing to profiler, emit structured log, and detect overruns.

        Thin wrapper around shared record_cycle_profiling() -- preserves method
        signature for test compatibility.
        """
        self._overrun_count, self._profile_cycle_count = record_cycle_profiling(
            profiler=self._profiler,
            timings={
                "autorate_rtt_measurement": rtt_ms,
                "autorate_state_management": state_ms,
                "autorate_router_communication": router_ms,
            },
            cycle_start=cycle_start,
            cycle_interval_ms=self._cycle_interval_ms,
            logger=self.logger,
            daemon_name=f"{self.wan_name}: Cycle",
            label_prefix="autorate",
            overrun_count=self._overrun_count,
            profiling_enabled=self._profiling_enabled,
            profile_cycle_count=self._profile_cycle_count,
        )

    def run_cycle(self) -> bool:
        """Main 5-second cycle for this WAN"""
        cycle_start = time.perf_counter()

        # === RTT Measurement (subsystem 1) ===
        rtt_early_return: bool | None = None  # None=continue, True/False=return value
        with PerfTimer("autorate_rtt_measurement", self.logger) as rtt_timer:
            measured_rtt = self.measure_rtt()
            raw_measured_rtt = measured_rtt  # Capture before fallback (ALRT-04/05)

            # Handle ICMP failure with fallback connectivity checks
            if measured_rtt is None:
                should_continue, measured_rtt = self.handle_icmp_failure()
                if not should_continue:
                    rtt_early_return = False
                elif measured_rtt is None:
                    # Freeze mode - save state and return success
                    self.save_state()
                    rtt_early_return = True
            else:
                # ICMP succeeded - reset fallback counter if it was set
                if self.icmp_unavailable_cycles > 0:
                    self.logger.info(
                        f"{self.wan_name}: ICMP recovered after "
                        f"{self.icmp_unavailable_cycles} cycles"
                    )
                    self.icmp_unavailable_cycles = 0

            # WAN connectivity alerts (ALRT-04, ALRT-05) -- uses raw RTT
            # before fallback so we track actual ICMP reachability
            self._check_connectivity_alerts(raw_measured_rtt)

        if rtt_early_return is not None:
            self._record_profiling(rtt_timer.elapsed_ms, 0.0, 0.0, cycle_start)
            return rtt_early_return

        # === State Management (subsystem 2) ===
        assert measured_rtt is not None  # guaranteed by rtt_early_return check above
        with PerfTimer("autorate_state_management", self.logger) as state_timer:
            # At this point, measured_rtt is valid (either from ICMP or last known value)

            # Signal processing: filter RTT, compute jitter/variance/confidence
            signal_result = self.signal_processor.process(
                raw_rtt=measured_rtt,
                load_rtt=self.load_rtt,
                baseline_rtt=self.baseline_rtt,
            )
            self._last_signal_result = signal_result
            fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
            # Split EWMA: fused for load (congestion sensitivity), ICMP for baseline (idle reference)
            # Fixes fusion baseline deadlock where IRTT path divergence freezes/corrupts baseline.
            # See Phase 103 research: baseline is an ICMP-derived concept.
            self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt
            self._update_baseline_if_idle(signal_result.filtered_rtt)

            # Rate-of-change (acceleration) detection for sudden RTT spikes
            # Catches spikes that EWMA smooths over, triggers immediate RED
            delta_accel = self.load_rtt - self.previous_load_rtt
            if delta_accel > self.accel_threshold:
                self.logger.warning(
                    f"{self.wan_name}: RTT spike detected! delta_accel={delta_accel:.1f}ms "
                    f"(threshold={self.accel_threshold}ms) - forcing RED"
                )
                # Force RED by setting streak counter (bypasses hysteresis)
                self.download.red_streak = 1
                self.download.green_streak = 0
                self.download.soft_red_streak = 0
            self.previous_load_rtt = self.load_rtt

            # Download: 4-state logic (GREEN/YELLOW/SOFT_RED/RED) - Phase 2A
            dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(
                self.baseline_rtt,
                self.load_rtt,
                self.green_threshold,
                self.soft_red_threshold,
                self.hard_red_threshold,
            )
            self._dl_zone = dl_zone

            # Upload: 3-state logic (GREEN/YELLOW/RED) - unchanged for Phase 2A
            ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(
                self.baseline_rtt, self.load_rtt, self.target_delta, self.warn_delta
            )
            self._ul_zone = ul_zone

            # Sustained congestion detection (ALRT-01)
            delta = self.load_rtt - self.baseline_rtt
            self._check_congestion_alerts(dl_zone, ul_zone, dl_rate, ul_rate, delta)

            # Baseline RTT drift detection (ALRT-06)
            self._check_baseline_drift()

            # Congestion zone flapping detection (ALRT-07)
            self._check_flapping_alerts(dl_zone, ul_zone)

            # IRTT observation mode: read cached result + protocol correlation (IRTT-03, IRTT-07)
            irtt_result = self._irtt_thread.get_latest() if self._irtt_thread else None
            if irtt_result is not None:
                age = time.monotonic() - irtt_result.timestamp
                cadence = self._irtt_thread._cadence_sec if self._irtt_thread else 10.0
                self.logger.debug(
                    f"{self.wan_name}: IRTT RTT={irtt_result.rtt_mean_ms:.1f}ms, "
                    f"IPDV={irtt_result.ipdv_mean_ms:.1f}ms, "
                    f"loss_up={irtt_result.send_loss:.1f}%, "
                    f"loss_down={irtt_result.receive_loss:.1f}%, "
                    f"age={age:.1f}s"
                )
                # Protocol correlation (IRTT-07) -- skip stale results (>3x cadence)
                if age <= cadence * 3 and irtt_result.rtt_mean_ms > 0 and self.load_rtt > 0:
                    ratio = self.load_rtt / irtt_result.rtt_mean_ms
                    self._check_protocol_correlation(ratio)
                elif age > cadence * 3:
                    self._irtt_correlation = None
                    self.logger.debug(
                        f"{self.wan_name}: IRTT result stale ({age:.0f}s > {cadence * 3:.0f}s), "
                        f"skipping correlation"
                    )

                # OWD asymmetry analysis (ASYM-01) -- only on fresh IRTT result
                if self._asymmetry_analyzer is not None:
                    asym = self._asymmetry_analyzer.analyze(irtt_result)
                    self._last_asymmetry_result = asym

                # IRTT loss alerts (ALRT-01, ALRT-02, ALRT-03)
                if isinstance(self.alert_engine, AlertEngine):
                    if age <= cadence * 3:
                        self._check_irtt_loss_alerts(irtt_result)
                    else:
                        self._irtt_loss_up_start = None
                        self._irtt_loss_up_fired = False
                        self._irtt_loss_down_start = None
                        self._irtt_loss_down_fired = False

            # Reflector quality probing (REFL-03) -- probe deprioritized hosts
            # Probes run at their own cadence (default 30s), one host per cycle
            now = time.monotonic()
            probed = self._reflector_scorer.maybe_probe(now, self.rtt_measurement)
            if probed:
                self._persist_reflector_events()
                for probe_host, probe_success in probed:
                    self.logger.debug(
                        f"{self.wan_name}: Reflector probe {probe_host}: "
                        f"{'success' if probe_success else 'failed'}"
                    )

            # Log decision
            self.logger.info(
                f"{self.wan_name}: [{dl_zone}/{ul_zone}] "
                f"RTT={measured_rtt:.1f}ms, load_ewma={self.load_rtt:.1f}ms, "
                f"baseline={self.baseline_rtt:.1f}ms, delta={delta:.1f}ms | "
                f"DL={dl_rate / 1e6:.0f}M, UL={ul_rate / 1e6:.0f}M"
            )

            # Record metrics to SQLite history (if enabled)
            if self._metrics_writer is not None:
                ts = int(time.time())
                metrics_batch = [
                    (ts, self.wan_name, "wanctl_rtt_ms", measured_rtt, None, "raw"),
                    (ts, self.wan_name, "wanctl_rtt_baseline_ms", self.baseline_rtt, None, "raw"),
                    (ts, self.wan_name, "wanctl_rtt_load_ewma_ms", self.load_rtt, None, "raw"),
                    (ts, self.wan_name, "wanctl_rtt_fused_ms", fused_rtt, None, "raw"),
                    (ts, self.wan_name, "wanctl_rtt_delta_ms", delta, None, "raw"),
                    (ts, self.wan_name, "wanctl_rate_download_mbps", dl_rate / 1e6, None, "raw"),
                    (ts, self.wan_name, "wanctl_rate_upload_mbps", ul_rate / 1e6, None, "raw"),
                    (
                        ts,
                        self.wan_name,
                        "wanctl_state",
                        float(self._encode_state(dl_zone)),
                        {"direction": "download"},
                        "raw",
                    ),
                ]

                # Signal quality metrics -- every cycle (OBSV-03)
                if self._last_signal_result is not None:
                    sr = self._last_signal_result
                    metrics_batch.extend([
                        (ts, self.wan_name, "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
                        (ts, self.wan_name, "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
                        (ts, self.wan_name, "wanctl_signal_confidence", sr.confidence, None, "raw"),
                        (ts, self.wan_name, "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
                    ])

                # IRTT metrics -- only on new measurement (OBSV-04)
                if irtt_result is not None and irtt_result.timestamp != self._last_irtt_write_ts:
                    metrics_batch.extend([
                        (ts, self.wan_name, "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                        (ts, self.wan_name, "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                        (ts, self.wan_name, "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                        (ts, self.wan_name, "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
                    ])
                    # OWD asymmetry metrics (ASYM-03) -- same dedup guard as IRTT metrics
                    if self._last_asymmetry_result is not None:
                        metrics_batch.extend([
                            (ts, self.wan_name, "wanctl_irtt_asymmetry_ratio",
                             self._last_asymmetry_result.ratio, None, "raw"),
                            (ts, self.wan_name, "wanctl_irtt_asymmetry_direction",
                             DIRECTION_ENCODING.get(self._last_asymmetry_result.direction, 0.0),
                             None, "raw"),
                        ])
                    self._last_irtt_write_ts = irtt_result.timestamp

                self._metrics_writer.write_metrics_batch(metrics_batch)

                # Record state transition if occurred (with reason in labels)
                if dl_transition_reason:
                    self._metrics_writer.write_metric(
                        timestamp=ts,
                        wan_name=self.wan_name,
                        metric_name="wanctl_state",
                        value=float(self._encode_state(dl_zone)),
                        labels={"direction": "download", "reason": dl_transition_reason},
                        granularity="raw",
                    )
                if ul_transition_reason:
                    self._metrics_writer.write_metric(
                        timestamp=ts,
                        wan_name=self.wan_name,
                        metric_name="wanctl_state",
                        value=float(self._encode_state(ul_zone)),
                        labels={"direction": "upload", "reason": ul_transition_reason},
                        granularity="raw",
                    )

        # === Router Communication (subsystem 3) ===
        router_failed = False
        with PerfTimer("autorate_router_communication", self.logger) as router_timer:
            # Apply rate changes (with flash wear + rate limit protection)
            # Track router connectivity state for cycle-level failure detection
            try:
                if not self.apply_rate_changes_if_needed(dl_rate, ul_rate):
                    # Router communication failed - record failure
                    self.router_connectivity.record_failure(
                        ConnectionError("Failed to apply rate limits to router")
                    )
                    router_failed = True
                else:
                    # Router communication succeeded - record success
                    self.router_connectivity.record_success()

                    # Apply pending rates on reconnection (ERRR-04)
                    if self.pending_rates.has_pending():
                        if self.pending_rates.is_stale():
                            self.logger.info(
                                f"{self.wan_name}: Discarding stale pending rates "
                                f"(queued >{60}s ago)"
                            )
                            self.pending_rates.clear()
                        else:
                            pending_dl = self.pending_rates.pending_dl_rate
                            pending_ul = self.pending_rates.pending_ul_rate
                            if pending_dl is not None and pending_ul is not None:
                                self.logger.info(
                                    f"{self.wan_name}: Applying pending rates after "
                                    f"reconnection "
                                    f"(DL={pending_dl / 1e6:.1f}Mbps, "
                                    f"UL={pending_ul / 1e6:.1f}Mbps)"
                                )
                                self.apply_rate_changes_if_needed(pending_dl, pending_ul)
            except Exception as e:
                # Unexpected exception during router communication
                failure_type = self.router_connectivity.record_failure(e)
                # Log on first failure, every 3rd failure, or on threshold exceeded
                failures = self.router_connectivity.consecutive_failures
                if failures == 1 or failures == 3 or failures % 10 == 0:
                    self.logger.warning(
                        f"{self.wan_name}: Router communication failed ({failure_type}, "
                        f"{failures} consecutive)"
                    )
                router_failed = True

        self._record_profiling(
            rtt_timer.elapsed_ms, state_timer.elapsed_ms, router_timer.elapsed_ms, cycle_start
        )
        if router_failed:
            return False

        # Save state with periodic force save (safety net against crashes)
        # Only after successful router communication
        self._cycles_since_forced_save += 1
        if self._cycles_since_forced_save >= FORCE_SAVE_INTERVAL_CYCLES:
            self.save_state(force=True)
            self._cycles_since_forced_save = 0
        else:
            self.save_state()

        # Record metrics if enabled
        if self.config.metrics_enabled:
            cycle_duration = time.perf_counter() - cycle_start
            record_autorate_cycle(
                wan_name=self.wan_name,
                dl_rate_mbps=dl_rate / 1e6,
                ul_rate_mbps=ul_rate / 1e6,
                baseline_rtt=self.baseline_rtt,
                load_rtt=self.load_rtt,
                dl_state=dl_zone,
                ul_state=ul_zone,
                cycle_duration=cycle_duration,
            )

        return True

    def _check_congestion_alerts(
        self,
        dl_zone: str,
        ul_zone: str,
        dl_rate: int,
        ul_rate: int,
        delta: float,
    ) -> None:
        """Check sustained congestion timers and fire alerts (ALRT-01).

        Called each run_cycle() after zone assignment. Tracks how long each
        direction has been in a congested zone (RED/SOFT_RED for DL, RED for UL).
        Fires congestion_sustained_dl/ul after sustained_sec threshold. Fires
        congestion_recovered_dl/ul when zone clears IF sustained alert had fired.

        Args:
            dl_zone: Current download zone (GREEN/YELLOW/SOFT_RED/RED).
            ul_zone: Current upload zone (GREEN/YELLOW/RED).
            dl_rate: Current download rate in bps.
            ul_rate: Current upload rate in bps.
            delta: Current RTT delta (load_rtt - baseline_rtt).
        """
        now = time.monotonic()

        # --- Download congestion ---
        dl_congested = dl_zone in ("RED", "SOFT_RED")
        if dl_congested:
            self._dl_last_congested_zone = dl_zone
            if self._dl_congestion_start is None:
                self._dl_congestion_start = now
            elif not self._dl_sustained_fired:
                # Check per-rule sustained_sec override
                sustained_sec = self.alert_engine._rules.get(
                    "congestion_sustained_dl", {}
                ).get("sustained_sec", self._sustained_sec)
                duration = now - self._dl_congestion_start
                if duration >= sustained_sec:
                    severity = "critical" if dl_zone == "RED" else "warning"
                    fired = self.alert_engine.fire(
                        "congestion_sustained_dl",
                        severity,
                        self.wan_name,
                        {
                            "zone": dl_zone,
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                            "rtt_ms": self.load_rtt,
                            "delta_ms": delta,
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._dl_sustained_fired = True
        else:
            # Zone cleared (GREEN or YELLOW)
            if self._dl_congestion_start is not None:
                if self._dl_sustained_fired:
                    duration = now - self._dl_congestion_start
                    self.alert_engine.fire(
                        "congestion_recovered_dl",
                        "recovery",
                        self.wan_name,
                        {
                            "recovered_from_zone": self._dl_last_congested_zone,
                            "duration_sec": round(duration, 1),
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                        },
                    )
                self._dl_congestion_start = None
                self._dl_sustained_fired = False

        # --- Upload congestion ---
        # UL is 3-state (GREEN/YELLOW/RED), only RED is congested
        ul_congested = ul_zone == "RED"
        if ul_congested:
            if self._ul_congestion_start is None:
                self._ul_congestion_start = now
            elif not self._ul_sustained_fired:
                sustained_sec = self.alert_engine._rules.get(
                    "congestion_sustained_ul", {}
                ).get("sustained_sec", self._sustained_sec)
                duration = now - self._ul_congestion_start
                if duration >= sustained_sec:
                    fired = self.alert_engine.fire(
                        "congestion_sustained_ul",
                        "critical",
                        self.wan_name,
                        {
                            "zone": ul_zone,
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                            "rtt_ms": self.load_rtt,
                            "delta_ms": delta,
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._ul_sustained_fired = True
        else:
            if self._ul_congestion_start is not None:
                if self._ul_sustained_fired:
                    duration = now - self._ul_congestion_start
                    self.alert_engine.fire(
                        "congestion_recovered_ul",
                        "recovery",
                        self.wan_name,
                        {
                            "recovered_from_zone": "RED",
                            "duration_sec": round(duration, 1),
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                        },
                    )
                self._ul_congestion_start = None
                self._ul_sustained_fired = False

    def _check_irtt_loss_alerts(self, irtt_result: IRTTResult) -> None:
        """Check sustained IRTT packet loss and fire alerts (ALRT-01, ALRT-02, ALRT-03).

        Called each run_cycle() when IRTT result is fresh (within 3x cadence).
        Tracks how long upstream/downstream loss has exceeded threshold. Fires
        irtt_loss_upstream/downstream after sustained_sec. Fires irtt_loss_recovered
        when loss clears IF sustained alert had fired (recovery gate).

        Args:
            irtt_result: Fresh IRTTResult with send_loss and receive_loss fields.
        """
        now = time.monotonic()

        # --- Upstream loss (send_loss) ---
        up_rule = self.alert_engine._rules.get("irtt_loss_upstream", {})
        up_threshold = up_rule.get(
            "loss_threshold_pct", self._irtt_loss_threshold_pct
        )
        up_sustained = up_rule.get("sustained_sec", self._sustained_sec)

        if irtt_result.send_loss >= up_threshold:
            if self._irtt_loss_up_start is None:
                self._irtt_loss_up_start = now
            elif not self._irtt_loss_up_fired:
                duration = now - self._irtt_loss_up_start
                if duration >= up_sustained:
                    fired = self.alert_engine.fire(
                        "irtt_loss_upstream",
                        "warning",
                        self.wan_name,
                        {
                            "loss_pct": irtt_result.send_loss,
                            "direction": "upstream",
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._irtt_loss_up_fired = True
        else:
            if self._irtt_loss_up_start is not None:
                if self._irtt_loss_up_fired:
                    duration = now - self._irtt_loss_up_start
                    self.alert_engine.fire(
                        "irtt_loss_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "direction": "upstream",
                            "duration_sec": round(duration, 1),
                            "loss_pct": irtt_result.send_loss,
                        },
                    )
                self._irtt_loss_up_start = None
                self._irtt_loss_up_fired = False

        # --- Downstream loss (receive_loss) ---
        down_rule = self.alert_engine._rules.get("irtt_loss_downstream", {})
        down_threshold = down_rule.get(
            "loss_threshold_pct", self._irtt_loss_threshold_pct
        )
        down_sustained = down_rule.get("sustained_sec", self._sustained_sec)

        if irtt_result.receive_loss >= down_threshold:
            if self._irtt_loss_down_start is None:
                self._irtt_loss_down_start = now
            elif not self._irtt_loss_down_fired:
                duration = now - self._irtt_loss_down_start
                if duration >= down_sustained:
                    fired = self.alert_engine.fire(
                        "irtt_loss_downstream",
                        "warning",
                        self.wan_name,
                        {
                            "loss_pct": irtt_result.receive_loss,
                            "direction": "downstream",
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._irtt_loss_down_fired = True
        else:
            if self._irtt_loss_down_start is not None:
                if self._irtt_loss_down_fired:
                    duration = now - self._irtt_loss_down_start
                    self.alert_engine.fire(
                        "irtt_loss_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "direction": "downstream",
                            "duration_sec": round(duration, 1),
                            "loss_pct": irtt_result.receive_loss,
                        },
                    )
                self._irtt_loss_down_start = None
                self._irtt_loss_down_fired = False

    def _check_connectivity_alerts(self, measured_rtt: float | None) -> None:
        """Check WAN connectivity and fire offline/recovery alerts (ALRT-04, ALRT-05).

        Called each run_cycle() with the raw measured RTT (before fallback processing).
        Tracks how long all ICMP targets have been unreachable. Fires wan_offline
        after sustained_sec threshold (default 30s). Fires wan_recovered when ICMP
        returns IF wan_offline had fired (recovery gate).

        Args:
            measured_rtt: Raw RTT from measure_rtt(), None if all targets unreachable.
        """
        now = time.monotonic()

        if measured_rtt is None:
            # All ICMP targets unreachable
            if self._connectivity_offline_start is None:
                self._connectivity_offline_start = now
            elif not self._wan_offline_fired:
                # Check per-rule sustained_sec override
                sustained_sec = self.alert_engine._rules.get(
                    "wan_offline", {}
                ).get("sustained_sec", self._sustained_sec)
                duration = now - self._connectivity_offline_start
                if duration >= sustained_sec:
                    fired = self.alert_engine.fire(
                        "wan_offline",
                        "critical",
                        self.wan_name,
                        {
                            "duration_sec": round(duration, 1),
                            "ping_targets": len(self.ping_hosts),
                            "last_known_rtt": round(self.load_rtt, 1),
                        },
                    )
                    if fired:
                        self._wan_offline_fired = True
        else:
            # ICMP recovered
            if self._connectivity_offline_start is not None:
                if self._wan_offline_fired:
                    duration = now - self._connectivity_offline_start
                    self.alert_engine.fire(
                        "wan_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "outage_duration_sec": round(duration, 1),
                            "current_rtt": round(measured_rtt, 1),
                            "ping_targets": len(self.ping_hosts),
                        },
                    )
                self._connectivity_offline_start = None
                self._wan_offline_fired = False

    def _check_baseline_drift(self) -> None:
        """Check if baseline RTT has drifted beyond threshold from initial (ALRT-06).

        Compares the EWMA baseline_rtt against the config-set baseline_rtt_initial.
        Fires baseline_drift alert when absolute percentage drift exceeds threshold.
        Cooldown suppression in AlertEngine handles re-fire naturally.

        Uses absolute percentage so both upward drift (ISP degradation) and
        downward drift (routing change) are detected.
        """
        reference = self.config.baseline_rtt_initial
        if reference <= 0:
            return

        drift_pct = abs(self.baseline_rtt - reference) / reference * 100.0

        # Per-rule threshold override (default 50%)
        threshold = self.alert_engine._rules.get("baseline_drift", {}).get(
            "drift_threshold_pct", 50
        )

        if drift_pct >= threshold:
            self.alert_engine.fire(
                "baseline_drift",
                "warning",
                self.wan_name,
                {
                    "current_baseline_ms": round(self.baseline_rtt, 2),
                    "reference_baseline_ms": round(reference, 2),
                    "drift_percent": round(drift_pct, 1),
                },
            )

    def _check_flapping_alerts(self, dl_zone: str, ul_zone: str) -> None:
        """Check for rapid congestion zone flapping and fire alerts (ALRT-07).

        Tracks zone transitions per direction in a sliding time window.
        Fires flapping_dl/flapping_ul when transitions exceed configured
        threshold within the window. DL and UL are tracked independently.

        Args:
            dl_zone: Current download zone (GREEN/YELLOW/SOFT_RED/RED).
            ul_zone: Current upload zone (GREEN/YELLOW/RED).
        """
        now = time.monotonic()

        # Shared config rule for both DL and UL flapping
        flap_rule = self.alert_engine._rules.get("congestion_flapping", {})
        flap_window = flap_rule.get("flap_window_sec", 120)
        flap_threshold = flap_rule.get("flap_threshold", 30)
        flap_severity = flap_rule.get("severity", "warning")

        # Dwell filter: only count transitions where departing zone was held
        # long enough to be a real state, not a single-cycle blip.
        min_hold_sec = flap_rule.get("min_hold_sec", 1.0)
        if min_hold_sec <= 0:
            min_hold_cycles = 0
        else:
            min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))

        # --- Download flapping ---
        if self._dl_prev_zone is not None and dl_zone != self._dl_prev_zone:
            # Only count transition if departing zone was held long enough
            if self._dl_zone_hold >= min_hold_cycles:
                self._dl_zone_transitions.append(now)
            self._dl_zone_hold = 0
        else:
            self._dl_zone_hold += 1
        self._dl_prev_zone = dl_zone

        # Prune old transitions outside window
        while self._dl_zone_transitions and (
            now - self._dl_zone_transitions[0] > flap_window
        ):
            self._dl_zone_transitions.popleft()

        if len(self._dl_zone_transitions) >= flap_threshold:
            self.alert_engine.fire(
                "flapping_dl",
                flap_severity,
                self.wan_name,
                {
                    "transition_count": len(self._dl_zone_transitions),
                    "window_sec": flap_window,
                    "current_zone": dl_zone,
                },
                rule_key="congestion_flapping",
            )
            self._dl_zone_transitions.clear()

        # --- Upload flapping ---
        if self._ul_prev_zone is not None and ul_zone != self._ul_prev_zone:
            # Only count transition if departing zone was held long enough
            if self._ul_zone_hold >= min_hold_cycles:
                self._ul_zone_transitions.append(now)
            self._ul_zone_hold = 0
        else:
            self._ul_zone_hold += 1
        self._ul_prev_zone = ul_zone

        # Prune old transitions outside window
        while self._ul_zone_transitions and (
            now - self._ul_zone_transitions[0] > flap_window
        ):
            self._ul_zone_transitions.popleft()

        if len(self._ul_zone_transitions) >= flap_threshold:
            self.alert_engine.fire(
                "flapping_ul",
                flap_severity,
                self.wan_name,
                {
                    "transition_count": len(self._ul_zone_transitions),
                    "window_sec": flap_window,
                    "current_zone": ul_zone,
                },
                rule_key="congestion_flapping",
            )
            self._ul_zone_transitions.clear()

    @handle_errors(error_msg="{self.wan_name}: Could not load state: {exception}")
    def load_state(self) -> None:
        """Load persisted hysteresis state from disk."""
        state = self.state_manager.load()

        if state is not None:
            # Restore download controller state
            if "download" in state:
                dl = state["download"]
                self.download.green_streak = dl.get("green_streak", 0)
                self.download.soft_red_streak = dl.get("soft_red_streak", 0)
                self.download.red_streak = dl.get("red_streak", 0)
                self.download.current_rate = dl.get("current_rate", self.download.ceiling_bps)

            # Restore upload controller state
            if "upload" in state:
                ul = state["upload"]
                self.upload.green_streak = ul.get("green_streak", 0)
                self.upload.soft_red_streak = ul.get("soft_red_streak", 0)
                self.upload.red_streak = ul.get("red_streak", 0)
                self.upload.current_rate = ul.get("current_rate", self.upload.ceiling_bps)

            # Restore EWMA state
            if "ewma" in state:
                ewma = state["ewma"]
                self.baseline_rtt = ewma.get("baseline_rtt", self.baseline_rtt)
                self.load_rtt = ewma.get("load_rtt", self.load_rtt)

            # Restore last applied rates (flash wear protection)
            if "last_applied" in state:
                applied = state["last_applied"]
                self.last_applied_dl_rate = applied.get("dl_rate")
                self.last_applied_ul_rate = applied.get("ul_rate")

    def _encode_state(self, state: str) -> int:
        """Encode congestion state to numeric value for storage.

        Matches STORED_METRICS schema: 0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED
        """
        state_map = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
        return state_map.get(state, 0)

    @handle_errors(error_msg="{self.wan_name}: Could not save state: {exception}")
    def save_state(self, force: bool = False) -> None:
        """Save hysteresis state to disk for persistence across restarts.

        Args:
            force: If True, bypass dirty tracking and always write
        """
        self.state_manager.save(
            download=self.state_manager.build_controller_state(
                self.download.green_streak,
                self.download.soft_red_streak,
                self.download.red_streak,
                self.download.current_rate,
            ),
            upload=self.state_manager.build_controller_state(
                self.upload.green_streak,
                self.upload.soft_red_streak,
                self.upload.red_streak,
                self.upload.current_rate,
            ),
            ewma={"baseline_rtt": self.baseline_rtt, "load_rtt": self.load_rtt},
            last_applied={
                "dl_rate": self.last_applied_dl_rate,
                "ul_rate": self.last_applied_ul_rate,
            },
            congestion={"dl_state": self._dl_zone, "ul_state": self._ul_zone},
            force=force,
        )


# =============================================================================
# MAIN CONTROLLER
# =============================================================================


class ContinuousAutoRate:
    """Main controller managing one or more WANs"""

    def __init__(self, config_files: list[str], debug: bool = False):
        self.wan_controllers: list[dict[str, Any]] = []
        self.debug = debug

        # Load each WAN config and create controller
        for config_file in config_files:
            config = Config(config_file)
            logger = setup_logging(config, "cake_continuous", debug)

            logger.info(f"=== Continuous CAKE Controller - {config.wan_name} ===")
            dl_green = config.download_floor_green / 1e6
            dl_yellow = config.download_floor_yellow / 1e6
            dl_soft_red = config.download_floor_soft_red / 1e6
            dl_red = config.download_floor_red / 1e6
            dl_ceil = config.download_ceiling / 1e6
            dl_step = config.download_step_up / 1e6
            logger.info(
                f"Download: GREEN={dl_green:.0f}M, YELLOW={dl_yellow:.0f}M, "
                f"SOFT_RED={dl_soft_red:.0f}M, RED={dl_red:.0f}M, "
                f"ceiling={dl_ceil:.0f}M, step={dl_step:.1f}M, "
                f"factor={config.download_factor_down}"
            )
            ul_green = config.upload_floor_green / 1e6
            ul_yellow = config.upload_floor_yellow / 1e6
            ul_red = config.upload_floor_red / 1e6
            ul_ceil = config.upload_ceiling / 1e6
            ul_step = config.upload_step_up / 1e6
            logger.info(
                f"Upload: GREEN={ul_green:.0f}M, YELLOW={ul_yellow:.0f}M, "
                f"RED={ul_red:.0f}M, ceiling={ul_ceil:.0f}M, "
                f"step={ul_step:.1f}M, factor={config.upload_factor_down}"
            )
            logger.info(
                f"Download Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, "
                f"YELLOW→SOFT_RED={config.warn_bloat_ms}ms, "
                f"SOFT_RED→RED={config.hard_red_bloat_ms}ms"
            )
            logger.info(
                f"Upload Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, "
                f"YELLOW→RED={config.warn_bloat_ms}ms"
            )
            logger.info(
                f"EWMA: baseline_alpha={config.alpha_baseline}, load_alpha={config.alpha_load}"
            )
            logger.info(
                f"Ping: hosts={config.ping_hosts}, median-of-three={config.use_median_of_three}"
            )

            # Create shared instances -- select backend based on transport config
            if config.router_transport == "linux-cake":
                from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

                router = LinuxCakeAdapter.from_config(config, logger)
            else:
                router = RouterOS(config, logger)
            clear_router_password(config)
            # Use unified RTTMeasurement with AVERAGE aggregation and sample stats logging
            rtt_measurement = RTTMeasurement(
                logger,
                timeout_ping=config.timeout_ping,
                aggregation_strategy=RTTAggregationStrategy.AVERAGE,
                log_sample_stats=True,  # Log min/max for debugging
                source_ip=config.ping_source_ip,
            )

            # Create WAN controller
            wan_controller = WANController(config.wan_name, config, router, rtt_measurement, logger)

            self.wan_controllers.append(
                {"controller": wan_controller, "config": config, "logger": logger}
            )

    def run_cycle(self, use_lock: bool = True) -> bool:
        """Run one cycle for all WANs

        Args:
            use_lock: If True, acquire lock per-cycle (oneshot mode).
                     If False, assume lock is already held (daemon mode).

        Returns:
            True if ALL WANs successfully completed cycle
            False if ANY WAN failed
        """
        all_success = True

        for wan_info in self.wan_controllers:
            controller = wan_info["controller"]
            config = wan_info["config"]
            logger = wan_info["logger"]

            try:
                if use_lock:
                    with LockFile(config.lock_file, config.lock_timeout, logger):
                        success = controller.run_cycle()
                        all_success = all_success and success
                else:
                    # Lock already held by daemon - just run the cycle
                    success = controller.run_cycle()
                    all_success = all_success and success
            except LockAcquisitionError:
                # Another instance is running - this is normal, not an error
                logger.debug("Skipping cycle - another instance is running")
                all_success = False
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                logger.debug(traceback.format_exc())
                all_success = False

        return all_success

    def get_lock_paths(self) -> list[Path]:
        """Return lock file paths for all configured WANs"""
        return [wan_info["config"].lock_file for wan_info in self.wan_controllers]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def validate_config_mode(config_files: list[str]) -> int:
    """Validate configuration files and print details.

    Args:
        config_files: List of config file paths to validate.

    Returns:
        0 if all configs valid, 1 if any invalid.
    """
    all_valid = True
    for config_file in config_files:
        try:
            config = Config(config_file)
            print(f"Configuration valid: {config_file}")
            print(f"  WAN: {config.wan_name}")
            print(f"  Transport: {config.router_transport}")
            print(f"  Router: {config.router_host}:{config.router_user}")
            dl_min = config.download_floor_red / 1e6
            dl_max = config.download_ceiling / 1e6
            print(f"  Download: {dl_min:.0f}M - {dl_max:.0f}M")
            print(
                f"    Floors: GREEN={config.download_floor_green / 1e6:.0f}M, "
                f"YELLOW={config.download_floor_yellow / 1e6:.0f}M, "
                f"SOFT_RED={config.download_floor_soft_red / 1e6:.0f}M, "
                f"RED={config.download_floor_red / 1e6:.0f}M"
            )
            ul_min = config.upload_floor_red / 1e6
            ul_max = config.upload_ceiling / 1e6
            print(f"  Upload: {ul_min:.0f}M - {ul_max:.0f}M")
            print(
                f"    Floors: GREEN={config.upload_floor_green / 1e6:.0f}M, "
                f"YELLOW={config.upload_floor_yellow / 1e6:.0f}M, "
                f"RED={config.upload_floor_red / 1e6:.0f}M"
            )
            print(
                f"  Thresholds: GREEN<={config.target_bloat_ms}ms, "
                f"SOFT_RED<={config.warn_bloat_ms}ms, RED>{config.hard_red_bloat_ms}ms"
            )
            print(f"  Ping hosts: {config.ping_hosts}")
            print(f"  Queue names: {config.queue_down}, {config.queue_up}")
        except Exception as e:
            print(f"Configuration INVALID: {config_file}")
            print(f"  Error: {e}")
            all_valid = False
    return 0 if all_valid else 1


def _parse_autorate_args() -> argparse.Namespace:
    """Parse command-line arguments for the autorate daemon.

    Returns:
        Parsed argument namespace with config, debug, oneshot, validate_config,
        and profile flags.
    """
    parser = argparse.ArgumentParser(
        description="Continuous CAKE Auto-Tuning Daemon with 50ms Control Loop"
    )
    parser.add_argument(
        "--config",
        nargs="+",
        required=True,
        help="One or more config files (supports single-WAN or multi-WAN)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging to console and debug log file"
    )
    parser.add_argument(
        "--oneshot", action="store_true", help="Run one cycle and exit (for testing/manual runs)"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit (dry-run mode for CI/CD)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable periodic profiling reports (INFO level)",
    )
    return parser.parse_args()


def _init_storage(
    controller: "ContinuousAutoRate",
) -> tuple[Any, int]:
    """Initialize storage, record config snapshot, and run startup maintenance.

    Args:
        controller: The ContinuousAutoRate instance (for config/logger access).

    Returns:
        Tuple of (maintenance_conn, maintenance_retention_days).
        maintenance_conn is None if storage is not enabled.
    """
    first_config = controller.wan_controllers[0]["config"]
    storage_config = get_storage_config(first_config.data)
    db_path = storage_config.get("db_path")
    maintenance_conn = None
    maintenance_retention_days = storage_config.get("retention_days", 7)

    # Only record snapshot if db_path is a valid string (not MagicMock in tests)
    if db_path and isinstance(db_path, str):
        from wanctl.storage import MetricsWriter, record_config_snapshot, run_startup_maintenance

        writer = MetricsWriter(Path(db_path))
        maintenance_conn = writer.connection
        record_config_snapshot(writer, first_config.wan_name, first_config.data, "startup")

        # Run startup maintenance (cleanup + downsampling)
        # Pass watchdog callback and time budget to prevent exceeding WatchdogSec=30s
        maint_result = run_startup_maintenance(
            maintenance_conn,
            retention_days=maintenance_retention_days,
            log=controller.wan_controllers[0]["logger"],
            watchdog_fn=notify_watchdog,
            max_seconds=20,
        )
        if maint_result.get("error"):
            controller.wan_controllers[0]["logger"].warning(
                f"Startup maintenance error: {maint_result['error']}"
            )

    return maintenance_conn, maintenance_retention_days


def _acquire_daemon_locks(
    controller: "ContinuousAutoRate",
) -> tuple[list[Path], int | None]:
    """Acquire exclusive locks for all WAN controllers.

    Args:
        controller: The ContinuousAutoRate instance.

    Returns:
        Tuple of (lock_files, error_code). error_code is None on success,
        1 if lock acquisition failed.
    """
    lock_files: list[Path] = []
    for lock_path in controller.get_lock_paths():
        logger = controller.wan_controllers[0]["logger"]
        lock_timeout = controller.wan_controllers[0]["config"].lock_timeout
        try:
            if not validate_and_acquire_lock(lock_path, lock_timeout, logger):
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].error("Another instance is running, refusing to start")
                return lock_files, 1
            lock_files.append(lock_path)
        except RuntimeError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].error(f"Failed to validate lock: {e}")
            return lock_files, 1
    return lock_files, None


def _start_servers(
    controller: "ContinuousAutoRate",
) -> tuple[Any, Any]:
    """Start optional metrics and health check servers.

    Args:
        controller: The ContinuousAutoRate instance.

    Returns:
        Tuple of (metrics_server, health_server). Either may be None if
        not configured or if startup fails (non-fatal).
    """
    metrics_server = None
    health_server = None
    first_config = controller.wan_controllers[0]["config"]

    if first_config.metrics_enabled:
        try:
            metrics_server = start_metrics_server(
                host=first_config.metrics_host,
                port=first_config.metrics_port,
            )
            for wan_info in controller.wan_controllers:
                wan_info["logger"].info(
                    f"Prometheus metrics available at "
                    f"http://{first_config.metrics_host}:{first_config.metrics_port}/metrics"
                )
        except OSError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].warning(f"Failed to start metrics server: {e}")

    if first_config.health_check_enabled:
        try:
            health_server = start_health_server(
                host=first_config.health_check_host,
                port=first_config.health_check_port,
                controller=controller,
            )
        except OSError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].warning(f"Failed to start health check server: {e}")

    return metrics_server, health_server


def _start_irtt_thread(
    controller: "ContinuousAutoRate",
) -> IRTTThread | None:
    """Start IRTT background measurement thread if IRTT is available.

    Returns None if IRTT is disabled or unavailable.
    """
    first_config = controller.wan_controllers[0]["config"]
    logger = controller.wan_controllers[0]["logger"]

    measurement = IRTTMeasurement(first_config.irtt_config, logger)
    if not measurement.is_available():
        return None

    shutdown_event = get_shutdown_event()
    cadence_sec = first_config.irtt_config.get("cadence_sec", 10.0)
    thread = IRTTThread(measurement, cadence_sec, shutdown_event, logger)
    thread.start()
    return thread


def main() -> int | None:
    """Main entry point for continuous CAKE auto-tuning daemon.

    Runs persistent bandwidth control with adaptive rate adjustment based on real-time
    latency measurements. Supports both single-WAN and multi-WAN configurations with
    concurrent control loops for each interface.

    The daemon operates in several modes:
    - **Daemon mode** (default): Runs continuous control loop at 50ms intervals,
      monitoring latency and adjusting CAKE queue limits to prevent bufferbloat while
      maximizing throughput. Handles SIGTERM/SIGINT gracefully and integrates with
      systemd watchdog for automatic recovery.
    - **Oneshot mode** (--oneshot): Executes single measurement and adjustment cycle,
      useful for testing and manual verification.
    - **Validation mode** (--validate-config): Validates configuration files and exits,
      ideal for CI/CD pipelines and pre-deployment checks.

    Startup sequence:
    1. Parse command-line arguments and load YAML configurations
    2. Initialize ContinuousAutoRate controller with per-WAN state machines
    3. Acquire exclusive locks to prevent concurrent instances
    4. Register signal handlers for graceful shutdown
    5. Start optional metrics (Prometheus) and health check servers
    6. Enter control loop with automatic watchdog notification

    Shutdown sequence (on SIGTERM/SIGINT):
    1. Stop accepting new cycles (shutdown_event set)
    2. Release all lock files
    3. Close router connections (SSH/REST)
    4. Shut down metrics and health servers
    5. Log clean shutdown and exit

    Returns:
        int | None: Exit code indicating daemon termination reason:
            - 0: Configuration validation passed (--validate-config mode)
            - 1: Configuration validation failed or lock acquisition failed
            - 130: Interrupted by signal (SIGINT/Ctrl+C)
            - None: Clean shutdown in daemon mode (SIGTERM or oneshot completion)
    """
    args = _parse_autorate_args()

    # Validate-config mode: check configuration and exit
    if args.validate_config:
        return validate_config_mode(args.config)

    # Create controller
    controller = ContinuousAutoRate(args.config, debug=args.debug)

    # Enable profiling on all WAN controllers if --profile flag set
    if args.profile:
        for wan_info in controller.wan_controllers:
            wan_info["controller"]._profiling_enabled = True

    # Initialize storage, record config snapshot, and run startup maintenance
    maintenance_conn, maintenance_retention_days = _init_storage(controller)

    # Oneshot mode for testing - use per-cycle locking
    if args.oneshot:
        controller.run_cycle(use_lock=True)
        return None

    # Daemon mode: continuous loop with 50ms cycle time
    # Acquire locks once at startup and hold for entire run
    lock_files, lock_error = _acquire_daemon_locks(controller)
    if lock_error is not None:
        return lock_error

    # Register emergency cleanup handler for abnormal termination (e.g., SIGKILL)
    # atexit handlers run on normal exit, sys.exit(), and unhandled exceptions
    # but NOT on SIGKILL - that's unavoidable. However, this covers more cases
    # than relying solely on the finally block.
    def emergency_lock_cleanup() -> None:
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # Best effort - nothing we can do

    atexit.register(emergency_lock_cleanup)

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    watchdog_enabled = True
    last_maintenance = time.monotonic()
    last_tuning = time.monotonic()

    # Start optional servers (metrics, health check)
    metrics_server, health_server = _start_servers(controller)

    # Start IRTT background measurement thread (if configured)
    irtt_thread = _start_irtt_thread(controller)

    # Pass irtt_thread reference to each WAN controller
    for wan_info in controller.wan_controllers:
        wan_info["controller"]._irtt_thread = irtt_thread

    # Log startup
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(
            f"Starting daemon mode with {CYCLE_INTERVAL_SECONDS}s cycle interval"
        )
        if is_systemd_available():
            wan_info["logger"].info("Systemd watchdog support enabled")

    # Get shutdown event for interruptible sleep (instant signal responsiveness)
    shutdown_event = get_shutdown_event()

    try:
        while not is_shutdown_requested():
            cycle_start = time.monotonic()

            # Run cycle - returns True if successful
            cycle_success = controller.run_cycle(use_lock=False)  # Lock already held

            elapsed = time.monotonic() - cycle_start

            # Track consecutive failures
            if cycle_success:
                consecutive_failures = 0
                # Re-enable watchdog if previously surrendered (recovery)
                if not watchdog_enabled:
                    watchdog_enabled = True
                    for wan_info in controller.wan_controllers:
                        wan_info["logger"].info(
                            "Cycle recovered after watchdog surrender. "
                            "Re-enabling watchdog notifications."
                        )
            else:
                consecutive_failures += 1

                for wan_info in controller.wan_controllers:
                    wan_info["logger"].warning(
                        f"Cycle failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    )

                # Check if we've exceeded failure threshold
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
                    watchdog_enabled = False
                    for wan_info in controller.wan_controllers:
                        wan_info["logger"].error(
                            f"Sustained failure: {consecutive_failures} consecutive "
                            f"failed cycles. Stopping watchdog - systemd will terminate us."
                        )
                    notify_degraded("consecutive failures exceeded threshold")

            # Update health check endpoint with current failure count
            update_health_status(consecutive_failures)

            # Determine if failure is router-only (daemon healthy, router down)
            router_only_failure = False
            if not cycle_success:
                all_routers_unreachable = all(
                    not wan_info["controller"].router_connectivity.is_reachable
                    for wan_info in controller.wan_controllers
                )
                any_auth_failure = any(
                    wan_info["controller"].router_connectivity.last_failure_type == "auth_failure"
                    for wan_info in controller.wan_controllers
                )
                router_only_failure = all_routers_unreachable and not any_auth_failure

            # Notify systemd watchdog with router failure distinction (ERRR-04)
            if watchdog_enabled and cycle_success:
                notify_watchdog()
            elif watchdog_enabled and router_only_failure:
                notify_watchdog()
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].info(
                        f"Router unreachable ({consecutive_failures} cycles), watchdog continues"
                    )
            elif not watchdog_enabled:
                notify_degraded(f"{consecutive_failures} consecutive failures")

            # Periodic maintenance: cleanup + downsample + vacuum every hour
            if maintenance_conn is not None:
                now = time.monotonic()
                if now - last_maintenance >= MAINTENANCE_INTERVAL:
                    maint_logger = controller.wan_controllers[0]["logger"]
                    try:
                        from wanctl.storage.downsampler import downsample_metrics
                        from wanctl.storage.retention import cleanup_old_metrics, vacuum_if_needed

                        deleted = cleanup_old_metrics(
                            maintenance_conn,
                            maintenance_retention_days,
                            watchdog_fn=notify_watchdog,
                        )
                        notify_watchdog()

                        downsampled = downsample_metrics(
                            maintenance_conn, watchdog_fn=notify_watchdog
                        )
                        notify_watchdog()

                        vacuumed = vacuum_if_needed(maintenance_conn, deleted)
                        notify_watchdog()

                        total_ds = sum(downsampled.values())
                        if deleted > 0 or total_ds > 0 or vacuumed:
                            maint_logger.info(
                                "Periodic maintenance: deleted=%d, downsampled=%d, vacuumed=%s",
                                deleted,
                                total_ds,
                                vacuumed,
                            )
                    except Exception as e:
                        maint_logger.error("Periodic maintenance failed: %s", e)

                    last_maintenance = now

            # Adaptive tuning (runs after maintenance, on its own cadence)
            tuning_config = getattr(
                controller.wan_controllers[0]["controller"].config,
                "tuning_config",
                None,
            )
            if isinstance(tuning_config, TuningConfig) and tuning_config.enabled:
                now = time.monotonic()
                tuning_cadence = tuning_config.cadence_sec
                if now - last_tuning >= tuning_cadence:
                    from wanctl.tuning.analyzer import run_tuning_analysis
                    from wanctl.tuning.applier import (
                        apply_tuning_results,
                        persist_revert_record,
                    )
                    from wanctl.tuning.safety import (
                        DEFAULT_MIN_CONGESTION_RATE,
                        DEFAULT_REVERT_COOLDOWN_SEC,
                        DEFAULT_REVERT_THRESHOLD,
                        PendingObservation,
                        check_and_revert,
                        is_parameter_locked,
                        lock_parameter,
                        measure_congestion_rate,
                    )
                    from wanctl.tuning.strategies.advanced import (
                        tune_baseline_bounds_max,
                        tune_baseline_bounds_min,
                        tune_fusion_weight,
                        tune_reflector_min_score,
                    )
                    from wanctl.tuning.strategies.congestion_thresholds import (
                        calibrate_target_bloat,
                        calibrate_warn_bloat,
                    )
                    from wanctl.tuning.strategies.signal_processing import (
                        tune_alpha_load,
                        tune_hampel_sigma,
                        tune_hampel_window,
                    )

                    first_config = controller.wan_controllers[0]["config"]
                    storage_config = get_storage_config(first_config.data)
                    db_path = storage_config.get("db_path", "")
                    metrics_writer = controller.wan_controllers[0][
                        "controller"
                    ]._metrics_writer

                    # Layer definitions for bottom-up tuning (SIGP-04)
                    SIGNAL_LAYER = [
                        ("hampel_sigma_threshold", tune_hampel_sigma),
                        ("hampel_window_size", tune_hampel_window),
                    ]
                    EWMA_LAYER = [
                        ("load_time_constant_sec", tune_alpha_load),
                    ]
                    THRESHOLD_LAYER = [
                        ("target_bloat_ms", calibrate_target_bloat),
                        ("warn_bloat_ms", calibrate_warn_bloat),
                    ]
                    ADVANCED_LAYER = [
                        ("fusion_icmp_weight", tune_fusion_weight),
                        ("reflector_min_score", tune_reflector_min_score),
                        ("baseline_rtt_min", tune_baseline_bounds_min),
                        ("baseline_rtt_max", tune_baseline_bounds_max),
                    ]
                    ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER]

                    for wan_info in controller.wan_controllers:
                        wc = wan_info["controller"]
                        if not wc._tuning_enabled:
                            continue

                        # Step 1: Check pending observation from previous cycle
                        try:
                            reverts = check_and_revert(
                                wc._pending_observation,
                                db_path,
                                wc.wan_name,
                                revert_threshold=DEFAULT_REVERT_THRESHOLD,
                                min_congestion_rate=DEFAULT_MIN_CONGESTION_RATE,
                            )
                            if reverts:
                                _apply_tuning_to_controller(wc, reverts)
                                for rv in reverts:
                                    persist_revert_record(rv, metrics_writer)
                                    lock_parameter(
                                        wc._parameter_locks,
                                        rv.parameter,
                                        DEFAULT_REVERT_COOLDOWN_SEC,
                                    )
                                    wan_info["logger"].error(
                                        "[TUNING] %s: %s",
                                        wc.wan_name,
                                        rv.rationale,
                                    )
                        except Exception as e:
                            wan_info["logger"].error(
                                "[TUNING] Revert check failed for %s: %s",
                                wc.wan_name,
                                e,
                            )
                        wc._pending_observation = None  # Clear regardless

                        # Step 2: Select active layer via round-robin (SIGP-04)
                        active_layer = ALL_LAYERS[
                            wc._tuning_layer_index % len(ALL_LAYERS)
                        ]
                        wc._tuning_layer_index += 1

                        # Step 3: Filter locked parameters from active layer
                        active_strategies = [
                            (pname, sfn)
                            for pname, sfn in active_layer
                            if not is_parameter_locked(
                                wc._parameter_locks, pname
                            )
                        ]
                        for pname, _ in active_layer:
                            if is_parameter_locked(
                                wc._parameter_locks, pname
                            ):
                                wan_info["logger"].info(
                                    "[TUNING] %s: %s locked until revert cooldown expires",
                                    wc.wan_name,
                                    pname,
                                )

                        # Step 4: Run analysis with active (unlocked) strategies
                        current_params = {
                            "target_bloat_ms": wc.green_threshold,
                            "warn_bloat_ms": wc.soft_red_threshold,
                            "hard_red_bloat_ms": wc.hard_red_threshold,
                            "alpha_load": wc.alpha_load,
                            "alpha_baseline": wc.alpha_baseline,
                            "hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
                            "hampel_window_size": float(wc.signal_processor._window_size),
                            "load_time_constant_sec": 0.05 / wc.alpha_load,
                            "fusion_icmp_weight": wc._fusion_icmp_weight,
                            "reflector_min_score": wc._reflector_scorer._min_score,
                            "baseline_rtt_min": wc.baseline_rtt_min,
                            "baseline_rtt_max": wc.baseline_rtt_max,
                        }
                        try:
                            results = run_tuning_analysis(
                                wan_name=wc.wan_name,
                                db_path=db_path,
                                tuning_config=tuning_config,
                                current_params=current_params,
                                strategies=active_strategies,
                            )
                            if results:
                                applied = apply_tuning_results(
                                    results, tuning_config, metrics_writer
                                )
                                if applied:
                                    _apply_tuning_to_controller(wc, applied)
                                    # Step 5: Snapshot pre-adjustment congestion rate
                                    pre_rate = measure_congestion_rate(
                                        db_path,
                                        wc.wan_name,
                                        start_ts=int(time.time())
                                        - tuning_config.cadence_sec,
                                        end_ts=int(time.time()),
                                    )
                                    if pre_rate is not None:
                                        wc._pending_observation = (
                                            PendingObservation(
                                                applied_ts=int(time.time()),
                                                pre_congestion_rate=pre_rate,
                                                applied_results=tuple(
                                                    applied
                                                ),
                                            )
                                        )
                        except Exception as e:
                            wan_info["logger"].error(
                                "[TUNING] Analysis failed for %s: %s",
                                wc.wan_name,
                                e,
                            )
                    last_tuning = now

            # Check for config reload signal (SIGUSR1)
            if is_reload_requested():
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].info(
                        "SIGUSR1 received, reloading config"
                    )
                    wan_info["controller"]._reload_fusion_config()
                    wan_info["controller"]._reload_tuning_config()
                reset_reload_state()

            # Sleep for remainder of cycle interval
            sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
            if sleep_time > 0 and not is_shutdown_requested():
                shutdown_event.wait(timeout=sleep_time)

        # Log shutdown when detected (safe - in main loop, not signal handler)
        if is_shutdown_requested():
            for wan_info in controller.wan_controllers:
                wan_info["logger"].info("Shutdown requested, exiting gracefully...")

    finally:
        # CLEANUP PRIORITY: state > locks > connections > servers > metrics
        cleanup_start = time.monotonic()
        deadline = cleanup_start + SHUTDOWN_TIMEOUT_SECONDS
        _cleanup_log = logging.getLogger(__name__)
        _cleanup_log.info("Shutting down daemon...")

        # 0. Force save state for all WANs (preserve EWMA/counters on shutdown)
        t0 = time.monotonic()
        for wan_info in controller.wan_controllers:
            try:
                wan_info["controller"].save_state(force=True)
            except Exception:
                pass  # nosec B110 - Best effort shutdown cleanup, failure is acceptable
        check_cleanup_deadline("state_save", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # 0.5. Stop IRTT background thread
        t0 = time.monotonic()
        if irtt_thread is not None:
            try:
                irtt_thread.stop()
            except Exception as e:
                _cleanup_log.debug(f"Error stopping IRTT thread: {e}")
        check_cleanup_deadline("irtt_thread", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # 1. Clean up lock files (highest priority for restart capability)
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Lock released: {lock_path}")
            except OSError:
                pass  # Best effort - may already be gone

        # Unregister atexit handler since we've cleaned up successfully
        try:
            atexit.unregister(emergency_lock_cleanup)
        except Exception:
            pass  # nosec B110 - Not critical if this fails during shutdown

        # 2. Clean up SSH/REST connections
        t0 = time.monotonic()
        for wan_info in controller.wan_controllers:
            try:
                router = wan_info["controller"].router
                # Handle both SSH and REST transports
                if hasattr(router, "client") and router.client:
                    router.client.close()
                if hasattr(router, "close"):
                    router.close()
            except Exception as e:
                wan_info["logger"].debug(f"Error closing router connection: {e}")
        check_cleanup_deadline("router_close", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # 3. Shut down metrics server
        t0 = time.monotonic()
        if metrics_server:
            try:
                metrics_server.stop()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Error shutting down metrics server: {e}")
        check_cleanup_deadline("metrics_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # 4. Shut down health check server
        t0 = time.monotonic()
        if health_server:
            try:
                health_server.shutdown()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Error shutting down health server: {e}")
        check_cleanup_deadline("health_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # 5. Close MetricsWriter (SQLite connection)
        t0 = time.monotonic()
        try:
            if MetricsWriter._instance is not None:
                MetricsWriter._instance.close()
                _cleanup_log.debug("MetricsWriter connection closed")
        except Exception as e:
            _cleanup_log.debug(f"Error closing MetricsWriter: {e}")
        check_cleanup_deadline("metrics_writer", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic())

        # Log clean shutdown
        total = time.monotonic() - cleanup_start
        for wan_info in controller.wan_controllers:
            wan_info["logger"].info(f"Daemon shutdown complete ({total:.1f}s)")

    return None


if __name__ == "__main__":
    sys.exit(main())

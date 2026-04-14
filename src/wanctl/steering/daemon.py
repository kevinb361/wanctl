#!/usr/bin/env python3
"""
Adaptive Multi-WAN Steering Daemon

Routes latency-sensitive traffic to an alternate WAN when the primary WAN degrades.
Uses three-layer architecture:
  Layer 1 (DSCP): EF/AF31 = latency-sensitive
  Layer 2 (Connection-marks): QOS_HIGH,QOS_MEDIUM,GAMES marks drive routing
  Layer 3 (Address-lists): Surgical overrides via FORCE_OUT_<WAN>

State machine:
  <PRIMARY>_GOOD: All traffic uses primary WAN (default)
  <PRIMARY>_DEGRADED: Latency-sensitive traffic routes to alternate WAN

Decision logic:
  delta = current_rtt - baseline_rtt
  Hysteresis prevents flapping (asymmetric streak counting)

Runs as a persistent daemon with configurable cycle interval.
Colocated with autorate_continuous on primary WAN controller.
"""

import argparse
import atexit
import json
import logging
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from ..alert_engine import AlertEngine
from ..backends.linux_cake import TIN_NAMES
from ..config_base import BaseConfig, get_storage_config
from ..config_validation_utils import (
    deprecate_param,
    validate_alpha,
    validate_retention_tuner_compat,
)
from ..daemon_utils import check_cleanup_deadline
from ..lock_utils import validate_and_acquire_lock
from ..logging_utils import setup_logging
from ..metrics import (
    get_storage_metrics_snapshot,
    record_steering_state,
    record_steering_transition,
    record_storage_maintenance_lock_skip,
)
from ..perf_profiler import (
    PROFILE_REPORT_INTERVAL,  # noqa: F401 -- re-exported for test compatibility
    OperationProfiler,
    PerfTimer,
    record_cycle_profiling,
)
from ..retry_utils import measure_with_retry, verify_with_retry
from ..router_client import clear_router_password, get_router_client_with_failover
from ..router_connectivity import RouterConnectivityState
from ..rtt_measurement import RTTAggregationStrategy, RTTMeasurement
from ..runtime_pressure import get_storage_file_snapshot, read_process_memory_status
from ..signal_utils import (
    SHUTDOWN_TIMEOUT_SECONDS,
    get_shutdown_event,
    is_reload_requested,
    is_shutdown_requested,
    register_signal_handlers,
    reset_reload_state,
)
from ..state_manager import StateSchema, SteeringStateManager
from ..state_utils import safe_json_load_file
from ..storage import MetricsWriter
from ..systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_watchdog,
)
from ..timeouts import DEFAULT_STEERING_SSH_TIMEOUT
from .cake_stats import CakeStatsReader, CongestionSignals
from .congestion_assessment import (
    CongestionState,
    StateThresholds,
    assess_congestion_state,
    ewma_update,
)
from .health import (
    SteeringHealthServer,
    start_steering_health_server,
    update_steering_health_status,
)
from .steering_confidence import (
    ConfidenceController,
    ConfidenceSignals,
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Default sample counts for state transitions
DEFAULT_GREEN_SAMPLES_REQUIRED = 15  # Consecutive GREEN samples before steering off

# Default RTT thresholds for congestion states (milliseconds)
DEFAULT_GREEN_RTT_MS = 5.0  # Below this = GREEN
DEFAULT_YELLOW_RTT_MS = 15.0  # Above this = YELLOW
DEFAULT_RED_RTT_MS = 15.0  # Above this (with drops) = RED

# Default queue thresholds (packets)
DEFAULT_MIN_QUEUE_YELLOW = 10  # Queue depth for YELLOW warning
DEFAULT_MIN_QUEUE_RED = 50  # Queue depth for RED (deeper congestion)

# Default EWMA smoothing factors
DEFAULT_RTT_EWMA_ALPHA = 0.3
DEFAULT_QUEUE_EWMA_ALPHA = 0.4

# Production standard: 0.05s interval (validated Phase 2, 2026-01-13)
# - Synchronizes with autorate_continuous.py CYCLE_INTERVAL_SECONDS
# - 40x faster than original 2s baseline
# See docs/PRODUCTION_INTERVAL.md for time-constant preservation methodology
ASSESSMENT_INTERVAL_SECONDS = 0.05  # Time between assessments (daemon cycle interval)

# Baseline RTT sanity bounds (milliseconds) - C4 fix: tightened from 5-100 to 10-60
# Typical home ISP latencies are 20-50ms. Anything below 10ms indicates local LAN,
# anything above 60ms suggests routing issues or compromised autorate state.
MIN_SANE_BASELINE_RTT = 10.0
MAX_SANE_BASELINE_RTT = 60.0
BASELINE_CHANGE_THRESHOLD = 5.0  # Log warning if baseline changes more than this

# Maximum sane RTT delta (ms) — anything above this is a network anomaly
# (routing hiccup, severe packet loss), not a usable congestion signal.
# With baseline ~23ms, this allows absolute RTT up to ~523ms before rejection.
MAX_SANE_RTT_DELTA_MS = 500.0

# PROFILE_REPORT_INTERVAL imported from perf_profiler (shared with autorate)


# =============================================================================
# CONFIGURATION
# =============================================================================


class SteeringConfig(BaseConfig):
    """Configuration loaded from YAML for steering daemon"""

    # Schema for steering daemon configuration validation
    SCHEMA = [
        # Topology (which WANs to monitor)
        {"path": "topology.primary_wan", "type": str, "required": True},
        {"path": "topology.primary_wan_config", "type": str, "required": True},
        {"path": "topology.alternate_wan", "type": str, "required": True},
        # Mangle rule
        {"path": "mangle_rule.comment", "type": str, "required": True},
        # Measurement
        {
            "path": "measurement.interval_seconds",
            "type": (int, float),
            "required": True,
            "min": 0.01,
            "max": 60,
        },
        {"path": "measurement.ping_host", "type": str, "required": True},
        {"path": "measurement.ping_count", "type": int, "required": True, "min": 1, "max": 20},
        # State persistence
        {"path": "state.file", "type": str, "required": True},
        {"path": "state.history_size", "type": int, "required": True, "min": 1, "max": 3000},
        # Thresholds (required section, individual fields have defaults)
        {"path": "thresholds", "type": dict, "required": True},
    ]

    def _load_router_transport(self) -> None:
        """Load router transport settings (REST or SSH)."""
        router = self.data["router"]
        self.router_transport = router.get(
            "transport", "rest"
        )  # Default to REST (2x faster than SSH, see docs/TRANSPORT_COMPARISON.md)
        # REST-specific settings
        self.router_password = router.get("password", "")
        self.router_port = router.get("port", 443)
        self.router_verify_ssl = router.get("verify_ssl", True)

    def _load_topology(self) -> None:
        """Load topology - which WANs to monitor and steer between."""
        topology = self.data.get("topology", {})
        self.primary_wan = topology.get("primary_wan", "wan1")
        self.primary_wan_config = Path(
            topology.get("primary_wan_config", f"/etc/wanctl/{self.primary_wan}.yaml")
        )
        self.alternate_wan = topology.get("alternate_wan", "wan2")

        # Derive state names from topology (e.g., "WAN1_GOOD", "WAN1_DEGRADED")
        self.state_good = f"{self.primary_wan.upper()}_GOOD"
        self.state_degraded = f"{self.primary_wan.upper()}_DEGRADED"

    def _load_state_sources(self) -> None:
        """Load primary WAN state file path with legacy support."""
        logger = logging.getLogger(__name__)
        sources = self.data.get("cake_state_sources", {})

        # Deprecation: translate legacy cake_state_sources.spectrum -> primary
        _primary_from_spectrum = deprecate_param(
            sources,
            "spectrum",
            "primary",
            logger,
        )
        if _primary_from_spectrum is not None:
            sources["primary"] = _primary_from_spectrum

        self.primary_state_file = Path(
            sources.get("primary", f"/var/lib/wanctl/{self.primary_wan}_state.json")
        )

    def _load_mangle_config(self) -> None:
        """Load mangle rule configuration with validation."""
        self.mangle_rule_comment = self.validate_comment(
            self.data["mangle_rule"]["comment"], "mangle_rule.comment"
        )

    def _load_rtt_measurement(self) -> None:
        """Load RTT measurement settings with validation (C3 fix)."""
        self.measurement_interval = self.data["measurement"]["interval_seconds"]
        self.ping_host = self.validate_ping_host(
            self.data["measurement"]["ping_host"], "measurement.ping_host"
        )
        self.ping_count = self.data["measurement"]["ping_count"]

    def _load_cake_queues(self) -> None:
        """Load CAKE queue names with legacy support and validation."""
        logger = logging.getLogger(__name__)
        cake_queues = self.data.get("cake_queues", {})
        default_dl_queue = f"WAN-Download-{self.primary_wan.capitalize()}"
        default_ul_queue = f"WAN-Upload-{self.primary_wan.capitalize()}"

        # Deprecation: translate legacy spectrum_download -> primary_download
        _dl_from_spectrum = deprecate_param(
            cake_queues,
            "spectrum_download",
            "primary_download",
            logger,
        )
        if _dl_from_spectrum is not None:
            cake_queues["primary_download"] = _dl_from_spectrum

        # Deprecation: translate legacy spectrum_upload -> primary_upload
        _ul_from_spectrum = deprecate_param(
            cake_queues,
            "spectrum_upload",
            "primary_upload",
            logger,
        )
        if _ul_from_spectrum is not None:
            cake_queues["primary_upload"] = _ul_from_spectrum

        self.primary_download_queue = self.validate_identifier(
            cake_queues.get("primary_download", default_dl_queue),
            "cake_queues.primary_download",
        )
        self.primary_upload_queue = self.validate_identifier(
            cake_queues.get("primary_upload", default_ul_queue),
            "cake_queues.primary_upload",
        )

    def _load_operational_mode(self) -> None:
        """Load operational mode settings."""
        mode = self.data.get("mode", {})

        # Deprecation: cake_aware was removed in v1.12 -- CAKE three-state model
        # is always active. Warn if someone still has it in their config.
        if "cake_aware" in mode:
            logger = logging.getLogger(__name__)
            logger.warning(
                "Deprecated config parameter 'mode.cake_aware': "
                "CAKE three-state model is always active, this key is ignored"
            )

        self.enable_yellow_state = mode.get("enable_yellow_state", True)
        self.use_confidence_scoring = mode.get("use_confidence_scoring", False)

    def _load_confidence_config(self) -> None:
        """Load confidence-based steering configuration.

        Only loads if use_confidence_scoring is enabled. All values have safe
        defaults, with dry_run=True as the most critical default for safe deployment.

        The confidence_config dict structure matches ConfidenceController's config_v3 format.
        """
        if not self.use_confidence_scoring:
            self.confidence_config = None
            return

        confidence = self.data.get("confidence", {})

        # Validate confidence thresholds are in 0-100 range
        steer_threshold = confidence.get("steer_threshold", 55)
        recovery_threshold = confidence.get("recovery_threshold", 20)
        if not (0 <= steer_threshold <= 100):
            raise ValueError(
                f"confidence.steer_threshold ({steer_threshold}) must be in range 0-100"
            )
        if not (0 <= recovery_threshold <= 100):
            raise ValueError(
                f"confidence.recovery_threshold ({recovery_threshold}) must be in range 0-100"
            )
        if recovery_threshold >= steer_threshold:
            raise ValueError(
                f"confidence.recovery_threshold ({recovery_threshold}) must be less than "
                f"steer_threshold ({steer_threshold})"
            )

        self.confidence_config = {
            "confidence": {
                "steer_threshold": steer_threshold,
                "recovery_threshold": recovery_threshold,
                "sustain_duration_sec": confidence.get("sustain_duration_sec", 2.0),
                "recovery_sustain_sec": confidence.get("recovery_sustain_sec", 3.0),
            },
            "timers": {
                "hold_down_duration_sec": confidence.get("hold_down_duration_sec", 30.0),
            },
            "flap_detection": {
                "enabled": confidence.get("flap_detection_enabled", True),
                "window_minutes": confidence.get("flap_window_minutes", 5),
                "max_toggles": confidence.get("max_toggles", 4),
                "penalty_duration_sec": confidence.get("penalty_duration_sec", 60.0),
                "penalty_threshold_add": confidence.get("penalty_threshold_add", 15),
            },
            "dry_run": {
                "enabled": confidence.get("dry_run", True),  # DEFAULT TRUE for safe deployment
            },
        }

    def _load_wan_state_config(self) -> None:
        """Load WAN-aware steering configuration.

        Validates the optional wan_state: YAML section. Invalid config warns
        and disables the feature (does not crash). Feature ships disabled by
        default per SAFE-04.

        Sets self.wan_state_config to a dict with all fields when valid and
        enabled, or None when absent/disabled/invalid.
        """
        logger = logging.getLogger(__name__)
        wan_state = self.data.get("wan_state", {})

        validated = self._validate_wan_state_fields(wan_state, logger)
        if validated is None:
            self.wan_state_config = None
            return

        self.wan_state_config = self._build_wan_state_config(validated, logger)

    def _validate_wan_state_fields(
        self, wan_state: dict, logger: logging.Logger
    ) -> dict | None:
        """Validate wan_state YAML fields. Returns validated dict or None."""
        known_keys = {
            "enabled", "red_weight", "staleness_threshold_sec",
            "grace_period_sec", "wan_override",
        }

        if not wan_state:
            logger.info("WAN awareness: disabled (enable via wan_state.enabled)")
            return None

        unknown = set(wan_state.keys()) - known_keys
        if unknown:
            logger.warning(f"wan_state: unrecognized keys {unknown} (possible typo)")

        enabled = wan_state.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"wan_state.enabled must be bool, got {type(enabled).__name__}; "
                "disabling WAN awareness"
            )
            return None

        wan_override = wan_state.get("wan_override", False)
        if not isinstance(wan_override, bool):
            logger.warning(
                f"wan_state.wan_override must be bool, got {type(wan_override).__name__}; "
                "disabling WAN awareness"
            )
            return None

        if wan_override and not enabled:
            logger.warning("wan_state: override has no effect when disabled")

        if not enabled:
            logger.info("WAN awareness: disabled (enable via wan_state.enabled)")
            return None

        numerics = self._validate_wan_state_numerics(wan_state, logger)
        if numerics is None:
            return None

        return {**numerics, "wan_override": wan_override}

    def _validate_wan_state_numerics(
        self, wan_state: dict, logger: logging.Logger
    ) -> dict[str, int | float] | None:
        """Validate numeric wan_state fields. Returns dict or None on error."""
        try:
            red_weight = wan_state.get("red_weight", 25)
            if not isinstance(red_weight, int) or isinstance(red_weight, bool):
                raise TypeError(
                    f"wan_state.red_weight must be int, got {type(red_weight).__name__}"
                )

            staleness_threshold_sec = wan_state.get("staleness_threshold_sec", 5)
            if not isinstance(staleness_threshold_sec, (int, float)) or isinstance(
                staleness_threshold_sec, bool
            ):
                raise TypeError(
                    f"wan_state.staleness_threshold_sec must be numeric, "
                    f"got {type(staleness_threshold_sec).__name__}"
                )

            grace_period_sec = wan_state.get("grace_period_sec", 30)
            if not isinstance(grace_period_sec, (int, float)) or isinstance(
                grace_period_sec, bool
            ):
                raise TypeError(
                    f"wan_state.grace_period_sec must be numeric, "
                    f"got {type(grace_period_sec).__name__}"
                )
        except TypeError as e:
            logger.warning(f"{e}; disabling WAN awareness")
            return None

        return {
            "red_weight": red_weight,
            "staleness_threshold_sec": staleness_threshold_sec,
            "grace_period_sec": grace_period_sec,
        }

    def _build_wan_state_config(
        self, validated: dict, logger: logging.Logger
    ) -> dict:
        """Build final wan_state config dict with clamping and logging."""
        red_weight = validated["red_weight"]
        wan_override = validated["wan_override"]
        staleness_threshold_sec = validated["staleness_threshold_sec"]
        grace_period_sec = validated["grace_period_sec"]

        if red_weight < 1:
            red_weight = 1

        steer_threshold = self.data.get("confidence", {}).get("steer_threshold", 55)
        if not wan_override and red_weight >= steer_threshold:
            clamped = steer_threshold - 1
            logger.warning(
                f"red_weight clamped to {clamped} (must be < steer_threshold {steer_threshold})"
            )
            red_weight = clamped

        soft_red_weight = int(red_weight * 0.48)

        if wan_override:
            logger.warning(
                "WAN override active -- WAN RED can trigger failover independently of CAKE signals"
            )
        logger.info(
            f"WAN awareness: enabled (grace period: {grace_period_sec}s, "
            f"red_weight: {red_weight}, wan_override: {wan_override})"
        )

        return {
            "enabled": True,
            "red_weight": red_weight,
            "soft_red_weight": soft_red_weight,
            "staleness_threshold_sec": staleness_threshold_sec,
            "grace_period_sec": grace_period_sec,
            "wan_override": wan_override,
        }

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

        enabled = alerting.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"alerting.enabled must be bool, got {type(enabled).__name__}; disabling alerting"
            )
            self.alerting_config = None
            return

        if not enabled:
            self.alerting_config = None
            logger.info("Alerting: disabled (enable via alerting.enabled)")
            return

        core = self._validate_alerting_core_fields(alerting, logger)
        if core is None:
            self.alerting_config = None
            return

        delivery = self._validate_alerting_delivery(alerting, logger)
        self.alerting_config = {**core, **delivery}
        logger.info(f"Alerting: enabled ({len(core['rules'])} rules configured)")

    def _validate_alerting_core_fields(
        self, alerting: dict, logger: logging.Logger
    ) -> dict | None:
        """Validate cooldown, sustained, and rules fields. Returns dict or None."""
        default_cooldown_sec = alerting.get("default_cooldown_sec", 300)
        if not isinstance(default_cooldown_sec, int) or isinstance(default_cooldown_sec, bool):
            logger.warning(
                f"alerting.default_cooldown_sec must be int, got {type(default_cooldown_sec).__name__}; "
                "disabling alerting"
            )
            return None
        if default_cooldown_sec < 0:
            logger.warning(
                f"alerting.default_cooldown_sec must be >= 0, got {default_cooldown_sec}; "
                "disabling alerting"
            )
            return None

        rules = alerting.get("rules", {})
        if not isinstance(rules, dict):
            logger.warning(
                f"alerting.rules must be a map, got {type(rules).__name__}; disabling alerting"
            )
            return None

        if not self._validate_alerting_rules(rules, logger):
            return None

        default_sustained_sec = alerting.get("default_sustained_sec", 60)
        if not isinstance(default_sustained_sec, int) or isinstance(default_sustained_sec, bool):
            logger.warning(
                f"alerting.default_sustained_sec must be int, got {type(default_sustained_sec).__name__}; "
                "disabling alerting"
            )
            return None
        if default_sustained_sec < 0:
            logger.warning(
                f"alerting.default_sustained_sec must be >= 0, got {default_sustained_sec}; "
                "disabling alerting"
            )
            return None

        return {
            "enabled": True,
            "default_cooldown_sec": default_cooldown_sec,
            "default_sustained_sec": default_sustained_sec,
            "rules": rules,
        }

    def _validate_alerting_rules(
        self, rules: dict, logger: logging.Logger
    ) -> bool:
        """Validate each alerting rule has valid severity. Returns True if valid."""
        valid_severities = {"info", "warning", "critical"}
        for rule_name, rule in rules.items():
            if not isinstance(rule, dict):
                logger.warning(f"alerting.rules.{rule_name} must be a map; disabling alerting")
                return False
            severity = rule.get("severity")
            if severity is None:
                logger.warning(
                    f"alerting.rules.{rule_name} missing required 'severity'; disabling alerting"
                )
                return False
            if severity not in valid_severities:
                logger.warning(
                    f"alerting.rules.{rule_name}.severity must be one of {valid_severities}, "
                    f"got '{severity}'; disabling alerting"
                )
                return False
        return True

    def _validate_alerting_delivery(
        self, alerting: dict, logger: logging.Logger
    ) -> dict:
        """Validate and extract webhook delivery config fields."""
        webhook_url = alerting.get("webhook_url", "")
        # Expand ${ENV_VAR} references (same pattern as router password)
        if (
            webhook_url
            and isinstance(webhook_url, str)
            and webhook_url.startswith("${")
            and webhook_url.endswith("}")
        ):
            env_var = webhook_url[2:-1]
            webhook_url = os.environ.get(env_var, "")

        mention_role_id = alerting.get("mention_role_id")
        if mention_role_id is not None and not isinstance(mention_role_id, str):
            logger.warning("alerting.mention_role_id must be string; ignoring")
            mention_role_id = None

        mention_severity = alerting.get("mention_severity", "critical")
        if mention_severity not in ("info", "recovery", "warning", "critical"):
            logger.warning(
                f"alerting.mention_severity invalid: '{mention_severity}'; defaulting to critical"
            )
            mention_severity = "critical"

        max_webhooks_per_minute = alerting.get("max_webhooks_per_minute", 20)
        if not isinstance(max_webhooks_per_minute, int) or max_webhooks_per_minute <= 0:
            logger.warning("alerting.max_webhooks_per_minute invalid; defaulting to 20")
            max_webhooks_per_minute = 20

        return {
            "webhook_url": webhook_url,
            "mention_role_id": mention_role_id,
            "mention_severity": mention_severity,
            "max_webhooks_per_minute": max_webhooks_per_minute,
        }

    def _load_thresholds(self) -> None:
        """Load state machine thresholds with EWMA alpha validation (C5 fix)."""
        thresholds = self.data["thresholds"]

        # CAKE thresholds (three-state congestion model)
        self.green_rtt_ms = thresholds.get("green_rtt_ms", DEFAULT_GREEN_RTT_MS)
        self.yellow_rtt_ms = thresholds.get("yellow_rtt_ms", DEFAULT_YELLOW_RTT_MS)
        self.red_rtt_ms = thresholds.get("red_rtt_ms", DEFAULT_RED_RTT_MS)
        self.min_drops_red = thresholds.get("min_drops_red", 1)
        self.min_queue_yellow = thresholds.get("min_queue_yellow", DEFAULT_MIN_QUEUE_YELLOW)
        self.min_queue_red = thresholds.get("min_queue_red", DEFAULT_MIN_QUEUE_RED)
        # C5 fix: Validate EWMA alpha bounds during config load
        self.rtt_ewma_alpha = validate_alpha(
            thresholds.get("rtt_ewma_alpha", DEFAULT_RTT_EWMA_ALPHA),
            "thresholds.rtt_ewma_alpha",
            logger=logging.getLogger(__name__),
        )
        self.queue_ewma_alpha = validate_alpha(
            thresholds.get("queue_ewma_alpha", DEFAULT_QUEUE_EWMA_ALPHA),
            "thresholds.queue_ewma_alpha",
            logger=logging.getLogger(__name__),
        )
        self.red_samples_required = thresholds.get("red_samples_required", 2)
        self.green_samples_required = thresholds.get(
            "green_samples_required", DEFAULT_GREEN_SAMPLES_REQUIRED
        )

    def _load_baseline_bounds(self) -> None:
        """Load baseline RTT bounds (C4 fix: configurable with security defaults)."""
        baseline_bounds = self.data["thresholds"].get("baseline_rtt_bounds", {})
        self.baseline_rtt_min = baseline_bounds.get("min", MIN_SANE_BASELINE_RTT)
        self.baseline_rtt_max = baseline_bounds.get("max", MAX_SANE_BASELINE_RTT)

    def _load_state_persistence(self) -> None:
        """Load state persistence settings."""
        self.state_file = Path(self.data["state"]["file"])
        self.history_size = self.data["state"]["history_size"]

    def _load_timeouts(self) -> None:
        """Load timeout settings with sensible defaults."""
        timeouts = self.data.get("timeouts", {})
        self.timeout_ssh_command = timeouts.get("ssh_command", DEFAULT_STEERING_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get("ping", 2)  # seconds (-W parameter)

    def _build_router_dict(self) -> None:
        """Build router dict for CakeStatsReader."""
        self.router = {
            "host": self.router_host,
            "user": self.router_user,
            "ssh_key": self.ssh_key,
            "transport": self.router_transport,
            # Keep compatibility shape without retaining a second plaintext secret copy.
            "password": "",
            "port": self.router_port,
            "verify_ssl": self.router_verify_ssl,
        }

    def _load_metrics_config(self) -> None:
        """Load metrics configuration (optional, disabled by default)."""
        metrics_config = self.data.get("metrics", {})
        self.metrics_enabled = metrics_config.get("enabled", False)

    def _load_health_check_config(self) -> None:
        """Load health check settings with defaults."""
        health = self.data.get("health_check", {})
        self.health_check_enabled = health.get("enabled", True)
        self.health_check_host = health.get("host", "127.0.0.1")
        self.health_check_port = health.get("port", 9102)

    def _load_specific_fields(self) -> None:
        """Load steering daemon-specific configuration fields.

        Orchestrates loading of all steering-specific config by calling
        focused helper methods in dependency order.
        """
        # Connection and topology
        self._load_router_transport()
        self._load_topology()
        self._load_state_sources()
        self._load_mangle_config()

        # Measurement and CAKE
        self._load_rtt_measurement()
        self._load_cake_queues()  # Depends on _load_topology for primary_wan
        self._load_operational_mode()
        self._load_confidence_config()  # Depends on _load_operational_mode for use_confidence_scoring
        self._load_wan_state_config()  # Depends on confidence for steer_threshold

        # Thresholds and bounds
        self._load_thresholds()
        self._load_baseline_bounds()

        # Persistence and operational
        self._load_state_persistence()
        # Steering-specific log setting (common logging loaded by BaseConfig)
        self.log_cake_stats = self.data.get("logging", {}).get("log_cake_stats", True)
        self._load_timeouts()

        # Router dict, metrics, and health check
        self._build_router_dict()  # Depends on router fields from _load_router_transport
        self._load_metrics_config()
        self._load_health_check_config()

        # Alerting (optional, disabled by default per INFRA-05)
        self._load_alerting_config()


# =============================================================================
# STATE MANAGEMENT
# =============================================================================


def create_steering_state_schema(config: SteeringConfig) -> StateSchema:
    """Create a StateSchema for steering daemon state.

    Defines all steering state fields with defaults based on config.

    Args:
        config: SteeringConfig instance

    Returns:
        StateSchema configured for steering state
    """
    return StateSchema(
        {
            "current_state": config.state_good,
            "good_count": 0,
            "baseline_rtt": None,
            "history_rtt": [],
            "history_delta": [],
            "transitions": [],
            "last_transition_time": None,
            "rtt_delta_ewma": 0.0,
            "queue_ewma": 0.0,
            "cake_drops_history": [],
            "queue_depth_history": [],
            "cake_state_history": [],  # For confidence-based steering
            "red_count": 0,
            "congestion_state": "GREEN",
            "cake_read_failures": 0,
        }
    )


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================


class RouterOSController:
    """RouterOS interface to toggle steering rule (supports SSH and REST)

    PROTECTED: Security C2 (command injection prevention) + Reliability W6 (retry with verification).
    See docs/CORE-ALGORITHM-ANALYSIS.md.
    """

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.client = get_router_client_with_failover(config, logger)

    def get_rule_status(self) -> bool | None:
        """
        Check if adaptive steering rule is enabled
        Returns: True if enabled, False if disabled, None on error
        """
        rc, out, _ = self.client.run_cmd(
            f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"',
            capture=True,
            timeout=5,  # Fast query operation
        )

        if rc != 0:
            self.logger.error("Failed to read mangle rule status")
            return None

        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, list):
            for item in parsed:
                if item.get("comment") == self.config.mangle_rule_comment:
                    return item.get("disabled") != "true"
            self.logger.error(f"Could not find ADAPTIVE rule in output: {out[:200]}")
            return None

        # Parse output - look for X flag in rule line (not in Flags legend)
        # Disabled rule: " 4 X  ;;; comment"
        # Enabled rule:  " 4    ;;; comment"
        lines = out.split("\n")
        for line in lines:
            if "ADAPTIVE" in line and ";;;" in line:
                # Found the rule line - check for X flag between number and comment
                # Split on ;;; to get the prefix part with flags
                prefix = line.split(";;;")[0] if ";;;" in line else line
                # Check if X appears in the prefix (after rule number)
                if " X " in prefix or "\tX\t" in prefix or "\tX " in prefix or " X\t" in prefix:
                    self.logger.debug(f"Rule is DISABLED: {line[:60]}")
                    return False
                self.logger.debug(f"Rule is ENABLED: {line[:60]}")
                return True

        self.logger.error(f"Could not find ADAPTIVE rule in output: {out[:200]}")
        return None

    def enable_steering(self) -> bool:
        """Enable adaptive steering rule (route latency-sensitive traffic to alternate WAN)"""
        self.logger.info(f"Enabling steering rule: {self.config.mangle_rule_comment}")

        rc, _, _ = self.client.run_cmd(
            f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]',
            timeout=10,  # State change operation
        )

        if rc != 0:
            self.logger.error("Failed to enable steering rule")
            return False

        # Verify with retry (W6 fix: handle RouterOS processing delay)
        if verify_with_retry(
            self.get_rule_status,
            expected_result=True,
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0,
            logger=self.logger,
            operation_name="steering rule enable verification",
        ):
            self.logger.info("Steering rule enabled and verified")
            return True
        self.logger.error("Steering rule enable verification failed after retries")
        return False

    def disable_steering(self) -> bool:
        """Disable adaptive steering rule (all traffic uses default routing)"""
        self.logger.info(f"Disabling steering rule: {self.config.mangle_rule_comment}")

        rc, _, _ = self.client.run_cmd(
            f'/ip firewall mangle disable [find comment~"{self.config.mangle_rule_comment}"]',
            timeout=10,  # State change operation
        )

        if rc != 0:
            self.logger.error("Failed to disable steering rule")
            return False

        # Verify with retry (W6 fix: handle RouterOS processing delay)
        if verify_with_retry(
            self.get_rule_status,
            expected_result=False,
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0,
            logger=self.logger,
            operation_name="steering rule disable verification",
        ):
            self.logger.info("Steering rule disabled and verified")
            return True
        self.logger.error("Steering rule disable verification failed after retries")
        return False


# Note: RTTMeasurement class is now unified in rtt_measurement.py
# This module imports it from there


# =============================================================================
# BASELINE RTT LOADER
# =============================================================================

STALE_BASELINE_THRESHOLD_SECONDS = 300
STALE_WAN_ZONE_THRESHOLD_SECONDS = 5


class BaselineLoader:
    """Load baseline RTT from autorate state file"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._stale_baseline_warned = False
        self._wan_staleness_threshold = STALE_WAN_ZONE_THRESHOLD_SECONDS

    def load_baseline_rtt(self) -> tuple[float | None, str | None]:
        """
        Load baseline RTT and WAN congestion zone from primary WAN autorate state file.

        Reads ewma.baseline_rtt and congestion.dl_state from autorate_continuous state.
        Returns (None, None) if unavailable (daemon will use config fallback).
        WAN zone defaults to GREEN if state file is stale (>5s) per SAFE-01.
        Warns (rate-limited) if state file is stale (>5 minutes old).

        Returns:
            tuple of (baseline_rtt, wan_zone):
                - baseline_rtt: float or None if unavailable/invalid
                - wan_zone: congestion zone str or None if congestion key missing
        """
        state = safe_json_load_file(
            self.config.primary_state_file,
            logger=self.logger,
            error_context="autorate state",
        )

        if state is None:
            return None, None

        # STEER-03: Check file staleness before parsing
        self._check_staleness()

        # FUSE-01: Extract WAN zone from same dict (zero additional I/O)
        if self.is_wan_zone_stale():
            wan_zone: str | None = "GREEN"  # SAFE-01: stale defaults to GREEN
        else:
            wan_zone = state.get("congestion", {}).get("dl_state", None)

        # autorate_continuous format: state['ewma']['baseline_rtt']
        if "ewma" in state and "baseline_rtt" in state["ewma"]:
            try:
                baseline_rtt = float(state["ewma"]["baseline_rtt"])
            except (ValueError, TypeError) as e:
                self.logger.error(f"Invalid baseline_rtt value: {e}")
                return None, wan_zone

            # PROTECTED: Security fix C4 - bounds baseline to 10-60ms to prevent malicious state file attacks.
            # Sanity check using configured bounds (C4 fix: prevents malicious baseline attacks)
            # Default range: 10-60ms (typical home ISP latencies)
            if self.config.baseline_rtt_min <= baseline_rtt <= self.config.baseline_rtt_max:
                self.logger.debug(f"Loaded baseline RTT from autorate state: {baseline_rtt:.2f}ms")
                return baseline_rtt, wan_zone
            self.logger.warning(
                f"Baseline RTT out of bounds [{self.config.baseline_rtt_min:.1f}-{self.config.baseline_rtt_max:.1f}ms]: "
                f"{baseline_rtt:.2f}ms, ignoring (possible autorate compromise)"
            )
            return None, wan_zone
        self.logger.warning("Baseline RTT not found in autorate state file")
        return None, wan_zone

    def get_wan_zone_age(self) -> float | None:
        """Get age of autorate state file in seconds.

        Returns:
            File age in seconds, or None if file is inaccessible.
        """
        try:
            return time.time() - self.config.primary_state_file.stat().st_mtime
        except OSError:
            return None

    def is_wan_zone_stale(self) -> bool:
        """Check if autorate state file is too old for WAN zone to be trusted."""
        try:
            file_age = time.time() - self.config.primary_state_file.stat().st_mtime
        except OSError:
            return True  # Cannot stat = treat as stale (fail-safe)
        return file_age > self._wan_staleness_threshold

    def _check_staleness(self) -> None:
        """Check if autorate state file is stale and warn (rate-limited)."""
        try:
            file_age = time.time() - self.config.primary_state_file.stat().st_mtime
        except OSError:
            return

        if file_age > STALE_BASELINE_THRESHOLD_SECONDS:
            if not self._stale_baseline_warned:
                self.logger.warning(
                    f"Autorate state file is {file_age:.0f}s old "
                    f"(threshold: {STALE_BASELINE_THRESHOLD_SECONDS}s), "
                    f"baseline RTT may be stale"
                )
                self._stale_baseline_warned = True
        else:
            # File is fresh -- reset the warning flag
            self._stale_baseline_warned = False


# =============================================================================
# STEERING DAEMON
# =============================================================================


class SteeringDaemon:
    """Main steering daemon logic with state machine"""

    def __init__(
        self,
        config: SteeringConfig,
        state: SteeringStateManager,
        router: RouterOSController,
        rtt_measurement: RTTMeasurement,
        baseline_loader: BaselineLoader,
        logger: logging.Logger,
    ):
        self.config = config
        self.state_mgr = state
        self.router = router
        self.rtt_measurement = rtt_measurement
        self.baseline_loader = baseline_loader
        self.logger = logger

        # Router connectivity tracking for cycle-level failure detection
        self.router_connectivity = RouterConnectivityState(self.logger)

        self._init_cake_reader(config)
        self._init_steering_metrics(config)
        self._init_steering_alerting()
        self._init_confidence_controller()
        self._init_steering_profiling(config)
        self._init_wan_awareness()

        # STEER-01: Track which legacy state names have already been warned about
        # to avoid log flooding at 20Hz cycle rate (log-once per name per lifetime)
        self._legacy_state_warned: set[str] = set()

    def _init_cake_reader(self, config: SteeringConfig) -> None:
        """Initialize CAKE congestion detection components."""
        self.cake_reader = CakeStatsReader(config, self.logger)
        self.thresholds = StateThresholds(
            green_rtt=config.green_rtt_ms,
            yellow_rtt=config.yellow_rtt_ms,
            red_rtt=config.red_rtt_ms,
            min_drops_red=config.min_drops_red,
            min_queue_yellow=config.min_queue_yellow,
            min_queue_red=config.min_queue_red,
            red_samples_required=config.red_samples_required,
            green_samples_required=config.green_samples_required,
        )
        self.logger.info("CAKE three-state congestion model initialized")

    def _init_steering_metrics(self, config: SteeringConfig) -> None:
        """Initialize metrics history storage (optional)."""
        storage_config = get_storage_config(config.data)
        self._metrics_writer: MetricsWriter | None = None
        self._storage_db_path: str | None = None
        db_path = storage_config.get("db_path")
        if db_path and isinstance(db_path, str):
            self._storage_db_path = db_path
            self._metrics_writer = MetricsWriter(Path(db_path))
            self._metrics_writer.set_process_role("steering")
            self.logger.info(f"Metrics storage enabled: {db_path}")

    def _init_steering_alerting(self) -> None:
        """Initialize alert engine and webhook delivery."""
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
                    "alerting.webhook_url not set; alerts will fire and persist but not deliver"
                )

            from wanctl import __version__
            from wanctl.webhook_delivery import DiscordFormatter, WebhookDelivery

            formatter = DiscordFormatter(version=__version__, container_id=self.config.wan_name)
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

        # Steering activation timestamp for duration tracking (ALRT-02/ALRT-03)
        self._steering_activated_time: float | None = None

    def _init_confidence_controller(self) -> None:
        """Initialize confidence-based steering controller (if enabled)."""
        self.confidence_controller: ConfidenceController | None = None
        if self.config.use_confidence_scoring and self.config.confidence_config:
            self.confidence_controller = ConfidenceController(
                config_v3=self.config.confidence_config,
                logger=self.logger,
                state_good=self.config.state_good,
                state_degraded=self.config.state_degraded,
                cycle_interval=ASSESSMENT_INTERVAL_SECONDS,
            )
            dry_run_status = self.config.confidence_config["dry_run"]["enabled"]
            self.logger.info(f"[CONFIDENCE] Confidence scoring enabled (dry_run={dry_run_status})")

    def _init_steering_profiling(self, config: SteeringConfig) -> None:
        """Initialize per-subsystem timing for cycle budget analysis."""
        self._profiler = OperationProfiler(max_samples=1200)
        self._profile_cycle_count = 0
        self._profiling_enabled = False
        self._overrun_count = 0
        self._cycle_interval_ms = config.measurement_interval * 1000.0

    def _init_wan_awareness(self) -> None:
        """Initialize WAN congestion zone tracking and awareness gating."""
        # WAN congestion zone from autorate state (FUSE-01)
        self._wan_zone: str | None = None

        # WAN awareness gating (SAFE-03, SAFE-04)
        self._startup_time = time.monotonic()
        wsc = self.config.wan_state_config
        self._wan_state_enabled = bool(wsc and wsc.get("enabled", False))
        self._wan_grace_period_sec = wsc["grace_period_sec"] if wsc else 30.0
        self._wan_red_weight: int | None = wsc["red_weight"] if wsc else None
        self._wan_soft_red_weight: int | None = wsc["soft_red_weight"] if wsc else None
        self._wan_staleness_sec: float = (
            wsc["staleness_threshold_sec"] if wsc else STALE_WAN_ZONE_THRESHOLD_SECONDS
        )

        # Override BaselineLoader staleness threshold with config value
        if hasattr(self.baseline_loader, "_wan_staleness_threshold"):
            self.baseline_loader._wan_staleness_threshold = self._wan_staleness_sec

    def _reload_dry_run_config(self) -> None:
        """Re-read dry_run flag from config YAML file (triggered by SIGUSR1).

        Only reloads the confidence.dry_run field. All other config values
        remain unchanged (require full restart to modify).
        """
        if self.confidence_controller is None:
            self.logger.info("[CONFIDENCE] Config reload: no-op (confidence scoring not enabled)")
            return

        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[CONFIDENCE] Config reload failed: {e}")
            return

        new_dry_run = fresh_data.get("confidence", {}).get("dry_run", True)
        # confidence_controller is not None (guarded above), so confidence_config is set
        assert self.config.confidence_config is not None
        old_dry_run = self.config.confidence_config["dry_run"]["enabled"]

        if new_dry_run == old_dry_run:
            self.logger.warning(f"[CONFIDENCE] Config reload: dry_run={old_dry_run} (unchanged)")
            return

        # Update both the config dict and the controller instance
        self.config.confidence_config["dry_run"]["enabled"] = new_dry_run
        self.confidence_controller.dry_run.enabled = new_dry_run

        mode_str = "DRY-RUN (log-only)" if new_dry_run else "LIVE (routing active)"
        self.logger.warning(
            f"[CONFIDENCE] Config reload: dry_run={old_dry_run}->{new_dry_run} mode={mode_str}"
        )

    def _reload_wan_state_config(self) -> None:
        """Re-read wan_state.enabled from config YAML file (triggered by SIGUSR1).

        Only reloads the wan_state.enabled field. All other wan_state values
        remain unchanged (require full restart to modify).

        If transitioning false->true, resets _startup_time to re-trigger the
        grace period (safe ramp-up after re-enable).
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[WAN_STATE] Config reload failed: {e}")
            return

        wan_state_section = fresh_data.get("wan_state") if fresh_data else None
        if wan_state_section is None:
            self.logger.info("[WAN_STATE] Config reload: no wan_state section in YAML (no-op)")
            return

        new_enabled = bool(wan_state_section.get("enabled", False))
        old_enabled = self._wan_state_enabled

        if new_enabled == old_enabled:
            self.logger.warning(f"[WAN_STATE] Config reload: enabled={old_enabled} (unchanged)")
            return

        self._wan_state_enabled = new_enabled

        # Re-trigger grace period when re-enabling (safe ramp-up)
        if new_enabled and not old_enabled:
            self._startup_time = time.monotonic()
            self.logger.warning(
                f"[WAN_STATE] Config reload: enabled={old_enabled}->{new_enabled} "
                f"(grace period re-triggered: {self._wan_grace_period_sec}s)"
            )
        else:
            self.logger.warning(f"[WAN_STATE] Config reload: enabled={old_enabled}->{new_enabled}")

    def _reload_webhook_url_config(self) -> None:
        """Re-read alerting.webhook_url from config YAML (triggered by SIGUSR1)."""
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                data = yaml.safe_load(f) or {}
            alerting = data.get("alerting", {})
            new_url = alerting.get("webhook_url", "")
            # Expand ${ENV_VAR} references
            if (
                new_url
                and isinstance(new_url, str)
                and new_url.startswith("${")
                and new_url.endswith("}")
            ):
                env_var = new_url[2:-1]
                new_url = os.environ.get(env_var, "")
            if self._webhook_delivery is not None:
                self._webhook_delivery.update_webhook_url(new_url)
                self.logger.info(
                    "[ALERTING] Webhook URL reloaded: %s",
                    "set" if new_url else "empty",
                )
        except Exception:
            self.logger.warning("Failed to reload webhook_url config", exc_info=True)

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    def get_health_data(self) -> dict[str, Any]:
        """Return all health-relevant data for the steering health endpoint.

        Mirrors WANController.get_health_data() pattern (D-10).
        Replaces ~15 cross-module private attribute accesses from steering/health.py.
        """
        wan_awareness: dict[str, Any] = {
            "enabled": self._wan_state_enabled,
        }
        if self._wan_state_enabled:
            wan_awareness["zone"] = self._wan_zone
            wan_awareness["effective_zone"] = self.get_effective_wan_zone()
            wan_awareness["grace_period_active"] = self.is_wan_grace_period_active()
            wan_awareness["zone_age"] = self.baseline_loader.get_wan_zone_age()
            wan_awareness["stale"] = self.baseline_loader.is_wan_zone_stale()
            wan_awareness["red_weight"] = self._wan_red_weight
            wan_awareness["soft_red_weight"] = self._wan_soft_red_weight
        else:
            # Disabled mode: include raw zone for staged rollout verification
            wan_awareness["zone"] = self._wan_zone

        storage_snapshot = get_storage_metrics_snapshot("steering")
        storage_files = get_storage_file_snapshot(self._storage_db_path)
        rss_bytes, swap_bytes = read_process_memory_status()
        return {
            "cycle_budget": {
                "profiler": self._profiler,
                "overrun_count": self._overrun_count,
                "cycle_interval_ms": self._cycle_interval_ms,
            },
            "wan_awareness": wan_awareness,
            "runtime": {
                "process": "steering",
                "rss_bytes": rss_bytes,
                "swap_bytes": swap_bytes,
            },
            "storage": storage_snapshot,
            "storage_files": storage_files,
        }

    def _is_current_state_good(self, current_state: str) -> bool:
        """Check if current state represents 'good' (supports both legacy and config-driven names).

        Args:
            current_state: The current state string to check

        Returns:
            True if state is "good", False otherwise
        """
        if current_state == self.config.state_good:
            return True

        # STEER-01: Legacy state name detection with rate-limited warning
        legacy_names = ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD")
        if current_state in legacy_names:
            if current_state not in self._legacy_state_warned:
                self.logger.warning(
                    f"Legacy state name '{current_state}' detected, "
                    f"normalized to '{self.config.state_good}'"
                )
                self._legacy_state_warned.add(current_state)
            return True

        return False

    def is_wan_grace_period_active(self) -> bool:
        """Check if startup grace period for WAN awareness is still active."""
        return (time.monotonic() - self._startup_time) < self._wan_grace_period_sec

    def get_effective_wan_zone(self) -> str | None:
        """Get WAN zone for confidence scoring, applying enabled and grace gates.

        Returns None (no WAN contribution) when:
        - WAN awareness is disabled (wan_state_config is None or enabled=False)
        - Grace period is still active (first N seconds after startup)

        Otherwise returns the actual WAN zone from autorate state.
        """
        if not self._wan_state_enabled:
            return None
        if self.is_wan_grace_period_active():
            return None
        return self._wan_zone

    def _evaluate_degradation_condition(
        self, signals: CongestionSignals
    ) -> tuple[bool, bool, bool, str]:
        """
        Evaluate degradation/recovery conditions using CAKE congestion assessment.

        Uses assess_congestion_state() with multi-signal analysis (RTT delta,
        CAKE drops, queue depth) to determine RED/YELLOW/GREEN state.

        Args:
            signals: CongestionSignals containing rtt_delta and other metrics

        Returns:
            tuple[bool, bool, bool, str]: (is_degraded, is_recovered, is_warning, assessment_value)
            - is_degraded: True if RED state (confirmed congestion)
            - is_recovered: True if GREEN state (healthy)
            - is_warning: True if YELLOW state (early warning, resets degrade counter)
            - assessment_value: CongestionState.value (RED/YELLOW/GREEN)
        """
        assessment = assess_congestion_state(signals, self.thresholds, self.logger)
        return (
            assessment == CongestionState.RED,
            assessment == CongestionState.GREEN,
            assessment == CongestionState.YELLOW,
            assessment.value,
        )

    def execute_steering_transition(
        self, from_state: str, to_state: str, enable_steering: bool
    ) -> bool:
        """Execute steering state transition with routing control.

        Handles router enable/disable, transition logging, state update,
        metrics recording, and router connectivity tracking.

        Args:
            from_state: Current state name
            to_state: Target state name
            enable_steering: True to enable steering (degrade), False to disable (recover)

        Returns:
            True if transition succeeded, False if routing failed
        """
        # Execute routing change with connectivity tracking
        try:
            if enable_steering:
                if not self.router.enable_steering():
                    self.router_connectivity.record_failure(
                        ConnectionError("Failed to enable steering rule")
                    )
                    self.logger.error(f"Failed to enable steering, staying in {from_state}")
                    return False
            else:
                if not self.router.disable_steering():
                    self.router_connectivity.record_failure(
                        ConnectionError("Failed to disable steering rule")
                    )
                    self.logger.error(f"Failed to disable steering, staying in {from_state}")
                    return False
            # Successful router operation
            self.router_connectivity.record_success()
        except Exception as e:
            # Unexpected exception during router communication
            failure_type = self.router_connectivity.record_failure(e)
            failures = self.router_connectivity.consecutive_failures
            if failures == 1 or failures == 3 or failures % 10 == 0:
                self.logger.warning(
                    f"Router communication failed during steering transition ({failure_type}, "
                    f"{failures} consecutive)"
                )
            return False

        # Log transition and update state
        self.state_mgr.log_transition(from_state, to_state)
        self.state_mgr.state["current_state"] = to_state

        # OBSV-03: Log WAN context when WAN contributed to this decision
        if self.confidence_controller:
            contributors = self.confidence_controller.timer_state.confidence_contributors
            wan_contributors = [c for c in contributors if c.startswith("WAN_")]
            if wan_contributors:
                wan_str = ", ".join(wan_contributors)
                self.logger.info(
                    f"[STEERING] Transition {from_state} -> {to_state} with WAN signal: [{wan_str}]"
                )

        # Record metrics if enabled (Prometheus)
        if self.config.metrics_enabled:
            record_steering_transition(self.config.primary_wan, from_state, to_state)

        # Record transition to SQLite history (if storage enabled)
        if self._metrics_writer is not None:
            ts = int(time.time())
            reason = f"Transitioned from {from_state} to {to_state}"
            self._metrics_writer.write_metric(
                timestamp=ts,
                wan_name=self.config.primary_wan,
                metric_name="wanctl_steering_transition",
                value=1.0 if enable_steering else 0.0,
                labels={"reason": reason, "from_state": from_state, "to_state": to_state},
                granularity="raw",
            )

        return True

    def _handle_good_state(
        self,
        signals: CongestionSignals,
        is_degraded: bool,
        is_warning: bool,
        assessment: str | None,
        degrade_count: int,
        degrade_threshold: int,
    ) -> tuple[int, bool]:
        """Handle state machine logic when in GOOD state.

        Returns:
            (new_degrade_count, state_changed)
        """
        wan = self.config.primary_wan.upper()
        state_changed = False

        if is_degraded:
            degrade_count += 1
            self.logger.info(
                f"[{wan}_GOOD] [{assessment}] {signals} | "
                f"red_count={degrade_count}/{degrade_threshold}"
            )

            if degrade_count >= degrade_threshold:
                self.logger.warning(
                    f"{wan} DEGRADED detected - {signals} (sustained {degrade_count} samples)"
                )
                if self.execute_steering_transition(
                    self.config.state_good, self.config.state_degraded, enable_steering=True
                ):
                    degrade_count = 0
                    state_changed = True

                    # Fire steering_activated alert (ALRT-02)
                    details: dict[str, object] = {
                        "from_state": self.config.state_good,
                        "to_state": self.config.state_degraded,
                        "rtt_delta": signals.rtt_delta,
                        "cake_drops": signals.cake_drops,
                        "queue_depth": signals.queued_packets,
                    }
                    if self.confidence_controller:
                        details["confidence_score"] = (
                            self.confidence_controller.timer_state.confidence_score
                        )
                    self.alert_engine.fire(
                        "steering_activated", "warning", self.config.primary_wan, details
                    )
                    self._steering_activated_time = time.monotonic()

        elif is_warning:
            degrade_count = 0
            self.logger.info(f"[{wan}_GOOD] [{assessment}] {signals} | early warning, no action")
        else:
            degrade_count = 0
            self.logger.debug(f"[{wan}_GOOD] [{assessment}] {signals}")

        return degrade_count, state_changed

    def _handle_degraded_state(
        self,
        signals: CongestionSignals,
        is_recovered: bool,
        assessment: str | None,
        recover_count: int,
        recover_threshold: int,
    ) -> tuple[int, bool]:
        """Handle state machine logic when in DEGRADED state.

        Returns:
            (new_recover_count, state_changed)
        """
        wan = self.config.primary_wan.upper()
        state_changed = False

        if is_recovered:
            recover_count += 1
            self.logger.info(
                f"[{wan}_DEGRADED] [{assessment}] {signals} | "
                f"good_count={recover_count}/{recover_threshold}"
            )

            if recover_count >= recover_threshold:
                self.logger.info(f"{wan} RECOVERED - {signals} (sustained {recover_count} samples)")
                if self.execute_steering_transition(
                    self.config.state_degraded, self.config.state_good, enable_steering=False
                ):
                    recover_count = 0
                    state_changed = True

                    # Fire steering_recovered alert (ALRT-03)
                    duration_sec: float | None = None
                    if self._steering_activated_time is not None:
                        duration_sec = round(time.monotonic() - self._steering_activated_time, 1)
                    recovery_details: dict[str, object] = {
                        "from_state": self.config.state_degraded,
                        "to_state": self.config.state_good,
                        "duration_sec": duration_sec,
                    }
                    self.alert_engine.fire(
                        "steering_recovered",
                        "recovery",
                        self.config.primary_wan,
                        recovery_details,
                    )
                    self._steering_activated_time = None
        else:
            recover_count = 0
            self.logger.info(f"[{wan}_DEGRADED] [{assessment}] {signals} | still degraded")

        return recover_count, state_changed

    def _update_state_machine_unified(self, signals: CongestionSignals) -> bool:
        """
        Hysteresis state machine for CAKE congestion-based steering.

        PROTECTED: Asymmetric hysteresis - quick to enable, slow to disable.
        Do not change thresholds without production validation.
        See docs/CORE-ALGORITHM-ANALYSIS.md.
        """
        state = self.state_mgr.state
        current_state = state["current_state"]

        # Evaluate congestion conditions
        is_degraded, is_recovered, is_warning, assessment = self._evaluate_degradation_condition(
            signals
        )

        # Store assessment for observability
        state["congestion_state"] = assessment

        # Get counters
        degrade_count = state["red_count"]
        degrade_threshold = self.thresholds.red_samples_required
        recover_threshold = self.thresholds.green_samples_required
        recover_count = state["good_count"]

        # Dispatch to state handler
        is_good = self._is_current_state_good(current_state)
        if is_good:
            if current_state != self.config.state_good:
                state["current_state"] = self.config.state_good
            degrade_count, state_changed = self._handle_good_state(
                signals, is_degraded, is_warning, assessment, degrade_count, degrade_threshold
            )
            recover_count = 0
        else:
            if current_state != self.config.state_degraded:
                state["current_state"] = self.config.state_degraded
            recover_count, state_changed = self._handle_degraded_state(
                signals, is_recovered, assessment, recover_count, recover_threshold
            )
            degrade_count = 0

        # Persist counters
        state["red_count"] = degrade_count
        state["good_count"] = recover_count

        return state_changed

    def measure_current_rtt(self) -> float | None:
        """Measure current RTT to ping host"""
        return self.rtt_measurement.ping_host(self.config.ping_host, self.config.ping_count)

    def _measure_current_rtt_with_retry(self, max_retries: int = 3) -> float | None:
        """
        Measure current RTT with retry and fallback to history (W7 fix)

        Uses measure_with_retry() utility with fallback to last known RTT from state.

        Args:
            max_retries: Maximum ping attempts

        Returns:
            Current RTT or None if all retries fail and no fallback available
        """

        def fallback_to_history() -> float | None:
            """Fallback to historical RTT data when current measurement fails.

            Uses moving average of last N RTT values as fallback when ping fails.
            Prevents steering disruption during transient measurement failures.

            This is a private implementation detail for measurement resilience (W7 fix).
            Returns the most recent RTT from state history if available.

            Returns:
                float | None: Historical RTT average in ms, or None if no history available
            """
            state = self.state_mgr.state
            if state.get("history_rtt") and len(state["history_rtt"]) > 0:
                last_rtt = state["history_rtt"][-1]
                self.logger.warning(
                    f"Using last known RTT from state: {last_rtt:.1f}ms "
                    f"(ping to {self.config.ping_host} failed after retries)"
                )
                return last_rtt  # type: ignore[no-any-return]
            self.logger.error("No ping response and no RTT history available - cannot proceed")
            return None

        return measure_with_retry(  # type: ignore[no-any-return]
            self.measure_current_rtt,
            max_retries=max_retries,
            retry_delay=0.5,
            fallback_func=fallback_to_history,
            logger=self.logger,
            operation_name="ping",
        )

    def update_baseline_rtt(self) -> bool:
        """
        Update baseline RTT and WAN zone from autorate state.
        Returns True if successful, False otherwise.
        """
        baseline_rtt, wan_zone = self.baseline_loader.load_baseline_rtt()
        self._wan_zone = wan_zone  # Store for use in update_state_machine

        if baseline_rtt is not None:
            old_baseline = self.state_mgr.state["baseline_rtt"]
            self.state_mgr.state["baseline_rtt"] = baseline_rtt

            if old_baseline is None:
                self.logger.info(f"Initialized baseline RTT: {baseline_rtt:.2f}ms")
            elif abs(baseline_rtt - old_baseline) > BASELINE_CHANGE_THRESHOLD:
                self.logger.info(
                    f"Baseline RTT updated: {old_baseline:.2f}ms -> {baseline_rtt:.2f}ms"
                )

            return True
        if self.state_mgr.state["baseline_rtt"] is None:
            self.logger.warning("No baseline RTT available, cannot make steering decisions")
            return False
        self.logger.debug("Using cached baseline RTT")
        return True

    def calculate_delta(self, current_rtt: float) -> float:
        """Calculate RTT delta (current - baseline)"""
        baseline_rtt = self.state_mgr.state["baseline_rtt"]
        if baseline_rtt is None:
            return 0.0

        delta = current_rtt - baseline_rtt
        return max(0.0, delta)  # type: ignore[no-any-return]  # Never negative

    def _apply_confidence_decision(self, decision: str) -> bool:
        """Apply a confidence controller steering decision.

        Args:
            decision: "ENABLE_STEERING" or "DISABLE_STEERING"

        Returns:
            True if routing state changed, False if routing failed
        """
        state = self.state_mgr.state
        current_state = state["current_state"]

        if decision == "ENABLE_STEERING":
            return self.execute_steering_transition(
                current_state, self.config.state_degraded, enable_steering=True
            )
        if decision == "DISABLE_STEERING":
            return self.execute_steering_transition(
                current_state, self.config.state_good, enable_steering=False
            )
        return False

    def update_state_machine(self, signals: CongestionSignals) -> bool:
        """
        Update state machine based on congestion signals.

        If confidence scoring is enabled:
        - Evaluates ConfidenceController in parallel with hysteresis
        - In dry-run mode: logs confidence decisions but uses hysteresis for routing
        - In live mode: uses confidence decision for routing

        Falls through to hysteresis state machine when confidence scoring is
        disabled or in dry-run mode.

        Args:
            signals: CongestionSignals containing rtt_delta, drops, queue depth, etc.

        Returns:
            True if routing state changed, False otherwise
        """
        # If confidence controller enabled, evaluate in parallel
        if self.confidence_controller:
            state = self.state_mgr.state

            # Convert CongestionSignals to ConfidenceSignals format
            phase2b_signals = ConfidenceSignals(
                cake_state=state.get("congestion_state", "GREEN"),
                rtt_delta_ms=signals.rtt_delta,
                drops_per_sec=float(signals.cake_drops),
                queue_depth_pct=float(signals.queued_packets),  # Simplified (packets not %)
                cake_state_history=list(state.get("cake_state_history", [])),
                drops_history=list(state.get("cake_drops_history", [])),
                queue_history=list(state.get("queue_depth_history", [])),
                wan_zone=self.get_effective_wan_zone(),
            )

            # Evaluate confidence (returns decision or None if dry-run)
            confidence_decision = self.confidence_controller.evaluate(
                phase2b_signals,
                state["current_state"],
                wan_red_weight=self._wan_red_weight,
                wan_soft_red_weight=self._wan_soft_red_weight,
            )

            # In live mode (dry_run=False), use confidence decision for routing
            assert (
                self.config.confidence_config is not None
            )  # Guaranteed by confidence_controller check
            if confidence_decision and not self.config.confidence_config["dry_run"]["enabled"]:
                return self._apply_confidence_decision(confidence_decision)
            # In dry-run mode, confidence logs decisions but falls through to hysteresis

        # Fall through to existing hysteresis logic
        return self._update_state_machine_unified(signals)

    def collect_cake_stats(self) -> tuple[int, int]:
        """Collect CAKE statistics (drops and queued packets).

        Handles stats reading, history updates, consecutive failure
        tracking (W8 fix), and router connectivity tracking.

        Returns:
            tuple[int, int]: (cake_drops, queued_packets)
            Returns (0, 0) if no reader configured or read fails
        """
        # Return early if no reader configured (defensive guard)
        if not self.cake_reader:
            return (0, 0)

        state = self.state_mgr.state

        # Read CAKE statistics (using delta math, no resets needed)
        try:
            stats = self.cake_reader.read_stats(self.config.primary_download_queue)
        except Exception as e:
            # Track router connectivity failure
            failure_type = self.router_connectivity.record_failure(e)
            failures = self.router_connectivity.consecutive_failures
            if failures == 1 or failures == 3 or failures % 10 == 0:
                self.logger.warning(
                    f"Router communication failed during CAKE stats read ({failure_type}, "
                    f"{failures} consecutive)"
                )
            state["cake_read_failures"] += 1
            return (0, 0)

        if stats:
            cake_drops = stats.dropped
            queued_packets = stats.queued_packets

            # Reset failure counter on successful read
            state["cake_read_failures"] = 0

            # Track router connectivity success
            self.router_connectivity.record_success()

            # Update history (W4 fix: deques handle automatic eviction)
            state["cake_drops_history"].append(cake_drops)
            state["queue_depth_history"].append(queued_packets)
            # No manual trim needed - deques with maxlen automatically evict oldest elements

            return (cake_drops, queued_packets)
        # W8 fix: Track consecutive CAKE read failures (stats returned None)
        # Note: This is a soft failure, not a router connectivity failure
        state["cake_read_failures"] += 1
        if state["cake_read_failures"] == 1:
            # First failure - log warning
            self.logger.warning(
                f"CAKE stats read failed for {self.config.primary_download_queue}, "
                f"using RTT-only decisions (failure {state['cake_read_failures']})"
            )
        elif state["cake_read_failures"] >= 3:
            # Multiple failures - enter degraded mode
            if state["cake_read_failures"] == 3:
                self.logger.error(
                    f"CAKE stats unavailable after {state['cake_read_failures']} attempts, "
                    f"entering degraded mode (RTT-only decisions)"
                )
        # cake_drops=0 and queued_packets=0 signal RTT-only mode downstream
        return (0, 0)

    def update_ewma_smoothing(self, delta: float, queued_packets: int) -> tuple[float, float]:
        """
        Update EWMA smoothed values for RTT delta and queue depth.

        PROTECTED: Numeric stability C5 - EWMA alphas validated at config load.
        Formula: (1-alpha)*current + alpha*new. Do not modify without approval.
        See docs/CORE-ALGORITHM-ANALYSIS.md.

        Args:
            delta: Current RTT delta (current_rtt - baseline_rtt)
            queued_packets: Current CAKE queue depth in packets

        Returns:
            tuple[float, float]: (rtt_delta_ewma, queue_ewma) updated values
        """
        state = self.state_mgr.state

        rtt_delta_ewma = ewma_update(
            state["rtt_delta_ewma"], delta, self.config.rtt_ewma_alpha, logger=self.logger
        )
        state["rtt_delta_ewma"] = rtt_delta_ewma

        queue_ewma = ewma_update(
            state["queue_ewma"],
            float(queued_packets),
            self.config.queue_ewma_alpha,
            max_value=10000.0,  # Queue depth can exceed 1000 packets under heavy load
            logger=self.logger,
        )
        state["queue_ewma"] = queue_ewma

        return rtt_delta_ewma, queue_ewma

    def _record_profiling(
        self,
        cake_ms: float,
        rtt_ms: float,
        state_ms: float,
        cycle_start: float,
    ) -> None:
        """Record subsystem timing to profiler, emit structured log, and detect overruns.

        Thin wrapper around shared record_cycle_profiling() -- preserves method
        signature for test compatibility.
        """
        self._overrun_count, self._profile_cycle_count = record_cycle_profiling(
            profiler=self._profiler,
            timings={
                "steering_cake_stats": cake_ms,
                "steering_rtt_measurement": rtt_ms,
                "steering_state_management": state_ms,
            },
            cycle_start=cycle_start,
            cycle_interval_ms=self._cycle_interval_ms,
            logger=self.logger,
            daemon_name="Steering cycle",
            label_prefix="steering",
            overrun_count=self._overrun_count,
            profiling_enabled=self._profiling_enabled,
            profile_cycle_count=self._profile_cycle_count,
        )

    def run_cycle(self) -> bool:
        """Execute one steering cycle. Returns True on success, False on failure."""
        state = self.state_mgr.state
        cycle_start = time.perf_counter()

        # Update baseline RTT from autorate state
        if not self.update_baseline_rtt():
            self.logger.error("Cannot proceed without baseline RTT")
            return False

        baseline_rtt = state["baseline_rtt"]

        # === CAKE Stats Collection (subsystem 1) ===
        with PerfTimer("steering_cake_stats", self.logger) as cake_timer:
            cake_drops, queued_packets = self.collect_cake_stats()

        # === RTT Measurement (subsystem 2) ===
        with PerfTimer("steering_rtt_measurement", self.logger) as rtt_timer:
            current_rtt = self._measure_current_rtt_with_retry()

        if current_rtt is None:
            self.logger.warning(
                "Ping failed after retries and no fallback available, skipping cycle"
            )
            self._record_profiling(cake_timer.elapsed_ms, rtt_timer.elapsed_ms, 0.0, cycle_start)
            return False

        # === State Management (subsystem 3) ===
        anomaly_detected = False
        with PerfTimer("steering_state_management", self.logger) as state_timer:
            anomaly_detected = self._run_steering_state_subsystem(
                current_rtt, baseline_rtt, cake_drops, queued_packets
            )

        self._record_profiling(
            cake_timer.elapsed_ms, rtt_timer.elapsed_ms, state_timer.elapsed_ms, cycle_start
        )
        if anomaly_detected:
            return True  # STEER-02: cycle-skip (not failure) -- anomalies are transient
        return True

    def _run_steering_state_subsystem(
        self,
        current_rtt: float,
        baseline_rtt: float,
        cake_drops: int,
        queued_packets: int,
    ) -> bool:
        """Process state management for a steering cycle.

        Returns True if anomaly detected (cycle should be skipped).
        """
        state = self.state_mgr.state
        delta = self.calculate_delta(current_rtt)

        # Pre-filter: reject extreme RTT deltas as network anomalies
        if delta > MAX_SANE_RTT_DELTA_MS:
            self.logger.warning(
                f"RTT delta {delta:.1f}ms exceeds ceiling "
                f"{MAX_SANE_RTT_DELTA_MS:.0f}ms "
                f"(rtt={current_rtt:.1f}ms), treating as anomaly — skipping cycle"
            )
            return True

        # === EWMA Smoothing ===
        # PROTECTED: Numeric stability C5 - EWMA alphas validated at config load.
        rtt_delta_ewma, _ = self.update_ewma_smoothing(delta, queued_packets)

        # Add to history
        self.state_mgr.add_measurement(current_rtt, delta)

        # === Build Congestion Signals ===
        signals = CongestionSignals(
            rtt_delta=delta,
            rtt_delta_ewma=rtt_delta_ewma,
            cake_drops=cake_drops,
            queued_packets=queued_packets,
            baseline_rtt=baseline_rtt,
        )

        # === Log Measurement ===
        wan_name = self.config.primary_wan.upper()
        self.logger.debug(
            f"[{wan_name}_{state['current_state'].split('_')[-1]}] "
            f"{signals} | "
            f"congestion={state.get('congestion_state', 'N/A')}"
        )

        # === Update State Machine ===
        state_changed = self.update_state_machine(signals)

        # Track cake_state_history for confidence-based steering
        if "congestion_state" in state:
            cake_state_history = state.get("cake_state_history", [])
            cake_state_history.append(state["congestion_state"])
            state["cake_state_history"] = cake_state_history[-10:]

        if state_changed:
            self.logger.info(
                f"State transition: {state['current_state']} "
                f"(last transition: {state.get('last_transition_time', 'never')})"
            )

        # Save state
        self.state_mgr.save()

        # Record metrics
        self._record_steering_metrics(current_rtt, baseline_rtt, delta)
        return False

    def _record_steering_metrics(
        self, current_rtt: float, baseline_rtt: float, delta: float
    ) -> None:
        """Record steering metrics to Prometheus and SQLite."""
        state = self.state_mgr.state

        # Record steering metrics if enabled (Prometheus)
        if self.config.metrics_enabled:
            steering_enabled = state["current_state"] == self.config.state_degraded
            congestion_state = state.get("congestion_state", "GREEN")
            record_steering_state(
                primary_wan=self.config.primary_wan,
                steering_enabled=steering_enabled,
                congestion_state=congestion_state,
            )

        if self._metrics_writer is None:
            return

        ts = int(time.time())
        steering_enabled_val = (
            1.0 if state["current_state"] == self.config.state_degraded else 0.0
        )
        state_val = {"GREEN": 0, "YELLOW": 1, "RED": 2}.get(
            state.get("congestion_state", "GREEN"), 0
        )

        metrics_batch = [
            (ts, self.config.primary_wan, "wanctl_rtt_ms", current_rtt, None, "raw"),
            (ts, self.config.primary_wan, "wanctl_rtt_baseline_ms", baseline_rtt, None, "raw"),
            (ts, self.config.primary_wan, "wanctl_rtt_delta_ms", delta, None, "raw"),
            (ts, self.config.primary_wan, "wanctl_steering_enabled", steering_enabled_val, None, "raw"),
            (ts, self.config.primary_wan, "wanctl_state", float(state_val), {"source": "steering"}, "raw"),
        ]

        self._append_wan_awareness_metrics(metrics_batch, ts)
        self._append_cake_tin_metrics(metrics_batch, ts)
        self._metrics_writer.write_metrics_batch(metrics_batch)

    def _append_wan_awareness_metrics(
        self, metrics_batch: list, ts: int
    ) -> None:
        """Append WAN awareness metrics to batch (OBSV-02)."""
        if not self._wan_state_enabled:
            return

        zone_map = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
        effective_zone = self.get_effective_wan_zone()
        zone_val = zone_map.get(effective_zone or "GREEN", 0)
        metrics_batch.append(
            (ts, self.config.primary_wan, "wanctl_wan_zone", float(zone_val),
             {"zone": effective_zone or "none"}, "raw")
        )

        # WAN weight applied this cycle (OBSV-02 gap closure)
        if effective_zone == "RED":
            from wanctl.steering.steering_confidence import ConfidenceWeights
            weight_val = float(
                self._wan_red_weight
                if self._wan_red_weight is not None
                else ConfidenceWeights.WAN_RED
            )
        elif effective_zone == "SOFT_RED":
            from wanctl.steering.steering_confidence import ConfidenceWeights
            weight_val = float(
                self._wan_soft_red_weight
                if self._wan_soft_red_weight is not None
                else ConfidenceWeights.WAN_SOFT_RED
            )
        else:
            weight_val = 0.0
        metrics_batch.append(
            (ts, self.config.primary_wan, "wanctl_wan_weight", weight_val, None, "raw")
        )

        # WAN staleness age in seconds (OBSV-02 gap closure)
        staleness_age = self.baseline_loader.get_wan_zone_age()
        metrics_batch.append(
            (ts, self.config.primary_wan, "wanctl_wan_staleness_sec",
             float(staleness_age) if staleness_age is not None else -1.0, None, "raw")
        )

    def _append_cake_tin_metrics(
        self, metrics_batch: list, ts: int
    ) -> None:
        """Append per-tin CAKE metrics to batch (CAKE-07 observability)."""
        if not (
            getattr(self.cake_reader, "is_linux_cake", False)
            and self.cake_reader.last_tin_stats
        ):
            return

        for i, tin in enumerate(self.cake_reader.last_tin_stats):
            tin_name = TIN_NAMES[i] if i < len(TIN_NAMES) else f"tin_{i}"
            tin_labels = {"tin": tin_name}
            metrics_batch.append(
                (ts, self.config.primary_wan, "wanctl_cake_tin_dropped",
                 float(tin.get("dropped_packets", 0)), tin_labels, "raw")
            )
            metrics_batch.append(
                (ts, self.config.primary_wan, "wanctl_cake_tin_ecn_marked",
                 float(tin.get("ecn_marked_packets", 0)), tin_labels, "raw")
            )
            metrics_batch.append(
                (ts, self.config.primary_wan, "wanctl_cake_tin_delay_us",
                 float(tin.get("avg_delay_us", 0)), tin_labels, "raw")
            )
            metrics_batch.append(
                (ts, self.config.primary_wan, "wanctl_cake_tin_backlog_bytes",
                 float(tin.get("backlog_bytes", 0)), tin_labels, "raw")
            )


# =============================================================================
# DAEMON LOOP
# =============================================================================


def run_daemon_loop(
    daemon: SteeringDaemon,
    config: SteeringConfig,
    logger: logging.Logger,
    shutdown_event: threading.Event,
) -> int:
    """
    Run continuous daemon loop with watchdog and failure tracking.

    Executes steering cycles until shutdown signal received.
    Manages systemd watchdog notifications based on cycle success.
    Stops watchdog after max_consecutive_failures to trigger restart.

    Args:
        daemon: Initialized SteeringDaemon instance
        config: Steering configuration (for measurement_interval)
        logger: Logger for status messages
        shutdown_event: Event signaling shutdown request

    Returns:
        Exit code: 0 for graceful shutdown
    """
    consecutive_failures = 0
    max_consecutive_failures = 3
    watchdog_enabled = True

    logger.info(f"Starting daemon mode with {config.measurement_interval}s cycle interval")
    if is_systemd_available():
        logger.info("Systemd watchdog support enabled")

    # Main event loop - runs continuously until shutdown signal
    while not shutdown_event.is_set():
        cycle_start = time.monotonic()

        # Run one cycle
        cycle_success = daemon.run_cycle()

        elapsed = time.monotonic() - cycle_start

        # Track consecutive failures for watchdog
        if cycle_success:
            consecutive_failures = 0
            # Re-enable watchdog if previously surrendered (recovery)
            if not watchdog_enabled:
                watchdog_enabled = True
                logger.info(
                    "Cycle recovered after watchdog surrender. Re-enabling watchdog notifications."
                )
        else:
            consecutive_failures += 1
            logger.warning(f"Cycle failed ({consecutive_failures}/{max_consecutive_failures})")

            # Stop watchdog notifications if sustained failures
            if consecutive_failures >= max_consecutive_failures and watchdog_enabled:
                watchdog_enabled = False
                logger.error(
                    f"Sustained failure: {consecutive_failures} consecutive failed cycles. "
                    f"Stopping watchdog - systemd will terminate us."
                )
                notify_degraded("consecutive failures exceeded threshold")

        # Update health server with current failure state (INTG-03)
        update_steering_health_status(consecutive_failures)

        # Check for config reload signal (SIGUSR1)
        if is_reload_requested():
            logger.info("SIGUSR1 received, reloading config (dry_run + wan_state + webhook_url)")
            daemon._reload_dry_run_config()
            daemon._reload_wan_state_config()
            daemon._reload_webhook_url_config()
            reset_reload_state()

        # Notify systemd watchdog ONLY if healthy
        if watchdog_enabled and cycle_success:
            notify_watchdog()
        elif not watchdog_enabled:
            notify_degraded(f"{consecutive_failures} consecutive failures")

        # Sleep for remainder of cycle interval (interruptible)
        sleep_time = max(0, config.measurement_interval - elapsed)
        if sleep_time > 0 and not shutdown_event.is_set():
            shutdown_event.wait(timeout=sleep_time)

    logger.info("Shutdown signal received, exiting gracefully")
    return 0


# =============================================================================
# MAIN
# =============================================================================


def _parse_steering_args() -> argparse.Namespace:
    """Parse steering daemon CLI arguments."""
    parser = argparse.ArgumentParser(description="Adaptive Multi-WAN Steering Daemon")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--reset", action="store_true", help="Reset state and disable steering")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable periodic profiling reports (INFO level)",
    )
    return parser.parse_args()


def _run_steering_startup_storage(
    config: SteeringConfig, logger: logging.Logger
) -> None:
    """Record config snapshot and run startup maintenance if storage enabled."""
    storage_config = get_storage_config(config.data)
    db_path = storage_config.get("db_path")
    retention_config = storage_config.get("retention")

    validate_retention_tuner_compat(
        retention_config,
        config.data.get("tuning"),
        logger=logger,
    )

    if db_path and isinstance(db_path, str):
        from wanctl.storage import record_config_snapshot, run_startup_maintenance
        from wanctl.storage.maintenance import maintenance_lock

        writer = MetricsWriter(Path(db_path))
        writer.set_process_role("steering")
        record_config_snapshot(writer, config.primary_wan, config.data, "startup")

        with maintenance_lock(db_path, logger) as acquired:
            if acquired:
                maint_result = run_startup_maintenance(
                    writer.connection,
                    retention_config=retention_config,
                    log=logger,
                    watchdog_fn=notify_watchdog,
                    max_seconds=20,
                )
                if maint_result.get("error"):
                    logger.warning(f"Startup maintenance error: {maint_result['error']}")
            else:
                record_storage_maintenance_lock_skip("steering")

        logger.info(f"Config snapshot recorded to {db_path}")


def _create_steering_components(
    config: SteeringConfig, logger: logging.Logger
) -> tuple[SteeringStateManager, RouterOSController, RTTMeasurement, BaselineLoader]:
    """Initialize steering daemon components."""
    schema = create_steering_state_schema(config)
    state_mgr = SteeringStateManager(
        config.state_file, schema, logger, history_maxlen=config.history_size
    )
    state_mgr.load()
    router = RouterOSController(config, logger)
    rtt_measurement = RTTMeasurement(
        logger,
        timeout_ping=config.timeout_ping,
        aggregation_strategy=RTTAggregationStrategy.MEDIAN,
        log_sample_stats=False,
    )
    baseline_loader = BaselineLoader(config, logger)
    return state_mgr, router, rtt_measurement, baseline_loader


def _cleanup_steering_daemon(
    daemon: SteeringDaemon,
    config: SteeringConfig,
    health_server: "SteeringHealthServer | None",
    logger: logging.Logger,
) -> None:
    """Ordered shutdown: state > health > connections > metrics > locks."""
    cleanup_start = time.monotonic()
    deadline = cleanup_start + SHUTDOWN_TIMEOUT_SECONDS
    logger.info("Shutting down daemon...")

    # 0. Force save state (preserve EWMA/counters on shutdown)
    t0 = time.monotonic()
    try:
        daemon.state_mgr.save()
        logger.debug("State saved on shutdown")
    except Exception as e:
        logger.warning(f"Error saving state on shutdown: {e}")
    check_cleanup_deadline(
        "state_save", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )

    # 1. Shutdown health server (INTG-02)
    if health_server is not None:
        t0 = time.monotonic()
        try:
            health_server.shutdown()
            logger.debug("Health server stopped")
        except Exception as e:
            logger.warning(f"Error shutting down health server: {e}")
        check_cleanup_deadline(
            "health_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS,
            logger, now=time.monotonic(),
        )

    # 2. Close router connection
    t0 = time.monotonic()
    try:
        daemon.router.client.close()
        logger.debug("Router connection closed")
    except Exception as e:
        logger.warning(f"Error closing router connection: {e}")
    check_cleanup_deadline(
        "router_close", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )

    # 3. Close MetricsWriter (SQLite connection)
    t0 = time.monotonic()
    try:
        mw = MetricsWriter.get_instance()
        if mw is not None:
            mw.close()
            logger.debug("MetricsWriter connection closed")
    except Exception as e:
        logger.warning(f"Error closing MetricsWriter: {e}")
    check_cleanup_deadline(
        "metrics_writer", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )

    # 4. Release lock file
    if config.lock_file.exists():
        config.lock_file.unlink()
        logger.debug(f"Lock released: {config.lock_file}")

    total = time.monotonic() - cleanup_start
    logger.info(f"Shutdown complete ({total:.1f}s)")


def _setup_steering_daemon(
    config: SteeringConfig,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> tuple[SteeringDaemon, SteeringHealthServer | None]:
    """Create daemon instance, acquire lock, start health server.

    Returns:
        (daemon, health_server) tuple
    """
    state_mgr, router, rtt_measurement, baseline_loader = _create_steering_components(
        config, logger
    )

    if args.reset:
        logger.info("RESET requested")
        state_mgr.reset()
        router.disable_steering()
        logger.info("Reset complete")
        raise SystemExit(0)

    if not validate_and_acquire_lock(config.lock_file, config.lock_timeout, logger):
        logger.error("Another instance is running, refusing to start")
        raise SystemExit(1)

    def emergency_lock_cleanup() -> None:
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        try:
            config.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(emergency_lock_cleanup)

    if is_shutdown_requested():
        logger.info("Shutdown requested before startup, exiting gracefully")
        config.lock_file.unlink(missing_ok=True)
        raise SystemExit(0)

    daemon = SteeringDaemon(config, state_mgr, router, rtt_measurement, baseline_loader, logger)
    clear_router_password(config)

    if args.profile:
        daemon._profiling_enabled = True

    health_server = None
    if config.health_check_enabled:
        try:
            health_server = start_steering_health_server(
                host=config.health_check_host,
                port=config.health_check_port,
                daemon=daemon,
            )
        except Exception as e:
            logger.warning(f"Failed to start health server: {e}")

    return daemon, health_server


def main() -> int | None:
    """Main entry point for adaptive multi-WAN steering daemon.

    Orchestrates setup, daemon loop, and cleanup for the steering service.

    Returns:
        int: Exit code - 0 for success, 1 for error, 130 for interrupt
    """
    args = _parse_steering_args()
    register_signal_handlers()

    try:
        config = SteeringConfig(args.config)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        traceback.print_exc()
        return 1

    logger = setup_logging(config, "steering", args.debug)
    logger.info("=" * 60)
    logger.info(
        f"Steering Daemon - Primary: {config.primary_wan}, Alternate: {config.alternate_wan}"
    )
    logger.info("=" * 60)

    _run_steering_startup_storage(config, logger)

    if is_shutdown_requested():
        logger.info("Shutdown requested during startup, exiting gracefully")
        return 0

    try:
        daemon, health_server = _setup_steering_daemon(config, args, logger)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 0

    try:
        return run_daemon_loop(daemon, config, logger, get_shutdown_event())
    except KeyboardInterrupt:
        logger.info("Interrupted by user (KeyboardInterrupt)")
        return 130
    except Exception as e:
        if is_shutdown_requested():
            logger.info("Exception during shutdown, exiting gracefully")
            return 0
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        _cleanup_steering_daemon(daemon, config, health_server, logger)


if __name__ == "__main__":
    sys.exit(main())

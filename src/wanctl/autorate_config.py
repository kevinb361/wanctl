"""Autorate daemon configuration loaded from YAML.

Contains the Config class (extends BaseConfig) and config-related constants
for baseline RTT thresholds, bloat defaults, and unit conversion.
"""

import logging
import os
from pathlib import Path
from typing import TypedDict

from wanctl.config_base import BaseConfig
from wanctl.config_validation_utils import (
    deprecate_param,
    validate_bandwidth_order,
    validate_threshold_order,
)
from wanctl.timeouts import DEFAULT_AUTORATE_PING_TIMEOUT, DEFAULT_AUTORATE_SSH_TIMEOUT
from wanctl.tuning.models import SafetyBounds, TuningConfig

# =============================================================================
# CONSTANTS
# =============================================================================

# Baseline RTT update threshold - only update baseline when delta is minimal
# This prevents baseline drift under load (architectural invariant)
DEFAULT_BASELINE_UPDATE_THRESHOLD_MS = 3.0

# Default bloat thresholds (milliseconds)
DEFAULT_HARD_RED_BLOAT_MS = 80  # SOFT_RED -> RED transition threshold

# Baseline RTT sanity bounds (milliseconds)
# Typical home ISP latencies are 20-50ms. Anything below 10ms indicates local LAN,
# anything above 60ms suggests routing issues or corrupted state.
MIN_SANE_BASELINE_RTT = 10.0
MAX_SANE_BASELINE_RTT = 60.0

# Conversion factors
MBPS_TO_BPS = 1_000_000


class FusionHealingConfig(TypedDict):
    """Typed dict for fusion healing parameters."""

    suspend_threshold: float
    recover_threshold: float
    suspend_window_sec: float
    recover_window_sec: float
    grace_period_sec: float


class FusionConfig(TypedDict):
    """Typed dict for fusion configuration."""

    icmp_weight: float
    enabled: bool
    healing: FusionHealingConfig


class IRTTConfig(TypedDict):
    """Typed dict for IRTT measurement configuration."""

    enabled: bool
    server: str | None
    port: int
    duration_sec: float
    interval_ms: int
    cadence_sec: float


class ReflectorQualityConfig(TypedDict):
    """Typed dict for reflector quality scoring configuration."""

    min_score: float
    window_size: int
    probe_interval_sec: float
    recovery_count: int


class OWDAsymmetryConfig(TypedDict):
    """Typed dict for OWD asymmetry detection configuration."""

    ratio_threshold: float


class Config(BaseConfig):
    """Configuration container loaded from YAML"""

    fusion_config: FusionConfig
    irtt_config: IRTTConfig
    reflector_quality_config: ReflectorQualityConfig
    owd_asymmetry_config: OWDAsymmetryConfig

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
        {
            "path": "continuous_monitoring.thresholds.accel_confirm_cycles",
            "type": int,
            "required": False,
            "min": 1,
            "max": 10,
        },
        # Hysteresis parameters (Phase 122)
        {
            "path": "continuous_monitoring.thresholds.dwell_cycles",
            "type": int,
            "required": False,
            "min": 0,
            "max": 20,
        },
        {
            "path": "continuous_monitoring.thresholds.deadband_ms",
            "type": (int, float),
            "required": False,
            "min": 0.0,
            "max": 20.0,
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
        self.target_bloat_ms = thresh["target_bloat_ms"]  # GREEN -> YELLOW (15ms)
        self.warn_bloat_ms = thresh["warn_bloat_ms"]  # YELLOW -> SOFT_RED (45ms)
        self.hard_red_bloat_ms = thresh.get("hard_red_bloat_ms", DEFAULT_HARD_RED_BLOAT_MS)

        # EWMA alpha from time constants (with legacy deprecation)
        self._load_ewma_alpha_config(thresh)

        # Baseline update threshold (architectural invariant)
        self.baseline_update_threshold_ms = thresh.get(
            "baseline_update_threshold_ms", DEFAULT_BASELINE_UPDATE_THRESHOLD_MS
        )

        # Acceleration threshold for rate-of-change detection (Phase 3)
        self.accel_threshold_ms = thresh.get("accel_threshold_ms", 15.0)
        self.accel_confirm_cycles = thresh.get("accel_confirm_cycles", 3)

        # Hysteresis: dwell timer and deadband for GREEN<->YELLOW transitions (Phase 122)
        self.dwell_cycles = thresh.get("dwell_cycles", 3)
        self.deadband_ms = thresh.get("deadband_ms", 3.0)

        # Baseline RTT security bounds
        bounds = thresh.get("baseline_rtt_bounds", {})
        self.baseline_rtt_min = bounds.get("min", MIN_SANE_BASELINE_RTT)
        self.baseline_rtt_max = bounds.get("max", MAX_SANE_BASELINE_RTT)

        validate_threshold_order(
            target_bloat_ms=self.target_bloat_ms,
            warn_bloat_ms=self.warn_bloat_ms,
            hard_red_bloat_ms=self.hard_red_bloat_ms,
            logger=logging.getLogger(__name__),
        )

    def _load_ewma_alpha_config(self, thresh: dict) -> None:
        """Resolve EWMA alpha values from time constants or legacy alpha params."""
        logger = logging.getLogger(__name__)
        from wanctl.wan_controller import CYCLE_INTERVAL_SECONDS

        cycle_interval = CYCLE_INTERVAL_SECONDS

        # Deprecation: translate legacy alpha -> time_constant
        _tc_from_baseline = deprecate_param(
            thresh, "alpha_baseline", "baseline_time_constant_sec", logger,
            transform_fn=lambda alpha: cycle_interval / alpha,
        )
        if _tc_from_baseline is not None:
            thresh["baseline_time_constant_sec"] = _tc_from_baseline

        _tc_from_load = deprecate_param(
            thresh, "alpha_load", "load_time_constant_sec", logger,
            transform_fn=lambda alpha: cycle_interval / alpha,
        )
        if _tc_from_load is not None:
            thresh["load_time_constant_sec"] = _tc_from_load

        # Resolve baseline alpha
        self.alpha_baseline = self._resolve_alpha(
            thresh, "baseline", cycle_interval, logger
        )
        # Resolve load alpha
        self.alpha_load = self._resolve_alpha(
            thresh, "load", cycle_interval, logger
        )

    def _resolve_alpha(
        self, thresh: dict, prefix: str, cycle_interval: float, logger: logging.Logger
    ) -> float:
        """Resolve alpha from time_constant or raw alpha. Raises ValueError if neither present."""
        tc_key = f"{prefix}_time_constant_sec"
        alpha_key = f"alpha_{prefix}"

        if tc_key in thresh:
            tc = thresh[tc_key]
            alpha = cycle_interval / tc
            logger.info(f"Calculated {alpha_key}={alpha:.6f} from time_constant={tc}s")
            return alpha  # type: ignore[no-any-return]
        if alpha_key in thresh:
            alpha = thresh[alpha_key]
            if prefix == "load":
                expected_tc = cycle_interval / alpha
                if expected_tc > 5.0:
                    logger.warning(
                        f"{alpha_key}={alpha} gives {expected_tc:.1f}s time constant - "
                        f"consider using {tc_key} for clarity"
                    )
            return alpha  # type: ignore[no-any-return]
        raise ValueError(f"Config must specify either {tc_key} or {alpha_key}")

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
        self.router_transport = router.get(
            "transport", "rest"
        )  # Default to REST (2x faster than SSH, see docs/TRANSPORT_COMPARISON.md)
        # REST API specific settings (only used if transport=rest)
        self.router_password = router.get("password", "")
        self.router_port = router.get("port", 443)
        self.router_verify_ssl = router.get("verify_ssl", True)

    def _load_rate_limiter_config(self) -> None:
        """Load rate limiter settings from router.rate_limiter YAML section.

        Per D-08: YAML-overridable under router.rate_limiter with keys:
          max_changes (int): Max API changes per window. Must be positive.
          window_seconds (int): Sliding window duration. Must be positive.
          enabled (bool): Whether rate limiting is active. Default True.

        Invalid values log a warning and are excluded (backend defaults apply).
        """
        router = self.data.get("router", {})
        rl = router.get("rate_limiter", {})
        if not isinstance(rl, dict):
            rl = {}
        validated: dict[str, int | bool] = {}
        logger = logging.getLogger(__name__)

        if "enabled" in rl:
            val = rl["enabled"]
            if isinstance(val, bool):
                validated["enabled"] = val
            else:
                logger.warning(
                    "router.rate_limiter.enabled must be bool, got %s -- ignoring",
                    type(val).__name__,
                )

        for key in ("max_changes", "window_seconds"):
            if key in rl:
                val = rl[key]
                if isinstance(val, int) and not isinstance(val, bool) and val > 0:
                    validated[key] = val
                else:
                    logger.warning(
                        "router.rate_limiter.%s must be positive int, got %r -- ignoring",
                        key,
                        val,
                    )

        self.rate_limiter_config: dict[str, int | bool] = validated

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

        # Validate enabled flag
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

        # Validate core fields, rules, and delivery settings
        defaults = self._validate_alerting_defaults(alerting, logger)
        if defaults is None:
            return
        rules = self._validate_alerting_rules(alerting, logger)
        if rules is None:
            return
        delivery = self._load_alerting_delivery_config(alerting, logger)

        self.alerting_config = {
            "enabled": True,
            "webhook_url": delivery["webhook_url"],
            "default_cooldown_sec": defaults["cooldown"],
            "default_sustained_sec": defaults["sustained"],
            "rules": rules,
            "mention_role_id": delivery["mention_role_id"],
            "mention_severity": delivery["mention_severity"],
            "max_webhooks_per_minute": delivery["max_webhooks_per_minute"],
        }
        logger.info(f"Alerting: enabled ({len(rules)} rules configured)")

    def _validate_alerting_defaults(
        self, alerting: dict, logger: logging.Logger
    ) -> dict | None:
        """Validate alerting cooldown and sustained duration. Returns None on failure."""
        default_cooldown_sec = alerting.get("default_cooldown_sec", 300)
        if not isinstance(default_cooldown_sec, int) or isinstance(default_cooldown_sec, bool):
            logger.warning(
                f"alerting.default_cooldown_sec must be int, got {type(default_cooldown_sec).__name__}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return None
        if default_cooldown_sec < 0:
            logger.warning(
                f"alerting.default_cooldown_sec must be >= 0, got {default_cooldown_sec}; "
                "disabling alerting"
            )
            self.alerting_config = None
            return None

        default_sustained_sec = alerting.get("default_sustained_sec", 60)
        if not isinstance(default_sustained_sec, int) or isinstance(default_sustained_sec, bool):
            logger.warning(
                f"alerting.default_sustained_sec must be int, "
                f"got {type(default_sustained_sec).__name__}; disabling alerting"
            )
            self.alerting_config = None
            return None
        if default_sustained_sec < 0:
            logger.warning(
                f"alerting.default_sustained_sec must be >= 0, "
                f"got {default_sustained_sec}; disabling alerting"
            )
            self.alerting_config = None
            return None

        return {"cooldown": default_cooldown_sec, "sustained": default_sustained_sec}

    def _validate_alerting_rules(
        self, alerting: dict, logger: logging.Logger
    ) -> dict | None:
        """Validate alerting rules map and per-rule severity. Returns None on failure."""
        rules = alerting.get("rules", {})
        if not isinstance(rules, dict):
            logger.warning(
                f"alerting.rules must be a map, got {type(rules).__name__}; disabling alerting"
            )
            self.alerting_config = None
            return None

        valid_severities = {"info", "warning", "critical"}
        for rule_name, rule in rules.items():
            if not isinstance(rule, dict):
                logger.warning(f"alerting.rules.{rule_name} must be a map; disabling alerting")
                self.alerting_config = None
                return None
            severity = rule.get("severity")
            if severity is None:
                logger.warning(
                    f"alerting.rules.{rule_name} missing required 'severity'; disabling alerting"
                )
                self.alerting_config = None
                return None
            if severity not in valid_severities:
                logger.warning(
                    f"alerting.rules.{rule_name}.severity must be one of {valid_severities}, "
                    f"got '{severity}'; disabling alerting"
                )
                self.alerting_config = None
                return None
        return rules

    def _load_alerting_delivery_config(
        self, alerting: dict, logger: logging.Logger
    ) -> dict:
        """Load webhook URL, mention settings, and rate limiting for alerting."""
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
        if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 3:
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
        if not isinstance(jitter_tc, (int, float)) or isinstance(jitter_tc, bool) or jitter_tc <= 0:
            logger.warning(
                f"signal_processing.jitter_time_constant_sec must be positive number, "
                f"got {jitter_tc!r}; defaulting to 2.0"
            )
            jitter_tc = 2.0

        variance_tc = sp.get("variance_time_constant_sec", 5.0) if isinstance(sp, dict) else 5.0
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
            logger.warning(f"irtt config must be dict, got {type(irtt).__name__}; using defaults")
            irtt = {}

        enabled = irtt.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(f"irtt.enabled must be bool, got {enabled!r}; defaulting to false")
            enabled = False

        server = irtt.get("server")
        if server is not None and not isinstance(server, str):
            logger.warning(f"irtt.server must be str, got {server!r}; defaulting to None")
            server = None

        port = irtt.get("port", 2112)
        if not isinstance(port, int) or isinstance(port, bool) or port < 1 or port > 65535:
            logger.warning(f"irtt.port must be int 1-65535, got {port!r}; defaulting to 2112")
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
        if not isinstance(interval_ms, int) or isinstance(interval_ms, bool) or interval_ms < 1:
            logger.warning(
                f"irtt.interval_ms must be positive int, got {interval_ms!r}; defaulting to 100"
            )
            interval_ms = 100

        cadence_sec = irtt.get("cadence_sec", 10)
        if (
            not isinstance(cadence_sec, (int, float))
            or isinstance(cadence_sec, bool)
            or cadence_sec < 1
        ):
            logger.warning(
                f"irtt.cadence_sec must be number >= 1, got {cadence_sec!r}; defaulting to 10"
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
                f"reflector_quality config must be dict, got {type(rq).__name__}; using defaults"
            )
            rq = {}

        min_score = rq.get("min_score", 0.8)
        if not isinstance(min_score, (int, float)) or isinstance(min_score, bool):
            logger.warning(
                f"reflector_quality.min_score must be number, got {min_score!r}; defaulting to 0.8"
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

        icmp_weight, enabled = self._validate_fusion_base(fusion, logger)
        healing = self._load_fusion_healing_config(fusion, logger)

        self.fusion_config = {
            "icmp_weight": float(icmp_weight),
            "enabled": enabled,
            "healing": healing,
        }
        logger.info(
            f"Fusion: enabled={enabled}, icmp_weight={icmp_weight}, "
            f"healing.suspend_threshold={healing['suspend_threshold']}, "
            f"healing.recover_threshold={healing['recover_threshold']}"
        )

    def _validate_fusion_base(
        self, fusion: dict, logger: logging.Logger
    ) -> tuple[float, bool]:
        """Validate fusion icmp_weight and enabled flag. Returns (icmp_weight, enabled)."""
        icmp_weight = fusion.get("icmp_weight", 0.7)
        if (
            not isinstance(icmp_weight, (int, float))
            or isinstance(icmp_weight, bool)
            or icmp_weight < 0.0
            or icmp_weight > 1.0
        ):
            logger.warning(
                f"fusion.icmp_weight must be number 0.0-1.0, got {icmp_weight!r}; defaulting to 0.7"
            )
            icmp_weight = 0.7

        enabled = fusion.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"fusion.enabled must be bool, got {type(enabled).__name__}; defaulting to false"
            )
            enabled = False

        return float(icmp_weight), enabled

    def _load_fusion_healing_config(
        self, fusion: dict, logger: logging.Logger
    ) -> FusionHealingConfig:
        """Load and validate fusion healing parameters (Phase 119: FUSE-01 through FUSE-05)."""
        healing = fusion.get("healing", {})
        if not isinstance(healing, dict):
            logger.warning(
                f"fusion.healing must be dict, got {type(healing).__name__}; using defaults"
            )
            healing = {}

        suspend_threshold = self._validate_fusion_threshold(
            healing, "suspend_threshold", 0.3, logger
        )
        recover_threshold = self._validate_fusion_threshold(
            healing, "recover_threshold", 0.5, logger
        )
        if recover_threshold <= suspend_threshold:
            logger.warning(
                f"fusion.healing.recover_threshold ({recover_threshold}) must be > "
                f"suspend_threshold ({suspend_threshold}); "
                f"defaulting to suspend_threshold + 0.2"
            )
            recover_threshold = min(suspend_threshold + 0.2, 1.0)

        suspend_window_sec = self._validate_fusion_window(
            healing, "suspend_window_sec", 60.0, 10.0, logger
        )
        recover_window_sec = self._validate_fusion_window(
            healing, "recover_window_sec", 300.0, 30.0, logger
        )

        grace_period_sec = healing.get("grace_period_sec", 1800.0)
        if (
            not isinstance(grace_period_sec, (int, float))
            or isinstance(grace_period_sec, bool)
            or grace_period_sec < 0
        ):
            logger.warning(
                f"fusion.healing.grace_period_sec invalid ({grace_period_sec!r}); "
                f"defaulting to 1800.0"
            )
            grace_period_sec = 1800.0

        return {
            "suspend_threshold": float(suspend_threshold),
            "recover_threshold": float(recover_threshold),
            "suspend_window_sec": float(suspend_window_sec),
            "recover_window_sec": float(recover_window_sec),
            "grace_period_sec": float(grace_period_sec),
        }

    def _validate_fusion_threshold(
        self, healing: dict, key: str, default: float, logger: logging.Logger
    ) -> float:
        """Validate a fusion healing threshold (0.0-1.0 range)."""
        value = healing.get(key, default)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not (0.0 <= value <= 1.0)
        ):
            logger.warning(f"fusion.healing.{key} invalid ({value!r}); defaulting to {default}")
            return default
        return float(value)

    def _validate_fusion_window(
        self, healing: dict, key: str, default: float, minimum: float, logger: logging.Logger
    ) -> float:
        """Validate a fusion healing window duration (must be >= minimum)."""
        value = healing.get(key, default)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < minimum
        ):
            logger.warning(
                f"fusion.healing.{key} invalid ({value!r}); defaulting to {default}"
            )
            return default
        return float(value)

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

        enabled = tuning.get("enabled", False)
        if not isinstance(enabled, bool):
            logger.warning(
                f"tuning.enabled must be bool, got {type(enabled).__name__}; disabling tuning"
            )
            self.tuning_config = None
            return
        if not enabled:
            self.tuning_config = None
            logger.info("Tuning: disabled (enable via tuning.enabled)")
            return

        core = self._validate_tuning_core(tuning, logger)
        if core is None:
            return
        exclude_params = self._load_tuning_exclude_params(tuning, logger)
        if exclude_params is None:
            return
        bounds = self._load_tuning_bounds(tuning, logger)
        if bounds is None:
            return

        self.tuning_config = TuningConfig(
            enabled=True,
            cadence_sec=core["cadence_sec"],
            lookback_hours=core["lookback_hours"],
            warmup_hours=core["warmup_hours"],
            max_step_pct=core["max_step_pct"],
            bounds=bounds,
            exclude_params=exclude_params,
        )
        exclude_msg = f", exclude={sorted(exclude_params)}" if exclude_params else ""
        logger.info(
            f"Tuning: enabled (cadence={core['cadence_sec']}s, lookback={core['lookback_hours']}h, "
            f"{len(bounds)} bounds{exclude_msg})"
        )

    def _validate_tuning_core(
        self, tuning: dict, logger: logging.Logger
    ) -> dict | None:
        """Validate tuning cadence, lookback, warmup, and max_step_pct. Returns None on failure."""
        cadence_sec = self._validate_tuning_int_param(
            tuning, "cadence_sec", 3600, 600, None, logger
        )
        if cadence_sec is None:
            return None
        lookback_hours = self._validate_tuning_int_param(
            tuning, "lookback_hours", 24, 1, 168, logger
        )
        if lookback_hours is None:
            return None
        warmup_hours = self._validate_tuning_int_param(
            tuning, "warmup_hours", 1, 1, 24, logger
        )
        if warmup_hours is None:
            return None

        max_step_pct = tuning.get("max_step_pct", 10.0)
        if not isinstance(max_step_pct, (int, float)) or isinstance(max_step_pct, bool):
            logger.warning(
                f"tuning.max_step_pct must be number, got {type(max_step_pct).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return None
        max_step_pct = float(max_step_pct)
        if max_step_pct < 1.0 or max_step_pct > 50.0:
            logger.warning(
                f"tuning.max_step_pct must be 1.0-50.0, got {max_step_pct}; disabling tuning"
            )
            self.tuning_config = None
            return None

        return {
            "cadence_sec": cadence_sec,
            "lookback_hours": lookback_hours,
            "warmup_hours": warmup_hours,
            "max_step_pct": max_step_pct,
        }

    def _validate_tuning_int_param(
        self,
        tuning: dict,
        key: str,
        default: int,
        min_val: int,
        max_val: int | None,
        logger: logging.Logger,
    ) -> int | None:
        """Validate a tuning integer parameter with range check. Returns None on failure."""
        value = tuning.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool):
            logger.warning(
                f"tuning.{key} must be int, got {type(value).__name__}; disabling tuning"
            )
            self.tuning_config = None
            return None
        if value < min_val or (max_val is not None and value > max_val):
            range_str = f">= {min_val}" if max_val is None else f"{min_val}-{max_val}"
            logger.warning(
                f"tuning.{key} must be {range_str}, got {value}; disabling tuning"
            )
            self.tuning_config = None
            return None
        return value

    def _load_tuning_exclude_params(
        self, tuning: dict, logger: logging.Logger
    ) -> frozenset[str] | None:
        """Parse tuning exclude_params list. Returns None on failure.

        Default: response params excluded (RTUN-05 graduation pattern).
        No exclude_params in YAML -> response params excluded (safe default).
        Explicit exclude_params: [] -> nothing excluded (all params tunable).
        """
        from wanctl.tuning.strategies.response import RESPONSE_PARAMS as _RESP_DEFAULTS

        _default_exclude = list(_RESP_DEFAULTS)
        raw_exclude = tuning.get("exclude_params", _default_exclude)
        if not isinstance(raw_exclude, list):
            logger.warning(
                f"tuning.exclude_params must be a list, got {type(raw_exclude).__name__}; "
                "disabling tuning"
            )
            self.tuning_config = None
            return None
        return frozenset(str(p) for p in raw_exclude)

    def _load_tuning_bounds(
        self, tuning: dict, logger: logging.Logger
    ) -> dict[str, SafetyBounds] | None:
        """Parse and validate tuning bounds dict. Returns None on failure."""
        raw_bounds = tuning.get("bounds", {})
        if not isinstance(raw_bounds, dict):
            logger.warning(
                f"tuning.bounds must be a dict, got {type(raw_bounds).__name__}; disabling tuning"
            )
            self.tuning_config = None
            return None

        bounds: dict[str, SafetyBounds] = {}
        for param_name, bound_spec in raw_bounds.items():
            result = self._validate_single_bound(param_name, bound_spec, logger)
            if result is None:
                return None
            bounds[param_name] = result
        return bounds

    def _validate_single_bound(
        self, param_name: str, bound_spec: object, logger: logging.Logger
    ) -> SafetyBounds | None:
        """Validate a single tuning bound entry. Returns None on failure."""
        if not isinstance(bound_spec, dict):
            logger.warning(
                f"tuning.bounds.{param_name} must be a dict with min/max, "
                f"got {type(bound_spec).__name__}; disabling tuning"
            )
            self.tuning_config = None
            return None

        min_val = bound_spec.get("min")
        max_val = bound_spec.get("max")

        if min_val is None or max_val is None:
            logger.warning(
                f"tuning.bounds.{param_name} must have 'min' and 'max' keys; disabling tuning"
            )
            self.tuning_config = None
            return None

        if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
            logger.warning(
                f"tuning.bounds.{param_name} min/max must be numeric; disabling tuning"
            )
            self.tuning_config = None
            return None

        if min_val > max_val:
            logger.warning(
                f"tuning.bounds.{param_name} min ({min_val}) > max ({max_val}); "
                "disabling tuning"
            )
            self.tuning_config = None
            return None

        return SafetyBounds(min_value=float(min_val), max_value=float(max_val))

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

        # Rate limiter (optional, YAML-overridable under router.rate_limiter)
        self._load_rate_limiter_config()

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

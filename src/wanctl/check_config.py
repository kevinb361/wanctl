"""Offline configuration validator for wanctl configs (autorate and steering).

Validates YAML config files against their schema, checks cross-field
constraints, file paths, environment variables, deprecated parameters, and
unknown keys. Auto-detects config type from file contents or accepts --type
override. Reports all problems at once with PASS/WARN/FAIL per category.

Usage:
    wanctl-check-config spectrum.yaml
    wanctl-check-config steering.yaml
    wanctl-check-config spectrum.yaml --type autorate
    wanctl-check-config spectrum.yaml --no-color
    wanctl-check-config spectrum.yaml -q
"""

import argparse
import difflib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from wanctl.autorate_continuous import Config
from wanctl.config_base import BaseConfig, ConfigValidationError, _get_nested, validate_field
from wanctl.config_validation_utils import validate_bandwidth_order, validate_threshold_order
from wanctl.steering.daemon import SteeringConfig

# =============================================================================
# DATA MODEL
# =============================================================================


class Severity(Enum):
    """Validation result severity levels."""

    PASS = "pass"
    WARN = "warn"
    ERROR = "error"


@dataclass
class CheckResult:
    """A single validation check result."""

    category: str
    field: str
    severity: Severity
    message: str
    suggestion: str | None = None


# =============================================================================
# KNOWN CONFIGURATION PATHS
# =============================================================================

# Comprehensive set of valid autorate config paths.
# Sources: BASE_SCHEMA + Config.SCHEMA + imperative loads in _load_specific_fields.
# This must cover ALL paths in production configs (spectrum.yaml, att.yaml)
# to avoid false-positive "unknown key" warnings.
KNOWN_AUTORATE_PATHS: set[str] = {
    # From BASE_SCHEMA
    "wan_name",
    "router",
    "router.host",
    "router.user",
    "router.ssh_key",
    "logging",
    "logging.main_log",
    "logging.debug_log",
    "logging.max_bytes",
    "logging.backup_count",
    "lock_file",
    "lock_timeout",
    # From Config.SCHEMA
    "queues",
    "queues.download",
    "queues.upload",
    "continuous_monitoring",
    "continuous_monitoring.enabled",
    "continuous_monitoring.baseline_rtt_initial",
    "continuous_monitoring.download",
    "continuous_monitoring.download.ceiling_mbps",
    "continuous_monitoring.download.step_up_mbps",
    "continuous_monitoring.download.factor_down",
    "continuous_monitoring.download.factor_down_yellow",
    "continuous_monitoring.download.green_required",
    # Legacy single-floor (ATT format)
    "continuous_monitoring.download.floor_mbps",
    # Modern multi-floor (Spectrum format)
    "continuous_monitoring.download.floor_green_mbps",
    "continuous_monitoring.download.floor_yellow_mbps",
    "continuous_monitoring.download.floor_soft_red_mbps",
    "continuous_monitoring.download.floor_red_mbps",
    # Upload (same legacy vs modern pattern)
    "continuous_monitoring.upload",
    "continuous_monitoring.upload.ceiling_mbps",
    "continuous_monitoring.upload.step_up_mbps",
    "continuous_monitoring.upload.factor_down",
    "continuous_monitoring.upload.factor_down_yellow",
    "continuous_monitoring.upload.green_required",
    "continuous_monitoring.upload.floor_mbps",
    "continuous_monitoring.upload.floor_green_mbps",
    "continuous_monitoring.upload.floor_yellow_mbps",
    "continuous_monitoring.upload.floor_red_mbps",
    # Thresholds
    "continuous_monitoring.thresholds",
    "continuous_monitoring.thresholds.target_bloat_ms",
    "continuous_monitoring.thresholds.warn_bloat_ms",
    "continuous_monitoring.thresholds.hard_red_bloat_ms",
    "continuous_monitoring.thresholds.alpha_baseline",
    "continuous_monitoring.thresholds.alpha_load",
    "continuous_monitoring.thresholds.baseline_time_constant_sec",
    "continuous_monitoring.thresholds.load_time_constant_sec",
    "continuous_monitoring.thresholds.accel_threshold_ms",
    "continuous_monitoring.thresholds.accel_confirm_cycles",
    "continuous_monitoring.thresholds.dwell_cycles",
    "continuous_monitoring.thresholds.deadband_ms",
    "continuous_monitoring.thresholds.baseline_update_threshold_ms",
    "continuous_monitoring.thresholds.baseline_rtt_bounds",
    "continuous_monitoring.thresholds.baseline_rtt_bounds.min",
    "continuous_monitoring.thresholds.baseline_rtt_bounds.max",
    # Ping
    "continuous_monitoring.ping_hosts",
    "continuous_monitoring.use_median_of_three",
    # Fallback checks
    "continuous_monitoring.fallback_checks",
    "continuous_monitoring.fallback_checks.enabled",
    "continuous_monitoring.fallback_checks.check_gateway",
    "continuous_monitoring.fallback_checks.check_tcp",
    "continuous_monitoring.fallback_checks.gateway_ip",
    "continuous_monitoring.fallback_checks.tcp_targets",
    "continuous_monitoring.fallback_checks.fallback_mode",
    "continuous_monitoring.fallback_checks.max_fallback_cycles",
    # Router (imperatively loaded)
    "router.transport",
    "router.password",
    "router.port",
    "router.verify_ssl",
    # State file (imperatively loaded)
    "state_file",
    # Timeouts (imperatively loaded)
    "timeouts",
    "timeouts.ssh_command",
    "timeouts.ping",
    # Health check (imperatively loaded)
    "health_check",
    "health_check.enabled",
    "health_check.host",
    "health_check.port",
    # Metrics (imperatively loaded)
    "metrics",
    "metrics.enabled",
    "metrics.host",
    "metrics.port",
    # Storage (from STORAGE_SCHEMA)
    "storage",
    "storage.retention_days",
    "storage.db_path",
    # Alerting (imperatively loaded, many sub-keys)
    "alerting",
    "alerting.enabled",
    "alerting.webhook_url",
    "alerting.default_cooldown_sec",
    "alerting.default_sustained_sec",
    "alerting.rules",
    # CAKE optimization (for wanctl-check-cake link-dependent param checks)
    "cake_optimization",
    "cake_optimization.overhead",
    "cake_optimization.rtt",
    # Schema version
    "schema_version",
    # CAKE params (for linux-cake transport, Phase 107)
    "cake_params",
    "cake_params.upload_interface",
    "cake_params.download_interface",
    "cake_params.overhead",
    "cake_params.memlimit",
    "cake_params.rtt",
    # Signal processing (_load_signal_processing_config)
    "signal_processing",
    "signal_processing.hampel",
    "signal_processing.hampel.window_size",
    "signal_processing.hampel.sigma_threshold",
    "signal_processing.jitter_time_constant_sec",
    "signal_processing.variance_time_constant_sec",
    # IRTT measurement (_load_irtt_config)
    "irtt",
    "irtt.enabled",
    "irtt.server",
    "irtt.port",
    "irtt.duration_sec",
    "irtt.interval_ms",
    "irtt.cadence_sec",
    # Reflector quality scoring (_load_reflector_quality_config)
    "reflector_quality",
    "reflector_quality.min_score",
    "reflector_quality.window_size",
    "reflector_quality.probe_interval_sec",
    "reflector_quality.recovery_count",
    # OWD asymmetry detection (_load_owd_asymmetry_config)
    "owd_asymmetry",
    "owd_asymmetry.ratio_threshold",
    # Fusion (_load_fusion_config)
    "fusion",
    "fusion.enabled",
    "fusion.icmp_weight",
    "fusion.healing",
    "fusion.healing.suspend_threshold",
    "fusion.healing.recover_threshold",
    "fusion.healing.suspend_window_sec",
    "fusion.healing.recover_window_sec",
    "fusion.healing.grace_period_sec",
    # Adaptive tuning (_load_tuning_config)
    "tuning",
    "tuning.enabled",
    "tuning.cadence_sec",
    "tuning.lookback_hours",
    "tuning.warmup_hours",
    "tuning.max_step_pct",
    "tuning.exclude_params",
    "tuning.bounds",
    "tuning.oscillation_threshold",
    # Ping source IP (_load_timeout_config)
    "ping_source_ip",
    # Storage retention (get_storage_config in config_base.py)
    "storage.retention",
    "storage.retention.raw_age_seconds",
    "storage.retention.aggregate_1m_age_seconds",
    "storage.retention.aggregate_5m_age_seconds",
    "storage.retention.prometheus_compensated",
    # Cycle budget warning (WANController.__init__)
    "continuous_monitoring.warning_threshold_pct",
    # Hysteresis suppression alert (WANController.__init__)
    "continuous_monitoring.thresholds.suppression_alert_threshold",
}

# Comprehensive set of valid steering config paths.
# Sources: BASE_SCHEMA + SteeringConfig.SCHEMA + imperative loads in _load_specific_fields.
# This must cover ALL paths in production configs (steering.yaml)
# to avoid false-positive "unknown key" warnings.
KNOWN_STEERING_PATHS: set[str] = {
    # From BASE_SCHEMA
    "wan_name",
    "router",
    "router.host",
    "router.user",
    "router.ssh_key",
    "logging",
    "logging.main_log",
    "logging.debug_log",
    "logging.max_bytes",
    "logging.backup_count",
    "lock_file",
    "lock_timeout",
    # From SteeringConfig.SCHEMA
    "topology",
    "topology.primary_wan",
    "topology.primary_wan_config",
    "topology.alternate_wan",
    "mangle_rule",
    "mangle_rule.comment",
    "measurement",
    "measurement.interval_seconds",
    "measurement.ping_host",
    "measurement.ping_count",
    "state",
    "state.file",
    "state.history_size",
    "thresholds",
    # Thresholds -- imperatively loaded in _load_thresholds
    "thresholds.green_rtt_ms",
    "thresholds.yellow_rtt_ms",
    "thresholds.red_rtt_ms",
    "thresholds.min_drops_red",
    "thresholds.min_queue_yellow",
    "thresholds.min_queue_red",
    "thresholds.rtt_ewma_alpha",
    "thresholds.queue_ewma_alpha",
    "thresholds.red_samples_required",
    "thresholds.green_samples_required",
    # Thresholds -- baseline bounds (imperatively loaded in _load_baseline_bounds)
    "thresholds.baseline_rtt_bounds",
    "thresholds.baseline_rtt_bounds.min",
    "thresholds.baseline_rtt_bounds.max",
    # Thresholds -- used in production config and storage config_snapshot
    "thresholds.bad_threshold_ms",
    "thresholds.recovery_threshold_ms",
    # Router -- imperatively loaded in _load_router_transport
    "router.transport",
    "router.password",
    "router.port",
    "router.verify_ssl",
    # CAKE state sources -- imperatively loaded in _load_state_sources
    "cake_state_sources",
    "cake_state_sources.primary",
    # Legacy deprecated: cake_state_sources.spectrum (-> primary)
    "cake_state_sources.spectrum",
    # CAKE queues -- imperatively loaded in _load_cake_queues
    "cake_queues",
    "cake_queues.primary_download",
    "cake_queues.primary_upload",
    # Legacy deprecated: cake_queues.spectrum_download/spectrum_upload
    "cake_queues.spectrum_download",
    "cake_queues.spectrum_upload",
    # Mode -- imperatively loaded in _load_operational_mode
    "mode",
    "mode.reset_counters",
    "mode.enable_yellow_state",
    "mode.use_confidence_scoring",
    # Legacy deprecated: mode.cake_aware (removed v1.12, ignored)
    "mode.cake_aware",
    # Confidence -- imperatively loaded in _load_confidence_config
    "confidence",
    "confidence.steer_threshold",
    "confidence.recovery_threshold",
    "confidence.sustain_duration_sec",
    "confidence.recovery_sustain_sec",
    "confidence.hold_down_duration_sec",
    "confidence.flap_detection_enabled",
    "confidence.flap_window_minutes",
    "confidence.max_toggles",
    "confidence.penalty_duration_sec",
    "confidence.penalty_threshold_add",
    "confidence.dry_run",
    # WAN state -- imperatively loaded in _load_wan_state_config
    "wan_state",
    "wan_state.enabled",
    "wan_state.red_weight",
    "wan_state.staleness_threshold_sec",
    "wan_state.grace_period_sec",
    "wan_state.wan_override",
    # Capacity protection (future, present in production config)
    "capacity_protection",
    "capacity_protection.att_upload_reserve_mbps",
    "capacity_protection.att_download_reserve_mbps",
    # Timeouts -- imperatively loaded in _load_timeouts
    "timeouts",
    "timeouts.ssh_command",
    "timeouts.ping",
    "timeouts.ping_total",
    # Logging -- steering-specific (log_cake_stats)
    "logging.log_cake_stats",
    # Health check -- imperatively loaded in _load_health_check_config
    "health_check",
    "health_check.enabled",
    "health_check.host",
    "health_check.port",
    # Metrics -- imperatively loaded in _load_metrics_config
    "metrics",
    "metrics.enabled",
    # Storage (from STORAGE_SCHEMA, shared)
    "storage",
    "storage.retention_days",
    "storage.db_path",
    # Alerting -- imperatively loaded in _load_alerting_config
    "alerting",
    "alerting.enabled",
    "alerting.webhook_url",
    "alerting.default_cooldown_sec",
    "alerting.default_sustained_sec",
    "alerting.rules",
    "alerting.mention_role_id",
    "alerting.mention_severity",
    "alerting.max_webhooks_per_minute",
    # Schema version
    "schema_version",
}

# Regex for detecting environment variable references in string values
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Default hard_red_bloat_ms (matches daemon constant)
_DEFAULT_HARD_RED_BLOAT_MS = 80

# ANSI color codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

# Cycle interval for alpha->time_constant conversion
_CYCLE_INTERVAL = 0.05


# =============================================================================
# CATEGORY VALIDATORS
# =============================================================================


def validate_schema_fields(data: dict) -> list[CheckResult]:
    """Validate individual schema fields from BASE_SCHEMA + Config.SCHEMA.

    Iterates each field spec and validates independently, collecting
    PASS/ERROR results per field. Never short-circuits.
    """
    results: list[CheckResult] = []
    combined_schema = BaseConfig.BASE_SCHEMA + Config.SCHEMA

    for field_spec in combined_schema:
        path = field_spec["path"]
        try:
            validate_field(
                data,
                path,
                field_spec.get("type", str),
                field_spec.get("required", True),
                field_spec.get("min"),
                field_spec.get("max"),
                field_spec.get("choices"),
                field_spec.get("default"),
            )
            results.append(CheckResult("Schema Validation", path, Severity.PASS, f"{path}: valid"))
        except ConfigValidationError as e:
            results.append(CheckResult("Schema Validation", path, Severity.ERROR, str(e)))

    return results


def validate_cross_fields(data: dict) -> list[CheckResult]:
    """Validate cross-field constraints: floor ordering, thresholds, ceiling >= floor.

    Checks download (4-state), upload (3-state), and threshold ordering.
    Handles both legacy single-floor and modern multi-floor formats.
    """
    results: list[CheckResult] = []
    cm = data.get("continuous_monitoring", {})

    # --- Download floor ordering ---
    dl = cm.get("download", {})
    if dl:
        ceiling = dl.get("ceiling_mbps")
        if ceiling is not None:
            if "floor_green_mbps" in dl:
                # Modern multi-floor format
                floor_green = dl.get("floor_green_mbps")
                floor_yellow = dl.get("floor_yellow_mbps")
                floor_soft_red = dl.get("floor_soft_red_mbps", floor_yellow)
                floor_red = dl.get("floor_red_mbps")
            elif "floor_mbps" in dl:
                # Legacy single-floor format
                floor = dl["floor_mbps"]
                floor_green = floor
                floor_yellow = floor
                floor_soft_red = floor
                floor_red = floor
            else:
                floor_green = floor_yellow = floor_soft_red = floor_red = None

            if floor_red is not None:
                try:
                    validate_bandwidth_order(
                        name="download",
                        floor_red=floor_red,
                        floor_soft_red=floor_soft_red,
                        floor_yellow=floor_yellow,
                        floor_green=floor_green,
                        ceiling=ceiling,
                    )
                    results.append(
                        CheckResult(
                            "Cross-field Checks",
                            "download.floors",
                            Severity.PASS,
                            "Download floor ordering: valid",
                        )
                    )
                except ConfigValidationError as e:
                    results.append(
                        CheckResult(
                            "Cross-field Checks",
                            "download.floors",
                            Severity.ERROR,
                            str(e),
                        )
                    )

    # --- Upload floor ordering ---
    ul = cm.get("upload", {})
    if ul:
        ceiling = ul.get("ceiling_mbps")
        if ceiling is not None:
            if "floor_green_mbps" in ul:
                floor_green = ul.get("floor_green_mbps")
                floor_yellow = ul.get("floor_yellow_mbps")
                floor_red = ul.get("floor_red_mbps")
            elif "floor_mbps" in ul:
                floor = ul["floor_mbps"]
                floor_green = floor
                floor_yellow = floor
                floor_red = floor
            else:
                floor_green = floor_yellow = floor_red = None

            if floor_red is not None:
                try:
                    validate_bandwidth_order(
                        name="upload",
                        floor_red=floor_red,
                        floor_yellow=floor_yellow,
                        floor_green=floor_green,
                        ceiling=ceiling,
                    )
                    results.append(
                        CheckResult(
                            "Cross-field Checks",
                            "upload.floors",
                            Severity.PASS,
                            "Upload floor ordering: valid",
                        )
                    )
                except ConfigValidationError as e:
                    results.append(
                        CheckResult(
                            "Cross-field Checks",
                            "upload.floors",
                            Severity.ERROR,
                            str(e),
                        )
                    )

    # --- Threshold ordering ---
    thresholds = cm.get("thresholds", {})
    target = thresholds.get("target_bloat_ms")
    warn = thresholds.get("warn_bloat_ms")
    hard_red = thresholds.get("hard_red_bloat_ms", _DEFAULT_HARD_RED_BLOAT_MS)

    if target is not None and warn is not None:
        try:
            validate_threshold_order(
                target_bloat_ms=float(target),
                warn_bloat_ms=float(warn),
                hard_red_bloat_ms=float(hard_red),
            )
            results.append(
                CheckResult(
                    "Cross-field Checks",
                    "thresholds",
                    Severity.PASS,
                    "Threshold ordering: valid",
                )
            )
        except ConfigValidationError as e:
            results.append(CheckResult("Cross-field Checks", "thresholds", Severity.ERROR, str(e)))

    # --- Transport / cake_params consistency ---
    transport = _get_nested(data, "router.transport", "rest")
    has_cake_params = isinstance(data.get("cake_params"), dict)

    if has_cake_params and transport != "linux-cake":
        results.append(
            CheckResult(
                "Cross-field Checks",
                "transport_mismatch",
                Severity.ERROR,
                f"cake_params section present but transport is '{transport}' (not 'linux-cake'). "
                "CAKE qdiscs will NOT be created at startup. Set router.transport to 'linux-cake'.",
                suggestion="Change router.transport to 'linux-cake' in YAML config",
            )
        )
    elif transport == "linux-cake" and not has_cake_params:
        results.append(
            CheckResult(
                "Cross-field Checks",
                "transport_mismatch",
                Severity.ERROR,
                "transport is 'linux-cake' but cake_params section is missing. "
                "CAKE qdiscs cannot be initialized without interface names.",
                suggestion="Add cake_params with download_interface and upload_interface",
            )
        )

    return results


def _walk_leaf_paths(data: dict, prefix: str = "") -> list[str]:
    """Walk a config dict and return all leaf paths (dot-notation)."""
    paths: list[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.append(path)
        if isinstance(value, dict):
            paths.extend(_walk_leaf_paths(value, path))
    return paths


def check_unknown_keys(data: dict) -> list[CheckResult]:
    """Detect unknown config keys with fuzzy match suggestions.

    Walks all paths in the config and compares against KNOWN_AUTORATE_PATHS.
    Sub-keys under alerting.rules are skipped (dynamic per-alert-type).
    """
    results: list[CheckResult] = []
    all_paths = _walk_leaf_paths(data)

    for path in all_paths:
        # Skip deep validation under alerting.rules (dynamic per-alert-type keys)
        if path.startswith("alerting.rules."):
            continue

        if path not in KNOWN_AUTORATE_PATHS:
            # Try fuzzy match
            matches = difflib.get_close_matches(path, KNOWN_AUTORATE_PATHS, n=1, cutoff=0.6)
            suggestion = f"did you mean: {matches[0]}?" if matches else None
            results.append(
                CheckResult(
                    "Unknown Keys",
                    path,
                    Severity.WARN,
                    f"Unknown config key: {path}",
                    suggestion=suggestion,
                )
            )

    return results


def check_paths(data: dict) -> list[CheckResult]:
    """Verify file paths and directories referenced in config.

    Checks log directory parents, state file parent, SSH key existence
    and permissions.
    """
    results: list[CheckResult] = []
    transport = _get_nested(data, "router.transport", "rest")

    # Log directory checks
    for log_path_key in ["logging.main_log", "logging.debug_log"]:
        log_path = _get_nested(data, log_path_key)
        if log_path and isinstance(log_path, str):
            parent = Path(log_path).parent
            if parent.exists():
                results.append(
                    CheckResult(
                        "File Paths",
                        log_path_key,
                        Severity.PASS,
                        f"{log_path_key}: parent directory exists ({parent})",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "File Paths",
                        log_path_key,
                        Severity.ERROR,
                        f"{log_path_key}: parent directory missing ({parent})",
                        suggestion=f"mkdir -p {parent}",
                    )
                )

    # State file parent check
    state_file = _get_nested(data, "state_file")
    if state_file and isinstance(state_file, str):
        parent = Path(state_file).parent
        if parent.exists():
            results.append(
                CheckResult(
                    "File Paths",
                    "state_file",
                    Severity.PASS,
                    f"state_file: parent directory exists ({parent})",
                )
            )
        else:
            results.append(
                CheckResult(
                    "File Paths",
                    "state_file",
                    Severity.ERROR,
                    f"state_file: parent directory missing ({parent})",
                    suggestion=f"mkdir -p {parent}",
                )
            )

    # SSH key check
    ssh_key = _get_nested(data, "router.ssh_key")
    if ssh_key and isinstance(ssh_key, str):
        key_path = Path(ssh_key)
        if not key_path.exists():
            # For REST transport, SSH key missing is informational (PASS)
            if transport == "rest":
                results.append(
                    CheckResult(
                        "File Paths",
                        "router.ssh_key",
                        Severity.PASS,
                        f"router.ssh_key: not found ({ssh_key}) -- REST transport, SSH key optional",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "File Paths",
                        "router.ssh_key",
                        Severity.ERROR,
                        f"router.ssh_key: file not found ({ssh_key})",
                    )
                )
        else:
            mode = key_path.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                results.append(
                    CheckResult(
                        "File Paths",
                        "router.ssh_key",
                        Severity.WARN,
                        f"router.ssh_key: insecure permissions ({oct(mode & 0o777)})",
                        suggestion=f"chmod 600 {ssh_key}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "File Paths",
                        "router.ssh_key",
                        Severity.PASS,
                        "router.ssh_key: exists with secure permissions",
                    )
                )

    return results


def _walk_string_values(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Walk config dict returning (path, value) pairs for string values."""
    pairs: list[tuple[str, str]] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, str):
            pairs.append((path, value))
        elif isinstance(value, dict):
            pairs.extend(_walk_string_values(value, path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    pairs.append((f"{path}[{i}]", item))
    return pairs


def check_env_vars(data: dict) -> list[CheckResult]:
    """Scan string values for ${VAR} references and check environment.

    WARN when referenced env var is not set in current environment.
    PASS when it is set.
    """
    results: list[CheckResult] = []

    for path, value in _walk_string_values(data):
        match = _ENV_VAR_PATTERN.search(value)
        if match:
            var_name = match.group(1)
            if var_name in os.environ:
                results.append(
                    CheckResult(
                        "Environment Variables",
                        path,
                        Severity.PASS,
                        f"{path}: ${{{var_name}}} is set",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "Environment Variables",
                        path,
                        Severity.WARN,
                        f"{path}: ${{{var_name}}} is not set in current environment",
                        suggestion="Set before running daemon, or check deployment environment",
                    )
                )

    return results


def check_deprecated_params(data: dict) -> list[CheckResult]:
    """Detect deprecated parameters and show translation.

    Checks for alpha_baseline and alpha_load in thresholds section.
    Shows WARN with the translated time constant value.
    Does NOT modify the config dict.
    """
    results: list[CheckResult] = []
    thresholds = _get_nested(data, "continuous_monitoring.thresholds")
    if not thresholds or not isinstance(thresholds, dict):
        return results

    # Deprecated alpha_baseline -> baseline_time_constant_sec
    if "alpha_baseline" in thresholds and "baseline_time_constant_sec" not in thresholds:
        old_value = thresholds["alpha_baseline"]
        try:
            translated = round(_CYCLE_INTERVAL / float(old_value), 1)
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "continuous_monitoring.thresholds.alpha_baseline",
                    Severity.WARN,
                    f"alpha_baseline is deprecated -> use baseline_time_constant_sec instead "
                    f"(auto-translated: {old_value} -> {translated}s)",
                )
            )
        except (ValueError, ZeroDivisionError, TypeError):
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "continuous_monitoring.thresholds.alpha_baseline",
                    Severity.WARN,
                    f"alpha_baseline is deprecated -> use baseline_time_constant_sec instead "
                    f"(could not auto-translate value: {old_value})",
                )
            )

    # Deprecated alpha_load -> load_time_constant_sec
    if "alpha_load" in thresholds and "load_time_constant_sec" not in thresholds:
        old_value = thresholds["alpha_load"]
        try:
            translated = round(_CYCLE_INTERVAL / float(old_value), 1)
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "continuous_monitoring.thresholds.alpha_load",
                    Severity.WARN,
                    f"alpha_load is deprecated -> use load_time_constant_sec instead "
                    f"(auto-translated: {old_value} -> {translated}s)",
                )
            )
        except (ValueError, ZeroDivisionError, TypeError):
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "continuous_monitoring.thresholds.alpha_load",
                    Severity.WARN,
                    f"alpha_load is deprecated -> use load_time_constant_sec instead "
                    f"(could not auto-translate value: {old_value})",
                )
            )

    return results


# =============================================================================
# CONFIG TYPE DETECTION
# =============================================================================


def detect_config_type(data: dict) -> str:
    """Detect config type from YAML contents.

    Returns:
        "autorate" or "steering"

    Raises:
        ValueError: If detection is ambiguous (both keys) or unknown (neither key).
    """
    has_topology = "topology" in data
    has_continuous = "continuous_monitoring" in data

    if has_topology and has_continuous:
        raise ValueError(
            "ambiguous config type: contains both 'topology' and 'continuous_monitoring' keys. "
            "Use --type autorate|steering"
        )
    if has_topology:
        return "steering"
    if has_continuous:
        return "autorate"
    raise ValueError(
        "could not determine config type: no 'topology' or 'continuous_monitoring' key found. "
        "Use --type autorate|steering"
    )


# =============================================================================
# STEERING VALIDATORS
# =============================================================================


def validate_steering_schema_fields(data: dict) -> list[CheckResult]:
    """Validate individual schema fields from BASE_SCHEMA + SteeringConfig.SCHEMA.

    Uses the same validate_field pattern as autorate schema validation.
    """
    results: list[CheckResult] = []
    combined_schema = BaseConfig.BASE_SCHEMA + SteeringConfig.SCHEMA

    for field_spec in combined_schema:
        path = field_spec["path"]
        try:
            validate_field(
                data,
                path,
                field_spec.get("type", str),
                field_spec.get("required", True),
                field_spec.get("min"),
                field_spec.get("max"),
                field_spec.get("choices"),
                field_spec.get("default"),
            )
            results.append(CheckResult("Schema Validation", path, Severity.PASS, f"{path}: valid"))
        except ConfigValidationError as e:
            results.append(CheckResult("Schema Validation", path, Severity.ERROR, str(e)))

    return results


def validate_steering_cross_fields(data: dict) -> list[CheckResult]:
    """Validate steering-specific cross-field constraints.

    Checks confidence threshold ordering, measurement interval range,
    and state history window duration.
    """
    results: list[CheckResult] = []

    # Confidence threshold ordering: recovery_threshold < steer_threshold
    confidence = data.get("confidence", {})
    mode = data.get("mode", {})
    if mode.get("use_confidence_scoring") and confidence:
        steer = confidence.get("steer_threshold", 55)
        recovery = confidence.get("recovery_threshold", 20)
        if isinstance(steer, (int, float)) and isinstance(recovery, (int, float)):
            if recovery >= steer:
                results.append(
                    CheckResult(
                        "Cross-field Checks",
                        "confidence.thresholds",
                        Severity.ERROR,
                        f"confidence.recovery_threshold ({recovery}) must be less than "
                        f"steer_threshold ({steer})",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "Cross-field Checks",
                        "confidence.thresholds",
                        Severity.PASS,
                        f"Confidence threshold ordering: valid "
                        f"(recovery={recovery} < steer={steer})",
                    )
                )

    # measurement.interval_seconds range (semantic check beyond schema min/max)
    measurement = data.get("measurement", {})
    interval = measurement.get("interval_seconds")
    if interval is not None and isinstance(interval, (int, float)):
        if interval < 0.05:
            results.append(
                CheckResult(
                    "Cross-field Checks",
                    "measurement.interval_seconds",
                    Severity.WARN,
                    f"measurement.interval_seconds ({interval}) is below autorate cycle "
                    f"interval (0.05s) -- steering may miss events",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Cross-field Checks",
                    "measurement.interval_seconds",
                    Severity.PASS,
                    f"measurement.interval_seconds ({interval}s): valid",
                )
            )

    # state.history_size relative to interval
    state = data.get("state", {})
    history_size = state.get("history_size")
    if history_size is not None and interval is not None:
        if isinstance(interval, (int, float)) and isinstance(history_size, (int, float)):
            window_sec = history_size * interval
            if window_sec < 30:
                results.append(
                    CheckResult(
                        "Cross-field Checks",
                        "state.history_size",
                        Severity.WARN,
                        f"state.history_size ({history_size}) x interval ({interval}s) = "
                        f"{window_sec:.0f}s window -- less than 30s may cause unstable steering",
                    )
                )

    return results


def check_steering_unknown_keys(data: dict) -> list[CheckResult]:
    """Detect unknown steering config keys with fuzzy match suggestions.

    Walks all paths in the config and compares against KNOWN_STEERING_PATHS.
    Sub-keys under alerting.rules are skipped (dynamic per-alert-type).
    """
    results: list[CheckResult] = []
    all_paths = _walk_leaf_paths(data)

    for path in all_paths:
        # Skip deep validation under alerting.rules (dynamic per-alert-type keys)
        if path.startswith("alerting.rules."):
            continue

        if path not in KNOWN_STEERING_PATHS:
            # Try fuzzy match
            matches = difflib.get_close_matches(path, KNOWN_STEERING_PATHS, n=1, cutoff=0.6)
            suggestion = f"did you mean: {matches[0]}?" if matches else None
            results.append(
                CheckResult(
                    "Unknown Keys",
                    path,
                    Severity.WARN,
                    f"Unknown config key: {path}",
                    suggestion=suggestion,
                )
            )

    return results


def check_steering_deprecated_params(data: dict) -> list[CheckResult]:
    """Detect deprecated steering parameters.

    Checks for mode.cake_aware (removed v1.12), cake_state_sources.spectrum
    (-> primary), and cake_queues.spectrum_download/upload (-> primary_*).
    """
    results: list[CheckResult] = []

    # mode.cake_aware -- removed in v1.12, always active
    mode = data.get("mode", {})
    if isinstance(mode, dict) and "cake_aware" in mode:
        results.append(
            CheckResult(
                "Deprecated Parameters",
                "mode.cake_aware",
                Severity.WARN,
                "mode.cake_aware is deprecated -- CAKE three-state model is always active, "
                "this key is ignored",
                suggestion="Remove mode.cake_aware from config",
            )
        )

    # cake_state_sources.spectrum -> primary
    sources = data.get("cake_state_sources", {})
    if isinstance(sources, dict) and "spectrum" in sources:
        results.append(
            CheckResult(
                "Deprecated Parameters",
                "cake_state_sources.spectrum",
                Severity.WARN,
                "cake_state_sources.spectrum is deprecated -> use cake_state_sources.primary",
            )
        )

    # cake_queues.spectrum_download -> primary_download
    queues = data.get("cake_queues", {})
    if isinstance(queues, dict):
        if "spectrum_download" in queues:
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "cake_queues.spectrum_download",
                    Severity.WARN,
                    "cake_queues.spectrum_download is deprecated -> use cake_queues.primary_download",
                )
            )
        if "spectrum_upload" in queues:
            results.append(
                CheckResult(
                    "Deprecated Parameters",
                    "cake_queues.spectrum_upload",
                    Severity.WARN,
                    "cake_queues.spectrum_upload is deprecated -> use cake_queues.primary_upload",
                )
            )

    return results


def check_steering_cross_config(data: dict) -> list[CheckResult]:
    """Validate cross-config references in steering config.

    Checks that topology.primary_wan_config file exists and that its
    wan_name matches topology.primary_wan. File existence is WARN (dev
    machine may not have other config). wan_name mismatch is ERROR.
    """
    results: list[CheckResult] = []
    primary_wan_config = _get_nested(data, "topology.primary_wan_config")
    primary_wan = _get_nested(data, "topology.primary_wan")

    if not primary_wan_config or not isinstance(primary_wan_config, str):
        return results  # Schema validation already catches missing required field

    try:
        config_path = Path(primary_wan_config)
        if not config_path.exists():
            results.append(
                CheckResult(
                    "Cross-config Checks",
                    "topology.primary_wan_config",
                    Severity.WARN,
                    f"topology.primary_wan_config: file not found ({primary_wan_config})",
                    suggestion="Verify path is correct or run on the deployment machine",
                )
            )
            return results

        # File exists -- parse and check wan_name
        results.append(
            CheckResult(
                "Cross-config Checks",
                "topology.primary_wan_config",
                Severity.PASS,
                f"topology.primary_wan_config: file exists ({primary_wan_config})",
            )
        )

        try:
            with open(config_path) as f:
                ref_data = yaml.safe_load(f)
            if not isinstance(ref_data, dict):
                results.append(
                    CheckResult(
                        "Cross-config Checks",
                        "topology.primary_wan_config",
                        Severity.WARN,
                        "topology.primary_wan_config: referenced file is not a valid YAML mapping",
                    )
                )
                return results

            ref_wan_name = ref_data.get("wan_name")
            if ref_wan_name is None:
                results.append(
                    CheckResult(
                        "Cross-config Checks",
                        "wan_name match",
                        Severity.WARN,
                        f"Referenced config ({primary_wan_config}) has no wan_name field",
                    )
                )
            elif ref_wan_name == primary_wan:
                results.append(
                    CheckResult(
                        "Cross-config Checks",
                        "wan_name match",
                        Severity.PASS,
                        f"wan_name match: topology.primary_wan '{primary_wan}' matches "
                        f"referenced config wan_name '{ref_wan_name}'",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "Cross-config Checks",
                        "wan_name match",
                        Severity.ERROR,
                        f"wan_name mismatch: topology.primary_wan is '{primary_wan}' but "
                        f"referenced config ({primary_wan_config}) has wan_name '{ref_wan_name}'",
                        suggestion=f"Change topology.primary_wan to '{ref_wan_name}' "
                        f"or update the referenced config",
                    )
                )
        except yaml.YAMLError:
            results.append(
                CheckResult(
                    "Cross-config Checks",
                    "topology.primary_wan_config",
                    Severity.WARN,
                    f"topology.primary_wan_config: could not parse referenced file "
                    f"({primary_wan_config})",
                )
            )
    except (PermissionError, UnicodeDecodeError, OSError) as e:
        results.append(
            CheckResult(
                "Cross-config Checks",
                "topology.primary_wan_config",
                Severity.WARN,
                f"topology.primary_wan_config: could not read referenced file "
                f"({primary_wan_config}): {e}",
            )
        )

    return results


def validate_linux_cake(data: dict) -> list[CheckResult]:
    """Validate linux-cake transport-specific settings (CONF-04).

    Only runs when router.transport is "linux-cake". Validates:
    1. cake_params section exists and is a dict
    2. upload_interface and download_interface are non-empty strings
    3. overhead keyword (if present) is in VALID_OVERHEAD_KEYWORDS
    4. tc binary exists on PATH (WARN, not ERROR -- offline validator)
    """
    results: list[CheckResult] = []
    transport = _get_nested(data, "router.transport", "rest")
    if transport != "linux-cake":
        return results

    # 1. cake_params section
    cake_params = data.get("cake_params")
    if not isinstance(cake_params, dict):
        results.append(
            CheckResult(
                "Linux CAKE",
                "cake_params",
                Severity.ERROR,
                "cake_params section required when router.transport is 'linux-cake'",
                suggestion="Add cake_params with upload_interface and download_interface",
            )
        )
        return results  # Can't validate sub-fields

    # 2. Required interface fields
    for field in ("upload_interface", "download_interface"):
        value = cake_params.get(field)
        if not value or not isinstance(value, str):
            results.append(
                CheckResult(
                    "Linux CAKE",
                    f"cake_params.{field}",
                    Severity.ERROR,
                    f"cake_params.{field} is required (non-empty string)",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Linux CAKE",
                    f"cake_params.{field}",
                    Severity.PASS,
                    f"cake_params.{field}: {value}",
                )
            )

    # 3. Overhead keyword validation (optional field)
    overhead = cake_params.get("overhead")
    if overhead is not None:
        from wanctl.cake_params import VALID_OVERHEAD_KEYWORDS

        if overhead not in VALID_OVERHEAD_KEYWORDS:
            results.append(
                CheckResult(
                    "Linux CAKE",
                    "cake_params.overhead",
                    Severity.ERROR,
                    f"Invalid overhead keyword: {overhead!r}",
                    suggestion=f"Valid: {sorted(VALID_OVERHEAD_KEYWORDS)}",
                )
            )

    # 4. tc binary existence (WARN, not ERROR -- D-08, offline validator)
    import shutil

    if shutil.which("tc"):
        results.append(
            CheckResult(
                "Linux CAKE",
                "tc binary",
                Severity.PASS,
                "tc binary found on PATH",
            )
        )
    else:
        results.append(
            CheckResult(
                "Linux CAKE",
                "tc binary",
                Severity.WARN,
                "tc binary not found on PATH",
                suggestion="Install iproute2 or verify PATH includes /usr/sbin",
            )
        )

    return results


# =============================================================================
# VALIDATOR DISPATCHERS
# =============================================================================


def _run_autorate_validators(data: dict) -> list[CheckResult]:
    """Run all autorate-specific validators."""
    results: list[CheckResult] = []
    results.extend(validate_schema_fields(data))
    results.extend(validate_cross_fields(data))
    results.extend(check_unknown_keys(data))
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_deprecated_params(data))
    results.extend(validate_linux_cake(data))
    return results


def _run_steering_validators(data: dict) -> list[CheckResult]:
    """Run all steering-specific validators."""
    results: list[CheckResult] = []
    results.extend(validate_steering_schema_fields(data))
    results.extend(validate_steering_cross_fields(data))
    results.extend(check_steering_unknown_keys(data))
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_steering_deprecated_params(data))
    results.extend(check_steering_cross_config(data))
    return results


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def _use_color(no_color: bool) -> bool:
    """Determine whether to use ANSI color codes."""
    if no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _marker(severity: Severity, color: bool) -> str:
    """Get the display marker for a severity level."""
    if color:
        markers = {
            Severity.PASS: f"{_GREEN}\u2713 PASS{_RESET}",
            Severity.WARN: f"{_YELLOW}\u26a0 WARN{_RESET}",
            Severity.ERROR: f"{_RED}\u2717 FAIL{_RESET}",
        }
    else:
        markers = {
            Severity.PASS: "\u2713 PASS",
            Severity.WARN: "\u26a0 WARN",
            Severity.ERROR: "\u2717 FAIL",
        }
    return markers[severity]


def format_results(
    results: list[CheckResult],
    no_color: bool = False,
    quiet: bool = False,
    config_type: str = "autorate",
) -> str:
    """Format validation results grouped by category.

    Args:
        results: List of CheckResult from all validators.
        no_color: Disable ANSI color codes.
        quiet: Suppress PASS results.
        config_type: Config type label for summary line.

    Returns:
        Formatted string for printing.
    """
    color = _use_color(no_color)
    lines: list[str] = []

    # Group by category preserving insertion order
    categories: dict[str, list[CheckResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    for cat_name, cat_results in categories.items():
        # Category header
        if color:
            lines.append(f"\n{_BOLD}=== {cat_name} ==={_RESET}")
        else:
            lines.append(f"\n=== {cat_name} ===")

        has_visible = False
        for r in cat_results:
            if quiet and r.severity == Severity.PASS:
                continue
            has_visible = True
            marker = _marker(r.severity, color)
            lines.append(f"  {marker}  {r.message}")
            if r.suggestion:
                lines.append(f"         -> {r.suggestion}")

        if not has_visible:
            lines.append("  (all checks passed)")

    # Summary line
    error_count = sum(1 for r in results if r.severity == Severity.ERROR)
    warn_count = sum(1 for r in results if r.severity == Severity.WARN)
    type_label = f"{config_type} config"

    if error_count > 0:
        summary_word = "FAIL"
    elif warn_count > 0:
        summary_word = "WARN"
    else:
        summary_word = "PASS"

    summary = (
        f"\nResult: {summary_word} ({type_label}) ({error_count} errors, {warn_count} warnings)"
    )
    if color:
        if error_count > 0:
            summary = (
                f"\n{_RED}{_BOLD}Result: FAIL{_RESET} ({type_label}) "
                f"({error_count} errors, {warn_count} warnings)"
            )
        elif warn_count > 0:
            summary = (
                f"\n{_YELLOW}{_BOLD}Result: WARN{_RESET} ({type_label}) ({warn_count} warnings)"
            )
        else:
            summary = (
                f"\n{_GREEN}{_BOLD}Result: PASS{_RESET} ({type_label}) (no errors, no warnings)"
            )
    lines.append(summary)

    return "\n".join(lines)


def format_results_json(results: list[CheckResult], config_type: str) -> str:
    """Format validation results as JSON for CI/scripting.

    Returns a JSON string with config_type, result word, error/warning counts,
    and all results grouped by category. All results are included (pass, warn,
    error) regardless of any --quiet flag. No ANSI codes are emitted.

    Args:
        results: List of CheckResult from all validators.
        config_type: Detected or overridden config type ("autorate" or "steering").

    Returns:
        JSON string (indented for readability).
    """
    error_count = sum(1 for r in results if r.severity == Severity.ERROR)
    warn_count = sum(1 for r in results if r.severity == Severity.WARN)

    if error_count > 0:
        result_word = "FAIL"
    elif warn_count > 0:
        result_word = "WARN"
    else:
        result_word = "PASS"

    # Group results by category preserving insertion order
    categories: dict[str, list[dict]] = {}
    for r in results:
        check: dict = {
            "field": r.field,
            "severity": r.severity.value,
            "message": r.message,
        }
        if r.suggestion is not None:
            check["suggestion"] = r.suggestion
        categories.setdefault(r.category, []).append(check)

    output = {
        "config_type": config_type,
        "result": result_word,
        "errors": error_count,
        "warnings": warn_count,
        "categories": categories,
    }
    return json.dumps(output, indent=2)


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="wanctl-check-config",
        description="Validate wanctl configuration files offline (autorate and steering)",
    )
    parser.add_argument("config_file", help="Path to YAML config file")
    parser.add_argument(
        "--type",
        choices=["autorate", "steering"],
        default=None,
        help="Override auto-detection of config type",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show warnings and errors")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    return parser


def main() -> int:
    """Main entry point for wanctl-check-config CLI.

    Returns:
        Exit code: 0=pass, 1=errors, 2=warnings-only
    """
    parser = create_parser()
    args = parser.parse_args()

    # Load YAML
    config_path = args.config_file
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML in {config_path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(
            f"Error: config file must contain a YAML mapping, got {type(data).__name__}",
            file=sys.stderr,
        )
        return 1

    # Determine config type
    if args.type:
        config_type = args.type
    else:
        try:
            config_type = detect_config_type(data)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Dispatch validators based on config type
    if config_type == "steering":
        results = _run_steering_validators(data)
    else:
        results = _run_autorate_validators(data)

    # Format and print
    if args.json:
        output = format_results_json(results, config_type=config_type)
    else:
        output = format_results(
            results, no_color=args.no_color, quiet=args.quiet, config_type=config_type
        )
    print(output)

    # Determine exit code
    has_errors = any(r.severity == Severity.ERROR for r in results)
    has_warnings = any(r.severity == Severity.WARN for r in results)

    if has_errors:
        return 1
    if has_warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

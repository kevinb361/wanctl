"""Autorate configuration validation functions.

Contains validator functions for autorate config files: schema validation,
cross-field checks, unknown key detection, path validation, environment
variable checks, and deprecated parameter warnings. Also defines the
KNOWN_AUTORATE_PATHS registry of valid config paths.
"""

import difflib
import os
import re
import stat
from pathlib import Path

from wanctl.autorate_config import Config
from wanctl.check_config import CheckResult, Severity
from wanctl.config_base import BaseConfig, ConfigValidationError, _get_nested, validate_field
from wanctl.config_validation_utils import validate_bandwidth_order, validate_threshold_order

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
    "continuous_monitoring.thresholds.suppression_alert_pct",
}

# Regex for detecting environment variable references in string values
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Default hard_red_bloat_ms (matches daemon constant)
_DEFAULT_HARD_RED_BLOAT_MS = 80

# Cycle interval for alpha->time_constant conversion
_CYCLE_INTERVAL = 0.05


# =============================================================================
# AUTORATE VALIDATORS
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

    results.extend(_validate_download_floors(cm))
    results.extend(_validate_upload_floors(cm))
    results.extend(_validate_threshold_ordering(cm))
    results.extend(_validate_transport_consistency(data))

    return results


def _validate_download_floors(cm: dict) -> list[CheckResult]:
    """Validate download floor ordering (4-state: red <= soft_red <= yellow <= green <= ceiling)."""
    dl = cm.get("download", {})
    if not dl:
        return []
    ceiling = dl.get("ceiling_mbps")
    if ceiling is None:
        return []

    if "floor_green_mbps" in dl:
        floor_green = dl.get("floor_green_mbps")
        floor_yellow = dl.get("floor_yellow_mbps")
        floor_soft_red = dl.get("floor_soft_red_mbps", floor_yellow)
        floor_red = dl.get("floor_red_mbps")
    elif "floor_mbps" in dl:
        floor = dl["floor_mbps"]
        floor_green = floor_yellow = floor_soft_red = floor_red = floor
    else:
        return []

    if floor_red is None:
        return []

    try:
        validate_bandwidth_order(
            name="download", floor_red=floor_red, floor_soft_red=floor_soft_red,
            floor_yellow=floor_yellow, floor_green=floor_green, ceiling=ceiling,
        )
        return [CheckResult("Cross-field Checks", "download.floors", Severity.PASS, "Download floor ordering: valid")]
    except ConfigValidationError as e:
        return [CheckResult("Cross-field Checks", "download.floors", Severity.ERROR, str(e))]


def _validate_upload_floors(cm: dict) -> list[CheckResult]:
    """Validate upload floor ordering (3-state: red <= yellow <= green <= ceiling)."""
    ul = cm.get("upload", {})
    if not ul:
        return []
    ceiling = ul.get("ceiling_mbps")
    if ceiling is None:
        return []

    if "floor_green_mbps" in ul:
        floor_green = ul.get("floor_green_mbps")
        floor_yellow = ul.get("floor_yellow_mbps")
        floor_red = ul.get("floor_red_mbps")
    elif "floor_mbps" in ul:
        floor = ul["floor_mbps"]
        floor_green = floor_yellow = floor_red = floor
    else:
        return []

    if floor_red is None:
        return []

    try:
        validate_bandwidth_order(
            name="upload", floor_red=floor_red, floor_yellow=floor_yellow,
            floor_green=floor_green, ceiling=ceiling,
        )
        return [CheckResult("Cross-field Checks", "upload.floors", Severity.PASS, "Upload floor ordering: valid")]
    except ConfigValidationError as e:
        return [CheckResult("Cross-field Checks", "upload.floors", Severity.ERROR, str(e))]


def _validate_threshold_ordering(cm: dict) -> list[CheckResult]:
    """Validate threshold ordering: target < warn < hard_red."""
    thresholds = cm.get("thresholds", {})
    target = thresholds.get("target_bloat_ms")
    warn = thresholds.get("warn_bloat_ms")
    hard_red = thresholds.get("hard_red_bloat_ms", _DEFAULT_HARD_RED_BLOAT_MS)

    if target is None or warn is None:
        return []

    try:
        validate_threshold_order(
            target_bloat_ms=float(target), warn_bloat_ms=float(warn), hard_red_bloat_ms=float(hard_red),
        )
        return [CheckResult("Cross-field Checks", "thresholds", Severity.PASS, "Threshold ordering: valid")]
    except ConfigValidationError as e:
        return [CheckResult("Cross-field Checks", "thresholds", Severity.ERROR, str(e))]


def _validate_transport_consistency(data: dict) -> list[CheckResult]:
    """Validate transport/cake_params consistency."""
    transport = _get_nested(data, "router.transport", "rest")
    has_cake_params = isinstance(data.get("cake_params"), dict)

    if has_cake_params and transport != "linux-cake":
        return [CheckResult(
            "Cross-field Checks", "transport_mismatch", Severity.ERROR,
            f"cake_params section present but transport is '{transport}' (not 'linux-cake'). "
            "CAKE qdiscs will NOT be created at startup. Set router.transport to 'linux-cake'.",
            suggestion="Change router.transport to 'linux-cake' in YAML config",
        )]
    if transport == "linux-cake" and not has_cake_params:
        return [CheckResult(
            "Cross-field Checks", "transport_mismatch", Severity.ERROR,
            "transport is 'linux-cake' but cake_params section is missing. "
            "CAKE qdiscs cannot be initialized without interface names.",
            suggestion="Add cake_params with download_interface and upload_interface",
        )]
    return []


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

    results.extend(_check_log_paths(data))
    results.extend(_check_state_file_path(data))
    results.extend(_check_ssh_key_path(data, transport))

    return results


def _check_parent_dir(key: str, path_str: str) -> CheckResult:
    """Check if a path's parent directory exists."""
    parent = Path(path_str).parent
    if parent.exists():
        return CheckResult("File Paths", key, Severity.PASS, f"{key}: parent directory exists ({parent})")
    return CheckResult(
        "File Paths", key, Severity.ERROR,
        f"{key}: parent directory missing ({parent})", suggestion=f"mkdir -p {parent}",
    )


def _check_log_paths(data: dict) -> list[CheckResult]:
    """Check log file parent directories exist."""
    results: list[CheckResult] = []
    for log_path_key in ["logging.main_log", "logging.debug_log"]:
        log_path = _get_nested(data, log_path_key)
        if log_path and isinstance(log_path, str):
            results.append(_check_parent_dir(log_path_key, log_path))
    return results


def _check_state_file_path(data: dict) -> list[CheckResult]:
    """Check state file parent directory exists."""
    state_file = _get_nested(data, "state_file")
    if state_file and isinstance(state_file, str):
        return [_check_parent_dir("state_file", state_file)]
    return []


def _check_ssh_key_path(data: dict, transport: str) -> list[CheckResult]:
    """Check SSH key existence and permissions."""
    ssh_key = _get_nested(data, "router.ssh_key")
    if not (ssh_key and isinstance(ssh_key, str)):
        return []

    key_path = Path(ssh_key)
    if not key_path.exists():
        if transport == "rest":
            return [CheckResult(
                "File Paths", "router.ssh_key", Severity.PASS,
                f"router.ssh_key: not found ({ssh_key}) -- REST transport, SSH key optional",
            )]
        return [CheckResult("File Paths", "router.ssh_key", Severity.ERROR, f"router.ssh_key: file not found ({ssh_key})")]

    mode = key_path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return [CheckResult(
            "File Paths", "router.ssh_key", Severity.WARN,
            f"router.ssh_key: insecure permissions ({oct(mode & 0o777)})",
            suggestion=f"chmod 600 {ssh_key}",
        )]
    return [CheckResult("File Paths", "router.ssh_key", Severity.PASS, "router.ssh_key: exists with secure permissions")]


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
# VALIDATOR DISPATCHERS
# =============================================================================


def _run_autorate_validators(data: dict) -> list[CheckResult]:
    """Run all autorate-specific validators."""
    # Local import to avoid circular dependency (check_steering_validators
    # imports CheckResult/Severity from check_config which we also import from)
    from wanctl.check_steering_validators import validate_linux_cake

    results: list[CheckResult] = []
    results.extend(validate_schema_fields(data))
    results.extend(validate_cross_fields(data))
    results.extend(check_unknown_keys(data))
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_deprecated_params(data))
    results.extend(validate_linux_cake(data))
    return results



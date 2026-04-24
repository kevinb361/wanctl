"""Steering configuration validation functions.

Contains validator functions for steering config files: schema validation,
cross-field checks, unknown key detection, deprecated parameter warnings,
cross-config consistency, and linux-cake transport validation.
"""

import difflib
from pathlib import Path

import yaml

from wanctl.check_config import CheckResult, Severity
from wanctl.config_base import BaseConfig, ConfigValidationError, _get_nested, validate_field
from wanctl.steering.daemon import SteeringConfig

# =============================================================================
# KNOWN CONFIGURATION PATHS
# =============================================================================

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
    "storage.retention",
    "storage.retention.raw_age_seconds",
    "storage.retention.aggregate_1m_age_seconds",
    "storage.retention.aggregate_5m_age_seconds",
    "storage.retention.prometheus_compensated",
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


# =============================================================================
# STEERING VALIDATORS
# =============================================================================


def _walk_leaf_paths(data: dict, prefix: str = "") -> list[str]:
    """Walk a config dict and return all leaf paths (dot-notation)."""
    paths: list[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.append(path)
        if isinstance(value, dict):
            paths.extend(_walk_leaf_paths(value, path))
    return paths


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
# VALIDATOR DISPATCHER
# =============================================================================


def _run_steering_validators(data: dict) -> list[CheckResult]:
    """Run all steering-specific validators."""
    # Local import to avoid circular dependency (check_paths/check_env_vars
    # live in check_config_validators which imports CheckResult from check_config)
    from wanctl.check_config_validators import check_env_vars, check_paths

    results: list[CheckResult] = []
    results.extend(validate_steering_schema_fields(data))
    results.extend(validate_steering_cross_fields(data))
    results.extend(check_steering_unknown_keys(data))
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_steering_deprecated_params(data))
    results.extend(check_steering_cross_config(data))
    return results

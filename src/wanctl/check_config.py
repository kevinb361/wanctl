"""Offline configuration validator for wanctl autorate configs.

Validates YAML config files against the autorate schema, checks cross-field
constraints, file paths, environment variables, deprecated parameters, and
unknown keys. Reports all problems at once with PASS/WARN/FAIL per category.

Usage:
    wanctl-check-config spectrum.yaml
    wanctl-check-config spectrum.yaml --no-color
    wanctl-check-config spectrum.yaml -q
"""

import argparse
import difflib
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
            results.append(
                CheckResult("Schema Validation", path, Severity.PASS, f"{path}: valid")
            )
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
            results.append(
                CheckResult("Cross-field Checks", "thresholds", Severity.ERROR, str(e))
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
# OUTPUT FORMATTING
# =============================================================================


def _use_color(no_color: bool) -> bool:
    """Determine whether to use ANSI color codes."""
    if no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


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
    results: list[CheckResult], no_color: bool = False, quiet: bool = False
) -> str:
    """Format validation results grouped by category.

    Args:
        results: List of CheckResult from all validators.
        no_color: Disable ANSI color codes.
        quiet: Suppress PASS results.

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

    if error_count > 0:
        summary_word = "FAIL"
    elif warn_count > 0:
        summary_word = "WARN"
    else:
        summary_word = "PASS"

    summary = f"\nResult: {summary_word} ({error_count} errors, {warn_count} warnings)"
    if color:
        if error_count > 0:
            summary = f"\n{_RED}{_BOLD}Result: FAIL{_RESET} ({error_count} errors, {warn_count} warnings)"
        elif warn_count > 0:
            summary = f"\n{_YELLOW}{_BOLD}Result: WARN{_RESET} ({warn_count} warnings)"
        else:
            summary = f"\n{_GREEN}{_BOLD}Result: PASS{_RESET} (no errors, no warnings)"
    lines.append(summary)

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="wanctl-check-config",
        description="Validate wanctl autorate configuration files offline",
    )
    parser.add_argument("config_file", help="Path to YAML config file")
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Only show warnings and errors"
    )
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
        print(f"Error: config file must contain a YAML mapping, got {type(data).__name__}", file=sys.stderr)
        return 1

    # Run all validators
    results: list[CheckResult] = []
    results.extend(validate_schema_fields(data))
    results.extend(validate_cross_fields(data))
    results.extend(check_unknown_keys(data))
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_deprecated_params(data))

    # Format and print
    output = format_results(results, no_color=args.no_color, quiet=args.quiet)
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

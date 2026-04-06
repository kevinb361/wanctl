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
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum

import yaml

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


# ANSI color codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


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
    # Local import to avoid circular dependency (validators import CheckResult/Severity from here)
    from wanctl.check_config_validators import (
        _run_autorate_validators,
        _run_steering_validators,
    )

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

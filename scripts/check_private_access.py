#!/usr/bin/env python3
"""Check for cross-module private attribute access via AST analysis.

Walks all .py files in a directory, parses each with the ast module, and
reports any Attribute node where the attr starts with '_' and the accessor
is NOT self or cls (which are legitimate same-class accesses). Dunder
attributes (__xxx__) are also excluded since they are part of the public
Python data model.

An allowlist of known violations is maintained so the script passes in CI
today. As plans 02-04 eliminate violations, entries are removed from the
allowlist. Any NEW violation (not in the allowlist) causes exit code 1.

Usage:
    python scripts/check_private_access.py src/wanctl/
    python scripts/check_private_access.py src/wanctl/ --verbose

Returns exit code 0 if no new violations (allowlisted ones are expected).
Returns exit code 1 if any new violation is found.
"""

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Allowlist of known cross-module private attribute accesses
# Organized by coupling boundary from the Phase 147 coupling census.
# Format: (source_file_stem, private_attr_name)
# Remove entries as Plans 02-04 eliminate violations.
# ---------------------------------------------------------------------------

ALLOWLIST: set[tuple[str, str]] = {
    # --- Boundary 1: autorate_continuous.py -> WANController ---
    # RESOLVED by Plan 02: all 21 entries eliminated via public facade API
    # --- Boundary 2: health_check.py -> WANController + QueueController ---
    # RESOLVED by Plan 03: all 16 entries eliminated via get_health_data() facade
    # --- Boundary 3: steering/health.py -> SteeringDaemon + BaselineLoader ---
    ("health", "_cycle_interval_ms"),
    ("health", "_enabled"),
    ("health", "_get_effective_wan_zone"),
    ("health", "_get_wan_zone_age"),
    ("health", "_is_wan_grace_period_active"),
    ("health", "_is_wan_zone_stale"),
    ("health", "_overrun_count"),
    ("health", "_profiler"),
    ("health", "_wan_red_weight"),
    ("health", "_wan_soft_red_weight"),
    ("health", "_wan_state_enabled"),
    ("health", "_wan_zone"),
    # --- Boundary 4: steering/daemon.py internal (entry point -> instance) ---
    ("daemon", "_get_wan_zone_age"),
    ("daemon", "_instance"),
    ("daemon", "_profiling_enabled"),
    ("daemon", "_reload_dry_run_config"),
    ("daemon", "_reload_wan_state_config"),
    ("daemon", "_reload_webhook_url_config"),
    ("daemon", "_wan_staleness_threshold"),
    # --- Boundary 5: wan_controller.py (module-level funcs -> WC instance) ---
    # RESOLVED by Plan 02: _cadence_sec, _db_path, _min_score, _outlier_window,
    #   _sigma_threshold, _window, _window_size (now use public properties)
    ("wan_controller", "_fusion_icmp_weight"),
    ("wan_controller", "_grace_period_sec"),
    ("wan_controller", "_reflector_scorer"),
    ("wan_controller", "_rules"),
    ("wan_controller", "_tuning_state"),
    ("wan_controller", "_window_had_congestion"),
    ("wan_controller", "_window_start_time"),
    # --- Boundary 6: Miscellaneous ---
    ("check_cake", "_find_mangle_rule_id"),
    ("writer", "_initialized"),
}


def check_file(filepath: Path) -> list[str]:
    """Find cross-module private attribute accesses in a Python file.

    Args:
        filepath: Path to a Python source file.

    Returns:
        List of violation strings in format "filepath:lineno: accessor.attr"
    """
    violations: list[str] = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        attr = node.attr
        if not attr.startswith("_"):
            continue
        # Skip self._ (same-class access)
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            continue
        # Skip cls._ (classmethod access)
        if isinstance(node.value, ast.Name) and node.value.id == "cls":
            continue
        # Skip dunder attributes (__xxx__)
        if attr.startswith("__") and attr.endswith("__"):
            continue

        # Build a readable accessor description
        if isinstance(node.value, ast.Name):
            accessor = node.value.id
        else:
            accessor = "<expr>"

        violations.append(f"{filepath}:{node.lineno}: {accessor}.{attr}")

    return violations


def _is_allowlisted(filepath: Path, attr: str) -> bool:
    """Check if a violation is in the allowlist."""
    return (filepath.stem, attr) in ALLOWLIST


def scan_directory(directory: Path, *, verbose: bool = False) -> tuple[int, int, int]:
    """Scan all Python files in directory for private attribute access violations.

    Args:
        directory: Root directory to scan recursively.
        verbose: If True, print each violation.

    Returns:
        Tuple of (total_violations, allowlisted_count, new_count).
    """
    total = 0
    allowlisted = 0
    new = 0
    new_violations: list[str] = []

    for py_file in sorted(directory.rglob("*.py")):
        violations = check_file(py_file)
        for v in violations:
            total += 1
            # Extract attr from the violation string: "path:line: accessor.attr"
            parts = v.rsplit(".", 1)
            if len(parts) == 2:
                attr = parts[1]
            else:
                attr = ""

            if _is_allowlisted(py_file, attr):
                allowlisted += 1
                if verbose:
                    print(f"  [allowlisted] {v}")
            else:
                new += 1
                new_violations.append(v)

    if new_violations:
        print("NEW violations (not in allowlist):")
        for v in new_violations:
            print(f"  {v}")
        print()

    print(f"{total} violations found ({allowlisted} in allowlist, {new} new)")
    return total, allowlisted, new


def main() -> int:
    """Entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check for cross-module private attribute access"
    )
    parser.add_argument("directory", type=Path, help="Directory to scan")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show allowlisted violations"
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        return 1

    _total, _allowlisted, new_count = scan_directory(args.directory, verbose=args.verbose)
    return 1 if new_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

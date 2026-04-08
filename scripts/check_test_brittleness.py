#!/usr/bin/env python3
"""Check for cross-module private mock patches in test files.

Scans test files for patch() calls that target private attributes (_prefixed)
in modules OTHER than the module under test. Per D-10, cross-module is defined
as: patching a _attr belonging to a different module than the code under test.

Same-module patches (test_foo.py patching wanctl.foo._private) are acceptable.

Detection approach:
  1. String-based patches: patch("wanctl.MODULE._attr") where MODULE differs
     from the test file's implied target module.
  2. Only string-literal patch targets are analyzed (patch.object with private
     strings is harder to resolve statically and is deferred).

Usage:
    python scripts/check_test_brittleness.py tests/
    python scripts/check_test_brittleness.py tests/ --threshold 3
    python scripts/check_test_brittleness.py tests/ --verbose

Returns exit code 0 if all files are within threshold.
Returns exit code 1 if any file exceeds threshold.
"""

import ast
import re
import sys
from pathlib import Path


def _extract_target_modules(test_filename: str) -> set[str]:
    """Derive the target module(s) from a test filename.

    test_foo.py -> {"foo"}
    test_foo_bar.py -> {"foo_bar"}

    The target module is what the test file is *about*. Patches on
    wanctl.<target>._ are same-module; patches on wanctl.<other>._ are cross.
    """
    stem = Path(test_filename).stem
    if stem.startswith("test_"):
        module_name = stem[5:]  # strip "test_"
    else:
        module_name = stem
    return {module_name}


def _parse_patch_target(patch_string: str) -> tuple[str | None, str | None]:
    """Parse a patch string like 'wanctl.module._attr' into (module, attr).

    Returns (module_path, attr_name) or (None, None) if not a wanctl private patch.

    Examples:
        'wanctl.check_cake._create_audit_client' -> ('check_cake', '_create_audit_client')
        'wanctl.steering.daemon._private' -> ('steering.daemon', '_private')
        'wanctl.foo.bar' -> (None, None)  # not private
        'os.path.join' -> (None, None)  # not wanctl
    """
    if not patch_string.startswith("wanctl."):
        return None, None

    # Strip 'wanctl.' prefix
    remainder = patch_string[7:]  # after "wanctl."

    # Split into parts: e.g. "check_cake._create_audit_client" -> ["check_cake", "_create_audit_client"]
    parts = remainder.split(".")

    if len(parts) < 2:
        return None, None

    attr_name = parts[-1]
    if not attr_name.startswith("_"):
        return None, None

    # Skip dunder attributes (__xxx__) -- they're public Python protocol
    if attr_name.startswith("__") and attr_name.endswith("__"):
        return None, None

    # Module path is everything except the last part (the private attr)
    module_path = ".".join(parts[:-1])

    return module_path, attr_name


def _is_cross_module(module_path: str, target_modules: set[str]) -> bool:
    """Check if a module path is cross-module relative to the test's targets.

    A module path like 'check_cake' matches target 'check_cake'.
    A module path like 'steering.daemon' matches target 'steering_daemon'
    (after normalizing dots to underscores for comparison).
    A module path like 'check_cake_fix' does NOT match target 'check_cake' -- cross-module.
    """
    # Direct match: module_path is exactly one of the targets
    if module_path in target_modules:
        return False

    # Normalize dots to underscores for submodule matching
    # e.g., "steering.daemon" should match target "steering_daemon"
    normalized = module_path.replace(".", "_")
    if normalized in target_modules:
        return False

    # Also check the leaf module name alone (last part)
    # e.g., "steering.daemon" leaf is "daemon" -- matches target "daemon"
    leaf = module_path.split(".")[-1]
    if leaf in target_modules:
        return False

    return True


def count_cross_module_patches(filepath: Path) -> list[str]:
    """Count cross-module private patches in a test file.

    Args:
        filepath: Path to a test file.

    Returns:
        List of violation descriptions (e.g., 'line 42: patch("wanctl.bar._priv")').
    """
    violations: list[str] = []

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    target_modules = _extract_target_modules(filepath.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Detect patch("wanctl.module._attr") calls
        patch_string = _extract_patch_string_arg(node)
        if patch_string is None:
            continue

        module_path, attr_name = _parse_patch_target(patch_string)
        if module_path is None or attr_name is None:
            continue

        if _is_cross_module(module_path, target_modules):
            violations.append(
                f"line {node.lineno}: patch(\"{patch_string}\")"
            )

    return violations


def _extract_patch_string_arg(call_node: ast.Call) -> str | None:
    """Extract the first string argument from a patch() call.

    Matches:
      - patch("wanctl.foo._bar")
      - mock.patch("wanctl.foo._bar")
      - unittest.mock.patch("wanctl.foo._bar")

    Does NOT match patch.object() -- that's a different pattern.
    """
    func = call_node.func

    # patch("...")
    if isinstance(func, ast.Name) and func.id == "patch":
        pass
    # mock.patch("...") or unittest.mock.patch("...")
    elif isinstance(func, ast.Attribute) and func.attr == "patch":
        # Verify it's not patch.object (which is patch().object -- different AST)
        pass
    else:
        return None

    # Exclude patch.object, patch.dict, etc. by checking the call isn't on an attribute
    # patch.object shows up as Attribute(value=Name(id='patch'), attr='object')
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "patch":
            # This is patch.object() or patch.dict() -- skip
            return None

    # Get first positional argument
    if not call_node.args:
        return None

    first_arg = call_node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value

    return None


def main() -> int:
    """Entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check for cross-module private mock patches in test files"
    )
    parser.add_argument("directory", type=Path, help="Test directory to scan")
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Max cross-module patches per file before FAIL (default: 3)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show all violations"
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        return 1

    violations_by_file: dict[Path, list[str]] = {}
    for test_file in sorted(args.directory.rglob("test_*.py")):
        violations = count_cross_module_patches(test_file)
        if violations:
            violations_by_file[test_file] = violations

    # Report
    exceeds = 0
    for filepath, violations in violations_by_file.items():
        count = len(violations)
        status = "FAIL" if count > args.threshold else "WARN"
        if status == "FAIL":
            exceeds += 1
        if args.verbose or status == "FAIL":
            print(f"  [{status}] {filepath.name}: {count} cross-module patches")
            for v in violations:
                print(f"    - {v}")

    total = sum(len(v) for v in violations_by_file.values())
    file_count = len(violations_by_file)
    print(f"\n{total} cross-module private patches across {file_count} files")
    if exceeds:
        print(f"FAIL: {exceeds} file(s) exceed threshold of {args.threshold}")
    else:
        print(f"OK: all files within threshold of {args.threshold}")
    return 1 if exceeds > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

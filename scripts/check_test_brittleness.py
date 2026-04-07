#!/usr/bin/env python3
"""Check for cross-module private attribute patches in test files.

Scans test files for patch("wanctl.MODULE._attr") calls where MODULE
is different from the module under test (derived from filename:
test_foo.py -> foo). Cross-module private patches create brittleness --
tests break when private internals are renamed, not when behavior changes.

Same-module patches are acceptable per D-10 (the test owns the module
it's testing and can patch its internals).

Uses AST analysis to only detect actual patch() function calls, not
patterns inside string literals or comments.

Usage:
    python scripts/check_test_brittleness.py tests/
    python scripts/check_test_brittleness.py tests/ --threshold 3
    python scripts/check_test_brittleness.py tests/ --verbose

Returns exit code 0 if all files have <= threshold cross-module patches.
Returns exit code 1 if any file exceeds threshold.
"""

import ast
import re
import sys
from pathlib import Path

# Pattern to extract module and private attr from a patch target string
# e.g., "wanctl.check_cake_fix._save_snapshot" -> ("check_cake_fix", "_save_snapshot")
_PATCH_TARGET_RE = re.compile(r"^wanctl\.(\w+)\._(\w+)$")


def _module_under_test(filename: str) -> str:
    """Derive the module under test from a test filename.

    test_foo.py -> foo
    test_foo_bar.py -> foo_bar
    """
    stem = Path(filename).stem
    if stem.startswith("test_"):
        return stem[5:]
    return stem


def _extract_patch_targets(tree: ast.Module) -> list[str]:
    """Extract string arguments from patch() calls in the AST.

    Finds:
      - patch("wanctl.module._attr")
      - patch("wanctl.module._attr", ...)

    Does NOT match:
      - Strings inside non-patch contexts (docstrings, variables, etc.)
      - patch.object() calls (handled separately if needed)

    Returns:
        List of patch target strings like "wanctl.module._attr".
    """
    targets: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Match: patch("...")
        func = node.func
        is_patch_call = False

        if isinstance(func, ast.Name) and func.id == "patch":
            is_patch_call = True
        elif isinstance(func, ast.Attribute) and func.attr == "patch":
            # mock.patch("...") or similar
            is_patch_call = True

        if not is_patch_call:
            continue

        # Extract first positional argument if it's a string constant
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            target = node.args[0].value
            targets.append(target)

    return targets


def scan_file(filepath: Path) -> int:
    """Count cross-module private patches in a single test file.

    A cross-module private patch is a patch("wanctl.MODULE._attr") where
    MODULE differs from the module under test (derived from filename).

    conftest.py files are exempt (they provide shared fixtures).

    Args:
        filepath: Path to a test file.

    Returns:
        Number of cross-module private patches found.
    """
    if filepath.name == "conftest.py":
        return 0

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return 0

    module_under_test = _module_under_test(filepath.name)
    count = 0

    for target in _extract_patch_targets(tree):
        match = _PATCH_TARGET_RE.match(target)
        if match:
            patched_module = match.group(1)
            if patched_module != module_under_test:
                count += 1

    return count


def scan_directory(
    directory: Path, *, threshold: int = 3, verbose: bool = False
) -> tuple[int, int, int]:
    """Scan all test files in directory for cross-module private patches.

    Args:
        directory: Root directory to scan recursively.
        threshold: Max cross-module patches per file (default 3 per D-12).
        verbose: If True, print per-file details.

    Returns:
        Tuple of (total_patches, files_over_threshold, exit_code).
        exit_code is 0 if no file exceeds threshold, 1 otherwise.
    """
    total = 0
    files_checked = 0
    files_over = 0
    violations: list[tuple[str, int]] = []

    for py_file in sorted(directory.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        if "__pycache__" in str(py_file):
            continue
        if not py_file.name.startswith("test_") and py_file.name != "conftest.py":
            continue

        files_checked += 1
        count = scan_file(py_file)
        total += count

        if count > threshold:
            files_over += 1
            violations.append((str(py_file), count))

        if verbose and count > 0:
            print(f"  {py_file}: {count} cross-module private patches")

    if violations:
        print("Files exceeding threshold:")
        for path, count in violations:
            print(f"  {path}: {count} (threshold: {threshold})")
        print()

    print(
        f"{files_checked} files checked, "
        f"{total} cross-module private patches found, "
        f"{files_over} files exceeding threshold"
    )

    exit_code = 1 if files_over > 0 else 0
    return total, files_over, exit_code


def main() -> int:
    """Entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check for cross-module private patches in test files"
    )
    parser.add_argument("directory", type=Path, help="Test directory to scan")
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Max cross-module patches per file (default: 3)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show per-file details"
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        return 1

    _total, _files_over, exit_code = scan_directory(
        args.directory, threshold=args.threshold, verbose=args.verbose
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

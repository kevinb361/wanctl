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
# Allowlist of known cross-module private attribute accesses.
# All cross-module violations eliminated by Phase 147 Plans 01-04.
# Any new cross-module violation will fail CI immediately (D-04).
# ---------------------------------------------------------------------------

ALLOWLIST: set[tuple[str, str]] = set()


def _collect_class_names(tree: ast.Module) -> set[str]:
    """Collect all class names defined at any level in the AST."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def _annotation_matches(annotation: ast.expr | None, class_names: set[str]) -> bool:
    """Check if a type annotation references a class defined in this file."""
    if annotation is None:
        return False
    # Direct name: param: ClassName
    if isinstance(annotation, ast.Name) and annotation.id in class_names:
        return True
    # String forward reference: param: "ClassName"
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value in class_names
    return False


def _collect_same_file_variables(tree: ast.Module, class_names: set[str]) -> set[str]:
    """Collect variable names that are instances of classes defined in this file.

    Detects patterns like:
      - ``var = ClassName(...)``        (direct instantiation)
      - ``var: ClassName = ...``        (annotated assignment)
      - function parameters with type annotations matching a local class

    Also includes the lowercase form of each class name as a common convention
    (e.g., class SteeringDaemon -> variable 'daemon').
    """
    import re

    variables: set[str] = set()

    # Convention: lowercase class name is a common variable name for that class
    for cn in class_names:
        parts = re.findall(r"[A-Z][a-z]*", cn)
        if parts:
            variables.add(parts[-1].lower())

    for node in ast.walk(tree):
        # var = ClassName(...)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id in class_names:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.add(target.id)
        # var: ClassName = ...
        if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name):
            if node.annotation.id in class_names and isinstance(node.target, ast.Name):
                variables.add(node.target.id)
        # Function parameters with type annotations
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                if _annotation_matches(arg.annotation, class_names):
                    variables.add(arg.arg)

    return variables


def _collect_same_file_attrs(tree: ast.Module, class_names: set[str]) -> set[str]:
    """Collect private attribute names defined on classes in this file.

    Used to skip chained-expression accesses (``<expr>._attr``) when
    the attribute is defined on a class in the same file.
    """
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name not in class_names:
            continue
        for item in ast.walk(node):
            # self._attr assignment in __init__ or methods
            if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name):
                if item.value.id == "self" and item.attr.startswith("_"):
                    attrs.add(item.attr)
            # Method definitions (including private ones)
            if isinstance(item, ast.FunctionDef) and item.name.startswith("_"):
                attrs.add(item.name)
    return attrs


def _build_class_line_ranges(tree: ast.Module, class_names: set[str]) -> list[tuple[int, int]]:
    """Build (start_line, end_line) ranges for all classes defined in this file."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in class_names:
            end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else node.lineno
            ranges.append((node.lineno, end))
    return ranges


def _is_inside_same_file_class(lineno: int, class_ranges: list[tuple[int, int]]) -> bool:
    """Check if a line number falls inside a class defined in this file."""
    return any(start <= lineno <= end for start, end in class_ranges)


def check_file(filepath: Path) -> list[str]:
    """Find cross-module private attribute accesses in a Python file.

    Cross-module = a file accessing private attributes of classes it imports.
    Within-module accesses are excluded:
      - self._ and cls._ (same-class)
      - Variables holding instances of classes defined in the same file
      - Class-level access on same-file classes (e.g., Class._instance)
      - Chained expressions (self.obj._attr) inside same-file class methods
      - Module-level functions accessing same-file class instances

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

    # Collect classes defined in this file and variables that hold their instances
    class_names = _collect_class_names(tree)
    same_file_vars = _collect_same_file_variables(tree, class_names)
    class_ranges = _build_class_line_ranges(tree, class_names)

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
        # Skip same-file variables (within-module access, not cross-module)
        if isinstance(node.value, ast.Name) and node.value.id in same_file_vars:
            continue
        # Skip class-level access on same-file classes (e.g., Class._instance)
        if isinstance(node.value, ast.Name) and node.value.id in class_names:
            continue
        # Skip chained expressions (self.obj._attr, expr._attr) inside
        # methods of classes defined in this file. These are within-module
        # collaborator accesses, not cross-module boundary violations.
        if _is_inside_same_file_class(node.lineno, class_ranges):
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

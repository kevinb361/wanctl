#!/usr/bin/env python3
"""AST-based function line counter for enforcing line-count thresholds.

Walks Python source files, counts lines per function/method excluding
docstrings, and reports violations exceeding a configurable threshold.

Measurement: lines excluding docstrings. Blank lines and comments count
toward the total (per D-08).

Usage:
    python scripts/check_function_lines.py src/wanctl/ --threshold 50
    python scripts/check_function_lines.py src/wanctl/ --show-all
"""

import argparse
import ast
import sys
from pathlib import Path


def _docstring_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the number of source lines occupied by the function's docstring.

    A docstring is the first statement if it is an ast.Expr containing an
    ast.Constant with a string value. Returns 0 if no docstring.
    """
    if not node.body:
        return 0
    first = node.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.end_lineno - first.lineno + 1  # type: ignore[operator]
    return 0


def count_function_lines(
    filepath: Path,
) -> list[tuple[str, int, int, int]]:
    """Parse a Python file and return (name, lineno, total_lines, lines_excl_docstring) per function.

    Handles nested classes and methods. Each function/method is reported
    with its fully qualified name (ClassName.method_name).
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results: list[tuple[str, int, int, int]] = []

    def _visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                class_prefix = f"{prefix}{child.name}." if prefix else f"{child.name}."
                _visit(child, class_prefix)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                total = child.end_lineno - child.lineno + 1  # type: ignore[operator]
                doc_lines = _docstring_lines(child)
                effective = total - doc_lines
                results.append((name, child.lineno, total, effective))
                # Visit nested functions/classes inside this function
                _visit(child, f"{name}.")

    _visit(tree)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check function line counts (excluding docstrings)"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="src/wanctl/",
        help="Directory or file to scan (default: src/wanctl/)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=50,
        help="Maximum allowed lines per function (default: 50)",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show ALL functions with their line counts",
    )
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_file():
        py_files = [target]
    elif target.is_dir():
        py_files = sorted(target.rglob("*.py"))
    else:
        print(f"Error: {target} is not a file or directory", file=sys.stderr)
        return 1

    violations: list[tuple[str, int, str, int]] = []
    all_functions: list[tuple[str, int, str, int]] = []

    for filepath in py_files:
        for name, lineno, _total, effective in count_function_lines(filepath):
            rel_path = str(filepath)
            all_functions.append((rel_path, lineno, name, effective))
            if effective > args.threshold:
                violations.append((rel_path, lineno, name, effective))

    if args.show_all:
        # Sort by line count descending for readability
        all_functions.sort(key=lambda x: x[3], reverse=True)
        for rel_path, lineno, name, effective in all_functions:
            marker = " ***" if effective > args.threshold else ""
            print(f"{rel_path}:{lineno} {name} ({effective} lines){marker}")
        print(f"\nTotal functions: {len(all_functions)}")
        print(f"Over threshold ({args.threshold}): {len(violations)}")
        return 1 if violations else 0

    if violations:
        violations.sort(key=lambda x: x[3], reverse=True)
        print(f"Functions exceeding {args.threshold} lines (excluding docstrings):\n")
        for rel_path, lineno, name, effective in violations:
            print(f"{rel_path}:{lineno} {name} ({effective} lines)")
        print(f"\n{len(violations)} violation(s) found")
        return 1

    print(f"All functions within {args.threshold}-line threshold")
    return 0


if __name__ == "__main__":
    sys.exit(main())

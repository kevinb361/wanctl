#!/usr/bin/env python3
"""Phase 239 SAFE-17 protected-body and allowed-shape verifier.

Compares the current tree against the v1.52 anchor.  This script is intentionally
fail-closed: missing nodes, parse errors, unexpected qualname deltas, protected
body drift, or module-level drift all return non-zero.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROTECTED: dict[str, list[str]] = {
    "src/wanctl/rtt_measurement.py": [
        "RTTSnapshot",
        "RTTMeasurement.__init__",
        "RTTMeasurement.ping_host",
        "RTTMeasurement._aggregate_rtts",
        "RTTMeasurement.ping_hosts_with_results",
        "BackgroundRTTThread._run",
        "BackgroundRTTThread._ping_with_persistent_pool",
    ],
    "src/wanctl/wan_controller.py": ["WANController.measure_rtt"],
}

RTT_MEASUREMENT_PATH = "src/wanctl/rtt_measurement.py"
DEFAULT_ALLOWED_ADDED = {"RTTMeasurement.probe"}
DEFAULT_CONTAINER_WITH_ADDED_CHILD = "RTTMeasurement"


@dataclass(frozen=True)
class ShapeResult:
    ok: bool
    added_qualnames: list[str]
    removed_qualnames: list[str]
    changed_nodes: list[str]
    module_level_ok: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "added_qualnames": self.added_qualnames,
            "removed_qualnames": self.removed_qualnames,
            "changed_nodes": self.changed_nodes,
            "module_level_ok": self.module_level_ok,
            "allowed_shape_ok": self.ok,
        }


class VerifierError(RuntimeError):
    """Usage, git, parse, or source extraction error."""


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise VerifierError(
            f"git {' '.join(args)} failed with {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def resolve_anchor(anchor: str) -> str:
    return run_git("rev-parse", "--verify", "--end-of-options", f"{anchor}^{{commit}}").strip()


def anchor_source(anchor: str, path: str) -> str:
    return run_git("show", f"{anchor}:{path}")


def read_head_source(path: str) -> str:
    return Path(path).read_text()


def parse_source(source: str, *, label: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise VerifierError(f"failed to parse {label}: {exc}") from exc


def source_segment(source: str, node: ast.AST, *, name: str) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise VerifierError(f"could not extract source segment for {name}")
    return segment


def build_qualname_map(tree: ast.Module) -> dict[str, ast.AST]:
    qualnames: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualnames[node.name] = node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualnames[f"{node.name}.{child.name}"] = child
    return qualnames


def class_child_names(node: ast.ClassDef) -> set[str]:
    return {child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}


def non_function_class_statements(source: str, node: ast.ClassDef) -> list[str]:
    return [
        source_segment(source, child, name=f"{node.name}.<class-statement>")
        for child in node.body
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def module_level_statements(source: str, tree: ast.Module) -> list[str]:
    return [
        source_segment(source, node, name="<module-level>")
        for node in tree.body
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def class_header_signature(source: str, node: ast.ClassDef) -> dict[str, Any]:
    # Compare the semantic header pieces and exact decorator/base/keyword source.
    return {
        "name": node.name,
        "decorators": [source_segment(source, d, name=f"{node.name}.decorator") for d in node.decorator_list],
        "bases": [source_segment(source, b, name=f"{node.name}.base") for b in node.bases],
        "keywords": [
            {
                "arg": kw.arg,
                "value": source_segment(source, kw.value, name=f"{node.name}.keyword"),
            }
            for kw in node.keywords
        ],
    }


def compare_allowed_shape(
    v152_source: str,
    head_source: str,
    allowed_added_qualnames: set[str],
    container_with_added_child: str | None,
) -> ShapeResult:
    """Pure allowed-diff-shape comparison for rtt_measurement.py.

    Accepts exactly the allowed qualname additions while requiring every
    pre-existing surface to remain byte-identical.  For the one container class
    that may gain an allowed child, the class is compared by header,
    class-level statements, and pre-existing child methods instead of comparing
    its whole source segment.
    """

    old_tree = parse_source(v152_source, label="v1.52 synthetic/old source")
    new_tree = parse_source(head_source, label="HEAD synthetic/new source")
    old_nodes = build_qualname_map(old_tree)
    new_nodes = build_qualname_map(new_tree)

    old_set = set(old_nodes)
    new_set = set(new_nodes)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    changed: list[str] = []

    if set(added) != allowed_added_qualnames:
        changed.append(f"unexpected added qualnames: {added}")
    if removed:
        changed.append(f"removed qualnames: {removed}")

    module_level_ok = module_level_statements(v152_source, old_tree) == module_level_statements(
        head_source, new_tree
    )
    if not module_level_ok:
        changed.append("<module-level>")

    for qualname in sorted(old_set & new_set):
        old_node = old_nodes[qualname]
        new_node = new_nodes[qualname]
        if qualname == container_with_added_child:
            if not isinstance(old_node, ast.ClassDef) or not isinstance(new_node, ast.ClassDef):
                changed.append(qualname)
                continue
            old_children = class_child_names(old_node)
            new_children = class_child_names(new_node)
            allowed_child = {
                name.split(".", 1)[1]
                for name in allowed_added_qualnames
                if name.startswith(f"{qualname}.") and "." in name
            }
            if new_children != old_children | allowed_child:
                changed.append(f"{qualname}.<children>")
            if class_header_signature(v152_source, old_node) != class_header_signature(head_source, new_node):
                changed.append(f"{qualname}.<header>")
            if non_function_class_statements(v152_source, old_node) != non_function_class_statements(
                head_source, new_node
            ):
                changed.append(f"{qualname}.<class-level>")
            for child_name in sorted(old_children & new_children):
                child_qualname = f"{qualname}.{child_name}"
                if source_segment(v152_source, old_nodes[child_qualname], name=child_qualname) != source_segment(
                    head_source, new_nodes[child_qualname], name=child_qualname
                ):
                    changed.append(child_qualname)
            continue

        old_segment = source_segment(v152_source, old_node, name=qualname)
        new_segment = source_segment(head_source, new_node, name=qualname)
        if old_segment != new_segment:
            changed.append(qualname)

    changed = sorted(dict.fromkeys(changed))
    ok = not removed and set(added) == allowed_added_qualnames and not changed and module_level_ok
    return ShapeResult(
        ok=ok,
        added_qualnames=added,
        removed_qualnames=removed,
        changed_nodes=changed,
        module_level_ok=module_level_ok,
    )


def protected_node_results(anchor: str) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    all_identical = True
    for path, qualnames in PROTECTED.items():
        old_source = anchor_source(anchor, path)
        new_source = read_head_source(path)
        old_nodes = build_qualname_map(parse_source(old_source, label=f"{anchor}:{path}"))
        new_nodes = build_qualname_map(parse_source(new_source, label=f"HEAD:{path}"))
        for qualname in qualnames:
            identical = False
            reason = "identical"
            try:
                if qualname not in old_nodes:
                    reason = "missing in anchor"
                elif qualname not in new_nodes:
                    reason = "missing in HEAD"
                else:
                    old_segment = source_segment(old_source, old_nodes[qualname], name=f"{path}:{qualname}")
                    new_segment = source_segment(new_source, new_nodes[qualname], name=f"{path}:{qualname}")
                    identical = old_segment == new_segment
                    if not identical:
                        reason = "source segment drift"
            except VerifierError as exc:
                reason = str(exc)
            if identical:
                print(f"PASS protected {path}:{qualname}", file=sys.stderr)
            else:
                print(f"FAIL protected {path}:{qualname}: {reason}", file=sys.stderr)
                all_identical = False
            results.append(
                {"file": path, "function": qualname, "identical": identical, "reason": reason}
            )
    return results, all_identical


def run_allowed_shape(anchor: str) -> ShapeResult:
    old_source = anchor_source(anchor, RTT_MEASUREMENT_PATH)
    new_source = read_head_source(RTT_MEASUREMENT_PATH)
    result = compare_allowed_shape(
        old_source,
        new_source,
        DEFAULT_ALLOWED_ADDED,
        DEFAULT_CONTAINER_WITH_ADDED_CHILD,
    )
    if result.ok:
        print("PASS allowed-shape src/wanctl/rtt_measurement.py", file=sys.stderr)
    else:
        print(
            "FAIL allowed-shape src/wanctl/rtt_measurement.py: "
            f"added={result.added_qualnames} removed={result.removed_qualnames} "
            f"changed={result.changed_nodes} module_level_ok={result.module_level_ok}",
            file=sys.stderr,
        )
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", default="v1.52", help="git anchor ref (default: v1.52)")
    parser.add_argument("--json", action="store_true", help="emit structured JSON to stdout")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        anchor_sha = resolve_anchor(args.anchor)
        protected, all_identical = protected_node_results(args.anchor)
        shape = run_allowed_shape(args.anchor)
        payload = {
            "anchor": args.anchor,
            "anchor_sha": anchor_sha,
            "protected": protected,
            "shape": {"file": RTT_MEASUREMENT_PATH, **shape.to_json()},
            "all_identical": all_identical,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if all_identical and shape.ok else 1
    except VerifierError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

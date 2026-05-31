#!/usr/bin/env python3
# ruff: noqa: N803, N999
"""Phase 220 target/path/window matrix aggregator.

Reads Phase 220 per-cell manifests plus Phase 214 signal-sheet outputs and
rolls them into a schema_version=1 cube summary. This file intentionally avoids
``src.wanctl`` imports; JSON output uses an inline tempfile + os.replace atomic
write to preserve the Phase 214 no-shared-helper precedent.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
WINDOW_CHOICES = {"off-peak", "daytime", "prime-time"}
CANONICAL_TARGET = "dallas"
DEFAULT_THRESHOLDS = {
    "canonical_control_p99_kill_ms": 200,
    "canonical_min_windows_kill": 2,
    "canonical_max_windows_kill_total": 3,
    "supplemental_defect_p99_ms": 500,
    "supplemental_defect_min_windows": 2,
    "supplemental_carry_multiplier_of_control": 1.5,
}
DEFECT_DRIVERS = {"reflector_loss", "cake_queue_mismatch"}
DEFAULT_EVIDENCE_ROOT = Path(".planning/phases/220-matrix-runner-scope-a1/evidence")
DEFAULT_YAML_PATH = Path("scripts/phase220-matrix.yaml")


def _latency_value(sheet: dict[str, Any], key: str) -> float:
    latency = sheet.get("latency")
    if isinstance(latency, dict) and key in latency:
        return float(latency[key])
    return float(sheet[key])


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8"
        ) as tf:
            json.dump(data, tf, indent=2, sort_keys=True)
            tf.write("\n")
            tmp_path = tf.name
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def load_matrix_definition(yaml_path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError("phase220-matrix.yaml must parse to a mapping")
    if parsed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("phase220-matrix.yaml schema_version must be 1")

    for path_entry in parsed.get("paths", []):
        if path_entry.get("name") == "att":
            signature = path_entry.get("egress_signature")
            if not isinstance(signature, str) or not signature.strip():
                raise ValueError(
                    "phase220-matrix.yaml: paths[name=att].egress_signature is REQUIRED "
                    "and must be non-empty (MATRIX-03)"
                )

    parsed["driver_allowlist"] = [str(driver) for driver in parsed.get("driver_allowlist", [])]
    parsed["driver_allowlist_set"] = set(parsed["driver_allowlist"])
    parsed["thresholds"] = {**DEFAULT_THRESHOLDS, **dict(parsed.get("thresholds") or {})}
    return parsed


def group_replicates_by_base_cell_id(per_replicate_inputs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in per_replicate_inputs:
        cell_id = str(record.get("cell_id") or record.get("manifest", {}).get("cell_id") or "")
        base_cell_id = re.sub(r"__r\d+$", "", cell_id)
        grouped[base_cell_id].append(record)
    return dict(grouped)


def collapse_replicate_p99(values: list[float]) -> float:
    return float(statistics.median(values))


def _primary_driver_for_replicates(replicate_records: list[dict[str, Any]]) -> str | None:
    drivers = [record.get("primary_driver") for record in replicate_records if record.get("primary_driver")]
    if not drivers:
        return None
    counts = Counter(str(driver) for driver in drivers)
    ranked_order: list[str] = []
    for record in replicate_records:
        ranked = record.get("ranked") or record.get("ranked_drivers") or []
        if isinstance(ranked, list):
            for driver in ranked:
                driver_name = str(driver)
                if driver_name not in ranked_order:
                    ranked_order.append(driver_name)

    def sort_key(driver: str) -> tuple[int, int, str]:
        order = ranked_order.index(driver) if driver in ranked_order else len(ranked_order)
        return (-counts[driver], order, driver)

    return sorted(counts, key=sort_key)[0]


def collapse_replicates_to_cell(replicate_records: list[dict[str, Any]]) -> dict[str, Any]:
    if not replicate_records:
        raise ValueError("collapse_replicates_to_cell requires at least one record")
    first = replicate_records[0]
    p99_values = [float(record["p99_ms"]) for record in replicate_records]
    samples: list[float] = []
    for record in replicate_records:
        samples.extend(float(value) for value in record.get("per_second_samples_ms", []))
    cell_id = re.sub(r"__r\d+$", "", str(first["cell_id"]))
    return {
        "cell_id": cell_id,
        "target_name": str(first["target_name"]),
        "path_name": str(first["path_name"]),
        "window_name": str(first["window_name"]),
        "is_canonical": bool(first.get("is_canonical") or first.get("target_kind") == "canonical"),
        "target_kind": "canonical" if first.get("is_canonical") or first.get("target_kind") == "canonical" else "supplemental",
        "median_p99_ms": float(statistics.median(p99_values)),
        "primary_driver": _primary_driver_for_replicates(replicate_records),
        "ranked": first.get("ranked") or first.get("ranked_drivers") or [],
        "replicate_count": len(replicate_records),
        "per_second_samples_ms": samples,
        "replicate_p99_ms": p99_values,
    }


def cell_verdict(
    cell: dict[str, Any],
    control_p99_for_window: float | None,
    *,
    driver_allowlist: set[str] | list[str],
    thresholds: dict[str, Any] | None = None,
) -> str:
    resolved = {**DEFAULT_THRESHOLDS, **dict(thresholds or {})}
    allowlist = set(driver_allowlist)
    p99 = float(cell["median_p99_ms"])
    if bool(cell.get("is_canonical")) or cell.get("target_kind") == "canonical":
        return "cell_kill_clear" if p99 <= float(resolved["canonical_control_p99_kill_ms"]) else "cell_carry"
    if p99 > float(resolved["supplemental_defect_p99_ms"]) and cell.get("primary_driver") in allowlist:
        return "cell_defect"
    if control_p99_for_window is not None and p99 <= float(resolved["supplemental_carry_multiplier_of_control"]) * control_p99_for_window:
        return "cell_kill_clear"
    return "cell_carry"


def axis_rollup(cells_on_axis: list[dict[str, Any]]) -> str:
    verdicts = [str(cell.get("verdict")) for cell in cells_on_axis]
    if "cell_defect" in verdicts:
        return "defect"
    if "cell_carry" in verdicts:
        return "carry"
    return "kill_clear"


def _target_key(cell: dict[str, Any]) -> str:
    target = str(cell["target_name"])
    if bool(cell.get("is_canonical")) or cell.get("target_kind") == "canonical":
        return f"canonical_{target.replace('-', '_')}"
    return target


def _orthogonal_corroboration(defect_cells: list[dict[str, Any]]) -> dict[str, bool]:
    path_orthogonal = False
    target_to_paths: dict[str, set[str]] = defaultdict(set)
    path_to_targets: dict[str, set[str]] = defaultdict(set)
    driver_to_pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for cell in defect_cells:
        target = str(cell["target_name"])
        path = str(cell["path_name"])
        target_to_paths[target].add(path)
        path_to_targets[path].add(target)
        driver = cell.get("primary_driver")
        if driver:
            driver_to_pairs[str(driver)].add((target, path))
    path_orthogonal = any(len(paths) >= 2 for paths in target_to_paths.values())
    target_orthogonal = any(len(targets) >= 2 for targets in path_to_targets.values())
    driver_orthogonal = any(len(pairs) >= 2 for pairs in driver_to_pairs.values())
    return {
        "path_orthogonal": path_orthogonal,
        "target_orthogonal": target_orthogonal,
        "driver_orthogonal": driver_orthogonal,
        "satisfied": path_orthogonal or target_orthogonal or driver_orthogonal,
    }


def matrix_verdict(cells: list[dict[str, Any]], *, thresholds: dict[str, Any], driver_allowlist: set[str] | list[str]) -> dict[str, Any]:
    resolved = {**DEFAULT_THRESHOLDS, **dict(thresholds)}
    control_by_window: dict[str, float | None] = {window: None for window in WINDOW_CHOICES}
    for cell in cells:
        if bool(cell.get("is_canonical")) or cell.get("target_kind") == "canonical":
            control_by_window[str(cell["window_name"])] = float(cell["median_p99_ms"])

    annotated: list[dict[str, Any]] = []
    for cell in cells:
        next_cell = dict(cell)
        next_cell["verdict"] = cell_verdict(
            next_cell,
            control_by_window.get(str(next_cell["window_name"])),
            driver_allowlist=driver_allowlist,
            thresholds=resolved,
        )
        annotated.append(next_cell)

    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in annotated:
        by_target[_target_key(cell)].append(cell)
        by_path[str(cell["path_name"])].append(cell)
        by_window[str(cell["window_name"])].append(cell)

    defect_cells = [cell for cell in annotated if cell["verdict"] == "cell_defect" and not cell.get("is_canonical")]
    pair_to_windows: dict[tuple[str, str], set[str]] = defaultdict(set)
    for cell in defect_cells:
        pair_to_windows[(str(cell["target_name"]), str(cell["path_name"]))].add(str(cell["window_name"]))
    reproduced = any(len(windows) >= int(resolved["supplemental_defect_min_windows"]) for windows in pair_to_windows.values())
    orthogonal = _orthogonal_corroboration(defect_cells)

    if reproduced and orthogonal["satisfied"]:
        if len(defect_cells) < 2:
            raise ValueError("single-cell defect_located is forbidden")
        verdict = "defect_located"
    else:
        clean_control_windows = sum(
            1
            for value in control_by_window.values()
            if value is not None and value <= float(resolved["canonical_control_p99_kill_ms"])
        )
        no_supplemental_exceeds_control = True
        for cell in annotated:
            if cell.get("is_canonical"):
                continue
            control = control_by_window.get(str(cell["window_name"]))
            if control is not None and float(cell["median_p99_ms"]) > float(resolved["supplemental_carry_multiplier_of_control"]) * control:
                no_supplemental_exceeds_control = False
                break
        if clean_control_windows >= int(resolved["canonical_min_windows_kill"]) and no_supplemental_exceeds_control:
            verdict = "hypothesis_killed"
        else:
            verdict = "carried_narrower_with_close_with_prejudice_rule"

    per_cell = {cell["cell_id"]: cell for cell in annotated}
    per_target = {key: axis_rollup(value) for key, value in sorted(by_target.items())}
    per_path = {key: axis_rollup(value) for key, value in sorted(by_path.items())}
    per_window = {key: axis_rollup(value) for key, value in sorted(by_window.items())}
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "matrix_verdict": verdict,
        "per_cell": per_cell,
        "per_target": per_target,
        "per_path": per_path,
        "per_window": per_window,
        "per_target_rollup": per_target,
        "per_path_rollup": per_path,
        "per_window_rollup": per_window,
        "orthogonal_corroboration": orthogonal,
        "reproducing_defect_cells": [cell["cell_id"] for cell in defect_cells],
        "control_p99_per_window": control_by_window,
    }


def mann_whitney_u(x: list[float], y: list[float], *, continuity_correction: bool = False) -> dict[str, Any]:
    n_x = len(x)
    n_y = len(y)
    empty = n_x == 0 or n_y == 0
    all_identical = bool(x or y) and len(set(float(value) for value in [*x, *y])) == 1
    if empty or all_identical or (n_x == 1 and n_y == 1):
        return {"u_x": None, "u_y": None, "z": None, "p": None, "degenerate": True, "tie_correction": "wilcoxon-mid-rank"}

    pooled = [(float(value), "x") for value in x] + [(float(value), "y") for value in y]
    pooled.sort(key=lambda item: item[0])
    rank_sum_x = 0.0
    tie_sizes: list[int] = []
    index = 0
    while index < len(pooled):
        end = index + 1
        while end < len(pooled) and pooled[end][0] == pooled[index][0]:
            end += 1
        mid_rank = (index + 1 + end) / 2.0
        tie_sizes.append(end - index)
        for _, arm in pooled[index:end]:
            if arm == "x":
                rank_sum_x += mid_rank
        index = end

    u_x = rank_sum_x - n_x * (n_x + 1) / 2.0
    u_y = n_x * n_y - u_x
    mu = n_x * n_y / 2.0
    n_total = n_x + n_y
    tie_sum = sum(size**3 - size for size in tie_sizes if size >= 2)
    sigma_sq = (n_x * n_y / 12.0) * ((n_total + 1) - tie_sum / (n_total * (n_total - 1)))
    if sigma_sq <= 0:
        return {"u_x": None, "u_y": None, "z": None, "p": None, "degenerate": True, "tie_correction": "wilcoxon-mid-rank"}
    adjusted_u = u_x
    if continuity_correction and u_x != mu:
        adjusted_u = u_x - 0.5 if u_x > mu else u_x + 0.5
    z = (adjusted_u - mu) / math.sqrt(sigma_sq)
    phi = 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0)))
    p_value = 2.0 * (1.0 - phi)
    return {"u_x": u_x, "u_y": u_y, "z": z, "p": p_value, "degenerate": False, "tie_correction": "wilcoxon-mid-rank"}


def bootstrap_ci_median_difference(
    x: list[float],
    y: list[float],
    *,
    seed: int = 220,
    B: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    empty = not x or not y
    all_identical = bool(x or y) and len(set(float(value) for value in [*x, *y])) == 1
    if empty or all_identical or (len(x) == 1 and len(y) == 1):
        return {"ci_lower": None, "ci_upper": None, "point_estimate": None, "B": B, "seed": seed, "degenerate": True, "alpha": alpha}
    x_values = [float(value) for value in x]
    y_values = [float(value) for value in y]
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(B):
        sample_x = [rng.choice(x_values) for _ in range(len(x_values))]
        sample_y = [rng.choice(y_values) for _ in range(len(y_values))]
        diffs.append(float(statistics.median(sample_x) - statistics.median(sample_y)))
    sorted_diffs = sorted(diffs)
    lower_idx = int((alpha / 2) * B)
    upper_idx = int((1 - alpha / 2) * B) - 1  # right-exclusive percentile convention
    return {
        "ci_lower": sorted_diffs[lower_idx],
        "ci_upper": sorted_diffs[upper_idx],
        "point_estimate": float(statistics.median(x_values) - statistics.median(y_values)),
        "B": B,
        "seed": seed,
        "degenerate": False,
        "alpha": alpha,
    }


def _record_from_paths(signal_path: Path, manifest_path: Path) -> dict[str, Any]:
    sheet = json.loads(signal_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ranked = sheet.get("ranked") or sheet.get("ranked_drivers") or []
    return {
        "cell_id": str(manifest["cell_id"]),
        "target_kind": str(manifest["target_kind"]),
        "is_canonical": manifest.get("target_kind") == "canonical",
        "target_name": str(manifest["target_name"]),
        "path_name": str(manifest["path_name"]),
        "window_name": str(manifest["window_name"]),
        "p99_ms": _latency_value(sheet, "p99_ms"),
        "primary_driver": sheet.get("primary_driver"),
        "ranked": [str(driver) for driver in ranked] if isinstance(ranked, list) else [],
        "per_second_samples_ms": [float(value) for value in sheet.get("per_second_samples_ms", [])],
    }


def _records_from_scenario(scenario_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    base = scenario_path.parents[1]
    records = []
    for name in scenario.get("cells", []):
        records.append(_record_from_paths(base / "signal-sheets" / f"{name}.json", base / "cell-manifests" / f"{name}.json"))
    return scenario, records


def aggregate_scenario(scenario_path: Path, yaml_path: Path = DEFAULT_YAML_PATH) -> dict[str, Any]:
    definition = load_matrix_definition(yaml_path)
    _scenario, records = _records_from_scenario(scenario_path)
    cells = [collapse_replicates_to_cell(group) for group in group_replicates_by_base_cell_id(records).values()]
    return matrix_verdict(cells, thresholds=definition["thresholds"], driver_allowlist=definition["driver_allowlist_set"])


def aggregate(evidence_root: Path, yaml_path: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    definition = load_matrix_definition(yaml_path)
    records: list[dict[str, Any]] = []
    for manifest_path in sorted(evidence_root.glob("**/phase220-cell.json")):
        signal_path = manifest_path.parent / "signal-sheet.json"
        if signal_path.exists():
            records.append(_record_from_paths(signal_path, manifest_path))
    cells = [collapse_replicates_to_cell(group) for group in group_replicates_by_base_cell_id(records).values()]
    summary = matrix_verdict(cells, thresholds=definition["thresholds"], driver_allowlist=definition["driver_allowlist_set"])
    if output_path is not None:
        _atomic_write_json(output_path, summary)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML_PATH)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = aggregate(args.evidence_root, args.yaml, output_path=args.output)
    if args.output is None:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

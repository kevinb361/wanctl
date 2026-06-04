#!/usr/bin/env python3
"""Phase 227 evidence-completeness gate for Phase 228 verdict readiness.

This is a readiness checker only: it proves the candidate capture exposes the
signals consumed by the locked GATE-01 thresholds, but it does not compute the
accept/reject verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MODE_RE = re.compile(r"\b(besteffort|diffserv3|diffserv4|diffserv8)\b")
TABLE_HEADER_RE = re.compile(r"^\s+(Bulk\s+)?Best Effort(\s+Video)?(\s+Voice)?\s*$")
ROW_RE = re.compile(r"^\s*(?P<label>pkts|backlog|av_delay)\s+(?P<values>.+)$")

STABLE_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_count",
    "baseline_window",
    "interfaces",
    "rrul_p99_latency_under_load_ms_mean",
    "ref_udp_unmarked",
    "ref_tcp_unmarked",
    "marked_ef",
}


class CompletenessError(Exception):
    """Raised when evidence is not ready for Phase 228 verdict evaluation."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact decoder exception not important
        raise CompletenessError(f"could not read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CompletenessError(f"JSON is not an object: {path}")
    return data


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value == value and value not in {float("inf"), float("-inf")}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise CompletenessError(reason)


def require_gate_thresholds(thresholds: dict[str, Any]) -> None:
    for key in ("RRUL_P99_REGRESSION_PCT", "RESTART_RATE_INCREASE_PCT", "TRANSITION_RATE_INCREASE_PCT"):
        require(key in thresholds, f"MISSING threshold: {key}")
    ul = thresholds.get("UL_STABILITY")
    require(isinstance(ul, dict), "MISSING threshold: UL_STABILITY")
    tin = thresholds.get("TIN_SEPARATION")
    require(isinstance(tin, dict), "MISSING threshold: TIN_SEPARATION")
    require(isinstance(tin.get("NOISE_BAND_MS"), dict), "MISSING threshold: TIN_SEPARATION.NOISE_BAND_MS")


def require_metric_summary(block: Any, name: str, metric_names: tuple[str, ...]) -> None:
    require(isinstance(block, dict), f"MISSING GATE-01 signal: {name}")
    require(block.get("valid") is True, f"{name} is not verdict-ready: valid is not true")
    require(block.get("run_count") == 3, f"{name} is not verdict-ready: run_count != 3")
    require(block.get("valid_run_count") == 3, f"{name} is not verdict-ready: valid_run_count != 3")
    for run in block.get("runs", []):
        require(isinstance(run, dict) and run.get("valid") is True, f"{name} contains invalid flow")
    for metric_name in metric_names:
        metric = block.get(metric_name)
        require(isinstance(metric, dict), f"MISSING GATE-01 signal: {name}.{metric_name}")
        require(finite_number(metric.get("mean")), f"MISSING GATE-01 signal: {name}.{metric_name}.mean")


def require_summary_signals(summary: dict[str, Any]) -> None:
    for key in STABLE_TOP_LEVEL_KEYS - {"interfaces"}:
        require(key in summary, f"MISSING GATE-01 signal: {key}")
    require(summary.get("run_count") == 3, "run_count != 3")
    require(finite_number(summary.get("rrul_p99_latency_under_load_ms_mean")), "MISSING GATE-01 signal: rrul_p99_latency_under_load_ms_mean")

    window = summary.get("baseline_window")
    require(isinstance(window, dict), "MISSING GATE-01 signal: baseline_window")
    for key in ("restart_rate", "transition_rate", "floor_hit_cycles", "soft_red_dwell_s"):
        require(finite_number(window.get(key)), f"MISSING GATE-01 signal: baseline_window.{key}")

    require_metric_summary(summary.get("ref_udp_unmarked"), "ref_udp_unmarked", ("jitter_ms", "loss_pct"))
    require_metric_summary(summary.get("marked_ef"), "marked_ef", ("jitter_ms", "loss_pct"))
    require(summary["marked_ef"].get("clean_mark") is True, "marked_ef is not verdict-ready: clean_mark is not true")
    require_metric_summary(summary.get("ref_tcp_unmarked"), "ref_tcp_unmarked", ("throughput_mbps",))


def _delay_to_ms(value: str) -> float:
    raw = value.strip()
    if raw.endswith("us"):
        return float(raw[:-2]) / 1000.0
    if raw.endswith("ms"):
        return float(raw[:-2])
    if raw.endswith("s"):
        return float(raw[:-1]) * 1000.0
    return float(raw)


def _parse_backlog(value: str) -> int:
    return int(value.rstrip("b"))


def parse_cake_table(text: str) -> dict[str, dict[str, float | int]]:
    lines = text.splitlines()
    headers: list[str] = []
    rows: dict[str, dict[str, float | int]] = {}
    for line in lines:
        if TABLE_HEADER_RE.match(line):
            headers = [part for part in re.split(r"\s{2,}", line.strip()) if part]
            continue
        if not headers:
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        label = match.group("label")
        values = [part for part in re.split(r"\s+", match.group("values").strip()) if part]
        if len(values) != len(headers):
            continue
        for tin, raw in zip(headers, values):
            row = rows.setdefault(tin, {})
            if label == "pkts":
                row["packets"] = int(raw)
            elif label == "backlog":
                row["backlog_bytes"] = _parse_backlog(raw)
            elif label == "av_delay":
                row["avg_delay_ms"] = _delay_to_ms(raw)
    return rows


def summary_has_tin_separation_inputs(summary: dict[str, Any]) -> bool:
    interfaces = summary.get("interfaces")
    if not isinstance(interfaces, dict) or not interfaces:
        return False
    found_be = False
    found_non_be = False
    for tins in interfaces.values():
        if not isinstance(tins, dict):
            continue
        for tin, row in tins.items():
            if not isinstance(row, dict):
                continue
            has_metrics = finite_number(row.get("mean_packets_delta")) and finite_number(row.get("mean_delay_delta_ms")) and finite_number(row.get("mean_backlog_bytes_delta"))
            if not has_metrics:
                continue
            if str(tin).lower() in {"0", "best effort", "besteffort", "best_effort"}:
                found_be = True
            else:
                found_non_be = True
    return found_be and found_non_be


def qdisc_files_are_complete(run_dir: Path) -> None:
    for iface in ("spec-router", "spec-modem"):
        for phase in ("before", "during", "after"):
            path = run_dir / f"tc-qdisc-{iface}.{phase}.txt"
            require(path.is_file() and path.stat().st_size > 0, f"run {run_dir.name} missing qdisc mode proof: {path.name}")
            text = path.read_text(encoding="utf-8", errors="replace")
            require("qdisc cake" in text and MODE_RE.search(text) is not None, f"run {run_dir.name} invalid qdisc mode proof: {path.name}")


def run_tree_has_tin_separation_inputs(run_tree: Path) -> bool:
    found_be = False
    found_non_be = False
    for run_dir in sorted(path for path in run_tree.glob("run-*") if path.is_dir()):
        qdisc_files_are_complete(run_dir)
        for iface in ("spec-router", "spec-modem"):
            rows = parse_cake_table((run_dir / f"tc-qdisc-{iface}.during.txt").read_text(encoding="utf-8", errors="replace"))
            for tin, row in rows.items():
                if not all(key in row for key in ("packets", "backlog_bytes", "avg_delay_ms")):
                    continue
                if str(tin).lower() in {"best effort", "besteffort", "best_effort", "0"}:
                    found_be = True
                elif int(row.get("packets", 0)) > 0 or float(row.get("avg_delay_ms", 0.0)) > 0:
                    found_non_be = True
    return found_be and found_non_be


def require_run_tree(run_tree: Path, summary: dict[str, Any]) -> None:
    runs = sorted(path for path in run_tree.glob("run-*") if path.is_dir())
    require(len(runs) == 3, "run-tree run_count != 3")
    require(summary.get("run_count") == 3, "summary run_count != 3")
    for run_dir in runs:
        qdisc_files_are_complete(run_dir)

    for block_name in ("ref_udp_unmarked", "ref_tcp_unmarked", "marked_ef"):
        block = summary.get(block_name)
        require(isinstance(block, dict), f"MISSING GATE-01 signal: {block_name}")
        require(block.get("valid") is True, f"{block_name} is not verdict-ready")
        for run in block.get("runs", []):
            require(isinstance(run, dict) and run.get("valid") is True, f"{block_name} has invalid flow")


def require_tin_separation(summary: dict[str, Any], run_tree: Path | None) -> None:
    if summary_has_tin_separation_inputs(summary):
        return
    if run_tree is not None and run_tree_has_tin_separation_inputs(run_tree):
        return
    raise CompletenessError("MISSING GATE-01 signal: per-tin separation inputs")


def require_stable_shape(candidate: dict[str, Any], baseline: dict[str, Any]) -> None:
    for key in STABLE_TOP_LEVEL_KEYS:
        require(key in candidate, f"candidate MISSING stable top-level field: {key}")
        require(key in baseline, f"baseline MISSING stable top-level field: {key}")


def check(args: argparse.Namespace) -> None:
    thresholds = load_json(args.thresholds)
    require_gate_thresholds(thresholds)
    candidate = load_json(args.candidate_summary)
    baseline = load_json(args.baseline_summary) if args.baseline_summary else None

    require_summary_signals(candidate)
    run_tree = args.run_tree
    if run_tree is not None:
        require_run_tree(run_tree, candidate)
    require_tin_separation(candidate, run_tree)
    if baseline is not None:
        require_stable_shape(candidate, baseline)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-summary", required=True, type=Path)
    parser.add_argument("--baseline-summary", type=Path)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--run-tree", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        check(args)
    except CompletenessError as exc:
        print(f"not verdict-ready: {exc}", file=sys.stderr)
        return 1
    print("verdict-ready: required GATE-01 signals present and successful")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

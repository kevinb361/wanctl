#!/usr/bin/env python3
# ruff: noqa: N999
"""Evaluate Phase 243 benchmark arms against frozen BENCH-02 thresholds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_ABORT = 2

JsonDict = dict[str, Any]


class GateEvalError(ValueError):
    """Structured input-shape failure for fail-fast gates."""

    def __init__(self, message: str, gate_id: str | None = None) -> None:
        super().__init__(message)
        self.gate_id = gate_id


def load_thresholds(path: Path | None = None) -> dict:
    target = path or (Path(__file__).resolve().parent / "phase243-thresholds.json")
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


def _gate(verdict: str, value: Any, **extra: Any) -> JsonDict:
    result: JsonDict = {"verdict": verdict, "value": value}
    result.update(extra)
    return result


def _delta_pct(current: float, baseline: float) -> float:
    return ((current - baseline) / baseline) * 100.0 if baseline > 0 else (0.0 if current == 0 else float("inf"))


def _require_number(payload: JsonDict, key: str, *, gate_id: str) -> float:
    value = payload.get(key)
    if not isinstance(value, int | float):
        raise GateEvalError(f"missing numeric {key}", gate_id=gate_id)
    return float(value)


def _require_int(payload: JsonDict, key: str, *, gate_id: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GateEvalError(f"missing integer {key}", gate_id=gate_id)
    return value


def _require_profile(arm: JsonDict, *, label: str) -> JsonDict:
    profile = arm.get("profile")
    if not isinstance(profile, dict):
        raise GateEvalError(f"{label} arm missing profile", gate_id="gate_input_completeness")
    invocation_id = profile.get("invocation_id")
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise GateEvalError(f"{label} arm missing invocation_id", gate_id="gate_input_completeness")
    cycle_total = profile.get("autorate_cycle_total")
    if not isinstance(cycle_total, dict):
        raise GateEvalError(
            f"{label} arm missing autorate_cycle_total",
            gate_id="gate_input_completeness",
        )
    for key in ("count", "avg_ms", "p99_ms"):
        if not isinstance(cycle_total.get(key), int | float):
            raise GateEvalError(
                f"{label} autorate_cycle_total missing numeric {key}",
                gate_id="gate_input_completeness",
            )
    for key in ("cpu_nsec_delta", "window_wall_sec", "n_cores"):
        if not isinstance(profile.get(key), int | float):
            raise GateEvalError(
                f"{label} arm missing cpu_nsec evidence field {key}",
                gate_id="gate_input_completeness",
            )
    return profile


def _require_hygiene(arm: JsonDict, *, label: str) -> list[JsonDict]:
    hygiene = arm.get("hygiene")
    if not isinstance(hygiene, list) or not hygiene:
        raise GateEvalError(f"{label} arm missing hygiene rows", gate_id="gate_input_completeness")
    rows: list[JsonDict] = []
    for index, row in enumerate(hygiene):
        if not isinstance(row, dict):
            raise GateEvalError(f"{label} hygiene row {index} is not an object", gate_id="gate_input_completeness")
        for key in ("fd", "tasks", "zombies"):
            if not isinstance(row.get(key), int):
                raise GateEvalError(
                    f"{label} hygiene row {index} missing integer {key}",
                    gate_id="gate_input_completeness",
                )
        rows.append(row)
    return rows


def _cycle_total(profile: JsonDict) -> JsonDict:
    cycle_total = profile["autorate_cycle_total"]
    if not isinstance(cycle_total, dict):  # guarded by _require_profile
        raise GateEvalError("autorate_cycle_total is not an object", gate_id="gate_input_completeness")
    return cycle_total


def _cpu_pct(profile: JsonDict, thresholds: JsonDict) -> float:
    normalization = thresholds.get("CPU_NORMALIZATION")
    if normalization != "per_core":
        raise GateEvalError(
            f"unsupported CPU_NORMALIZATION {normalization!r}",
            gate_id="gate_input_completeness",
        )
    cpu_nsec_delta = _require_number(profile, "cpu_nsec_delta", gate_id="gate_input_completeness")
    window_wall_sec = _require_number(profile, "window_wall_sec", gate_id="gate_input_completeness")
    n_cores = _require_number(profile, "n_cores", gate_id="gate_input_completeness")
    if window_wall_sec <= 0 or n_cores <= 0:
        raise GateEvalError("CPU evidence has non-positive wall window or core count", gate_id="gate_input_completeness")
    return cpu_nsec_delta / (window_wall_sec * 1_000_000_000.0 * n_cores) * 100.0


def _window_medians(values: list[int], window_count: int = 4) -> list[float]:
    if len(values) < window_count:
        return [float(value) for value in values]
    medians: list[float] = []
    for index in range(window_count):
        start = round(index * len(values) / window_count)
        end = round((index + 1) * len(values) / window_count)
        window = values[start:end]
        if window:
            medians.append(float(median(window)))
    return medians


def _strictly_increasing(values: list[float]) -> bool:
    return len(values) >= 2 and all(current > previous for previous, current in zip(values, values[1:], strict=False))


def _record_provenance() -> JsonDict:
    helper = Path(__file__).resolve().parent / "phase243-prereg-provenance.sh"
    result = subprocess.run(
        [str(helper), "record"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise GateEvalError(
            f"failed to record prereg provenance: {result.stderr.strip()}",
            gate_id="gate_prereg_provenance",
        )
    payload = json.loads(result.stdout)
    for key in ("thresholds_blob_sha", "prereg_commit_sha"):
        value = payload.get(key)
        if not isinstance(value, str) or len(value) != 40:
            raise GateEvalError(f"invalid provenance field {key}", gate_id="gate_prereg_provenance")
    return payload


def _evaluate_pair(pair_id: str, arms: JsonDict, thresholds: JsonDict) -> JsonDict:
    icmplib = arms.get("icmplib")
    fping = arms.get("fping")
    if not isinstance(icmplib, dict) or not isinstance(fping, dict):
        raise GateEvalError(f"{pair_id} requires icmplib and fping arms", gate_id="gate_input_completeness")

    icmp_profile = _require_profile(icmplib, label=f"{pair_id} icmplib")
    fping_profile = _require_profile(fping, label=f"{pair_id} fping")
    icmp_hygiene = _require_hygiene(icmplib, label=f"{pair_id} icmplib")
    fping_hygiene = _require_hygiene(fping, label=f"{pair_id} fping")
    icmp_cycle = _cycle_total(icmp_profile)
    fping_cycle = _cycle_total(fping_profile)

    floor = max(
        _require_int(thresholds, "MIN_CYCLES", gate_id="gate_thresholds"),
        _require_int(thresholds, "CYCLE_HZ", gate_id="gate_thresholds")
        * 60
        * _require_int(thresholds, "MIN_MINUTES", gate_id="gate_thresholds"),
    )

    gates: JsonDict = {}
    icmp_avg = float(icmp_cycle["avg_ms"])
    icmp_p99 = float(icmp_cycle["p99_ms"])
    avg_rep_delta = abs(icmp_avg - float(thresholds["ICMPLIB_REPRESENTATIVE_AVG_MS"]))
    p99_rep_delta = abs(icmp_p99 - float(thresholds["ICMPLIB_REPRESENTATIVE_P99_MS"]))
    rep_pass = (
        avg_rep_delta <= float(thresholds["ICMPLIB_REPRESENTATIVE_AVG_TOL_MS"])
        and p99_rep_delta <= float(thresholds["ICMPLIB_REPRESENTATIVE_P99_TOL_MS"])
    )
    gates["gate_icmplib_representativeness"] = _gate(
        "pass" if rep_pass else "fail",
        {
            "avg_ms": icmp_avg,
            "p99_ms": icmp_p99,
            "avg_delta_ms": avg_rep_delta,
            "p99_delta_ms": p99_rep_delta,
        },
        outcome_on_fail="input_error",
    )

    avg_delta_pct = _delta_pct(float(fping_cycle["avg_ms"]), icmp_avg)
    gates["gate_avg_delta_pct"] = _gate(
        "pass" if avg_delta_pct <= float(thresholds["CYCLE_AVG_REGRESSION_PCT"]) else "fail",
        {"avg_delta_pct": avg_delta_pct, "threshold_pct": thresholds["CYCLE_AVG_REGRESSION_PCT"]},
    )

    p99_delta_pct = _delta_pct(float(fping_cycle["p99_ms"]), icmp_p99)
    gates["gate_p99_delta_pct"] = _gate(
        "pass" if p99_delta_pct <= float(thresholds["CYCLE_P99_REGRESSION_PCT"]) else "fail",
        {"p99_delta_pct": p99_delta_pct, "threshold_pct": thresholds["CYCLE_P99_REGRESSION_PCT"]},
    )

    fping_p99 = float(fping_cycle["p99_ms"])
    gates["gate_p99_abs_ceiling_ms"] = _gate(
        "pass" if fping_p99 < float(thresholds["CYCLE_P99_ABS_CEILING_MS"]) else "fail",
        {"p99_ms": fping_p99, "ceiling_ms": thresholds["CYCLE_P99_ABS_CEILING_MS"]},
    )

    icmp_cpu_pct = _cpu_pct(icmp_profile, thresholds)
    fping_cpu_pct = _cpu_pct(fping_profile, thresholds)
    cpu_delta_pts = fping_cpu_pct - icmp_cpu_pct
    gates["gate_cpu_delta_pts"] = _gate(
        "pass" if cpu_delta_pts < float(thresholds["CPU_DELTA_PCT_POINTS"]) else "fail",
        {
            "cpu_delta_pts": cpu_delta_pts,
            "icmplib_cpu_pct": icmp_cpu_pct,
            "fping_cpu_pct": fping_cpu_pct,
            "normalization": thresholds["CPU_NORMALIZATION"],
            "threshold_pts": thresholds["CPU_DELTA_PCT_POINTS"],
        },
    )

    max_zombies = max(int(row["zombies"]) for row in fping_hygiene + icmp_hygiene)
    gates["gate_zombies"] = _gate(
        "pass" if max_zombies <= int(thresholds["ZOMBIES_MAX"]) else "fail",
        {"max_zombies": max_zombies, "threshold": thresholds["ZOMBIES_MAX"]},
    )

    fd_values = [int(row["fd"]) for row in fping_hygiene]
    fd_medians = _window_medians(fd_values)
    gates["gate_fd_trend"] = _gate(
        "fail" if _strictly_increasing(fd_medians) else "pass",
        {"window_medians": fd_medians},
    )

    baseline_tasks = int(icmp_hygiene[0]["tasks"])
    max_tasks = max(int(row["tasks"]) for row in fping_hygiene + icmp_hygiene)
    task_limit = baseline_tasks + int(thresholds["TASKS_BOUND"])
    gates["gate_tasks_bound"] = _gate(
        "pass" if max_tasks <= task_limit else "fail",
        {"baseline_tasks": baseline_tasks, "max_tasks": max_tasks, "task_limit": task_limit},
    )

    stall = fping_profile.get("stall")
    if not isinstance(stall, dict):
        raise GateEvalError(f"{pair_id} fping profile missing stall block", gate_id="gate_input_completeness")
    stall_events = stall.get("stall_events")
    if not isinstance(stall_events, list):
        raise GateEvalError(f"{pair_id} fping stall_events missing", gate_id="gate_input_completeness")
    gates["gate_stall_events"] = _gate(
        "pass" if len(stall_events) == 0 else "fail",
        {"stall_event_count": len(stall_events), "threshold_ms": thresholds["STALL_GAP_MS"]},
    )

    min_count = min(int(icmp_cycle["count"]), int(fping_cycle["count"]))
    gates["gate_n_floor"] = _gate(
        "pass" if min_count >= floor else "fail",
        {"min_count": min_count, "floor": floor, "CYCLE_HZ": thresholds["CYCLE_HZ"]},
    )

    return {"gates": gates}


def evaluate(pairs: dict[str, JsonDict], thresholds_path: Path | None = None) -> JsonDict:
    thresholds = load_thresholds(thresholds_path)
    comparisons = {pair_id: _evaluate_pair(pair_id, arms, thresholds) for pair_id, arms in pairs.items()}
    any_input_error = any(
        gate["verdict"] == "fail" and gate.get("outcome_on_fail") == "input_error"
        for comparison in comparisons.values()
        for gate in comparison["gates"].values()
    )
    any_fail = any(
        gate["verdict"] == "fail"
        for comparison in comparisons.values()
        for gate in comparison["gates"].values()
    )
    outcome = "input_error" if any_input_error else "rollback_trigger" if any_fail else "pass"
    return {
        "evaluated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "thresholds": thresholds,
        "provenance": _record_provenance(),
        "comparisons": comparisons,
        "outcome": outcome,
    }


def _read_json(path: Path) -> JsonDict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise GateEvalError(f"JSON root is not an object: {path}", gate_id="gate_input_completeness")
    return data


def _read_hygiene(path: Path) -> list[JsonDict]:
    rows: list[JsonDict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateEvalError(
                    f"invalid hygiene NDJSON at {path}:{line_no}",
                    gate_id="gate_input_completeness",
                ) from exc
            if not isinstance(row, dict):
                raise GateEvalError(
                    f"hygiene NDJSON row is not an object at {path}:{line_no}",
                    gate_id="gate_input_completeness",
                )
            rows.append(row)
    return rows


def _parse_arm(value: str) -> tuple[str, str, str, Path, Path]:
    parts = value.split(":", 4)
    if len(parts) != 5:
        raise GateEvalError(
            "--arm must be WAN:LOAD:BACKEND:PROFILE_JSON:HYGIENE_NDJSON",
            gate_id="gate_input_completeness",
        )
    wan, load, backend, profile_path, hygiene_path = parts
    if backend not in {"icmplib", "fping"}:
        raise GateEvalError(f"unsupported backend in --arm: {backend}", gate_id="gate_input_completeness")
    return wan, load, backend, Path(profile_path), Path(hygiene_path)


def _pairs_from_args(arms: list[str]) -> dict[str, JsonDict]:
    pairs: dict[str, JsonDict] = {}
    for arm_arg in arms:
        wan, load, backend, profile_path, hygiene_path = _parse_arm(arm_arg)
        pair_id = f"{wan}/{load}"
        pairs.setdefault(pair_id, {})[backend] = {
            "profile": _read_json(profile_path),
            "hygiene": _read_hygiene(hygiene_path),
        }
    return pairs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 243 frozen-threshold benchmark gate evaluator")
    parser.add_argument(
        "--arm",
        action="append",
        required=True,
        help="WAN:LOAD:BACKEND:PROFILE_JSON:HYGIENE_NDJSON; provide icmplib and fping per WAN/load",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path(__file__).resolve().parent / "phase243-thresholds.json",
    )
    parser.add_argument("--output", type=Path, default=Path("243-BENCHMARK-VERDICT.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        verdict = evaluate(_pairs_from_args(args.arm), thresholds_path=args.thresholds)
    except GateEvalError as exc:
        payload: JsonDict = {"error": str(exc), "gate_id": exc.gate_id, "outcome": "input_error"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return EXIT_ABORT

    args.output.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if verdict["outcome"] == "pass":
        return EXIT_PASS
    if verdict["outcome"] == "rollback_trigger":
        return EXIT_BLOCK
    return EXIT_ABORT


if __name__ == "__main__":
    sys.exit(main())

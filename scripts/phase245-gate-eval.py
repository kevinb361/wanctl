#!/usr/bin/env python3
# ruff: noqa: N999
"""Evaluate Phase 245 live A/B summary against frozen AB-03 thresholds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_ABORT = 2

JsonDict = dict[str, Any]
FLOAT_EPSILON = 1e-9


class GateEvalError(ValueError):
    """Structured input-shape failure for fail-fast gates."""

    def __init__(self, message: str, gate_id: str | None = None) -> None:
        super().__init__(message)
        self.gate_id = gate_id


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    target = path or (Path(__file__).resolve().parent / "phase245-thresholds.json")
    with target.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise GateEvalError("thresholds root is not an object", gate_id="gate_thresholds")
    return payload


def _gate(verdict: str, value: Any, **extra: Any) -> JsonDict:
    result: JsonDict = {"verdict": verdict, "value": value}
    result.update(extra)
    return result


def _require_mapping(payload: JsonDict, key: str, *, gate_id: str) -> JsonDict:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise GateEvalError(f"missing object {key}", gate_id=gate_id)
    return value


def _require_number(payload: JsonDict, key: str, *, gate_id: str) -> float:
    value = payload.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise GateEvalError(f"missing numeric {key}", gate_id=gate_id)
    return float(value)


def _require_int(payload: JsonDict, key: str, *, gate_id: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise GateEvalError(f"missing integer {key}", gate_id=gate_id)
    return value


def _delta_pct(current: float, baseline: float) -> float:
    return ((current - baseline) / baseline) * 100.0 if baseline > 0 else (0.0 if current == 0 else float("inf"))


def _read_json(path: Path) -> JsonDict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise GateEvalError(f"JSON root is not an object: {path}", gate_id="gate_input_completeness")
    return data


def _record_provenance() -> JsonDict:
    helper = Path(__file__).resolve().parent / "phase245-prereg-provenance.sh"
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


def _backend_samples(summary: JsonDict, backend: str) -> JsonDict:
    samples = _require_mapping(summary, "backend_samples", gate_id="gate_input_completeness")
    arm = samples.get(backend)
    if not isinstance(arm, dict):
        raise GateEvalError(f"missing backend_samples.{backend}", gate_id="gate_input_completeness")
    return arm


def _decision_enable_pct(arm: JsonDict, backend: str) -> float:
    decisions = _require_mapping(arm, "steering_decisions", gate_id=f"gate_{backend}_decision_input")
    enable = _require_number(decisions, "enable", gate_id=f"gate_{backend}_decision_input")
    disable = _require_number(decisions, "disable", gate_id=f"gate_{backend}_decision_input")
    total = enable + disable
    if total <= 0:
        raise GateEvalError(f"{backend} steering_decisions total must be positive", gate_id="gate_steering_decision_stability")
    return enable / total * 100.0


def _backend_fraction(arm: JsonDict, backend: str) -> float:
    wanctl_cycles = _require_number(arm, "wanctl_backend_cycles", gate_id="gate_min_backend_cycle_fraction")
    total_cycles = _require_number(arm, "total_accepted_cycles", gate_id="gate_min_backend_cycle_fraction")
    if total_cycles <= 0:
        raise GateEvalError(f"{backend} total_accepted_cycles must be positive", gate_id="gate_min_backend_cycle_fraction")
    return wanctl_cycles / total_cycles


def evaluate(summary: JsonDict, thresholds_path: Path | None = None) -> JsonDict:
    thresholds = load_thresholds(thresholds_path)
    icmp = _backend_samples(summary, "icmplib")
    fping = _backend_samples(summary, "fping")

    gates: JsonDict = {}

    icmp_median = _require_number(icmp, "median_rtt_ms", gate_id="gate_rtt_agreement")
    fping_median = _require_number(fping, "median_rtt_ms", gate_id="gate_rtt_agreement")
    rtt_delta = abs(fping_median - icmp_median)
    rtt_tol = float(thresholds["RTT_AGREEMENT_TOL_MS"])
    gates["rtt_agreement"] = _gate(
        "pass" if rtt_delta <= rtt_tol + FLOAT_EPSILON else "fail",
        {"median_icmplib_ms": icmp_median, "median_fping_ms": fping_median, "delta_ms": rtt_delta, "threshold_ms": rtt_tol},
    )

    icmp_avg = _require_number(icmp, "cycle_avg_ms", gate_id="gate_cycle_budget_nonregression")
    fping_avg = _require_number(fping, "cycle_avg_ms", gate_id="gate_cycle_budget_nonregression")
    icmp_p99 = _require_number(icmp, "cycle_p99_ms", gate_id="gate_cycle_budget_nonregression")
    fping_p99 = _require_number(fping, "cycle_p99_ms", gate_id="gate_cycle_budget_nonregression")
    avg_delta_pct = _delta_pct(fping_avg, icmp_avg)
    p99_delta_pct = _delta_pct(fping_p99, icmp_p99)
    cycle_pass = (
        avg_delta_pct <= float(thresholds["CYCLE_AVG_REGRESSION_PCT"]) + FLOAT_EPSILON
        and p99_delta_pct <= float(thresholds["CYCLE_P99_REGRESSION_PCT"]) + FLOAT_EPSILON
        and fping_p99 < float(thresholds["CYCLE_P99_ABS_CEILING_MS"])
    )
    gates["cycle_budget_nonregression"] = _gate(
        "pass" if cycle_pass else "fail",
        {
            "avg_delta_pct": avg_delta_pct,
            "p99_delta_pct": p99_delta_pct,
            "fping_p99_ms": fping_p99,
            "avg_threshold_pct": thresholds["CYCLE_AVG_REGRESSION_PCT"],
            "p99_threshold_pct": thresholds["CYCLE_P99_REGRESSION_PCT"],
            "p99_ceiling_ms": thresholds["CYCLE_P99_ABS_CEILING_MS"],
        },
    )

    icmp_loss = _require_number(icmp, "loss_rate_pct", gate_id="gate_loss_detection_nonregression")
    fping_loss = _require_number(fping, "loss_rate_pct", gate_id="gate_loss_detection_nonregression")
    loss_delta = abs(fping_loss - icmp_loss)
    loss_tol = float(thresholds["LOSS_DETECTION_MAX_DELTA_PCT"])
    gates["loss_detection_nonregression"] = _gate(
        "pass" if loss_delta <= loss_tol + FLOAT_EPSILON else "fail",
        {"icmplib_loss_rate_pct": icmp_loss, "fping_loss_rate_pct": fping_loss, "delta_pct": loss_delta, "threshold_pct": loss_tol},
    )

    icmp_fraction = _backend_fraction(icmp, "icmplib")
    fping_fraction = _backend_fraction(fping, "fping")
    min_fraction = min(icmp_fraction, fping_fraction)
    fraction_floor = float(thresholds["MIN_WANCTL_BACKEND_CYCLE_FRACTION"])
    gates["min_backend_cycle_fraction"] = _gate(
        "pass" if min_fraction >= fraction_floor - FLOAT_EPSILON else "fail",
        {"min_fraction": min_fraction, "icmplib_fraction": icmp_fraction, "fping_fraction": fping_fraction, "threshold": fraction_floor},
    )

    baseline_nrestarts = _require_int(summary, "baseline_nrestarts", gate_id="gate_unexpected_restarts")
    planned_restarts = _require_int(summary, "planned_restarts", gate_id="gate_unexpected_restarts")
    total_nrestarts = _require_int(summary, "total_nrestarts", gate_id="gate_unexpected_restarts")
    unexpected_restarts = total_nrestarts - baseline_nrestarts - planned_restarts
    if unexpected_restarts < 0:
        raise GateEvalError("computed unexpected_restarts is negative", gate_id="gate_unexpected_restarts")
    max_unexpected = _require_int(thresholds, "MAX_UNEXPECTED_RESTARTS", gate_id="gate_thresholds")
    max_planned_raw = thresholds.get("MAX_PLANNED_RESTARTS")
    planned_ok = True if max_planned_raw is None else planned_restarts <= int(max_planned_raw)
    restart_ok = unexpected_restarts <= max_unexpected and planned_ok
    gates["unexpected_restarts"] = _gate(
        "pass" if restart_ok else "fail",
        {
            "baseline_nrestarts": baseline_nrestarts,
            "planned_restarts": planned_restarts,
            "total_nrestarts": total_nrestarts,
            "unexpected_restarts": unexpected_restarts,
            "max_unexpected_restarts": max_unexpected,
            "max_planned_restarts": max_planned_raw,
        },
    )

    icmp_enable_pct = _decision_enable_pct(icmp, "icmplib")
    fping_enable_pct = _decision_enable_pct(fping, "fping")
    decision_delta = abs(fping_enable_pct - icmp_enable_pct)
    stability_tol = float(thresholds["STEERING_DECISION_STABILITY_MAX_DELTA_PCT"])
    gates["steering_decision_stability"] = _gate(
        "pass" if decision_delta <= stability_tol + FLOAT_EPSILON else "fail",
        {"icmplib_enable_pct": icmp_enable_pct, "fping_enable_pct": fping_enable_pct, "delta_pct": decision_delta, "threshold_pct": stability_tol},
    )

    hard_safety_fail = any(
        gates[name]["verdict"] == "fail"
        for name in ("cycle_budget_nonregression", "min_backend_cycle_fraction", "unexpected_restarts")
    )
    any_fail = any(gate["verdict"] == "fail" for gate in gates.values())
    outcome = "rollback_trigger" if hard_safety_fail or any_fail else "pass"
    recommendation = "switch-eligible" if outcome == "pass" and fping_median < icmp_median and fping_loss <= icmp_loss else "keep-icmplib"

    return {
        "evaluated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "thresholds_path": str(thresholds_path or (Path(__file__).resolve().parent / "phase245-thresholds.json")),
        "provenance": _record_provenance(),
        "gates": gates,
        "outcome": outcome,
        "recommendation": recommendation,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 245 frozen-threshold A/B gate evaluator")
    parser.add_argument("--summary", type=Path, required=True, help="Aggregated Phase 245 A/B run summary JSON")
    parser.add_argument("--thresholds", type=Path, default=Path(__file__).resolve().parent / "phase245-thresholds.json")
    parser.add_argument("--output", type=Path, default=Path("245-AB-VERDICT.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        verdict = evaluate(_read_json(args.summary), thresholds_path=args.thresholds)
    except GateEvalError as exc:
        payload: JsonDict = {"error": str(exc), "gate_id": exc.gate_id, "outcome": "input_error"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return EXIT_ABORT

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if verdict["outcome"] == "pass":
        return EXIT_PASS
    if verdict["outcome"] == "rollback_trigger":
        return EXIT_BLOCK
    return EXIT_ABORT


if __name__ == "__main__":
    sys.exit(main())

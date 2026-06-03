#!/usr/bin/env python3
# ruff: noqa: N999
"""Phase 224 canary gate evaluator.

Consumes raw steering ``/health`` JSON plus ``phase224-spine-probe.sh`` output
and emits a verdict JSON. The restart-window classification is governed by
``.planning/decisions/phase-224-clean-restart-risk-acceptance.md``: a bounded
post-restart binary-on/off symptom is distinct from a steady-state rollback
trigger. The spectrum-state gate is explicitly exempt because code identity is
deterministic across restarts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class GateEvalError(ValueError):
    """Structured input-shape failure for fail-fast gates."""

    def __init__(self, message: str, gate_id: str | None = None) -> None:
        super().__init__(message)
        self.gate_id = gate_id


def _read_json(path_or_dash: str) -> Any:
    if path_or_dash == "-":
        return json.load(sys.stdin)
    with Path(path_or_dash).open() as handle:
        return json.load(handle)


def _parse_ts(value: str, *, field: str) -> datetime:
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise GateEvalError(f"invalid {field} ISO8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validate_raw_health(health: Any) -> JsonDict:
    if isinstance(health, list):
        raise GateEvalError(
            "gate-eval requires raw /health JSON, not canary-check --json summary; "
            "invoke ssh host curl http://127.0.0.1:9102/health"
        )
    if not isinstance(health, dict):
        raise GateEvalError("gate-eval requires raw /health JSON object")
    required = ("version", "status", "decision", "rtt_source")
    missing = [key for key in required if key not in health]
    if missing:
        raise GateEvalError(
            "gate-eval requires raw /health JSON with keys "
            f"version, status, decision, rtt_source; missing {missing}"
        )
    if not isinstance(health.get("decision"), dict) or not isinstance(
        health.get("rtt_source"), dict
    ):
        raise GateEvalError("raw /health decision and rtt_source fields must be objects")
    return health


def _bool_gate(value: Any) -> str:
    return "pass" if value is True else "fail"


def _gate(verdict: str, value: Any, **extra: Any) -> JsonDict:
    result: JsonDict = {"verdict": verdict, "value": value}
    result.update(extra)
    return result


def _require_spectrum_fingerprint(spine: JsonDict) -> JsonDict:
    # Required production proxy shape: method == "code-fingerprint" with hashes.
    spectrum = spine.get("spectrum_state_not_written_by_daemon")
    if not isinstance(spectrum, dict):
        raise GateEvalError(
            "gate_spectrum_state_not_written_by_daemon requires spine block object",
            gate_id="gate_spectrum_state_not_written_by_daemon",
        )
    required = ("method", "deployed_sha256", "baseline_sha256")
    missing = [key for key in required if key not in spectrum]
    if missing or spectrum.get("method") != "code-fingerprint":
        raise GateEvalError(
            "gate_spectrum_state_not_written_by_daemon requires method == "
            "\"code-fingerprint\" with deployed_sha256 and baseline_sha256; "
            "legacy file-absence spectrum_state shape is not accepted",
            gate_id="gate_spectrum_state_not_written_by_daemon",
        )
    return spectrum


def _is_restart_window_symptom(
    *,
    captured_at: datetime,
    observation_start: datetime,
    restart_window_cycles: int,
    time_in_state_seconds: Any,
) -> tuple[bool, float, float]:
    seconds_since_restart = (captured_at - observation_start).total_seconds()
    restart_window_seconds = restart_window_cycles * 0.05
    try:
        time_in_state = float(time_in_state_seconds)
    except (TypeError, ValueError):
        return False, seconds_since_restart, restart_window_seconds
    return (
        seconds_since_restart <= restart_window_seconds
        and time_in_state <= seconds_since_restart
    ), seconds_since_restart, restart_window_seconds


def evaluate(
    *,
    health_payload: Any,
    spine_payload: Any,
    expected_version: str,
    snapshot: str | None,
    observation_start_ts: str,
    observation_end_ts: str,
    restart_window_cycles: int = 15,
    rtt_staleness_seconds: float = 5.0,
) -> JsonDict:
    health = _validate_raw_health(health_payload)
    if not isinstance(spine_payload, dict):
        raise GateEvalError("spine JSON must be an object")
    spine = spine_payload.get("spine")
    if not isinstance(spine, dict):
        raise GateEvalError("spine JSON must contain object key 'spine'")

    captured_at_raw = spine_payload.get("captured_at")
    if not isinstance(captured_at_raw, str):
        raise GateEvalError("spine JSON must contain captured_at ISO8601 string")
    captured_at = _parse_ts(captured_at_raw, field="captured_at")
    observation_start = _parse_ts(observation_start_ts, field="observation_start_ts")
    observation_end = _parse_ts(observation_end_ts, field="observation_end_ts")

    gates: JsonDict = {}
    gates["gate_version_alignment"] = _gate(
        "pass"
        if health.get("version") == expected_version and health.get("status") == "healthy"
        else "fail",
        {"version": health.get("version"), "status": health.get("status")},
    )

    binary = spine.get("binary_on_off") if isinstance(spine, dict) else None
    binary_match = binary.get("match") if isinstance(binary, dict) else None
    gates["gate_binary_on_off"] = _gate(_bool_gate(binary_match), binary)

    only_new = spine.get("only_new_connections") if isinstance(spine, dict) else None
    only_new_match = only_new.get("match") if isinstance(only_new, dict) else None
    gates["gate_only_new_connections"] = _gate(_bool_gate(only_new_match), only_new)

    spectrum = _require_spectrum_fingerprint(spine)
    spectrum_pass = (
        spectrum.get("match") is True
        and spectrum.get("method") == "code-fingerprint"
        and spectrum.get("deployed_sha256") == spectrum.get("baseline_sha256")
    )
    gates["gate_spectrum_state_not_written_by_daemon"] = _gate(
        _bool_gate(spectrum_pass),
        {
            "method": spectrum.get("method"),
            "deployed_sha256": spectrum.get("deployed_sha256"),
            "baseline_sha256": spectrum.get("baseline_sha256"),
            "match": spectrum.get("match"),
        },
        restart_window_eligible=False,
    )

    rtt_age = health.get("rtt_source", {}).get("last_measurement_age_sec")
    rtt_fresh = isinstance(rtt_age, int | float) and rtt_age <= rtt_staleness_seconds
    gates["gate_rtt_source_fresh"] = _gate(
        _bool_gate(rtt_fresh),
        {"last_measurement_age_sec": rtt_age, "threshold": rtt_staleness_seconds},
    )

    time_in_state = health.get("decision", {}).get("time_in_state_seconds")
    daemon_not_degraded = health.get("status") == "healthy" and time_in_state is not None
    gates["gate_daemon_not_degraded"] = _gate(
        _bool_gate(daemon_not_degraded),
        {"status": health.get("status"), "time_in_state_seconds": time_in_state},
    )

    in_restart_window, seconds_since_restart, restart_window_seconds = (
        _is_restart_window_symptom(
            captured_at=captured_at,
            observation_start=observation_start,
            restart_window_cycles=restart_window_cycles,
            time_in_state_seconds=time_in_state,
        )
    )
    if gates["gate_binary_on_off"]["verdict"] == "fail" and in_restart_window:
        gates["gate_binary_on_off"]["verdict"] = "restart_window_symptom"
        gates["gate_binary_on_off"]["restart_window_symptom"] = True
        gates["gate_binary_on_off"]["note"] = (
            "restart_window_symptom_per_decision_artifact"
        )
    else:
        gates["gate_binary_on_off"]["restart_window_symptom"] = False

    for gate_id, gate in gates.items():
        if gate_id != "gate_binary_on_off":
            gate.setdefault("restart_window_symptom", False)

    rollback_trigger = next(
        (gate_id for gate_id, gate in gates.items() if gate["verdict"] == "fail"),
        None,
    )
    window_end_reached = captured_at >= observation_end
    if rollback_trigger is not None:
        outcome = "rollback"
    elif all(gate["verdict"] == "pass" for gate in gates.values()) and window_end_reached:
        outcome = "kept_aligned"
    else:
        outcome = "continue_observation"

    evaluated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "evaluated_at": evaluated_at,
        "observation_start_ts": observation_start_ts,
        "observation_end_ts": observation_end_ts,
        "snapshot_anchor": snapshot,
        "expected_version": expected_version,
        "captured_at": captured_at_raw,
        "window_end_reached": window_end_reached,
        "restart_window": {
            "cycles": restart_window_cycles,
            "seconds": restart_window_seconds,
            "seconds_since_restart": seconds_since_restart,
        },
        "gates": gates,
        "rollback_trigger": rollback_trigger,
        "outcome": outcome,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 224 canary gate evaluator")
    parser.add_argument("--health", required=True, help="Raw steering /health JSON path or -")
    parser.add_argument("--spine", required=True, help="phase224-spine-probe JSON path or -")
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--snapshot", default=None, help="Snapshot directory anchor")
    parser.add_argument("--observation-start-ts", required=True)
    parser.add_argument("--observation-end-ts", required=True)
    parser.add_argument("--restart-window-cycles", type=int, default=15)
    parser.add_argument("--rtt-staleness-seconds", type=float, default=5.0)
    parser.add_argument("--output", default="-", help="Verdict JSON path or -")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        verdict = evaluate(
            health_payload=_read_json(args.health),
            spine_payload=_read_json(args.spine),
            expected_version=args.expected_version,
            snapshot=args.snapshot,
            observation_start_ts=args.observation_start_ts,
            observation_end_ts=args.observation_end_ts,
            restart_window_cycles=args.restart_window_cycles,
            rtt_staleness_seconds=args.rtt_staleness_seconds,
        )
    except GateEvalError as exc:
        payload: JsonDict = {
            "error": str(exc),
            "gate_id": exc.gate_id,
            "outcome": "rollback" if exc.gate_id else "input_error",
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    serialized = json.dumps(verdict, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(serialized)
    else:
        Path(args.output).write_text(serialized)

    if verdict["outcome"] == "kept_aligned":
        return 0
    if verdict["outcome"] == "rollback":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())

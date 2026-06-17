import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase243-gate-eval.py"
PROVENANCE = ROOT / "scripts" / "phase243-prereg-provenance.sh"
THRESHOLDS = ROOT / "scripts" / "phase243-thresholds.json"


def load_module():
    spec = importlib.util.spec_from_file_location("phase243_gate_eval", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def thresholds() -> dict[str, object]:
    return json.loads(THRESHOLDS.read_text())


def profile(
    *,
    count: int | None = None,
    avg_ms: float = 3.0,
    p99_ms: float = 7.0,
    invocation_id: str | None = "inv-1",
    cpu_nsec_delta: int | None = 500_000_000,
    window_wall_sec: float = 60.0,
    n_cores: int = 4,
    stall_events: list[dict[str, float]] | None = None,
) -> dict[str, object]:
    t = thresholds()
    floor = max(int(t["MIN_CYCLES"]), int(t["CYCLE_HZ"]) * 60 * int(t["MIN_MINUTES"]))
    payload: dict[str, object] = {
        "autorate_cycle_total": {
            "count": floor if count is None else count,
            "avg_ms": avg_ms,
            "p99_ms": p99_ms,
        },
        "parse_counters": {"cycle_records": floor if count is None else count},
        "stall": {"stall_events": stall_events or [], "max_gap_ms": 50.0},
    }
    if invocation_id is not None:
        payload["invocation_id"] = invocation_id
    if cpu_nsec_delta is not None:
        payload.update(
            {
                "cpu_nsec_start": 1_000,
                "cpu_nsec_end": 1_000 + cpu_nsec_delta,
                "cpu_nsec_delta": cpu_nsec_delta,
                "window_wall_sec": window_wall_sec,
                "n_cores": n_cores,
            }
        )
    return payload


def hygiene(*, fd: list[int] | None = None, tasks: list[int] | None = None, zombies: list[int] | None = None) -> list[dict[str, int]]:
    fd_values = fd or [10, 10, 11, 10]
    task_values = tasks or [4 for _ in fd_values]
    zombie_values = zombies or [0 for _ in fd_values]
    return [
        {"t": index, "fd": f, "tasks": task_values[index], "zombies": zombie_values[index], "cpu_nsec": index * 100}
        for index, f in enumerate(fd_values)
    ]


def pass_arms() -> dict[str, dict[str, object]]:
    return {
        "icmplib": {"profile": profile(avg_ms=3.0, p99_ms=7.0), "hygiene": hygiene()},
        "fping": {"profile": profile(avg_ms=3.3, p99_ms=8.0, cpu_nsec_delta=800_000_000), "hygiene": hygiene()},
    }


def evaluate_pair(arms: dict[str, dict[str, object]]) -> dict[str, object]:
    module = load_module()
    return module.evaluate({"spectrum/idle": arms}, thresholds_path=THRESHOLDS, require_complete=False)


def gate(verdict: dict[str, object], name: str) -> dict[str, object]:
    return verdict["comparisons"]["spectrum/idle"]["gates"][name]


def test_pass_fixture_records_provenance_and_outcome_pass() -> None:
    verdict = evaluate_pair(pass_arms())

    assert verdict["outcome"] == "pass"
    assert re.fullmatch(r"[0-9a-f]{40}", verdict["provenance"]["thresholds_blob_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", verdict["provenance"]["prereg_commit_sha"])
    assert gate(verdict, "gate_avg_delta_pct")["verdict"] == "pass"


def test_representativeness_outside_frozen_band_is_input_error() -> None:
    arms = pass_arms()
    arms["icmplib"]["profile"] = profile(avg_ms=10.0, p99_ms=7.0)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "input_error"
    assert gate(verdict, "gate_icmplib_representativeness")["verdict"] == "fail"


def test_avg_regression_triggers_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["profile"] = profile(avg_ms=3.7, p99_ms=8.0, cpu_nsec_delta=800_000_000)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_avg_delta_pct")["verdict"] == "fail"


def test_p99_regression_triggers_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["profile"] = profile(avg_ms=3.3, p99_ms=8.5, cpu_nsec_delta=800_000_000)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_p99_delta_pct")["verdict"] == "fail"


def test_absolute_p99_ceiling_triggers_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["profile"] = profile(avg_ms=3.3, p99_ms=10.0, cpu_nsec_delta=800_000_000)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_p99_abs_ceiling_ms")["verdict"] == "fail"


def test_cpu_delta_uses_per_core_cpu_nsec_window_delta() -> None:
    arms = pass_arms()
    arms["icmplib"]["profile"] = profile(cpu_nsec_delta=0, window_wall_sec=10.0, n_cores=4)
    arms["fping"]["profile"] = profile(cpu_nsec_delta=900_000_000, window_wall_sec=10.0, n_cores=4)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_cpu_delta_pts")["verdict"] == "fail"
    assert gate(verdict, "gate_cpu_delta_pts")["value"]["cpu_delta_pts"] >= 2.0


def test_nonzero_zombie_triggers_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["hygiene"] = hygiene(zombies=[0, 0, 1, 0])

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_zombies")["verdict"] == "fail"


def test_monotonic_fd_trend_triggers_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["hygiene"] = hygiene(fd=[10, 11, 12, 13, 14, 15, 16, 17])

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_fd_trend")["verdict"] == "fail"


def test_stall_events_trigger_rollback() -> None:
    arms = pass_arms()
    arms["fping"]["profile"] = profile(stall_events=[{"index": 2, "gap_ms": 150.0}])

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_stall_events")["verdict"] == "fail"


def test_n_floor_uses_frozen_cycle_hz_and_fails_closed_below_floor() -> None:
    t = thresholds()
    floor = max(int(t["MIN_CYCLES"]), int(t["CYCLE_HZ"]) * 60 * int(t["MIN_MINUTES"]))
    arms = pass_arms()
    arms["fping"]["profile"] = profile(count=floor - 1, cpu_nsec_delta=800_000_000)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "gate_n_floor")["verdict"] == "fail"
    assert gate(verdict, "gate_n_floor")["value"]["floor"] == floor


def test_n_floor_boundary_from_frozen_cycle_hz_passes_at_floor() -> None:
    t = thresholds()
    floor = max(int(t["MIN_CYCLES"]), int(t["CYCLE_HZ"]) * 60 * int(t["MIN_MINUTES"]))
    arms = pass_arms()
    arms["icmplib"]["profile"] = profile(count=floor)
    arms["fping"]["profile"] = profile(count=floor, avg_ms=3.3, p99_ms=8.0, cpu_nsec_delta=800_000_000)

    verdict = evaluate_pair(arms)

    assert verdict["outcome"] == "pass"
    assert gate(verdict, "gate_n_floor")["value"]["floor"] == floor


def test_missing_autorate_cycle_total_fails_closed() -> None:
    module = load_module()
    arms = pass_arms()
    del arms["fping"]["profile"]["autorate_cycle_total"]

    with pytest.raises(module.GateEvalError) as exc:
        module.evaluate({"spectrum/idle": arms}, thresholds_path=THRESHOLDS)

    assert exc.value.gate_id == "gate_input_completeness"


def test_missing_cpu_nsec_or_invocation_id_fails_closed() -> None:
    module = load_module()
    arms = pass_arms()
    arms["fping"]["profile"] = profile(cpu_nsec_delta=None)
    with pytest.raises(module.GateEvalError) as cpu_exc:
        module.evaluate({"spectrum/idle": arms}, thresholds_path=THRESHOLDS)
    assert cpu_exc.value.gate_id == "gate_input_completeness"

    arms = pass_arms()
    arms["fping"]["profile"] = profile(invocation_id=None)
    with pytest.raises(module.GateEvalError) as invocation_exc:
        module.evaluate({"spectrum/idle": arms}, thresholds_path=THRESHOLDS)
    assert invocation_exc.value.gate_id == "gate_input_completeness"


def test_incomplete_arm_set_fails_closed_by_default() -> None:
    module = load_module()

    with pytest.raises(module.GateEvalError) as exc:
        module.evaluate({"spectrum/idle": pass_arms()}, thresholds_path=THRESHOLDS)

    assert exc.value.gate_id == "gate_input_completeness"


def test_inconsistent_cpu_evidence_fails_closed() -> None:
    module = load_module()
    arms = pass_arms()
    arms["fping"]["profile"] = profile(cpu_nsec_delta=1_000)
    arms["fping"]["profile"]["cpu_nsec_end"] = 1_500

    with pytest.raises(module.GateEvalError) as exc:
        module.evaluate({"spectrum/idle": arms}, thresholds_path=THRESHOLDS, require_complete=False)

    assert exc.value.gate_id == "gate_input_completeness"


def test_frozen_threshold_boundaries_flip_verdict() -> None:
    t = thresholds()
    arms = pass_arms()
    avg_limit = 3.0 * (1 + float(t["CYCLE_AVG_REGRESSION_PCT"]) / 100.0)
    p99_limit = 7.0 * (1 + float(t["CYCLE_P99_REGRESSION_PCT"]) / 100.0)
    arms["fping"]["profile"] = profile(avg_ms=avg_limit, p99_ms=p99_limit, cpu_nsec_delta=800_000_000)
    assert evaluate_pair(arms)["outcome"] == "pass"

    arms = pass_arms()
    arms["fping"]["profile"] = profile(avg_ms=avg_limit + 0.001, p99_ms=8.0, cpu_nsec_delta=800_000_000)
    assert gate(evaluate_pair(arms), "gate_avg_delta_pct")["verdict"] == "fail"

    arms = pass_arms()
    arms["fping"]["profile"] = profile(avg_ms=3.3, p99_ms=float(t["CYCLE_P99_ABS_CEILING_MS"]), cpu_nsec_delta=800_000_000)
    assert gate(evaluate_pair(arms), "gate_p99_abs_ceiling_ms")["verdict"] == "fail"

    arms = pass_arms()
    arms["icmplib"]["profile"] = profile(cpu_nsec_delta=0, window_wall_sec=10.0, n_cores=4)
    arms["fping"]["profile"] = profile(
        cpu_nsec_delta=int(float(t["CPU_DELTA_PCT_POINTS"]) / 100.0 * 10.0 * 1_000_000_000 * 4),
        window_wall_sec=10.0,
        n_cores=4,
    )
    assert gate(evaluate_pair(arms), "gate_cpu_delta_pts")["verdict"] == "fail"


def test_cli_writes_verdict_and_maps_input_error_to_exit_abort(tmp_path: Path) -> None:
    icmp_profile = tmp_path / "icmp.profile.json"
    fping_profile = tmp_path / "fping.profile.json"
    icmp_hygiene = tmp_path / "icmp.hygiene.ndjson"
    fping_hygiene = tmp_path / "fping.hygiene.ndjson"
    output = tmp_path / "243-BENCHMARK-VERDICT.json"

    icmp_profile.write_text(json.dumps(profile(avg_ms=10.0, p99_ms=7.0)))
    fping_profile.write_text(json.dumps(profile(avg_ms=10.5, p99_ms=8.0, cpu_nsec_delta=800_000_000)))
    icmp_hygiene.write_text("\n".join(json.dumps(row) for row in hygiene()) + "\n")
    fping_hygiene.write_text("\n".join(json.dumps(row) for row in hygiene()) + "\n")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--arm",
            f"spectrum:idle:icmplib:{icmp_profile}:{icmp_hygiene}",
            "--arm",
            f"spectrum:idle:fping:{fping_profile}:{fping_hygiene}",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert json.loads(output.read_text())["outcome"] == "input_error"


def test_pass_verdict_blob_sha_still_matches_real_provenance_helper() -> None:
    verdict = evaluate_pair(pass_arms())
    blob_sha = verdict["provenance"]["thresholds_blob_sha"]

    result = subprocess.run(
        [str(PROVENANCE), "assert-blob-unchanged", blob_sha],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase245-gate-eval.py"
THRESHOLDS = ROOT / "scripts" / "phase245-thresholds.json"


def load_module():
    spec = importlib.util.spec_from_file_location("phase245_gate_eval", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_summary(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "baseline_nrestarts": 10,
        "planned_restarts": 2,
        "total_nrestarts": 12,
        "backend_samples": {
            "icmplib": {
                "median_rtt_ms": 24.0,
                "loss_rate_pct": 0.5,
                "cycle_avg_ms": 2.85,
                "cycle_p99_ms": 6.9,
                "wanctl_backend_cycles": 9800,
                "total_accepted_cycles": 10000,
                "steering_decisions": {"enable": 100, "disable": 900},
            },
            "fping": {
                "median_rtt_ms": 24.5,
                "loss_rate_pct": 0.6,
                "cycle_avg_ms": 3.0,
                "cycle_p99_ms": 7.1,
                "wanctl_backend_cycles": 9800,
                "total_accepted_cycles": 10000,
                "steering_decisions": {"enable": 105, "disable": 895},
            },
        },
    }
    payload.update(overrides)
    return payload


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    module = load_module()
    return module.evaluate(payload, thresholds_path=THRESHOLDS)


def gate(verdict: dict[str, Any], name: str) -> dict[str, Any]:
    return verdict["gates"][name]


def test_keep_icmplib_is_passing_close_with_provenance() -> None:
    verdict = evaluate(sample_summary())

    assert verdict["outcome"] == "pass"
    assert verdict["recommendation"] == "keep-icmplib"
    assert re.fullmatch(r"[0-9a-f]{40}", verdict["provenance"]["thresholds_blob_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", verdict["provenance"]["prereg_commit_sha"])
    assert gate(verdict, "rtt_agreement")["verdict"] == "pass"


def test_clear_fping_win_is_switch_eligible_pass() -> None:
    summary = sample_summary()
    summary["backend_samples"]["fping"].update({"median_rtt_ms": 22.0, "loss_rate_pct": 0.2})

    verdict = evaluate(summary)

    assert verdict["outcome"] == "pass"
    assert verdict["recommendation"] == "switch-eligible"


def test_planned_restarts_pass_but_unexpected_restart_triggers_rollback() -> None:
    planned = evaluate(sample_summary(total_nrestarts=12, planned_restarts=2))
    unexpected = evaluate(sample_summary(total_nrestarts=13, planned_restarts=2))

    assert planned["outcome"] == "pass"
    assert gate(planned, "unexpected_restarts")["value"]["unexpected_restarts"] == 0
    assert unexpected["outcome"] == "rollback_trigger"
    assert gate(unexpected, "unexpected_restarts")["verdict"] == "fail"
    assert gate(unexpected, "unexpected_restarts")["value"]["unexpected_restarts"] == 1


def test_min_backend_cycle_fraction_below_floor_triggers_rollback() -> None:
    summary = sample_summary()
    summary["backend_samples"]["fping"]["wanctl_backend_cycles"] = 9000

    verdict = evaluate(summary)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "min_backend_cycle_fraction")["verdict"] == "fail"


def test_cycle_budget_regression_triggers_rollback() -> None:
    summary = sample_summary()
    summary["backend_samples"]["fping"].update({"cycle_avg_ms": 4.0, "cycle_p99_ms": 9.5})

    verdict = evaluate(summary)

    assert verdict["outcome"] == "rollback_trigger"
    assert gate(verdict, "cycle_budget_nonregression")["verdict"] == "fail"


def test_missing_restart_accounting_is_input_error(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    output_path = tmp_path / "verdict.json"
    payload = sample_summary()
    payload.pop("planned_restarts")
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            str(SCRIPT),
            "--summary",
            str(summary_path),
            "--thresholds",
            str(THRESHOLDS),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    verdict = json.loads(output_path.read_text())
    assert verdict["outcome"] == "input_error"
    assert verdict["gate_id"] == "gate_unexpected_restarts"


def test_verdict_carries_all_six_ab03_dimensions() -> None:
    verdict = evaluate(sample_summary())

    assert set(verdict["gates"]) == {
        "rtt_agreement",
        "cycle_budget_nonregression",
        "loss_detection_nonregression",
        "min_backend_cycle_fraction",
        "unexpected_restarts",
        "steering_decision_stability",
    }

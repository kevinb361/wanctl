"""Regression tests for the Phase 227 evidence-completeness gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "phase227-evidence-completeness.py"
THRESHOLDS = REPO_ROOT / "scripts" / "phase226-thresholds.json"


def metric(mean: float) -> dict[str, float]:
    return {"mean": mean, "min": mean, "max": mean, "spread": 0.0, "stddev": 0.0}


def flow_run(run: str) -> dict[str, Any]:
    return {"run": run, "valid": True, "validity_reason": "ok"}


def complete_summary(*, diffserv4: bool = True) -> dict[str, Any]:
    tins = {
        "Best Effort" if diffserv4 else "0": {
            "mean_packets_delta": 1000,
            "mean_delay_delta_ms": 1.0,
            "mean_backlog_bytes_delta": 128,
        }
    }
    if diffserv4:
        tins["Video"] = {
            "mean_packets_delta": 10,
            "mean_delay_delta_ms": 2.0,
            "mean_backlog_bytes_delta": 64,
        }
    return {
        "schema_version": 1,
        "run_count": 3,
        "rrul_p99_latency_under_load_ms_mean": 100.0,
        "baseline_window": {
            "restart_rate": 0.0,
            "transition_rate": 0.0,
            "floor_hit_cycles": 0,
            "soft_red_dwell_s": 0.0,
        },
        "interfaces": {"spec-router": tins},
        "ref_udp_unmarked": {
            "valid": True,
            "valid_run_count": 3,
            "run_count": 3,
            "jitter_ms": metric(1.2),
            "loss_pct": metric(0.1),
            "runs": [flow_run(f"run-{i:02d}") for i in range(1, 4)],
        },
        "ref_tcp_unmarked": {
            "valid": True,
            "valid_run_count": 3,
            "run_count": 3,
            "throughput_mbps": metric(5.0),
            "runs": [flow_run(f"run-{i:02d}") for i in range(1, 4)],
        },
        "marked_ef": {
            "valid": True,
            "valid_run_count": 3,
            "run_count": 3,
            "clean_mark": True,
            "jitter_ms": metric(1.1),
            "loss_pct": metric(0.2),
            "runs": [flow_run(f"run-{i:02d}") for i in range(1, 4)],
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def write_run_tree(root: Path, *, runs: int = 3) -> Path:
    qdisc = """qdisc cake 1: root bandwidth 920Mbit diffserv4 wash

                   Bulk  Best Effort        Video        Voice
  pkts               10          100           20            1
  av_delay          4us          2us         68us          2us
  backlog            0b           0b          64b           0b
"""
    for idx in range(1, runs + 1):
        run_dir = root / f"run-{idx:02d}"
        run_dir.mkdir(parents=True)
        for iface in ("spec-router", "spec-modem"):
            for phase in ("before", "during", "after"):
                (run_dir / f"tc-qdisc-{iface}.{phase}.txt").write_text(qdisc, encoding="utf-8")
    return root


def run_checker(tmp_path: Path, summary: dict[str, Any], *, baseline: dict[str, Any] | None = None, run_tree: Path | None = None) -> subprocess.CompletedProcess[str]:
    candidate_path = write_json(tmp_path / "candidate-summary.json", summary)
    cmd = [
        "python3",
        str(SCRIPT),
        "--candidate-summary",
        str(candidate_path),
        "--thresholds",
        str(THRESHOLDS),
    ]
    if baseline is not None:
        baseline_path = write_json(tmp_path / "baseline-summary.json", baseline)
        cmd.extend(["--baseline-summary", str(baseline_path)])
    if run_tree is not None:
        cmd.extend(["--run-tree", str(run_tree)])
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_complete_summary_and_three_run_tree_are_verdict_ready(tmp_path: Path) -> None:
    result = run_checker(
        tmp_path,
        complete_summary(diffserv4=True),
        baseline=complete_summary(diffserv4=False),
        run_tree=write_run_tree(tmp_path / "runs"),
    )
    assert result.returncode == 0, result.stderr
    assert "verdict-ready" in result.stdout


def test_missing_rrul_signal_fails_named_not_verdict_ready(tmp_path: Path) -> None:
    summary = complete_summary()
    summary.pop("rrul_p99_latency_under_load_ms_mean")
    result = run_checker(tmp_path, summary)
    assert result.returncode != 0
    assert "not verdict-ready" in result.stderr
    assert "rrul_p99_latency_under_load_ms_mean" in result.stderr


def test_run_tree_count_mismatch_fails_not_verdict_ready(tmp_path: Path) -> None:
    result = run_checker(tmp_path, complete_summary(), run_tree=write_run_tree(tmp_path / "runs", runs=2))
    assert result.returncode != 0
    assert "not verdict-ready" in result.stderr
    assert "run_count != 3" in result.stderr


def test_invalid_flow_fails_not_verdict_ready(tmp_path: Path) -> None:
    summary = complete_summary()
    summary["marked_ef"]["valid"] = False
    summary["marked_ef"]["runs"][0]["valid"] = False
    result = run_checker(tmp_path, summary)
    assert result.returncode != 0
    assert "not verdict-ready" in result.stderr
    assert "marked_ef" in result.stderr


def test_mode_dependent_tin_names_do_not_false_fail_shape_check(tmp_path: Path) -> None:
    result = run_checker(
        tmp_path,
        complete_summary(diffserv4=True),
        baseline=complete_summary(diffserv4=False),
    )
    assert result.returncode == 0, result.stderr


def test_stable_top_level_shape_missing_field_fails(tmp_path: Path) -> None:
    baseline = complete_summary(diffserv4=False)
    baseline.pop("marked_ef")
    result = run_checker(tmp_path, complete_summary(diffserv4=True), baseline=baseline)
    assert result.returncode != 0
    assert "not verdict-ready" in result.stderr
    assert "stable top-level field" in result.stderr

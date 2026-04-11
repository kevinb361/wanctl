"""Tests for scripts/analyze_storage_contention.py."""

import json
import subprocess
import sys
from pathlib import Path


def _write_capture(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def _run_helper(tmp_path: Path, autorate: dict, steering: dict, metrics_text: str) -> dict:
    autorate_path = _write_capture(tmp_path / "autorate.json", autorate)
    steering_path = _write_capture(tmp_path / "steering.json", steering)
    metrics_path = tmp_path / "metrics.txt"
    metrics_path.write_text(metrics_text)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_storage_contention.py",
            "--autorate-health",
            str(autorate_path),
            "--steering-health",
            str(steering_path),
            "--metrics-text",
            str(metrics_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_helper_classifies_keep_shared_db(tmp_path: Path) -> None:
    autorate = {
        "wans": [
            {
                "cycle_budget": {"utilization_pct": 42.0},
                "storage": {
                    "pending_writes": 0,
                    "queue": {"error_total": 0},
                    "writes": {"lock_failure_total": 0, "max_duration_ms": 4.0},
                    "checkpoint": {"busy": 0},
                },
            }
        ]
    }
    steering = {
        "cycle_budget": {"utilization_pct": 30.0},
        "storage": {
            "pending_writes": 0,
            "queue": {"error_total": 0},
            "writes": {"lock_failure_total": 0, "max_duration_ms": 2.0},
            "checkpoint": {"busy": 0},
        },
    }
    summary = _run_helper(
        tmp_path,
        autorate,
        steering,
        "wanctl_storage_write_success_total{process=\"autorate\"} 10\n"
        "wanctl_storage_write_success_total{process=\"steering\"} 10\n",
    )
    assert summary["classification"] == "keep_shared_db"


def test_helper_classifies_reduce_write_pressure(tmp_path: Path) -> None:
    autorate = {
        "wans": [
            {
                "cycle_budget": {"utilization_pct": 82.0},
                "storage": {
                    "pending_writes": 6,
                    "queue": {"error_total": 0},
                    "writes": {"lock_failure_total": 1, "max_duration_ms": 20.0},
                    "checkpoint": {"busy": 0},
                },
            }
        ]
    }
    steering = {
        "cycle_budget": {"utilization_pct": 55.0},
        "storage": {
            "pending_writes": 1,
            "queue": {"error_total": 0},
            "writes": {"lock_failure_total": 0, "max_duration_ms": 3.0},
            "checkpoint": {"busy": 0},
        },
    }
    summary = _run_helper(
        tmp_path,
        autorate,
        steering,
        "wanctl_storage_write_success_total{process=\"autorate\"} 10\n"
        "wanctl_storage_write_success_total{process=\"steering\"} 10\n",
    )
    assert summary["classification"] == "reduce_write_pressure"


def test_helper_classifies_plan_split_db_phase(tmp_path: Path) -> None:
    autorate = {
        "wans": [
            {
                "cycle_budget": {"utilization_pct": 97.0},
                "storage": {
                    "pending_writes": 25,
                    "queue": {"error_total": 2},
                    "writes": {"lock_failure_total": 3, "max_duration_ms": 60.0},
                    "checkpoint": {"busy": 1},
                },
            }
        ]
    }
    steering = {
        "cycle_budget": {"utilization_pct": 85.0},
        "storage": {
            "pending_writes": 10,
            "queue": {"error_total": 1},
            "writes": {"lock_failure_total": 1, "max_duration_ms": 18.0},
            "checkpoint": {"busy": 0},
        },
    }
    summary = _run_helper(
        tmp_path,
        autorate,
        steering,
        "wanctl_storage_write_success_total{process=\"autorate\"} 10\n"
        "wanctl_storage_write_success_total{process=\"steering\"} 10\n",
    )
    assert summary["classification"] == "plan_split_db_phase"

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts/phase215-reclaim-gate.sh"


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_health(
    path: Path,
    *,
    floor_start: int = 10,
    floor_end: int = 10,
    signal_outlier_rate: float = 0.05,
    measurement_state: str = "healthy",
    alert_events: int = 0,
    bloat_excursion_ms: float = 10.0,
) -> Path:
    samples = []
    for index in range(6):
        floor_value = floor_start if index == 0 else floor_end
        events = [{"wan_name": "spectrum", "alert_type": "flapping_ul"}] if index < alert_events else []
        samples.append(
            {
                "wans": [
                    {
                        "baseline_rtt_ms": 20.0,
                        "load_rtt_ms": 20.0 + bloat_excursion_ms,
                        "measurement_state": measurement_state,
                        "upload": {
                            "floor_hit_cycles_total": floor_value,
                            "signal_outlier_rate": signal_outlier_rate,
                        },
                    }
                ],
                "alert_fire_events": events,
            }
        )
    path.write_text("\n".join(json.dumps(sample) for sample in samples) + "\n", encoding="utf-8")
    return path


def _extract(latency_p95: float, latency_p99: float, upload_median: float) -> dict:
    return {
        "latency": {"p95_ms": latency_p95, "p99_ms": latency_p99},
        "upload_throughput": {"throughput_median_mbps": upload_median},
    }


def _run_gate(tmp_path: Path, candidate: dict, health: Path) -> tuple[int, dict, str]:
    baseline = _write_json(tmp_path / "baseline.json", _extract(50.0, 70.0, 11.0))
    candidate_path = _write_json(tmp_path / "candidate.json", candidate)
    out_dir = tmp_path / "out"
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--baseline-extract",
            str(baseline),
            "--candidate-extract",
            str(candidate_path),
            "--baseline-health",
            str(health),
            "--candidate-health",
            str(health),
            "--output-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    verdict = json.loads((out_dir / "verdict.json").read_text(encoding="utf-8"))
    return proc.returncode, verdict, proc.stderr + proc.stdout


def test_gate_passes_when_throughput_wins_and_rollback_gates_clear(tmp_path: Path) -> None:
    health = _write_health(tmp_path / "health.ndjson")
    rc, verdict, output = _run_gate(tmp_path, _extract(52.0, 72.0, 12.6), health)

    assert output == ""
    assert rc == 0
    assert verdict["verdict"] == "pass"
    assert verdict["exit_code"] == 0
    assert verdict["derived_p95_bound"] == pytest.approx(55.0)
    assert verdict["derived_p99_bound"] == pytest.approx(77.0)
    assert verdict["derived_win_bound"] == 12.5
    assert verdict["alert_fire_source"] == "candidate_health_ndjson_spectrum_events"


def test_gate_fails_when_candidate_p99_exceeds_derived_bound(tmp_path: Path) -> None:
    health = _write_health(tmp_path / "health.ndjson")
    rc, verdict, _output = _run_gate(tmp_path, _extract(52.0, 80.0, 12.6), health)

    assert rc == 1
    assert verdict["verdict"] == "fail"
    assert verdict["exit_code"] == 1
    assert "p99_latency_regression" in verdict["reason"]


def test_gate_fails_when_floor_hit_delta_is_positive(tmp_path: Path) -> None:
    health = _write_health(tmp_path / "health.ndjson", floor_start=10, floor_end=11)
    rc, verdict, _output = _run_gate(tmp_path, _extract(52.0, 72.0, 12.6), health)

    assert rc == 1
    assert verdict["verdict"] == "fail"
    assert verdict["exit_code"] == 1
    assert verdict["floor_hit_delta"] == 1
    assert "floor_hit_delta" in verdict["reason"]


def test_gate_voids_when_candidate_window_is_collapsed(tmp_path: Path) -> None:
    health = _write_health(tmp_path / "health.ndjson", signal_outlier_rate=0.30, measurement_state="collapsed")
    rc, verdict, _output = _run_gate(tmp_path, _extract(52.0, 72.0, 12.6), health)

    assert rc == 2
    assert verdict["verdict"] == "void"
    assert verdict["exit_code"] == 2
    assert verdict["signal_outlier_rate_p90"] == 0.30
    assert verdict["measurement_state_collapsed"] is True

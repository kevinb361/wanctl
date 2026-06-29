import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIER = REPO_ROOT / "scripts/phase213-classify.py"
FIXTURES = REPO_ROOT / "tests/fixtures/phase213"
BUCKETS = {
    "upload_ceiling_setpoint",
    "download_recovery_lag",
    "measurement_collapse",
    "steering_drift",
    "refractory_semantics",
    "external_isp",
}


def _run_classifier(run_dir: Path, tmp_path: Path) -> dict:
    if not CLASSIFIER.exists():
        pytest.skip("scripts/phase213-classify.py not built yet")
    out = tmp_path / "signal-sheet.json"
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER), "--run-dir", str(run_dir), "--output-json", str(out)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text())


def _minimal_ul_ceiling_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "RUN-ul-ceiling"
    test_dir = run_dir / "spectrum" / "tcp_upload"
    test_dir.mkdir(parents=True)
    rows = []
    for i in range(40):
        rows.append(
            {
                "wan": "spectrum",
                "upload_rate_mbps": 18.0 if i < 34 else 15.0,
                "upload_ceiling_mbps": 18.0,
                "upload_setpoint_mbps": 12.0,
                "download_state": "GREEN",
                "download_green_streak": 5,
                "download_green_required": 5,
                "cake_dl_peak_delay_us": 0,
                "signal_outlier_rate": 0.0,
                "arb_refractory_active": False,
                "cake_ul_backlog_suppressed_count": 0,
            }
        )
    (test_dir / "health-spectrum.ndjson").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (run_dir / "manifest.json").write_text(
        json.dumps({"phase": 213, "run_id": "ul-ceiling", "bind_map": {"spectrum": "10.10.110.226"}})
    )
    return run_dir


def test_six_buckets_present(tmp_path: Path) -> None:
    out = _run_classifier(_minimal_ul_ceiling_run(tmp_path), tmp_path)
    assert set(out["buckets"].keys()) == BUCKETS


def test_bucket_1_threshold_flags_on_ceiling_pegged(tmp_path: Path) -> None:
    out = _run_classifier(_minimal_ul_ceiling_run(tmp_path), tmp_path)
    assert out["buckets"]["upload_ceiling_setpoint"]["flagged"] is True


@pytest.mark.parametrize(
    ("fixture_dir", "bucket"),
    [
        ("RUN-bucket-2", "download_recovery_lag"),
        ("RUN-bucket-3", "measurement_collapse"),
        ("RUN-bucket-5", "refractory_semantics"),
        ("RUN-bucket-6", "external_isp"),
    ],
)
def test_per_bucket_fixture_flags(tmp_path: Path, fixture_dir: str, bucket: str) -> None:
    out = _run_classifier(FIXTURES / fixture_dir, tmp_path)
    assert out["buckets"][bucket]["flagged"] is True


def test_bucket_4_steering_drift_no_threshold_name_compare() -> None:
    if not CLASSIFIER.exists():
        pytest.skip("scripts/phase213-classify.py not built yet")
    source = CLASSIFIER.read_text()
    for name in ["green_rtt_ms", "yellow_rtt_ms", "red_rtt_ms", "red_samples_required", "green_samples_required"]:
        for match in re.finditer(name, source):
            line = source[: match.start()].count("\n") + 1
            text = source.splitlines()[line - 1].strip()
            assert text.startswith("#") or re.search(rf"[\"']{name}[\"']\s*:", text), f"bad {name} use on line {line}: {text}"
            assert not re.search(rf"(if|while).*({name}).*(<=|>=|==|!=|<|>)", text)


def test_ranked_next_phase_recommendation_present(tmp_path: Path) -> None:
    out = _run_classifier(_minimal_ul_ceiling_run(tmp_path), tmp_path)
    assert out["recommended_next_phase"]["primary"] in {214, 215, 216}
    assert len(out["recommended_next_phase"]["runners_up"]) >= 1


def test_bucket_1_ceiling_source_is_config_not_arithmetic() -> None:
    if not CLASSIFIER.exists():
        pytest.skip("scripts/phase213-classify.py not built yet")
    assert re.search(r"setpoint_mbps\s*\+\s*6", CLASSIFIER.read_text()) is None

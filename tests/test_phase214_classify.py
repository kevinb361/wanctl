import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIER = REPO_ROOT / "scripts/phase214-classify.py"
ALIGNER = REPO_ROOT / "scripts/phase214-align.py"
FIXTURES = REPO_ROOT / "tests/fixtures/phase214"


def _load_classifier():
    assert CLASSIFIER.exists(), "scripts/phase214-classify.py not built yet"
    spec = importlib.util.spec_from_file_location("phase214_classify_test", CLASSIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["phase214_classify_test"] = module
    spec.loader.exec_module(module)
    return module


def _event(ts: int, message: str, unit: str = "wanctl@spectrum.service") -> dict:
    return {"ts": ts, "message": message, "MESSAGE": message, "_SYSTEMD_UNIT": unit}


def _rows(success_counts=None, **overrides) -> list[dict]:
    counts = success_counts if success_counts is not None else [3, 3, 3]
    rows = []
    for i, count in enumerate(counts):
        row = {
            "t_unix": 1779920855 + i,
            "in_flent_window": True,
            "measurement_successful_count": count,
            "measurement_stale": False,
            "measurement_staleness_sec": 0.0,
            "load_rtt_ms": 22.0,
            "irtt_rtt_mean_ms": 20.0,
            "download_state": "GREEN",
            "cake_dl_peak_delay_us": 1000,
            "signal_outlier_rate": 0.0,
            "journal_events": [],
            "alerts_in_second": [],
        }
        for key, value in overrides.items():
            row[key] = value(i) if callable(value) else value
        rows.append(row)
    return rows


def test_classify_reflector_loss() -> None:
    module = _load_classifier()
    result = module.classify(_rows(success_counts=[3, 0, 3]))
    assert result["primary_driver"] == "reflector_loss"
    assert result["drivers"]["reflector_loss"]["fired"] is True


def test_classify_protocol_divergence() -> None:
    module = _load_classifier()
    rows = _rows(journal_events=lambda i: [_event(1779920855 + i, "ICMP deprioritized (ratio=2.21)")] if i == 1 else [])
    result = module.classify(rows)
    assert result["primary_driver"] == "icmp_udp_divergence"


def test_classify_stale_cached_rtt() -> None:
    module = _load_classifier()
    result = module.classify(_rows(success_counts=[3, 3, 3], measurement_stale=True))
    assert result["primary_driver"] == "stale_cached_rtt"


def test_classify_cake_queue_mismatch() -> None:
    module = _load_classifier()
    result = module.classify(_rows(cake_dl_peak_delay_us=60000, download_state="GREEN"))
    assert result["drivers"]["cake_queue_mismatch"]["fired"] is True


def test_classify_multi_driver_ranking() -> None:
    module = _load_classifier()
    rows = _rows(
        success_counts=[0, 0, 0, 0, 0, 0, 0, 0],
        journal_events=lambda i: [_event(1779920855 + i, "UDP deprioritized (ratio=0.58)")] if i in {0, 1} else [],
    )
    result = module.classify(rows)
    assert result["ranked"][0] == "reflector_loss"
    assert result["drivers"]["reflector_loss"]["fired"] is True
    assert result["drivers"]["icmp_udp_divergence"]["fired"] is True


def test_classify_external_path_fallback() -> None:
    module = _load_classifier()
    result = module.classify(_rows())
    assert result["primary_driver"] == "external_path"


def test_classify_empty_rows_returns_none() -> None:
    module = _load_classifier()
    result = module.classify([])
    assert result["primary_driver"] is None
    assert result["ranked"] == []


def test_verdict_pass() -> None:
    module = _load_classifier()
    drivers = {"reflector_loss": {"fired": False}, "icmp_udp_divergence": {"fired": False}}
    assert module.verdict_for_window({"p99_ms": 300}, drivers) == "pass"


def test_verdict_fail() -> None:
    module = _load_classifier()
    drivers = {"reflector_loss": {"fired": True, "score": 5}, "icmp_udp_divergence": {"fired": False}}
    assert module.verdict_for_window({"p99_ms": 1500}, drivers) == "fail"


def test_verdict_ambiguous_low_p99_with_driver() -> None:
    module = _load_classifier()
    drivers = {"reflector_loss": {"fired": True, "score": 1}}
    assert module.verdict_for_window({"p99_ms": 400}, drivers) == "ambiguous"


def test_verdict_ambiguous_high_p99_no_driver() -> None:
    module = _load_classifier()
    drivers = {"reflector_loss": {"fired": False}, "icmp_udp_divergence": {"fired": False}}
    assert module.verdict_for_window({"p99_ms": 1200}, drivers) == "ambiguous"


def test_verdict_ambiguous_zone_700ms() -> None:
    module = _load_classifier()
    drivers = {"reflector_loss": {"fired": False}, "icmp_udp_divergence": {"fired": False}}
    assert module.verdict_for_window({"p99_ms": 700}, drivers) == "ambiguous"


def test_verdict_pass_with_subordinate_drivers_firing() -> None:
    module = _load_classifier()
    drivers = {
        "reflector_loss": {"fired": False},
        "icmp_udp_divergence": {"fired": False},
        "stale_cached_rtt": {"fired": True},
        "cake_queue_mismatch": {"fired": True},
    }
    assert module.verdict_for_window({"p99_ms": 300}, drivers) == "pass"


def test_classify_reports_zero_cycle_counts() -> None:
    module = _load_classifier()
    result = module.classify(_rows(success_counts=[0, 0, 0, 2, 0, 0, 2]))
    driver = result["drivers"]["reflector_loss"]
    assert driver["consecutive_zero_cycles"] == 3
    assert driver["total_zero_cycles"] == 5


def _aligned_fixture(tmp_path: Path) -> Path:
    aligned = tmp_path / "aligned.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ALIGNER),
            "--flent-gz",
            str(FIXTURES / "sample-tcp_12down.flent.gz"),
            "--health-ndjson",
            str(FIXTURES / "sample-bad-p99-health.ndjson"),
            "--journal-ndjson",
            str(FIXTURES / "sample-journal-window.ndjson"),
            "--output-json",
            str(aligned),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return aligned


def _run_cli(tmp_path: Path, window_label: str = "off-peak") -> tuple[Path, Path]:
    aligned = _aligned_fixture(tmp_path)
    out_json = tmp_path / "signal-sheet.json"
    out_md = tmp_path / "signal-sheet.md"
    result = subprocess.run(
        [
            sys.executable,
            str(CLASSIFIER),
            "--aligned-window",
            str(aligned),
            "--flent-gz",
            str(FIXTURES / "sample-tcp_12down.flent.gz"),
            "--health-ndjson",
            str(FIXTURES / "sample-bad-p99-health.ndjson"),
            "--journal-ndjson",
            str(FIXTURES / "sample-journal-window.ndjson"),
            "--window-label",
            window_label,
            "--run-dir",
            "RUN-fixture",
            "--wan",
            "spectrum",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return out_json, out_md


def test_signal_sheet_md_has_signal_disposition_section(tmp_path: Path) -> None:
    _, out_md = _run_cli(tmp_path)
    text = out_md.read_text()
    assert "Signal Disposition" in text
    assert "observational" in text.lower()


def test_signal_sheet_md_does_not_recommend_mutation(tmp_path: Path) -> None:
    _, out_md = _run_cli(tmp_path)
    text = out_md.read_text().lower()
    forbidden = ["restart wanctl", "systemctl", "ceiling_mbps", "setpoint_mbps", "/etc/wanctl/", "mikrotik"]
    assert not any(token in text for token in forbidden)


def test_signal_sheet_includes_metadata(tmp_path: Path) -> None:
    out_json, _ = _run_cli(tmp_path)
    data = json.loads(out_json.read_text())
    for key in ["run_dir", "started_utc", "ended_utc", "window", "wan", "artifact_paths"]:
        assert data[key]
    assert data["run_dir"] == "RUN-fixture"
    assert data["window"] == "off-peak"
    assert data["wan"] == "spectrum"


def test_window_label_accepts_att_contrast(tmp_path: Path) -> None:
    out_json, _ = _run_cli(tmp_path, window_label="att-contrast")
    data = json.loads(out_json.read_text())
    assert data["window"] == "att-contrast"

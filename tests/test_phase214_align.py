import gzip
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIGNER = REPO_ROOT / "scripts/phase214-align.py"
EXTRACTOR = REPO_ROOT / "scripts/phase214-extract.py"
FIXTURES = REPO_ROOT / "tests/fixtures/phase214"
GOOD_FLENT = FIXTURES / "sample-tcp_12down.flent.gz"
MISSING_RAW_FLENT = FIXTURES / "sample-no-raw-values.flent.gz"
BAD_HEALTH = FIXTURES / "sample-bad-p99-health.ndjson"

ROW_SCHEMA_KEYS = {
    "t_unix",
    "in_flent_window",
    "ping_count",
    "ping_max_ms",
    "ping_mean_ms",
    "health_status",
    "download_state",
    "download_state_reason",
    "measurement_state",
    "measurement_successful_count",
    "measurement_stale",
    "measurement_staleness_sec",
    "signal_outlier_rate",
    "signal_confidence",
    "signal_warming_up",
    "baseline_rtt_ms",
    "load_rtt_ms",
    "load_rtt_delta_us",
    "cake_dl_peak_delay_us",
    "cake_dl_drop_rate",
    "cake_dl_backlog_suppressed_count",
    "arb_active_primary_signal",
    "arb_refractory_active",
    "arb_rtt_confidence",
    "irtt_rtt_mean_ms",
    "irtt_loss_up_pct",
    "irtt_loss_down_pct",
    "irtt_asymmetry_ratio",
    "journal_events",
    "alerts_in_second",
}


def _load_module(path: Path, name: str):
    assert path.exists(), f"{path} not built yet"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_aligner():
    return _load_module(ALIGNER, "phase214_align_test")


def _load_extractor():
    return _load_module(EXTRACTOR, "phase214_extract")


def _write_flent(path: Path, pings: list[dict[str, float]]) -> Path:
    payload = {
        "metadata": {"T0": "2026-05-27T22:27:35+00:00", "TOTAL_LENGTH": 10},
        "raw_values": {"Ping (ms) ICMP": pings},
        "results": {"TCP download sum": [1.0]},
        "version": "phase214-align-test",
        "x_values": [],
    }
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return path


def _write_health(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    out = tmp_path / "health.ndjson"
    out.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return out


def _health_row(t_unix: int, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "t_wall": datetime.fromtimestamp(t_unix, tz=UTC).isoformat(),
        "status": "healthy",
        "download_state": "GREEN",
        "download_state_reason": "green_stable",
        "measurement_state": "healthy",
        "measurement_successful_count": 3,
        "measurement_stale": False,
        "measurement_staleness_sec": 0.0,
        "signal_outlier_rate": 0.0,
        "signal_confidence": 0.95,
        "signal_warming_up": False,
        "baseline_rtt_ms": 18.0,
        "load_rtt_ms": 22.0,
        "load_rtt_delta_us": 4000,
        "cake_dl_peak_delay_us": 25000,
        "cake_dl_drop_rate": 0.0,
        "cake_dl_backlog_suppressed_count": 0,
        "arb_active_primary_signal": "queue",
        "arb_refractory_active": False,
        "arb_rtt_confidence": 0.0,
        "irtt_rtt_mean_ms": None,
        "irtt_loss_up_pct": None,
        "irtt_loss_down_pct": None,
        "irtt_asymmetry_ratio": None,
    }
    row.update(overrides)
    return row


def test_align_basic() -> None:
    aligner = _load_aligner()
    rows = aligner.align_window(
        GOOD_FLENT,
        BAD_HEALTH,
        journal_lines=[],
        alerts_window=[],
        flent_t0_unix=1779920855,
        flent_end_unix=1779920865,
        pre_buf_sec=2,
        post_buf_sec=2,
    )
    assert len(rows) == 15
    assert rows[0]["t_unix"] == 1779920853
    assert rows[-1]["t_unix"] == 1779920867
    assert all(row["in_flent_window"] is (1779920855 <= row["t_unix"] <= 1779920865) for row in rows)


def test_align_ping_bucketing(tmp_path: Path) -> None:
    aligner = _load_aligner()
    flent = _write_flent(
        tmp_path / "tiny.flent.gz",
        [
            {"t": 1779920855.2, "val": 10.0},
            {"t": 1779920855.7, "val": 30.0},
            {"t": 1779920857.1, "val": 50.0},
        ],
    )
    health = _write_health(tmp_path, [_health_row(t) for t in range(1779920854, 1779920859)])
    rows = {row["t_unix"]: row for row in aligner.align_window(flent, health, [], [], 1779920855, 1779920857, 1, 1)}
    assert rows[1779920855]["ping_count"] == 2
    assert rows[1779920855]["ping_max_ms"] == 30.0
    assert rows[1779920855]["ping_mean_ms"] == 20.0
    assert rows[1779920856]["ping_count"] == 0
    assert rows[1779920856]["ping_max_ms"] is None


def test_align_health_field_subset() -> None:
    aligner = _load_aligner()
    rows = aligner.align_window(GOOD_FLENT, BAD_HEALTH, [], [], 1779920855, 1779920856, 0, 0)
    assert rows
    assert set(rows[0]) == ROW_SCHEMA_KEYS


def test_align_journal_tolerance(tmp_path: Path) -> None:
    aligner = _load_aligner()
    flent = _write_flent(tmp_path / "tiny.flent.gz", [{"t": 1779920855.2, "val": 10.0}])
    health = _write_health(tmp_path, [_health_row(t) for t in range(1779920854, 1779920858)])
    event = {"ts": 1779920855.4, "unit": "wanctl@spectrum.service", "message": "Ping to 8.8.8.8 failed"}
    rows = {row["t_unix"]: row for row in aligner.align_window(flent, health, [event], [], 1779920855, 1779920856, 0, 0)}
    assert event in rows[1779920855]["journal_events"]
    assert event in rows[1779920856]["journal_events"]


def test_align_fails_closed_on_missing_flent(tmp_path: Path) -> None:
    out = tmp_path / "aligned.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ALIGNER),
            "--flent-gz",
            str(MISSING_RAW_FLENT),
            "--health-ndjson",
            str(BAD_HEALTH),
            "--output-json",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert "FlentExtractionError" in result.stderr


def test_align_fails_closed_on_missing_t_wall(tmp_path: Path) -> None:
    aligner = _load_aligner()
    flent = _write_flent(tmp_path / "tiny.flent.gz", [{"t": 1779920855.2, "val": 10.0}])
    health = _write_health(tmp_path, [{"download_state": "GREEN", "status": "healthy"}])
    with pytest.raises(aligner.AlignmentError):
        aligner.align_window(flent, health, [], [], 1779920855, 1779920856, 0, 0)


def test_align_flent_extraction_error_is_extractor_class() -> None:
    aligner = _load_aligner()
    extractor = _load_extractor()
    assert aligner.FlentExtractionError is extractor.FlentExtractionError


def test_align_status_to_health_status_mapping(tmp_path: Path) -> None:
    aligner = _load_aligner()
    flent = _write_flent(tmp_path / "tiny.flent.gz", [{"t": 1779920855.2, "val": 10.0}])
    health = _write_health(
        tmp_path,
        [
            _health_row(1779920855, status="degraded"),
            _health_row(1779920856, status="healthy", health_status="stray-value"),
        ],
    )
    rows = {row["t_unix"]: row for row in aligner.align_window(flent, health, [], [], 1779920855, 1779920856, 0, 0)}
    assert rows[1779920855]["health_status"] == "degraded"
    assert rows[1779920856]["health_status"] == "healthy"


def test_cli_derives_window_from_extractor(tmp_path: Path) -> None:
    out = tmp_path / "aligned.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ALIGNER),
            "--flent-gz",
            str(GOOD_FLENT),
            "--health-ndjson",
            str(BAD_HEALTH),
            "--output-json",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    rows = json.loads(out.read_text())
    assert any(row["in_flent_window"] for row in rows)

    bad_flags = subprocess.run(
        [
            sys.executable,
            str(ALIGNER),
            "--flent-gz",
            str(GOOD_FLENT),
            "--health-ndjson",
            str(BAD_HEALTH),
            "--output-json",
            str(out),
            "--flent-t0",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert bad_flags.returncode != 0
    assert "unrecognized arguments" in bad_flags.stderr

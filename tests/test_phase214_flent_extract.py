import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR = REPO_ROOT / "scripts/phase214-extract.py"
FIXTURES = REPO_ROOT / "tests/fixtures/phase214"


def _run_extractor(flent_gz: Path, tmp_path: Path) -> dict:
    assert EXTRACTOR.exists(), "scripts/phase214-extract.py not built yet"
    out = tmp_path / "extracted.json"
    result = subprocess.run(
        [sys.executable, str(EXTRACTOR), "--flent-gz", str(flent_gz), "--output-json", str(out)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def _percentile_index(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * percentile))]


def test_extract_known_good(tmp_path: Path) -> None:
    result = _run_extractor(FIXTURES / "sample-tcp_12down.flent.gz", tmp_path)
    latency = result["latency"]

    assert latency["p50_ms"] > 0
    assert latency["p95_ms"] >= latency["p50_ms"]
    assert latency["p99_ms"] >= latency["p95_ms"]
    assert latency["sample_count"] > 100
    assert "+00:00" in latency["window_start_utc"]
    assert "+00:00" in latency["window_end_utc"]
    assert latency["ping_command"]
    assert "ping" in latency["ping_command"]


def test_extract_missing_raw_fails_closed(tmp_path: Path) -> None:
    assert EXTRACTOR.exists(), "scripts/phase214-extract.py not built yet"
    out = tmp_path / "extracted.json"
    result = subprocess.run(
        [
            sys.executable,
            str(EXTRACTOR),
            "--flent-gz",
            str(FIXTURES / "sample-no-raw-values.flent.gz"),
            "--output-json",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "FlentExtractionError" in result.stderr or "missing or empty" in result.stderr


def test_extract_throughput(tmp_path: Path) -> None:
    result = _run_extractor(FIXTURES / "sample-tcp_12down.flent.gz", tmp_path)
    throughput = result["throughput"]

    assert throughput["throughput_median_mbps"] > 0
    assert throughput["throughput_p95_mbps"] >= throughput["throughput_median_mbps"]
    assert throughput["throughput_max_mbps"] >= throughput["throughput_p95_mbps"]
    assert throughput["series_key_used"] in ("TCP download sum", "TCP totals", "TCP download avg")


def test_extract_uses_raw_not_results_for_pings(tmp_path: Path) -> None:
    fixture = FIXTURES / "sample-tcp_12down.flent.gz"
    with gzip.open(fixture, "rt") as fh:
        data = json.load(fh)
    raw_values = [float(sample["val"]) for sample in data["raw_values"]["Ping (ms) ICMP"]]
    result_values = [float(value) for value in data["results"]["Ping (ms) ICMP"] if value is not None]

    raw_p99 = _percentile_index(raw_values, 0.99)
    results_p99 = _percentile_index(result_values, 0.99)
    extractor_p99 = _run_extractor(fixture, tmp_path)["latency"]["p99_ms"]

    assert extractor_p99 == pytest.approx(raw_p99, abs=0.01)
    if results_p99 != raw_p99:
        assert abs(extractor_p99 - results_p99) > 0.01


def test_extract_known_good_pinned_values(tmp_path: Path) -> None:
    result = _run_extractor(FIXTURES / "sample-tcp_12down.flent.gz", tmp_path)
    latency = result["latency"]

    assert latency["p50_ms"] == pytest.approx(31.2, abs=0.01)
    assert latency["p95_ms"] == pytest.approx(60.3, abs=0.01)
    assert latency["p99_ms"] == pytest.approx(124.0, abs=0.01)
    assert latency["sample_count"] == 647
    assert latency["min_ms"] == pytest.approx(12.7, abs=0.01)
    assert latency["max_ms"] == pytest.approx(954.0, abs=0.01)

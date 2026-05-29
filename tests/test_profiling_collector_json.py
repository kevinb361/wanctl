"""Tests for NDJSON cycle-timing profiling collector."""

import json
import subprocess
import sys

SCRIPT = "scripts/profiling_collector_json.py"


def write_ndjson(path, records):
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


def test_parses_cycle_timing_records_and_reconstructs_labels(tmp_path):
    ndjson = tmp_path / "spectrum_debug.ndjson"
    write_ndjson(
        ndjson,
        [
            json.dumps(
                {
                    "message": "Cycle timing",
                    "cycle_total_ms": 12.0,
                    "rtt_measurement_ms": 6.0,
                    "cake_stats_ms": 1.0,
                    "router_communication_ms": 2.0,
                    "logging_metrics_ms": 1.0,
                }
            ),
            "not json",
            json.dumps({"message": "Some other log", "cycle_total_ms": 999.0}),
            json.dumps(
                {
                    "message": "Cycle timing",
                    "cycle_total_ms": 14.0,
                    "rtt_measurement_ms": 7.0,
                    "cake_stats_ms": 1.5,
                    "router_communication_ms": 2.5,
                    "logging_metrics_ms": 1.2,
                }
            ),
            json.dumps(
                {
                    "message": "Cycle timing",
                    "cycle_total_ms": 16.0,
                    "rtt_measurement_ms": 8.0,
                    "cake_stats_ms": 2.0,
                    "router_communication_ms": 3.0,
                    "logging_metrics_ms": 1.5,
                    "router_write_download_ms": 0.3,
                }
            ),
        ],
    )

    result = subprocess.run(
        [sys.executable, SCRIPT, str(ndjson)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["autorate_cycle_total"] == {
        "count": 3,
        "min_ms": 12.0,
        "p50_ms": 14.0,
        "avg_ms": 14.0,
        "max_ms": 16.0,
        "p95_ms": 16.0,
        "p99_ms": 16.0,
    }
    assert output["autorate_rtt_measurement"]["count"] == 3
    assert "autorate_cake_stats" in output
    assert "autorate_router_communication" in output
    assert "autorate_logging_metrics" in output
    assert output["autorate_router_write_download"]["count"] == 1
    assert all(label.startswith("autorate_") for label in output)


def test_writes_output_file_and_fails_with_exit_2_when_no_cycle_timing(tmp_path):
    ndjson = tmp_path / "input.ndjson"
    output_path = tmp_path / "profile.json"
    write_ndjson(
        ndjson,
        [json.dumps({"message": "Cycle timing", "cycle_total_ms": 1.25})],
    )

    result = subprocess.run(
        [sys.executable, SCRIPT, "--input", str(ndjson), "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output_path.read_text(encoding="utf-8"))["autorate_cycle_total"]["count"] == 1
    assert result.stdout == ""

    empty = tmp_path / "empty.ndjson"
    empty.write_text("", encoding="utf-8")
    empty_result = subprocess.run(
        [sys.executable, SCRIPT, str(empty)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert empty_result.returncode == 2
    assert "ERROR: no Cycle timing records in input" in empty_result.stderr

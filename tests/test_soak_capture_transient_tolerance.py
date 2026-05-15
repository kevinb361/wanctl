"""HRDN-02 (Phase 207): soak-capture bounded transient tolerance tests."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = REPO_ROOT / "scripts" / "soak-capture.sh"
SIDECAR_HEADER = "t_wall\tfailure_mode\tlast_curl_exit\tlast_message"
EXPECTED_NDJSON_KEYS = {
    "t_wall",
    "t_monotonic",
    "version",
    "status",
    "floor_hit_cycles_total",
    "suppressions_per_min",
    "max_delay_delta_us",
    "red_streak",
    "zone_trace_tail",
    "headroom_state",
    "headroom_exhausted_streak",
    "anti_windup_triggers",
    "rtt_integral_ms_s",
    "docsis_mode_active",
    "red_decay_step_pct",
    "red_decay_delta_max_pct",
    "load_rtt_ms",
    "baseline_rtt_ms",
    "load_rtt_delta_us",
    "last_zone",
    "ul_hysteresis_window_start_epoch",
    "ul_suppressions_completed_window_count",
    "ul_suppressions_completed_window_by_cause",
    "ul_suppressions_lifetime_by_cause",
}


def _write_shim(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _setup_shims(tmp_path: Path, schedule: list[str]) -> Path:
    """Schedule entries: 'ok', 'curl_exit', 'http_503', 'empty', 'bad_json'."""
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    schedule_file = tmp_path / "schedule.txt"
    schedule_file.write_text("\n".join(schedule) + "\n", encoding="utf-8")
    counter_file = tmp_path / "counter"
    counter_file.write_text("0", encoding="utf-8")

    curl_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -u
        SCHEDULE="{schedule_file}"
        COUNTER="{counter_file}"
        out_file=""
        write_out=""
        while [ "$#" -gt 0 ]; do
          case "$1" in
            --output) out_file="$2"; shift 2 ;;
            --write-out) write_out="$2"; shift 2 ;;
            *) shift ;;
          esac
        done
        i=$(cat "$COUNTER")
        echo $((i + 1)) > "$COUNTER"
        action=$(sed -n "$((i + 1))p" "$SCHEDULE")
        [ -z "$action" ] && action="ok"
        case "$action" in
          curl_exit)
            exit 7
            ;;
          http_503)
            [ -n "$out_file" ] && printf '%s\n' "service unavailable" > "$out_file"
            [ "$write_out" = "%{{http_code}}" ] && printf '503'
            exit 0
            ;;
          empty)
            [ -n "$out_file" ] && : > "$out_file"
            [ "$write_out" = "%{{http_code}}" ] && printf '200'
            exit 0
            ;;
          bad_json)
            [ -n "$out_file" ] && printf '%s\n' "not json {{" > "$out_file"
            [ "$write_out" = "%{{http_code}}" ] && printf '200'
            exit 0
            ;;
          ok|*)
            if [ -n "$out_file" ]; then
              printf '%s\n' '{{"version":"1.43.0","status":"ok","wans":[{{"load_rtt_ms":10.0,"baseline_rtt_ms":9.5,"upload":{{"floor_hit_cycles_total":0,"hysteresis":{{"suppressions_per_min":0,"last_zone":"GREEN","window_start_epoch":1700000000,"suppressions_completed_window_count":0,"suppressions_completed_window_by_cause":{{}},"suppressions_lifetime_by_cause":{{}}}},"max_delay_delta_us":0,"red_streak":0,"zone_trace":["GREEN"],"headroom_state":"OK","headroom_exhausted_streak":0,"anti_windup_triggers":0,"rtt_integral_ms_s":0,"docsis_mode_active":false,"red_decay_step_pct":0,"red_decay_delta_max_pct":0}}}}]}}' > "$out_file"
            fi
            [ "$write_out" = "%{{http_code}}" ] && printf '200'
            exit 0
            ;;
        esac
        """
    )
    _write_shim(shim_dir / "curl", curl_body)
    return shim_dir


def _run_capture(
    tmp_path: Path,
    schedule: list[str],
    *,
    duration_sec: int = 5,
    min_samples_before_eval: int | None = None,
    threshold: str = "0.01",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    shim_dir = _setup_shims(tmp_path, schedule)
    capture_dir = tmp_path / "capture"
    env = {
        **os.environ,
        "PATH": f"{shim_dir}:{os.environ.get('PATH', '')}",
        "HEALTH_URL": "http://stub/health",
        "SOAK_DURATION_SEC": str(duration_sec),
        "CAPTURE_DIR": str(capture_dir),
        "SOAK_FAIL_RATE_THRESHOLD": threshold,
    }
    if min_samples_before_eval is not None:
        env["MIN_SAMPLES_BEFORE_EVAL"] = str(min_samples_before_eval)
    result = subprocess.run(
        ["bash", str(CAPTURE_SCRIPT), "test-ts"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, capture_dir


def _sidecar_rows(capture_dir: Path) -> list[str]:
    tsv_lines = (capture_dir / "soak-capture-errors.tsv").read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0] == SIDECAR_HEADER
    return [line for line in tsv_lines[1:] if line.strip()]


def test_single_transient_curl_failure_continues(tmp_path: Path) -> None:
    schedule = ["curl_exit"] + ["ok"] * 20
    result, capture_dir = _run_capture(
        tmp_path, schedule, duration_sec=5, threshold="0.5", min_samples_before_eval=100
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    ndjson = (capture_dir / "soak-capture.ndjson").read_text(encoding="utf-8")
    assert ndjson.count("\n") >= 1
    assert any("curl_exit_nonzero" in row for row in _sidecar_rows(capture_dir))


def test_single_http_non_200_continues(tmp_path: Path) -> None:
    schedule = ["http_503"] + ["ok"] * 20
    result, capture_dir = _run_capture(
        tmp_path, schedule, duration_sec=5, threshold="0.5", min_samples_before_eval=100
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert any("curl_http_nonzero" in row for row in _sidecar_rows(capture_dir))


def test_single_jq_parse_error_continues(tmp_path: Path) -> None:
    schedule = ["bad_json"] + ["ok"] * 20
    result, capture_dir = _run_capture(
        tmp_path, schedule, duration_sec=5, threshold="0.5", min_samples_before_eval=100
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert any("jq_parse_error" in row for row in _sidecar_rows(capture_dir))


def test_ndjson_schema_unchanged_after_recovery(tmp_path: Path) -> None:
    schedule = ["curl_exit"] + ["ok"] * 20
    result, capture_dir = _run_capture(
        tmp_path, schedule, duration_sec=5, threshold="0.5", min_samples_before_eval=100
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (capture_dir / "soak-capture-errors.tsv").read_text(encoding="utf-8").splitlines()[0] == SIDECAR_HEADER
    lines = (capture_dir / "soak-capture.ndjson").read_text(encoding="utf-8").splitlines()
    assert lines, "no NDJSON rows produced"
    for line in lines:
        assert set(json.loads(line)) == EXPECTED_NDJSON_KEYS


@pytest.mark.slow
def test_sustained_failure_above_threshold_aborts(tmp_path: Path) -> None:
    schedule = ["curl_exit"] * 200
    result, capture_dir = _run_capture(
        tmp_path, schedule, duration_sec=10, threshold="0.5", min_samples_before_eval=5
    )
    assert result.returncode != 0
    assert "ABORT" in result.stderr and "lifetime failure rate" in result.stderr
    assert len(_sidecar_rows(capture_dir)) >= 5


def test_invalid_threshold_aborts_before_loop(tmp_path: Path) -> None:
    result, capture_dir = _run_capture(tmp_path, ["ok"] * 5, duration_sec=3, threshold="notanumber")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "SOAK_FAIL_RATE_THRESHOLD must be numeric" in result.stderr
    assert not (capture_dir / "soak-capture.ndjson").exists()


def test_threshold_outside_range_aborts(tmp_path: Path) -> None:
    result, _ = _run_capture(tmp_path, ["ok"] * 5, duration_sec=3, threshold="1.5")
    assert result.returncode == 2
    assert "SOAK_FAIL_RATE_THRESHOLD must be numeric" in result.stderr


def test_invalid_min_samples_aborts_before_loop(tmp_path: Path) -> None:
    result, _ = _run_capture(
        tmp_path, ["ok"] * 5, duration_sec=3, threshold="0.5", min_samples_before_eval=0
    )
    assert result.returncode == 2
    assert "MIN_SAMPLES_BEFORE_EVAL must be a positive integer" in result.stderr

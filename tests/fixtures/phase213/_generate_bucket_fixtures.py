#!/usr/bin/env python3
"""Generate deterministic Phase 213 per-bucket classifier fixtures."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path("tests/fixtures/phase213")


def write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def base_row(i: int) -> dict:
    return {
        "t_wall": f"2026-05-27T21:{i:02d}:00Z",
        "t_monotonic_sec": i,
        "wan": "spectrum",
        "version": "1.45.0",
        "status": "healthy",
        "download_state": "GREEN",
        "download_state_reason": "green_stable",
        "download_rate_mbps": 920.0,
        "download_green_streak": 10,
        "download_green_required": 5,
        "upload_state": "GREEN",
        "upload_state_reason": "green_stable",
        "upload_rate_mbps": 18.0,
        "upload_setpoint_mbps": 12.0,
        "upload_docsis_mode_active": True,
        "upload_floor_hit_cycles_total": 0,
        "upload_headroom_state": "AVAILABLE",
        "upload_headroom_exhausted_streak": 0,
        "upload_red_streak": 0,
        "upload_anti_windup_triggers": 0,
        "cake_dl_peak_delay_us": 0,
        "cake_dl_drop_rate": 0.0,
        "cake_ul_peak_delay_us": 0,
        "cake_ul_drop_rate": 0.0,
        "cake_dl_backlog_suppressed_count": 0,
        "cake_ul_backlog_suppressed_count": 0,
        "cake_dl_refractory_remaining": 0,
        "cake_ul_refractory_remaining": 0,
        "cake_refractory_cycles": 40,
        "cake_burst_active": False,
        "cake_burst_trigger_count": 0,
        "arb_active_primary_signal": "queue",
        "arb_control_decision_reason": "green_stable",
        "arb_refractory_active": False,
        "arb_rtt_confidence": 0.0,
        "signal_confidence": 0.95,
        "signal_outlier_rate": 0.02,
        "signal_warming_up": False,
        "measurement_state": "healthy",
        "measurement_stale": False,
        "measurement_staleness_sec": 0.1,
        "measurement_successful_count": 3,
        "baseline_rtt_ms": 22.0,
        "load_rtt_ms": 23.0,
        "load_rtt_delta_us": 1000,
        "irtt_rtt_mean_ms": None,
        "irtt_loss_up_pct": None,
        "irtt_loss_down_pct": None,
        "irtt_asymmetry_ratio": None,
        "router_reachable": True,
        "alerting_fire_count": 0,
        "alerting_active_cooldowns_count": 0,
    }


def write_manifest(run_dir: Path, run_id: str, test: str) -> None:
    manifest = {
        "phase": 213,
        "run_id": run_id,
        "started_utc": "2026-05-27T21:00:00Z",
        "ended_utc": "2026-05-27T21:01:00Z",
        "host_dev_vm": "dev",
        "source_ip": "10.10.110.226",
        "netperf_host": "dallas",
        "flent_version": "2.1.1",
        "wanctl_version_dev_repo": "1.45.0",
        "wanctl_version_spectrum_runtime": "1.45.0",
        "wanctl_version_att_runtime": "1.45.0",
        "wanctl_version_steering_runtime": "1.39.0",
        "git_head_sha": "fixture",
        "tests_ordered": [{"wan": "spectrum", "test": test, "test_start_unix": 1717000000, "test_end_unix": 1717000060}],
        "redaction_posture": "fixture contains no secrets",
        "mutation_posture": "offline synthetic fixture only",
        "bind_map": {"spectrum": "10.10.110.226", "att": "10.10.110.233"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def write_empty_alerts(test_dir: Path) -> None:
    payload = {"wan": "spectrum", "db": "tests/fixtures/phase213/alerts-test.db", "present": True, "rows": [], "summary": []}
    for name in ["alerts-spectrum.json", "alerts-att.json", "alerts-steering.json"]:
        (test_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    (test_dir / "steering-pre.redacted.json").write_text('{"counters":{"good_count":1,"red_count":0,"cake_read_failures":0}}\n')
    (test_dir / "steering-post.redacted.json").write_text('{"counters":{"good_count":1,"red_count":0,"cake_read_failures":0}}\n')


def bucket2() -> None:
    run = ROOT / "RUN-bucket-2"
    test_dir = run / "spectrum" / "rrul"
    rows = []
    for i in range(40):
        row = base_row(i)
        if 5 <= i < 25:
            row["download_state"] = "RED"
            row["download_state_reason"] = "queue_delay"
            row["download_green_streak"] = 0
        elif i >= 25:
            row["download_green_streak"] = max(0, i - 35)
        if i in (8, 12, 16, 20):
            row["cake_dl_peak_delay_us"] = 60000
        rows.append(row)
    write_ndjson(test_dir / "health-spectrum.ndjson", rows)
    write_empty_alerts(test_dir)
    write_manifest(run, "bucket-2-fixture", "rrul")


def bucket3() -> None:
    run = ROOT / "RUN-bucket-3"
    test_dir = run / "spectrum" / "tcp_download"
    rows = []
    for i in range(60):
        row = base_row(i)
        if i < 8:
            row["signal_outlier_rate"] = 0.45
            row["signal_confidence"] = 0.35
        rows.append(row)
    write_ndjson(test_dir / "health-spectrum.ndjson", rows)
    (test_dir / "flent-summary.json").write_text(json.dumps({"throughput": {"p99": 900, "median": 150}}, indent=2) + "\n")
    write_empty_alerts(test_dir)
    write_manifest(run, "bucket-3-fixture", "tcp_download")


def bucket5() -> None:
    run = ROOT / "RUN-bucket-5"
    test_dir = run / "spectrum" / "tcp_upload"
    rows = []
    for i in range(60):
        row = base_row(i)
        row["cake_ul_backlog_suppressed_count"] = i * 3
        if i < 5:
            row["arb_refractory_active"] = True
            row["cake_ul_refractory_remaining"] = 20
        rows.append(row)
    write_ndjson(test_dir / "health-spectrum.ndjson", rows)
    write_empty_alerts(test_dir)
    write_manifest(run, "bucket-5-fixture", "tcp_upload")


def bucket6() -> None:
    run = ROOT / "RUN-bucket-6"
    test_dir = run / "spectrum" / "tcp_download"
    rows = [base_row(i) for i in range(60)]
    write_ndjson(test_dir / "health-spectrum.ndjson", rows)
    (test_dir / "flent-summary.json").write_text(json.dumps({"throughput": {"median": 400, "plan_mbps": 920}}, indent=2) + "\n")
    browse_dir = run / "spectrum" / "browse"
    browse_dir.mkdir(parents=True, exist_ok=True)
    with (browse_dir / "browse.curl.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts_utc", "site", "http_code", "time_starttransfer", "time_total", "size_download", "exit_code"])
        for i in range(30):
            writer.writerow([f"2026-05-27T21:{i:02d}:00Z", "https://example.com/", 200, 2.2 if i == 29 else 0.2, 2.4, 1000, 0])
    write_empty_alerts(test_dir)
    write_manifest(run, "bucket-6-fixture", "tcp_download")


def main() -> None:
    bucket2()
    bucket3()
    bucket5()
    bucket6()


if __name__ == "__main__":
    main()

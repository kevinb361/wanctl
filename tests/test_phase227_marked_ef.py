from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = ROOT / "scripts" / "phase226-baseline-capture.sh"
SUMMARY_PATH = ROOT / "scripts" / "phase226-baseline-summary.py"

spec = importlib.util.spec_from_file_location("phase226_baseline_summary", SUMMARY_PATH)
assert spec is not None and spec.loader is not None
summary = importlib.util.module_from_spec(spec)
sys.modules["phase226_baseline_summary"] = summary
spec.loader.exec_module(summary)


def _dry_run(*args: str) -> str:
    result = subprocess.run(
        [str(CAPTURE_SCRIPT), "--output-dir", "/tmp/phase227-dry", "--dry-run", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def _write_minimal_run(capture: Path, *, bad_udp: bool = False, missing_udp_sum: bool = False) -> None:
    run = capture / "run-01"
    run.mkdir(parents=True)
    tc = """
qdisc cake 8001: root refcnt 2 bandwidth 920Mbit diffserv4 wash
 Tin 0
  pkts 10
  drops 0
  backlog 0b
  av_delay 1ms
  pk_delay 2ms
"""
    for iface in ("spec-router", "spec-modem"):
        for suffix in ("before", "during", "after"):
            (run / f"tc-qdisc-{iface}.{suffix}.txt").write_text(tc, encoding="utf-8")
    (run / "health.window.ndjson").write_text(
        json.dumps({"sampled_unix": 1, "wans": [{"name": "spectrum", "pressure_state": "GREEN"}]}) + "\n",
        encoding="utf-8",
    )
    if bad_udp:
        udp_payload = {"error": "server busy"}
    elif missing_udp_sum:
        udp_payload = {"end": {}}
    else:
        udp_payload = {"end": {"sum": {"jitter_ms": 1.5, "lost_percent": 0.2}}}
    (run / "ref-udp-unmarked.01.txt").write_text(json.dumps(udp_payload), encoding="utf-8")
    (run / "ref-tcp-bulk-unmarked.01.txt").write_text(
        json.dumps(
            {
                "end": {
                    "sum_received": {"bits_per_second": 250_000_000},
                    "streams": [{"sender": {"retransmits": 2}, "receiver": {"retransmits": 0}}],
                }
            }
        ),
        encoding="utf-8",
    )
    (run / "ref-udp-marked-ef.01.txt").write_text(
        json.dumps({"end": {"sum": {"jitter_ms": 0.5, "lost_percent": 0.0}}}),
        encoding="utf-8",
    )
    (run / "ref-ef-marking.01.txt").write_text(
        "EF_MARK_METHOD=dscp\nEF_CLEAN_MARK=true\nEF_REF_PORT=5203\n",
        encoding="utf-8",
    )


def test_default_dry_run_has_no_marked_ef_tokens_or_new_port() -> None:
    output = _dry_run()

    assert "DRY_RUN: defaults" in output
    assert "marked_ef" not in output
    assert "ef_ref_port" not in output
    assert "5203" not in output


def test_marked_ef_dry_run_reports_distinct_default_port() -> None:
    output = _dry_run("--marked-ef")

    assert "marked_ef enabled" in output
    assert "ef_ref_port=5203" in output
    assert "ref=dallas:5201" in output
    assert "tcp_ref=dallas:5201" in output
    assert "reflector_prerequisite=dallas:5203" in output


def test_marked_ef_refuses_ref_port_collision() -> None:
    result = subprocess.run(
        [
            str(CAPTURE_SCRIPT),
            "--output-dir",
            "/tmp/phase227-dry",
            "--dry-run",
            "--marked-ef",
            "--ef-ref-port",
            "5201",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 2
    assert "must differ from --ref-port" in result.stderr


def test_matched_reference_invocations_still_target_ref_port() -> None:
    source = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert 'flent -l "$DURATION" -H "$REF_HOST" --local-bind "$LOCAL_BIND"' in source
    assert 'iperf3 -c "$REF_HOST" -p "$REF_PORT" -u -b "$REF_UDP_RATE"' in source
    assert 'iperf3 -c "$REF_HOST" -p "$TCP_REF_PORT" -t "$((DURATION > 5 ? DURATION - 5 : DURATION))" --json' in source
    assert 'iperf3 -c "$REF_HOST" -p "$EF_REF_PORT" -u -b "$REF_UDP_RATE"' in source


def test_tcp_ref_port_can_be_separated_for_parallel_iperf3_servers() -> None:
    output = _dry_run("--marked-ef", "--tcp-ref-port", "5202", "--ef-ref-port", "5203")

    assert "ref=dallas:5201" in output
    assert "tcp_ref=dallas:5202" in output
    assert "ef_ref_port=5203" in output


def test_ef_degrade_to_best_effort_record_path_exists() -> None:
    source = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "EF_MARK_METHOD=%s" in source
    assert "EF_CLEAN_MARK=%s" in source
    assert 'method="none"' in source
    assert 'clean="false"' in source


def test_summary_marks_top_level_error_or_missing_sum_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    _write_minimal_run(bad, bad_udp=True)
    built_bad = summary.build_summary(bad)

    assert built_bad["ref_udp_unmarked"]["valid"] is False
    assert built_bad["ref_udp_unmarked"]["runs"][0]["validity_reason"] == "top_level_error"
    assert built_bad["ref_udp_unmarked"]["jitter_ms"]["mean"] is None

    missing = tmp_path / "missing"
    _write_minimal_run(missing, missing_udp_sum=True)
    built_missing = summary.build_summary(missing)

    assert built_missing["ref_udp_unmarked"]["valid"] is False
    assert built_missing["ref_udp_unmarked"]["runs"][0]["validity_reason"] == "missing_end_sum"


def test_summary_emits_unmarked_and_marked_iperf_metrics(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    _write_minimal_run(capture)

    built = summary.build_summary(capture)

    assert built["ref_udp_unmarked"]["jitter_ms"]["mean"] == 1.5
    assert built["ref_udp_unmarked"]["loss_pct"]["mean"] == 0.2
    assert built["ref_tcp_unmarked"]["throughput_mbps"]["mean"] == 250.0
    assert built["ref_tcp_unmarked"]["retransmits"]["total"] == 2
    assert built["marked_ef"]["jitter_ms"]["mean"] == 0.5
    assert built["marked_ef"]["mark_method"] == "dscp"
    assert built["marked_ef"]["clean_mark"] is True
    assert built["marked_ef"]["ef_ref_port"] == 5203

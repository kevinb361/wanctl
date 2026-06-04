from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
MODULE_PATH = ROOT / "scripts" / "phase226-baseline-summary.py"

spec = importlib.util.spec_from_file_location("phase226_baseline_summary", MODULE_PATH)
assert spec is not None and spec.loader is not None
summary = importlib.util.module_from_spec(spec)
sys.modules["phase226_baseline_summary"] = summary
spec.loader.exec_module(summary)


def test_tc_qdisc_parser_reports_during_minus_before_delta_not_raw_cumulative() -> None:
    before = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.before.txt").read_text())
    during = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.during.txt").read_text())
    after = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.after.txt").read_text())

    rows = summary.compute_tin_deltas(before, during, after)
    tin = rows["0"]

    assert tin["packets_delta"] == 550
    assert tin["packets_delta"] != 650  # raw cumulative during packet value
    assert tin["drops_delta"] == 15
    assert tin["backlog_bytes_delta"] == 3000


def test_after_minus_before_cross_check_is_ge_during_minus_before() -> None:
    before = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.before.txt").read_text())
    during = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.during.txt").read_text())
    after = summary.parse_tc_qdisc((FIXTURES / "tc-qdisc.after.txt").read_text())

    rows = summary.compute_tin_deltas(before, during, after)

    assert rows["0"]["after_minus_before_ge_during"] is True
    assert rows["0"]["after_packets_delta"] == 700


def test_real_cake_tin_block_parses_bare_labels_without_synthetic_helpers() -> None:
    parsed = summary.parse_tc_qdisc(
        """
        qdisc cake 8001: root refcnt 2 bandwidth 920Mbit besteffort wash
         Tin 0
          thresh        920Mbit
          target            5ms
          interval        100ms
          pk_delay       3.78ms
          av_delay         54us
          sp_delay          5us
          backlog        1844b
          pkts       1551553525
          bytes    1774567043006
          drops          657899
          marks            6585
        """
    )

    tin = parsed["0"]

    assert tin.packets > 0
    assert tin.drops > 0
    assert tin.backlog_bytes == 1844
    assert tin.avg_delay_ms == pytest.approx(0.054)
    assert tin.peak_delay_ms == pytest.approx(3.78)


def test_retained_spec_router_evidence_parses_real_packet_and_delay_rows() -> None:
    path = (
        ROOT
        / ".planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/"
        / "baseline-20260604T113435Z/run-01/tc-qdisc-spec-router.during.txt"
    )
    if not path.exists():
        pytest.skip(f"retained evidence absent: {path}")

    tin = summary.parse_tc_qdisc(path.read_text())["0"]

    assert tin.packets > 0
    assert tin.avg_delay_ms > 0


def test_retained_spec_modem_evidence_parses_real_backlog_and_peak_rows() -> None:
    path = (
        ROOT
        / ".planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/"
        / "baseline-20260604T113435Z/run-01/tc-qdisc-spec-modem.during.txt"
    )
    if not path.exists():
        pytest.skip(f"retained evidence absent: {path}")

    tin = summary.parse_tc_qdisc(path.read_text())["0"]

    assert tin.backlog_bytes > 0
    assert tin.peak_delay_ms > 0


def test_health_window_derives_restart_transition_floor_and_soft_red_dwell() -> None:
    window = summary.parse_health_window(FIXTURES / "health.window.ndjson")

    assert window["restart_rate"] == 0.25
    assert window["transition_rate"] == 0.75
    assert window["floor_hit_cycles"] == 2
    assert window["soft_red_dwell_s"] == 2.0


def test_build_summary_emits_tin_queue_delay_spread_and_baseline_window(tmp_path: Path) -> None:
    capture = tmp_path / "baseline-TEST"
    run = capture / "run-01"
    run.mkdir(parents=True)
    for iface in ("spec-router", "spec-modem"):
        for suffix in ("before", "during", "after"):
            shutil.copyfile(
                FIXTURES / f"tc-qdisc.{suffix}.txt",
                run / f"tc-qdisc-{iface}.{suffix}.txt",
            )
    shutil.copyfile(FIXTURES / "health.window.ndjson", run / "health.window.ndjson")

    built = summary.build_summary(capture)

    assert built["interfaces"]["spec-router"]["0"]["tin_queue_delay_spread_ms"] == 0.0
    assert "baseline_window" in built
    assert built["baseline_window"]["restart_rate"] == 0.25

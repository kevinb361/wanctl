"""Phase 206 A/B replay harness invariants."""

from __future__ import annotations

# ruff: noqa: I001
import json
import subprocess
import sys
from pathlib import Path

from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot
from wanctl.queue_controller import QueueController

from tests.test_phase_193_replay import (
    EXPECTED_ATT_RATES,
    EXPECTED_SPECTRUM_RATES,
    EXPECTED_ZONES,
    TRACE,
    _fresh_controller,
    _replay,
    _snap,
)

from tests.fixtures.phase206_replay_corpus import GOLDEN_NDJSON, GoldenSample, load_golden

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "scripts" / "phase206-ab-replay.py"

EXPECTED_TOP_KEYS = {
    "schema_version",
    "phase",
    "fixture_provenance",
    "fixture_sha256",
    "meta",
    "pre",
    "post",
    "delta",
    "gates",
}

EXPECTED_SIDE_KEYS_CONTROLLER = {
    "config",
    "controller_mean_rate_mbps",
    "controller_rate_p99_mbps",
    "controller_rate_stddev_mbps",
    "rate_trace_mbps",
    "zone_distribution",
    "zone_sequence",
    "rate_apply_count",
}

EXPECTED_SIDE_KEYS_FLENT = {"rrul_p99_latency_ms", "throughput_mbps", "jitter_ms"}
VALID_ZONES = {"GREEN", "YELLOW", "SOFT_RED", "RED"}


def _snap_for(sample: GoldenSample, layout: str) -> CakeSignalSnapshot:
    tin_names = (
        ("Bulk", "BestEffort", "Video", "Voice")
        if layout == "diffserv4"
        else ("BestEffort",)
    )
    delay_delta_us = max(0, sample.cake_avg_delay_us - sample.cake_base_delay_us)
    tins = tuple(
        TinSnapshot(
            name=name,
            dropped_packets=0,
            drop_delta=0,
            backlog_bytes=0,
            peak_delay_us=sample.cake_avg_delay_us,
            ecn_marked_packets=0,
            avg_delay_us=sample.cake_avg_delay_us,
            base_delay_us=sample.cake_base_delay_us,
            delay_delta_us=delay_delta_us,
        )
        for name in tin_names
    )
    return CakeSignalSnapshot(
        drop_rate=0.0,
        total_drop_rate=0.0,
        backlog_bytes=0,
        peak_delay_us=sample.cake_avg_delay_us,
        tins=tins,
        cold_start=False,
        avg_delay_us=sample.cake_avg_delay_us,
        base_delay_us=sample.cake_base_delay_us,
        max_delay_delta_us=delay_delta_us,
    )


def _replay_samples(
    samples: list[GoldenSample],
    layout: str,
    controller: QueueController,
) -> dict:
    """Per-sample replay helper introduced in Phase 206 (revision 2026-05-14).

    Consumes the per-row cake_avg_delay_us / cake_base_delay_us trace
    synthesized by the golden fixture. Phase 193's _replay() reuses one
    CakeSignalSnapshot for every cycle (correct for 193's invariant tests
    but throws away the per-row CAKE trace this fixture provides).

    Candidate for promotion to wanctl.testing.replay in v1.45+.
    """
    zones: list[str] = []
    rates: list[int] = []
    for sample in samples:
        snap = _snap_for(sample, layout)
        zone, rate, _diag = controller.adjust_4state(
            baseline_rtt=sample.baseline_rtt_ms,
            load_rtt=sample.load_rtt_ms,
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
            cake_snapshot=snap,
        )
        zones.append(zone)
        rates.append(rate)
    return {"zones": zones, "rates": rates, "snapshots_consumed": len(samples)}


class TestPattern193Reuse:
    def test_imports_resolve(self) -> None:
        assert EXPECTED_ATT_RATES is not None
        assert EXPECTED_SPECTRUM_RATES is not None
        assert _snap is not None
        assert callable(_replay)
        assert callable(_fresh_controller)
        assert isinstance(TRACE, list)
        assert TRACE
        assert len(EXPECTED_ZONES) == len(TRACE)


class TestGoldenFixtureDeterminism:
    def test_two_loads_equal(self) -> None:
        assert load_golden() == load_golden()

    def test_fixture_nonempty(self) -> None:
        assert len(load_golden()) >= 24


class TestSchemaV1Stability:
    def test_harness_emits_schema_v1(self, tmp_path: Path) -> None:
        out = tmp_path / "summary.json"
        subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "--fixture",
                str(GOLDEN_NDJSON),
                "--out",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
        summary = json.loads(out.read_text(encoding="utf-8"))
        assert summary["schema_version"] == 1
        assert set(summary.keys()) == EXPECTED_TOP_KEYS
        assert EXPECTED_SIDE_KEYS_CONTROLLER <= set(summary["pre"].keys())
        assert EXPECTED_SIDE_KEYS_CONTROLLER <= set(summary["post"].keys())
        assert set(summary["pre"]["zone_distribution"].keys()) == VALID_ZONES
        assert summary["meta"]["metric_source"] == "controller_replay"


class TestReplayEquivalence:
    @staticmethod
    def _post_controller() -> QueueController:
        return _fresh_controller("spectrum")

    @staticmethod
    def _pre_controller() -> QueueController:
        c = _fresh_controller("spectrum")
        c.ceiling = 940_000_000
        c.current_rate = 940_000_000
        return c

    def test_replay_zones_and_rates_bounded(self) -> None:
        samples = load_golden()
        trace = [(s.baseline_rtt_ms, s.load_rtt_ms) for s in samples]
        snap_pre = _snap_for(samples[0], "diffserv4")
        snap_post = _snap_for(samples[0], "besteffort")
        zones_pre, rates_pre = _replay(self._pre_controller(), trace, snap_pre)
        zones_post, rates_post = _replay(self._post_controller(), trace, snap_post)
        assert set(zones_pre) <= VALID_ZONES
        assert set(zones_post) <= VALID_ZONES
        assert all(400_000_000 <= r <= 940_000_000 for r in rates_pre)
        assert all(400_000_000 <= r <= 920_000_000 for r in rates_post)


class TestReplaySamplesConsumesAllRows:
    def test_per_sample_helper_consumes_every_row(self) -> None:
        samples = load_golden()
        result = _replay_samples(samples, "besteffort", _fresh_controller("spectrum"))
        assert result["snapshots_consumed"] == len(samples)
        assert len(result["zones"]) == len(samples)
        assert len(result["rates"]) == len(samples)
        assert set(result["zones"]) <= VALID_ZONES


def test_flent_key_constant_is_deliberately_unused_until_task_3() -> None:
    assert EXPECTED_SIDE_KEYS_FLENT == {
        "rrul_p99_latency_ms",
        "throughput_mbps",
        "jitter_ms",
    }

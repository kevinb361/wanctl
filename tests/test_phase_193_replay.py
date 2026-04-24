"""Phase 193 SAFE-05 replay-equivalence harness.

Proves that adding avg/base/max-delay queue telemetry to CAKE snapshots does not
change download 4-state classifier transitions or rate-apply sequences.
"""

from __future__ import annotations

from collections import Counter

from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot
from wanctl.queue_controller import QueueController

TRACE = [
    (25.0, 30.0),
    (25.0, 35.0),
    (25.0, 40.0),
    (25.0, 40.0),
    (25.0, 45.0),
    (25.0, 45.0),
    (25.0, 70.0),
    (25.0, 70.0),
    (25.0, 75.0),
    (25.0, 75.0),
    (25.0, 105.0),
    (25.0, 105.0),
    (25.0, 106.0),
    (25.0, 106.0),
    (25.0, 75.0),
    (25.0, 75.0),
    (25.0, 45.0),
    (25.0, 45.0),
    (25.0, 40.0),
    (25.0, 35.0),
    (25.0, 30.0),
    (25.0, 30.0),
    (25.0, 30.0),
    (25.0, 30.0),
]

EXPECTED_ZONES = [
    "GREEN",
    "GREEN",
    "GREEN",
    "GREEN",
    "GREEN",
    "YELLOW",
    "YELLOW",
    "YELLOW",
    "SOFT_RED",
    "SOFT_RED",
    "SOFT_RED",
    "SOFT_RED",
    "RED",
    "RED",
    "SOFT_RED",
    "SOFT_RED",
    "GREEN",
    "YELLOW",
    "YELLOW",
    "GREEN",
    "GREEN",
    "GREEN",
    "GREEN",
    "GREEN",
]

EXPECTED_SPECTRUM_RATES = [
    920000000,
    920000000,
    920000000,
    920000000,
    920000000,
    883200000,
    847872000,
    813957120,
    813957120,
    813957120,
    813957120,
    813957120,
    691863552,
    588084019,
    588084019,
    588084019,
    800000000,
    768000000,
    737280000,
    800000000,
    800000000,
    800000000,
    800000000,
    810000000,
]

EXPECTED_ATT_RATES = [
    95000000,
    95000000,
    95000000,
    95000000,
    95000000,
    91200000,
    87552000,
    84049920,
    84049920,
    84049920,
    84049920,
    84049920,
    71442432,
    60726067,
    60726067,
    60726067,
    80000000,
    76800000,
    73728000,
    80000000,
    80000000,
    80000000,
    83000000,
    86000000,
]


def _fresh_controller(shape: str = "spectrum") -> QueueController:
    """Construct a fresh QueueController for one replay run."""
    if shape == "att":
        return QueueController(
            name="download",
            floor_green=80_000_000,
            floor_yellow=65_000_000,
            floor_soft_red=55_000_000,
            floor_red=45_000_000,
            ceiling=95_000_000,
            step_up=3_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=4,
            dwell_cycles=2,
            deadband_ms=0.0,
        )
    return QueueController(
        name="download",
        floor_green=800_000_000,
        floor_yellow=600_000_000,
        floor_soft_red=500_000_000,
        floor_red=400_000_000,
        ceiling=920_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=2,
        deadband_ms=0.0,
    )


def _snap(
    avg_delay_us: int,
    base_delay_us: int,
    max_delay_delta_us: int | None = None,
) -> CakeSignalSnapshot:
    if max_delay_delta_us is None:
        max_delay_delta_us = max(0, avg_delay_us - base_delay_us)
    return CakeSignalSnapshot(
        drop_rate=0.0,
        total_drop_rate=0.0,
        backlog_bytes=0,
        peak_delay_us=0,
        tins=(
            TinSnapshot(
                name="BestEffort",
                dropped_packets=0,
                drop_delta=0,
                backlog_bytes=0,
                peak_delay_us=0,
                ecn_marked_packets=0,
                avg_delay_us=avg_delay_us,
                base_delay_us=base_delay_us,
                delay_delta_us=max_delay_delta_us,
            ),
        ),
        cold_start=False,
        avg_delay_us=avg_delay_us,
        base_delay_us=base_delay_us,
        max_delay_delta_us=max_delay_delta_us,
    )


def _replay(
    controller: QueueController, trace: list[tuple[float, float]], snapshot: CakeSignalSnapshot
) -> tuple[list[str], list[int]]:
    zones: list[str] = []
    rates: list[int] = []
    for baseline_rtt, load_rtt in trace:
        zone, rate, _ = controller.adjust_4state(
            baseline_rtt=baseline_rtt,
            load_rtt=load_rtt,
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
            cake_snapshot=snapshot,
        )
        zones.append(zone)
        rates.append(rate)
    return zones, rates


class TestPhase193ReplayEquivalence:
    def test_fresh_controller_identity_guard(self) -> None:
        controller_a = _fresh_controller("spectrum")
        controller_b = _fresh_controller("spectrum")

        assert id(controller_a) != id(controller_b)
        controller_a.current_rate = 700_000_000
        assert controller_b.current_rate == 920_000_000

    def test_spectrum_shape_classifier_equivalence(self) -> None:
        controller_a = _fresh_controller("spectrum")
        controller_b = _fresh_controller("spectrum")

        zones_a, rates_a = _replay(controller_a, TRACE, _snap(0, 0, 0))
        zones_b, rates_b = _replay(controller_b, TRACE, _snap(10000, 200, 9800))

        assert zones_a == EXPECTED_ZONES
        assert rates_a == EXPECTED_SPECTRUM_RATES
        assert zones_b == EXPECTED_ZONES
        assert rates_b == EXPECTED_SPECTRUM_RATES

    def test_att_shape_classifier_equivalence(self) -> None:
        controller_a = _fresh_controller("att")
        controller_b = _fresh_controller("att")

        zones_a, rates_a = _replay(controller_a, TRACE, _snap(0, 0, 0))
        zones_b, rates_b = _replay(controller_b, TRACE, _snap(10000, 200, 9800))

        assert zones_a == EXPECTED_ZONES
        assert rates_a == EXPECTED_ATT_RATES
        assert zones_b == EXPECTED_ZONES
        assert rates_b == EXPECTED_ATT_RATES

    def test_trace_covers_all_4_zones(self) -> None:
        zones, _ = _replay(_fresh_controller("spectrum"), TRACE, _snap(0, 0, 0))

        assert Counter(zones) == {
            "GREEN": 11,
            "YELLOW": 5,
            "SOFT_RED": 6,
            "RED": 2,
        }

    def test_trace_covers_dwell_and_boundaries(self) -> None:
        deltas = [load - baseline for baseline, load in TRACE]

        assert deltas.count(15.0) == 3
        assert deltas.count(20.0) == 4
        assert deltas.count(45.0) == 2
        assert deltas.count(80.0) == 2
        assert TRACE[4:6] == [(25.0, 45.0), (25.0, 45.0)]
        assert TRACE[6:8] == [(25.0, 70.0), (25.0, 70.0)]
        assert TRACE[10:12] == [(25.0, 105.0), (25.0, 105.0)]

    def test_rate_sequence_is_deterministic_and_equal(self) -> None:
        controller_a = _fresh_controller("spectrum")
        controller_b = _fresh_controller("spectrum")

        _, rates_a = _replay(controller_a, TRACE, _snap(0, 0, 0))
        _, rates_b = _replay(controller_b, TRACE, _snap(50000, 100, 49900))

        assert rates_a == EXPECTED_SPECTRUM_RATES
        assert rates_b == EXPECTED_SPECTRUM_RATES

    def test_avg_delay_delta_does_not_feed_classifier(self) -> None:
        baseline_zones, baseline_rates = _replay(
            _fresh_controller("spectrum"), TRACE, _snap(0, 0, 0)
        )

        for max_delay_delta_us in [0, 5000, 50000, 100000]:
            zones, rates = _replay(
                _fresh_controller("spectrum"),
                TRACE,
                _snap(max_delay_delta_us + 100, 100, max_delay_delta_us),
            )
            assert zones == baseline_zones
            assert rates == baseline_rates

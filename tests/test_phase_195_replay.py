"""Phase 195 ARB-02 + ARB-03 + SAFE-05 deterministic replay harness.

Supersedes tests/test_phase_194_replay.py::test_phase_194_never_emits_rtt_veto.
Covers:
  * rtt_confidence derivation (Plan 195-01).
  * ARB-02 RTT-veto gate parametrized (Plan 195-02 Task 1).
  * ARB-03 6-cycle healer-bypass streak gate (Plan 195-02 Task 2).
  * 2026-04-23 Spectrum event replay -- single-path ICMP/UDP flip MUST NOT
    trip healer bypass and MUST NOT clamp DL rate on phantom RTT bloat.
  * UL byte-parity regex guard + SAFE-05 textual no-touch guards.
"""

from __future__ import annotations

# ruff: noqa: I001
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor, CakeSignalSnapshot
from wanctl.queue_controller import QueueController
from wanctl.wan_controller import (
    ARBITRATION_PRIMARY_ENCODING,
    ARBITRATION_REASON_GREEN_STABLE,
    ARBITRATION_REASON_HEALER_BYPASS,
    ARBITRATION_REASON_QUEUE_DISTRESS,
    ARBITRATION_REASON_RTT_PRIMARY_NORMAL,
    ARBITRATION_REASON_RTT_VETO,
    WANController,
)

from tests.test_phase_193_replay import (
    EXPECTED_ATT_RATES,
    EXPECTED_SPECTRUM_RATES,
    EXPECTED_ZONES,
    TRACE,
    _fresh_controller,
    _replay,
    _snap,
)


SPECTRUM_2026_04_23_TRACE = [
    # Cycles 1-5: steady state, healthy.
    *[(500, 5.0, 1.0) for _ in range(5)],
    # Cycles 6-15: single-path ICMP flip. ICMP-derived RTT spikes to 40ms,
    # kernel queue stays low, irtt_correlation flips outside the normal band.
    *[(500, 40.0, 0.54) for _ in range(10)],
    # Cycles 16-25: recovery.
    *[(500, 5.0, 1.0) for _ in range(10)],
]


@pytest.fixture
def integrated_controller(mock_autorate_config):
    """Real WANController with MagicMock dependencies for end-to-end tests."""
    router = MagicMock()
    router.set_limits.return_value = True
    router.needs_rate_limiting = True
    router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
    rtt_measurement = MagicMock()
    logger = MagicMock()
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=router,
            rtt_measurement=rtt_measurement,
            logger=logger,
        )
    return ctrl


def _queue_snapshot(
    max_delta_us: int,
    *,
    avg_delay_us: int | None = None,
    base_delay_us: int = 0,
) -> CakeSignalSnapshot:
    if avg_delay_us is None:
        avg_delay_us = max_delta_us + base_delay_us
    return CakeSignalSnapshot(
        drop_rate=0.0,
        total_drop_rate=0.0,
        backlog_bytes=0,
        peak_delay_us=max_delta_us,
        tins=(),
        cold_start=False,
        avg_delay_us=avg_delay_us,
        base_delay_us=base_delay_us,
        max_delay_delta_us=max_delta_us,
    )


def _prepare_queue_primary_controller(ctrl: WANController) -> None:
    ctrl._cake_signal_supported = True
    ctrl.download = _fresh_controller("spectrum")
    ctrl._dl_cake_signal = CakeSignalProcessor(
        config=CakeSignalConfig(enabled=True, metrics_enabled=True)
    )
    ctrl._ul_cake_signal = CakeSignalProcessor(
        config=CakeSignalConfig(enabled=True, metrics_enabled=True)
    )
    ctrl._metrics_writer = MagicMock()
    ctrl.baseline_rtt = 25.0
    ctrl.load_rtt = 25.0
    ctrl.green_threshold = 15.0
    ctrl.soft_red_threshold = 45.0
    ctrl.hard_red_threshold = 80.0
    ctrl.target_delta = 15.0
    ctrl.warn_delta = 45.0
    ctrl._ul_cake_snapshot = None
    ctrl._dl_refractory_remaining = 0
    ctrl._ul_refractory_remaining = 0
    ctrl._dl_burst_pending = False
    ctrl._irtt_correlation = None
    ctrl._prev_queue_delta_ms = None
    ctrl._prev_rtt_delta_ms = None
    ctrl._last_rtt_confidence = None
    ctrl._last_queue_direction = "unknown"
    ctrl._last_rtt_direction = "unknown"
    ctrl._healer_aligned_streak = 0
    ctrl._fusion_bypass_active = False
    ctrl._fusion_bypass_reason = None
    ctrl._fusion_bypass_count = 0
    ctrl.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))


def _metrics_by_name(batch):
    return {
        (metric_name, tuple(sorted((labels or {}).items()))): value
        for _, _, metric_name, value, labels, _ in batch
    }


def _run_one_cycle(
    ctrl: WANController,
    *,
    queue_delta_us: int,
    raw_rtt_delta_ms: float,
    irtt_correlation: float | None,
) -> tuple[str, int, str | None, str, int, str | None, float]:
    ctrl._dl_refractory_remaining = 0
    ctrl._ul_refractory_remaining = 0
    ctrl._dl_burst_pending = False
    ctrl._irtt_correlation = irtt_correlation
    ctrl._dl_cake_snapshot = _queue_snapshot(queue_delta_us)
    ctrl._ul_cake_snapshot = None
    ctrl.load_rtt = ctrl.baseline_rtt + raw_rtt_delta_ms
    return ctrl._run_congestion_assessment()


def _seed_worsening_history(
    ctrl: WANController,
    *,
    queue_delta_ms: float = 16.0,
    rtt_delta_ms: float = 20.0,
) -> None:
    ctrl._prev_queue_delta_ms = queue_delta_ms - 1.0
    ctrl._prev_rtt_delta_ms = rtt_delta_ms - 1.0


def _prime_aligned_streak(ctrl: WANController, *, cycles: int = 5) -> None:
    _seed_worsening_history(ctrl)
    for offset in range(cycles):
        _run_one_cycle(
            ctrl,
            queue_delta_us=int((16.0 + offset) * 1000),
            raw_rtt_delta_ms=20.0 + offset,
            irtt_correlation=1.0,
        )


class TestPhase195ConfidenceDerivation:
    def test_phase193_trace_derives_confidence_on_valid_cycles(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        observed_confidence: list[float | None] = []

        for baseline_rtt, load_rtt in TRACE:
            integrated_controller.baseline_rtt = baseline_rtt
            raw_delta_ms = load_rtt - baseline_rtt
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=int(raw_delta_ms * 1000),
                raw_rtt_delta_ms=raw_delta_ms,
                irtt_correlation=1.0,
            )
            if (
                integrated_controller._dl_cake_snapshot is not None
                and not integrated_controller._dl_cake_snapshot.cold_start
                and integrated_controller._prev_queue_delta_ms is not None
            ):
                observed_confidence.append(integrated_controller._last_rtt_confidence)

        assert observed_confidence
        assert all(confidence is not None for confidence in observed_confidence)

    def test_trace_includes_high_and_zero_confidence_cycles(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=500,
            raw_rtt_delta_ms=5.0,
            irtt_correlation=1.0,
        )
        _run_one_cycle(
            integrated_controller,
            queue_delta_us=5_000,
            raw_rtt_delta_ms=20.0,
            irtt_correlation=1.0,
        )
        high_confidence = integrated_controller._last_rtt_confidence

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=10_000,
            raw_rtt_delta_ms=35.0,
            irtt_correlation=0.3,
        )
        zero_confidence = integrated_controller._last_rtt_confidence

        assert high_confidence == pytest.approx(1.0)
        assert zero_confidence == pytest.approx(0.0)

    def test_metrics_emit_exactly_one_confidence_row_when_available(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._dl_cake_snapshot = _queue_snapshot(20_000)
        integrated_controller._last_rtt_confidence = 0.85

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            integrated_controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = integrated_controller._metrics_writer.write_metrics_batch.call_args.args[0]
        confidence_rows = [
            (row[2], row[3], row[4])
            for row in batch
            if row[2] == "wanctl_rtt_confidence"
        ]
        metrics = _metrics_by_name(batch)
        labels_key = (("direction", "download"),)

        assert confidence_rows == [
            ("wanctl_rtt_confidence", 0.85, integrated_controller._download_labels)
        ]
        assert metrics[("wanctl_rtt_confidence", labels_key)] == pytest.approx(0.85)

    def test_metrics_skip_confidence_row_when_unavailable(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._dl_cake_snapshot = _queue_snapshot(20_000)
        integrated_controller._last_rtt_confidence = None

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            integrated_controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = integrated_controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = _metrics_by_name(batch)
        labels_key = (("direction", "download"),)

        assert ("wanctl_rtt_confidence", labels_key) not in metrics


class TestPhase195RttVetoGate:
    @pytest.mark.parametrize(
        (
            "snapshot",
            "raw_rtt_delta_ms",
            "confidence",
            "queue_direction",
            "rtt_direction",
            "expected_primary",
            "expected_reason",
        ),
        [
            (
                _queue_snapshot(500),
                30.0,
                0.3,
                "worsening",
                "worsening",
                "queue",
                ARBITRATION_REASON_GREEN_STABLE,
            ),
            (
                _queue_snapshot(500),
                30.0,
                0.6,
                "worsening",
                "worsening",
                "rtt",
                ARBITRATION_REASON_RTT_VETO,
            ),
            (
                _queue_snapshot(20_000),
                30.0,
                1.0,
                "worsening",
                "worsening",
                "queue",
                ARBITRATION_REASON_QUEUE_DISTRESS,
            ),
            (
                _queue_snapshot(500),
                5.0,
                1.0,
                "worsening",
                "worsening",
                "queue",
                ARBITRATION_REASON_GREEN_STABLE,
            ),
            (
                _queue_snapshot(500),
                30.0,
                1.0,
                "worsening",
                "improving",
                "queue",
                ARBITRATION_REASON_GREEN_STABLE,
            ),
            (
                _queue_snapshot(500),
                30.0,
                1.0,
                "worsening",
                "unknown",
                "queue",
                ARBITRATION_REASON_GREEN_STABLE,
            ),
            (
                None,
                30.0,
                1.0,
                "worsening",
                "worsening",
                "rtt",
                ARBITRATION_REASON_GREEN_STABLE,
            ),
        ],
    )
    def test_arb02_reason_vocabulary(
        self,
        integrated_controller,
        snapshot: CakeSignalSnapshot | None,
        raw_rtt_delta_ms: float,
        confidence: float,
        queue_direction: str,
        rtt_direction: str,
        expected_primary: str,
        expected_reason: str,
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._cake_signal_supported = snapshot is not None
        integrated_controller.load_rtt = (
            integrated_controller.baseline_rtt + raw_rtt_delta_ms
        )
        integrated_controller._last_rtt_confidence = confidence
        integrated_controller._last_queue_direction = queue_direction
        integrated_controller._last_rtt_direction = rtt_direction

        primary, load_for_classifier, reason = (
            integrated_controller._select_dl_primary_scalar_ms(snapshot)
        )

        assert (primary, reason) == (expected_primary, expected_reason)
        if expected_primary == "queue":
            assert load_for_classifier != pytest.approx(integrated_controller.load_rtt)
        else:
            assert load_for_classifier == pytest.approx(integrated_controller.load_rtt)

    def test_reason_encoding_keeps_phase195_primary_vocabulary(self) -> None:
        assert ARBITRATION_PRIMARY_ENCODING == {"none": 0, "queue": 1, "rtt": 2}
        assert ARBITRATION_REASON_RTT_PRIMARY_NORMAL == "rtt_primary_operating_normally"


class TestPhase195HealerBypassStreak:
    def test_single_path_icmp_flip_never_trips_healer_bypass(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._prev_queue_delta_ms = 0.5
        integrated_controller._prev_rtt_delta_ms = 39.0

        for _ in range(10):
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=500,
                raw_rtt_delta_ms=40.0,
                irtt_correlation=0.3,
            )
            assert integrated_controller._fusion_bypass_active is False
            assert integrated_controller._healer_aligned_streak == 0
            assert (
                integrated_controller._last_arbitration_reason
                != ARBITRATION_REASON_HEALER_BYPASS
            )

    def test_aligned_distress_trips_at_exactly_cycle_six(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        _seed_worsening_history(integrated_controller)

        for offset in range(5):
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=int((16.0 + offset) * 1000),
                raw_rtt_delta_ms=20.0 + offset,
                irtt_correlation=1.0,
            )
            assert integrated_controller._fusion_bypass_active is False
            assert integrated_controller._healer_aligned_streak == offset + 1

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=21_000,
            raw_rtt_delta_ms=25.0,
            irtt_correlation=1.0,
        )

        assert integrated_controller._fusion_bypass_active is True
        assert integrated_controller._fusion_bypass_reason == "queue_rtt_aligned_distress"
        assert integrated_controller._fusion_bypass_count == 1
        assert (
            integrated_controller._last_arbitration_reason
            == ARBITRATION_REASON_HEALER_BYPASS
        )

        for offset in range(2):
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=int((22.0 + offset) * 1000),
                raw_rtt_delta_ms=26.0 + offset,
                irtt_correlation=1.0,
            )
            assert integrated_controller._fusion_bypass_active is True
            assert integrated_controller._fusion_bypass_count == 1

    def test_streak_resets_on_direction_flip_at_cycle_six(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        _prime_aligned_streak(integrated_controller, cycles=5)

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=21_000,
            raw_rtt_delta_ms=10.0,
            irtt_correlation=1.0,
        )

        assert integrated_controller._healer_aligned_streak == 0
        assert integrated_controller._fusion_bypass_active is False

    def test_held_direction_counts_as_alignment(self, integrated_controller) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._prev_queue_delta_ms = 16.0
        integrated_controller._prev_rtt_delta_ms = 20.0

        for _ in range(6):
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=16_000,
                raw_rtt_delta_ms=20.0,
                irtt_correlation=1.0,
            )

        assert integrated_controller._healer_aligned_streak == 6
        assert integrated_controller._fusion_bypass_active is True
        assert integrated_controller._fusion_bypass_reason == "queue_rtt_aligned_distress"

    def test_bypass_releases_when_condition_ends(self, integrated_controller) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        _prime_aligned_streak(integrated_controller, cycles=6)
        assert integrated_controller._fusion_bypass_active is True
        assert integrated_controller._fusion_bypass_count == 1

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=500,
            raw_rtt_delta_ms=26.0,
            irtt_correlation=1.0,
        )

        assert integrated_controller._fusion_bypass_active is False
        assert integrated_controller._fusion_bypass_reason is None
        assert integrated_controller._fusion_bypass_count == 1

    def test_confidence_drop_mid_streak_resets(self, integrated_controller) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        _prime_aligned_streak(integrated_controller, cycles=5)

        _run_one_cycle(
            integrated_controller,
            queue_delta_us=21_000,
            raw_rtt_delta_ms=25.0,
            irtt_correlation=None,
        )

        assert integrated_controller._last_rtt_confidence == pytest.approx(0.5)
        assert integrated_controller._healer_aligned_streak == 0
        assert integrated_controller._fusion_bypass_active is False


class TestPhase195Spectrum20260423Replay:
    def test_single_path_flip_never_trips_healer_or_veto(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        reasons: list[str] = []
        bypass_active: list[bool] = []
        bypass_reasons: list[str | None] = []
        confidences: list[float | None] = []

        for queue_delta_us, raw_rtt_delta_ms, correlation in SPECTRUM_2026_04_23_TRACE:
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=queue_delta_us,
                raw_rtt_delta_ms=raw_rtt_delta_ms,
                irtt_correlation=correlation,
            )
            reasons.append(integrated_controller._last_arbitration_reason)
            bypass_active.append(integrated_controller._fusion_bypass_active)
            bypass_reasons.append(integrated_controller._fusion_bypass_reason)
            confidences.append(integrated_controller._last_rtt_confidence)

        assert len(SPECTRUM_2026_04_23_TRACE) == 25
        assert confidences[5:15] == [0.0] * 10
        assert ARBITRATION_REASON_HEALER_BYPASS not in reasons
        assert ARBITRATION_REASON_RTT_VETO not in reasons
        assert bypass_active == [False] * 25
        assert "absolute_disagreement" not in bypass_reasons
        assert "queue_rtt_aligned_distress" not in bypass_reasons

    def test_dl_rate_does_not_clamp_on_phantom_bloat(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        captured_loads: list[float] = []
        rates: list[int] = []
        real_adjust = integrated_controller.download.adjust_4state

        def spy_adjust(
            baseline_rtt: float,
            load_for_classifier: float,
            green_threshold: float,
            soft_red_threshold: float,
            hard_red_threshold: float,
            *,
            cake_snapshot: CakeSignalSnapshot | None = None,
        ) -> tuple[str, int, str | None]:
            captured_loads.append(load_for_classifier)
            zone, rate, reason = real_adjust(
                baseline_rtt,
                load_for_classifier,
                green_threshold,
                soft_red_threshold,
                hard_red_threshold,
                cake_snapshot=cake_snapshot,
            )
            rates.append(rate)
            return zone, rate, reason

        integrated_controller.download.adjust_4state = MagicMock(side_effect=spy_adjust)

        for queue_delta_us, raw_rtt_delta_ms, correlation in SPECTRUM_2026_04_23_TRACE:
            _run_one_cycle(
                integrated_controller,
                queue_delta_us=queue_delta_us,
                raw_rtt_delta_ms=raw_rtt_delta_ms,
                irtt_correlation=correlation,
            )

        spike_loads = captured_loads[5:15]
        spike_rates = rates[5:15]

        assert spike_loads == [pytest.approx(integrated_controller.baseline_rtt + 0.5)] * 10
        assert integrated_controller.baseline_rtt + 40.0 not in spike_loads
        assert min(spike_rates) > integrated_controller.download.floor_green
        assert integrated_controller._last_arbitration_primary == "queue"


class TestPhase195SourceGuards:
    def test_phase193_replay_imports_still_match_expected_sequences(self) -> None:
        spectrum_zones, spectrum_rates = _replay(
            _fresh_controller("spectrum"),
            TRACE,
            _snap(0, 0, 0),
        )
        att_zones, att_rates = _replay(_fresh_controller("att"), TRACE, _snap(0, 0, 0))

        assert spectrum_zones == EXPECTED_ZONES
        assert spectrum_rates == EXPECTED_SPECTRUM_RATES
        assert att_zones == EXPECTED_ZONES
        assert att_rates == EXPECTED_ATT_RATES
        assert isinstance(_fresh_controller("spectrum"), QueueController)

    def test_ul_call_site_signature_unchanged(self) -> None:
        src = Path("src/wanctl/wan_controller.py").read_text()
        # ARB-04 guard targets the production self.upload.adjust call site.
        pattern = re.compile(
            r"ul_zone, ul_rate, ul_transition_reason = self\.upload\.adjust\(\s*"
            r"self\.baseline_rtt,\s*effective_ul_load_rtt,\s*self\.target_delta,\s*"
            r"self\.warn_delta,\s*cake_snapshot=ul_cake,\s*\)",
        )

        assert pattern.search(src) is not None, (
            "UL call site signature drift detected (ARB-04 violation)"
        )

    def test_safe05_threshold_name_counts_are_unchanged(self) -> None:
        src = Path("src/wanctl/wan_controller.py").read_text()
        expected_counts = {
            "factor_down": 17,
            "step_up": 12,
            "dwell_cycles": 14,
            "deadband_ms": 14,
            "warn_bloat": 4,
            "target_bloat": 4,
            "hard_red": 17,
            "burst_threshold": 0,
            "green_required": 12,
        }

        for name, expected_count in expected_counts.items():
            assert len(re.findall(name, src)) == expected_count

    def test_no_absolute_disagreement_literal_remains(self) -> None:
        src = Path("src/wanctl/wan_controller.py").read_text()

        assert "absolute_disagreement" not in src

    def test_no_queue_rtt_magnitude_ratio(self) -> None:
        src = Path("src/wanctl/wan_controller.py").read_text()

        assert not re.search(r"max_delay_delta_us\s*/\s*(?:self\.)?load_rtt", src)
        assert not re.search(r"(?:self\.)?load_rtt\s*/\s*.*max_delay_delta_us", src)

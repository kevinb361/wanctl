"""Phase 197 replay harness.

Two invariants tested here:

1. Outside refractory, controller behavior is byte-identical to Phase 193/194:
   the 24-row TRACE produces EXPECTED_ZONES and EXPECTED_SPECTRUM_RATES /
   EXPECTED_ATT_RATES verbatim, and arbitration never uses the new Phase 197
   refractory reasons. (D-11.1 + D-10 byte-identity invariant)

2. Inside refractory, the new split makes queue-primary arbitration possible:
   with a valid snapshot, every cycle emits "queue" + "queue_during_refractory";
   with a None/cold_start snapshot, every cycle emits "rtt" +
   "rtt_fallback_during_refractory". (D-11.2 + D-10.2 + D-10.3)

3. Phase 160 cascade safety is preserved: detection path (adjust_4state's
   cake_snapshot kwarg) sees None for every refractory cycle, so dwell-bypass
   cannot re-fire on the same congestion event. (D-10.1 + Phase 160 invariant)

Phase 195 healer-bypass interaction tests (D-12) live in Plan 197-02 alongside
the metric emission and audit-script update.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.test_phase_193_replay import (
    EXPECTED_ATT_RATES,
    EXPECTED_SPECTRUM_RATES,
    EXPECTED_ZONES,
    TRACE,
    _fresh_controller,
    _replay,
    _snap,
)
from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor, CakeSignalSnapshot
from wanctl.wan_controller import (
    ARBITRATION_REASON_GREEN_STABLE,
    ARBITRATION_REASON_QUEUE_DISTRESS,
    ARBITRATION_REASON_QUEUE_DURING_REFRACTORY,
    ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY,
    WANController,
)

# ---------------------------------------------------------------------------
# Helpers (mirrors test_phase_194_replay.py:93-147)
# ---------------------------------------------------------------------------


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
    max_delay_delta_us: int, *, cold_start: bool = False
) -> CakeSignalSnapshot:
    """Canonical valid snapshot — mirrors test_phase_194_replay.py."""
    return CakeSignalSnapshot(
        drop_rate=0.0,
        total_drop_rate=0.0,
        backlog_bytes=0,
        peak_delay_us=max_delay_delta_us + 1000,
        tins=(),
        cold_start=cold_start,
        avg_delay_us=max_delay_delta_us + 500,
        base_delay_us=500,
        max_delay_delta_us=max_delay_delta_us,
    )


def _prepare_queue_primary_controller(ctrl: WANController, variant: str = "spectrum") -> None:
    """Prime ctrl for queue-primary path. Phase 197: also reset refractory stash."""
    ctrl._cake_signal_supported = True
    ctrl.download = _fresh_controller(variant)
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
    ctrl._last_rtt_confidence = None
    ctrl._last_queue_direction = "unknown"
    ctrl._last_rtt_direction = "unknown"
    ctrl._healer_aligned_streak = 0
    ctrl._ul_cake_snapshot = None
    ctrl._dl_refractory_remaining = 0
    ctrl._ul_refractory_remaining = 0
    ctrl._dl_burst_pending = False
    ctrl._dl_arbitration_used_refractory_snapshot = False
    ctrl.download.get_health_data = MagicMock(
        return_value={"cake_detection": {"dwell_bypassed_this_cycle": False}}
    )
    ctrl.upload.get_health_data = MagicMock(
        return_value={"cake_detection": {"dwell_bypassed_this_cycle": False}}
    )


# ---------------------------------------------------------------------------
# D-11.1 + D-10 byte-identity invariant (outside refractory)
# ---------------------------------------------------------------------------


class TestPhase197NonRefractoryByteIdentity:
    """Outside refractory, Phase 197 must be byte-identical to Phase 193/194."""

    @pytest.mark.parametrize(
        "variant,expected_rates",
        [("spectrum", EXPECTED_SPECTRUM_RATES), ("att", EXPECTED_ATT_RATES)],
    )
    def test_replay_byte_identical_to_phase_193_when_no_refractory(
        self, variant, expected_rates
    ) -> None:
        """24-row TRACE with no refractory matches EXPECTED_* at QueueController level."""
        qc = _fresh_controller(variant)
        zones, rates = _replay(qc, TRACE, _snap(0, 0, 0))
        assert zones == EXPECTED_ZONES
        assert rates == expected_rates

    def test_integrated_run_never_uses_refractory_reasons_when_remaining_zero(
        self, integrated_controller
    ) -> None:
        """Refractory-active stash stays False and refractory reasons never emit."""
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        for _ in range(10):
            ctrl._dl_refractory_remaining = 0
            ctrl._dl_cake_snapshot = _queue_snapshot(20_000)
            ctrl._run_congestion_assessment()
            assert ctrl._dl_arbitration_used_refractory_snapshot is False
            assert ctrl._last_arbitration_reason != ARBITRATION_REASON_QUEUE_DURING_REFRACTORY
            assert ctrl._last_arbitration_reason != ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY


# ---------------------------------------------------------------------------
# Phase 197 integrated WANController byte-identity (PRIMARY truth #3 gate)
# ---------------------------------------------------------------------------


class TestPhase197IntegratedNonRefractoryByteIdentity:
    """Drive the changed seam over the 24-row TRACE; assert byte identity."""

    @pytest.mark.parametrize(
        "variant,expected_rates",
        [("spectrum", EXPECTED_SPECTRUM_RATES), ("att", EXPECTED_ATT_RATES)],
    )
    def test_integrated_seam_replay_byte_identical_to_phase_195(
        self, integrated_controller, variant, expected_rates
    ) -> None:
        """24-row TRACE through `_run_congestion_assessment` matches EXPECTED_* per cycle."""
        ctrl = integrated_controller
        ctrl._cake_signal_supported = False
        ctrl.download = _fresh_controller(variant)
        captured_zones: list[str] = []
        captured_rates: list[int] = []
        for baseline_rtt, load_rtt in TRACE:
            ctrl.baseline_rtt = baseline_rtt
            ctrl.load_rtt = load_rtt
            ctrl._dl_cake_snapshot = None
            ctrl._ul_cake_snapshot = None
            ctrl._dl_refractory_remaining = 0
            ctrl._ul_refractory_remaining = 0
            ctrl._dl_burst_pending = False
            ctrl.download.get_health_data = MagicMock(
                return_value={"cake_detection": {"dwell_bypassed_this_cycle": False}}
            )
            ctrl.upload.get_health_data = MagicMock(
                return_value={"cake_detection": {"dwell_bypassed_this_cycle": False}}
            )
            dl_zone, dl_rate, *_ = ctrl._run_congestion_assessment()
            captured_zones.append(dl_zone)
            captured_rates.append(dl_rate)
            assert ctrl._dl_arbitration_used_refractory_snapshot is False
            assert ctrl._last_arbitration_reason != ARBITRATION_REASON_QUEUE_DURING_REFRACTORY
            assert ctrl._last_arbitration_reason != ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY
        assert captured_zones == EXPECTED_ZONES
        assert captured_rates == expected_rates


# ---------------------------------------------------------------------------
# D-11.2 + D-10.3 refractory queue-arbitration semantics
# ---------------------------------------------------------------------------


class TestPhase197RefractoryQueueArbitration:
    """During refractory with a valid snapshot, every cycle is queue-primary."""

    def test_refractory_window_keeps_queue_primary_with_valid_snapshot(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_refractory_remaining = 40
        for cycle_idx in range(40):
            ctrl._dl_cake_snapshot = _queue_snapshot(20_000)
            ctrl._run_congestion_assessment()
            assert ctrl._last_arbitration_primary == "queue", f"cycle {cycle_idx}"
            assert ctrl._last_arbitration_reason == ARBITRATION_REASON_QUEUE_DURING_REFRACTORY
            assert ctrl._dl_arbitration_used_refractory_snapshot is True
        assert ctrl._dl_refractory_remaining == 0
        ctrl._dl_cake_snapshot = _queue_snapshot(20_000)
        ctrl._run_congestion_assessment()
        assert ctrl._last_arbitration_reason in {
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_GREEN_STABLE,
        }
        assert ctrl._dl_arbitration_used_refractory_snapshot is False


# ---------------------------------------------------------------------------
# D-04 + D-10.2 RTT fallback during refractory when snapshot invalid
# ---------------------------------------------------------------------------


class TestPhase197RTTFallbackDuringRefractory:
    """Refractory + invalid snapshot -> rtt_fallback_during_refractory."""

    def test_rtt_fallback_during_refractory_when_snapshot_none(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_refractory_remaining = 40
        ctrl._dl_cake_snapshot = None
        ctrl._run_congestion_assessment()
        assert ctrl._last_arbitration_primary == "rtt"
        assert ctrl._last_arbitration_reason == ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY
        assert ctrl._dl_arbitration_used_refractory_snapshot is True

    def test_rtt_fallback_during_refractory_when_snapshot_cold_start(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_refractory_remaining = 40
        ctrl._dl_cake_snapshot = _queue_snapshot(20_000, cold_start=True)
        ctrl._run_congestion_assessment()
        assert ctrl._last_arbitration_primary == "rtt"
        assert ctrl._last_arbitration_reason == ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY
        assert ctrl._dl_arbitration_used_refractory_snapshot is True


# ---------------------------------------------------------------------------
# D-10.1 + Phase 160 invariant: detection path masked during refractory
# ---------------------------------------------------------------------------


class TestPhase197NoCascadeOnDetection:
    """During refractory, adjust_4state must receive cake_snapshot=None."""

    def test_detection_path_does_not_recascade_during_refractory(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_refractory_remaining = 40
        spy = MagicMock(wraps=ctrl.download.adjust_4state)
        with patch.object(ctrl.download, "adjust_4state", spy):
            for _ in range(10):
                ctrl._dl_cake_snapshot = _queue_snapshot(50_000)
                ctrl._run_congestion_assessment()
        assert spy.call_count == 10
        for call in spy.call_args_list:
            assert call.kwargs.get("cake_snapshot") is None, (
                "Phase 160 cascade safety violated: detection saw live snapshot during refractory"
            )

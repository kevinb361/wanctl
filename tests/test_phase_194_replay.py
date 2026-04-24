"""Phase 194 SAFE-05 + ARB-04 + ARB-01 deterministic replay harness.

Proves three identity axes:

Classifier-level (compositional):
- Forced-fallback DL classifier output is behaviorally identical to v1.39 when
  driven directly through QueueController.adjust_4state.

End-to-end (integrated):
- Phase 193 TRACE driven through WANController._run_congestion_assessment()
  with CAKE disabled produces the same DL zones/rates and apply-call shape.
- Hand-crafted DL CAKE snapshots driven through the same seam with CAKE enabled
  invoke adjust_4state with the queue-delta scalar and surface queue-primary
  through controller state, metrics, and health.

Plus:
- Queue-primary exact-sequence test.
- UL parity and call-site signature guard.
- control_decision_reason vocabulary stays in {'queue_distress', 'green_stable'}.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor, CakeSignalSnapshot
from wanctl.queue_controller import QueueController
from wanctl.wan_controller import ARBITRATION_PRIMARY_ENCODING, ARBITRATION_REASON_GREEN_STABLE, ARBITRATION_REASON_QUEUE_DISTRESS, ARBITRATION_REASON_RTT_VETO, WANController  # noqa: E501

from tests.test_phase_193_replay import (
    EXPECTED_ATT_RATES,
    EXPECTED_SPECTRUM_RATES,
    EXPECTED_ZONES,
    TRACE,
    _fresh_controller,
    _replay,
    _snap,
)

QUEUE_PRIMARY_TRACE_DELTAS_US = [
    0,
    0,
    5_000,
    10_000,
    16_000,
    20_000,
    25_000,
    30_000,
    46_000,
    52_000,
    60_000,
    10_000,
    5_000,
]

EXPECTED_QUEUE_PRIMARY_ZONES = [
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
    "GREEN",
    "GREEN",
]
EXPECTED_QUEUE_PRIMARY_RATES = [
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
    813957120,
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


def _queue_snapshot(max_delta_us: int, *, avg_delay_us: int | None = None, base_delay_us: int = 0) -> CakeSignalSnapshot:
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
    ctrl._ul_cake_snapshot = None
    ctrl._dl_refractory_remaining = 0
    ctrl._ul_refractory_remaining = 0
    ctrl._dl_burst_pending = False


def _metrics_by_name(batch):
    return {
        (metric_name, tuple(sorted((labels or {}).items()))): value
        for _, _, metric_name, value, labels, _ in batch
    }


def _drive_queue_primary(
    controller: QueueController,
    baseline_rtt: float,
    deltas_us: list[int],
    green_threshold: float = 15.0,
    soft_red_threshold: float = 45.0,
    hard_red_threshold: float = 80.0,
) -> tuple[list[str], list[int], list[str]]:
    zones: list[str] = []
    rates: list[int] = []
    reasons: list[str] = []
    for delta_us in deltas_us:
        snap = _snap(
            avg_delay_us=delta_us,
            base_delay_us=0,
            max_delay_delta_us=delta_us,
        )
        delta_ms = snap.max_delay_delta_us / 1000.0
        zone, rate, _transition = controller.adjust_4state(
            baseline_rtt=baseline_rtt,
            load_rtt=baseline_rtt + delta_ms,
            green_threshold=green_threshold,
            soft_red_threshold=soft_red_threshold,
            hard_red_threshold=hard_red_threshold,
            cake_snapshot=snap,
        )
        zones.append(zone)
        rates.append(rate)
        reasons.append(
            ARBITRATION_REASON_QUEUE_DISTRESS
            if delta_ms > green_threshold
            else ARBITRATION_REASON_GREEN_STABLE
        )
    return zones, rates, reasons


def _drive_queue_primary_snapshots(
    controller: QueueController,
    baseline_rtt: float,
    snapshots: list[CakeSignalSnapshot],
    green_threshold: float = 15.0,
    soft_red_threshold: float = 45.0,
    hard_red_threshold: float = 80.0,
) -> tuple[list[str], list[int]]:
    zones: list[str] = []
    rates: list[int] = []
    for snap in snapshots:
        load_rtt = baseline_rtt + snap.max_delay_delta_us / 1000.0
        zone, rate, _transition = controller.adjust_4state(
            baseline_rtt=baseline_rtt,
            load_rtt=load_rtt,
            green_threshold=green_threshold,
            soft_red_threshold=soft_red_threshold,
            hard_red_threshold=hard_red_threshold,
            cake_snapshot=snap,
        )
        zones.append(zone)
        rates.append(rate)
    return zones, rates


class TestPhase194ForcedFallbackByteIdentity:
    def test_spectrum_shape_forced_fallback_zone_sequence_matches_v139(self) -> None:
        zones, _rates = _replay(_fresh_controller("spectrum"), TRACE, _snap(0, 0, 0))

        assert zones == EXPECTED_ZONES

    def test_spectrum_shape_forced_fallback_rate_sequence_matches_v139(self) -> None:
        _zones, rates = _replay(_fresh_controller("spectrum"), TRACE, _snap(0, 0, 0))

        assert rates == EXPECTED_SPECTRUM_RATES

    def test_att_shape_forced_fallback_rate_sequence_matches_v139(self) -> None:
        zones, rates = _replay(_fresh_controller("att"), TRACE, _snap(0, 0, 0))

        assert zones == EXPECTED_ZONES
        assert rates == EXPECTED_ATT_RATES

    def test_selector_in_fallback_returns_load_rtt_literally(self, integrated_controller) -> None:
        integrated_controller._cake_signal_supported = False
        integrated_controller.load_rtt = 37.4

        primary, load_rtt, reason = integrated_controller._select_dl_primary_scalar_ms(None)

        assert (primary, load_rtt, reason) == ("rtt", 37.4, ARBITRATION_REASON_GREEN_STABLE)
        assert load_rtt == integrated_controller.load_rtt


class TestPhase194IntegratedFallbackEndToEnd:
    def test_integrated_fallback_zones_rates_and_apply_order_match_v139(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        ctrl._cake_signal_supported = False
        ctrl.download = _fresh_controller("spectrum")
        real_dl_adjust = ctrl.download.adjust_4state
        real_ul_adjust = ctrl.upload.adjust
        apply_call_order: list[tuple[str, int]] = []
        captured_zones: list[str] = []
        captured_rates: list[int] = []

        for cycle_idx, (baseline_rtt, load_rtt) in enumerate(TRACE):
            ctrl.baseline_rtt = baseline_rtt
            ctrl.load_rtt = load_rtt
            ctrl._dl_cake_snapshot = None
            ctrl._ul_cake_snapshot = None
            ctrl._dl_refractory_remaining = 0
            ctrl._ul_refractory_remaining = 0
            ctrl._dl_burst_pending = False

            def tracking_dl_adjust(*args, **kwargs):
                apply_call_order.append(("download.adjust_4state", cycle_idx))
                return real_dl_adjust(*args, **kwargs)

            def tracking_ul_adjust(*args, **kwargs):
                apply_call_order.append(("upload.adjust", cycle_idx))
                return real_ul_adjust(*args, **kwargs)

            with (
                patch.object(ctrl.download, "adjust_4state", side_effect=tracking_dl_adjust),
                patch.object(ctrl.upload, "adjust", side_effect=tracking_ul_adjust),
            ):
                dl_zone, dl_rate, *_ = ctrl._run_congestion_assessment()
            captured_zones.append(dl_zone)
            captured_rates.append(dl_rate)

        assert captured_zones == EXPECTED_ZONES
        assert captured_rates == EXPECTED_SPECTRUM_RATES
        dl_calls = [call for call in apply_call_order if call[0] == "download.adjust_4state"]
        ul_calls = [call for call in apply_call_order if call[0] == "upload.adjust"]
        assert [call[1] for call in dl_calls] == list(range(len(TRACE)))
        assert [call[1] for call in ul_calls] == list(range(len(TRACE)))


class TestPhase194IntegratedQueuePrimaryPath:
    def test_integrated_queue_primary_invokes_adjust4state_with_queue_delta_scalar(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        deltas_us = [5_000, 20_000, 50_000]
        spy = MagicMock(wraps=ctrl.download.adjust_4state)

        with patch.object(ctrl.download, "adjust_4state", spy):
            for delta_us in deltas_us:
                ctrl._dl_cake_snapshot = _queue_snapshot(delta_us)
                ctrl._run_congestion_assessment()

        assert spy.call_count == len(deltas_us)
        for cycle_idx, delta_us in enumerate(deltas_us):
            args, _kwargs = spy.call_args_list[cycle_idx]
            assert args[0] == pytest.approx(25.0)
            assert args[1] == pytest.approx(25.0 + delta_us / 1000.0)

    def test_integrated_queue_primary_stashes_queue_on_controller(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)

        for delta_us in [5_000, 20_000, 50_000]:
            ctrl._dl_cake_snapshot = _queue_snapshot(delta_us)
            ctrl._run_congestion_assessment()
            assert ctrl._last_arbitration_primary == "queue"

    def test_integrated_queue_primary_metric_value_is_queue_encoding(
        self, integrated_controller
    ) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_cake_snapshot = _queue_snapshot(20_000)
        dl_zone, dl_rate, dl_reason, ul_zone, ul_rate, ul_reason, delta = (
            ctrl._run_congestion_assessment()
        )

        ctrl._run_logging_metrics(
            measured_rtt=25.0,
            fused_rtt=25.0,
            dl_zone=dl_zone,
            ul_zone=ul_zone,
            dl_rate=dl_rate,
            ul_rate=ul_rate,
            delta=delta,
            dl_transition_reason=dl_reason,
            ul_transition_reason=ul_reason,
            irtt_result=None,
        )

        batch = ctrl._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = _metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert metrics[("wanctl_arbitration_active_primary", dl_key)] == pytest.approx(
            float(ARBITRATION_PRIMARY_ENCODING["queue"])
        )

    def test_integrated_queue_primary_health_reports_queue(self, integrated_controller) -> None:
        ctrl = integrated_controller
        _prepare_queue_primary_controller(ctrl)
        ctrl._dl_cake_snapshot = _queue_snapshot(20_000)
        ctrl._run_congestion_assessment()

        result = ctrl.get_health_data()

        assert result["signal_arbitration"]["active_primary_signal"] == "queue"
        assert result["signal_arbitration"]["control_decision_reason"] in {
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_GREEN_STABLE,
        }


class TestPhase194QueuePrimaryDeterministicSequence:
    def test_queue_primary_exact_zone_sequence_for_escalating_deltas(self) -> None:
        zones, rates, reasons = _drive_queue_primary(
            _fresh_controller("spectrum"),
            baseline_rtt=25.0,
            deltas_us=QUEUE_PRIMARY_TRACE_DELTAS_US,
        )

        assert reasons == [
            ARBITRATION_REASON_GREEN_STABLE,
            ARBITRATION_REASON_GREEN_STABLE,
            ARBITRATION_REASON_GREEN_STABLE,
            ARBITRATION_REASON_GREEN_STABLE,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_GREEN_STABLE,
            ARBITRATION_REASON_GREEN_STABLE,
        ]
        assert zones == EXPECTED_QUEUE_PRIMARY_ZONES
        assert rates == EXPECTED_QUEUE_PRIMARY_RATES

    def test_queue_primary_uses_max_delay_delta_us_not_avg_minus_base(self) -> None:
        snapshots = [
            _queue_snapshot(50_000, avg_delay_us=8_000, base_delay_us=0)
            for _ in range(6)
        ]

        zones, _rates = _drive_queue_primary_snapshots(
            _fresh_controller("spectrum"),
            baseline_rtt=25.0,
            snapshots=snapshots,
        )

        assert "SOFT_RED" in zones


class TestPhase194UplinkParity:
    @staticmethod
    def _fresh_upload_controller() -> QueueController:
        return QueueController(
            name="upload",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=30_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.94,
            green_required=5,
            dwell_cycles=3,
            deadband_ms=3.0,
        )

    def test_ul_classifier_output_invariant_to_dl_selector_branch(self) -> None:
        trace = [
            (25.0, 30.0),
            (25.0, 45.0),
            (25.0, 75.0),
            (25.0, 30.0),
            (25.0, 31.0),
            (25.0, 32.0),
        ]
        controllers = [self._fresh_upload_controller(), self._fresh_upload_controller()]
        outputs: list[tuple[list[str], list[int]]] = []

        for controller in controllers:
            zones: list[str] = []
            rates: list[int] = []
            for baseline_rtt, load_rtt in trace:
                zone, rate, _reason = controller.adjust(
                    baseline_rtt,
                    load_rtt,
                    target_delta=15.0,
                    warn_delta=45.0,
                    cake_snapshot=None,
                )
                zones.append(zone)
                rates.append(rate)
            outputs.append((zones, rates))

        assert outputs[0][0] == outputs[1][0]
        assert outputs[0][1] == outputs[1][1]

    def test_ul_call_site_signature_unchanged(self) -> None:
        src = Path("src/wanctl/wan_controller.py").read_text()
        pattern = re.compile(
            r"ul_zone, ul_rate, ul_transition_reason = self\.upload\.adjust\(\s*"
            r"self\.baseline_rtt,\s*effective_ul_load_rtt,\s*self\.target_delta,\s*self\.warn_delta,\s*"
            r"cake_snapshot=ul_cake,\s*\)",
        )

        assert pattern.search(src) is not None, (
            "UL call site signature drift detected (ARB-04 violation)"
        )


class TestPhase194ReasonVocabulary:
    def test_control_decision_reason_is_queue_distress_when_delta_exceeds_green(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._dl_cake_snapshot = _queue_snapshot(20_000)

        _primary, _load_rtt, reason = integrated_controller._select_dl_primary_scalar_ms(
            integrated_controller._dl_cake_snapshot
        )

        assert reason == ARBITRATION_REASON_QUEUE_DISTRESS

    def test_control_decision_reason_is_green_stable_when_delta_below_green(
        self, integrated_controller
    ) -> None:
        _prepare_queue_primary_controller(integrated_controller)
        integrated_controller._dl_cake_snapshot = _queue_snapshot(5_000)

        _primary, _load_rtt, reason = integrated_controller._select_dl_primary_scalar_ms(
            integrated_controller._dl_cake_snapshot
        )

        assert reason == ARBITRATION_REASON_GREEN_STABLE

    def test_control_decision_reason_is_green_stable_in_fallback(
        self, integrated_controller
    ) -> None:
        integrated_controller._cake_signal_supported = False
        integrated_controller.load_rtt = 40.0

        _primary, _load_rtt, reason = integrated_controller._select_dl_primary_scalar_ms(None)

        assert reason == ARBITRATION_REASON_GREEN_STABLE

    @pytest.mark.parametrize(
        ("cake_supported", "snapshot", "baseline_rtt", "green_threshold", "load_rtt"),
        [
            (False, None, 25.0, 15.0, 37.0),
            (True, None, 25.0, 15.0, 37.0),
            (True, _queue_snapshot(0), 25.0, 15.0, 37.0),
            (True, _queue_snapshot(5_000), 25.0, 15.0, 37.0),
            (True, _queue_snapshot(20_000), 25.0, 15.0, 37.0),
            (True, _queue_snapshot(50_000), 25.0, 15.0, 37.0),
        ],
    )
    def test_phase_194_never_emits_rtt_veto(
        self,
        integrated_controller,
        cake_supported: bool,
        snapshot: CakeSignalSnapshot | None,
        baseline_rtt: float,
        green_threshold: float,
        load_rtt: float,
    ) -> None:
        integrated_controller._cake_signal_supported = cake_supported
        integrated_controller.baseline_rtt = baseline_rtt
        integrated_controller.green_threshold = green_threshold
        integrated_controller.load_rtt = load_rtt

        _primary, _load_rtt, reason = integrated_controller._select_dl_primary_scalar_ms(snapshot)

        assert reason in {
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_GREEN_STABLE,
        }
        assert reason != ARBITRATION_REASON_RTT_VETO
        assert reason != "healer_bypass"

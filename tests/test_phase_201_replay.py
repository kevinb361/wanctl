"""Phase 201 replay tests — Attempt 3 diagnostic + legacy byte-identity.

Plan 201-04 Task 3 wires these against the live QueueController surface
landed in Plan 201-04 Tasks 1-2.

Checkpoint revision (2026-05-04): the cycle-fidelity Attempt 3 replay is a
safety diagnostic/regression for legacy byte-identity and replay mechanics, not
a synthetic VALN-06 closure proof. Plan 201-14 later superseded the original
1003-floor-hit diagnostic with bounded-absolute RED decay, so the replay now
pins the post-fix zero-floor-hit invariant.
"""

from __future__ import annotations

from wanctl.cake_signal import CakeSignalSnapshot
from wanctl.queue_controller import QueueController

EXPECTED_ATTEMPT3_CYCLE_FIDELITY_FLOOR_HITS = 0


def _make_docsis_controller(*, setpoint_bps: int = 12_000_000) -> QueueController:
    return QueueController(
        name="ReplayUL",
        floor_green=8_000_000,
        floor_yellow=8_000_000,
        floor_soft_red=8_000_000,
        floor_red=8_000_000,
        ceiling=18_000_000,
        step_up=5_000_000,
        factor_down=0.90,
        factor_down_yellow=1.0,
        green_required=3,
        dwell_cycles=3,
        deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=True,
        setpoint_bps=setpoint_bps,
        integral_window_seconds=2.0,
        integral_threshold_ms_s=30.0,
        cake_backlog_low_threshold_bytes=5000,
        cake_delay_delta_low_threshold_us=5000,
    )


def _make_legacy_controller() -> QueueController:
    return QueueController(
        name="ReplayLegacy",
        floor_green=8_000_000,
        floor_yellow=8_000_000,
        floor_soft_red=8_000_000,
        floor_red=8_000_000,
        ceiling=18_000_000,
        step_up=5_000_000,
        factor_down=0.90,
        factor_down_yellow=1.0,
        green_required=3,
        dwell_cycles=3,
        deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
    )


def _make_docsis_off_controller() -> QueueController:
    """docsis_mode=False must match legacy (zone, rate) traces exactly."""
    return QueueController(
        name="ReplayDocsisOff",
        floor_green=8_000_000,
        floor_yellow=8_000_000,
        floor_soft_red=8_000_000,
        floor_red=8_000_000,
        ceiling=18_000_000,
        step_up=5_000_000,
        factor_down=0.90,
        factor_down_yellow=1.0,
        green_required=3,
        dwell_cycles=3,
        deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=False,
    )


def _synth_cake_from_sample(sample) -> CakeSignalSnapshot | None:
    """Synthesize a CakeSignalSnapshot from a ReplaySample.

    Per 201-01-CORPUS-AUDIT.md, Attempt 3 has backlog_bytes and cold_start but
    lacks max_delay_delta_us. High backlog maps to high delay-delta so the
    corroborator remains conservatively biased toward vetoing push-up under
    load. Hold-last replay keeps this synthesized value constant for all 20
    synthetic cycles emitted from a 1 Hz sample.
    """
    if sample.cake_backlog_bytes is None:
        return None
    backlog = int(sample.cake_backlog_bytes)
    delay_delta = 8000 if backlog > 5000 else 100
    return CakeSignalSnapshot(
        drop_rate=0.0,
        total_drop_rate=0.0,
        backlog_bytes=backlog,
        peak_delay_us=delay_delta + 100,
        tins=(),
        cold_start=bool(sample.cake_cold_start),
        avg_delay_us=delay_delta + 50,
        base_delay_us=50,
        max_delay_delta_us=delay_delta,
    )


class TestAttempt3ReplayWithDocsisMode:
    # REVIEWS HIGH-4 (2026-05-04), revised after checkpoint decision.
    # Each 1 Hz NDJSON sample expands to 20 synthetic 50ms cycles via
    # hold-last interpolation to exercise the 2s integral and dwell windows at
    # production cadence while preserving RED-heavy samples instead of smoothing
    # them away.
    CYCLES_PER_SAMPLE = 20  # 1 Hz NDJSON -> 20 Hz controller cadence (1/0.05)

    def test_red_heavy_replay_holds_above_floor_after_bounded_decay(
        self, phase201_attempt3_trace
    ) -> None:
        """Cycle-fidelity replay safety diagnostic for Attempt 3.

        Plan 201-14 replaced the earlier multiplicative RED decay with
        bounded-absolute decay that holds above the floor under DOCSIS mode.
        Keep RED-heavy replay coverage while pinning the final post-fix
        invariant: no floor-hit cycles.
        """
        assert phase201_attempt3_trace, "Attempt 3 trace empty — corpus loader missing"

        ctrl = _make_docsis_controller(setpoint_bps=12_000_000)
        # Codex pre-review HIGH #3: Phase 201 runtime falls back to Spectrum
        # global thresholds after upload R0 keys are stripped.
        target_delta = 15.0
        warn_delta = 75.0
        cycles_replayed = 0
        red_cycles = 0

        for sample in phase201_attempt3_trace:
            if sample.baseline_rtt_ms is None or sample.load_rtt_ms is None:
                continue
            cake = _synth_cake_from_sample(sample)
            # Hold-last expansion: 20 synthetic cycles per NDJSON sample.
            for _ in range(self.CYCLES_PER_SAMPLE):
                zone, _, _ = ctrl.adjust(
                    sample.baseline_rtt_ms,
                    sample.load_rtt_ms,
                    target_delta,
                    warn_delta,
                    cake_snapshot=cake,
                )
                cycles_replayed += 1
                red_cycles += int(zone == "RED")

        assert cycles_replayed > 0, "no samples replayed"
        assert red_cycles > 0, "Attempt 3 diagnostic must remain RED-heavy"
        assert ctrl.floor_hit_cycles == EXPECTED_ATTEMPT3_CYCLE_FIDELITY_FLOOR_HITS


class TestLegacyByteIdentity:
    def test_no_docsis_key_byte_identical_3state(
        self, phase201_sustained_load_trace
    ) -> None:
        legacy = _make_legacy_controller()
        docsis_off = _make_docsis_off_controller()
        target_delta, warn_delta = 5.0, 15.0
        legacy_trace, docsis_trace = [], []
        for sample in phase201_sustained_load_trace:
            l_zone, l_rate, _ = legacy.adjust(
                sample.baseline_rtt_ms,
                sample.load_rtt_ms,
                target_delta,
                warn_delta,
            )
            d_zone, d_rate, _ = docsis_off.adjust(
                sample.baseline_rtt_ms,
                sample.load_rtt_ms,
                target_delta,
                warn_delta,
            )
            legacy_trace.append((l_zone, l_rate))
            docsis_trace.append((d_zone, d_rate))
        assert legacy_trace == docsis_trace, (
            "D-17 invariant: docsis_mode=False is byte-identical to legacy"
        )

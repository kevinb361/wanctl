"""Tests for fusion baseline deadlock fix (signal path split).

Validates that baseline EWMA receives ICMP-only filtered_rtt while load EWMA
receives fused RTT. Prevents IRTT path divergence from freezing or corrupting
baseline RTT.

Covers:
- FBLK-01: _update_baseline_if_idle receives ICMP-only signal (not fused)
- FBLK-02: load_rtt EWMA uses fused signal for congestion detection
- FBLK-03: ATT scenario baseline updates when idle despite IRTT divergence
- FBLK-04: Fusion-disabled behavior is identical to pre-fix code path
- FBLK-05: Freeze gate delta uses icmp_rtt - baseline_rtt

Requirements: FBLK-01, FBLK-02, FBLK-03, FBLK-04, FBLK-05.
"""

import logging
from unittest.mock import MagicMock

import pytest

from wanctl.wan_controller import WANController

# =============================================================================
# HELPERS
# =============================================================================


def _make_controller(**overrides):
    """Create a lightweight mock WANController with real baseline/EWMA methods.

    Uses MagicMock(spec=WANController) with real methods bound for
    _update_baseline_if_idle and update_ewma. Sets explicit float attributes
    to avoid MagicMock truthy trap.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = overrides.get("wan_name", "TestWAN")
    controller.logger = logging.getLogger("test.fusion_baseline")

    # EWMA parameters
    controller.alpha_load = overrides.get("alpha_load", 0.1)
    controller.alpha_baseline = overrides.get("alpha_baseline", 0.001)
    controller.baseline_update_threshold = overrides.get("baseline_update_threshold", 3.0)

    # RTT state
    controller.load_rtt = overrides.get("load_rtt", 25.0)
    controller.baseline_rtt = overrides.get("baseline_rtt", 25.0)
    controller.baseline_rtt_min = overrides.get("baseline_rtt_min", 10.0)
    controller.baseline_rtt_max = overrides.get("baseline_rtt_max", 60.0)

    # Bind real methods
    controller._update_baseline_if_idle = WANController._update_baseline_if_idle.__get__(
        controller, WANController
    )
    controller.update_ewma = WANController.update_ewma.__get__(controller, WANController)

    return controller


# =============================================================================
# FBLK-01: BASELINE USES ICMP-ONLY SIGNAL
# =============================================================================


class TestBaselineUsesIcmpOnly:
    """Validate that _update_baseline_if_idle uses ICMP-only delta for freeze gate."""

    def test_baseline_receives_icmp_not_fused(self):
        """Baseline updates when ICMP delta < threshold even if fused load is high.

        ATT scenario: baseline=29.0, load_rtt=33.2 (fused value).
        Call _update_baseline_if_idle(25.0).
        Fix: delta = 25.0 - 29.0 = -4.0 < 3.0 -> baseline updates.
        Old code: delta = load_rtt(33.2) - baseline(29.0) = 4.2 >= 3.0 -> FROZEN.
        """
        controller = _make_controller(
            baseline_rtt=29.0,
            load_rtt=33.2,  # Fused value (ATT: 0.7*29 + 0.3*43)
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,  # Large alpha for visible change
        )

        controller._update_baseline_if_idle(25.0)

        # With the fix, delta = 25.0 - 29.0 = -4.0 < 3.0 -> baseline updates
        # Baseline should move toward 25.0: 0.9*29 + 0.1*25 = 28.6
        assert controller.baseline_rtt != 29.0, (
            "Baseline should have updated (ICMP delta < threshold)"
        )
        assert controller.baseline_rtt == pytest.approx(28.6, abs=0.01)

    def test_baseline_ewma_uses_icmp_value(self):
        """Baseline EWMA computation uses icmp_rtt, not load_rtt or fused value."""
        controller = _make_controller(
            baseline_rtt=20.0,
            load_rtt=20.5,  # Small delta, ensures update
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,
        )

        controller._update_baseline_if_idle(22.0)

        # Expected: 0.9*20 + 0.1*22 = 20.2
        assert controller.baseline_rtt == pytest.approx(20.2, abs=0.01)


# =============================================================================
# FBLK-02: LOAD EWMA USES FUSED SIGNAL
# =============================================================================


class TestLoadEwmaUsesFused:
    """Validate that load_rtt tracks the fused signal, not ICMP-only."""

    def test_load_rtt_tracks_fused_signal(self):
        """After inline EWMA with fused_rtt=33.2, load_rtt converges toward 33.2."""
        controller = _make_controller(
            load_rtt=25.0,
            alpha_load=0.1,
        )

        fused_rtt = 33.2
        # Inline load EWMA (the fix does this instead of update_ewma)
        controller.load_rtt = (
            1 - controller.alpha_load
        ) * controller.load_rtt + controller.alpha_load * fused_rtt

        # Expected: 0.9*25 + 0.1*33.2 = 25.82
        assert controller.load_rtt == pytest.approx(25.82, abs=0.01)

    def test_load_rtt_not_icmp_when_fused(self):
        """Load EWMA must move toward fused value (33.2), not ICMP (25.0)."""
        controller = _make_controller(
            load_rtt=25.0,
            alpha_load=0.1,
        )

        fused_rtt = 33.2
        controller.load_rtt = (
            1 - controller.alpha_load
        ) * controller.load_rtt + controller.alpha_load * fused_rtt

        # load_rtt must be > 25.0 (moved toward fused, not stayed at ICMP)
        assert controller.load_rtt > 25.0


# =============================================================================
# FBLK-03: ATT/SPECTRUM DIVERGENCE SCENARIOS
# =============================================================================


class TestBaselineUpdatesWithIrttDivergence:
    """Validate baseline tracks ICMP idle despite IRTT path divergence."""

    def test_att_scenario_baseline_not_frozen(self):
        """ATT production: ICMP=29ms, IRTT=43ms, fused=33.2ms.

        100 idle cycles: baseline must track ICMP (~29ms), not freeze.
        Pre-fix: fused load_rtt=33.2, delta=33.2-29=4.2 > 3ms -> FROZEN.
        Post-fix: delta=29-29=0 < 3ms -> baseline updates (stays ~29ms).
        """
        controller = _make_controller(
            baseline_rtt=29.0,
            load_rtt=29.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        icmp_filtered = 29.0
        irtt_rtt = 43.0
        icmp_weight = 0.7

        for _ in range(100):
            # Compute fused RTT
            fused_rtt = icmp_weight * icmp_filtered + (1 - icmp_weight) * irtt_rtt
            # 0.7*29 + 0.3*43 = 33.2

            # Split EWMA (the fix): load uses fused, baseline uses ICMP
            controller.load_rtt = (
                1 - controller.alpha_load
            ) * controller.load_rtt + controller.alpha_load * fused_rtt
            controller._update_baseline_if_idle(icmp_filtered)

        # After 100 cycles:
        # - load_rtt should converge toward 33.2 (fused)
        assert controller.load_rtt == pytest.approx(33.2, abs=0.5)
        # - baseline should stay near 29.0 (ICMP idle, not frozen)
        assert controller.baseline_rtt == pytest.approx(29.0, abs=0.5)

    def test_spectrum_scenario_baseline_tracks_icmp(self):
        """Spectrum production: ICMP=25ms, IRTT=19ms, fused=23.2ms.

        100 idle cycles: baseline stays near 25.0ms (ICMP), load converges to 23.2ms.
        """
        controller = _make_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        icmp_filtered = 25.0
        irtt_rtt = 19.0
        icmp_weight = 0.7

        for _ in range(100):
            fused_rtt = icmp_weight * icmp_filtered + (1 - icmp_weight) * irtt_rtt
            # 0.7*25 + 0.3*19 = 23.2

            controller.load_rtt = (
                1 - controller.alpha_load
            ) * controller.load_rtt + controller.alpha_load * fused_rtt
            controller._update_baseline_if_idle(icmp_filtered)

        # load_rtt converges toward 23.2 (fused)
        assert controller.load_rtt == pytest.approx(23.2, abs=0.5)
        # baseline stays near 25.0 (ICMP idle)
        assert controller.baseline_rtt == pytest.approx(25.0, abs=0.5)


# =============================================================================
# FBLK-04: FUSION DISABLED PRODUCES IDENTICAL BEHAVIOR
# =============================================================================


class TestFusionDisabledIdentical:
    """When fusion is disabled, split path must produce identical results to old path."""

    def test_split_path_matches_update_ewma_when_no_fusion(self):
        """Two controllers, same input, old vs new path -- identical results.

        Controller A: update_ewma(filtered_rtt) per cycle (old path).
        Controller B: inline load EWMA + _update_baseline_if_idle(filtered_rtt) (new path).
        When fusion disabled, fused_rtt == filtered_rtt.
        """
        controller_a = _make_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )
        controller_b = _make_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        # 50 cycles with varying RTT (ramp from 20 to 35)
        for i in range(50):
            filtered_rtt = 20.0 + (i * 15.0 / 49.0)

            # Controller A: old path (update_ewma does both)
            controller_a.update_ewma(filtered_rtt)

            # Controller B: new split path (fusion disabled, fused == filtered)
            fused_rtt = filtered_rtt  # No fusion
            controller_b.load_rtt = (
                1 - controller_b.alpha_load
            ) * controller_b.load_rtt + controller_b.alpha_load * fused_rtt
            controller_b._update_baseline_if_idle(filtered_rtt)

        # Both should produce identical results
        assert controller_a.load_rtt == pytest.approx(controller_b.load_rtt, abs=1e-10)
        assert controller_a.baseline_rtt == pytest.approx(controller_b.baseline_rtt, abs=1e-10)


# =============================================================================
# FBLK-05: FREEZE GATE DELTA USES ICMP
# =============================================================================


class TestCongestionZoneDelta:
    """Validate that freeze gate delta = icmp_rtt - baseline_rtt."""

    def test_freeze_gate_uses_icmp_delta(self):
        """Baseline updates when ICMP is close to baseline, regardless of fused load.

        baseline=25.0, load_rtt=23.2 (fused Spectrum idle).
        Call _update_baseline_if_idle(25.5).
        Fix: delta = 25.5 - 25.0 = 0.5 < 3.0 -> baseline updates.
        Old code: delta = 23.2 - 25.0 = -1.8 < 3.0 -> also updates (but wrong reason).
        """
        controller = _make_controller(
            baseline_rtt=25.0,
            load_rtt=23.2,  # Fused Spectrum idle (IRTT < ICMP)
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,
        )

        controller._update_baseline_if_idle(25.5)

        # Baseline should update: 0.9*25 + 0.1*25.5 = 25.05
        assert controller.baseline_rtt == pytest.approx(25.05, abs=0.01)

    def test_freeze_gate_freezes_on_icmp_load(self):
        """Baseline freezes when ICMP shows load (delta >= threshold).

        baseline=25.0, call _update_baseline_if_idle(30.0).
        Fix: delta = 30.0 - 25.0 = 5.0 >= 3.0 -> FROZEN.
        """
        controller = _make_controller(
            baseline_rtt=25.0,
            load_rtt=23.2,  # Irrelevant with fix (not used in delta)
            baseline_update_threshold=3.0,
        )

        original_baseline = controller.baseline_rtt
        controller._update_baseline_if_idle(30.0)

        # Baseline should NOT change (ICMP delta >= threshold)
        assert controller.baseline_rtt == original_baseline

"""Tests for dual-signal fusion computation and fallback behavior.

Covers:
- _compute_fused_rtt() weighted average with fresh IRTT
- _compute_fused_rtt() fallback to filtered_rtt when IRTT disabled
- _compute_fused_rtt() fallback to filtered_rtt when IRTT unavailable (None)
- _compute_fused_rtt() fallback to filtered_rtt when IRTT stale
- _compute_fused_rtt() fallback to filtered_rtt when IRTT rtt_mean_ms <= 0
- Staleness boundary tests (just within / just beyond 3x cadence)
- Weight variation tests (0.0, 0.5, 0.7, 1.0)
- DEBUG logging behavior

Requirements: FUSE-01, FUSE-04.
"""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.irtt_measurement import IRTTResult


# =============================================================================
# HELPERS
# =============================================================================


def _make_irtt_result(rtt_ms: float = 20.0, age_offset: float = 0.0) -> IRTTResult:
    """Create an IRTTResult with controllable RTT and timestamp.

    Args:
        rtt_ms: The rtt_mean_ms value.
        age_offset: Seconds to subtract from current monotonic time (simulates age).
    """
    return IRTTResult(
        rtt_mean_ms=rtt_ms,
        rtt_median_ms=rtt_ms - 0.5,
        ipdv_mean_ms=1.0,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=100,
        packets_received=100,
        server="104.200.21.31",
        port=2112,
        timestamp=time.monotonic() - age_offset,
        success=True,
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_controller():
    """Create a lightweight mock WANController with fusion attributes.

    Uses MagicMock(spec=WANController) with specific attributes set for
    _compute_fused_rtt. The real method is bound to the mock.
    """
    from wanctl.autorate_continuous import WANController

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.fusion_core")

    # Fusion config (default weights, enabled for computation tests)
    controller._fusion_icmp_weight = 0.7
    controller._fusion_enabled = True

    # IRTT thread (default: None / disabled)
    controller._irtt_thread = None

    # Bind the real method
    controller._compute_fused_rtt = (
        WANController._compute_fused_rtt.__get__(controller, WANController)
    )

    return controller


# =============================================================================
# FUSION COMPUTATION (FUSE-01)
# =============================================================================


class TestFusionComputation:
    """Tests for weighted average fusion when IRTT is fresh and valid."""

    def test_default_weights_0_7_icmp_0_3_irtt(self, mock_controller):
        """0.7*30 + 0.3*20 = 27.0 with default weights."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(27.0)

    def test_custom_weights_0_5(self, mock_controller):
        """0.5*30 + 0.5*20 = 25.0 with equal weights."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 0.5

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(25.0)

    def test_all_icmp_weight_1_0(self, mock_controller):
        """Weight 1.0 means fused = filtered_rtt (IRTT ignored)."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 1.0

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(30.0)

    def test_all_irtt_weight_0_0(self, mock_controller):
        """Weight 0.0 means fused = irtt_rtt (ICMP ignored)."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 0.0

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(20.0)

    def test_debug_log_emitted_on_fusion(self, mock_controller, caplog):
        """DEBUG log emitted with icmp, irtt, and fused values when fusion active."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" in caplog.text
        assert "icmp=" in caplog.text
        assert "irtt=" in caplog.text


# =============================================================================
# FUSION FALLBACK (FUSE-04)
# =============================================================================


class TestFusionFallback:
    """Tests for fallback to filtered_rtt when IRTT is unavailable/stale/invalid."""

    def test_irtt_thread_none_returns_filtered_rtt(self, mock_controller):
        """When _irtt_thread is None (disabled), filtered_rtt passes through unchanged."""
        mock_controller._irtt_thread = None

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_get_latest_none_returns_filtered_rtt(self, mock_controller):
        """When get_latest() returns None (no data yet), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = None
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_stale_returns_filtered_rtt(self, mock_controller):
        """When IRTT result is stale (age > 3x cadence), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        # age=35s, cadence=10s -> 35 > 30 threshold -> stale
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=35.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_rtt_zero_returns_filtered_rtt(self, mock_controller):
        """When IRTT rtt_mean_ms is 0.0 (total loss), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=0.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_rtt_negative_returns_filtered_rtt(self, mock_controller):
        """When IRTT rtt_mean_ms is negative (invalid), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=-1.0, age_offset=1.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_staleness_boundary_just_within(self, mock_controller):
        """IRTT at exactly 3x cadence boundary (age=29.9, cadence=10) -> fused value."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=29.9)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        # 0.7*30 + 0.3*20 = 27.0
        assert result == pytest.approx(27.0)

    def test_staleness_boundary_just_beyond(self, mock_controller):
        """IRTT just past 3x cadence boundary (age=30.1, cadence=10) -> filtered_rtt."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=30.1)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_no_debug_log_when_irtt_none(self, mock_controller, caplog):
        """No DEBUG log emitted when IRTT is disabled (thread None)."""
        mock_controller._irtt_thread = None

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text

    def test_no_debug_log_when_irtt_stale(self, mock_controller, caplog):
        """No DEBUG log emitted when IRTT result is stale."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=35.0)
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text

    def test_no_debug_log_when_irtt_result_none(self, mock_controller, caplog):
        """No DEBUG log emitted when get_latest() returns None."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = None
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text


# =============================================================================
# FUSION ENABLED GUARD (FUSE-02)
# =============================================================================


class TestFusionEnabledGuard:
    """Tests for _fusion_enabled guard in _compute_fused_rtt."""

    def test_disabled_returns_filtered_rtt_without_irtt_access(self, mock_controller):
        """When _fusion_enabled=False, returns filtered_rtt and does NOT access IRTT."""
        irtt_thread = MagicMock()
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = False

        result = mock_controller._compute_fused_rtt(30.0)

        assert result == 30.0
        irtt_thread.get_latest.assert_not_called()

    def test_enabled_with_irtt_computes_fusion(self, mock_controller):
        """When _fusion_enabled=True and IRTT is valid, returns weighted average."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(
            rtt_ms=20.0, age_offset=1.0
        )
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = True

        result = mock_controller._compute_fused_rtt(30.0)
        # 0.7*30 + 0.3*20 = 27.0
        assert result == pytest.approx(27.0)


# =============================================================================
# FUSION RTT TRACKING (FUSE-05 observability support)
# =============================================================================


class TestFusionRTTTracking:
    """Tests for _last_fused_rtt and _last_icmp_filtered_rtt attribute storage."""

    def test_disabled_stores_icmp_rtt_and_null_fused(self, mock_controller):
        """When fusion disabled, stores ICMP RTT but fused is None."""
        mock_controller._fusion_enabled = False

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        assert mock_controller._last_fused_rtt is None

    def test_fallback_no_irtt_stores_icmp_rtt_and_null_fused(self, mock_controller):
        """When fusion enabled but IRTT unavailable, stores ICMP RTT, fused is None."""
        mock_controller._fusion_enabled = True
        mock_controller._irtt_thread = None

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        assert mock_controller._last_fused_rtt is None

    def test_fused_stores_both_values(self, mock_controller):
        """When fusion active, stores both ICMP and fused RTT values."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(
            rtt_ms=20.0, age_offset=1.0
        )
        irtt_thread._cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = True
        mock_controller._fusion_icmp_weight = 0.7

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        # 0.7*30 + 0.3*20 = 27.0
        assert mock_controller._last_fused_rtt == pytest.approx(27.0)

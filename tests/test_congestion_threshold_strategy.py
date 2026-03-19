"""Tests for congestion threshold calibration strategies (CALI-01 thru CALI-04).

Tests cover:
- _extract_green_deltas: timestamp-based GREEN-state filtering
- calibrate_target_bloat: p75 of GREEN-state RTT delta (CALI-01)
- calibrate_warn_bloat: p90 of GREEN-state RTT delta (CALI-02)
- Convergence detection via sub-window CoV (CALI-03)
- 24h diurnal lookback processing (CALI-04)
"""

from __future__ import annotations

import random
import time

import pytest

from wanctl.tuning.models import SafetyBounds

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def _make_green_metrics(
    count: int = 200,
    base_delta: float = 10.0,
    noise_scale: float = 3.0,
    green_fraction: float = 0.8,
) -> list[dict]:
    """Generate synthetic metrics with mixed GREEN/YELLOW state.

    Produces interleaved wanctl_state and wanctl_rtt_delta_ms rows with
    controllable GREEN fraction. First `count * green_fraction` timestamps
    are GREEN, remainder are YELLOW.

    Delta values include a time-correlated ramp so sub-windows have different
    distributions (avoids triggering convergence detection in tests that
    expect a TuningResult).
    """
    now = int(time.time())
    metrics: list[dict] = []
    green_count = int(count * green_fraction)
    for i in range(count):
        ts = now - (count - i) * 60  # 1m intervals going backward
        # Cycling noise + linear ramp to ensure inter-sub-window variance
        delta = base_delta + (i % 5) * noise_scale / 5 + (i / count) * noise_scale
        state = 0.0 if i < green_count else 1.0

        metrics.append({
            "timestamp": ts,
            "wan_name": "Spectrum",
            "metric_name": "wanctl_rtt_delta_ms",
            "value": delta,
            "labels": None,
            "granularity": "1m",
        })
        metrics.append({
            "timestamp": ts,
            "wan_name": "Spectrum",
            "metric_name": "wanctl_state",
            "value": state,
            "labels": None,
            "granularity": "1m",
        })
    return metrics


def _make_uniform_metrics(
    count: int = 200,
    delta_value: float = 12.0,
) -> list[dict]:
    """Generate all-GREEN metrics with uniform delta for convergence testing.

    All timestamps have state=GREEN (0.0) and identical delta values.
    """
    now = int(time.time())
    metrics: list[dict] = []
    for i in range(count):
        ts = now - (count - i) * 60
        metrics.append({
            "timestamp": ts,
            "wan_name": "Spectrum",
            "metric_name": "wanctl_rtt_delta_ms",
            "value": delta_value,
            "labels": None,
            "granularity": "1m",
        })
        metrics.append({
            "timestamp": ts,
            "wan_name": "Spectrum",
            "metric_name": "wanctl_state",
            "value": 0.0,
            "labels": None,
            "granularity": "1m",
        })
    return metrics


# Default safety bounds used across tests
DEFAULT_BOUNDS = SafetyBounds(min_value=3.0, max_value=50.0)


# ---------------------------------------------------------------------------
# TestExtractGreenDeltas
# ---------------------------------------------------------------------------

class TestExtractGreenDeltas:
    """Tests for _extract_green_deltas helper."""

    def test_returns_deltas_only_for_green_state(self) -> None:
        """Test 1: Returns RTT deltas only where wanctl_state == 0.0 (GREEN)."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas,
        )

        metrics = _make_green_metrics(count=100, green_fraction=0.5)
        result = _extract_green_deltas(metrics)
        # 50% of 100 = 50 GREEN timestamps
        assert len(result) == 50

    def test_returns_empty_when_no_green_state(self) -> None:
        """Test 2: Returns empty list when no GREEN-state timestamps exist."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas,
        )

        metrics = _make_green_metrics(count=100, green_fraction=0.0)
        result = _extract_green_deltas(metrics)
        assert result == []

    def test_returns_empty_when_no_matching_timestamps(self) -> None:
        """Test 3: Returns empty list when timestamps don't overlap."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas,
        )

        now = int(time.time())
        # State rows at timestamps 1000-1010, delta rows at 2000-2010
        metrics = [
            {"timestamp": now + i, "wan_name": "Spectrum",
             "metric_name": "wanctl_state", "value": 0.0,
             "labels": None, "granularity": "1m"}
            for i in range(10)
        ] + [
            {"timestamp": now + 1000 + i, "wan_name": "Spectrum",
             "metric_name": "wanctl_rtt_delta_ms", "value": 5.0,
             "labels": None, "granularity": "1m"}
            for i in range(10)
        ]
        result = _extract_green_deltas(metrics)
        assert result == []

    def test_handles_only_state_or_only_delta_rows(self) -> None:
        """Test 4: Handles metrics with only state or only delta rows."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas,
        )

        now = int(time.time())
        # Only state rows
        state_only = [
            {"timestamp": now + i, "wan_name": "Spectrum",
             "metric_name": "wanctl_state", "value": 0.0,
             "labels": None, "granularity": "1m"}
            for i in range(10)
        ]
        assert _extract_green_deltas(state_only) == []

        # Only delta rows
        delta_only = [
            {"timestamp": now + i, "wan_name": "Spectrum",
             "metric_name": "wanctl_rtt_delta_ms", "value": 5.0,
             "labels": None, "granularity": "1m"}
            for i in range(10)
        ]
        assert _extract_green_deltas(delta_only) == []


# ---------------------------------------------------------------------------
# TestCalibrateTargetBloat (CALI-01)
# ---------------------------------------------------------------------------

class TestCalibrateTargetBloat:
    """Tests for calibrate_target_bloat strategy function."""

    def test_returns_tuning_result_with_p75(self) -> None:
        """Test 5: Returns TuningResult with parameter='target_bloat_ms'
        and new_value=round(p75, 1) for 200 GREEN samples."""
        from statistics import quantiles

        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")

        assert result is not None
        assert result.parameter == "target_bloat_ms"

        # Verify p75 computation matches expected
        # Delta formula: base + (i%5)*noise/5 + (i/count)*noise
        # with base=10.0, noise=3.0, count=200
        deltas = [10.0 + (i % 5) * 3.0 / 5 + (i / 200) * 3.0 for i in range(200)]
        expected_p75 = quantiles(deltas, n=100)[74]
        assert result.new_value == round(expected_p75, 1)

    def test_returns_none_when_fewer_than_60_green(self) -> None:
        """Test 6: Returns None when fewer than 60 GREEN samples."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        metrics = _make_green_metrics(count=50, green_fraction=1.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is None

    def test_confidence_equals_green_count_over_1440(self) -> None:
        """Test 7: Confidence equals min(1.0, green_count / 1440.0)."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        # 200 GREEN samples -> confidence = 200/1440 = 0.1388...
        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is not None
        expected_confidence = min(1.0, 200 / 1440.0)
        assert result.confidence == pytest.approx(expected_confidence, abs=0.001)

    def test_rationale_contains_p75_and_count(self) -> None:
        """Test 8: Rationale contains 'p75' and sample count."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is not None
        assert "p75" in result.rationale
        assert "200" in result.rationale

    def test_wan_name_passed_through(self) -> None:
        """Test 9: wan_name is passed through to TuningResult."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "ATT")
        assert result is not None
        assert result.wan_name == "ATT"


# ---------------------------------------------------------------------------
# TestCalibrateWarnBloat (CALI-02)
# ---------------------------------------------------------------------------

class TestCalibrateWarnBloat:
    """Tests for calibrate_warn_bloat strategy function."""

    def test_returns_tuning_result_with_p90(self) -> None:
        """Test 10: Returns TuningResult with parameter='warn_bloat_ms'
        and new_value=round(p90, 1) for 200 GREEN samples."""
        from statistics import quantiles

        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_warn_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_warn_bloat(metrics, 45.0, DEFAULT_BOUNDS, "Spectrum")

        assert result is not None
        assert result.parameter == "warn_bloat_ms"

        deltas = [10.0 + (i % 5) * 3.0 / 5 + (i / 200) * 3.0 for i in range(200)]
        expected_p90 = quantiles(deltas, n=100)[89]
        assert result.new_value == round(expected_p90, 1)

    def test_returns_none_when_fewer_than_60_green(self) -> None:
        """Test 11: Returns None when fewer than 60 GREEN samples."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_warn_bloat,
        )

        metrics = _make_green_metrics(count=50, green_fraction=1.0)
        result = calibrate_warn_bloat(metrics, 45.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is None

    def test_confidence_equals_green_count_over_1440(self) -> None:
        """Test 12: Confidence equals min(1.0, green_count / 1440.0)."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_warn_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_warn_bloat(metrics, 45.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is not None
        expected_confidence = min(1.0, 200 / 1440.0)
        assert result.confidence == pytest.approx(expected_confidence, abs=0.001)

    def test_rationale_contains_p90_and_count(self) -> None:
        """Test 13: Rationale contains 'p90' and sample count."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_warn_bloat,
        )

        metrics = _make_green_metrics(count=200, green_fraction=1.0)
        result = calibrate_warn_bloat(metrics, 45.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is not None
        assert "p90" in result.rationale
        assert "200" in result.rationale


# ---------------------------------------------------------------------------
# TestConvergenceDetection (CALI-03)
# ---------------------------------------------------------------------------

class TestConvergenceDetection:
    """Tests for convergence detection via sub-window CoV."""

    def test_returns_none_when_converged(self) -> None:
        """Test 14: Returns None when _is_converged detects CoV below threshold."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        # Uniform data -> all sub-windows have same percentile -> CoV = 0 -> converged
        metrics = _make_uniform_metrics(count=200, delta_value=12.0)
        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is None

    def test_returns_result_when_not_converged(self) -> None:
        """Test 15: Returns TuningResult when CoV is above threshold."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        # Create data with high variance between sub-windows
        now = int(time.time())
        metrics: list[dict] = []
        for i in range(200):
            ts = now - (200 - i) * 60
            # Sub-windows get very different delta values
            quarter = i // 50
            if quarter == 0:
                delta = 5.0
            elif quarter == 1:
                delta = 15.0
            elif quarter == 2:
                delta = 25.0
            else:
                delta = 35.0

            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_rtt_delta_ms", "value": delta,
                "labels": None, "granularity": "1m",
            })
            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_state", "value": 0.0,
                "labels": None, "granularity": "1m",
            })

        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        assert result is not None  # Not converged, returns a result

    def test_not_converged_when_insufficient_sub_window_data(self) -> None:
        """Test 16: Not converged when sub-windows have < 10 samples each."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas_with_timestamps,
            _is_converged,
        )

        # Only 20 total samples -> 5 per sub-window (< 10 minimum)
        metrics = _make_uniform_metrics(count=20, delta_value=12.0)
        green_deltas, timestamps = _extract_green_deltas_with_timestamps(metrics)
        # Should not be converged due to insufficient sub-window data
        assert not _is_converged(green_deltas, timestamps, 74)

    def test_converged_when_mean_near_zero(self) -> None:
        """Test 17: Converged when avg < 0.001 guard."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _is_converged,
        )

        # All sub-window percentiles near zero
        now = int(time.time())
        deltas = [0.0001] * 200
        timestamps = [now - (200 - i) * 60 for i in range(200)]
        result = _is_converged(deltas, timestamps, 74)
        assert result is True


# ---------------------------------------------------------------------------
# TestDiurnalLookback (CALI-04)
# ---------------------------------------------------------------------------

class TestDiurnalLookback:
    """Tests for 24h diurnal pattern processing."""

    def test_processes_full_24h_without_error(self) -> None:
        """Test 18: Strategy processes full 24h of 1m data (1440 timestamps)."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            calibrate_target_bloat,
        )

        # Generate 1440 timestamps (full 24h at 1m intervals)
        now = int(time.time())
        metrics: list[dict] = []
        random.seed(42)
        for i in range(1440):
            ts = now - (1440 - i) * 60
            # Simulated diurnal pattern: lower deltas at night, higher during day
            hour = (i // 60) % 24
            base = 8.0 + (4.0 if 8 <= hour <= 22 else 0.0)
            delta = base + random.gauss(0, 2.0)

            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_rtt_delta_ms", "value": delta,
                "labels": None, "granularity": "1m",
            })
            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_state", "value": 0.0,
                "labels": None, "granularity": "1m",
            })

        result = calibrate_target_bloat(metrics, 15.0, DEFAULT_BOUNDS, "Spectrum")
        # Should return a result (diurnal data has high variance -> not converged)
        assert result is not None
        assert result.data_points == 1440
        # Full day of GREEN -> confidence = 1440/1440 = 1.0
        assert result.confidence == pytest.approx(1.0, abs=0.001)

    def test_extract_green_deltas_handles_1440_rows(self) -> None:
        """Test 19: _extract_green_deltas handles 1440-row datasets efficiently."""
        from wanctl.tuning.strategies.congestion_thresholds import (
            _extract_green_deltas,
        )

        now = int(time.time())
        metrics: list[dict] = []
        for i in range(1440):
            ts = now - (1440 - i) * 60
            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_rtt_delta_ms", "value": 10.0 + (i * 0.01),
                "labels": None, "granularity": "1m",
            })
            metrics.append({
                "timestamp": ts, "wan_name": "Spectrum",
                "metric_name": "wanctl_state", "value": 0.0,
                "labels": None, "granularity": "1m",
            })

        result = _extract_green_deltas(metrics)
        assert len(result) == 1440

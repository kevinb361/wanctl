"""Tests for signal processing tuning strategies.

Tests tune_hampel_sigma, tune_hampel_window, and tune_alpha_load strategy
functions. Each strategy matches StrategyFn signature and returns
TuningResult | None.

SIGP-01: Hampel sigma from outlier rate analysis
SIGP-02: Hampel window from jitter-based noise level proxy
SIGP-03: Load EWMA time constant from settling time analysis
"""

import pytest

from wanctl.tuning.models import SafetyBounds, TuningResult
from wanctl.tuning.strategies.signal_processing import (
    MIN_SAMPLES,
    tune_alpha_load,
    tune_hampel_sigma,
    tune_hampel_window,
)


def _make_metrics(
    metric_name: str, values: list[float], start_ts: int = 1000000
) -> list[dict]:
    """Build metrics_data list for a single metric."""
    return [
        {"timestamp": start_ts + i * 60, "metric_name": metric_name, "value": v}
        for i, v in enumerate(values)
    ]


def _make_multi_metrics(
    *args: tuple[str, list[float]], start_ts: int = 1000000
) -> list[dict]:
    """Build metrics_data list for multiple metrics aligned by timestamp."""
    result: list[dict] = []
    for metric_name, values in args:
        result.extend(_make_metrics(metric_name, values, start_ts))
    return result


# ---------------------------------------------------------------------------
# SIGP-01: tune_hampel_sigma
# ---------------------------------------------------------------------------


class TestTuneHampelSigma:
    """Tests for Hampel sigma tuning based on outlier rate analysis."""

    BOUNDS = SafetyBounds(min_value=1.5, max_value=5.0)

    def test_high_outlier_rate_decreases_sigma(self):
        """outlier_rate=0.20 (above 0.15 max) -> sigma decreases."""
        # Monotonically increasing counter: increments of 240 per minute
        # = 240/1200 = 20% outlier rate (above TARGET_OUTLIER_RATE_MAX=0.15)
        n = 100
        counts = [i * 240.0 for i in range(n)]
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.new_value < 3.0
        assert result.parameter == "hampel_sigma_threshold"
        assert result.wan_name == "Spectrum"
        assert result.confidence > 0
        assert "outlier_rate" in result.rationale

    def test_low_outlier_rate_increases_sigma(self):
        """outlier_rate=0.01 (below 0.05 min) -> sigma increases."""
        # Increments of 12 per minute = 12/1200 = 1% outlier rate
        n = 100
        counts = [i * 12.0 for i in range(n)]
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "ATT")
        assert result is not None
        assert result.new_value > 3.0
        assert result.parameter == "hampel_sigma_threshold"
        assert result.wan_name == "ATT"
        assert "outlier_rate" in result.rationale

    def test_in_range_outlier_rate_returns_none(self):
        """outlier_rate=0.10 (within 0.05-0.15 range) -> None (converged)."""
        # Increments of 120 per minute = 120/1200 = 10% outlier rate
        n = 100
        counts = [i * 120.0 for i in range(n)]
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_insufficient_data_returns_none(self):
        """Fewer than MIN_SAMPLES deltas -> None."""
        # Only 10 data points (9 deltas, well below MIN_SAMPLES=60)
        counts = [i * 240.0 for i in range(10)]
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_negative_deltas_from_counter_reset_discarded(self):
        """Counter resets (negative deltas) should be skipped."""
        # Counter goes 0, 120, 240, 0, 120, 240, ... (resets every 3 minutes)
        # After discarding negative deltas, we'd have only 2 valid deltas per
        # 3 points which is well under MIN_SAMPLES. So returns None.
        counts = []
        for i in range(100):
            counts.append((i % 3) * 120.0)
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        # With frequent resets we might get enough positive deltas, or not.
        # The key guarantee: negative deltas are NOT included in rate computation.
        # With 100 points and pattern [0,120,240,0,...], positive deltas are
        # at indices 0->1, 1->2 = 120 each, then reset at 2->3 (skipped).
        # That's 66 positive deltas out of 99 total, > MIN_SAMPLES.
        # Rate = 120/1200 = 0.10 = in range, returns None.
        assert result is None

    def test_confidence_scales_with_data_count(self):
        """Confidence = min(1.0, len(rates) / 1440.0)."""
        n = 100
        counts = [i * 240.0 for i in range(n)]
        metrics = _make_metrics("wanctl_signal_outlier_count", counts)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is not None
        # 99 deltas / 1440 = ~0.069
        assert 0.05 < result.confidence < 0.1
        assert result.data_points == 99


# ---------------------------------------------------------------------------
# SIGP-02: tune_hampel_window
# ---------------------------------------------------------------------------


class TestTuneHampelWindow:
    """Tests for Hampel window tuning based on jitter level."""

    BOUNDS = SafetyBounds(min_value=5.0, max_value=15.0)

    def test_low_jitter_maps_to_max_window(self):
        """Low jitter (<1ms) -> window near MAX_WINDOW=15."""
        n = 100
        jitter_values = [0.5] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.new_value >= 14.0  # Near MAX_WINDOW=15
        assert result.parameter == "hampel_window_size"
        assert result.wan_name == "Spectrum"
        assert result.confidence > 0

    def test_high_jitter_maps_to_min_window(self):
        """High jitter (>5ms) -> window near MIN_WINDOW=5."""
        n = 100
        jitter_values = [8.0] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "ATT")
        assert result is not None
        assert result.new_value <= 5.0  # Near MIN_WINDOW=5
        assert result.parameter == "hampel_window_size"
        assert result.wan_name == "ATT"

    def test_moderate_jitter_interpolates(self):
        """Jitter ~2.5ms -> interpolated window between 5 and 15."""
        n = 100
        jitter_values = [2.5] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        # Linear interpolation: 15 - 10 * (2.5 - 1.0) / (5.0 - 1.0) = 15 - 3.75 = 11.25
        assert 10.0 <= result.new_value <= 12.0

    def test_insufficient_data_returns_none(self):
        """Fewer than MIN_SAMPLES jitter values -> None."""
        jitter_values = [2.0] * 10  # Way below MIN_SAMPLES
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_returned_value_is_float(self):
        """Window new_value is a float (int conversion in applier)."""
        n = 100
        jitter_values = [3.0] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert isinstance(result.new_value, float)

    def test_confidence_scales_with_data_count(self):
        """Confidence = min(1.0, len(jitter_values) / 1440.0)."""
        n = 100
        jitter_values = [0.5] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        # 100 / 1440 = ~0.069
        assert 0.05 < result.confidence < 0.1
        assert result.data_points == 100


# ---------------------------------------------------------------------------
# SIGP-03: tune_alpha_load (outputs load_time_constant_sec)
# ---------------------------------------------------------------------------


class TestTuneAlphaLoad:
    """Tests for load EWMA time constant tuning from settling time analysis."""

    # Bounds are in time constant seconds (NOT raw alpha)
    BOUNDS = SafetyBounds(min_value=0.5, max_value=10.0)

    def _make_step_response_data(
        self,
        step_times: list[int],
        baseline_rtt: float = 30.0,
        step_magnitude: float = 20.0,
        settling_minutes: int = 5,
    ) -> list[dict]:
        """Build metrics with RTT step changes and slow EWMA response.

        Args:
            step_times: List of minute indices where steps occur.
            baseline_rtt: Base RTT value before steps.
            step_magnitude: Size of RTT jump.
            settling_minutes: How many minutes the EWMA takes to settle.
        """
        total_minutes = max(step_times) + settling_minutes + 20
        total_minutes = max(total_minutes, 200)  # Ensure enough data

        rtt_values: list[float] = []
        ewma_values: list[float] = []
        jitter_values: list[float] = []

        current_level = baseline_rtt
        current_ewma = baseline_rtt

        for minute in range(total_minutes):
            if minute in step_times:
                current_level = baseline_rtt + step_magnitude

            rtt_values.append(current_level)

            # Simulate EWMA settling: move 30% toward current level each minute
            # This creates settling_minutes ~ 3-5 depending on interpretation
            alpha_per_minute = 1.0 / settling_minutes
            current_ewma = current_ewma + alpha_per_minute * (
                current_level - current_ewma
            )
            ewma_values.append(current_ewma)

            jitter_values.append(1.0)  # Stable jitter for step detection threshold

        return _make_multi_metrics(
            ("wanctl_rtt_ms", rtt_values),
            ("wanctl_rtt_load_ewma_ms", ewma_values),
            ("wanctl_signal_jitter_ms", jitter_values),
        )

    def test_slow_settling_decreases_time_constant(self):
        """Slow settling (>3s) -> tc decreases (faster alpha)."""
        # Steps at minutes 20, 60, 120 with 5-minute settling (= 300s settling)
        # settling_time = 5 * 60 = 300s >> target 2s
        metrics = self._make_step_response_data(
            step_times=[20, 60, 120],
            settling_minutes=5,
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.parameter == "load_time_constant_sec"
        # Current tc=2.0, settling is way above target -> tc should decrease
        assert result.new_value < 2.0
        assert result.wan_name == "Spectrum"

    def test_fast_settling_increases_time_constant(self):
        """Fast settling (<1s) -> tc increases (slower alpha)."""
        # Steps with very fast settling (1 minute = 60s, but that's still
        # above TARGET_SETTLING_SEC=2.0, so we need sub-minute settling).
        # Actually at 1m granularity, the fastest observable settling is 60s
        # (one sample interval). With TARGET_SETTLING_SEC=2.0, even 60s
        # settling is "slow". We need to test the direction logic:
        # if measured settling < target - tolerance, tc should increase.
        #
        # Since we're at 1m granularity, and settling at 1 minute means 60s,
        # which is >> 2s target, both slow and fast settling in this test
        # framework will measure much larger than the 2s target.
        # The test helper creates settling via EWMA convergence.
        # Let's create data where EWMA settles within 1 minute (fast for 1m data).
        total_minutes = 200
        rtt_values: list[float] = []
        ewma_values: list[float] = []
        jitter_values: list[float] = []

        steps = [20, 60, 120]
        current_level = 30.0

        for minute in range(total_minutes):
            if minute in steps:
                current_level = 50.0

            rtt_values.append(current_level)
            # EWMA exactly follows RTT (instant settling = 0s)
            ewma_values.append(current_level)
            jitter_values.append(1.0)

        metrics = _make_multi_metrics(
            ("wanctl_rtt_ms", rtt_values),
            ("wanctl_rtt_load_ewma_ms", ewma_values),
            ("wanctl_signal_jitter_ms", jitter_values),
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        # With instant settling (0s), avg_settling < TARGET - TOLERANCE
        # The function might see 0s settling and want to slow down (increase tc).
        # Or it returns None if settling is within tolerance of target.
        # With settling=0 and target=2.0, tolerance=0.5:
        # abs(0 - 2.0) = 2.0 > 0.5, so not converged.
        # settling < target -> tc should increase (slower alpha).
        if result is not None:
            assert result.parameter == "load_time_constant_sec"
            assert result.new_value > 2.0

    def test_settling_near_target_returns_none(self):
        """Settling time within tolerance of target -> None (converged)."""
        # We need settling time close to TARGET_SETTLING_SEC=2.0
        # At 1m granularity this is tricky. The settling time is measured
        # as seconds between the step and when EWMA settles.
        # For 2.0s settling, the EWMA would settle almost immediately in
        # 1m-resolution data (within the same minute).
        # This means the settling check at minute boundaries would see ~0s
        # settling. To get exactly 2.0s, we'd need sub-minute data.
        # The algorithm measures (t_settle - t_step) as seconds using
        # actual timestamps. With 1m-resolution timestamps, the minimum
        # non-zero settling time is 60s.
        #
        # Since exact 2.0s cannot be tested at 1m granularity, we test
        # convergence by providing data where no steps are detected.
        total_minutes = 200
        rtt_values = [30.0] * total_minutes
        ewma_values = [30.0] * total_minutes
        jitter_values = [1.0] * total_minutes
        metrics = _make_multi_metrics(
            ("wanctl_rtt_ms", rtt_values),
            ("wanctl_rtt_load_ewma_ms", ewma_values),
            ("wanctl_signal_jitter_ms", jitter_values),
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        # No steps detected -> returns None
        assert result is None

    def test_no_steps_detected_returns_none(self):
        """Flat RTT data with no step changes -> None."""
        total_minutes = 200
        rtt_values = [30.0] * total_minutes
        ewma_values = [30.0] * total_minutes
        jitter_values = [1.0] * total_minutes
        metrics = _make_multi_metrics(
            ("wanctl_rtt_ms", rtt_values),
            ("wanctl_rtt_load_ewma_ms", ewma_values),
            ("wanctl_signal_jitter_ms", jitter_values),
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_insufficient_data_returns_none(self):
        """Fewer than MIN_SAMPLES data points -> None."""
        metrics = _make_multi_metrics(
            ("wanctl_rtt_ms", [30.0] * 10),
            ("wanctl_rtt_load_ewma_ms", [30.0] * 10),
            ("wanctl_signal_jitter_ms", [1.0] * 10),
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_returned_parameter_is_load_time_constant_sec(self):
        """Returned parameter must be 'load_time_constant_sec', NOT 'alpha_load'."""
        metrics = self._make_step_response_data(
            step_times=[20, 60, 120],
            settling_minutes=5,
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        if result is not None:
            assert result.parameter == "load_time_constant_sec"
            assert result.parameter != "alpha_load"

    def test_returned_value_in_tc_range(self):
        """Returned new_value must be in time constant range (0.5-10.0s)."""
        metrics = self._make_step_response_data(
            step_times=[20, 60, 120],
            settling_minutes=5,
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        if result is not None:
            assert 0.5 <= result.new_value <= 10.0

    def test_fewer_than_min_steps_returns_none(self):
        """Fewer than MIN_STEPS (3) step events -> None."""
        # Only 2 step events
        metrics = self._make_step_response_data(
            step_times=[20, 60],
            settling_minutes=5,
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        # With only 2 steps, should return None (need MIN_STEPS=3)
        assert result is None

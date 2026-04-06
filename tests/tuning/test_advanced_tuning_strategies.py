"""Tests for advanced tuning strategies.

Tests tune_fusion_weight, tune_reflector_min_score, tune_baseline_bounds_min,
and tune_baseline_bounds_max strategy functions. Each strategy matches
StrategyFn signature and returns TuningResult | None.

ADVT-01: Fusion ICMP/IRTT weight from per-signal reliability scoring
ADVT-02: Reflector min_score from signal confidence proxy
ADVT-03: Baseline RTT bounds from p5/p95 baseline history
"""

from wanctl.tuning.models import SafetyBounds, TuningResult
from wanctl.tuning.strategies.advanced import (
    tune_baseline_bounds_max,
    tune_baseline_bounds_min,
    tune_fusion_weight,
    tune_reflector_min_score,
)


def _make_metrics(metric_name: str, values: list[float], start_ts: int = 1000000) -> list[dict]:
    """Build metrics_data list for a single metric."""
    return [
        {"timestamp": start_ts + i * 60, "metric_name": metric_name, "value": v}
        for i, v in enumerate(values)
    ]


def _make_multi_metrics(*args: tuple[str, list[float]], start_ts: int = 1000000) -> list[dict]:
    """Build metrics_data list for multiple metrics aligned by timestamp."""
    result: list[dict] = []
    for metric_name, values in args:
        result.extend(_make_metrics(metric_name, values, start_ts))
    return result


# ---------------------------------------------------------------------------
# ADVT-01: tune_fusion_weight
# ---------------------------------------------------------------------------


class TestTuneFusionWeight:
    """Tests for fusion ICMP weight tuning from per-signal reliability."""

    BOUNDS = SafetyBounds(min_value=0.3, max_value=0.95)

    def test_returns_none_insufficient_icmp_variance(self):
        """<60 wanctl_signal_variance_ms2 samples -> returns None."""
        metrics = _make_multi_metrics(
            ("wanctl_signal_variance_ms2", [1.0] * 30),
            ("wanctl_irtt_ipdv_ms", [0.5] * 100),
        )
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is None

    def test_returns_none_no_irtt_data(self):
        """ICMP variance present but zero IRTT jitter samples -> None."""
        metrics = _make_metrics("wanctl_signal_variance_ms2", [1.0] * 100)
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is None

    def test_returns_result_with_both_signals(self):
        """100+ ICMP variance + 100+ IRTT jitter/loss -> TuningResult."""
        n = 100
        metrics = _make_multi_metrics(
            ("wanctl_signal_variance_ms2", [1.0] * n),
            ("wanctl_irtt_ipdv_ms", [0.5] * n),
            ("wanctl_irtt_loss_up_pct", [1.0] * n),
            ("wanctl_irtt_loss_down_pct", [1.0] * n),
        )
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        assert isinstance(result, TuningResult)
        assert result.parameter == "fusion_icmp_weight"

    def test_higher_icmp_reliability_increases_weight(self):
        """Low ICMP variance + high IRTT jitter/loss -> icmp_weight increases."""
        n = 100
        metrics = _make_multi_metrics(
            ("wanctl_signal_variance_ms2", [0.1] * n),  # Very low variance = very reliable
            ("wanctl_irtt_ipdv_ms", [8.0] * n),  # Very high jitter = unreliable
            ("wanctl_irtt_loss_up_pct", [10.0] * n),  # 10% loss
            ("wanctl_irtt_loss_down_pct", [10.0] * n),
        )
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        # ICMP is more reliable -> weight should increase (favor ICMP more)
        assert result.new_value > 0.7

    def test_higher_irtt_reliability_decreases_weight(self):
        """High ICMP variance + low IRTT jitter/loss -> icmp_weight decreases."""
        n = 100
        metrics = _make_multi_metrics(
            ("wanctl_signal_variance_ms2", [5.0] * n),  # High variance = unreliable
            ("wanctl_irtt_ipdv_ms", [0.5] * n),  # Low jitter = reliable
            ("wanctl_irtt_loss_up_pct", [0.0] * n),  # 0% loss
            ("wanctl_irtt_loss_down_pct", [0.0] * n),
        )
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        # IRTT is more reliable -> weight should decrease (favor IRTT more)
        assert result.new_value < 0.7

    def test_result_fields(self):
        """Verify result field values match expectations."""
        n = 100
        metrics = _make_multi_metrics(
            ("wanctl_signal_variance_ms2", [1.0] * n),
            ("wanctl_irtt_ipdv_ms", [0.5] * n),
            ("wanctl_irtt_loss_up_pct", [1.0] * n),
            ("wanctl_irtt_loss_down_pct", [1.0] * n),
        )
        result = tune_fusion_weight(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.parameter == "fusion_icmp_weight"
        assert result.wan_name == "Spectrum"
        assert result.data_points > 0
        assert result.old_value == 0.7
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# ADVT-02: tune_reflector_min_score
# ---------------------------------------------------------------------------


class TestTuneReflectorMinScore:
    """Tests for reflector min_score tuning from signal confidence proxy."""

    BOUNDS = SafetyBounds(min_value=0.5, max_value=0.95)

    def test_returns_none_insufficient_confidence(self):
        """<60 wanctl_signal_confidence samples -> returns None."""
        metrics = _make_metrics("wanctl_signal_confidence", [0.8] * 30)
        result = tune_reflector_min_score(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is None

    def test_low_confidence_lowers_min_score(self):
        """Mean confidence < 0.5 -> candidate < current (too strict)."""
        n = 100
        metrics = _make_metrics("wanctl_signal_confidence", [0.3] * n)
        result = tune_reflector_min_score(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.new_value < 0.7

    def test_high_confidence_raises_min_score(self):
        """Mean confidence > 0.9 -> candidate > current (too lenient)."""
        n = 100
        metrics = _make_metrics("wanctl_signal_confidence", [0.95] * n)
        result = tune_reflector_min_score(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.new_value > 0.7

    def test_moderate_confidence_returns_none(self):
        """Mean confidence 0.6-0.8 -> returns None (converged)."""
        n = 100
        metrics = _make_metrics("wanctl_signal_confidence", [0.7] * n)
        result = tune_reflector_min_score(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is None

    def test_result_fields(self):
        """Verify result field values."""
        n = 100
        metrics = _make_metrics("wanctl_signal_confidence", [0.3] * n)
        result = tune_reflector_min_score(metrics, 0.7, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.parameter == "reflector_min_score"
        assert "confidence" in result.rationale
        assert result.wan_name == "Spectrum"
        assert result.data_points > 0


# ---------------------------------------------------------------------------
# ADVT-03: tune_baseline_bounds_min
# ---------------------------------------------------------------------------


class TestTuneBaselineBoundsMin:
    """Tests for baseline RTT min bound tuning from p5 of baseline history."""

    BOUNDS = SafetyBounds(min_value=1.0, max_value=30.0)

    def test_returns_none_insufficient_baseline(self):
        """<60 wanctl_rtt_baseline_ms samples -> returns None."""
        metrics = _make_metrics("wanctl_rtt_baseline_ms", [20.0] * 30)
        result = tune_baseline_bounds_min(metrics, 10.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_candidate_is_p5_with_margin(self):
        """200 baseline samples -> candidate = p5 * 0.9."""
        import random

        random.seed(42)
        n = 200
        # Generate values clustered around 20ms with some spread
        values = [20.0 + random.gauss(0, 2.0) for _ in range(n)]
        metrics = _make_metrics("wanctl_rtt_baseline_ms", values)
        result = tune_baseline_bounds_min(metrics, 10.0, self.BOUNDS, "Spectrum")
        assert result is not None

        # Compute expected p5
        from statistics import quantiles

        percentiles = quantiles(values, n=100)
        expected_p5 = percentiles[4]
        expected_candidate = round(expected_p5 * 0.9, 1)
        assert result.new_value == expected_candidate

    def test_floor_at_hard_minimum(self):
        """p5 * 0.9 very low -> candidate floors at bounds min (1.0ms)."""
        n = 200
        # Very low baseline values: p5 * 0.9 would be < 1.0
        values = [0.8 + i * 0.01 for i in range(n)]
        metrics = _make_metrics("wanctl_rtt_baseline_ms", values)
        result = tune_baseline_bounds_min(metrics, 2.0, self.BOUNDS, "Spectrum")
        assert result is not None
        # p5 of these values is near 0.9, * 0.9 = ~0.81, floored to 1.0
        assert result.new_value >= 1.0

    def test_result_fields(self):
        """Verify result field values."""
        n = 200
        values = [20.0] * n
        metrics = _make_metrics("wanctl_rtt_baseline_ms", values)
        result = tune_baseline_bounds_min(metrics, 10.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.parameter == "baseline_rtt_min"
        assert result.wan_name == "Spectrum"
        assert result.data_points == n


# ---------------------------------------------------------------------------
# ADVT-03: tune_baseline_bounds_max
# ---------------------------------------------------------------------------


class TestTuneBaselineBoundsMax:
    """Tests for baseline RTT max bound tuning from p95 of baseline history."""

    BOUNDS = SafetyBounds(min_value=30.0, max_value=200.0)

    def test_returns_none_insufficient_baseline(self):
        """<60 wanctl_rtt_baseline_ms samples -> returns None."""
        metrics = _make_metrics("wanctl_rtt_baseline_ms", [20.0] * 30)
        result = tune_baseline_bounds_max(metrics, 100.0, self.BOUNDS, "Spectrum")
        assert result is None

    def test_candidate_is_p95_with_margin(self):
        """200 baseline samples -> candidate = p95 * 1.1."""
        import random

        random.seed(42)
        n = 200
        values = [40.0 + random.gauss(0, 5.0) for _ in range(n)]
        metrics = _make_metrics("wanctl_rtt_baseline_ms", values)
        result = tune_baseline_bounds_max(metrics, 100.0, self.BOUNDS, "Spectrum")
        assert result is not None

        # Compute expected p95
        from statistics import quantiles

        percentiles = quantiles(values, n=100)
        expected_p95 = percentiles[94]
        expected_candidate = round(expected_p95 * 1.1, 1)
        assert result.new_value == expected_candidate

    def test_result_fields(self):
        """Verify result field values."""
        n = 200
        values = [50.0] * n
        metrics = _make_metrics("wanctl_rtt_baseline_ms", values)
        result = tune_baseline_bounds_max(metrics, 100.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.parameter == "baseline_rtt_max"
        assert result.wan_name == "Spectrum"
        assert result.data_points == n

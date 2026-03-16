"""Tests for SignalProcessor and SignalResult in signal_processing module.

Covers all SIGP-01 through SIGP-05 behaviors:
- Hampel outlier filter (detect, replace, MAD=0 guard, warm-up)
- Jitter EWMA from consecutive raw RTT deltas
- Variance EWMA of raw RTT deviation from load_rtt
- Confidence score: 1/(1 + variance/baseline^2)
- Stdlib-only imports (no numpy, scipy, pandas)
"""

import dataclasses
import inspect
import logging
import statistics

import pytest

from wanctl.signal_processing import SignalProcessor, SignalResult

# =============================================================================
# CONSTANTS
# =============================================================================

CYCLE_INTERVAL = 0.05  # 50ms
DEFAULT_WINDOW_SIZE = 7
DEFAULT_SIGMA = 3.0
DEFAULT_JITTER_TC = 2.0  # -> alpha = 0.05/2.0 = 0.025
DEFAULT_VARIANCE_TC = 5.0  # -> alpha = 0.05/5.0 = 0.01

# Hampel filter MAD scale factor for Gaussian consistency
# 1 / Phi^-1(3/4) = 1.4826
MAD_SCALE_FACTOR = 1.4826


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def processor():
    """Create a default SignalProcessor for testing."""
    return SignalProcessor(
        wan_name="TestWAN",
        config={
            "hampel_window_size": DEFAULT_WINDOW_SIZE,
            "hampel_sigma_threshold": DEFAULT_SIGMA,
            "jitter_time_constant_sec": DEFAULT_JITTER_TC,
            "variance_time_constant_sec": DEFAULT_VARIANCE_TC,
        },
        logger=logging.getLogger("test"),
    )


def _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0, load_rtt=25.0, baseline_rtt=25.0):
    """Feed count samples through the processor to fill/warm up the window."""
    results = []
    for _ in range(count):
        results.append(processor.process(raw_rtt=rtt, load_rtt=load_rtt, baseline_rtt=baseline_rtt))
    return results


# =============================================================================
# TestSignalResult
# =============================================================================


class TestSignalResult:
    """Tests for SignalResult frozen dataclass structure."""

    def test_frozen_dataclass(self):
        """SignalResult is frozen -- assignment raises AttributeError."""
        result = SignalResult(
            filtered_rtt=25.0,
            raw_rtt=25.0,
            jitter_ms=0.0,
            variance_ms2=0.0,
            confidence=1.0,
            is_outlier=False,
            outlier_rate=0.0,
            total_outliers=0,
            consecutive_outliers=0,
            warming_up=False,
        )
        with pytest.raises(AttributeError):
            result.filtered_rtt = 30.0  # type: ignore[misc]

    def test_slots_present(self):
        """SignalResult uses __slots__ for memory efficiency."""
        assert hasattr(SignalResult, "__slots__")

    def test_all_fields_present(self):
        """SignalResult has exactly the 10 required fields."""
        field_names = {f.name for f in dataclasses.fields(SignalResult)}
        expected = {
            "filtered_rtt",
            "raw_rtt",
            "jitter_ms",
            "variance_ms2",
            "confidence",
            "is_outlier",
            "outlier_rate",
            "total_outliers",
            "consecutive_outliers",
            "warming_up",
        }
        assert field_names == expected


# =============================================================================
# TestHampelFilter
# =============================================================================


class TestHampelFilter:
    """Tests for Hampel outlier detection and replacement (SIGP-01)."""

    def test_outlier_detected_and_replaced(self, processor):
        """Large RTT spike detected as outlier and replaced with window median."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.is_outlier is True
        assert result.filtered_rtt == pytest.approx(25.0, abs=0.1)
        assert result.raw_rtt == 100.0

    def test_non_outlier_passes_through(self, processor):
        """RTT within normal range passes through unfiltered."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        result = processor.process(raw_rtt=25.5, load_rtt=25.0, baseline_rtt=25.0)
        assert result.is_outlier is False
        assert result.filtered_rtt == 25.5

    def test_constant_window_mad_zero(self, processor):
        """When all window values are identical, MAD=0 skips outlier detection."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=30.0)
        result = processor.process(raw_rtt=31.0, load_rtt=30.0, baseline_rtt=30.0)
        assert result.is_outlier is False
        assert result.filtered_rtt == 31.0

    def test_outlier_replacement_value_is_median(self, processor):
        """When outlier detected, filtered_rtt equals the median of the window."""
        # Build a window with known values
        values = [24.0, 25.0, 25.0, 25.0, 25.0, 26.0, 25.0]
        for v in values:
            processor.process(raw_rtt=v, load_rtt=25.0, baseline_rtt=25.0)

        expected_median = statistics.median(values)
        result = processor.process(raw_rtt=200.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.is_outlier is True
        assert result.filtered_rtt == pytest.approx(expected_median, abs=0.01)


# =============================================================================
# TestWarmUp
# =============================================================================


class TestWarmUp:
    """Tests for warm-up period behavior (SIGP-01 warm-up)."""

    def test_warming_up_true_until_window_full(self, processor):
        """warming_up=True for first window_size-1 calls."""
        for i in range(DEFAULT_WINDOW_SIZE - 1):
            result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
            assert result.warming_up is True, f"Call {i+1} should be warming up"

    def test_warming_up_false_after_window_full(self, processor):
        """warming_up=False once window has window_size samples."""
        for _ in range(DEFAULT_WINDOW_SIZE - 1):
            processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.warming_up is False

    def test_raw_rtt_passed_through_during_warmup(self, processor):
        """During warm-up, filtered_rtt == raw_rtt (no Hampel replacement)."""
        for rtt in [23.0, 24.0, 25.0, 100.0, 26.0, 27.0]:
            result = processor.process(raw_rtt=rtt, load_rtt=25.0, baseline_rtt=25.0)
            assert result.filtered_rtt == rtt

    def test_no_outlier_during_warmup(self, processor):
        """During warm-up, is_outlier=False always (no detection possible)."""
        for rtt in [25.0, 100.0, 200.0, 25.0, 25.0, 25.0]:
            result = processor.process(raw_rtt=rtt, load_rtt=25.0, baseline_rtt=25.0)
            assert result.is_outlier is False


# =============================================================================
# TestJitter
# =============================================================================


class TestJitter:
    """Tests for jitter EWMA tracking (SIGP-02)."""

    def test_first_cycle_zero(self, processor):
        """First process() call returns jitter_ms=0.0 (no previous RTT)."""
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.jitter_ms == 0.0

    def test_second_cycle_initializes_from_delta(self, processor):
        """Second call initializes jitter from |raw_rtt - previous_raw_rtt|."""
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        result = processor.process(raw_rtt=26.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.jitter_ms == pytest.approx(1.0, abs=0.01)

    def test_ewma_smoothing(self, processor):
        """After initialization, jitter EWMA converges toward new delta values."""
        # Build up jitter with stable 1.0ms delta
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        processor.process(raw_rtt=26.0, load_rtt=25.0, baseline_rtt=25.0)

        # Now send a large delta -- EWMA should not jump immediately
        result = processor.process(raw_rtt=36.0, load_rtt=25.0, baseline_rtt=25.0)
        # alpha=0.025, previous=1.0, new_delta=|36-26|=10.0
        # ewma = 0.975 * 1.0 + 0.025 * 10.0 = 0.975 + 0.25 = 1.225
        assert result.jitter_ms == pytest.approx(1.225, abs=0.01)

    def test_uses_raw_rtt_not_filtered(self, processor):
        """Jitter is computed from raw RTT, not filtered RTT."""
        # Fill window with stable values
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # Previous raw_rtt was 25.0; send an outlier at 100.0
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Jitter should reflect |100.0 - 25.0| = 75.0 delta (raw), not small delta
        assert result.jitter_ms > 1.0  # Would be tiny if using filtered


# =============================================================================
# TestVariance
# =============================================================================


class TestVariance:
    """Tests for variance EWMA tracking (SIGP-04)."""

    def test_first_call_initializes(self, processor):
        """First call initializes variance to (raw_rtt - load_rtt)^2."""
        result = processor.process(raw_rtt=26.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.variance_ms2 == pytest.approx(1.0, abs=0.01)

    def test_ewma_tracks_deviation(self, processor):
        """Variance EWMA converges toward new squared deviations."""
        # First call: variance = (26-25)^2 = 1.0
        processor.process(raw_rtt=26.0, load_rtt=25.0, baseline_rtt=25.0)
        # Second call: new dev = (30-25)^2 = 25.0
        # EWMA: (1-0.01)*1.0 + 0.01*25.0 = 0.99 + 0.25 = 1.24
        result = processor.process(raw_rtt=30.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.variance_ms2 == pytest.approx(1.24, abs=0.01)

    def test_uses_raw_rtt(self, processor):
        """Variance computed from raw_rtt deviation, not filtered_rtt."""
        # Fill window, then send outlier
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # Outlier: raw=100, filtered=25 (median). Variance uses raw.
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # (100-25)^2 = 5625 -- should be large, not near 0
        assert result.variance_ms2 > 100.0


# =============================================================================
# TestConfidence
# =============================================================================


class TestConfidence:
    """Tests for confidence scoring (SIGP-03)."""

    def test_stable_high_confidence(self, processor):
        """Zero variance and positive baseline -> confidence=1.0."""
        # All RTT exactly at load_rtt -> variance stays 0 after init
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        # First call with zero deviation: variance = (25-25)^2 = 0.0
        # But variance EWMA initialized to 0, so it stays 0
        # confidence = 1/(1 + 0/625) = 1.0
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_moderate_variance(self, processor):
        """variance=625, baseline=25 -> confidence=0.5."""
        # We need to manually verify the formula since variance EWMA builds up
        # confidence = 1/(1 + 625/625) = 1/(1+1) = 0.5
        # This tests the internal formula, so we set up conditions to get known variance
        # Feed enough data points to reach target variance
        # Direct formula test: use process to get a known variance, then check confidence
        # Simpler: just feed one sample with large deviation to init variance
        # raw=50, load=25, deviation=(50-25)^2=625
        result = processor.process(raw_rtt=50.0, load_rtt=25.0, baseline_rtt=25.0)
        # First sample: variance initializes to 625.0
        # confidence = 1/(1 + 625/25^2) = 1/(1+1) = 0.5
        assert result.confidence == pytest.approx(0.5, abs=0.01)

    def test_high_variance_low_confidence(self, processor):
        """High variance relative to baseline -> low confidence."""
        # raw=100, load=25, deviation=(100-25)^2=5625
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # variance = 5625, confidence = 1/(1 + 5625/625) = 1/(1+9) = 0.1
        assert result.confidence == pytest.approx(0.1, abs=0.01)

    def test_zero_baseline_returns_one(self, processor):
        """Zero baseline -> confidence=1.0 (guard against division by zero)."""
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=0.0)
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_negative_baseline_returns_one(self, processor):
        """Negative baseline -> confidence=1.0 (guard)."""
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=-5.0)
        assert result.confidence == pytest.approx(1.0, abs=0.01)


# =============================================================================
# TestOutlierRate
# =============================================================================


class TestOutlierRate:
    """Tests for outlier rate, lifetime count, and consecutive streak tracking (SIGP-01)."""

    def test_no_outliers_rate_zero(self, processor):
        """Normal values produce outlier_rate=0.0."""
        results = _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # After window is full, send one more normal value
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.outlier_rate == pytest.approx(0.0, abs=0.01)

    def test_outlier_increments_rate(self, processor):
        """After one outlier, outlier_rate reflects 1/window_size."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Window has 7 non-outlier + 1 outlier = 8 entries, but outlier_window is
        # also maxlen=7, so it holds the last 7+1=8? No, maxlen=7 means last 7.
        # After warm-up (7 non-outlier entries in outlier_window), appending outlier
        # pushes out the oldest -> window has 6 non-outlier + 1 outlier = 7
        expected_rate = 1.0 / DEFAULT_WINDOW_SIZE
        assert result.outlier_rate == pytest.approx(expected_rate, abs=0.01)

    def test_rate_decays_as_window_moves(self, processor):
        """After outlier, continued normal values push outlier out of window."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # One outlier
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Send window_size-1 more normal values to push outlier out of window
        for _ in range(DEFAULT_WINDOW_SIZE - 1):
            result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.outlier_rate == pytest.approx(0.0, abs=0.01)

    def test_total_outliers_lifetime_count(self, processor):
        """total_outliers counts all outliers ever detected (monotonically increasing)."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # Send 3 outliers interspersed with normal values
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 1
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)   # normal
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 2
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)   # normal
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 3
        assert result.total_outliers == 3

    def test_total_outliers_zero_when_no_outliers(self, processor):
        """No outliers detected -> total_outliers remains 0."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.total_outliers == 0

    def test_consecutive_outliers_streak(self, processor):
        """Consecutive outliers increment the streak counter."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=1
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=2
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=3
        assert result.consecutive_outliers == 3

    def test_consecutive_outliers_resets_on_normal(self, processor):
        """Streak resets to 0 when a non-outlier is received."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=1
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=2
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)  # reset
        assert result.consecutive_outliers == 0

    def test_consecutive_outliers_zero_during_warmup(self, processor):
        """During warm-up, consecutive_outliers is always 0."""
        for rtt in [25.0, 100.0, 200.0, 25.0, 25.0, 25.0]:
            result = processor.process(raw_rtt=rtt, load_rtt=25.0, baseline_rtt=25.0)
            assert result.consecutive_outliers == 0


# =============================================================================
# TestStdlibOnly
# =============================================================================


class TestStdlibOnly:
    """Tests for stdlib-only constraint (SIGP-05)."""

    def test_no_third_party_imports(self):
        """signal_processing.py uses only stdlib imports."""
        source = inspect.getsource(SignalProcessor)
        # Also check module-level source
        import wanctl.signal_processing as mod

        module_source = inspect.getsource(mod)

        forbidden = ["numpy", "scipy", "pandas", "icmplib", "requests", "httpx"]
        for pkg in forbidden:
            assert pkg not in module_source, f"Found forbidden import: {pkg}"

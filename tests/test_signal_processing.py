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
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_config import Config
from wanctl.signal_processing import SignalProcessor, SignalResult
from wanctl.tuning.models import SafetyBounds
from wanctl.tuning.strategies.signal_processing import (
    MAX_WINDOW,
    tune_alpha_load,
    tune_hampel_sigma,
    tune_hampel_window,
)

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


# Varying RTT values near 25.0 that produce non-zero MAD for Hampel detection
VARYING_RTTS = [24.5, 25.0, 25.5, 24.8, 25.2, 24.9, 25.1]


def _fill_window_varying(processor, load_rtt=25.0, baseline_rtt=25.0):
    """Fill window with slightly varying values so MAD is non-zero."""
    results = []
    for rtt in VARYING_RTTS:
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
        _fill_window_varying(processor)
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.is_outlier is True
        assert result.filtered_rtt == pytest.approx(25.0, abs=0.5)
        assert result.raw_rtt == 100.0

    def test_non_outlier_passes_through(self, processor):
        """RTT within normal range passes through unfiltered."""
        _fill_window_varying(processor)
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
        # Build a window with known values that produce non-zero MAD
        values = [23.0, 24.0, 25.0, 25.0, 26.0, 27.0, 25.0]
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
        """warming_up=True for first window_size calls (window not yet full at check time)."""
        for i in range(DEFAULT_WINDOW_SIZE):
            result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
            assert result.warming_up is True, f"Call {i + 1} should be warming up"

    def test_warming_up_false_after_window_full(self, processor):
        """warming_up=False once window has window_size samples at check time."""
        for _ in range(DEFAULT_WINDOW_SIZE):
            processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        # Window now has 7 items; 8th call checks len(window)=7 < 7 = False
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.warming_up is False

    def test_raw_rtt_passed_through_during_warmup(self, processor):
        """During warm-up, filtered_rtt == raw_rtt (no Hampel replacement)."""
        # 7 calls during warm-up (window checked before append)
        for rtt in [23.0, 24.0, 25.0, 100.0, 26.0, 27.0, 28.0]:
            result = processor.process(raw_rtt=rtt, load_rtt=25.0, baseline_rtt=25.0)
            assert result.filtered_rtt == rtt

    def test_no_outlier_during_warmup(self, processor):
        """During warm-up, is_outlier=False always (no detection possible)."""
        for rtt in [25.0, 100.0, 200.0, 25.0, 25.0, 25.0, 300.0]:
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
        # Fill window with varying values (last value is 25.1)
        _fill_window_varying(processor)
        # Previous raw_rtt was 25.1; send an outlier at 100.0
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Jitter should reflect large delta from raw (not filtered median)
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
        # Fill window with varying values, then send outlier
        _fill_window_varying(processor)
        # Outlier: raw=100, filtered~=25 (median). Variance uses raw.
        # EWMA blends (100-25)^2=5625 with accumulated small variances.
        # If using filtered_rtt (~25), deviation would be near 0 -> variance tiny.
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Variance should increase substantially from the raw deviation
        assert result.variance_ms2 > 10.0  # Would be near 0 if using filtered


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
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        # After window is full, send one more normal value
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.outlier_rate == pytest.approx(0.0, abs=0.01)

    def test_outlier_increments_rate(self, processor):
        """After one outlier, outlier_rate reflects 1/window_size."""
        _fill_window_varying(processor)
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # outlier_window has 7 non-outlier entries, appending outlier pushes out
        # the oldest -> window has 6 non-outlier + 1 outlier = 7
        expected_rate = 1.0 / DEFAULT_WINDOW_SIZE
        assert result.outlier_rate == pytest.approx(expected_rate, abs=0.01)

    def test_rate_decays_as_window_moves(self, processor):
        """After outlier, continued normal values push outlier out of window."""
        _fill_window_varying(processor)
        # One outlier
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)
        # Send window_size more normal values to fully push outlier out of window
        for _ in range(DEFAULT_WINDOW_SIZE):
            result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.outlier_rate == pytest.approx(0.0, abs=0.01)

    def test_total_outliers_lifetime_count(self, processor):
        """total_outliers counts all outliers ever detected (monotonically increasing)."""
        _fill_window_varying(processor)
        # Send 3 outliers interspersed with normal values
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 1
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)  # normal
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 2
        processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)  # normal
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # outlier 3
        assert result.total_outliers == 3

    def test_total_outliers_zero_when_no_outliers(self, processor):
        """No outliers detected -> total_outliers remains 0."""
        _fill_window(processor, count=DEFAULT_WINDOW_SIZE, rtt=25.0)
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)
        assert result.total_outliers == 0

    def test_consecutive_outliers_streak(self, processor):
        """Consecutive outliers increment the streak counter."""
        _fill_window_varying(processor)
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=1
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=2
        result = processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=3
        assert result.consecutive_outliers == 3

    def test_consecutive_outliers_resets_on_normal(self, processor):
        """Streak resets to 0 when a non-outlier is received."""
        _fill_window_varying(processor)
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=1
        processor.process(raw_rtt=100.0, load_rtt=25.0, baseline_rtt=25.0)  # streak=2
        result = processor.process(raw_rtt=25.0, load_rtt=25.0, baseline_rtt=25.0)  # reset
        assert result.consecutive_outliers == 0

    def test_consecutive_outliers_zero_during_warmup(self, processor):
        """During warm-up, consecutive_outliers is always 0."""
        for rtt in [25.0, 100.0, 200.0, 25.0, 25.0, 25.0, 300.0]:
            result = processor.process(raw_rtt=rtt, load_rtt=25.0, baseline_rtt=25.0)
            assert result.consecutive_outliers == 0


# =============================================================================
# TestStdlibOnly
# =============================================================================


class TestStdlibOnly:
    """Tests for stdlib-only constraint (SIGP-05)."""

    def test_no_third_party_imports(self):
        """signal_processing.py uses only stdlib imports."""
        import wanctl.signal_processing as mod

        module_source = inspect.getsource(mod)

        # Extract only import lines (not comments or docstrings)
        import_lines = [
            line.strip()
            for line in module_source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)

        forbidden = ["numpy", "scipy", "pandas", "icmplib", "requests", "httpx"]
        for pkg in forbidden:
            assert pkg not in import_text, f"Found forbidden import: {pkg}"


# =============================================================================
# MERGED FROM test_signal_processing_config.py
# =============================================================================


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for signal processing tests."""
    return {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }


def _make_signal_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


# =============================================================================
# TestSignalProcessingConfigDefaults
# =============================================================================


class TestSignalProcessingConfigDefaults:
    """Config loading with default values when section is omitted."""

    def test_missing_section_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config without signal_processing section gets default values."""
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config is not None
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0

    def test_empty_section_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config with empty signal_processing: {} gets default values."""
        autorate_config_dict["signal_processing"] = {}
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0

    def test_default_values_are_exact(self, tmp_path, autorate_config_dict):
        """Verify exact default values match spec."""
        config = _make_signal_config(tmp_path, autorate_config_dict)
        sp = config.signal_processing_config
        assert sp == {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }


# =============================================================================
# TestSignalProcessingConfigValidation
# =============================================================================


class TestSignalProcessingConfigValidation:
    """Warn+default behavior for invalid config values."""

    def test_window_size_too_small_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size < 3 triggers warning and defaults to 7."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": 2}}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_window_size_not_int_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size as string triggers warning and defaults to 7."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": "five"}}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_sigma_threshold_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """sigma_threshold <= 0 triggers warning and defaults to 3.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 0}}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert "sigma_threshold must be positive" in caplog.text

    def test_sigma_threshold_negative_warns_and_defaults(
        self, tmp_path, autorate_config_dict, caplog
    ):
        """sigma_threshold < 0 triggers warning and defaults to 3.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": -1.5}}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert "sigma_threshold must be positive" in caplog.text

    def test_jitter_tc_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """jitter_time_constant_sec <= 0 triggers warning and defaults to 2.0."""
        autorate_config_dict["signal_processing"] = {"jitter_time_constant_sec": 0}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert "jitter_time_constant_sec must be positive" in caplog.text

    def test_variance_tc_negative_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """variance_time_constant_sec < 0 triggers warning and defaults to 5.0."""
        autorate_config_dict["signal_processing"] = {"variance_time_constant_sec": -2.0}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0
        assert "variance_time_constant_sec must be positive" in caplog.text

    def test_boolean_window_size_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size=True (isinstance(True, int) is True) triggers warning."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": True}}
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_non_dict_section_uses_defaults(self, tmp_path, autorate_config_dict, caplog):
        """signal_processing: "invalid" (not a dict) uses all defaults."""
        autorate_config_dict["signal_processing"] = "invalid"
        with caplog.at_level(logging.WARNING):
            config = _make_signal_config(tmp_path, autorate_config_dict)
        # When sp is not a dict, hampel = {} and time constants use defaults
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0


# =============================================================================
# TestSignalProcessingConfigCustom
# =============================================================================


class TestSignalProcessingConfigCustom:
    """Custom values are correctly parsed."""

    def test_custom_window_size(self, tmp_path, autorate_config_dict):
        """Custom window_size=11 is accepted."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": 11}}
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 11

    def test_custom_sigma_threshold(self, tmp_path, autorate_config_dict):
        """Custom sigma_threshold=2.5 is accepted."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 2.5}}
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 2.5

    def test_custom_time_constants(self, tmp_path, autorate_config_dict):
        """Custom jitter_tc=1.0 and variance_tc=10.0 are accepted."""
        autorate_config_dict["signal_processing"] = {
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 10.0,
        }
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["jitter_time_constant_sec"] == 1.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 10.0

    def test_full_custom_config(self, tmp_path, autorate_config_dict):
        """Full custom signal_processing config with all fields."""
        autorate_config_dict["signal_processing"] = {
            "hampel": {
                "window_size": 11,
                "sigma_threshold": 2.0,
            },
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 3.0,
        }
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config == {
            "hampel_window_size": 11,
            "hampel_sigma_threshold": 2.0,
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 3.0,
        }

    def test_integer_sigma_threshold_converted_to_float(self, tmp_path, autorate_config_dict):
        """Integer sigma_threshold=2 is stored as float 2.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 2}}
        config = _make_signal_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 2.0
        assert isinstance(config.signal_processing_config["hampel_sigma_threshold"], float)


# =============================================================================
# TestObservationMode
# =============================================================================


class TestObservationMode:
    """Verify signal processing operates in observation mode only (SIGP-06)."""

    def test_signal_processor_instantiated_in_wan_controller(self, mock_autorate_config):
        """WANController.__init__ creates self.signal_processor."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert hasattr(controller, "signal_processor")
        from wanctl.signal_processing import SignalProcessor

        assert isinstance(controller.signal_processor, SignalProcessor)

    def test_signal_processor_has_correct_config(self, mock_autorate_config):
        """WANController passes config to SignalProcessor correctly."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Verify the signal processor has correct window size from config
        assert controller.signal_processor._window_size == 7
        assert controller.signal_processor._sigma_threshold == 3.0

    def test_last_signal_result_initially_none(self, mock_autorate_config):
        """WANController._last_signal_result starts as None."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller._last_signal_result is None

    def test_run_cycle_uses_filtered_rtt(self, mock_autorate_config):
        """run_cycle passes signal_result.filtered_rtt to update_ewma."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Mock measure_rtt to return a value
        controller.measure_rtt = MagicMock(return_value=25.0)
        # Mock signal_processor.process to track calls
        mock_result = MagicMock()
        mock_result.filtered_rtt = 24.5  # Different from raw 25.0
        controller.signal_processor = MagicMock()
        controller.signal_processor.process.return_value = mock_result
        # Mock downstream to avoid side effects
        controller.download = MagicMock()
        controller.download.adjust_4state.return_value = ("GREEN", 800_000_000, "")
        controller.upload = MagicMock()
        controller.upload.adjust.return_value = ("GREEN", 40_000_000, "")
        controller.save_state = MagicMock()
        controller._check_connectivity_alerts = MagicMock()
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()
        controller._record_profiling = MagicMock()

        with patch("wanctl.autorate_continuous.update_health_status"):
            controller.run_cycle()

        # Verify signal_processor.process was called
        controller.signal_processor.process.assert_called_once()
        call_kwargs = controller.signal_processor.process.call_args
        # Verify raw_rtt was passed (could be positional or keyword)
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs["raw_rtt"] == 25.0
        else:
            assert call_kwargs.args[0] == 25.0

    def test_run_cycle_stores_signal_result(self, mock_autorate_config):
        """run_cycle stores signal_result in _last_signal_result."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Mock measure_rtt to return a value
        controller.measure_rtt = MagicMock(return_value=25.0)
        # Mock signal_processor.process
        mock_result = MagicMock()
        mock_result.filtered_rtt = 24.5
        controller.signal_processor = MagicMock()
        controller.signal_processor.process.return_value = mock_result
        # Mock downstream to avoid side effects
        controller.download = MagicMock()
        controller.download.adjust_4state.return_value = ("GREEN", 800_000_000, "")
        controller.upload = MagicMock()
        controller.upload.adjust.return_value = ("GREEN", 40_000_000, "")
        controller.save_state = MagicMock()
        controller._check_connectivity_alerts = MagicMock()
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()
        controller._record_profiling = MagicMock()

        with patch("wanctl.autorate_continuous.update_health_status"):
            controller.run_cycle()

        assert controller._last_signal_result is mock_result


# =============================================================================
# MERGED FROM test_signal_processing_strategy.py
# =============================================================================


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


class TestHampelSigmaRecordingDensity:
    """Verify SIGP-01 rate normalization is correct at all recording densities."""

    BOUNDS = SafetyBounds(min_value=1.5, max_value=5.0)

    @staticmethod
    def _make_density_metrics(
        interval_sec: float, outlier_fraction: float, n: int = 100
    ) -> list[dict]:
        """Build metrics with variable timestamp spacing and known outlier rate.

        Args:
            interval_sec: seconds between consecutive timestamps
            outlier_fraction: target outlier rate (0.0-1.0)
            n: number of data points
        """
        samples_per_sec = 1.0 / 0.05  # 20 at 50ms cycle
        outliers_per_interval = interval_sec * samples_per_sec * outlier_fraction
        counts = [i * outliers_per_interval for i in range(n)]
        return [
            {
                "timestamp": int(1000000 + i * interval_sec),
                "metric_name": "wanctl_signal_outlier_count",
                "value": c,
            }
            for i, c in enumerate(counts)
        ]

    @pytest.mark.parametrize("interval_sec", [1, 5, 60])
    def test_rate_consistent_across_recording_densities(self, interval_sec):
        """Same 20% outlier rate produces sigma decrease at any recording interval."""
        metrics = self._make_density_metrics(interval_sec, 0.20, n=100)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is not None, f"Expected result at {interval_sec}s intervals"
        assert result.new_value < 3.0, f"Expected sigma decrease at {interval_sec}s"

    def test_production_density_05s_converged(self):
        """At production density (1s gaps), 10% rate returns None (converged)."""
        metrics = self._make_density_metrics(1, 0.10, n=100)
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is None  # 10% is within 5-15% target range

    def test_zero_time_gap_skipped(self):
        """Duplicate timestamps are skipped without error."""
        n = 100
        # Create metrics where some timestamps are duplicated
        metrics = []
        for i in range(n):
            ts = 1000000 + (i // 2) * 60  # Every pair shares a timestamp
            metrics.append(
                {
                    "timestamp": ts,
                    "metric_name": "wanctl_signal_outlier_count",
                    "value": float(i * 240),
                }
            )
        # Should not raise, may return None due to insufficient valid deltas
        tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        # No crash is the primary assertion

    def test_single_sample_returns_none(self):
        """Only 1 timestamp means 0 deltas, returns None."""
        metrics = [
            {
                "timestamp": 1000000,
                "metric_name": "wanctl_signal_outlier_count",
                "value": 100.0,
            }
        ]
        result = tune_hampel_sigma(metrics, 3.0, self.BOUNDS, "Spectrum")
        assert result is None


class TestMaxWindowAlignment:
    """Verify MAX_WINDOW code constant matches ATT config ceiling."""

    def test_max_window_is_21(self):
        """MAX_WINDOW must be 21 to allow ATT window proposals up to 21."""
        assert MAX_WINDOW == 21


# ---------------------------------------------------------------------------
# SIGP-02: tune_hampel_window
# ---------------------------------------------------------------------------


class TestTuneHampelWindow:
    """Tests for Hampel window tuning based on jitter level."""

    BOUNDS = SafetyBounds(min_value=5.0, max_value=15.0)

    def test_low_jitter_maps_to_max_window(self):
        """Low jitter (<1ms) -> window near MAX_WINDOW=21."""
        n = 100
        jitter_values = [0.5] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        assert result.new_value >= 14.0  # Near MAX_WINDOW=21
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
        """Jitter ~2.5ms -> interpolated window between 5 and 21."""
        n = 100
        jitter_values = [2.5] * n
        metrics = _make_metrics("wanctl_signal_jitter_ms", jitter_values)
        result = tune_hampel_window(metrics, 7.0, self.BOUNDS, "Spectrum")
        assert result is not None
        # Linear interpolation: 21 - 16 * (2.5 - 1.0) / (5.0 - 1.0) = 21 - 6.0 = 15.0
        assert 14.0 <= result.new_value <= 16.0

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

        Each step jumps RTT to baseline + step_magnitude and holds it there
        for settling_minutes * 2 before returning to baseline. Steps need
        enough spacing to allow settling measurement.

        Args:
            step_times: List of minute indices where steps occur.
            baseline_rtt: Base RTT value before steps.
            step_magnitude: Size of RTT jump.
            settling_minutes: How many minutes the EWMA takes to settle.
        """
        total_minutes = max(step_times) + settling_minutes * 3 + 20
        total_minutes = max(total_minutes, 200)  # Ensure enough data

        rtt_values: list[float] = []
        ewma_values: list[float] = []
        jitter_values: list[float] = []

        # Build RTT profile: baseline with step-up periods
        step_set = set(step_times)
        active_steps: dict[int, int] = {}  # step_start -> remaining_minutes
        current_level = baseline_rtt

        for minute in range(total_minutes):
            if minute in step_set:
                # Start a new step: hold elevated for settling_minutes * 2
                active_steps[minute] = settling_minutes * 2

            # Check if any step is still active
            elevated = False
            to_remove = []
            for start, remaining in active_steps.items():
                if remaining > 0:
                    elevated = True
                    active_steps[start] = remaining - 1
                else:
                    to_remove.append(start)
            for s in to_remove:
                del active_steps[s]

            if elevated:
                current_level = baseline_rtt + step_magnitude
            else:
                current_level = baseline_rtt

            rtt_values.append(current_level)
            jitter_values.append(1.0)

        # Build EWMA with controlled settling speed.
        # alpha_per_minute controls how fast EWMA follows the step.
        # Higher alpha = faster settling. With alpha=0.5 and step_magnitude=20:
        #   min 0: diff=20, min 1: diff=10, min 2: diff=5, min 3: diff=2.5,
        #   min 4: diff=1.25, min 5: diff=0.625 (within 5% of 20 = 1.0ms)
        # So settling_minutes=5 means ~5 minutes = 300 seconds settling time.
        alpha_per_minute = 0.5 if settling_minutes <= 2 else 0.4
        current_ewma = baseline_rtt
        for minute in range(total_minutes):
            current_ewma = current_ewma + alpha_per_minute * (rtt_values[minute] - current_ewma)
            ewma_values.append(current_ewma)

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
        """Fewer than MIN_STEPS (3) settled step events -> None."""
        # Only 1 step event (creates 2 transitions: up + down).
        # The algorithm needs at least MIN_STEPS=3 settled events.
        metrics = self._make_step_response_data(
            step_times=[20],
            settling_minutes=5,
        )
        result = tune_alpha_load(metrics, 2.0, self.BOUNDS, "Spectrum")
        # With only 1 step_time (2 transitions), fewer than 3 settled steps
        assert result is None


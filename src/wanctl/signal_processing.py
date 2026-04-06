"""Signal processing for RTT measurements.

Provides pre-EWMA filtering, jitter tracking, variance estimation,
and confidence scoring for raw RTT samples. All algorithms use Python
stdlib only -- no numpy, scipy, or third-party dependencies.

Components:
    SignalResult: Frozen dataclass containing per-cycle signal quality metadata
    SignalProcessor: Stateful processor with Hampel filter, jitter/variance EWMA,
        and confidence scoring

Signal flow:
    raw_rtt -> SignalProcessor.process() -> SignalResult
        -> filtered_rtt feeds into existing update_ewma()
        -> jitter, variance, confidence available for metrics/logging

Args pattern:
    SignalProcessor is instantiated per-WAN in WANController.__init__() with
    config dict extracted from the signal_processing YAML section.
"""

from __future__ import annotations

import logging
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Any

# Hampel filter MAD scale factor for Gaussian consistency.
# Equals 1 / Phi^-1(3/4) where Phi^-1 is the inverse normal CDF.
# Converts MAD to an estimate of the standard deviation for Gaussian data.
MAD_SCALE_FACTOR = 1.4826

# Cycle interval in seconds -- matches autorate_continuous.py production value.
CYCLE_INTERVAL_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class SignalResult:
    """Per-cycle signal quality metadata returned by SignalProcessor.process().

    Attributes:
        filtered_rtt: Post-Hampel RTT in ms (or raw if warming up).
        raw_rtt: Original measured RTT in ms (always preserved).
        jitter_ms: EWMA jitter from consecutive raw RTT deltas.
        variance_ms2: EWMA variance of raw RTT around load_rtt (ms^2).
        confidence: 0-1 score: 1.0 / (1.0 + variance / baseline^2).
        is_outlier: True if Hampel detected this sample as an outlier.
        outlier_rate: Fraction of recent window that were outliers.
        total_outliers: Lifetime count of all outliers detected (monotonically increasing).
        consecutive_outliers: Current streak of consecutive outliers (resets on non-outlier).
        warming_up: True if Hampel window not yet full.
    """

    filtered_rtt: float
    raw_rtt: float
    jitter_ms: float
    variance_ms2: float
    confidence: float
    is_outlier: bool
    outlier_rate: float
    total_outliers: int
    consecutive_outliers: int
    warming_up: bool


class SignalProcessor:
    """RTT signal processor with Hampel filter, jitter, variance, and confidence.

    Processes raw RTT measurements and produces SignalResult with:
    - Hampel outlier detection and median replacement
    - EWMA jitter tracking from consecutive raw RTT deltas
    - EWMA variance tracking of raw RTT deviation from load_rtt
    - Confidence scoring based on variance relative to baseline

    All computations use Python stdlib only (statistics, collections, math).

    Args:
        wan_name: WAN identifier for log messages.
        config: Dict with optional keys: hampel_window_size (default 7),
            hampel_sigma_threshold (default 3.0), jitter_time_constant_sec
            (default 2.0), variance_time_constant_sec (default 5.0).
        logger: Logger instance for debug/info messages.
    """

    def __init__(
        self,
        wan_name: str,
        config: dict[str, Any],
        logger: logging.Logger,
    ) -> None:
        self._wan_name = wan_name
        self._logger = logger

        # Extract config with defaults
        self._window_size: int = config.get("hampel_window_size", 7)
        self._sigma_threshold: float = config.get("hampel_sigma_threshold", 3.0)
        jitter_tc: float = config.get("jitter_time_constant_sec", 2.0)
        variance_tc: float = config.get("variance_time_constant_sec", 5.0)

        # Compute EWMA alphas from time constants
        # Formula: alpha = cycle_interval / time_constant
        self._jitter_alpha: float = CYCLE_INTERVAL_SECONDS / jitter_tc
        self._variance_alpha: float = CYCLE_INTERVAL_SECONDS / variance_tc

        # Hampel rolling window (stores raw RTT values)
        self._window: deque[float] = deque(maxlen=self._window_size)

        # Outlier tracking window (parallel to _window for rate calculation)
        self._outlier_window: deque[bool] = deque(maxlen=self._window_size)

        # EWMA state
        self._jitter_ewma: float = 0.0
        self._variance_ewma: float = 0.0

        # Previous raw RTT for jitter delta computation
        self._previous_raw_rtt: float | None = None

        # Lifetime and streak counters
        self._total_outliers: int = 0
        self._consecutive_outliers: int = 0

    def process(
        self,
        raw_rtt: float,
        load_rtt: float,
        baseline_rtt: float,
    ) -> SignalResult:
        """Process a raw RTT measurement and return signal quality metadata.

        Args:
            raw_rtt: Raw measured RTT in milliseconds.
            load_rtt: Current load EWMA RTT in milliseconds.
            baseline_rtt: Current baseline RTT in milliseconds.

        Returns:
            SignalResult with filtered RTT, jitter, variance, confidence,
            and outlier detection results.
        """
        # 1. Warm-up check: window not yet full
        warming_up = len(self._window) < self._window_size

        # 2. Hampel filter
        if warming_up:
            filtered_rtt = raw_rtt
            is_outlier = False
        else:
            is_outlier, filtered_rtt = self._hampel_check(raw_rtt)

        # 3. Add raw RTT to window (always raw, not filtered)
        self._window.append(raw_rtt)

        # 4. Track outlier in parallel window and update counters
        self._outlier_window.append(is_outlier)
        if is_outlier:
            self._total_outliers += 1
            self._consecutive_outliers += 1
        else:
            self._consecutive_outliers = 0

        # 5. Outlier rate: fraction of recent window that were outliers
        outlier_rate = sum(self._outlier_window) / len(self._outlier_window)

        # Log outlier at INFO for operator visibility
        if is_outlier:
            self._logger.info(
                f"{self._wan_name}: RTT outlier detected: {raw_rtt:.1f}ms "
                f"-> {filtered_rtt:.1f}ms (outlier_rate={outlier_rate:.1%})"
            )

        # 6. Jitter: EWMA of consecutive raw RTT deltas
        jitter_ms = self._update_jitter(raw_rtt)

        # 7. Variance: EWMA of squared deviation from load_rtt
        variance_ms2 = self._update_variance(raw_rtt, load_rtt)

        # 8. Confidence: 1 / (1 + variance / baseline^2)
        confidence = self._compute_confidence(variance_ms2, baseline_rtt)

        # 9. Debug log
        self._logger.debug(
            f"{self._wan_name}: signal rtt={raw_rtt:.1f}ms "
            f"filtered={filtered_rtt:.1f}ms jitter={jitter_ms:.2f}ms "
            f"var={variance_ms2:.2f} conf={confidence:.3f}"
        )

        # 10. Return frozen result
        return SignalResult(
            filtered_rtt=filtered_rtt,
            raw_rtt=raw_rtt,
            jitter_ms=jitter_ms,
            variance_ms2=variance_ms2,
            confidence=confidence,
            is_outlier=is_outlier,
            outlier_rate=outlier_rate,
            total_outliers=self._total_outliers,
            consecutive_outliers=self._consecutive_outliers,
            warming_up=warming_up,
        )

    def _hampel_check(self, new_value: float) -> tuple[bool, float]:
        """Check if new_value is a Hampel outlier relative to the current window.

        Uses Median Absolute Deviation (MAD) scaled by MAD_SCALE_FACTOR to
        estimate robust standard deviation. Values beyond sigma_threshold
        scaled MADs from the median are classified as outliers.

        Args:
            new_value: New RTT measurement to check.

        Returns:
            Tuple of (is_outlier, filtered_value). If outlier, filtered_value
            is the window median; otherwise it is new_value unchanged.
        """
        values = list(self._window)
        med = statistics.median(values)
        abs_devs = [abs(v - med) for v in values]
        mad = statistics.median(abs_devs)

        # MAD-based threshold for outlier detection
        threshold = mad * MAD_SCALE_FACTOR * self._sigma_threshold

        # MAD=0 guard: when all window values are identical, threshold is 0
        # and any deviation would be flagged -- skip detection instead
        if threshold == 0.0:
            return (False, new_value)

        if abs(new_value - med) > threshold:
            return (True, med)

        return (False, new_value)

    def _update_jitter(self, raw_rtt: float) -> float:
        """Update jitter EWMA from consecutive raw RTT deltas.

        Jitter tracks the absolute difference between consecutive raw RTT
        measurements, smoothed via EWMA. Uses raw (not filtered) RTT to
        reflect true network behavior including spikes.

        Args:
            raw_rtt: Current raw RTT measurement in milliseconds.

        Returns:
            Current jitter EWMA value in milliseconds.
        """
        if self._previous_raw_rtt is None:
            self._previous_raw_rtt = raw_rtt
            return 0.0

        delta = abs(raw_rtt - self._previous_raw_rtt)
        self._previous_raw_rtt = raw_rtt

        # First-sample initialization: set EWMA directly from first delta
        if self._jitter_ewma == 0.0:
            self._jitter_ewma = delta
        else:
            self._jitter_ewma = (
                1.0 - self._jitter_alpha
            ) * self._jitter_ewma + self._jitter_alpha * delta

        return self._jitter_ewma

    def _update_variance(self, raw_rtt: float, load_rtt: float) -> float:
        """Update variance EWMA from squared deviation of raw RTT from load_rtt.

        Tracks how much raw RTT deviates from the load EWMA mean. Uses raw
        (not filtered) RTT to capture true measurement noise.

        Args:
            raw_rtt: Current raw RTT measurement in milliseconds.
            load_rtt: Current load EWMA RTT in milliseconds.

        Returns:
            Current variance EWMA value in ms^2.
        """
        deviation_sq = (raw_rtt - load_rtt) ** 2

        # First-sample initialization
        if self._variance_ewma == 0.0:
            self._variance_ewma = deviation_sq
        else:
            self._variance_ewma = (
                1.0 - self._variance_alpha
            ) * self._variance_ewma + self._variance_alpha * deviation_sq

        return self._variance_ewma

    def _compute_confidence(
        self,
        variance_ms2: float,
        baseline_rtt: float,
    ) -> float:
        """Compute confidence score from variance relative to baseline.

        Formula: 1.0 / (1.0 + variance / baseline^2)
        - High confidence (near 1.0): low variance relative to baseline
        - Low confidence (near 0.0): high variance relative to baseline

        Args:
            variance_ms2: Current variance EWMA in ms^2.
            baseline_rtt: Current baseline RTT in milliseconds.

        Returns:
            Confidence score in range [0.0, 1.0].
        """
        if baseline_rtt <= 0.0:
            return 1.0

        return 1.0 / (1.0 + variance_ms2 / (baseline_rtt**2))

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    @property
    def sigma_threshold(self) -> float:
        """Hampel filter sigma threshold."""
        return self._sigma_threshold

    @sigma_threshold.setter
    def sigma_threshold(self, value: float) -> None:
        self._sigma_threshold = value

    @property
    def window_size(self) -> int:
        """Hampel filter window size."""
        return self._window_size

    def resize_window(self, new_size: int) -> None:
        """Resize Hampel window, preserving existing data."""
        self._window_size = new_size
        self._window = deque(self._window, maxlen=new_size)
        self._outlier_window = deque(self._outlier_window, maxlen=new_size)

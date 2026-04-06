"""Signal processing tuning strategies.

Optimizes Hampel filter parameters and load EWMA time constant per-WAN from
production metrics. All strategies are pure StrategyFn callables.

SIGP-01: Hampel sigma from outlier rate analysis (target-based approach)
SIGP-02: Hampel window from jitter-based noise level proxy
SIGP-03: Load EWMA time constant from settling time analysis

NOTE on SIGP-03: This strategy outputs parameter="load_time_constant_sec"
(range 0.5-10s), NOT "alpha_load" directly. The applier converts tc to alpha
via alpha = 0.05 / tc in _apply_tuning_to_controller. This avoids Pitfall 3
from research: clamp_to_step rounds to 1 decimal (destroying alpha precision
like 0.025 -> 0.0), and the trivial change filter (abs < 0.1) blocks tiny
alpha deltas. Time constants in the 0.5-10s range survive both filters.
"""

from __future__ import annotations

import logging
from statistics import mean, median

from wanctl.tuning.models import SafetyBounds, TuningResult

logger = logging.getLogger(__name__)

# Minimum 1m samples needed for reliable analysis (~1 hour of data).
MIN_SAMPLES = 60

# ---------------------------------------------------------------------------
# SIGP-01: Hampel sigma tuning constants
# ---------------------------------------------------------------------------

# Target outlier rate range (fraction of samples flagged as outliers).
TARGET_OUTLIER_RATE_MIN = 0.05  # 5% -- below this, sigma is too loose
TARGET_OUTLIER_RATE_MAX = 0.15  # 15% -- above this, sigma is too tight

# Sigma adjustment step per tuning cycle.
SIGMA_STEP = 0.1

# ---------------------------------------------------------------------------
# SIGP-02: Hampel window tuning constants
# ---------------------------------------------------------------------------

# Jitter thresholds for window size interpolation (milliseconds).
JITTER_LOW_THRESHOLD = 1.0  # Below this: stable signal
JITTER_HIGH_THRESHOLD = 5.0  # Above this: noisy signal

# Window size range.
MIN_WINDOW = 5  # Minimum for robust median
MAX_WINDOW = 21  # Maximum window size (per-WAN config bounds enforce actual limits)

# ---------------------------------------------------------------------------
# SIGP-03: Load EWMA time constant tuning constants
# ---------------------------------------------------------------------------

# Target settling time for 95% step response.
TARGET_SETTLING_SEC = 2.0

# Tolerance around target (within +/-0.5s considered converged).
SETTLING_TOLERANCE = 0.5

# Step detection: delta must exceed this multiple of median jitter.
STEP_DETECTION_MULTIPLIER = 2.0

# Settling threshold: EWMA within 5% of step magnitude.
SETTLING_THRESHOLD_PCT = 0.05

# Cycle interval in seconds (50ms).
CYCLE_INTERVAL = 0.05

# Minimum step events needed for reliable analysis.
MIN_STEPS = 3

# Minimum absolute RTT delta to qualify as a step (milliseconds).
MIN_STEP_MAGNITUDE = 2.0

# Maximum settling window to scan forward (seconds).
MAX_SETTLING_WINDOW = 600  # 10 minutes


def tune_hampel_sigma(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune Hampel sigma threshold based on outlier rate analysis.

    SIGP-01: Adjusts sigma toward a target outlier rate range (5-15%).
    Too many outliers -> decrease sigma (more aggressive filtering).
    Too few outliers -> increase sigma (less aggressive filtering).

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    rates = _compute_outlier_rates(metrics_data, wan_name)
    if rates is None:
        return None

    if len(rates) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: hampel_sigma skipped, only %d rate deltas (need %d)",
            wan_name, len(rates), MIN_SAMPLES,
        )
        return None

    mean_outlier_rate = mean(rates)

    if TARGET_OUTLIER_RATE_MIN <= mean_outlier_rate <= TARGET_OUTLIER_RATE_MAX:
        logger.info(
            "[TUNING] %s: hampel_sigma converged, outlier_rate=%.1f%% in target range",
            wan_name, mean_outlier_rate * 100,
        )
        return None

    candidate = current_value - SIGMA_STEP if mean_outlier_rate > TARGET_OUTLIER_RATE_MAX else current_value + SIGMA_STEP
    confidence = min(1.0, len(rates) / 1440.0)
    direction = "above" if mean_outlier_rate > TARGET_OUTLIER_RATE_MAX else "below"

    return TuningResult(
        parameter="hampel_sigma_threshold",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=(
            f"outlier_rate={mean_outlier_rate:.1%} {direction} "
            f"target range {TARGET_OUTLIER_RATE_MIN:.0%}-{TARGET_OUTLIER_RATE_MAX:.0%}"
        ),
        data_points=len(rates),
        wan_name=wan_name,
    )


def _compute_outlier_rates(
    metrics_data: list[dict], wan_name: str
) -> list[float] | None:
    """Extract outlier count deltas and compute per-sample outlier rates.

    Returns None if insufficient data (fewer than 2 outlier_count samples).
    """
    count_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == "wanctl_signal_outlier_count":
            count_by_ts[row["timestamp"]] = row["value"]

    if len(count_by_ts) < 2:
        logger.info(
            "[TUNING] %s: hampel_sigma skipped, only %d outlier_count samples",
            wan_name, len(count_by_ts),
        )
        return None

    sorted_ts = sorted(count_by_ts.keys())
    rates: list[float] = []
    samples_per_sec = 1.0 / CYCLE_INTERVAL

    for i in range(1, len(sorted_ts)):
        delta = count_by_ts[sorted_ts[i]] - count_by_ts[sorted_ts[i - 1]]
        if delta < 0:
            continue  # Counter reset on daemon restart
        time_gap = sorted_ts[i] - sorted_ts[i - 1]
        if time_gap <= 0:
            continue  # Duplicate timestamps
        expected_samples = time_gap * samples_per_sec
        rate = max(0.0, min(1.0, delta / max(expected_samples, 1.0)))
        rates.append(rate)

    return rates


def tune_hampel_window(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune Hampel window size based on jitter level proxy.

    SIGP-02: Maps signal jitter to window size via linear interpolation.
    Low jitter (stable signal) -> larger window (smooth more).
    High jitter (noisy signal) -> smaller window (fast response).

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    # 1. Extract jitter values
    jitter_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_signal_jitter_ms":
            jitter_values.append(row["value"])

    # 2. Check minimum data requirement
    if len(jitter_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: hampel_window skipped, only %d jitter samples (need %d)",
            wan_name,
            len(jitter_values),
            MIN_SAMPLES,
        )
        return None

    # 3. Compute median jitter
    median_jitter = median(jitter_values)

    # 4. Linear interpolation: jitter -> window size
    if median_jitter <= JITTER_LOW_THRESHOLD:
        candidate = float(MAX_WINDOW)
    elif median_jitter >= JITTER_HIGH_THRESHOLD:
        candidate = float(MIN_WINDOW)
    else:
        # Interpolate linearly between MAX_WINDOW and MIN_WINDOW
        fraction = (median_jitter - JITTER_LOW_THRESHOLD) / (
            JITTER_HIGH_THRESHOLD - JITTER_LOW_THRESHOLD
        )
        candidate = MAX_WINDOW - (MAX_WINDOW - MIN_WINDOW) * fraction

    # 5. Confidence scales with data count
    confidence = min(1.0, len(jitter_values) / 1440.0)

    return TuningResult(
        parameter="hampel_window_size",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"median_jitter={median_jitter:.2f}ms -> window={candidate:.0f}",
        data_points=len(jitter_values),
        wan_name=wan_name,
    )


def tune_alpha_load(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune load EWMA time constant from step response settling time analysis.

    SIGP-03: Detects RTT step changes, measures how long the load EWMA takes
    to settle within 5% of the new level, and adjusts the time constant
    toward a target settling time of 2.0 seconds.

    Outputs parameter="load_time_constant_sec" (NOT "alpha_load"). The applier
    converts tc to alpha via alpha = 0.05 / tc.

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    rtt_by_ts, ewma_by_ts, jitter_values = _extract_alpha_load_metrics(metrics_data)

    if len(rtt_by_ts) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: alpha_load skipped, only %d RTT samples (need %d)",
            wan_name, len(rtt_by_ts), MIN_SAMPLES,
        )
        return None

    sorted_ts = sorted(rtt_by_ts.keys())
    settling_times = _measure_settling_times(rtt_by_ts, ewma_by_ts, sorted_ts, jitter_values)

    if len(settling_times) < MIN_STEPS:
        logger.info(
            "[TUNING] %s: alpha_load skipped, only %d steps detected (need %d)",
            wan_name, len(settling_times), MIN_STEPS,
        )
        return None

    return _compute_alpha_load_result(settling_times, current_value, wan_name)


def _extract_alpha_load_metrics(
    metrics_data: list[dict],
) -> tuple[dict[int, float], dict[int, float], list[float]]:
    """Extract RTT, EWMA, and jitter metrics by timestamp for alpha_load tuning."""
    rtt_by_ts: dict[int, float] = {}
    ewma_by_ts: dict[int, float] = {}
    jitter_values: list[float] = []

    for row in metrics_data:
        ts = row["timestamp"]
        name = row["metric_name"]
        val = row["value"]
        if name == "wanctl_rtt_ms":
            rtt_by_ts[ts] = val
        elif name == "wanctl_rtt_load_ewma_ms":
            ewma_by_ts[ts] = val
        elif name == "wanctl_signal_jitter_ms":
            jitter_values.append(val)

    return rtt_by_ts, ewma_by_ts, jitter_values


def _measure_settling_times(
    rtt_by_ts: dict[int, float],
    ewma_by_ts: dict[int, float],
    sorted_ts: list[int],
    jitter_values: list[float],
) -> list[float]:
    """Detect RTT steps and measure EWMA settling time for each."""
    # Compute step detection threshold from jitter
    if jitter_values:
        median_jitter = median(jitter_values)
    else:
        consecutive_deltas = [
            abs(rtt_by_ts[sorted_ts[i]] - rtt_by_ts[sorted_ts[i - 1]])
            for i in range(1, len(sorted_ts))
        ]
        if not consecutive_deltas:
            return []
        median_jitter = median(consecutive_deltas)

    step_threshold = max(STEP_DETECTION_MULTIPLIER * median_jitter, MIN_STEP_MAGNITUDE)

    # Find step indices
    step_indices = [
        i for i in range(1, len(sorted_ts))
        if abs(rtt_by_ts[sorted_ts[i]] - rtt_by_ts[sorted_ts[i - 1]]) >= step_threshold
    ]

    # Measure settling for each step
    settling_times: list[float] = []
    for step_idx in step_indices:
        settling = _measure_single_step_settling(
            rtt_by_ts, ewma_by_ts, sorted_ts, step_idx
        )
        if settling is not None:
            settling_times.append(settling)

    return settling_times


def _measure_single_step_settling(
    rtt_by_ts: dict[int, float],
    ewma_by_ts: dict[int, float],
    sorted_ts: list[int],
    step_idx: int,
) -> float | None:
    """Measure settling time for a single RTT step. Returns None if step is too small or unsettled."""
    step_ts = sorted_ts[step_idx]
    step_rtt = rtt_by_ts[step_ts]
    prev_rtt = rtt_by_ts[sorted_ts[step_idx - 1]]
    step_magnitude = abs(step_rtt - prev_rtt)

    if step_magnitude < MIN_STEP_MAGNITUDE:
        return None

    settle_threshold = SETTLING_THRESHOLD_PCT * step_magnitude

    for j in range(step_idx, len(sorted_ts)):
        scan_ts = sorted_ts[j]
        if scan_ts not in ewma_by_ts:
            continue
        elapsed_sec = scan_ts - step_ts
        if elapsed_sec > MAX_SETTLING_WINDOW:
            break
        if abs(ewma_by_ts[scan_ts] - step_rtt) <= settle_threshold:
            return float(elapsed_sec)

    return None


def _compute_alpha_load_result(
    settling_times: list[float], current_value: float, wan_name: str
) -> TuningResult | None:
    """Compute tuning result from settling times. Returns None if converged."""
    avg_settling_sec = mean(settling_times)

    if abs(avg_settling_sec - TARGET_SETTLING_SEC) <= SETTLING_TOLERANCE:
        logger.info(
            "[TUNING] %s: alpha_load converged, settling=%.1fs near target %.1fs",
            wan_name, avg_settling_sec, TARGET_SETTLING_SEC,
        )
        return None

    target_tc = TARGET_SETTLING_SEC / 3.0
    candidate_tc = current_value + 0.2 * (target_tc - current_value)
    confidence = min(1.0, len(settling_times) / 10.0)

    return TuningResult(
        parameter="load_time_constant_sec",
        old_value=current_value,
        new_value=round(candidate_tc, 1),
        confidence=confidence,
        rationale=(
            f"settling={avg_settling_sec:.1f}s "
            f"(target {TARGET_SETTLING_SEC}s), "
            f"{len(settling_times)} steps"
        ),
        data_points=len(settling_times),
        wan_name=wan_name,
    )

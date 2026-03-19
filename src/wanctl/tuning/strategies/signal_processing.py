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

# Expected samples per minute at 20Hz cycle rate.
SAMPLES_PER_MINUTE = 1200

# ---------------------------------------------------------------------------
# SIGP-02: Hampel window tuning constants
# ---------------------------------------------------------------------------

# Jitter thresholds for window size interpolation (milliseconds).
JITTER_LOW_THRESHOLD = 1.0   # Below this: stable signal
JITTER_HIGH_THRESHOLD = 5.0  # Above this: noisy signal

# Window size range.
MIN_WINDOW = 5   # Minimum for robust median
MAX_WINDOW = 15  # Maximum before detection latency

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
    # 1. Extract outlier_count values by timestamp
    count_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == "wanctl_signal_outlier_count":
            count_by_ts[row["timestamp"]] = row["value"]

    if len(count_by_ts) < 2:
        logger.info(
            "[TUNING] %s: hampel_sigma skipped, only %d outlier_count samples",
            wan_name,
            len(count_by_ts),
        )
        return None

    # 2. Sort timestamps, compute deltas between consecutive minutes
    sorted_ts = sorted(count_by_ts.keys())
    rates: list[float] = []
    for i in range(1, len(sorted_ts)):
        delta = count_by_ts[sorted_ts[i]] - count_by_ts[sorted_ts[i - 1]]
        # Discard negative deltas (counter reset on daemon restart)
        if delta < 0:
            continue
        # Convert delta to rate: outliers per sample
        rate = delta / SAMPLES_PER_MINUTE
        # Clamp to [0.0, 1.0] guard
        rate = max(0.0, min(1.0, rate))
        rates.append(rate)

    # 3. Check minimum data requirement
    if len(rates) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: hampel_sigma skipped, only %d rate deltas (need %d)",
            wan_name,
            len(rates),
            MIN_SAMPLES,
        )
        return None

    # 4. Compute mean outlier rate
    mean_outlier_rate = mean(rates)

    # 5. Check convergence (within target range)
    if TARGET_OUTLIER_RATE_MIN <= mean_outlier_rate <= TARGET_OUTLIER_RATE_MAX:
        logger.info(
            "[TUNING] %s: hampel_sigma converged, outlier_rate=%.1%% in target range",
            wan_name,
            mean_outlier_rate * 100,
        )
        return None

    # 6. Compute candidate
    if mean_outlier_rate > TARGET_OUTLIER_RATE_MAX:
        candidate = current_value - SIGMA_STEP  # More filtering
    else:
        candidate = current_value + SIGMA_STEP  # Less filtering

    # 7. Confidence scales with data count
    confidence = min(1.0, len(rates) / 1440.0)

    # 8. Direction label for rationale
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
    # 1. Extract metrics by timestamp into aligned dicts
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

    # 2. Check minimum data
    if len(rtt_by_ts) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: alpha_load skipped, only %d RTT samples (need %d)",
            wan_name,
            len(rtt_by_ts),
            MIN_SAMPLES,
        )
        return None

    # 3. Sort timestamps for sequential analysis
    sorted_ts = sorted(rtt_by_ts.keys())

    # 4. Compute median jitter for step detection threshold
    if jitter_values:
        median_jitter = median(jitter_values)
    else:
        # Fallback: compute from consecutive RTT deltas
        consecutive_deltas = [
            abs(rtt_by_ts[sorted_ts[i]] - rtt_by_ts[sorted_ts[i - 1]])
            for i in range(1, len(sorted_ts))
        ]
        if consecutive_deltas:
            median_jitter = median(consecutive_deltas)
        else:
            return None

    # 5. Detect steps: consecutive raw RTT delta > multiplier * median_jitter
    #    AND absolute delta >= MIN_STEP_MAGNITUDE
    step_threshold = max(
        STEP_DETECTION_MULTIPLIER * median_jitter, MIN_STEP_MAGNITUDE
    )

    step_indices: list[int] = []
    for i in range(1, len(sorted_ts)):
        delta = abs(rtt_by_ts[sorted_ts[i]] - rtt_by_ts[sorted_ts[i - 1]])
        if delta >= step_threshold:
            step_indices.append(i)

    # 6. For each step, measure settling time
    settling_times: list[float] = []
    for step_idx in step_indices:
        step_ts = sorted_ts[step_idx]
        step_rtt = rtt_by_ts[step_ts]
        prev_rtt = rtt_by_ts[sorted_ts[step_idx - 1]]
        step_magnitude = abs(step_rtt - prev_rtt)

        if step_magnitude < MIN_STEP_MAGNITUDE:
            continue

        settle_threshold = SETTLING_THRESHOLD_PCT * step_magnitude

        # Scan forward from step to find settling point
        for j in range(step_idx, len(sorted_ts)):
            scan_ts = sorted_ts[j]
            if scan_ts not in ewma_by_ts:
                continue

            elapsed_sec = scan_ts - step_ts
            if elapsed_sec > MAX_SETTLING_WINDOW:
                break  # Too long, discard this step

            ewma_val = ewma_by_ts[scan_ts]
            if abs(ewma_val - step_rtt) <= settle_threshold:
                settling_sec = float(elapsed_sec)
                settling_times.append(settling_sec)
                break

        # If EWMA never settled within window, discard the step

    # 7. Check minimum steps requirement
    if len(settling_times) < MIN_STEPS:
        logger.info(
            "[TUNING] %s: alpha_load skipped, only %d steps detected (need %d)",
            wan_name,
            len(settling_times),
            MIN_STEPS,
        )
        return None

    # 8. Compute average settling time
    avg_settling_sec = mean(settling_times)

    # 9. Check convergence
    if abs(avg_settling_sec - TARGET_SETTLING_SEC) <= SETTLING_TOLERANCE:
        logger.info(
            "[TUNING] %s: alpha_load converged, settling=%.1fs near target %.1fs",
            wan_name,
            avg_settling_sec,
            TARGET_SETTLING_SEC,
        )
        return None

    # 10. Derive target time constant: tc ≈ settling_time / 3 (95% settling)
    target_tc = TARGET_SETTLING_SEC / 3.0

    # 11. Move current tc 20% toward target (conservative)
    candidate_tc = current_value + 0.2 * (target_tc - current_value)

    # 12. Confidence scales with step count
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

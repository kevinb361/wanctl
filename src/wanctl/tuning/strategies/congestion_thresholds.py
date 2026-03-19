"""Congestion threshold calibration strategies.

Derives target_bloat_ms (GREEN->YELLOW threshold) from the p75 of GREEN-state
RTT delta distributions, and warn_bloat_ms (YELLOW->SOFT_RED threshold) from
the p90.  Both are pure StrategyFn callables compatible with the tuning
analyzer framework from Phase 98.

CALI-01: target_bloat_ms from p75 GREEN-state RTT delta
CALI-02: warn_bloat_ms from p90 GREEN-state RTT delta
CALI-03: Convergence detection via sub-window CoV
CALI-04: Processes full 24h diurnal lookback window
"""

from __future__ import annotations

import logging
from statistics import mean, quantiles, stdev

from wanctl.tuning.models import SafetyBounds, TuningResult

logger = logging.getLogger(__name__)

# Minimum GREEN-state 1m samples needed for reliable percentile derivation.
# 60 samples = ~1 hour of GREEN minutes in a 24h lookback window.
MIN_GREEN_SAMPLES = 60

# State encoding (matches _encode_state in autorate_continuous.py)
STATE_GREEN = 0.0

# Default coefficient of variation threshold for convergence detection.
# CoV < 0.05 means standard deviation is < 5% of the mean across sub-windows.
DEFAULT_COV_THRESHOLD = 0.05

# Number of sub-windows to split the lookback period into for convergence.
NUM_SUB_WINDOWS = 4

# Minimum samples per sub-window for convergence check.
_MIN_SUB_WINDOW_SAMPLES = 10


def _extract_green_deltas(metrics_data: list[dict]) -> list[float]:
    """Extract RTT delta values from timestamps where state was GREEN.

    In 1m aggregated data, wanctl_state uses MODE aggregation (most common
    state in the minute).  State value 0.0 = GREEN (majority of minute).

    Builds two dicts keyed by timestamp, then returns delta values where
    the corresponding state is GREEN.
    """
    state_by_ts: dict[int, float] = {}
    delta_by_ts: dict[int, float] = {}

    for row in metrics_data:
        ts = row["timestamp"]
        name = row["metric_name"]
        val = row["value"]
        if name == "wanctl_state":
            state_by_ts[ts] = val
        elif name == "wanctl_rtt_delta_ms":
            delta_by_ts[ts] = val

    return [
        delta_by_ts[ts]
        for ts in delta_by_ts
        if state_by_ts.get(ts) == STATE_GREEN
    ]


def _extract_green_deltas_with_timestamps(
    metrics_data: list[dict],
) -> tuple[list[float], list[int]]:
    """Extract GREEN-state RTT deltas and their timestamps.

    Same logic as _extract_green_deltas but also returns the matched
    timestamps for convergence sub-windowing.
    """
    state_by_ts: dict[int, float] = {}
    delta_by_ts: dict[int, float] = {}

    for row in metrics_data:
        ts = row["timestamp"]
        name = row["metric_name"]
        val = row["value"]
        if name == "wanctl_state":
            state_by_ts[ts] = val
        elif name == "wanctl_rtt_delta_ms":
            delta_by_ts[ts] = val

    deltas: list[float] = []
    timestamps: list[int] = []
    for ts in delta_by_ts:
        if state_by_ts.get(ts) == STATE_GREEN:
            deltas.append(delta_by_ts[ts])
            timestamps.append(ts)

    return deltas, timestamps


def _is_converged(
    green_deltas: list[float],
    timestamps: list[int],
    percentile_index: int,
    cov_threshold: float = DEFAULT_COV_THRESHOLD,
) -> bool:
    """Check if a percentile has converged across sub-windows of lookback.

    Splits timestamps into NUM_SUB_WINDOWS equal ranges, computes the target
    percentile in each sub-window, and checks if the coefficient of variation
    across those sub-percentiles is below threshold.

    Returns False when insufficient data prevents a reliable convergence check.
    """
    if not timestamps or not green_deltas:
        return False

    min_ts = min(timestamps)
    max_ts = max(timestamps)
    span = max_ts - min_ts
    if span == 0:
        # All timestamps identical -- cannot split into sub-windows
        return False

    window_size = span / NUM_SUB_WINDOWS

    sub_percentiles: list[float] = []
    for i in range(NUM_SUB_WINDOWS):
        win_start = min_ts + i * window_size
        win_end = win_start + window_size
        chunk = [
            d
            for d, t in zip(green_deltas, timestamps, strict=True)
            if win_start <= t < win_end
        ]
        if len(chunk) < _MIN_SUB_WINDOW_SAMPLES:
            return False  # Insufficient data in sub-window
        p = quantiles(chunk, n=100)
        sub_percentiles.append(p[percentile_index])

    if len(sub_percentiles) < 3:
        return False

    avg = mean(sub_percentiles)
    if avg < 0.001:
        return True  # Effectively zero, consider converged

    cov = stdev(sub_percentiles) / avg
    return cov < cov_threshold


def calibrate_target_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Derive target_bloat_ms from p75 of GREEN-state RTT delta distribution.

    CALI-01: target_bloat_ms converges toward p75 of GREEN-state deltas.
    CALI-04: Uses full 24h lookback window from metrics_data.

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    green_deltas, timestamps = _extract_green_deltas_with_timestamps(metrics_data)

    if len(green_deltas) < MIN_GREEN_SAMPLES:
        logger.info(
            "[TUNING] %s: target_bloat_ms skipped, only %d GREEN samples (need %d)",
            wan_name,
            len(green_deltas),
            MIN_GREEN_SAMPLES,
        )
        return None

    if _is_converged(green_deltas, timestamps, 74):
        logger.info(
            "[TUNING] %s: target_bloat_ms converged (CoV < %.2f across %d sub-windows)",
            wan_name,
            DEFAULT_COV_THRESHOLD,
            NUM_SUB_WINDOWS,
        )
        return None

    percentiles = quantiles(green_deltas, n=100)
    candidate = percentiles[74]  # p75

    confidence = min(1.0, len(green_deltas) / 1440.0)

    return TuningResult(
        parameter="target_bloat_ms",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"p75 GREEN delta={candidate:.1f}ms ({len(green_deltas)} samples)",
        data_points=len(green_deltas),
        wan_name=wan_name,
    )


def calibrate_warn_bloat(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Derive warn_bloat_ms from p90 of GREEN-state RTT delta distribution.

    CALI-02: warn_bloat_ms converges toward p90 of GREEN-state deltas.
    CALI-04: Uses full 24h lookback window from metrics_data.

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    green_deltas, timestamps = _extract_green_deltas_with_timestamps(metrics_data)

    if len(green_deltas) < MIN_GREEN_SAMPLES:
        logger.info(
            "[TUNING] %s: warn_bloat_ms skipped, only %d GREEN samples (need %d)",
            wan_name,
            len(green_deltas),
            MIN_GREEN_SAMPLES,
        )
        return None

    if _is_converged(green_deltas, timestamps, 89):
        logger.info(
            "[TUNING] %s: warn_bloat_ms converged (CoV < %.2f across %d sub-windows)",
            wan_name,
            DEFAULT_COV_THRESHOLD,
            NUM_SUB_WINDOWS,
        )
        return None

    percentiles = quantiles(green_deltas, n=100)
    candidate = percentiles[89]  # p90

    confidence = min(1.0, len(green_deltas) / 1440.0)

    return TuningResult(
        parameter="warn_bloat_ms",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"p90 GREEN delta={candidate:.1f}ms ({len(green_deltas)} samples)",
        data_points=len(green_deltas),
        wan_name=wan_name,
    )

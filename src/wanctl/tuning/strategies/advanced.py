"""Advanced tuning strategies -- fusion weight, reflector scoring, baseline bounds.

ADVT-01: Fusion ICMP/IRTT weight from per-signal reliability scoring
ADVT-02: Reflector min_score from signal confidence proxy
ADVT-03: Baseline RTT bounds from p5/p95 baseline history

All strategies are pure StrategyFn callables matching the established
Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
signature from the tuning analyzer framework.
"""

from __future__ import annotations

import logging
from statistics import mean, quantiles

from wanctl.tuning.models import SafetyBounds, TuningResult

logger = logging.getLogger(__name__)

# Minimum 1m samples needed for reliable analysis (~1 hour of data).
MIN_SAMPLES = 60

# ---------------------------------------------------------------------------
# ADVT-02: Reflector min_score confidence thresholds
# ---------------------------------------------------------------------------

# Below this mean confidence: min_score is too strict (lower it).
CONFIDENCE_LOW = 0.5

# Above this mean confidence: min_score is too lenient (raise it).
CONFIDENCE_HIGH = 0.9

# Adjustment step per tuning cycle.
CONFIDENCE_STEP = 0.05

# ---------------------------------------------------------------------------
# ADVT-03: Baseline margin multipliers
# ---------------------------------------------------------------------------

# p5 margin: candidate_min = p5 * 0.9 (10% below observed minimum).
BASELINE_MIN_MARGIN = 0.9

# p95 margin: candidate_max = p95 * 1.1 (10% above observed maximum).
BASELINE_MAX_MARGIN = 1.1


def tune_fusion_weight(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune fusion ICMP weight based on per-signal reliability scoring.

    ADVT-01: Computes reliability scores for ICMP and IRTT signals from
    variance, jitter, and loss metrics. Derives candidate ICMP weight
    proportional to ICMP's relative reliability.

    Returns None when IRTT metrics are absent (fusion disabled or no data).

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    # 1. Extract ICMP signal variance values
    icmp_variance_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_signal_variance_ms2":
            icmp_variance_values.append(row["value"])

    # 2. Extract IRTT jitter (ipdv) values
    irtt_ipdv_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_irtt_ipdv_ms":
            irtt_ipdv_values.append(row["value"])

    # 3. Extract IRTT loss values (up and down, percentages 0-100)
    irtt_loss_up_values: list[float] = []
    irtt_loss_down_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_irtt_loss_up_pct":
            irtt_loss_up_values.append(row["value"])
        elif row["metric_name"] == "wanctl_irtt_loss_down_pct":
            irtt_loss_down_values.append(row["value"])

    # 4. Check ICMP minimum data requirement
    if len(icmp_variance_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: fusion_icmp_weight skipped, only %d ICMP variance samples (need %d)",
            wan_name,
            len(icmp_variance_values),
            MIN_SAMPLES,
        )
        return None

    # 5. Check IRTT minimum data requirement (no comparison possible without IRTT)
    if len(irtt_ipdv_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: fusion_icmp_weight skipped, only %d IRTT jitter samples (need %d)",
            wan_name,
            len(irtt_ipdv_values),
            MIN_SAMPLES,
        )
        return None

    # 6. Compute ICMP reliability: 1.0 / (1.0 + mean_variance)
    mean_icmp_variance = mean(icmp_variance_values)
    icmp_reliability = 1.0 / (1.0 + mean_icmp_variance)

    # 7. Compute mean IRTT loss fraction (percentage 0-100 -> fraction 0-1)
    if irtt_loss_up_values and irtt_loss_down_values:
        mean_loss_up = mean(irtt_loss_up_values)
        mean_loss_down = mean(irtt_loss_down_values)
        mean_irtt_loss_fraction = max(0.0, min(1.0, (mean_loss_up + mean_loss_down) / 2.0 / 100.0))
    else:
        mean_irtt_loss_fraction = 0.0

    # 8. Compute IRTT reliability: (1.0 - loss_fraction) / (1.0 + mean_jitter)
    mean_irtt_ipdv = mean(irtt_ipdv_values)
    irtt_reliability = (1.0 - mean_irtt_loss_fraction) / (1.0 + mean_irtt_ipdv)

    # 9. Candidate ICMP weight = proportion of ICMP reliability
    total_reliability = icmp_reliability + irtt_reliability
    if total_reliability < 0.001:
        # Both signals equally unreliable -- keep current
        return None
    candidate = icmp_reliability / total_reliability

    # 10. Confidence scales with minimum data count
    min_count = min(len(icmp_variance_values), len(irtt_ipdv_values))
    confidence = min(1.0, min_count / 1440.0)

    return TuningResult(
        parameter="fusion_icmp_weight",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=(
            f"icmp_reliability={icmp_reliability:.3f} "
            f"irtt_reliability={irtt_reliability:.3f} "
            f"-> icmp_weight={candidate:.3f}"
        ),
        data_points=min_count,
        wan_name=wan_name,
    )


def tune_reflector_min_score(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune reflector min_score threshold from signal confidence proxy.

    ADVT-02: Uses mean signal confidence as a proxy for reflector quality.
    Low confidence suggests min_score is too strict (good reflectors being
    deprioritized). High confidence suggests min_score could be raised.

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    # 1. Extract signal confidence values
    confidence_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_signal_confidence":
            confidence_values.append(row["value"])

    # 2. Check minimum data requirement
    if len(confidence_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: reflector_min_score skipped, only %d confidence samples (need %d)",
            wan_name,
            len(confidence_values),
            MIN_SAMPLES,
        )
        return None

    # 3. Compute mean confidence
    mean_confidence = mean(confidence_values)

    # 4. Check convergence (within acceptable range)
    if CONFIDENCE_LOW <= mean_confidence <= CONFIDENCE_HIGH:
        logger.info(
            "[TUNING] %s: reflector_min_score converged, mean_confidence=%.2f in range [%.1f, %.1f]",
            wan_name,
            mean_confidence,
            CONFIDENCE_LOW,
            CONFIDENCE_HIGH,
        )
        return None

    # 5. Compute candidate
    if mean_confidence < CONFIDENCE_LOW:
        # Confidence too low -> min_score is too strict, loosen it
        candidate = current_value - CONFIDENCE_STEP
    else:
        # Confidence very high -> min_score is too lenient, tighten it
        candidate = current_value + CONFIDENCE_STEP

    # 6. Confidence scales with data count
    confidence = min(1.0, len(confidence_values) / 1440.0)

    direction = "below" if mean_confidence < CONFIDENCE_LOW else "above"

    return TuningResult(
        parameter="reflector_min_score",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=(
            f"mean_confidence={mean_confidence:.2f} {direction} "
            f"range [{CONFIDENCE_LOW:.1f}, {CONFIDENCE_HIGH:.1f}]"
        ),
        data_points=len(confidence_values),
        wan_name=wan_name,
    )


def tune_baseline_bounds_min(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune baseline RTT minimum bound from p5 of baseline history.

    ADVT-03: Derives baseline_rtt_min from the 5th percentile of observed
    baseline RTT values with a 10% margin below (p5 * 0.9).

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    # 1. Extract baseline RTT values
    baseline_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_rtt_baseline_ms":
            baseline_values.append(row["value"])

    # 2. Check minimum data requirement
    if len(baseline_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: baseline_rtt_min skipped, only %d baseline samples (need %d)",
            wan_name,
            len(baseline_values),
            MIN_SAMPLES,
        )
        return None

    # 3. Compute percentiles
    percentiles = quantiles(baseline_values, n=100)

    # 4. p5 with margin
    p5 = percentiles[4]  # 5th percentile (0-indexed)
    candidate = p5 * BASELINE_MIN_MARGIN

    # 5. Floor at hard minimum (1.0ms via bounds, but also enforce explicitly)
    candidate = max(candidate, 1.0)

    # 6. Confidence scales with data count
    confidence = min(1.0, len(baseline_values) / 1440.0)

    return TuningResult(
        parameter="baseline_rtt_min",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"p5={p5:.1f}ms * {BASELINE_MIN_MARGIN} = {candidate:.1f}ms ({len(baseline_values)} samples)",
        data_points=len(baseline_values),
        wan_name=wan_name,
    )


def tune_baseline_bounds_max(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune baseline RTT maximum bound from p95 of baseline history.

    ADVT-03: Derives baseline_rtt_max from the 95th percentile of observed
    baseline RTT values with a 10% margin above (p95 * 1.1).

    Matches StrategyFn signature:
        Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
    """
    # 1. Extract baseline RTT values
    baseline_values: list[float] = []
    for row in metrics_data:
        if row["metric_name"] == "wanctl_rtt_baseline_ms":
            baseline_values.append(row["value"])

    # 2. Check minimum data requirement
    if len(baseline_values) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: baseline_rtt_max skipped, only %d baseline samples (need %d)",
            wan_name,
            len(baseline_values),
            MIN_SAMPLES,
        )
        return None

    # 3. Compute percentiles
    percentiles = quantiles(baseline_values, n=100)

    # 4. p95 with margin
    p95 = percentiles[94]  # 95th percentile (0-indexed)
    candidate = p95 * BASELINE_MAX_MARGIN

    # 5. Confidence scales with data count
    confidence = min(1.0, len(baseline_values) / 1440.0)

    return TuningResult(
        parameter="baseline_rtt_max",
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=confidence,
        rationale=f"p95={p95:.1f}ms * {BASELINE_MAX_MARGIN} = {candidate:.1f}ms ({len(baseline_values)} samples)",
        data_points=len(baseline_values),
        wan_name=wan_name,
    )

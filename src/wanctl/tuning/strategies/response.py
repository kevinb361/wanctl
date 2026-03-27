"""Response tuning strategies -- step_up, factor_down, green_required.

RTUN-01: Step up adjustment from recovery episode re-trigger analysis
RTUN-02: Factor down adjustment from congestion resolution speed
RTUN-03: Green required adjustment from re-trigger rate
RTUN-04: Oscillation lockout -- freeze response params when state transitions exceed threshold

All strategies are pure StrategyFn callables matching the established
Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]
signature from the tuning analyzer framework.

Six public functions (dl/ul variants of 3 strategies) share 3 internal
implementations and a common episode detection infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import median
from typing import Any

from wanctl.tuning.models import SafetyBounds, TuningResult
from wanctl.tuning.safety import lock_parameter

logger = logging.getLogger(__name__)

# Minimum 1m samples needed for reliable analysis (~1 hour of data).
MIN_SAMPLES = 60

# All 6 response parameter names (used by oscillation lockout in Plan 02).
RESPONSE_PARAMS = [
    "dl_step_up_mbps",
    "ul_step_up_mbps",
    "dl_factor_down",
    "ul_factor_down",
    "dl_green_required",
    "ul_green_required",
]

# Re-trigger window: if congestion re-enters within this window after
# recovery, count as a re-trigger event (seconds).
RE_TRIGGER_WINDOW_SEC = 300

# Re-trigger rate thresholds.
RE_TRIGGER_HIGH = 0.5  # 50% -- too aggressive
RE_TRIGGER_LOW = 0.3  # 30% -- safe to increase

# Step adjustment for step_up tuning (Mbps per tuning cycle).
STEP_ADJUSTMENT = 0.5

# Ratio adjustment step for factor_down tuning (per tuning cycle).
FACTOR_ADJUSTMENT = 0.01

# Congestion resolution speed thresholds (seconds).
MEDIAN_DURATION_FAST_SEC = 120  # 2 min -- factor_down is effective
MEDIAN_DURATION_SLOW_SEC = 300  # 5 min -- factor_down is too gentle


@dataclass(frozen=True, slots=True)
class RecoveryEpisode:
    """A single congestion-to-recovery episode detected from state time series.

    Attributes:
        congestion_start_ts: Unix timestamp when congestion began (state >= 2.0).
        recovery_end_ts: Unix timestamp when recovery completed (state == 0.0).
        duration_sec: Duration from congestion start to recovery end.
        peak_severity: Maximum state value observed during the episode.
        pre_rate_mbps: Rate at the timestamp before congestion start (None if unavailable).
        post_rate_mbps: Rate at the recovery end timestamp (None if unavailable).
    """

    congestion_start_ts: int
    recovery_end_ts: int
    duration_sec: int
    peak_severity: float
    pre_rate_mbps: float | None
    post_rate_mbps: float | None


def _detect_recovery_episodes(
    metrics_data: list[dict], direction: str = "download"
) -> list[RecoveryEpisode]:
    """Detect congestion-to-recovery episodes from wanctl_state time series.

    Walks sorted timestamps looking for transitions:
    - Congestion start: state goes from < 2.0 to >= 2.0
    - Recovery end: state goes from >= 2.0 to 0.0

    Args:
        metrics_data: List of metric dicts with timestamp, metric_name, value.
        direction: "download" or "upload" for rate metric selection.

    Returns:
        List of RecoveryEpisode instances.
    """
    # Extract state values by timestamp
    state_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == "wanctl_state":
            state_by_ts[row["timestamp"]] = row["value"]

    # Extract rate values by timestamp
    rate_metric = f"wanctl_rate_{direction}_mbps"
    rate_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == rate_metric:
            rate_by_ts[row["timestamp"]] = row["value"]

    if len(state_by_ts) < 2:
        return []

    sorted_ts = sorted(state_by_ts.keys())
    episodes: list[RecoveryEpisode] = []

    congestion_start_ts: int | None = None
    peak_severity: float = 0.0

    for i in range(len(sorted_ts)):
        ts = sorted_ts[i]
        state = state_by_ts[ts]

        if congestion_start_ts is None:
            # Not in congestion -- look for start
            if state >= 2.0:
                congestion_start_ts = ts
                peak_severity = state
        else:
            # In congestion -- track peak and look for recovery
            if state >= 2.0:
                peak_severity = max(peak_severity, state)
            elif state == 0.0:
                # Recovery complete
                # Pre-rate: rate at the timestamp just before congestion start
                pre_rate: float | None = None
                start_idx = sorted_ts.index(congestion_start_ts)
                if start_idx > 0:
                    prev_ts = sorted_ts[start_idx - 1]
                    pre_rate = rate_by_ts.get(prev_ts)

                # Post-rate: rate at the recovery end timestamp
                post_rate = rate_by_ts.get(ts)

                duration = ts - congestion_start_ts
                episodes.append(
                    RecoveryEpisode(
                        congestion_start_ts=congestion_start_ts,
                        recovery_end_ts=ts,
                        duration_sec=duration,
                        peak_severity=peak_severity,
                        pre_rate_mbps=pre_rate,
                        post_rate_mbps=post_rate,
                    )
                )
                congestion_start_ts = None
                peak_severity = 0.0

    return episodes


def _compute_re_trigger_rate(episodes: list[RecoveryEpisode]) -> float:
    """Compute fraction of episodes followed by a quick re-trigger.

    For each consecutive pair of episodes, checks if the next congestion_start_ts
    is within RE_TRIGGER_WINDOW_SEC of the previous recovery_end_ts.

    Returns:
        Fraction of episodes that are followed by a quick re-trigger (0.0-1.0).
        Returns 0.0 if fewer than 2 episodes.
    """
    if len(episodes) < 2:
        return 0.0

    re_triggers = 0
    pairs = len(episodes) - 1

    for i in range(pairs):
        gap = episodes[i + 1].congestion_start_ts - episodes[i].recovery_end_ts
        if gap <= RE_TRIGGER_WINDOW_SEC:
            re_triggers += 1

    return re_triggers / pairs


# ---------------------------------------------------------------------------
# Internal implementations (shared by dl/ul variants)
# ---------------------------------------------------------------------------


def _tune_step_up_impl(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
    param_name: str,
    direction: str,
) -> TuningResult | None:
    """Tune step_up based on recovery episode re-trigger rate.

    RTUN-01: High re-trigger rate -> step_up is too aggressive (decrease).
    Low re-trigger rate -> step_up may be too conservative (increase).
    """
    # Filter wanctl_state samples
    state_samples = [r for r in metrics_data if r["metric_name"] == "wanctl_state"]
    if len(state_samples) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: %s skipped, only %d state samples (need %d)",
            wan_name,
            param_name,
            len(state_samples),
            MIN_SAMPLES,
        )
        return None

    episodes = _detect_recovery_episodes(metrics_data, direction)
    if not episodes:
        return None

    re_trigger = _compute_re_trigger_rate(episodes)

    if re_trigger > RE_TRIGGER_HIGH:
        candidate = current_value - STEP_ADJUSTMENT
    elif re_trigger < RE_TRIGGER_LOW:
        candidate = current_value + STEP_ADJUSTMENT
    else:
        return None

    # Clamp to bounds
    candidate = max(bounds.min_value, min(bounds.max_value, candidate))

    # Trivial change check
    if abs(candidate - current_value) < 0.1:
        return None

    return TuningResult(
        parameter=param_name,
        old_value=current_value,
        new_value=round(candidate, 1),
        confidence=0.6,
        rationale=(
            f"re-trigger rate {re_trigger:.0%}: "
            f"{'decreasing' if candidate < current_value else 'increasing'} step_up"
        ),
        data_points=len(episodes),
        wan_name=wan_name,
    )


def _tune_factor_down_impl(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
    param_name: str,
    direction: str,
) -> TuningResult | None:
    """Tune factor_down based on congestion episode resolution speed.

    RTUN-02: Fast resolution -> factor_down may be too aggressive (increase toward 1.0).
    Slow resolution -> factor_down is too gentle (decrease toward 0.0).
    """
    state_samples = [r for r in metrics_data if r["metric_name"] == "wanctl_state"]
    if len(state_samples) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: %s skipped, only %d state samples (need %d)",
            wan_name,
            param_name,
            len(state_samples),
            MIN_SAMPLES,
        )
        return None

    episodes = _detect_recovery_episodes(metrics_data, direction)
    if not episodes:
        return None

    durations = [e.duration_sec for e in episodes]
    med_duration = median(durations)

    if med_duration < MEDIAN_DURATION_FAST_SEC:
        # Fast resolution: factor_down may be too aggressive, relax it
        candidate = current_value + FACTOR_ADJUSTMENT
    elif med_duration > MEDIAN_DURATION_SLOW_SEC:
        # Slow resolution: factor_down is too gentle, tighten it
        candidate = current_value - FACTOR_ADJUSTMENT
    else:
        return None

    # Clamp to bounds
    candidate = max(bounds.min_value, min(bounds.max_value, candidate))

    # Trivial change check for ratio params
    if abs(candidate - current_value) < 0.005:
        return None

    return TuningResult(
        parameter=param_name,
        old_value=current_value,
        new_value=round(candidate, 2),
        confidence=0.5,
        rationale=(
            f"median episode duration {med_duration:.0f}s: "
            f"{'relaxing' if candidate > current_value else 'tightening'} factor_down"
        ),
        data_points=len(episodes),
        wan_name=wan_name,
    )


def _tune_green_required_impl(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
    param_name: str,
    direction: str,
) -> TuningResult | None:
    """Tune green_required based on re-trigger rate analysis.

    RTUN-03: High re-trigger -> green_required too low (increase by 1).
    Low re-trigger with room to decrease -> green_required may be too high (decrease by 1).
    """
    state_samples = [r for r in metrics_data if r["metric_name"] == "wanctl_state"]
    if len(state_samples) < MIN_SAMPLES:
        logger.info(
            "[TUNING] %s: %s skipped, only %d state samples (need %d)",
            wan_name,
            param_name,
            len(state_samples),
            MIN_SAMPLES,
        )
        return None

    episodes = _detect_recovery_episodes(metrics_data, direction)
    if not episodes:
        return None

    re_trigger = _compute_re_trigger_rate(episodes)

    if re_trigger > RE_TRIGGER_HIGH:
        candidate = float(round(current_value) + 1)
    elif re_trigger < RE_TRIGGER_LOW and current_value > bounds.min_value:
        candidate = float(round(current_value) - 1)
    else:
        return None

    # Clamp to bounds
    candidate = max(bounds.min_value, min(bounds.max_value, candidate))

    # Ensure integer-valued float
    candidate = float(round(candidate))

    # No-change check
    if candidate == float(round(current_value)):
        return None

    return TuningResult(
        parameter=param_name,
        old_value=current_value,
        new_value=candidate,
        confidence=0.5,
        rationale=(
            f"re-trigger rate {re_trigger:.0%}: "
            f"{'increasing' if candidate > current_value else 'decreasing'} green_required"
        ),
        data_points=len(episodes),
        wan_name=wan_name,
    )


# ---------------------------------------------------------------------------
# Public StrategyFn-compatible functions (6 thin wrappers)
# ---------------------------------------------------------------------------


def tune_dl_step_up(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune download step_up_mbps from recovery episode re-trigger analysis (RTUN-01)."""
    return _tune_step_up_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="dl_step_up_mbps", direction="download",
    )


def tune_ul_step_up(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune upload step_up_mbps from recovery episode re-trigger analysis (RTUN-01)."""
    return _tune_step_up_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="ul_step_up_mbps", direction="download",
    )


def tune_dl_factor_down(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune download factor_down from congestion resolution speed (RTUN-02)."""
    return _tune_factor_down_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="dl_factor_down", direction="download",
    )


def tune_ul_factor_down(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune upload factor_down from congestion resolution speed (RTUN-02)."""
    return _tune_factor_down_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="ul_factor_down", direction="download",
    )


def tune_dl_green_required(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune download green_required from re-trigger rate analysis (RTUN-03)."""
    return _tune_green_required_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="dl_green_required", direction="download",
    )


def tune_ul_green_required(
    metrics_data: list[dict],
    current_value: float,
    bounds: SafetyBounds,
    wan_name: str,
) -> TuningResult | None:
    """Tune upload green_required from re-trigger rate analysis (RTUN-03)."""
    return _tune_green_required_impl(
        metrics_data, current_value, bounds, wan_name,
        param_name="ul_green_required", direction="download",
    )


# ---------------------------------------------------------------------------
# Oscillation lockout (RTUN-04)
# ---------------------------------------------------------------------------

OSCILLATION_LOCKOUT_SEC = 7200  # 2 hours
DEFAULT_OSCILLATION_THRESHOLD = 0.1  # transitions per minute (6/hour)


def check_oscillation_lockout(
    metrics_data: list[dict],
    locks: dict[str, float],
    oscillation_threshold: float = DEFAULT_OSCILLATION_THRESHOLD,
    alert_engine: Any = None,
    wan_name: str = "",
) -> bool:
    """Check state transition rate and lock all response params if oscillating.

    Counts state transitions in the last 60 minutes of wanctl_state data.
    If transitions/minute exceeds the threshold, locks ALL 6 RESPONSE_PARAMS
    for OSCILLATION_LOCKOUT_SEC (2 hours) and optionally fires a Discord alert.

    Args:
        metrics_data: List of metric dicts with timestamp, metric_name, value.
        locks: Parameter lock dict (modified in-place via lock_parameter).
        oscillation_threshold: Max transitions/minute before lockout (default 0.1).
        alert_engine: Optional AlertEngine instance for Discord alerts.
        wan_name: WAN name for logging/alerting.

    Returns:
        True if lockout was triggered, False otherwise.
    """
    # Extract state values by timestamp
    state_by_ts: dict[int, float] = {}
    for row in metrics_data:
        if row["metric_name"] == "wanctl_state":
            state_by_ts[row["timestamp"]] = row["value"]

    if len(state_by_ts) < 2:
        return False

    sorted_ts = sorted(state_by_ts.keys())

    # Count transitions in last 60 minutes
    cutoff = sorted_ts[-1] - 3600
    recent = [ts for ts in sorted_ts if ts >= cutoff]

    if len(recent) < 2:
        return False

    transitions = sum(
        1
        for i in range(1, len(recent))
        if state_by_ts[recent[i]] != state_by_ts[recent[i - 1]]
    )

    span_min = max(1, (recent[-1] - recent[0]) / 60)
    trans_per_min = transitions / span_min

    if trans_per_min <= oscillation_threshold:
        return False

    # Lock ALL response parameters
    for p in RESPONSE_PARAMS:
        lock_parameter(locks, p, OSCILLATION_LOCKOUT_SEC)

    logger.warning(
        "[TUNING] %s: oscillation lockout triggered (%.2f trans/min > %.2f), "
        "all response params locked for %ds",
        wan_name,
        trans_per_min,
        oscillation_threshold,
        OSCILLATION_LOCKOUT_SEC,
    )

    # Fire Discord alert if engine available
    if alert_engine is not None:
        try:
            alert_engine.fire(
                alert_type="oscillation_lockout",
                severity="warning",
                wan_name=wan_name,
                details={
                    "transitions_per_min": round(trans_per_min, 2),
                    "threshold": oscillation_threshold,
                    "locked_params": list(RESPONSE_PARAMS),
                    "lockout_sec": OSCILLATION_LOCKOUT_SEC,
                },
            )
        except Exception:
            pass  # Alert delivery failure must not crash daemon

    return True

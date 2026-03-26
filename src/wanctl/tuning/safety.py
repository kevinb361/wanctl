"""Tuning safety module -- congestion measurement, revert detection, hysteresis lock.

Provides pure-function safety primitives for the adaptive tuning engine:
- measure_congestion_rate: Fraction of time in congested state (SOFT_RED/RED)
- check_and_revert: Detect post-adjustment degradation, produce revert TuningResults
- PendingObservation: Frozen dataclass capturing pre-adjustment snapshot
- is_parameter_locked / lock_parameter: Hysteresis cooldown after reverts
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from wanctl.storage.reader import query_metrics
from wanctl.tuning.models import TuningResult

logger = logging.getLogger(__name__)

# Revert detection thresholds
DEFAULT_REVERT_THRESHOLD = 1.5  # 50% increase triggers revert
DEFAULT_MIN_CONGESTION_RATE = 0.05  # Below 5%, skip revert check
DEFAULT_REVERT_COOLDOWN_SEC = 86400  # 24 hours
MIN_OBSERVATION_SAMPLES = 10  # Minimum 1m samples needed


@dataclass(frozen=True, slots=True)
class PendingObservation:
    """Snapshot of state when a tuning adjustment was applied.

    Attributes:
        applied_ts: Unix timestamp when adjustment was applied.
        pre_congestion_rate: Congestion rate before adjustment.
        applied_results: Tuple of TuningResults that were applied (immutable).
    """

    applied_ts: int
    pre_congestion_rate: float
    applied_results: tuple[TuningResult, ...]


def measure_congestion_rate(
    db_path: Path | str,
    wan_name: str,
    start_ts: int,
    end_ts: int,
) -> float | None:
    """Measure the fraction of time in congested state (SOFT_RED or RED).

    Queries wanctl_state metric at 1m granularity and counts samples
    where state >= 2.0 (SOFT_RED=2, RED=3).

    Args:
        db_path: Path to SQLite metrics database.
        wan_name: WAN name to filter (e.g., "Spectrum").
        start_ts: Start timestamp (Unix seconds, inclusive).
        end_ts: End timestamp (Unix seconds, inclusive).

    Returns:
        Fraction of congested samples (0.0-1.0), or None if insufficient data.
    """
    rows = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan=wan_name,
        granularity="1m",
    )

    # Defensive filter: only wanctl_state rows
    state_values = [row["value"] for row in rows if row["metric_name"] == "wanctl_state"]

    if len(state_values) < MIN_OBSERVATION_SAMPLES:
        return None

    congested = sum(1 for v in state_values if v >= 2.0)
    return congested / len(state_values)


def check_and_revert(
    pending_observation: PendingObservation | None,
    db_path: Path | str,
    wan_name: str,
    revert_threshold: float = DEFAULT_REVERT_THRESHOLD,
    min_congestion_rate: float = DEFAULT_MIN_CONGESTION_RATE,
) -> list[TuningResult]:
    """Check if a previous tuning adjustment caused degradation and produce reverts.

    Compares post-adjustment congestion rate to pre-adjustment rate.
    If the ratio exceeds revert_threshold, produces revert TuningResults
    that swap old_value/new_value to undo the adjustment.

    Args:
        pending_observation: Snapshot from when adjustment was applied (None = skip).
        db_path: Path to SQLite metrics database.
        wan_name: WAN name to check.
        revert_threshold: Ratio threshold for triggering revert (default 1.5).
        min_congestion_rate: Minimum post rate to consider (default 0.05).

    Returns:
        List of revert TuningResults (empty if no revert needed).
    """
    if pending_observation is None:
        return []

    post_rate = measure_congestion_rate(
        db_path=db_path,
        wan_name=wan_name,
        start_ts=pending_observation.applied_ts,
        end_ts=int(time.time()),
    )

    if post_rate is None:
        return []

    if post_rate < min_congestion_rate:
        return []

    pre_rate = pending_observation.pre_congestion_rate
    # Avoid division by near-zero: use min_congestion_rate as floor
    denominator = pre_rate if pre_rate >= 0.001 else min_congestion_rate
    ratio = post_rate / denominator

    if ratio <= revert_threshold:
        return []

    # Build revert TuningResults: swap old_value/new_value
    reverts: list[TuningResult] = []
    for original in pending_observation.applied_results:
        revert = TuningResult(
            parameter=original.parameter,
            old_value=original.new_value,  # Current value is the applied new_value
            new_value=original.old_value,  # Revert to the original old_value
            confidence=1.0,  # Reverts are authoritative
            rationale=(
                f"REVERT: congestion rate {pre_rate:.2%}->{post_rate:.2%} "
                f"(ratio {ratio:.1f}x > {revert_threshold}x)"
            ),
            data_points=0,  # Reverts are not data-driven
            wan_name=original.wan_name,
        )
        reverts.append(revert)

    logger.warning(
        "[TUNING] %s: reverting %d adjustment(s), congestion %s->%s (%.1fx)",
        wan_name,
        len(reverts),
        f"{pre_rate:.2%}",
        f"{post_rate:.2%}",
        ratio,
    )

    return reverts


def is_parameter_locked(locks: dict[str, float], parameter: str) -> bool:
    """Check if a parameter is in hysteresis cooldown.

    Operates on caller-provided dict so WANController owns the state.

    Args:
        locks: Dict mapping parameter name to monotonic expiry time.
        parameter: Parameter name to check.

    Returns:
        True if locked (cooldown active), False if unlocked or expired.
    """
    expiry = locks.get(parameter)
    if expiry is None:
        return False
    if time.monotonic() >= expiry:
        del locks[parameter]
        return False
    return True


def lock_parameter(locks: dict[str, float], parameter: str, cooldown_sec: float) -> None:
    """Lock a parameter for a cooldown period after revert.

    Operates on caller-provided dict so WANController owns the state.

    Args:
        locks: Dict mapping parameter name to monotonic expiry time.
        parameter: Parameter name to lock.
        cooldown_sec: Cooldown duration in seconds.
    """
    locks[parameter] = time.monotonic() + cooldown_sec

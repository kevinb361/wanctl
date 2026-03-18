"""Tuning analyzer -- per-WAN metric query and strategy orchestration.

Queries historical metrics from SQLite, runs registered strategies,
and returns TuningResult list for the applier to process.
"""

import logging
import time
from typing import Callable

from wanctl.storage.reader import query_metrics
from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult

logger = logging.getLogger(__name__)

# Type alias for strategy functions (pure functions, not classes)
StrategyFn = Callable[[list[dict], float, SafetyBounds, str], TuningResult | None]


def _query_wan_metrics(
    db_path: str,
    wan_name: str,
    lookback_hours: int,
) -> list[dict]:
    """Query 1m-granularity metrics for a single WAN."""
    now_ts = int(time.time())
    start_ts = now_ts - (lookback_hours * 3600)
    return query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        wan=wan_name,
        granularity="1m",
    )


def _check_warmup(
    metrics_data: list[dict],
    warmup_hours: int,
    wan_name: str,
) -> bool:
    """Check if enough data exists for tuning analysis.

    Returns True if sufficient data, False otherwise.
    """
    if not metrics_data:
        logger.info("[TUNING] %s: skipping, no metrics data", wan_name)
        return False

    timestamps = [m["timestamp"] for m in metrics_data if "timestamp" in m]
    if not timestamps:
        logger.info("[TUNING] %s: skipping, no timestamped data", wan_name)
        return False

    earliest = min(timestamps)
    now_ts = int(time.time())
    data_hours = (now_ts - earliest) / 3600.0

    if data_hours < warmup_hours:
        logger.info(
            "[TUNING] %s: skipping, only %.0f minutes of data (need %d hours)",
            wan_name,
            data_hours * 60,
            warmup_hours,
        )
        return False

    return True


def _compute_data_hours(metrics_data: list[dict]) -> float:
    """Compute hours of data span from metrics timestamps."""
    timestamps = [m["timestamp"] for m in metrics_data if "timestamp" in m]
    if len(timestamps) < 2:
        return 0.0
    return (max(timestamps) - min(timestamps)) / 3600.0


def run_tuning_analysis(
    wan_name: str,
    db_path: str,
    tuning_config: TuningConfig,
    current_params: dict[str, float],
    strategies: list[tuple[str, StrategyFn]],
) -> list[TuningResult]:
    """Run tuning analysis for a single WAN.

    Args:
        wan_name: WAN identifier (e.g., "Spectrum")
        db_path: Path to metrics SQLite database
        tuning_config: Validated tuning configuration
        current_params: Current parameter values {name: value}
        strategies: List of (parameter_name, strategy_fn) tuples

    Returns:
        List of TuningResult for parameters that should change.
        Empty list if no changes needed or insufficient data.
    """
    if not strategies:
        return []

    # Query metrics for this WAN
    metrics_data = _query_wan_metrics(db_path, wan_name, tuning_config.lookback_hours)

    # Check warmup
    if not _check_warmup(metrics_data, tuning_config.warmup_hours, wan_name):
        return []

    data_hours = _compute_data_hours(metrics_data)
    confidence_scale = min(1.0, data_hours / 24.0)

    results: list[TuningResult] = []

    for param_name, strategy_fn in strategies:
        current_value = current_params.get(param_name)
        if current_value is None:
            logger.debug(
                "[TUNING] %s: no current value for %s, skipping",
                wan_name,
                param_name,
            )
            continue

        bounds = tuning_config.bounds.get(param_name)
        if bounds is None:
            logger.debug(
                "[TUNING] %s: no bounds for %s, skipping", wan_name, param_name
            )
            continue

        try:
            result = strategy_fn(metrics_data, current_value, bounds, wan_name)
            if result is not None:
                # Scale confidence by data availability
                scaled_result = TuningResult(
                    parameter=result.parameter,
                    old_value=result.old_value,
                    new_value=result.new_value,
                    confidence=round(result.confidence * confidence_scale, 3),
                    rationale=result.rationale,
                    data_points=result.data_points,
                    wan_name=result.wan_name,
                )
                results.append(scaled_result)
        except Exception:
            logger.warning(
                "[TUNING] %s: strategy for %s failed",
                wan_name,
                param_name,
                exc_info=True,
            )

    return results

"""Tuning applier -- bounds enforcement, persistence, and logging.

Receives TuningResult list from analyzer, clamps to bounds + max_step,
persists to SQLite, logs changes, and returns applied results.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from wanctl.tuning.models import TuningConfig, TuningResult, clamp_to_step

if TYPE_CHECKING:
    from wanctl.storage.writer import MetricsWriter

logger = logging.getLogger(__name__)


def persist_tuning_result(
    result: TuningResult,
    writer: MetricsWriter | None,
) -> int | None:
    """Persist a tuning adjustment to SQLite tuning_params table.

    Args:
        result: The tuning result to persist
        writer: MetricsWriter instance (or None if storage disabled)

    Returns:
        Row ID on success, None on failure or storage disabled.
    """
    if writer is None:
        return None
    try:
        ts = int(time.time())
        cursor = writer.connection.execute(
            "INSERT INTO tuning_params "
            "(timestamp, wan_name, parameter, old_value, new_value, "
            "confidence, rationale, data_points) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts,
                result.wan_name,
                result.parameter,
                result.old_value,
                result.new_value,
                result.confidence,
                result.rationale,
                result.data_points,
            ),
        )
        return cursor.lastrowid
    except Exception:
        logger.warning(
            "Failed to persist tuning result %s on %s",
            result.parameter,
            result.wan_name,
            exc_info=True,
        )
        return None


def persist_revert_record(
    result: TuningResult,
    writer: MetricsWriter | None,
) -> int | None:
    """Persist a revert to tuning_params table with reverted=1.

    Same as persist_tuning_result but sets reverted=1 to mark this
    as an automatic revert rather than a forward adjustment.

    Args:
        result: The revert TuningResult to persist.
        writer: MetricsWriter instance (or None if storage disabled).

    Returns:
        Row ID on success, None on failure or storage disabled.
    """
    if writer is None:
        return None
    try:
        ts = int(time.time())
        cursor = writer.connection.execute(
            "INSERT INTO tuning_params "
            "(timestamp, wan_name, parameter, old_value, new_value, "
            "confidence, rationale, data_points, reverted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                ts,
                result.wan_name,
                result.parameter,
                result.old_value,
                result.new_value,
                result.confidence,
                result.rationale,
                result.data_points,
            ),
        )
        return cursor.lastrowid
    except Exception:
        logger.warning(
            "Failed to persist revert for %s on %s",
            result.parameter,
            result.wan_name,
            exc_info=True,
        )
        return None


def apply_tuning_results(
    results: list[TuningResult],
    tuning_config: TuningConfig,
    writer: MetricsWriter | None = None,
) -> list[TuningResult]:
    """Apply tuning results with bounds enforcement and persistence.

    For each result:
    1. Clamp new_value to safety bounds + max_step_pct
    2. Skip trivial changes (abs difference < 0.1)
    3. Log at WARNING with old->new and rationale
    4. Persist to SQLite
    5. Return list of actually-applied results (post-clamp)

    Args:
        results: TuningResult list from analyzer
        tuning_config: Config with bounds and max_step_pct
        writer: MetricsWriter for persistence (None = skip persist)

    Returns:
        List of TuningResult that were actually applied (post-clamp).
    """
    if not results:
        return []

    applied: list[TuningResult] = []

    for result in results:
        bounds = tuning_config.bounds.get(result.parameter)
        if bounds is None:
            logger.debug(
                "[TUNING] %s: no bounds for %s, skipping apply",
                result.wan_name,
                result.parameter,
            )
            continue

        # Clamp to bounds + max step
        clamped_value = clamp_to_step(
            current=result.old_value,
            candidate=result.new_value,
            max_step_pct=tuning_config.max_step_pct,
            bounds=bounds,
        )

        # Skip trivial changes
        if abs(clamped_value - result.old_value) < 0.1:
            logger.debug(
                "[TUNING] %s: %s trivial change %.1f->%.1f, skipping",
                result.wan_name,
                result.parameter,
                result.old_value,
                clamped_value,
            )
            continue

        # Create post-clamp result
        applied_result = TuningResult(
            parameter=result.parameter,
            old_value=result.old_value,
            new_value=clamped_value,
            confidence=result.confidence,
            rationale=result.rationale,
            data_points=result.data_points,
            wan_name=result.wan_name,
        )

        # Log at WARNING (same level as SIGUSR1 transitions)
        logger.warning(
            "[TUNING] %s: %s %.1f->%.1f (%s)",
            applied_result.wan_name,
            applied_result.parameter,
            applied_result.old_value,
            applied_result.new_value,
            applied_result.rationale,
        )

        # Persist to SQLite
        persist_tuning_result(applied_result, writer)

        applied.append(applied_result)

    return applied

"""Select direction-specific congestion state samples from mixed metrics history."""

from __future__ import annotations

import json
from typing import Any


def _identity_priority(labels: object, direction: str) -> int | None:
    """Rank a legacy state row for one direction, or reject another identity."""
    if labels in (None, ""):
        return 1
    parsed: object = labels
    if isinstance(labels, str):
        try:
            parsed = json.loads(labels)
        except json.JSONDecodeError:
            # Preserve historical fallback for malformed old labels, but let
            # any valid legacy/directional row at the timestamp outrank it.
            return 0
    if not isinstance(parsed, dict):
        return 0
    row_direction = parsed.get("direction")
    if row_direction == direction:
        return 2
    if row_direction is not None or parsed.get("source") is not None:
        return None
    return 1


def state_rows_for_direction(
    metrics_data: list[dict[str, Any]], direction: str
) -> list[dict[str, Any]]:
    """Return one best state row per timestamp for ``direction``.

    Durable direction-specific metric names take precedence globally. Legacy
    ``wanctl_state`` rows are then selected by identity labels, with a labeled
    direction outranking an unlabeled historical row at the same timestamp.
    Sibling directions and steering state are never borrowed.
    """
    metric_name = f"wanctl_state_{direction}"
    directional = [row for row in metrics_data if row.get("metric_name") == metric_name]
    if directional:
        return list({row["timestamp"]: row for row in directional}.values())
    if any(
        row.get("metric_name") in {"wanctl_state_download", "wanctl_state_upload"}
        for row in metrics_data
    ):
        return []

    selected: dict[int, tuple[int, dict[str, Any]]] = {}
    for row in metrics_data:
        if row.get("metric_name") != "wanctl_state":
            continue
        priority = _identity_priority(row.get("labels"), direction)
        if priority is None:
            continue
        timestamp = row["timestamp"]
        previous = selected.get(timestamp)
        if previous is None or priority > previous[0]:
            selected[timestamp] = (priority, row)
    return [ranked_row[1] for ranked_row in selected.values()]

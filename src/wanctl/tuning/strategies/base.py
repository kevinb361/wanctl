"""Tuning strategy protocol for parameter optimization.

Defines the interface that all tuning strategies must implement.
Concrete strategies (e.g., percentile-based, trend-based) will be
added in Phase 99+.
"""

from __future__ import annotations

from typing import Protocol

from wanctl.tuning.models import SafetyBounds, TuningResult


class TuningStrategy(Protocol):
    """Protocol for tuning strategy implementations.

    Each strategy analyzes historical metrics data and proposes parameter
    adjustments. Returns None if no adjustment is warranted.
    """

    def analyze(
        self,
        metrics_data: list[dict],
        current_value: float,
        bounds: SafetyBounds,
    ) -> TuningResult | None: ...

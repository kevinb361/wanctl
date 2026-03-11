"""Cycle budget gauge widget for utilization visualization.

Provides CycleBudgetGaugeWidget with a ProgressBar showing the percentage
of the 50ms cycle budget used by the autorate daemon.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ProgressBar, Static


class CycleBudgetGaugeWidget(Widget):
    """Gauge showing cycle budget utilization as a progress bar.

    Displays the percentage of the 50ms cycle budget consumed by the
    autorate daemon. Updated from health endpoint cycle_budget data.
    """

    DEFAULT_CSS = """
    CycleBudgetGaugeWidget {
        height: auto;
        min-height: 2;
        padding: 0 1;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._utilization_pct: float = 0

    def compose(self) -> ComposeResult:
        """Yield label and progress bar."""
        yield Static("Cycle Budget")
        yield ProgressBar(total=100, show_eta=False, id="cycle-gauge")

    def update_utilization(self, utilization_pct: float | None) -> None:
        """Update the gauge with new utilization percentage.

        Args:
            utilization_pct: Percentage of cycle budget used (0-100).
                If None, treats as 0%.
        """
        if utilization_pct is None:
            utilization_pct = 0
        self._utilization_pct = utilization_pct

        try:
            bar = self.query_one("#cycle-gauge", ProgressBar)
            bar.update(progress=utilization_pct)
        except Exception:
            pass

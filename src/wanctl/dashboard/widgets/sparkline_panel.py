"""Sparkline trend panel widget for WAN rate and RTT delta visualization.

Provides SparklinePanelWidget with 3 Sparkline children (DL, UL, RTT delta)
and bounded deques to ensure constant memory regardless of runtime.
"""

from __future__ import annotations

from collections import deque

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Sparkline, Static


class SparklinePanelWidget(Widget):
    """Panel showing DL/UL rate sparklines and RTT delta trend.

    Uses bounded deques (default maxlen=120 ~ 2min at 1Hz polling) to keep
    memory constant. RTT delta sparkline uses green-to-red gradient to
    highlight congestion visually.
    """

    DEFAULT_CSS = """
    SparklinePanelWidget {
        height: auto;
        min-height: 5;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        maxlen: int = 120,
        *,
        wan_name: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._wan_name = wan_name
        self._maxlen = maxlen
        self._dl_data: deque[float] = deque(maxlen=maxlen)
        self._ul_data: deque[float] = deque(maxlen=maxlen)
        self._rtt_delta_data: deque[float] = deque(maxlen=maxlen)
        # RTT gradient config (accessible for testing before compose)
        self._rtt_min_color = "green"
        self._rtt_max_color = "red"

    def compose(self) -> ComposeResult:
        """Yield label and 3 sparkline widgets."""
        yield Static(f"Trends: {self._wan_name}")
        yield Sparkline(id="dl-spark", min_color="yellow", max_color="green")
        yield Sparkline(id="ul-spark", min_color="yellow", max_color="green")
        yield Sparkline(
            id="rtt-spark",
            min_color=self._rtt_min_color,
            max_color=self._rtt_max_color,
        )

    def append_data(
        self, dl_rate: float, ul_rate: float, rtt_delta: float
    ) -> None:
        """Append new data points and update sparkline reactives."""
        self._dl_data.append(dl_rate)
        self._ul_data.append(ul_rate)
        self._rtt_delta_data.append(rtt_delta)

        # Update sparkline data reactives (triggers re-render)
        try:
            dl_spark = self.query_one("#dl-spark", Sparkline)
            dl_spark.data = list(self._dl_data)
        except Exception:
            pass

        try:
            ul_spark = self.query_one("#ul-spark", Sparkline)
            ul_spark.data = list(self._ul_data)
        except Exception:
            pass

        try:
            rtt_spark = self.query_one("#rtt-spark", Sparkline)
            rtt_spark.data = list(self._rtt_delta_data)
        except Exception:
            pass

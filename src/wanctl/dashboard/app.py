"""Dashboard CLI entry point and Textual application.

Provides the wanctl-dashboard command, DashboardApp (Textual App subclass),
and Textual Widget wrappers for the render-only widget classes from Plan 02.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import httpx
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import TabbedContent, TabPane

from wanctl.dashboard.config import (
    DashboardConfig,
    apply_cli_overrides,
    load_dashboard_config,
)
from wanctl.dashboard.poller import EndpointPoller
from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget
from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget
from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget
from wanctl.dashboard.widgets.status_bar import StatusBar
from wanctl.dashboard.widgets.steering_panel import SteeringPanel
from wanctl.dashboard.widgets.wan_panel import WanPanel


class WanPanelWidget(Widget):
    """Textual Widget wrapper for WanPanel renderer.

    Delegates rendering to the plain WanPanel class which returns Rich Text.
    """

    DEFAULT_CSS = """
    WanPanelWidget {
        height: auto;
        min-height: 5;
        border: solid green;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        wan_name: str = "",
        rate_limits: dict[str, float] | None = None,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._renderer = WanPanel(wan_name=wan_name, rate_limits=rate_limits)

    def update_from_data(
        self,
        wan_data: dict | None,
        status: str | None = None,
        last_seen: datetime | None = None,
    ) -> None:
        """Forward data update to the renderer and refresh display."""
        self._renderer.update_from_data(wan_data, status=status, last_seen=last_seen)
        self.refresh()

    def render(self) -> Text:
        """Render via the WanPanel renderer."""
        return self._renderer.render()


class SteeringPanelWidget(Widget):
    """Textual Widget wrapper for SteeringPanel renderer.

    Delegates rendering to the plain SteeringPanel class which returns Rich Text.
    """

    DEFAULT_CSS = """
    SteeringPanelWidget {
        height: auto;
        min-height: 5;
        border: solid cyan;
        padding: 0 1;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._renderer = SteeringPanel()

    def update_from_data(
        self,
        data: dict | None,
        last_seen: datetime | None = None,
    ) -> None:
        """Forward data update to the renderer and refresh display."""
        self._renderer.update_from_data(data, last_seen=last_seen)
        self.refresh()

    def render(self) -> Text:
        """Render via the SteeringPanel renderer."""
        return self._renderer.render()


class StatusBarWidget(Widget):
    """Textual Widget wrapper for StatusBar renderer.

    Delegates rendering to the plain StatusBar class which returns Rich Text.
    """

    DEFAULT_CSS = """
    StatusBarWidget {
        height: 1;
        dock: bottom;
        background: $surface;
        color: $text;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._renderer = StatusBar()

    def update_status(
        self, version: str, uptime_seconds: float, disk_status: str
    ) -> None:
        """Forward status update to the renderer and refresh display."""
        self._renderer.update(
            version=version, uptime_seconds=uptime_seconds, disk_status=disk_status
        )
        self.refresh()

    def render(self) -> Text:
        """Render via the StatusBar renderer."""
        return self._renderer.render()


BREAKPOINT_WIDE = 120
HYSTERESIS_DELAY = 0.3


class DashboardApp(App):
    """Textual TUI application for wanctl monitoring.

    Composes WAN panels, steering panel, and status bar in a responsive layout.
    Wide terminals (>=120 cols) show WAN panels side-by-side; narrow terminals
    stack them vertically. Polls health endpoints at the configured interval.
    """

    CSS_PATH = "dashboard.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, config: DashboardConfig) -> None:
        super().__init__()
        self.config = config
        self._autorate_poller = EndpointPoller(
            "autorate",
            config.autorate_url,
            normal_interval=config.refresh_interval,
        )
        self._steering_poller = EndpointPoller(
            "steering",
            config.steering_url,
            normal_interval=config.refresh_interval,
        )
        self._secondary_autorate_poller: EndpointPoller | None = None
        if config.secondary_autorate_url:
            self._secondary_autorate_poller = EndpointPoller(
                "autorate-secondary",
                config.secondary_autorate_url,
                normal_interval=config.refresh_interval,
            )
        self._client: httpx.AsyncClient | None = None
        self._layout_mode: str = ""
        self._resize_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the dashboard widget tree with Live/History tabs."""
        with TabbedContent(initial="live"):
            with TabPane("Live", id="live"):
                with Horizontal(id="wan-row"):
                    with Vertical(id="wan-col-1", classes="wan-col"):
                        yield WanPanelWidget("WAN 1 (Spectrum)", id="wan-1")
                        yield SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
                        yield CycleBudgetGaugeWidget(id="gauge-wan-1")
                    with Vertical(id="wan-col-2", classes="wan-col"):
                        yield WanPanelWidget("WAN 2 (ATT)", id="wan-2")
                        yield SparklinePanelWidget(wan_name="WAN 2", id="spark-wan-2")
                        yield CycleBudgetGaugeWidget(id="gauge-wan-2")
                yield SteeringPanelWidget(id="steering")
            with TabPane("History", id="history"):
                yield HistoryBrowserWidget(
                    autorate_url=self.config.autorate_url,
                    id="history-browser",
                )
        yield StatusBarWidget(id="status-bar")

    async def on_mount(self) -> None:
        """Initialize HTTP client, start polling timers, and set initial layout."""
        self._client = httpx.AsyncClient(timeout=2.0)
        self.set_interval(self.config.refresh_interval, self._poll_autorate)
        self.set_interval(self.config.refresh_interval, self._poll_steering)
        if self._secondary_autorate_poller is not None:
            self.set_interval(
                self.config.refresh_interval, self._poll_secondary_autorate
            )
        self._apply_layout()

    def on_resize(self, event: Resize) -> None:
        """Debounced layout switch on terminal resize."""
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(
            HYSTERESIS_DELAY, self._apply_layout
        )

    def _apply_layout(self) -> None:
        """Switch layout based on current terminal width."""
        new_mode = "wide" if self.size.width >= BREAKPOINT_WIDE else "narrow"
        if new_mode == self._layout_mode:
            return
        self._layout_mode = new_mode
        wan_row = self.query_one("#wan-row")
        wan_row.set_class(new_mode == "wide", "wide-layout")
        wan_row.set_class(new_mode == "narrow", "narrow-layout")

    async def on_unmount(self) -> None:
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()

    def _route_wan_data(
        self, wan_data: dict | None, wan_num: int, full_response: dict | None
    ) -> None:
        """Route WAN data to panel, sparkline, and gauge for the given WAN number."""
        wan_widget = self.query_one(f"#wan-{wan_num}", WanPanelWidget)
        if wan_data is None:
            wan_widget.update_from_data(None)
            return

        status = full_response.get("status") if full_response else None
        if wan_num == 1:
            last_seen = self._autorate_poller.last_seen
        else:
            last_seen = (
                self._secondary_autorate_poller.last_seen
                if self._secondary_autorate_poller
                else self._autorate_poller.last_seen
            )
        wan_widget.update_from_data(wan_data, status=status, last_seen=last_seen)

        dl_rate = wan_data.get("download", {}).get("current_rate_mbps", 0)
        ul_rate = wan_data.get("upload", {}).get("current_rate_mbps", 0)
        baseline_rtt = wan_data.get("baseline_rtt_ms", 0)
        load_rtt = wan_data.get("load_rtt_ms", 0)
        rtt_delta = max(0, load_rtt - baseline_rtt)

        spark = self.query_one(f"#spark-wan-{wan_num}", SparklinePanelWidget)
        spark.append_data(dl_rate, ul_rate, rtt_delta)

        cycle_budget = wan_data.get("cycle_budget")
        if cycle_budget is not None:
            gauge = self.query_one(
                f"#gauge-wan-{wan_num}", CycleBudgetGaugeWidget
            )
            gauge.update_utilization(cycle_budget.get("utilization_pct", 0))

    async def _poll_autorate(self) -> None:
        """Poll primary autorate endpoint and route data to WAN panels."""
        if self._client is None:
            return

        data = await self._autorate_poller.poll(self._client)
        wan1 = self.query_one("#wan-1", WanPanelWidget)
        wan2 = self.query_one("#wan-2", WanPanelWidget)

        if data and "wans" in data:
            wans = data["wans"]
            if self._secondary_autorate_poller is not None:
                # Dual mode: primary handles only WAN 1
                self._route_wan_data(wans[0] if wans else None, 1, data)
            else:
                # Single mode: primary handles both WANs (existing behavior)
                for i, wan_data in enumerate(wans[:2]):
                    self._route_wan_data(wan_data, i + 1, data)

            status_bar = self.query_one("#status-bar", StatusBarWidget)
            status_bar.update_status(
                version=data.get("version", "?"),
                uptime_seconds=data.get("uptime_seconds", 0),
                disk_status=data.get("disk_space", {}).get("status", "unknown"),
            )
        else:
            wan1.update_from_data(None, last_seen=self._autorate_poller.last_seen)
            if self._secondary_autorate_poller is None:
                wan2.update_from_data(
                    None, last_seen=self._autorate_poller.last_seen
                )

    async def _poll_secondary_autorate(self) -> None:
        """Poll secondary autorate endpoint and route data to WAN 2 panel."""
        if self._client is None or self._secondary_autorate_poller is None:
            return

        data = await self._secondary_autorate_poller.poll(self._client)
        wan2 = self.query_one("#wan-2", WanPanelWidget)

        if data and "wans" in data:
            wans = data["wans"]
            if wans:
                self._route_wan_data(wans[0], 2, data)
        else:
            wan2.update_from_data(
                None, last_seen=self._secondary_autorate_poller.last_seen
            )

    async def _poll_steering(self) -> None:
        """Poll steering endpoint and route data to steering panel."""
        if self._client is None:
            return

        data = await self._steering_poller.poll(self._client)
        panel = self.query_one("#steering", SteeringPanelWidget)
        if data:
            panel.update_from_data(data, last_seen=self._steering_poller.last_seen)
        else:
            panel.update_from_data(None, last_seen=self._steering_poller.last_seen)

    async def action_refresh(self) -> None:
        """Handle 'r' keybinding: force immediate refresh of all endpoints."""
        await self._poll_autorate()
        if self._secondary_autorate_poller is not None:
            await self._poll_secondary_autorate()
        await self._poll_steering()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for wanctl-dashboard."""
    parser = argparse.ArgumentParser(
        prog="wanctl-dashboard",
        description="TUI dashboard for wanctl monitoring",
    )
    parser.add_argument(
        "--autorate-url",
        default=None,
        help="Autorate health endpoint URL (default: http://127.0.0.1:9101)",
    )
    parser.add_argument(
        "--steering-url",
        default=None,
        help="Steering health endpoint URL (default: http://127.0.0.1:9102)",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=None,
        help="Polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--secondary-autorate-url",
        default=None,
        help="Secondary autorate health endpoint URL for WAN 2 (default: disabled)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to dashboard config file",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable all color output",
    )
    parser.add_argument(
        "--256-color",
        action="store_true",
        dest="color_256",
        help="Use 256-color mode (for limited terminals)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for wanctl-dashboard CLI."""
    args = parse_args(argv)

    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    elif args.color_256:
        os.environ["TEXTUAL_COLOR_SYSTEM"] = "256"

    config = load_dashboard_config(Path(args.config) if args.config else None)
    config = apply_cli_overrides(config, args)
    app = DashboardApp(config)
    app.run()


if __name__ == "__main__":
    main()

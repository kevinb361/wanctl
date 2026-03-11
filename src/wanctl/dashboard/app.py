"""Dashboard CLI entry point and Textual application.

Provides the wanctl-dashboard command, DashboardApp (Textual App subclass),
and Textual Widget wrappers for the render-only widget classes from Plan 02.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import httpx
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget

from wanctl.dashboard.config import (
    DashboardConfig,
    apply_cli_overrides,
    load_dashboard_config,
)
from wanctl.dashboard.poller import EndpointPoller
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


class DashboardApp(App):
    """Textual TUI application for wanctl monitoring.

    Composes WAN panels, steering panel, and status bar in a vertical layout.
    Polls health endpoints at the configured interval and routes data to widgets.
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
        self._client: httpx.AsyncClient | None = None

    def compose(self) -> ComposeResult:
        """Compose the dashboard widget tree."""
        with Vertical():
            yield WanPanelWidget("WAN 1 (Spectrum)", id="wan-1")
            yield WanPanelWidget("WAN 2 (ATT)", id="wan-2")
            yield SteeringPanelWidget(id="steering")
            yield StatusBarWidget(id="status-bar")

    async def on_mount(self) -> None:
        """Initialize HTTP client and start polling timers."""
        self._client = httpx.AsyncClient(timeout=2.0)
        self.set_interval(self.config.refresh_interval, self._poll_autorate)
        self.set_interval(self.config.refresh_interval, self._poll_steering)

    async def on_unmount(self) -> None:
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()

    async def _poll_autorate(self) -> None:
        """Poll autorate endpoint and route data to WAN panels and status bar."""
        if self._client is None:
            return

        data = await self._autorate_poller.poll(self._client)
        wan1 = self.query_one("#wan-1", WanPanelWidget)
        wan2 = self.query_one("#wan-2", WanPanelWidget)

        if data and "wans" in data:
            wans = data["wans"]
            if len(wans) >= 1:
                wan1.update_from_data(
                    wans[0],
                    status=data.get("status"),
                    last_seen=self._autorate_poller.last_seen,
                )
            if len(wans) >= 2:
                wan2.update_from_data(
                    wans[1],
                    status=data.get("status"),
                    last_seen=self._autorate_poller.last_seen,
                )
            status_bar = self.query_one("#status-bar", StatusBarWidget)
            status_bar.update_status(
                version=data.get("version", "?"),
                uptime_seconds=data.get("uptime_seconds", 0),
                disk_status=data.get("disk_space", {}).get("status", "unknown"),
            )
        else:
            wan1.update_from_data(None, last_seen=self._autorate_poller.last_seen)
            wan2.update_from_data(None, last_seen=self._autorate_poller.last_seen)

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
        "--config",
        type=str,
        default=None,
        help="Path to dashboard config file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for wanctl-dashboard CLI."""
    args = parse_args(argv)
    config = load_dashboard_config(Path(args.config) if args.config else None)
    config = apply_cli_overrides(config, args)
    app = DashboardApp(config)
    app.run()


if __name__ == "__main__":
    main()

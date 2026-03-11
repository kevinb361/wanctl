"""Tests for DashboardApp composition, polling, keybindings, and CSS."""

import asyncio
from unittest.mock import AsyncMock

from wanctl.dashboard.config import DashboardConfig


def _make_autorate_response(
    wans_count: int = 2,
    dl_state: str = "GREEN",
    version: str = "1.13.0",
    uptime: float = 3600,
    disk_status: str = "ok",
    include_cycle_budget: bool = True,
) -> dict:
    """Build sample autorate health response."""
    wans = []
    names = ["spectrum", "att"]
    utilization_pcts = [70.4, 56.2]
    for i in range(wans_count):
        wan = {
            "name": names[i] if i < len(names) else f"wan{i}",
            "baseline_rtt_ms": 12.3,
            "load_rtt_ms": 18.7,
            "download": {"current_rate_mbps": 245.0, "state": dl_state},
            "upload": {"current_rate_mbps": 10.5, "state": "GREEN"},
            "router_connectivity": True,
        }
        if include_cycle_budget:
            wan["cycle_budget"] = {
                "used_ms": 35.2 if i == 0 else 28.1,
                "budget_ms": 50.0,
                "utilization_pct": utilization_pcts[i] if i < 2 else 50.0,
            }
        wans.append(wan)
    return {
        "status": "healthy",
        "version": version,
        "uptime_seconds": uptime,
        "wan_count": wans_count,
        "wans": wans,
        "disk_space": {"status": disk_status, "free_pct": 50.0},
    }


def _make_steering_response(
    enabled: bool = True,
    confidence: float = 72.5,
) -> dict:
    """Build sample steering health response."""
    return {
        "status": "healthy",
        "steering": {"enabled": enabled, "state": "monitoring", "mode": "active"},
        "confidence": {"primary": confidence},
        "wan_awareness": {
            "enabled": True,
            "zone": "GREEN",
            "effective_zone": "GREEN",
            "grace_period_active": False,
            "confidence_contribution": 25.0,
        },
        "decision": {
            "last_transition_time": "2026-03-11T12:00:00Z",
            "time_in_state_seconds": 120.5,
        },
    }


class TestDashboardAppComposition:
    """Test DashboardApp.compose() yields the correct widget tree."""

    def test_compose_yields_two_wan_panels(self):
        """DashboardApp.compose() yields 2 WanPanel wrapper widgets."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                wan_panels = app.query(WanPanelWidget)
                assert len(wan_panels) == 2

        asyncio.run(_test())

    def test_compose_yields_one_steering_panel(self):
        """DashboardApp.compose() yields 1 SteeringPanel wrapper widget."""
        from wanctl.dashboard.app import DashboardApp, SteeringPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                steering_panels = app.query(SteeringPanelWidget)
                assert len(steering_panels) == 1

        asyncio.run(_test())

    def test_compose_yields_one_status_bar(self):
        """DashboardApp.compose() yields 1 StatusBar wrapper widget."""
        from wanctl.dashboard.app import DashboardApp, StatusBarWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                status_bars = app.query(StatusBarWidget)
                assert len(status_bars) == 1

        asyncio.run(_test())

    def test_compose_vertical_layout_has_all_widgets(self):
        """Widgets are arranged with correct IDs."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                wan1 = app.query_one("#wan-1")
                wan2 = app.query_one("#wan-2")
                steering = app.query_one("#steering")
                status_bar = app.query_one("#status-bar")
                assert wan1 is not None
                assert wan2 is not None
                assert steering is not None
                assert status_bar is not None

        asyncio.run(_test())


class TestDashboardAppBindings:
    """Test DashboardApp keybindings."""

    def test_bindings_include_quit(self):
        """DashboardApp BINDINGS includes q for quit."""
        from wanctl.dashboard.app import DashboardApp

        config = DashboardConfig()
        app = DashboardApp(config)
        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys

    def test_bindings_include_refresh(self):
        """DashboardApp BINDINGS includes r for refresh."""
        from wanctl.dashboard.app import DashboardApp

        config = DashboardConfig()
        app = DashboardApp(config)
        binding_keys = [b.key for b in app.BINDINGS]
        assert "r" in binding_keys


class TestDashboardAppHttpClient:
    """Test DashboardApp creates httpx.AsyncClient on mount."""

    def test_creates_client_on_mount(self):
        """DashboardApp creates httpx.AsyncClient when mounted."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                assert app._client is not None

        asyncio.run(_test())


class TestDashboardAppPolling:
    """Test poll callback routing."""

    def test_action_refresh_triggers_both_polls(self):
        """action_refresh triggers immediate poll of all endpoints."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                app._autorate_poller.poll = AsyncMock(
                    return_value=_make_autorate_response()
                )
                app._steering_poller.poll = AsyncMock(
                    return_value=_make_steering_response()
                )
                await app.action_refresh()
                app._autorate_poller.poll.assert_called_once()
                app._steering_poller.poll.assert_called_once()

        asyncio.run(_test())

    def test_poll_routes_autorate_wans_to_wan_panels(self):
        """Poll callback routes autorate response wans[0] to WanPanel 1."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                wan1 = app.query_one("#wan-1", WanPanelWidget)
                assert wan1._renderer._data is not None
                assert wan1._renderer._data["name"] == "spectrum"

        asyncio.run(_test())

    def test_poll_routes_steering_to_steering_panel(self):
        """Poll callback routes steering response to SteeringPanel."""
        from wanctl.dashboard.app import DashboardApp, SteeringPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_steering_response()
                app._steering_poller.poll = AsyncMock(return_value=response)
                await app._poll_steering()
                panel = app.query_one("#steering", SteeringPanelWidget)
                assert panel._renderer._data is not None

        asyncio.run(_test())

    def test_poll_updates_status_bar(self):
        """Poll callback updates StatusBar with version, uptime, disk status."""
        from wanctl.dashboard.app import DashboardApp, StatusBarWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(
                    version="1.13.0", uptime=7200, disk_status="ok"
                )
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                bar = app.query_one("#status-bar", StatusBarWidget)
                assert bar._renderer._version == "1.13.0"
                assert bar._renderer._uptime_seconds == 7200
                assert bar._renderer._disk_status == "ok"

        asyncio.run(_test())


class TestDashboardAppOfflineIsolation:
    """Test that one endpoint going offline only affects its panel."""

    def test_autorate_offline_steering_continues(self):
        """When autorate poller goes offline, SteeringPanel continues updating."""
        from wanctl.dashboard.app import DashboardApp, SteeringPanelWidget, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                app._autorate_poller.poll = AsyncMock(return_value=None)
                app._steering_poller.poll = AsyncMock(
                    return_value=_make_steering_response()
                )
                await app._poll_autorate()
                await app._poll_steering()

                wan1 = app.query_one("#wan-1", WanPanelWidget)
                assert wan1._renderer._online is False

                panel = app.query_one("#steering", SteeringPanelWidget)
                assert panel._renderer._data is not None

        asyncio.run(_test())

    def test_steering_offline_wan_panels_continue(self):
        """When steering poller goes offline, WanPanels continue updating."""
        from wanctl.dashboard.app import DashboardApp, SteeringPanelWidget, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                app._autorate_poller.poll = AsyncMock(
                    return_value=_make_autorate_response()
                )
                app._steering_poller.poll = AsyncMock(return_value=None)
                await app._poll_autorate()
                await app._poll_steering()

                wan1 = app.query_one("#wan-1", WanPanelWidget)
                assert wan1._renderer._data is not None
                assert wan1._renderer._online is True

                panel = app.query_one("#steering", SteeringPanelWidget)
                assert panel._renderer._online is False

        asyncio.run(_test())


class TestDashboardAppSparklineWidgets:
    """Test DashboardApp.compose() includes sparkline and gauge widgets."""

    def test_compose_yields_sparkline_panels(self):
        """DashboardApp.compose() yields 2 SparklinePanelWidget children."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                panels = app.query(SparklinePanelWidget)
                assert len(panels) == 2

        asyncio.run(_test())

    def test_compose_yields_gauge_widgets(self):
        """DashboardApp.compose() yields 2 CycleBudgetGaugeWidget children."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                gauges = app.query(CycleBudgetGaugeWidget)
                assert len(gauges) == 2

        asyncio.run(_test())

    def test_sparkline_widgets_have_correct_ids(self):
        """Sparkline panels have IDs spark-wan-1 and spark-wan-2."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                spark1 = app.query_one("#spark-wan-1", SparklinePanelWidget)
                spark2 = app.query_one("#spark-wan-2", SparklinePanelWidget)
                assert spark1 is not None
                assert spark2 is not None

        asyncio.run(_test())

    def test_gauge_widgets_have_correct_ids(self):
        """Gauge widgets have IDs gauge-wan-1 and gauge-wan-2."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                gauge1 = app.query_one("#gauge-wan-1", CycleBudgetGaugeWidget)
                gauge2 = app.query_one("#gauge-wan-2", CycleBudgetGaugeWidget)
                assert gauge1 is not None
                assert gauge2 is not None

        asyncio.run(_test())


class TestDashboardAppSparklineRouting:
    """Test poll callback routes data to sparkline and gauge widgets."""

    def test_poll_routes_data_to_sparkline_widgets(self):
        """Poll callback extracts DL/UL/RTT and routes to SparklinePanelWidget."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()

                spark1 = app.query_one("#spark-wan-1", SparklinePanelWidget)
                assert len(spark1._dl_data) == 1
                assert spark1._dl_data[0] == 245.0
                assert spark1._ul_data[0] == 10.5
                # RTT delta = max(0, 18.7 - 12.3) = 6.4
                assert abs(spark1._rtt_delta_data[0] - 6.4) < 0.01

        asyncio.run(_test())

    def test_poll_routes_cycle_budget_to_gauge(self):
        """Poll callback routes cycle_budget.utilization_pct to gauge widget."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()

                gauge1 = app.query_one("#gauge-wan-1", CycleBudgetGaugeWidget)
                assert gauge1._utilization_pct == 70.4

                gauge2 = app.query_one("#gauge-wan-2", CycleBudgetGaugeWidget)
                assert gauge2._utilization_pct == 56.2

        asyncio.run(_test())

    def test_poll_missing_cycle_budget_does_not_crash(self):
        """When cycle_budget is None, gauge is not updated and no crash."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(
                    wans_count=2, include_cycle_budget=False
                )
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()

                # Should not crash; gauge stays at initial 0
                gauge1 = app.query_one("#gauge-wan-1", CycleBudgetGaugeWidget)
                assert gauge1._utilization_pct == 0

        asyncio.run(_test())

    def test_poll_accumulates_sparkline_data(self):
        """Multiple polls accumulate sparkline data points."""
        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                await app._poll_autorate()
                await app._poll_autorate()

                spark1 = app.query_one("#spark-wan-1", SparklinePanelWidget)
                assert len(spark1._dl_data) == 3

        asyncio.run(_test())


class TestDashboardAppTabbedContent:
    """Test DashboardApp uses TabbedContent with Live and History tabs."""

    def test_compose_yields_tabbed_content(self):
        """DashboardApp.compose() yields TabbedContent with 2 TabPanes."""
        from textual.widgets import TabbedContent, TabPane

        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                tabbed = app.query(TabbedContent)
                assert len(tabbed) == 1
                panes = app.query(TabPane)
                assert len(panes) == 2

        asyncio.run(_test())

    def test_live_tab_contains_wan_and_steering_widgets(self):
        """Live tab contains WanPanelWidget, SparklinePanelWidget, CycleBudgetGaugeWidget, SteeringPanelWidget."""
        from textual.widgets import TabPane

        from wanctl.dashboard.app import (
            DashboardApp,
            SteeringPanelWidget,
            WanPanelWidget,
        )
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                live_pane = app.query_one("#live", TabPane)
                wan_panels = live_pane.query(WanPanelWidget)
                assert len(wan_panels) == 2
                sparklines = live_pane.query(SparklinePanelWidget)
                assert len(sparklines) == 2
                gauges = live_pane.query(CycleBudgetGaugeWidget)
                assert len(gauges) == 2
                steering = live_pane.query(SteeringPanelWidget)
                assert len(steering) == 1

        asyncio.run(_test())

    def test_history_tab_contains_history_browser(self):
        """History tab contains HistoryBrowserWidget."""
        from textual.widgets import TabPane

        from wanctl.dashboard.app import DashboardApp
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                history_pane = app.query_one("#history", TabPane)
                browsers = history_pane.query(HistoryBrowserWidget)
                assert len(browsers) == 1

        asyncio.run(_test())

    def test_status_bar_outside_tabbed_content(self):
        """StatusBarWidget is outside TabbedContent (docked to bottom)."""
        from textual.widgets import TabbedContent

        from wanctl.dashboard.app import DashboardApp, StatusBarWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                status_bar = app.query_one("#status-bar", StatusBarWidget)
                tabbed = app.query_one(TabbedContent)
                # StatusBarWidget should not be a descendant of TabbedContent
                tabbed_status = tabbed.query(StatusBarWidget)
                assert len(tabbed_status) == 0
                assert status_bar is not None

        asyncio.run(_test())

    def test_poll_routing_works_through_tab_panes(self):
        """query_one still finds widgets inside TabPanes for poll routing."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                wan1 = app.query_one("#wan-1", WanPanelWidget)
                assert wan1._renderer._data is not None
                assert wan1._renderer._data["name"] == "spectrum"

        asyncio.run(_test())


class TestDashboardAppDualPollerMode:
    """Test dual-poller mode when secondary_autorate_url is configured."""

    def test_no_secondary_url_preserves_single_poller_behavior(self):
        """Default config (empty secondary URL) routes both WANs from single endpoint."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                wan1 = app.query_one("#wan-1", WanPanelWidget)
                wan2 = app.query_one("#wan-2", WanPanelWidget)
                assert wan1._renderer._data is not None
                assert wan1._renderer._data["name"] == "spectrum"
                assert wan2._renderer._data is not None
                assert wan2._renderer._data["name"] == "att"

        asyncio.run(_test())

    def test_secondary_url_creates_secondary_poller(self):
        """Non-empty secondary_autorate_url creates secondary poller."""
        from wanctl.dashboard.app import DashboardApp

        config = DashboardConfig(secondary_autorate_url="http://10.0.0.2:9101")
        app = DashboardApp(config)
        assert app._secondary_autorate_poller is not None
        assert app._secondary_autorate_poller.base_url == "http://10.0.0.2:9101"

    def test_no_secondary_url_has_none_secondary_poller(self):
        """Default config has None secondary poller."""
        from wanctl.dashboard.app import DashboardApp

        config = DashboardConfig()
        app = DashboardApp(config)
        assert app._secondary_autorate_poller is None

    def test_dual_mode_primary_only_routes_wan1(self):
        """In dual mode, primary poll routes only WAN 1 (not WAN 2)."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig(
                secondary_autorate_url="http://10.0.0.2:9101"
            )
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                response = _make_autorate_response(wans_count=2)
                app._autorate_poller.poll = AsyncMock(return_value=response)
                await app._poll_autorate()
                wan1 = app.query_one("#wan-1", WanPanelWidget)
                wan2 = app.query_one("#wan-2", WanPanelWidget)
                # WAN 1 should have data from primary
                assert wan1._renderer._data is not None
                assert wan1._renderer._data["name"] == "spectrum"
                # WAN 2 should NOT have been updated by primary in dual mode
                assert wan2._renderer._data is None

        asyncio.run(_test())

    def test_dual_mode_secondary_routes_wan2(self):
        """In dual mode, secondary poll routes data to WAN 2."""
        from wanctl.dashboard.app import DashboardApp, WanPanelWidget

        async def _test():
            config = DashboardConfig(
                secondary_autorate_url="http://10.0.0.2:9101"
            )
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                secondary_response = _make_autorate_response(wans_count=1)
                secondary_response["wans"][0]["name"] = "att"
                app._secondary_autorate_poller.poll = AsyncMock(
                    return_value=secondary_response
                )
                await app._poll_secondary_autorate()
                wan2 = app.query_one("#wan-2", WanPanelWidget)
                assert wan2._renderer._data is not None
                assert wan2._renderer._data["name"] == "att"

        asyncio.run(_test())

    def test_action_refresh_calls_secondary_poll_when_configured(self):
        """action_refresh polls secondary endpoint when configured."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig(
                secondary_autorate_url="http://10.0.0.2:9101"
            )
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                app._autorate_poller.poll = AsyncMock(
                    return_value=_make_autorate_response()
                )
                app._secondary_autorate_poller.poll = AsyncMock(
                    return_value=_make_autorate_response(wans_count=1)
                )
                app._steering_poller.poll = AsyncMock(
                    return_value=_make_steering_response()
                )
                await app.action_refresh()
                app._secondary_autorate_poller.poll.assert_called_once()

        asyncio.run(_test())

    def test_action_refresh_skips_secondary_when_not_configured(self):
        """action_refresh skips secondary poll when not configured (no error)."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                app._autorate_poller.poll = AsyncMock(
                    return_value=_make_autorate_response()
                )
                app._steering_poller.poll = AsyncMock(
                    return_value=_make_steering_response()
                )
                await app.action_refresh()
                app._autorate_poller.poll.assert_called_once()
                app._steering_poller.poll.assert_called_once()

        asyncio.run(_test())

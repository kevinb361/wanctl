"""Tests for responsive layout: wide/narrow switching with hysteresis."""

import asyncio
import os
from unittest.mock import patch

import pytest

# Dashboard tests use async app runners with real event loops
pytestmark = pytest.mark.timeout(10)

from wanctl.dashboard.app import parse_args
from wanctl.dashboard.config import DashboardConfig


class TestWideLayout:
    """At >=120 columns, #wan-row has class 'wide-layout' and not 'narrow-layout'."""

    def test_wide_layout_at_140_columns(self):
        """App at 140 columns has wide-layout class on #wan-row."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("wide-layout")
                assert not wan_row.has_class("narrow-layout")

        asyncio.run(_test())

    def test_wide_layout_at_exactly_120_columns(self):
        """App at exactly 120 columns has wide-layout class on #wan-row."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("wide-layout")
                assert not wan_row.has_class("narrow-layout")

        asyncio.run(_test())

    def test_wide_layout_at_200_columns(self):
        """App at 200 columns has wide-layout class on #wan-row."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(200, 40)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("wide-layout")

        asyncio.run(_test())


class TestNarrowLayout:
    """At <120 columns, #wan-row has class 'narrow-layout' and not 'wide-layout'."""

    def test_narrow_layout_at_80_columns(self):
        """App at 80 columns has narrow-layout class on #wan-row."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("narrow-layout")
                assert not wan_row.has_class("wide-layout")

        asyncio.run(_test())

    def test_narrow_layout_at_119_columns(self):
        """App at 119 columns (just below breakpoint) has narrow-layout."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(119, 40)) as pilot:
                await pilot.pause()
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("narrow-layout")
                assert not wan_row.has_class("wide-layout")

        asyncio.run(_test())


class TestHysteresis:
    """Rapid resize does not immediately switch layout; debounce delay required."""

    def test_rapid_resize_does_not_switch_immediately(self):
        """Resizing near breakpoint does not immediately change layout mode."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "wide"
                # Rapid resize to narrow -- should NOT switch immediately
                await pilot.resize_terminal(80, 24)
                # Check immediately (no pause for debounce)
                # Layout mode should still be wide since hysteresis hasn't elapsed
                assert app._layout_mode == "wide"

        asyncio.run(_test())

    def test_layout_switches_after_debounce_delay(self):
        """Layout switches after waiting for the hysteresis debounce period."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "wide"
                # Resize to narrow
                await pilot.resize_terminal(80, 24)
                # Wait for hysteresis (0.3s) plus some buffer
                await pilot.pause(0.5)
                assert app._layout_mode == "narrow"
                wan_row = app.query_one("#wan-row")
                assert wan_row.has_class("narrow-layout")

        asyncio.run(_test())

    def test_rapid_resize_cancels_previous_timer(self):
        """Multiple rapid resizes only trigger one layout switch."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "wide"
                # Rapid resize: narrow -> wide -> narrow
                await pilot.resize_terminal(80, 24)
                await pilot.resize_terminal(140, 40)
                await pilot.resize_terminal(80, 24)
                # Wait for hysteresis
                await pilot.pause(0.5)
                # Should be narrow (last resize was to 80)
                assert app._layout_mode == "narrow"

        asyncio.run(_test())


class TestInitialLayout:
    """App launched at various sizes starts in the correct mode."""

    def test_initial_wide_at_140_columns(self):
        """App launched at 140 columns starts in wide mode."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "wide"

        asyncio.run(_test())

    def test_initial_narrow_at_80_columns(self):
        """App launched at 80 columns starts in narrow mode."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                assert app._layout_mode == "narrow"

        asyncio.run(_test())


class TestWidgetPreservation:
    """All existing widget IDs remain queryable after layout restructure."""

    def test_all_widget_ids_queryable(self):
        """All core widget IDs are still present in the restructured layout."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                expected_ids = [
                    "#wan-1",
                    "#wan-2",
                    "#spark-wan-1",
                    "#spark-wan-2",
                    "#gauge-wan-1",
                    "#gauge-wan-2",
                    "#steering",
                    "#status-bar",
                ]
                for widget_id in expected_ids:
                    widget = app.query_one(widget_id)
                    assert widget is not None, f"Widget {widget_id} not found"

        asyncio.run(_test())

    def test_wan_row_container_exists(self):
        """#wan-row Horizontal container exists in the layout."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                wan_row = app.query_one("#wan-row")
                assert wan_row is not None

        asyncio.run(_test())

    def test_wan_columns_exist(self):
        """Two .wan-col Vertical containers exist inside #wan-row."""
        from wanctl.dashboard.app import DashboardApp

        async def _test():
            config = DashboardConfig()
            app = DashboardApp(config)
            async with app.run_test(size=(120, 40)):
                wan_row = app.query_one("#wan-row")
                wan_cols = wan_row.query(".wan-col")
                assert len(wan_cols) == 2

        asyncio.run(_test())


class TestColorFlags:
    """Tests for --no-color and --256-color CLI flags."""

    def test_no_color_flag_parsed(self):
        """parse_args(['--no-color']) returns args.no_color == True."""
        args = parse_args(["--no-color"])
        assert args.no_color is True

    def test_256_color_flag_parsed(self):
        """parse_args(['--256-color']) returns args.color_256 == True."""
        args = parse_args(["--256-color"])
        assert args.color_256 is True

    def test_no_color_sets_env(self):
        """When main() called with --no-color, os.environ['NO_COLOR'] is set to '1'."""
        from wanctl.dashboard.app import main

        env_copy = os.environ.copy()
        env_copy.pop("NO_COLOR", None)
        env_copy.pop("TEXTUAL_COLOR_SYSTEM", None)

        with (
            patch.dict(os.environ, env_copy, clear=True),
            patch("wanctl.dashboard.app.DashboardApp") as mock_app_cls,
        ):
            mock_app_cls.return_value.run.return_value = None
            main(["--no-color"])
            assert os.environ.get("NO_COLOR") == "1"

    def test_256_color_sets_env(self):
        """When main() called with --256-color, os.environ['TEXTUAL_COLOR_SYSTEM'] is '256'."""
        from wanctl.dashboard.app import main

        env_copy = os.environ.copy()
        env_copy.pop("NO_COLOR", None)
        env_copy.pop("TEXTUAL_COLOR_SYSTEM", None)

        with (
            patch.dict(os.environ, env_copy, clear=True),
            patch("wanctl.dashboard.app.DashboardApp") as mock_app_cls,
        ):
            mock_app_cls.return_value.run.return_value = None
            main(["--256-color"])
            assert os.environ.get("TEXTUAL_COLOR_SYSTEM") == "256"

    def test_flags_mutually_exclusive_priority(self):
        """--no-color takes priority over --256-color."""
        from wanctl.dashboard.app import main

        env_copy = os.environ.copy()
        env_copy.pop("NO_COLOR", None)
        env_copy.pop("TEXTUAL_COLOR_SYSTEM", None)

        with (
            patch.dict(os.environ, env_copy, clear=True),
            patch("wanctl.dashboard.app.DashboardApp") as mock_app_cls,
        ):
            mock_app_cls.return_value.run.return_value = None
            main(["--no-color", "--256-color"])
            assert os.environ.get("NO_COLOR") == "1"
            assert os.environ.get("TEXTUAL_COLOR_SYSTEM") is None

    def test_no_flags_no_env_change(self):
        """When neither flag passed, NO_COLOR and TEXTUAL_COLOR_SYSTEM are not set."""
        from wanctl.dashboard.app import main

        env_copy = os.environ.copy()
        env_copy.pop("NO_COLOR", None)
        env_copy.pop("TEXTUAL_COLOR_SYSTEM", None)

        with (
            patch.dict(os.environ, env_copy, clear=True),
            patch("wanctl.dashboard.app.DashboardApp") as mock_app_cls,
        ):
            mock_app_cls.return_value.run.return_value = None
            main([])
            assert os.environ.get("NO_COLOR") is None
            assert os.environ.get("TEXTUAL_COLOR_SYSTEM") is None

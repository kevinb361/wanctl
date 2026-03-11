"""Tests for HistoryBrowserWidget -- time range selection, DataTable, summary stats."""

import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestHistoryBrowserCompose:
    """Test HistoryBrowserWidget.compose() yields correct children."""

    def test_compose_yields_select_static_datatable(self):
        """compose() produces Select, Static, and DataTable widgets."""
        from textual.widgets import DataTable, Select, Static

        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        async def _test():
            from textual.app import App, ComposeResult

            class TestApp(App):
                def compose(self) -> ComposeResult:
                    yield HistoryBrowserWidget(
                        autorate_url="http://localhost:9101",
                        id="history-browser",
                    )

            app = TestApp()
            async with app.run_test(size=(120, 40)):
                selects = app.query(Select)
                app.query(Static)
                tables = app.query(DataTable)
                assert len(selects) >= 1
                # Static for summary
                summary = app.query_one("#summary-stats", Static)
                assert summary is not None
                assert len(tables) >= 1

        asyncio.run(_test())


class TestComputeSummary:
    """Test _compute_summary with various inputs."""

    def test_multiple_values_returns_correct_stats(self):
        """_compute_summary with multiple values returns min/max/avg/p95/p99."""
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        widget = HistoryBrowserWidget(autorate_url="http://localhost:9101")
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        result = widget._compute_summary(values)
        assert result["min"] == 10.0
        assert result["max"] == 100.0
        assert result["avg"] == 55.0
        assert "p95" in result
        assert "p99" in result

    def test_empty_list_returns_empty_dict(self):
        """_compute_summary with empty list returns {}."""
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        widget = HistoryBrowserWidget(autorate_url="http://localhost:9101")
        result = widget._compute_summary([])
        assert result == {}

    def test_single_value_returns_that_value_for_all_keys(self):
        """_compute_summary with single value returns it for all stats."""
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        widget = HistoryBrowserWidget(autorate_url="http://localhost:9101")
        result = widget._compute_summary([42.0])
        assert result["min"] == 42.0
        assert result["max"] == 42.0
        assert result["avg"] == 42.0
        assert result["p95"] == 42.0
        assert result["p99"] == 42.0


class TestFetchAndPopulate:
    """Test _fetch_and_populate with mocked HTTP responses."""

    def test_populates_datatable_from_mock_response(self):
        """_fetch_and_populate populates DataTable rows from mock API response."""
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        mock_response_data = {
            "data": [
                {
                    "timestamp": "2026-03-11T12:00:00+00:00",
                    "wan_name": "spectrum",
                    "metric_name": "dl_rate_mbps",
                    "value": 245.3,
                    "labels": "",
                    "granularity": "raw",
                },
                {
                    "timestamp": "2026-03-11T12:01:00+00:00",
                    "wan_name": "att",
                    "metric_name": "ul_rate_mbps",
                    "value": 18.5,
                    "labels": "",
                    "granularity": "raw",
                },
            ],
            "metadata": {"total_count": 2, "returned_count": 2},
        }

        async def _test():
            from textual.app import App, ComposeResult

            class TestApp(App):
                def compose(self) -> ComposeResult:
                    yield HistoryBrowserWidget(
                        autorate_url="http://localhost:9101",
                        id="history-browser",
                    )

            app = TestApp()
            async with app.run_test(size=(120, 40)):
                widget = app.query_one("#history-browser", HistoryBrowserWidget)
                mock_client = AsyncMock()
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json.return_value = mock_response_data
                mock_client.get = AsyncMock(return_value=mock_resp)
                widget._http_client = mock_client

                await widget._fetch_and_populate("1h")

                from textual.widgets import DataTable

                table = app.query_one("#history-table", DataTable)
                assert table.row_count == 2

        asyncio.run(_test())

    def test_handles_http_error_gracefully(self):
        """_fetch_and_populate handles HTTP errors without crashing."""
        import httpx

        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        async def _test():
            from textual.app import App, ComposeResult

            class TestApp(App):
                def compose(self) -> ComposeResult:
                    yield HistoryBrowserWidget(
                        autorate_url="http://localhost:9101",
                        id="history-browser",
                    )

            app = TestApp()
            async with app.run_test(size=(120, 40)):
                widget = app.query_one("#history-browser", HistoryBrowserWidget)
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(
                    side_effect=httpx.HTTPStatusError(
                        "500",
                        request=MagicMock(),
                        response=MagicMock(status_code=500),
                    )
                )
                widget._http_client = mock_client

                await widget._fetch_and_populate("1h")

                from textual.widgets import DataTable, Static

                table = app.query_one("#history-table", DataTable)
                assert table.row_count == 0
                summary = app.query_one("#summary-stats", Static)
                rendered = str(summary.render())
                assert "No data" in rendered or "Failed" in rendered

        asyncio.run(_test())


class TestSelectChangedTriggerseFetch:
    """Test on_select_changed triggers _fetch_and_populate."""

    def test_on_select_changed_triggers_fetch(self):
        """Changing select value triggers _fetch_and_populate with correct range."""
        from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget

        async def _test():
            from textual.app import App, ComposeResult

            class TestApp(App):
                def compose(self) -> ComposeResult:
                    yield HistoryBrowserWidget(
                        autorate_url="http://localhost:9101",
                        id="history-browser",
                    )

            app = TestApp()
            async with app.run_test(size=(120, 40)):
                widget = app.query_one("#history-browser", HistoryBrowserWidget)
                widget._fetch_and_populate = AsyncMock()

                from textual.widgets import Select

                select = app.query_one("#time-range", Select)
                # Simulate select change by calling the handler directly
                event = MagicMock()
                event.value = "6h"
                event.select = select
                widget.on_select_changed(event)

                # Give worker time to start
                await asyncio.sleep(0.1)
                widget._fetch_and_populate.assert_called_once_with("6h")

        asyncio.run(_test())

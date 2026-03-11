"""Tests for CycleBudgetGaugeWidget -- cycle budget utilization gauge."""


class TestCycleBudgetGaugeInit:
    """Test CycleBudgetGaugeWidget initialization."""

    def test_creates_with_default_state(self):
        """CycleBudgetGaugeWidget initializes without error."""
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        widget = CycleBudgetGaugeWidget(id="gauge-wan-1")
        assert widget is not None


class TestCycleBudgetGaugeUpdate:
    """Test CycleBudgetGaugeWidget.update_utilization() method."""

    def test_update_utilization_stores_value(self):
        """update_utilization() stores the percentage value."""
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        widget = CycleBudgetGaugeWidget(id="gauge-wan-1")
        widget.update_utilization(70.4)
        assert widget._utilization_pct == 70.4

    def test_update_utilization_none_treated_as_zero(self):
        """update_utilization(None) sets value to 0."""
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        widget = CycleBudgetGaugeWidget(id="gauge-wan-1")
        widget.update_utilization(None)
        assert widget._utilization_pct == 0

    def test_update_utilization_initial_value_is_zero(self):
        """Initial utilization_pct is 0 before any update."""
        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        widget = CycleBudgetGaugeWidget(id="gauge-wan-1")
        assert widget._utilization_pct == 0


class TestCycleBudgetGaugeCompose:
    """Test CycleBudgetGaugeWidget.compose() yields correct children."""

    def test_compose_yields_progress_bar(self):
        """compose() yields a ProgressBar with total=100, show_eta=False."""
        import asyncio

        from textual.app import App, ComposeResult
        from textual.widgets import ProgressBar

        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CycleBudgetGaugeWidget(id="gauge-wan-1")

        async def _test():
            app = TestApp()
            async with app.run_test(size=(80, 20)):
                bar = app.query_one("#cycle-gauge", ProgressBar)
                assert bar is not None
                assert bar.total == 100

        asyncio.run(_test())

    def test_compose_yields_label(self):
        """compose() yields a Static label 'Cycle Budget'."""
        import asyncio

        from textual.app import App, ComposeResult
        from textual.widgets import Static

        from wanctl.dashboard.widgets.cycle_gauge import CycleBudgetGaugeWidget

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CycleBudgetGaugeWidget(id="gauge-wan-1")

        async def _test():
            app = TestApp()
            async with app.run_test(size=(80, 20)):
                statics = app.query(Static)
                labels = [s for s in statics if "Cycle Budget" in str(s.render())]
                assert len(labels) >= 1

        asyncio.run(_test())

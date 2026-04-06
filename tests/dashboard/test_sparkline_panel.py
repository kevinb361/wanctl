"""Tests for SparklinePanelWidget -- sparkline trend visualization."""

from collections import deque


class TestSparklinePanelInit:
    """Test SparklinePanelWidget initialization and bounded deques."""

    def test_creates_three_bounded_deques(self):
        """SparklinePanelWidget creates 3 deques with maxlen=120."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        assert isinstance(widget._dl_data, deque)
        assert isinstance(widget._ul_data, deque)
        assert isinstance(widget._rtt_delta_data, deque)
        assert widget._dl_data.maxlen == 120
        assert widget._ul_data.maxlen == 120
        assert widget._rtt_delta_data.maxlen == 120

    def test_custom_maxlen(self):
        """SparklinePanelWidget respects custom maxlen parameter."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(maxlen=60, wan_name="WAN 1", id="spark-wan-1")
        assert widget._dl_data.maxlen == 60

    def test_deques_start_empty(self):
        """All deques start with zero elements."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        assert len(widget._dl_data) == 0
        assert len(widget._ul_data) == 0
        assert len(widget._rtt_delta_data) == 0


class TestSparklinePanelAppendData:
    """Test SparklinePanelWidget.append_data() method."""

    def test_append_data_adds_to_deques(self):
        """append_data() appends values to all three deques."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        widget.append_data(dl_rate=245.0, ul_rate=10.5, rtt_delta=6.4)
        assert list(widget._dl_data) == [245.0]
        assert list(widget._ul_data) == [10.5]
        assert list(widget._rtt_delta_data) == [6.4]

    def test_append_data_multiple_values(self):
        """Multiple appends accumulate correctly."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        widget.append_data(100.0, 10.0, 1.0)
        widget.append_data(200.0, 20.0, 2.0)
        widget.append_data(300.0, 30.0, 3.0)
        assert list(widget._dl_data) == [100.0, 200.0, 300.0]
        assert list(widget._ul_data) == [10.0, 20.0, 30.0]
        assert list(widget._rtt_delta_data) == [1.0, 2.0, 3.0]

    def test_bounded_deque_after_150_appends(self):
        """After 150 appends, deque length is still 120 (bounded)."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        for i in range(150):
            widget.append_data(float(i), float(i), float(i))
        assert len(widget._dl_data) == 120
        assert len(widget._ul_data) == 120
        assert len(widget._rtt_delta_data) == 120
        # Oldest values dropped
        assert widget._dl_data[0] == 30.0


class TestSparklinePanelCompose:
    """Test SparklinePanelWidget.compose() yields correct children."""

    def test_compose_yields_sparklines_with_correct_ids(self):
        """compose() yields 3 Sparkline widgets with IDs dl-spark, ul-spark, rtt-spark."""
        import asyncio

        from textual.app import App, ComposeResult
        from textual.widgets import Sparkline

        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")

        async def _test():
            app = TestApp()
            async with app.run_test(size=(80, 20)):
                dl = app.query_one("#dl-spark", Sparkline)
                ul = app.query_one("#ul-spark", Sparkline)
                rtt = app.query_one("#rtt-spark", Sparkline)
                assert dl is not None
                assert ul is not None
                assert rtt is not None

        asyncio.run(_test())

    def test_compose_yields_label(self):
        """compose() yields a Static label with the WAN name."""
        import asyncio

        from textual.app import App, ComposeResult
        from textual.widgets import Static

        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")

        async def _test():
            app = TestApp()
            async with app.run_test(size=(80, 20)):
                statics = app.query(Static)
                labels = [s for s in statics if "Trends" in str(s.render())]
                assert len(labels) >= 1

        asyncio.run(_test())

    def test_rtt_sparkline_uses_green_to_red_gradient(self):
        """RTT delta sparkline has min_color=green, max_color=red."""
        from wanctl.dashboard.widgets.sparkline_panel import SparklinePanelWidget

        widget = SparklinePanelWidget(wan_name="WAN 1", id="spark-wan-1")
        # Access the configured colors before compose
        assert widget._rtt_min_color == "green"
        assert widget._rtt_max_color == "red"

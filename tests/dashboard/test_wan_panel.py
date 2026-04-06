"""Tests for WanPanel widget rendering."""

from datetime import UTC, datetime

from wanctl.dashboard.widgets.wan_panel import WanPanel


class TestWanPanelRendering:
    """Test WanPanel renders WAN data correctly."""

    def _make_wan_data(
        self,
        name: str = "spectrum",
        baseline_rtt: float = 12.3,
        load_rtt: float = 18.7,
        dl_rate: float = 245.0,
        dl_state: str = "GREEN",
        ul_rate: float = 10.5,
        ul_state: str = "GREEN",
        router_reachable: bool = True,
    ) -> dict:
        """Build a sample WAN data dict matching autorate wans[] element."""
        return {
            "name": name,
            "baseline_rtt_ms": baseline_rtt,
            "load_rtt_ms": load_rtt,
            "download": {"current_rate_mbps": dl_rate, "state": dl_state},
            "upload": {"current_rate_mbps": ul_rate, "state": ul_state},
            "router_connectivity": router_reachable,
        }

    def _render_text(self, panel: WanPanel) -> str:
        """Render the panel and return the plain text representation."""
        renderable = panel.render()
        # Rich renderables have a __str__ or we can use Rich console to capture
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        console.print(renderable, end="")
        return buf.getvalue()

    def test_panel_title_contains_wan_name(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(name="spectrum"))
        text = self._render_text(panel)
        assert "spectrum" in text.lower()

    def test_green_state_renders(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(dl_state="GREEN"))
        text = self._render_text(panel)
        assert "GREEN" in text

    def test_yellow_state_renders(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(dl_state="YELLOW"))
        text = self._render_text(panel)
        assert "YELLOW" in text

    def test_soft_red_state_renders(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(dl_state="SOFT_RED"))
        text = self._render_text(panel)
        assert "SOFT_RED" in text

    def test_red_state_renders(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(dl_state="RED"))
        text = self._render_text(panel)
        assert "RED" in text

    def test_dl_rate_with_limit(self):
        panel = WanPanel(wan_name="spectrum", rate_limits={"dl_mbps": 300.0, "ul_mbps": 12.0})
        panel.update_from_data(self._make_wan_data(dl_rate=245.3))
        text = self._render_text(panel)
        assert "245.3" in text
        assert "300.0" in text

    def test_dl_rate_without_limit(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(dl_rate=245.3))
        text = self._render_text(panel)
        assert "245.3" in text
        # Should NOT show a limit
        assert "300.0" not in text

    def test_ul_rate_with_limit(self):
        panel = WanPanel(wan_name="spectrum", rate_limits={"dl_mbps": 300.0, "ul_mbps": 12.0})
        panel.update_from_data(self._make_wan_data(ul_rate=11.2))
        text = self._render_text(panel)
        assert "11.2" in text
        assert "12.0" in text

    def test_rtt_baseline_load_delta(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(baseline_rtt=12.3, load_rtt=18.7))
        text = self._render_text(panel)
        assert "12.3" in text
        assert "18.7" in text
        # Delta = 18.7 - 12.3 = 6.4
        assert "6.4" in text

    def test_router_reachable_badge(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(router_reachable=True))
        text = self._render_text(panel)
        # Should show some form of "OK" or reachable indicator
        assert "OK" in text.upper() or "REACHABLE" in text.upper()

    def test_router_unreachable_badge(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(router_reachable=False))
        text = self._render_text(panel)
        assert "UNREACHABLE" in text.upper()

    def test_offline_mode_shows_badge(self):
        panel = WanPanel(wan_name="spectrum")
        # First give it data, then set offline
        panel.update_from_data(self._make_wan_data())
        panel.update_from_data(None, last_seen=datetime(2026, 3, 11, 12, 0, 0, tzinfo=UTC))
        text = self._render_text(panel)
        assert "OFFLINE" in text

    def test_offline_mode_shows_last_seen(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data())
        last_seen = datetime(2026, 3, 11, 12, 0, 0, tzinfo=UTC)
        panel.update_from_data(None, last_seen=last_seen)
        text = self._render_text(panel)
        assert "12:00:00" in text

    def test_degraded_mode_shows_badge(self):
        panel = WanPanel(wan_name="spectrum")
        panel.update_from_data(self._make_wan_data(), status="degraded")
        text = self._render_text(panel)
        assert "DEGRADED" in text

    def test_update_with_none_keeps_last_data(self):
        panel = WanPanel(wan_name="spectrum")
        data = self._make_wan_data(dl_rate=245.3)
        panel.update_from_data(data)
        panel.update_from_data(None)
        # Should still have the data internally for frozen display
        assert panel._data is not None
        assert panel._data["download"]["current_rate_mbps"] == 245.3
        assert panel._online is False

"""Tests for SteeringPanel and StatusBar widget rendering."""

from datetime import UTC, datetime

from wanctl.dashboard.widgets.status_bar import StatusBar, format_duration
from wanctl.dashboard.widgets.steering_panel import SteeringPanel


class TestSteeringPanelRendering:
    """Test SteeringPanel renders steering data correctly."""

    def _make_steering_data(
        self,
        enabled: bool = True,
        mode: str = "active",
        state: str = "monitoring",
        confidence: float = 72.5,
        wan_enabled: bool = True,
        zone: str = "GREEN",
        contribution: float = 25.0,
        grace_active: bool = False,
        transition_time: str = "2026-03-11T12:00:00Z",
        time_in_state: float = 456.7,
    ) -> dict:
        """Build a sample steering health response dict."""
        return {
            "status": "healthy",
            "steering": {"enabled": enabled, "state": state, "mode": mode},
            "confidence": {"primary": confidence},
            "wan_awareness": {
                "enabled": wan_enabled,
                "zone": zone,
                "effective_zone": zone,
                "grace_period_active": grace_active,
                "staleness_age_sec": 1.2,
                "stale": False,
                "confidence_contribution": contribution,
            },
            "decision": {
                "last_transition_time": transition_time,
                "time_in_state_seconds": time_in_state,
            },
        }

    def _render_text(self, panel: SteeringPanel) -> str:
        """Render the panel and return plain text via Rich console."""
        renderable = panel.render()
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        console.print(renderable, end="")
        return buf.getvalue()

    def test_shows_enabled_status(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(enabled=True))
        text = self._render_text(panel)
        assert "Enabled" in text or "ENABLED" in text.upper()

    def test_shows_disabled_status(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(enabled=False))
        text = self._render_text(panel)
        assert "Disabled" in text or "DISABLED" in text.upper()

    def test_shows_active_mode(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(mode="active"))
        text = self._render_text(panel)
        assert "active" in text.lower()

    def test_shows_dry_run_mode(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(mode="dry_run"))
        text = self._render_text(panel)
        assert "dry_run" in text.lower() or "dry run" in text.lower()

    def test_shows_confidence_score(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(confidence=23.5))
        text = self._render_text(panel)
        # Should show rounded to int
        assert "24" in text or "23" in text

    def test_shows_wan_awareness_zone_when_enabled(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(wan_enabled=True, zone="YELLOW"))
        text = self._render_text(panel)
        assert "YELLOW" in text

    def test_shows_wan_awareness_contribution(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(contribution=25.0))
        text = self._render_text(panel)
        assert "25" in text

    def test_shows_grace_period_when_active(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(grace_active=True))
        text = self._render_text(panel)
        assert "grace" in text.lower()

    def test_shows_last_transition_relative(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(time_in_state=456.7))
        text = self._render_text(panel)
        # 456.7s = 7m 36s
        assert "7m" in text

    def test_shows_time_in_state(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(time_in_state=456.7))
        text = self._render_text(panel)
        # Should show formatted duration somewhere
        assert "7m" in text or "456" in text

    def test_offline_mode_shows_badge(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data())
        panel.update_from_data(None, last_seen=datetime(2026, 3, 11, 12, 0, 0, tzinfo=UTC))
        text = self._render_text(panel)
        assert "OFFLINE" in text

    def test_wan_awareness_disabled_shows_disabled(self):
        panel = SteeringPanel()
        panel.update_from_data(self._make_steering_data(wan_enabled=False))
        text = self._render_text(panel)
        assert "disabled" in text.lower()


class TestStatusBarRendering:
    """Test StatusBar renders system info correctly."""

    def _render_text(self, bar: StatusBar) -> str:
        """Render the bar and return plain text."""
        renderable = bar.render()
        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        console.print(renderable, end="")
        return buf.getvalue()

    def test_shows_version(self):
        bar = StatusBar()
        bar.update(version="1.13.0", uptime_seconds=3600, disk_status="ok")
        text = self._render_text(bar)
        assert "1.13.0" in text

    def test_shows_uptime_formatted(self):
        bar = StatusBar()
        bar.update(version="1.13.0", uptime_seconds=4980, disk_status="ok")
        text = self._render_text(bar)
        # 4980s = 1h 23m
        assert "1h" in text
        assert "23m" in text

    def test_shows_disk_status(self):
        bar = StatusBar()
        bar.update(version="1.13.0", uptime_seconds=3600, disk_status="ok")
        text = self._render_text(bar)
        assert "ok" in text.lower()


class TestFormatDuration:
    """Test format_duration helper."""

    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        result = format_duration(125)
        assert "2m" in result
        assert "5s" in result

    def test_hours_and_minutes(self):
        result = format_duration(4980)
        assert "1h" in result
        assert "23m" in result

    def test_days_and_hours(self):
        result = format_duration(90000)
        assert "1d" in result
        assert "1h" in result

    def test_zero(self):
        assert format_duration(0) == "0s"

    def test_large_duration(self):
        result = format_duration(259200)  # 3 days
        assert "3d" in result

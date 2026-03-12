"""Tests for webhook delivery: AlertFormatter Protocol, DiscordFormatter, WebhookDelivery."""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from wanctl.webhook_delivery import AlertFormatter, DiscordFormatter


class TestAlertFormatterProtocol:
    """Verify AlertFormatter is a Protocol allowing duck typing."""

    def test_duck_typing_compatible(self) -> None:
        """Any object with format() method satisfies AlertFormatter Protocol."""

        class CustomFormatter:
            def format(
                self,
                alert_type: str,
                severity: str,
                wan_name: str,
                details: dict[str, Any],
                *,
                mention_role_id: str | None = None,
                mention_severity: str = "critical",
            ) -> dict[str, Any]:
                return {"custom": True}

        formatter: AlertFormatter = CustomFormatter()  # type: ignore[assignment]
        result = formatter.format("test", "info", "spectrum", {})
        assert result == {"custom": True}


class TestDiscordFormatterSeverityColors:
    """DiscordFormatter maps severity to correct embed color."""

    @pytest.mark.parametrize(
        "severity,expected_color",
        [
            ("critical", 0xE74C3C),
            ("warning", 0xF39C12),
            ("recovery", 0x2ECC71),
            ("info", 0x3498DB),
        ],
    )
    def test_severity_color_mapping(self, severity: str, expected_color: int) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", severity, "spectrum", {})
        embed = result["embeds"][0]
        assert embed["color"] == expected_color


class TestDiscordFormatterSeverityEmoji:
    """DiscordFormatter prefixes title with correct emoji per severity."""

    @pytest.mark.parametrize(
        "severity,expected_emoji",
        [
            ("critical", "\U0001f534"),  # red circle
            ("warning", "\U0001f7e1"),  # yellow circle
            ("recovery", "\U0001f7e2"),  # green circle
            ("info", "\U0001f535"),  # blue circle
        ],
    )
    def test_severity_emoji_prefix(self, severity: str, expected_emoji: str) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", severity, "spectrum", {})
        embed = result["embeds"][0]
        assert embed["title"].startswith(expected_emoji)


class TestDiscordFormatterTitle:
    """DiscordFormatter converts snake_case alert_type to emoji + Title Case."""

    def test_snake_case_to_title_case(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("congestion_sustained", "critical", "spectrum", {})
        embed = result["embeds"][0]
        # Should be "emoji Congestion Sustained"
        assert "Congestion Sustained" in embed["title"]

    def test_single_word_alert_type(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("recovery", "recovery", "spectrum", {})
        embed = result["embeds"][0]
        assert "Recovery" in embed["title"]


class TestDiscordFormatterDescription:
    """DiscordFormatter builds a one-line description."""

    def test_description_includes_wan_name(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("congestion_sustained", "critical", "spectrum", {})
        embed = result["embeds"][0]
        assert "Spectrum" in embed["description"]

    def test_description_includes_severity(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("congestion_sustained", "critical", "spectrum", {})
        embed = result["embeds"][0]
        assert "critical" in embed["description"].lower()


class TestDiscordFormatterFields:
    """DiscordFormatter produces stacked fields: Severity, WAN, Timestamp."""

    def test_severity_field_present(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "spectrum", {})
        embed = result["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Severity" in field_names

    def test_wan_field_present(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "spectrum", {})
        embed = result["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "WAN" in field_names

    def test_timestamp_field_uses_discord_format(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "spectrum", {})
        embed = result["embeds"][0]
        ts_field = next(f for f in embed["fields"] if f["name"] == "Timestamp")
        # Discord relative timestamp format: <t:epoch:R>
        assert ts_field["value"].startswith("<t:")
        assert ts_field["value"].endswith(":R>")

    def test_wan_display_name_spectrum(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "spectrum", {})
        embed = result["embeds"][0]
        wan_field = next(f for f in embed["fields"] if f["name"] == "WAN")
        assert wan_field["value"] == "Spectrum"

    def test_wan_display_name_att(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "att", {})
        embed = result["embeds"][0]
        wan_field = next(f for f in embed["fields"] if f["name"] == "WAN")
        assert wan_field["value"] == "ATT"

    def test_wan_display_name_unknown_capitalizes(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "warning", "starlink", {})
        embed = result["embeds"][0]
        wan_field = next(f for f in embed["fields"] if f["name"] == "WAN")
        assert wan_field["value"] == "Starlink"


class TestDiscordFormatterMetrics:
    """DiscordFormatter builds metrics code block from numeric details."""

    def test_metrics_field_present_with_numeric_details(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"dl_rate": 50.0, "ul_rate": 10.0, "rtt": 25.3}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Metrics" in field_names

    def test_metrics_field_uses_code_block(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"dl_rate": 50.0}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        metrics_field = next(f for f in embed["fields"] if f["name"] == "Metrics")
        assert metrics_field["value"].startswith("```")
        assert metrics_field["value"].endswith("```")

    def test_metrics_includes_units_mbps_for_rate(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"dl_rate": 50.0}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        metrics_field = next(f for f in embed["fields"] if f["name"] == "Metrics")
        assert "Mbps" in metrics_field["value"]

    def test_metrics_includes_units_ms_for_rtt(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"rtt": 25.3}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        metrics_field = next(f for f in embed["fields"] if f["name"] == "Metrics")
        assert "ms" in metrics_field["value"]

    def test_no_metrics_field_without_numeric_details(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"state": "RED", "message": "congested"}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Metrics" not in field_names

    def test_metrics_labels_aligned(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        details = {"dl_rate": 50.0, "rtt": 25.3}
        result = formatter.format("test_alert", "warning", "spectrum", details)
        embed = result["embeds"][0]
        metrics_field = next(f for f in embed["fields"] if f["name"] == "Metrics")
        # Both lines should have colon at the same column (aligned labels)
        lines = [l for l in metrics_field["value"].split("\n") if ":" in l]
        colon_positions = [l.index(":") for l in lines]
        assert len(set(colon_positions)) == 1, f"Colons not aligned: {colon_positions}"


class TestDiscordFormatterFooter:
    """DiscordFormatter footer includes version and container_id."""

    def test_footer_includes_version(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "info", "spectrum", {})
        embed = result["embeds"][0]
        assert "1.15.0" in embed["footer"]["text"]

    def test_footer_includes_container_id(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "info", "spectrum", {})
        embed = result["embeds"][0]
        assert "cake-spectrum" in embed["footer"]["text"]

    def test_footer_has_timestamp_iso(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "info", "spectrum", {})
        embed = result["embeds"][0]
        # Footer should have ISO 8601 timestamp
        assert "timestamp" in embed


class TestDiscordFormatterUsername:
    """DiscordFormatter sets username to 'wanctl'."""

    def test_username_is_wanctl(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format("test_alert", "info", "spectrum", {})
        assert result["username"] == "wanctl"


class TestDiscordFormatterMention:
    """DiscordFormatter mention logic respects severity threshold."""

    def test_mention_included_when_severity_meets_threshold(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format(
            "test_alert",
            "critical",
            "spectrum",
            {},
            mention_role_id="123456",
            mention_severity="critical",
        )
        assert "<@&123456>" in result["content"]

    def test_mention_excluded_when_severity_below_threshold(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format(
            "test_alert",
            "warning",
            "spectrum",
            {},
            mention_role_id="123456",
            mention_severity="critical",
        )
        assert "<@&123456>" not in result.get("content", "")

    def test_no_mention_when_role_id_none(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format(
            "test_alert",
            "critical",
            "spectrum",
            {},
            mention_role_id=None,
            mention_severity="critical",
        )
        assert not result.get("content", "")

    def test_mention_warning_meets_warning_threshold(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format(
            "test_alert",
            "warning",
            "spectrum",
            {},
            mention_role_id="789",
            mention_severity="warning",
        )
        assert "<@&789>" in result["content"]

    def test_mention_critical_meets_warning_threshold(self) -> None:
        formatter = DiscordFormatter(version="1.15.0", container_id="cake-spectrum")
        result = formatter.format(
            "test_alert",
            "critical",
            "spectrum",
            {},
            mention_role_id="789",
            mention_severity="warning",
        )
        assert "<@&789>" in result["content"]

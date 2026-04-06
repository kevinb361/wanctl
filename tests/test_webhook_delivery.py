"""Tests for webhook delivery: AlertFormatter Protocol, DiscordFormatter, WebhookDelivery."""

import logging
import sqlite3
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from wanctl.alert_engine import AlertEngine
from wanctl.autorate_config import Config
from wanctl.steering.daemon import SteeringConfig
from wanctl.storage.schema import ALERTS_SCHEMA
from wanctl.storage.writer import MetricsWriter
from wanctl.webhook_delivery import AlertFormatter, DiscordFormatter, WebhookDelivery


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


# ============================================================================
# Task 2: WebhookDelivery tests
# ============================================================================


@pytest.fixture
def mock_formatter() -> MagicMock:
    """Create a mock AlertFormatter returning a valid Discord payload."""
    formatter = MagicMock(spec=DiscordFormatter)
    formatter.format.return_value = {
        "username": "wanctl",
        "content": "",
        "embeds": [{"title": "Test", "color": 0x3498DB}],
    }
    return formatter


@pytest.fixture
def alerts_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with alerts table."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(ALERTS_SCHEMA)
    conn.commit()
    return conn


class TestWebhookDeliveryConstruction:
    """WebhookDelivery constructed with formatter, URL, rate limit config."""

    def test_construction_basic(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        assert delivery.delivery_failures == 0

    def test_construction_with_rate_limit(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
            max_per_minute=10,
        )
        assert delivery.delivery_failures == 0

    def test_construction_with_mention_params(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
            mention_role_id="123456",
            mention_severity="warning",
        )
        assert delivery.delivery_failures == 0


class TestWebhookDeliveryEmptyUrl:
    """WebhookDelivery with empty/None URL silently skips."""

    def test_empty_url_silently_skips(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(formatter=mock_formatter, webhook_url="")
        delivery.deliver(None, "test_alert", "info", "spectrum", {})
        mock_formatter.format.assert_not_called()

    def test_none_url_silently_skips(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(formatter=mock_formatter, webhook_url=None)  # type: ignore[arg-type]
        delivery.deliver(None, "test_alert", "info", "spectrum", {})
        mock_formatter.format.assert_not_called()


class TestWebhookDeliveryBackground:
    """WebhookDelivery dispatches HTTP POST in a background thread."""

    @patch("wanctl.webhook_delivery.threading.Thread")
    def test_deliver_spawns_daemon_thread(
        self, mock_thread_cls: MagicMock, mock_formatter: MagicMock
    ) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery.deliver(1, "test_alert", "warning", "spectrum", {"rtt": 25.3})
        mock_thread_cls.assert_called_once()
        call_kwargs = mock_thread_cls.call_args
        assert call_kwargs[1]["daemon"] is True
        mock_thread_cls.return_value.start.assert_called_once()


class TestWebhookDeliveryRetry:
    """WebhookDelivery retries on 5xx/timeout, stops on 4xx."""

    @patch("wanctl.webhook_delivery.requests.post")
    def test_success_on_first_attempt(
        self, mock_post: MagicMock, mock_formatter: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        # Call _do_deliver directly to test synchronously
        delivery._do_deliver(1, "test_alert", "warning", "spectrum", {"rtt": 25.3})
        assert mock_post.call_count == 1

    @patch("wanctl.webhook_delivery.time.sleep")
    @patch("wanctl.webhook_delivery.requests.post")
    def test_retries_on_5xx(
        self, mock_post: MagicMock, mock_sleep: MagicMock, mock_formatter: MagicMock
    ) -> None:
        """5xx triggers retry up to max_attempts."""
        response_500 = MagicMock()
        response_500.status_code = 500
        http_error = requests.exceptions.HTTPError(response=response_500)
        response_500.raise_for_status.side_effect = http_error

        response_ok = MagicMock()
        response_ok.status_code = 204
        response_ok.raise_for_status.return_value = None

        mock_post.side_effect = [response_500, response_ok]

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery._do_deliver(None, "test_alert", "warning", "spectrum", {})
        assert mock_post.call_count == 2

    @patch("wanctl.webhook_delivery.time.sleep")
    @patch("wanctl.webhook_delivery.requests.post")
    def test_retries_on_timeout(
        self, mock_post: MagicMock, mock_sleep: MagicMock, mock_formatter: MagicMock
    ) -> None:
        """Timeout triggers retry."""
        mock_post.side_effect = [
            requests.exceptions.Timeout("timed out"),
            MagicMock(status_code=204, raise_for_status=MagicMock(return_value=None)),
        ]

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery._do_deliver(None, "test_alert", "warning", "spectrum", {})
        assert mock_post.call_count == 2

    @patch("wanctl.webhook_delivery.requests.post")
    def test_no_retry_on_4xx(self, mock_post: MagicMock, mock_formatter: MagicMock) -> None:
        """4xx is permanent failure, no retry."""
        response_400 = MagicMock()
        response_400.status_code = 400
        http_error = requests.exceptions.HTTPError(response=response_400)
        response_400.raise_for_status.side_effect = http_error
        mock_post.return_value = response_400

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery._do_deliver(None, "test_alert", "warning", "spectrum", {})
        assert mock_post.call_count == 1

    @patch("wanctl.webhook_delivery.time.sleep")
    @patch("wanctl.webhook_delivery.requests.post")
    def test_retry_exhaustion_increments_failures(
        self, mock_post: MagicMock, mock_sleep: MagicMock, mock_formatter: MagicMock
    ) -> None:
        """After max retries exhausted, failure counter increments."""
        response_500 = MagicMock()
        response_500.status_code = 500
        http_error = requests.exceptions.HTTPError(response=response_500)
        response_500.raise_for_status.side_effect = http_error
        mock_post.return_value = response_500

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery._do_deliver(None, "test_alert", "warning", "spectrum", {})
        assert delivery.delivery_failures == 1

    @patch("wanctl.webhook_delivery.time.sleep")
    @patch("wanctl.webhook_delivery.requests.post")
    def test_exponential_backoff_delays(
        self, mock_post: MagicMock, mock_sleep: MagicMock, mock_formatter: MagicMock
    ) -> None:
        """Backoff doubles delay on each retry attempt."""
        response_500 = MagicMock()
        response_500.status_code = 500
        http_error = requests.exceptions.HTTPError(response=response_500)
        response_500.raise_for_status.side_effect = http_error
        mock_post.return_value = response_500

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        delivery._do_deliver(None, "test_alert", "warning", "spectrum", {})
        # 3 attempts = 2 sleeps (2s, 4s)
        assert mock_sleep.call_count == 2
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] == pytest.approx(2.0)
        assert delays[1] == pytest.approx(4.0)


class TestWebhookDeliveryRateLimit:
    """WebhookDelivery rate-limits webhook delivery."""

    @patch("wanctl.webhook_delivery.threading.Thread")
    def test_rate_limited_drops_delivery(
        self, mock_thread_cls: MagicMock, mock_formatter: MagicMock
    ) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
            max_per_minute=1,
        )
        # First deliver goes through
        delivery.deliver(None, "test_alert", "info", "spectrum", {})
        assert mock_thread_cls.call_count == 1

        # Second deliver is rate limited (dropped)
        delivery.deliver(None, "test_alert_2", "info", "spectrum", {})
        assert mock_thread_cls.call_count == 1  # Still 1, second was dropped


class TestWebhookDeliveryStatus:
    """WebhookDelivery updates delivery_status in SQLite."""

    @patch("wanctl.webhook_delivery.requests.post")
    def test_success_sets_delivered_status(
        self, mock_post: MagicMock, mock_formatter: MagicMock, alerts_db: sqlite3.Connection
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.connection = alerts_db

        # Insert an alert row to update
        alerts_db.execute(
            "INSERT INTO alerts (id, timestamp, alert_type, severity, wan_name, details, delivery_status) "
            "VALUES (1, 1000, 'test', 'info', 'spectrum', '{}', 'pending')"
        )
        alerts_db.commit()

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
            writer=mock_writer,
        )
        delivery._do_deliver(1, "test_alert", "info", "spectrum", {})

        row = alerts_db.execute("SELECT delivery_status FROM alerts WHERE id = 1").fetchone()
        assert row[0] == "delivered"

    @patch("wanctl.webhook_delivery.time.sleep")
    @patch("wanctl.webhook_delivery.requests.post")
    def test_failure_sets_failed_status(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
        mock_formatter: MagicMock,
        alerts_db: sqlite3.Connection,
    ) -> None:
        response_500 = MagicMock()
        response_500.status_code = 500
        http_error = requests.exceptions.HTTPError(response=response_500)
        response_500.raise_for_status.side_effect = http_error
        mock_post.return_value = response_500

        mock_writer = MagicMock()
        mock_writer.connection = alerts_db

        alerts_db.execute(
            "INSERT INTO alerts (id, timestamp, alert_type, severity, wan_name, details, delivery_status) "
            "VALUES (1, 1000, 'test', 'info', 'spectrum', '{}', 'pending')"
        )
        alerts_db.commit()

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
            writer=mock_writer,
        )
        delivery._do_deliver(1, "test_alert", "info", "spectrum", {})

        row = alerts_db.execute("SELECT delivery_status FROM alerts WHERE id = 1").fetchone()
        assert row[0] == "failed"


class TestWebhookDeliveryNeverCrashes:
    """WebhookDelivery catches all exceptions -- never propagates out of thread."""

    @patch("wanctl.webhook_delivery.requests.post")
    def test_unexpected_exception_caught(
        self, mock_post: MagicMock, mock_formatter: MagicMock
    ) -> None:
        mock_post.side_effect = RuntimeError("unexpected chaos")

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        # Should not raise
        delivery._do_deliver(None, "test_alert", "info", "spectrum", {})
        assert delivery.delivery_failures == 1

    def test_formatter_exception_caught(self, mock_formatter: MagicMock) -> None:
        mock_formatter.format.side_effect = ValueError("bad format")

        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        # Should not raise
        delivery._do_deliver(None, "test_alert", "info", "spectrum", {})
        assert delivery.delivery_failures == 1


class TestWebhookDeliveryUpdateUrl:
    """WebhookDelivery.update_webhook_url() validates and updates URL."""

    def test_valid_https_url_accepted(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/old",
        )
        delivery.update_webhook_url("https://discord.com/api/webhooks/new")
        assert delivery._webhook_url == "https://discord.com/api/webhooks/new"

    def test_http_url_rejected(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/old",
        )
        delivery.update_webhook_url("http://insecure.com/webhook")
        # URL should not change
        assert delivery._webhook_url == "https://discord.com/api/webhooks/old"

    def test_empty_url_clears(self, mock_formatter: MagicMock) -> None:
        delivery = WebhookDelivery(
            formatter=mock_formatter,
            webhook_url="https://discord.com/api/webhooks/old",
        )
        delivery.update_webhook_url("")
        assert delivery._webhook_url == ""


class TestAlertsSchemaDeliveryStatus:
    """ALERTS_SCHEMA includes delivery_status column."""

    def test_delivery_status_column_in_schema(self) -> None:
        assert "delivery_status" in ALERTS_SCHEMA

    def test_delivery_status_default_pending(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(ALERTS_SCHEMA)
        conn.execute(
            "INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details) "
            "VALUES (1000, 'test', 'info', 'spectrum', '{}')"
        )
        conn.commit()
        row = conn.execute("SELECT delivery_status FROM alerts WHERE id = 1").fetchone()
        assert row[0] == "pending"
        conn.close()


# =============================================================================
# MERGED FROM test_webhook_integration.py
# =============================================================================


@pytest.fixture
def tmp_writer(tmp_path):
    """Provide a MetricsWriter with a temp database, reset after use."""
    MetricsWriter._reset_instance()
    db_path = tmp_path / "test_integration.db"
    writer = MetricsWriter(db_path)
    yield writer
    MetricsWriter._reset_instance()


@pytest.fixture
def default_rules():
    """Standard rules for testing."""
    return {
        "congestion_sustained": {
            "enabled": True,
            "cooldown_sec": 600,
            "severity": "critical",
        },
    }


class TestAlertEngineDeliveryCallback:
    """Tests for AlertEngine delivery_callback invocation."""

    def test_fire_calls_delivery_callback(self, tmp_writer, default_rules):
        """fire() calls delivery_callback with correct args when alert fires."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        details = {"rtt_delta": 25.0}
        engine.fire("congestion_sustained", "critical", "spectrum", details)

        callback.assert_called_once()
        args = callback.call_args
        # Should be called with (alert_id, alert_type, severity, wan_name, details)
        assert args[0][1] == "congestion_sustained"
        assert args[0][2] == "critical"
        assert args[0][3] == "spectrum"
        assert args[0][4] == details

    def test_fire_passes_alert_id_from_persist(self, tmp_writer, default_rules):
        """fire() passes alert_id (rowid from INSERT) to delivery_callback."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})

        # alert_id should be an integer (rowid)
        alert_id = callback.call_args[0][0]
        assert isinstance(alert_id, int)
        assert alert_id > 0

    def test_fire_passes_none_alert_id_when_no_writer(self, default_rules):
        """fire() passes None as alert_id when no writer configured."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=None,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})

        alert_id = callback.call_args[0][0]
        assert alert_id is None

    def test_callback_error_logged_not_raised(self, tmp_writer, default_rules, caplog):
        """Delivery callback errors are caught and logged, never crash."""
        callback = MagicMock(side_effect=RuntimeError("delivery failed"))
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        with caplog.at_level(logging.WARNING):
            # Must not raise
            result = engine.fire("congestion_sustained", "critical", "spectrum", {})

        # Alert still fired successfully despite callback error
        assert result is True
        assert "Delivery callback failed" in caplog.text

    def test_no_callback_when_suppressed(self, tmp_writer, default_rules):
        """Delivery callback is NOT called when alert is suppressed by cooldown."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})
        callback.reset_mock()

        # Second fire within cooldown should be suppressed
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False
        callback.assert_not_called()

    def test_no_callback_when_disabled(self, tmp_writer, default_rules):
        """Delivery callback is NOT called when engine is disabled."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=False,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False
        callback.assert_not_called()

    def test_no_callback_when_none(self, tmp_writer, default_rules):
        """fire() succeeds when delivery_callback is None (default)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
        )

        # Must not raise
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True


# =============================================================================
# HELPER: Config dict builders + YAML file creators
# =============================================================================


def _autorate_config_dict(alerting_config):
    """Build a minimal valid autorate config dict with alerting section."""
    cfg = {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }
    if alerting_config:
        cfg["alerting"] = alerting_config
    return cfg


def _steering_config_dict(alerting_config):
    """Build a minimal valid steering config dict with alerting section."""
    cfg = {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "topology": {
            "primary_wan": "spectrum",
            "primary_wan_config": "/etc/wanctl/spectrum.yaml",
            "alternate_wan": "att",
        },
        "mangle_rule": {"comment": "ADAPTIVE-STEER"},
        "measurement": {
            "interval_seconds": 0.5,
            "ping_host": "1.1.1.1",
            "ping_count": 3,
        },
        "state": {
            "file": "/var/lib/wanctl/steering_state.json",
            "history_size": 240,
        },
        "logging": {
            "main_log": "/var/log/wanctl/steering.log",
            "debug_log": "/var/log/wanctl/steering_debug.log",
        },
        "lock_file": "/run/wanctl/steering.lock",
        "lock_timeout": 60,
        "thresholds": {
            "bad_threshold_ms": 25.0,
            "recovery_threshold_ms": 12.0,
        },
    }
    if alerting_config:
        cfg["alerting"] = alerting_config
    return cfg


def _make_autorate_config(tmp_path, alerting_config):
    """Write YAML and create autorate Config from it."""

    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(_autorate_config_dict(alerting_config)))
    return Config(str(config_file))


def _make_steering_config(tmp_path, alerting_config):
    """Write YAML and create SteeringConfig from it."""

    config_file = tmp_path / "steering.yaml"
    config_file.write_text(yaml.dump(_steering_config_dict(alerting_config)))
    return SteeringConfig(str(config_file))


class TestDaemonWebhookWiring:
    """Tests for WebhookDelivery construction in daemon __init__ methods."""

    def test_mention_role_id_parsed(self, tmp_path):
        """mention_role_id is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_role_id": "123456789",
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] == "123456789"

    def test_mention_severity_parsed(self, tmp_path):
        """mention_severity is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_severity": "warning",
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "warning"

    def test_mention_severity_defaults_to_critical(self, tmp_path):
        """mention_severity defaults to 'critical' when absent."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "critical"

    def test_max_webhooks_per_minute_parsed(self, tmp_path):
        """max_webhooks_per_minute is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
                "max_webhooks_per_minute": 10,
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 10

    def test_max_webhooks_per_minute_defaults_to_20(self, tmp_path):
        """max_webhooks_per_minute defaults to 20 when absent."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 20

    def test_invalid_mention_role_id_ignored(self, tmp_path, caplog):
        """Non-string mention_role_id is ignored with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "mention_role_id": 12345,
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] is None
        assert "mention_role_id must be string" in caplog.text

    def test_invalid_mention_severity_defaults(self, tmp_path, caplog):
        """Invalid mention_severity defaults to 'critical' with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "mention_severity": "bogus",
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "critical"
        assert "mention_severity invalid" in caplog.text

    def test_invalid_max_webhooks_defaults(self, tmp_path, caplog):
        """Invalid max_webhooks_per_minute defaults to 20 with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "max_webhooks_per_minute": -5,
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 20
        assert "max_webhooks_per_minute invalid" in caplog.text

    def test_webhook_delivery_constructed_in_wancontroller(self, tmp_path):
        """WANController constructs WebhookDelivery when alerting enabled with webhook_url."""
        from wanctl.wan_controller import WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/test",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            mock_router = MagicMock()
            mock_rtt = MagicMock()
            controller = WANController(
                wan_name="spectrum",
                config=config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=logging.getLogger("test"),
            )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
        finally:
            MetricsWriter._reset_instance()

    def test_empty_webhook_url_still_constructs(self, tmp_path, caplog):
        """Empty webhook_url still constructs WebhookDelivery (deliver silently skips)."""
        from wanctl.wan_controller import WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            with caplog.at_level(logging.WARNING):
                mock_router = MagicMock()
                mock_rtt = MagicMock()
                controller = WANController(
                    wan_name="spectrum",
                    config=config,
                    router=mock_router,
                    rtt_measurement=mock_rtt,
                    logger=logging.getLogger("test"),
                )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
            assert "webhook_url not set" in caplog.text
        finally:
            MetricsWriter._reset_instance()

    def test_http_url_rejected_with_warning(self, tmp_path, caplog):
        """http:// webhook_url is rejected with warning and treated as empty."""
        from wanctl.wan_controller import WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "http://insecure.example.com/hook",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            with caplog.at_level(logging.WARNING):
                mock_router = MagicMock()
                mock_rtt = MagicMock()
                controller = WANController(
                    wan_name="spectrum",
                    config=config,
                    router=mock_router,
                    rtt_measurement=mock_rtt,
                    logger=logging.getLogger("test"),
                )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
            assert "must start with https://" in caplog.text
        finally:
            MetricsWriter._reset_instance()

    def test_no_alerting_config_sets_webhook_none(self, tmp_path):
        """No alerting config sets _webhook_delivery to None."""
        from wanctl.wan_controller import WANController

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict({})
            cfg_dict.pop("alerting", None)
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            mock_router = MagicMock()
            mock_rtt = MagicMock()
            controller = WANController(
                wan_name="spectrum",
                config=config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=logging.getLogger("test"),
            )

            assert controller._webhook_delivery is None
        finally:
            MetricsWriter._reset_instance()

    def test_steering_config_parses_new_fields(self, tmp_path):
        """SteeringConfig parses mention_role_id, mention_severity, max_webhooks_per_minute."""
        config = _make_steering_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_role_id": "987654321",
                "mention_severity": "warning",
                "max_webhooks_per_minute": 15,
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] == "987654321"
        assert config.alerting_config["mention_severity"] == "warning"
        assert config.alerting_config["max_webhooks_per_minute"] == 15


class TestSIGUSR1WebhookReload:
    """Tests for SIGUSR1 webhook_url reload in steering daemon."""

    def test_reload_webhook_url_reads_yaml(self, tmp_path):
        """_reload_webhook_url_config() reads alerting.webhook_url from YAML."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict(
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/new",
                "default_cooldown_sec": 300,
                "rules": {},
            }
        )
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        # Build daemon with mocked internals
        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)
        mock_webhook = MagicMock()

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = mock_webhook

        daemon._reload_webhook_url_config()

        mock_webhook.update_webhook_url.assert_called_once_with(
            "https://discord.com/api/webhooks/new"
        )

    def test_reload_webhook_url_empty_yaml(self, tmp_path):
        """_reload_webhook_url_config() passes empty string when webhook_url absent."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict(
            {
                "enabled": True,
                "default_cooldown_sec": 300,
                "rules": {},
            }
        )
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)
        mock_webhook = MagicMock()

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = mock_webhook

        daemon._reload_webhook_url_config()

        mock_webhook.update_webhook_url.assert_called_once_with("")

    def test_reload_webhook_url_no_webhook_delivery(self, tmp_path):
        """_reload_webhook_url_config() is no-op when _webhook_delivery is None."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict({})
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = None

        # Should not raise
        daemon._reload_webhook_url_config()

    def test_reload_webhook_url_error_caught(self, tmp_path, caplog):
        """_reload_webhook_url_config() catches and logs errors."""
        from wanctl.steering.daemon import SteeringDaemon

        mock_config = MagicMock()
        mock_config.config_file_path = "/nonexistent/path.yaml"

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = MagicMock()

        with caplog.at_level(logging.WARNING):
            # Must not raise
            daemon._reload_webhook_url_config()

        assert "Failed to reload webhook_url" in caplog.text


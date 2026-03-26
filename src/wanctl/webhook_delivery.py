"""Webhook delivery subsystem: formatting, retry, rate-limiting, background dispatch.

Provides a generic AlertFormatter Protocol for extensibility (Discord, ntfy.sh, etc.)
and a concrete DiscordFormatter that produces rich color-coded embeds. WebhookDelivery
handles HTTP POST with retry on transient failures, rate-limiting, and non-blocking
background thread dispatch to avoid blocking the 50ms control loop.

Design principles:
- Never crash the daemon (all delivery errors caught and logged)
- Non-blocking: HTTP POST runs in daemon thread
- Retry only on transient errors (5xx/timeout), not 4xx
- Rate-limited to prevent Discord API abuse
- Formatter Protocol allows new backends without modifying delivery code
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import requests

from wanctl.rate_utils import RateLimiter

if TYPE_CHECKING:
    from wanctl.storage.writer import MetricsWriter

logger = logging.getLogger(__name__)

# WAN display name overrides
_WAN_DISPLAY_NAMES: dict[str, str] = {
    "spectrum": "Spectrum",
    "att": "ATT",
}


@runtime_checkable
class AlertFormatter(Protocol):
    """Protocol for alert formatters. Duck-typing compatible.

    Any class implementing format() with the correct signature satisfies this Protocol.
    Allows new formatter backends (ntfy.sh, Slack, etc.) without modifying delivery code.
    """

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
        """Format an alert into a payload dict suitable for HTTP POST.

        Args:
            alert_type: Snake_case alert type (e.g., "congestion_sustained").
            severity: Alert severity ("info", "warning", "critical", "recovery").
            wan_name: WAN identifier (e.g., "spectrum", "att").
            details: Structured dict with alert-specific data.
            mention_role_id: Optional role ID for @mentions.
            mention_severity: Minimum severity to trigger @mention.

        Returns:
            Dict payload for requests.post(url, json=payload).
        """
        ...  # pragma: no cover


class DiscordFormatter:
    """Format alerts as Discord webhook embeds with color-coded severity.

    Produces rich embeds with emoji-prefixed title, stacked fields (Severity, WAN,
    Timestamp), metrics code block, and footer with version + container info.

    Attributes:
        SEVERITY_COLORS: Map severity -> Discord embed color integer.
        SEVERITY_EMOJI: Map severity -> emoji prefix for title.
        SEVERITY_ORDER: Map severity -> numeric order for mention threshold.
    """

    SEVERITY_COLORS: dict[str, int] = {
        "critical": 0xE74C3C,
        "warning": 0xF39C12,
        "recovery": 0x2ECC71,
        "info": 0x3498DB,
    }

    SEVERITY_EMOJI: dict[str, str] = {
        "critical": "\U0001f534",  # red circle
        "warning": "\U0001f7e1",  # yellow circle
        "recovery": "\U0001f7e2",  # green circle
        "info": "\U0001f535",  # blue circle
    }

    SEVERITY_ORDER: dict[str, int] = {
        "info": 0,
        "recovery": 1,
        "warning": 2,
        "critical": 3,
    }

    # Unit suffixes based on key name patterns
    _UNIT_MAP: dict[str, str] = {
        "rate": "Mbps",
        "rtt": "ms",
        "delta": "ms",
        "baseline": "ms",
        "latency": "ms",
        "loss": "%",
    }

    def __init__(self, version: str, container_id: str) -> None:
        """Initialize DiscordFormatter.

        Args:
            version: Application version string for footer (e.g., "1.15.0").
            container_id: Container identifier for footer (e.g., "cake-spectrum").
        """
        self._version = version
        self._container_id = container_id

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
        """Format alert as Discord webhook payload with embed.

        Args:
            alert_type: Snake_case alert type.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict.
            mention_role_id: Optional Discord role ID for @mention.
            mention_severity: Minimum severity to trigger mention.

        Returns:
            Dict payload for requests.post(url, json=payload).
        """
        now = int(time.time())
        now_iso = datetime.now(UTC).isoformat()

        emoji = self.SEVERITY_EMOJI.get(severity, "\U0001f535")
        color = self.SEVERITY_COLORS.get(severity, 0x3498DB)
        title = f"{emoji} {self._title_case(alert_type)}"
        description = self._build_description(alert_type, severity, wan_name, details)

        # Stacked fields
        fields: list[dict[str, Any]] = [
            {"name": "Severity", "value": severity.capitalize(), "inline": True},
            {"name": "WAN", "value": self._wan_display_name(wan_name), "inline": True},
            {"name": "Timestamp", "value": f"<t:{now}:R>", "inline": True},
        ]

        # Metrics code block (only if there are numeric values)
        metrics_block = self._build_metrics_field(details)
        if metrics_block:
            fields.append({"name": "Metrics", "value": metrics_block, "inline": False})

        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": f"wanctl v{self._version} - {self._container_id}"},
            "timestamp": now_iso,
        }

        # Build content with optional mention
        content = ""
        if mention_role_id and self._should_mention(severity, mention_severity):
            content = f"<@&{mention_role_id}>"

        return {
            "username": "wanctl",
            "content": content,
            "embeds": [embed],
        }

    @staticmethod
    def _title_case(snake_str: str) -> str:
        """Convert snake_case alert type to Title Case.

        Args:
            snake_str: Snake_case string (e.g., "congestion_sustained").

        Returns:
            Title Case string (e.g., "Congestion Sustained").
        """
        return " ".join(word.capitalize() for word in snake_str.split("_"))

    @staticmethod
    def _wan_display_name(wan_name: str) -> str:
        """Get display-friendly WAN name.

        Args:
            wan_name: Raw WAN identifier.

        Returns:
            Display name (e.g., "spectrum" -> "Spectrum", "att" -> "ATT").
        """
        return _WAN_DISPLAY_NAMES.get(wan_name, wan_name.capitalize())

    @staticmethod
    def _build_description(
        alert_type: str, severity: str, wan_name: str, details: dict[str, Any]
    ) -> str:
        """Build one-line description for embed.

        Args:
            alert_type: Alert type identifier.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict.

        Returns:
            Human-readable one-line description.
        """
        wan_display = _WAN_DISPLAY_NAMES.get(wan_name, wan_name.capitalize())
        type_display = " ".join(word.capitalize() for word in alert_type.split("_"))

        if severity == "recovery":
            duration = details.get("duration", "")
            prev_state = details.get("previous_state", "")
            if duration and prev_state:
                return f"{wan_display} WAN recovered: was {prev_state} for {duration}, now GREEN"
            return f"{wan_display} WAN has recovered to normal state"

        state = details.get("state", severity.upper())
        return f"{wan_display} WAN: {type_display} ({severity} - {state})"

    def _build_metrics_field(self, details: dict[str, Any]) -> str:
        """Build aligned metrics code block from numeric details.

        Args:
            details: Alert details dict.

        Returns:
            Fenced code block string, or empty string if no numeric values.
        """
        numeric_items: list[tuple[str, float, str]] = []
        for key, value in details.items():
            if isinstance(value, (int, float)):
                unit = self._get_unit(key)
                numeric_items.append((key, value, unit))

        if not numeric_items:
            return ""

        # Calculate max label width for alignment
        max_label_len = max(len(item[0]) for item in numeric_items)

        lines: list[str] = []
        for label, value, unit in numeric_items:
            padded_label = label.ljust(max_label_len)
            if unit:
                lines.append(f"{padded_label}: {value} {unit}")
            else:
                lines.append(f"{padded_label}: {value}")

        return "```\n" + "\n".join(lines) + "\n```"

    @classmethod
    def _get_unit(cls, key: str) -> str:
        """Get unit suffix for a metric key.

        Args:
            key: Metric key name.

        Returns:
            Unit string (e.g., "Mbps", "ms") or empty string.
        """
        key_lower = key.lower()
        for pattern, unit in cls._UNIT_MAP.items():
            if pattern in key_lower:
                return unit
        return ""

    @classmethod
    def _should_mention(cls, severity: str, mention_severity: str) -> bool:
        """Check if severity meets mention threshold.

        Args:
            severity: Current alert severity.
            mention_severity: Minimum severity for mentions.

        Returns:
            True if severity >= mention_severity threshold.
        """
        sev_order = cls.SEVERITY_ORDER.get(severity, 0)
        threshold_order = cls.SEVERITY_ORDER.get(mention_severity, 3)
        return sev_order >= threshold_order


class WebhookDelivery:
    """Non-blocking webhook delivery with retry, rate-limiting, and status tracking.

    Dispatches HTTP POST to a webhook URL in a daemon thread so it never blocks
    the 50ms control loop. Retries on transient failures (5xx, timeout) with
    exponential backoff. Rate-limits to prevent Discord API abuse.

    Attributes:
        delivery_failures: Count of failed delivery attempts (for health endpoint).
    """

    # Retry configuration
    _MAX_ATTEMPTS: int = 3
    _INITIAL_DELAY: float = 2.0
    _BACKOFF_FACTOR: float = 2.0

    def __init__(
        self,
        formatter: AlertFormatter,
        webhook_url: str | None,
        max_per_minute: int = 20,
        writer: MetricsWriter | None = None,
        mention_role_id: str | None = None,
        mention_severity: str = "critical",
    ) -> None:
        """Initialize WebhookDelivery.

        Args:
            formatter: AlertFormatter instance for payload generation.
            webhook_url: Webhook URL for HTTP POST. Empty/None disables delivery.
            max_per_minute: Maximum webhook deliveries per minute (rate limit).
            writer: MetricsWriter instance for delivery_status updates. None disables.
            mention_role_id: Optional Discord role ID for @mentions.
            mention_severity: Minimum severity to trigger @mention.
        """
        self._formatter = formatter
        self._webhook_url = webhook_url or ""
        self._rate_limiter = RateLimiter(max_changes=max_per_minute, window_seconds=60)
        self._writer = writer
        self._mention_role_id = mention_role_id
        self._mention_severity = mention_severity
        self._delivery_failures = 0
        self._lock = threading.Lock()

    @property
    def delivery_failures(self) -> int:
        """Return count of failed delivery attempts."""
        return self._delivery_failures

    def deliver(
        self,
        alert_id: int | None,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
    ) -> None:
        """Submit delivery to a background thread (non-blocking).

        Args:
            alert_id: SQLite alert row ID for status updates. None skips status updates.
            alert_type: Snake_case alert type.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict.
        """
        if not self._webhook_url:
            return

        if not self._rate_limiter.can_change():
            logger.warning("Webhook rate limited, dropping delivery for %s", alert_type)
            return

        self._rate_limiter.record_change()

        thread = threading.Thread(
            target=self._do_deliver,
            args=(alert_id, alert_type, severity, wan_name, details),
            daemon=True,
        )
        thread.start()

    def _do_deliver(
        self,
        alert_id: int | None,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
    ) -> None:
        """Execute delivery with retry logic. Runs in daemon thread.

        Never raises -- all exceptions caught and logged.

        Args:
            alert_id: SQLite alert row ID.
            alert_type: Alert type.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict.
        """
        try:
            payload = self._formatter.format(
                alert_type,
                severity,
                wan_name,
                details,
                mention_role_id=self._mention_role_id,
                mention_severity=self._mention_severity,
            )
        except Exception:
            logger.warning("Failed to format webhook payload for %s", alert_type, exc_info=True)
            with self._lock:
                self._delivery_failures += 1
            return

        delay = self._INITIAL_DELAY

        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                response = requests.post(self._webhook_url, json=payload, timeout=10)
                response.raise_for_status()

                # Success
                if alert_id is not None:
                    self._update_delivery_status(alert_id, "delivered")
                logger.debug("Webhook delivered: %s (attempt %d)", alert_type, attempt)
                return

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if 400 <= status < 500 and status != 408:
                    # 4xx (except 408) = permanent failure, no retry
                    logger.warning(
                        "Webhook delivery failed (HTTP %d), not retrying: %s",
                        status,
                        alert_type,
                    )
                    with self._lock:
                        self._delivery_failures += 1
                    if alert_id is not None:
                        self._update_delivery_status(alert_id, "failed")
                    return

                # 5xx or 408 = retryable
                if attempt < self._MAX_ATTEMPTS:
                    logger.warning(
                        "Webhook delivery failed (HTTP %d), retrying in %.1fs: %s",
                        status,
                        delay,
                        alert_type,
                    )
                    time.sleep(delay)
                    delay *= self._BACKOFF_FACTOR
                    continue

                # Exhausted
                logger.warning(
                    "Webhook delivery failed after %d attempts: %s",
                    self._MAX_ATTEMPTS,
                    alert_type,
                )
                with self._lock:
                    self._delivery_failures += 1
                if alert_id is not None:
                    self._update_delivery_status(alert_id, "failed")
                return

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < self._MAX_ATTEMPTS:
                    logger.warning(
                        "Webhook delivery error (%s), retrying in %.1fs: %s",
                        type(e).__name__,
                        delay,
                        alert_type,
                    )
                    time.sleep(delay)
                    delay *= self._BACKOFF_FACTOR
                    continue

                logger.warning(
                    "Webhook delivery failed after %d attempts: %s",
                    self._MAX_ATTEMPTS,
                    alert_type,
                )
                with self._lock:
                    self._delivery_failures += 1
                if alert_id is not None:
                    self._update_delivery_status(alert_id, "failed")
                return

            except Exception:
                logger.warning(
                    "Unexpected webhook delivery error for %s",
                    alert_type,
                    exc_info=True,
                )
                with self._lock:
                    self._delivery_failures += 1
                if alert_id is not None:
                    self._update_delivery_status(alert_id, "failed")
                return

    def update_webhook_url(self, url: str) -> None:
        """Update webhook URL (for SIGUSR1 config reload).

        Validates https:// prefix for non-empty URLs. Logs warning if invalid.

        Args:
            url: New webhook URL. Empty string clears the URL (disabling delivery).
        """
        if not url:
            self._webhook_url = ""
            logger.info("Webhook URL cleared (delivery disabled)")
            return

        if not url.startswith("https://"):
            logger.warning("Invalid webhook URL (must start with https://): %s", url[:50])
            return

        self._webhook_url = url
        logger.info("Webhook URL updated")

    def _update_delivery_status(self, alert_id: int, status: str) -> None:
        """Update delivery_status in SQLite alerts table.

        Never raises -- logs warning on failure.

        Args:
            alert_id: Alert row ID.
            status: New status ("delivered" or "failed").
        """
        if self._writer is None:
            return

        try:
            self._writer.connection.execute(
                "UPDATE alerts SET delivery_status = ? WHERE id = ?",
                (status, alert_id),
            )
            self._writer.connection.commit()
        except Exception:
            logger.warning("Failed to update delivery_status for alert %d", alert_id, exc_info=True)

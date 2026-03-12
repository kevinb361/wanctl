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

import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

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
        now_iso = datetime.now(timezone.utc).isoformat()

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
                return (
                    f"{wan_display} WAN recovered: was {prev_state} for {duration}, "
                    f"now GREEN"
                )
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

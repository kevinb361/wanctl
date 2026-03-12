"""AlertEngine - Per-event cooldown suppression and SQLite persistence.

Provides a reusable alert engine that both autorate and steering daemons
instantiate. Handles accepting alert events, suppressing duplicates via
(type, wan) cooldown, and persisting fired alerts to the `alerts` table
in the existing metrics SQLite database.

Design principles:
- Never crash the daemon (all persistence errors caught and logged)
- Disabled by default (enabled gate checked first)
- Per-rule overrides for cooldown and enabled state
- Cooldown uses time.monotonic() to avoid system clock issues
"""

import json
import logging
import time
from typing import Any

from wanctl.storage.writer import MetricsWriter

logger = logging.getLogger(__name__)


class AlertEngine:
    """Core alert engine with per-event cooldown suppression and SQLite persistence.

    Each daemon instantiates its own AlertEngine. No cross-daemon coordination.
    Alerts are stored in the `alerts` table of the per-daemon MetricsWriter
    SQLite database.

    Attributes:
        _enabled: Master switch for the alert engine.
        _default_cooldown_sec: Default cooldown in seconds between same (type, wan) alerts.
        _rules: Map of alert_type -> {enabled, cooldown_sec, severity}.
        _writer: MetricsWriter instance for SQLite persistence (None disables persistence).
        _cooldowns: Map of (type, wan) -> monotonic timestamp of last fire.
    """

    def __init__(
        self,
        enabled: bool,
        default_cooldown_sec: int,
        rules: dict[str, dict],
        writer: MetricsWriter | None = None,
    ) -> None:
        """Initialize the alert engine.

        Args:
            enabled: Master switch. If False, all fire() calls return False.
            default_cooldown_sec: Default cooldown between duplicate (type, wan) alerts.
            rules: Map of type_name -> {enabled, cooldown_sec, severity}.
            writer: MetricsWriter instance for SQLite persistence. None disables persistence.
        """
        self._enabled = enabled
        self._default_cooldown_sec = default_cooldown_sec
        self._rules = rules
        self._writer = writer
        self._cooldowns: dict[tuple[str, str], float] = {}

    def fire(
        self,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
    ) -> bool:
        """Fire an alert event, subject to enabled gates and cooldown suppression.

        Args:
            alert_type: Alert type identifier (e.g., "congestion_sustained").
            severity: Alert severity ("info", "warning", "critical").
            wan_name: WAN identifier (e.g., "spectrum", "att").
            details: Structured dict with alert-specific data (JSON-serializable).

        Returns:
            True if alert fired (not suppressed), False if suppressed or disabled.
        """
        if not self._enabled:
            return False

        # Check per-rule enabled gate
        rule = self._rules.get(alert_type, {})
        if rule.get("enabled") is False:
            return False

        # Check cooldown suppression
        if self._is_cooled_down(alert_type, wan_name):
            return False

        # Record cooldown timestamp
        self._cooldowns[(alert_type, wan_name)] = time.monotonic()

        # Persist to SQLite
        self._persist_alert(alert_type, severity, wan_name, details)

        logger.info("Alert fired: %s [%s] on %s", alert_type, severity, wan_name)
        return True

    def _is_cooled_down(self, alert_type: str, wan_name: str) -> bool:
        """Check if (type, wan) is still within cooldown window.

        Args:
            alert_type: Alert type identifier.
            wan_name: WAN identifier.

        Returns:
            True if within cooldown (should suppress), False if cooldown expired or never fired.
        """
        key = (alert_type, wan_name)
        last_fire = self._cooldowns.get(key)
        if last_fire is None:
            return False

        cooldown_sec = self._rules.get(alert_type, {}).get(
            "cooldown_sec", self._default_cooldown_sec
        )
        return (time.monotonic() - last_fire) < cooldown_sec

    def _persist_alert(
        self,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
    ) -> None:
        """Persist alert event to SQLite alerts table.

        Never raises -- logs warning on failure to avoid crashing the daemon.

        Args:
            alert_type: Alert type identifier.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict (serialized to JSON).
        """
        if self._writer is None:
            return

        try:
            timestamp = int(time.time())
            details_json = json.dumps(details)
            self._writer.connection.execute(
                "INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, alert_type, severity, wan_name, details_json),
            )
        except Exception:
            logger.warning(
                "Failed to persist alert %s on %s", alert_type, wan_name, exc_info=True
            )

    def get_active_cooldowns(self) -> dict[tuple[str, str], float]:
        """Return active cooldowns with seconds remaining.

        Returns:
            Dict of (alert_type, wan_name) -> seconds remaining for active cooldowns.
            Expired cooldowns are excluded.
        """
        now = time.monotonic()
        active: dict[tuple[str, str], float] = {}

        for key, last_fire in self._cooldowns.items():
            alert_type = key[0]
            cooldown_sec = self._rules.get(alert_type, {}).get(
                "cooldown_sec", self._default_cooldown_sec
            )
            remaining = cooldown_sec - (now - last_fire)
            if remaining > 0:
                active[key] = remaining

        return active

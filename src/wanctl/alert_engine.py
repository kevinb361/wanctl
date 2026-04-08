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
from collections.abc import Callable
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
        _delivery_callback: Optional callback invoked after successful fire().
    """

    def __init__(
        self,
        enabled: bool,
        default_cooldown_sec: int,
        rules: dict[str, dict],
        writer: MetricsWriter | None = None,
        delivery_callback: Callable[[int | None, str, str, str, dict[str, Any]], None]
        | None = None,
    ) -> None:
        """Initialize the alert engine.

        Args:
            enabled: Master switch. If False, all fire() calls return False.
            default_cooldown_sec: Default cooldown between duplicate (type, wan) alerts.
            rules: Map of type_name -> {enabled, cooldown_sec, severity}.
            writer: MetricsWriter instance for SQLite persistence. None disables persistence.
            delivery_callback: Optional callback invoked after fire() succeeds.
                Receives (alert_id, alert_type, severity, wan_name, details).
                Errors are caught and logged (never crash).
        """
        self._enabled = enabled
        self._default_cooldown_sec = default_cooldown_sec
        self._rules = rules
        self._writer = writer
        self._delivery_callback = delivery_callback
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._fire_count: int = 0
        self._rule_key_map: dict[str, str] = {}

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    @property
    def enabled(self) -> bool:
        """Whether alerting is enabled."""
        return self._enabled

    @property
    def fire_count(self) -> int:
        """Total number of alerts fired (not suppressed) since startup."""
        return self._fire_count

    def fire(
        self,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
        *,
        rule_key: str | None = None,
    ) -> bool:
        """Fire an alert event, subject to enabled gates and cooldown suppression.

        Args:
            alert_type: Alert type identifier (e.g., "congestion_sustained").
            severity: Alert severity ("info", "warning", "critical").
            wan_name: WAN identifier (e.g., "spectrum", "att").
            details: Structured dict with alert-specific data (JSON-serializable).
            rule_key: Optional parent rule key for config lookup. When provided,
                uses this key instead of alert_type for rule enabled/cooldown lookup.
                The cooldown dict key remains (alert_type, wan_name).

        Returns:
            True if alert fired (not suppressed), False if suppressed or disabled.
        """
        if not self._enabled:
            return False

        # Store rule_key mapping for get_active_cooldowns()
        if rule_key is not None:
            self._rule_key_map[alert_type] = rule_key

        # Check per-rule enabled gate (use rule_key for config lookup)
        rule = self._rules.get(rule_key or alert_type, {})
        if rule.get("enabled") is False:
            return False

        # Check cooldown suppression
        if self._is_cooled_down(alert_type, wan_name, rule_key=rule_key):
            return False

        # Record cooldown timestamp and increment fire count
        self._cooldowns[(alert_type, wan_name)] = time.monotonic()
        self._fire_count += 1

        # Persist to SQLite
        alert_id = self._persist_alert(alert_type, severity, wan_name, details)

        # Invoke delivery callback (webhook, etc.)
        if self._delivery_callback is not None:
            try:
                self._delivery_callback(alert_id, alert_type, severity, wan_name, details)
            except Exception:
                logger.warning(
                    "Delivery callback failed for %s on %s",
                    alert_type,
                    wan_name,
                    exc_info=True,
                )

        logger.info("Alert fired: %s [%s] on %s", alert_type, severity, wan_name)
        return True

    def _is_cooled_down(
        self,
        alert_type: str,
        wan_name: str,
        *,
        rule_key: str | None = None,
    ) -> bool:
        """Check if (type, wan) is still within cooldown window.

        Args:
            alert_type: Alert type identifier.
            wan_name: WAN identifier.
            rule_key: Optional parent rule key for cooldown config lookup.

        Returns:
            True if within cooldown (should suppress), False if cooldown expired or never fired.
        """
        key = (alert_type, wan_name)
        last_fire = self._cooldowns.get(key)
        if last_fire is None:
            return False

        lookup_key = rule_key or alert_type
        cooldown_sec = self._rules.get(lookup_key, {}).get(
            "cooldown_sec", self._default_cooldown_sec
        )
        return (time.monotonic() - last_fire) < cooldown_sec

    def _persist_alert(
        self,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
    ) -> int | None:
        """Persist alert event to SQLite alerts table.

        Never raises -- logs warning on failure to avoid crashing the daemon.

        Args:
            alert_type: Alert type identifier.
            severity: Alert severity.
            wan_name: WAN identifier.
            details: Alert details dict (serialized to JSON).

        Returns:
            Row ID of the inserted alert, or None if no writer or on error.
        """
        if self._writer is None:
            return None

        try:
            timestamp = int(time.time())
            details_json = json.dumps(details)
            cursor = self._writer.connection.execute(
                "INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, alert_type, severity, wan_name, details_json),
            )
            return cursor.lastrowid
        except Exception:
            logger.warning("Failed to persist alert %s on %s", alert_type, wan_name, exc_info=True)
            return None

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
            # Use rule_key mapping if available (e.g., flapping_dl -> congestion_flapping)
            lookup_key = self._rule_key_map.get(alert_type, alert_type)
            cooldown_sec = self._rules.get(lookup_key, {}).get(
                "cooldown_sec", self._default_cooldown_sec
            )
            remaining = cooldown_sec - (now - last_fire)
            if remaining > 0:
                active[key] = remaining

        return active

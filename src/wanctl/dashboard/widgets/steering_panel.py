"""Steering status widget with confidence score and WAN awareness.

Renders steering daemon status from the steering health endpoint data.
Handles online, degraded, and offline states with appropriate visual treatment.
"""

from __future__ import annotations

from datetime import datetime

from rich.text import Text

from wanctl.dashboard.widgets.status_bar import format_duration

# Reuse state colors from wan_panel
STATE_COLORS: dict[str, str] = {
    "GREEN": "green",
    "YELLOW": "yellow",
    "SOFT_RED": "dark_orange",
    "RED": "bold red",
}


class SteeringPanel:
    """Steering status panel displaying mode, confidence, WAN awareness, and transition timing.

    Consumes the full steering health endpoint response dict.
    """

    def __init__(self) -> None:
        self._data: dict | None = None
        self._online: bool = False
        self._last_seen: datetime | None = None

    def update_from_data(
        self,
        data: dict | None,
        last_seen: datetime | None = None,
    ) -> None:
        """Update panel from steering health response.

        Args:
            data: Full steering health response dict, or None if offline.
            last_seen: Timestamp of last successful poll (used in offline display).
        """
        if data is None:
            self._online = False
            if last_seen is not None:
                self._last_seen = last_seen
            # Keep _data for frozen display
        else:
            self._data = data
            self._online = True
            self._last_seen = last_seen

    def render(self) -> Text:
        """Render the panel as a Rich Text object."""
        text = Text()
        dim = not self._online

        # Title with status badge
        text.append(" STEERING ", style="bold")
        if not self._online:
            text.append(" OFFLINE ", style="bold white on red")
        text.append("\n")

        # Offline last-seen timestamp
        if not self._online and self._last_seen is not None:
            ts = self._last_seen.strftime("%H:%M:%S")
            text.append(f"  Last seen: {ts}\n", style="dim")

        if self._data is None:
            text.append("  No data\n", style="dim")
            return text

        steering = self._data.get("steering", {})
        confidence = self._data.get("confidence", {})
        wan_awareness = self._data.get("wan_awareness", {})
        decision = self._data.get("decision", {})

        # Enabled/disabled + mode
        enabled = steering.get("enabled", False)
        mode = steering.get("mode", "unknown")
        if enabled:
            text.append(
                f"  Enabled [{mode}]\n",
                style="dim" if dim else "",
            )
        else:
            text.append("  Disabled\n", style="dim" if dim else "")

        # Confidence score (rounded to int)
        primary = confidence.get("primary", 0)
        text.append(
            f"  Confidence: {round(primary)}\n",
            style="dim" if dim else "",
        )

        # WAN awareness section
        wan_enabled = wan_awareness.get("enabled", False)
        if wan_enabled:
            zone = wan_awareness.get("zone", "UNKNOWN")
            zone_color = STATE_COLORS.get(zone, "white")
            contribution = wan_awareness.get("confidence_contribution", 0)
            grace_active = wan_awareness.get("grace_period_active", False)
            grace_str = "active" if grace_active else "inactive"

            text.append("  Zone: ", style="dim" if dim else "")
            text.append(zone, style=f"dim {zone_color}" if dim else zone_color)
            text.append(
                f"  Contrib: {contribution}  Grace: {grace_str}\n",
                style="dim" if dim else "",
            )
        else:
            text.append(
                "  WAN Awareness: disabled\n",
                style="dim" if dim else "",
            )

        # Transition timing
        time_in_state = decision.get("time_in_state_seconds", 0)
        if time_in_state > 0:
            duration_str = format_duration(time_in_state)
            text.append(
                f"  In state: {duration_str}\n",
                style="dim" if dim else "",
            )

        return text

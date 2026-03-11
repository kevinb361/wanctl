"""Per-WAN status widget with congestion state, rates, and RTT.

Renders a single WAN link's live status from autorate health endpoint data.
Handles online, degraded, and offline states with appropriate visual treatment.
"""

from __future__ import annotations

from datetime import datetime

from rich.text import Text

# Color mapping for congestion states
STATE_COLORS: dict[str, str] = {
    "GREEN": "green",
    "YELLOW": "yellow",
    "SOFT_RED": "dark_orange",
    "RED": "bold red",
}


def _parse_router_reachable(connectivity: object) -> bool:
    """Extract reachability from router_connectivity field.

    Handles both boolean (True/False) and dict ({"is_reachable": true}) formats.
    """
    if isinstance(connectivity, bool):
        return connectivity
    if isinstance(connectivity, dict):
        return bool(connectivity.get("is_reachable", False))
    return False


class WanPanel:
    """Per-WAN status panel displaying congestion state, rates, RTT, and router badge.

    Args:
        wan_name: Human-readable WAN identifier (e.g., "spectrum", "att").
        rate_limits: Optional ceiling rates from DashboardConfig.wan_rate_limits.
            Keys: dl_mbps, ul_mbps. When provided, rates display as "245.3 / 300.0 Mbps".
    """

    def __init__(
        self,
        wan_name: str = "",
        rate_limits: dict[str, float] | None = None,
    ) -> None:
        self.wan_name = wan_name
        self.rate_limits = rate_limits
        self._data: dict | None = None
        self._online: bool = False
        self._degraded: bool = False
        self._last_seen: datetime | None = None

    def update_from_data(
        self,
        wan_data: dict | None,
        status: str | None = None,
        last_seen: datetime | None = None,
    ) -> None:
        """Update panel from a wans[] array element.

        Args:
            wan_data: Single WAN element from autorate health response, or None if offline.
            status: Endpoint status string (e.g., "healthy", "degraded").
            last_seen: Timestamp of last successful poll (used in offline display).
        """
        if wan_data is None:
            self._online = False
            if last_seen is not None:
                self._last_seen = last_seen
            # Keep _data for frozen display
        else:
            self._data = wan_data
            self._online = True
            self._degraded = status == "degraded"
            self._last_seen = last_seen

    def render(self) -> Text:
        """Render the panel as a Rich Text object."""
        text = Text()
        dim = not self._online

        # Title line with WAN name and status badge
        text.append(f" {self.wan_name.upper()} ", style="bold")
        if not self._online:
            text.append(" OFFLINE ", style="bold white on red")
        elif self._degraded:
            text.append(" DEGRADED ", style="bold white on yellow")
        text.append("\n")

        # Offline last-seen timestamp
        if not self._online and self._last_seen is not None:
            ts = self._last_seen.strftime("%H:%M:%S")
            text.append(f"  Last seen: {ts}\n", style="dim")

        if self._data is None:
            text.append("  No data\n", style="dim")
            return text

        dl = self._data.get("download", {})
        ul = self._data.get("upload", {})
        dl_state = dl.get("state", "")
        ul_state = ul.get("state", "")

        # Congestion state -- most prominent element
        primary_state = dl_state or ul_state or "UNKNOWN"
        state_color = STATE_COLORS.get(primary_state, "white")
        style = f"dim {state_color}" if dim else state_color
        text.append(f"  {primary_state}\n", style=style)

        # Download rate
        dl_rate = dl.get("current_rate_mbps")
        if dl_rate is not None:
            dl_color = STATE_COLORS.get(dl_state, "white")
            dl_style = f"dim {dl_color}" if dim else dl_color
            if self.rate_limits and "dl_mbps" in self.rate_limits:
                text.append(
                    f"  DL {dl_rate:.1f} / {self.rate_limits['dl_mbps']:.1f} Mbps",
                    style="dim" if dim else "",
                )
            else:
                text.append(
                    f"  DL {dl_rate:.1f} Mbps",
                    style="dim" if dim else "",
                )
            text.append(f" [{dl_state}]", style=dl_style)
            text.append("\n")

        # Upload rate
        ul_rate = ul.get("current_rate_mbps")
        if ul_rate is not None:
            ul_color = STATE_COLORS.get(ul_state, "white")
            ul_style = f"dim {ul_color}" if dim else ul_color
            if self.rate_limits and "ul_mbps" in self.rate_limits:
                text.append(
                    f"  UL {ul_rate:.1f} / {self.rate_limits['ul_mbps']:.1f} Mbps",
                    style="dim" if dim else "",
                )
            else:
                text.append(
                    f"  UL {ul_rate:.1f} Mbps",
                    style="dim" if dim else "",
                )
            text.append(f" [{ul_state}]", style=ul_style)
            text.append("\n")

        # RTT: baseline -> load delta
        baseline = self._data.get("baseline_rtt_ms")
        load = self._data.get("load_rtt_ms")
        if baseline is not None and load is not None:
            delta = load - baseline
            text.append(
                f"  RTT {baseline:.1f} -> {load:.1f} D{delta:.1f}ms\n",
                style="dim" if dim else "",
            )

        # Router reachability badge
        connectivity = self._data.get("router_connectivity")
        if connectivity is not None:
            reachable = _parse_router_reachable(connectivity)
            if reachable:
                text.append("  [Router OK]\n", style="dim green" if dim else "green")
            else:
                text.append(
                    "  [Router UNREACHABLE]\n",
                    style="dim red" if dim else "bold red",
                )

        return text

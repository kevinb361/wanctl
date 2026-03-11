"""Bottom status bar widget with version, uptime, and disk space.

Provides a single-line summary at the bottom of the dashboard.
"""

from __future__ import annotations

from rich.text import Text


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration.

    Examples:
        0 -> "0s"
        45 -> "45s"
        125 -> "2m 5s"
        4980 -> "1h 23m"
        90000 -> "1d 1h"
        259200 -> "3d 0h"
    """
    total = int(seconds)
    if total <= 0:
        return "0s"

    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class StatusBar:
    """Bottom status bar showing version, uptime, and disk space status.

    Renders as a single compact line.
    """

    def __init__(self) -> None:
        self._version: str = ""
        self._uptime_seconds: float = 0.0
        self._disk_status: str = ""

    def update(self, version: str, uptime_seconds: float, disk_status: str) -> None:
        """Update status bar values.

        Args:
            version: Application version string (e.g., "1.13.0").
            uptime_seconds: Daemon uptime in seconds.
            disk_status: Disk space status string (e.g., "ok", "warning").
        """
        self._version = version
        self._uptime_seconds = uptime_seconds
        self._disk_status = disk_status

    def render(self) -> Text:
        """Render the status bar as a single-line Rich Text."""
        uptime_str = format_duration(self._uptime_seconds)
        text = Text()
        text.append(
            f" wanctl v{self._version} | Up {uptime_str} | Disk: {self._disk_status} ",
            style="bold",
        )
        return text

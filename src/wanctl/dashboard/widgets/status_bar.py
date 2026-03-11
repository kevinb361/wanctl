"""Bottom status bar widget — stub for TDD RED phase."""


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    raise NotImplementedError("GREEN phase not yet implemented")


class StatusBar:
    """Stub StatusBar for test collection."""

    def __init__(self) -> None:
        self._version: str = ""
        self._uptime_seconds: float = 0.0
        self._disk_status: str = ""

    def update(self, version: str, uptime_seconds: float, disk_status: str) -> None:
        raise NotImplementedError("GREEN phase not yet implemented")

    def render(self):
        raise NotImplementedError("GREEN phase not yet implemented")

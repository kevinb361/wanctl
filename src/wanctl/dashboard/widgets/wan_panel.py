"""Per-WAN status widget — stub for TDD RED phase."""

from datetime import datetime


class WanPanel:
    """Stub WanPanel for test collection."""

    def __init__(self, wan_name: str = "", rate_limits: dict | None = None) -> None:
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
        raise NotImplementedError("GREEN phase not yet implemented")

    def render(self):
        raise NotImplementedError("GREEN phase not yet implemented")

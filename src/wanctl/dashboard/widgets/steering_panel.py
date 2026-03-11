"""Steering status widget — stub for TDD RED phase."""

from datetime import datetime


class SteeringPanel:
    """Stub SteeringPanel for test collection."""

    def __init__(self) -> None:
        self._data: dict | None = None
        self._online: bool = False
        self._last_seen: datetime | None = None

    def update_from_data(
        self,
        data: dict | None,
        last_seen: datetime | None = None,
    ) -> None:
        raise NotImplementedError("GREEN phase not yet implemented")

    def render(self):
        raise NotImplementedError("GREEN phase not yet implemented")

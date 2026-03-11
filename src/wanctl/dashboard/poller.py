"""Async endpoint poller with independent polling and backoff.

Each EndpointPoller instance tracks its own state independently.
The DashboardApp creates one per endpoint and manages the httpx.AsyncClient lifecycle.
"""

import logging
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)


class EndpointPoller:
    """Polls a single HTTP health endpoint with backoff on failure.

    Args:
        name: Human-readable name for this endpoint (e.g., "autorate", "steering").
        base_url: Base URL of the health endpoint (e.g., "http://127.0.0.1:9101").
        normal_interval: Polling interval in seconds when online.
        backoff_interval: Polling interval in seconds when offline.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        normal_interval: float = 2.0,
        backoff_interval: float = 5.0,
    ) -> None:
        self.name = name
        self.base_url = base_url
        self._normal_interval = normal_interval
        self._backoff_interval = backoff_interval

        self._is_online: bool = False
        self._last_seen: datetime | None = None
        self._last_data: dict | None = None
        self._current_interval: float = normal_interval

    @property
    def is_online(self) -> bool:
        """Whether the last poll was successful."""
        return self._is_online

    @property
    def last_seen(self) -> datetime | None:
        """Timestamp of the last successful poll."""
        return self._last_seen

    @property
    def last_data(self) -> dict | None:
        """Most recent successful response data."""
        return self._last_data

    @property
    def current_interval(self) -> float:
        """Current polling interval in seconds."""
        return self._current_interval

    async def poll(self, client: httpx.AsyncClient) -> dict | None:
        """Poll the health endpoint.

        Args:
            client: Shared httpx.AsyncClient (managed by caller).

        Returns:
            Parsed JSON dict on success, None on failure.
        """
        url = f"{self.base_url}/health"
        try:
            response = await client.get(url, timeout=2.0)
            response.raise_for_status()
            data = response.json()

            self._last_data = data
            self._last_seen = datetime.now(tz=UTC)
            self._is_online = True
            self._current_interval = self._normal_interval

            return data

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.debug("Poll failed for %s (%s): %s", self.name, url, exc)
            self._is_online = False
            self._current_interval = self._backoff_interval
            return None

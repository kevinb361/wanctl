"""Tests for async endpoint poller with independent polling and backoff."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from wanctl.dashboard.poller import EndpointPoller


class TestEndpointPollerSuccess:
    """Test successful polling behavior."""

    def test_poll_returns_parsed_json_on_success(self):
        """EndpointPoller.poll() returns parsed JSON dict on successful HTTP 200."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy", "uptime_seconds": 3600}
        mock_client.get = AsyncMock(return_value=mock_response)

        result = asyncio.run(poller.poll(mock_client))
        assert result == {"status": "healthy", "uptime_seconds": 3600}

    def test_poll_tracks_last_seen_timestamp(self):
        """EndpointPoller tracks last_seen timestamp on successful poll."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        assert poller.last_seen is None

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_client.get = AsyncMock(return_value=mock_response)

        before = datetime.now(tz=timezone.utc)
        asyncio.run(poller.poll(mock_client))
        after = datetime.now(tz=timezone.utc)

        assert poller.last_seen is not None
        assert before <= poller.last_seen <= after

    def test_is_online_true_after_success(self):
        """EndpointPoller.is_online is True after success."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        assert poller.is_online is False

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_client.get = AsyncMock(return_value=mock_response)

        asyncio.run(poller.poll(mock_client))
        assert poller.is_online is True

    def test_last_data_holds_most_recent_response(self):
        """EndpointPoller.last_data holds the most recent successful response."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        assert poller.last_data is None

        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # First poll
        mock_response1 = MagicMock()
        mock_response1.raise_for_status = MagicMock()
        mock_response1.json.return_value = {"status": "healthy", "uptime_seconds": 100}
        mock_client.get = AsyncMock(return_value=mock_response1)
        asyncio.run(poller.poll(mock_client))
        assert poller.last_data == {"status": "healthy", "uptime_seconds": 100}

        # Second poll with different data
        mock_response2 = MagicMock()
        mock_response2.raise_for_status = MagicMock()
        mock_response2.json.return_value = {"status": "healthy", "uptime_seconds": 200}
        mock_client.get = AsyncMock(return_value=mock_response2)
        asyncio.run(poller.poll(mock_client))
        assert poller.last_data == {"status": "healthy", "uptime_seconds": 200}


class TestEndpointPollerFailure:
    """Test failure and error handling behavior."""

    def test_poll_returns_none_on_connect_error(self):
        """EndpointPoller.poll() returns None on connection error (httpx.ConnectError)."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = asyncio.run(poller.poll(mock_client))
        assert result is None

    def test_poll_returns_none_on_timeout(self):
        """EndpointPoller.poll() returns None on timeout (httpx.TimeoutException)."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        result = asyncio.run(poller.poll(mock_client))
        assert result is None

    def test_is_online_false_after_failure(self):
        """EndpointPoller.is_online is False after failure."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")

        # First make it online
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_client.get = AsyncMock(return_value=mock_response)
        asyncio.run(poller.poll(mock_client))
        assert poller.is_online is True

        # Then make it fail
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        asyncio.run(poller.poll(mock_client))
        assert poller.is_online is False

    def test_http_500_treated_as_failure(self):
        """EndpointPoller handles HTTP 500 as failure (returns None, goes offline)."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )
        mock_client.get = AsyncMock(return_value=mock_response)

        result = asyncio.run(poller.poll(mock_client))
        assert result is None
        assert poller.is_online is False


class TestEndpointPollerBackoff:
    """Test backoff interval behavior."""

    def test_interval_changes_to_backoff_after_failure(self):
        """EndpointPoller interval changes from normal (2s) to backoff (5s) after failure."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        assert poller.current_interval == 2.0

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        asyncio.run(poller.poll(mock_client))
        assert poller.current_interval == 5.0

    def test_interval_returns_to_normal_after_recovery(self):
        """EndpointPoller interval returns to normal (2s) after recovery."""
        poller = EndpointPoller("autorate", "http://127.0.0.1:9101")
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Fail first
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        asyncio.run(poller.poll(mock_client))
        assert poller.current_interval == 5.0

        # Then succeed
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_client.get = AsyncMock(return_value=mock_response)
        asyncio.run(poller.poll(mock_client))
        assert poller.current_interval == 2.0

    def test_custom_intervals(self):
        """Custom normal and backoff intervals are respected."""
        poller = EndpointPoller(
            "autorate", "http://127.0.0.1:9101",
            normal_interval=1.0, backoff_interval=10.0,
        )
        assert poller.current_interval == 1.0

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        asyncio.run(poller.poll(mock_client))
        assert poller.current_interval == 10.0


class TestEndpointPollerIndependence:
    """Test that multiple poller instances are independent."""

    def test_two_pollers_are_independent(self):
        """Two EndpointPoller instances are fully independent (one failing doesn't affect other)."""
        poller_a = EndpointPoller("autorate", "http://127.0.0.1:9101")
        poller_b = EndpointPoller("steering", "http://127.0.0.1:9102")

        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Poller A succeeds
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_client.get = AsyncMock(return_value=mock_response)
        asyncio.run(poller_a.poll(mock_client))

        # Poller B fails
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        asyncio.run(poller_b.poll(mock_client))

        # Verify independence
        assert poller_a.is_online is True
        assert poller_a.current_interval == 2.0
        assert poller_a.last_data == {"status": "healthy"}

        assert poller_b.is_online is False
        assert poller_b.current_interval == 5.0
        assert poller_b.last_data is None

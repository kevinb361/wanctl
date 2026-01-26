"""Tests for /metrics/history endpoint in health check HTTP server."""

import json
import socket
import time
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.health_check import (
    HealthCheckHandler,
    start_health_server,
)
from wanctl.storage.writer import MetricsWriter


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def reset_handler_state():
    """Reset HealthCheckHandler class state before each test."""
    HealthCheckHandler.controller = None
    HealthCheckHandler.start_time = None
    HealthCheckHandler.consecutive_failures = 0
    yield
    HealthCheckHandler.controller = None
    HealthCheckHandler.start_time = None
    HealthCheckHandler.consecutive_failures = 0


@pytest.fixture
def sample_db(tmp_path: Path):
    """Create a temporary database with sample metrics data.

    Creates 10 sample metrics with timestamps spanning the last hour.
    """
    db_path = tmp_path / "test_metrics.db"

    # Reset singleton before creating test instance
    MetricsWriter._reset_instance()

    writer = MetricsWriter(db_path=db_path)

    # Generate sample data: 10 metrics over the last 30 minutes
    base_time = int(time.time()) - 1800  # 30 minutes ago

    # write_metrics_batch expects list of tuples:
    # (timestamp, wan_name, metric_name, value, labels, granularity)
    metrics = []
    for i in range(10):
        timestamp = base_time + (i * 180)  # Every 3 minutes
        metrics.extend(
            [
                (timestamp, "spectrum", "wanctl_rtt_ms", 25.0 + i, None, "raw"),
                (timestamp, "spectrum", "wanctl_state", 1.0, None, "raw"),  # GREEN
            ]
        )

    writer.write_metrics_batch(metrics)

    yield db_path

    # Cleanup
    MetricsWriter._reset_instance()


class TestMetricsHistoryEndpoint:
    """Integration tests for /metrics/history endpoint."""

    def test_returns_json(self, sample_db: Path):
        """GET /metrics/history returns 200 and valid JSON."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    assert response.status == 200
                    data = json.loads(response.read().decode())

                assert "data" in data
                assert "metadata" in data
                assert isinstance(data["data"], list)
            finally:
                server.shutdown()

    def test_default_time_range(self, sample_db: Path):
        """No params defaults to last 1 hour."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should find our sample data from last 30 minutes
                assert data["metadata"]["total_count"] > 0
            finally:
                server.shutdown()

    def test_range_param(self, sample_db: Path):
        """?range=1h filters to last hour."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?range=1h"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should include our sample data
                assert data["metadata"]["total_count"] > 0
            finally:
                server.shutdown()

    def test_from_to_params(self, sample_db: Path):
        """?from=...&to=... filters by absolute time range."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                # Query for a time range that includes our data
                # Use a range < 6 hours to get "raw" granularity (matching our test data)
                from datetime import datetime

                now = datetime.now()
                from_dt = now.replace(hour=0, minute=0, second=0)  # Start of today
                to_dt = now  # Now

                from_iso = from_dt.isoformat()
                to_iso = to_dt.isoformat()

                url = f"http://127.0.0.1:{port}/metrics/history?from={from_iso}&to={to_iso}"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # Should find data and use the from/to we specified in query
                assert "query" in data["metadata"]
                assert data["metadata"]["query"]["start"] is not None
                assert data["metadata"]["query"]["end"] is not None
            finally:
                server.shutdown()

    def test_metrics_filter(self, sample_db: Path):
        """?metrics=wanctl_rtt_ms filters by metric name."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?metrics=wanctl_rtt_ms"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # All returned records should be wanctl_rtt_ms
                for record in data["data"]:
                    assert record["metric_name"] == "wanctl_rtt_ms"
            finally:
                server.shutdown()

    def test_wan_filter(self, sample_db: Path):
        """?wan=spectrum filters by WAN name."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?wan=spectrum"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                # All returned records should be spectrum
                for record in data["data"]:
                    assert record["wan_name"] == "spectrum"
            finally:
                server.shutdown()

    def test_pagination_limit(self, sample_db: Path):
        """?limit=5 returns at most 5 results."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=5"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                assert data["metadata"]["returned_count"] <= 5
                assert len(data["data"]) <= 5
                assert data["metadata"]["limit"] == 5
            finally:
                server.shutdown()

    def test_pagination_offset(self, sample_db: Path):
        """?offset=5 skips first 5 results."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                # First get all results
                url_all = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url_all, timeout=5) as response:
                    data_all = json.loads(response.read().decode())

                # Then get with offset
                url_offset = f"http://127.0.0.1:{port}/metrics/history?offset=5"
                with urllib.request.urlopen(url_offset, timeout=5) as response:
                    data_offset = json.loads(response.read().decode())

                # Offset should skip first 5
                assert data_offset["metadata"]["offset"] == 5
                if data_all["metadata"]["total_count"] > 5:
                    assert data_offset["metadata"]["returned_count"] == data_all["metadata"]["total_count"] - 5
            finally:
                server.shutdown()

    def test_pagination_metadata(self, sample_db: Path):
        """Response includes total_count and returned_count."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=3"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                assert "total_count" in data["metadata"]
                assert "returned_count" in data["metadata"]
                assert data["metadata"]["total_count"] >= data["metadata"]["returned_count"]
            finally:
                server.shutdown()

    def test_empty_results(self, tmp_path: Path):
        """Returns 200 with empty data array when no matches."""
        # Create empty database (just initialize writer without adding data)
        db_path = tmp_path / "empty.db"
        MetricsWriter._reset_instance()
        _ = MetricsWriter(db_path=db_path)
        MetricsWriter._reset_instance()

        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", db_path):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    assert response.status == 200
                    data = json.loads(response.read().decode())

                assert data["data"] == []
                assert data["metadata"]["total_count"] == 0
            finally:
                server.shutdown()

    def test_response_metadata_structure(self, sample_db: Path):
        """Verify all metadata fields are present."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                metadata = data["metadata"]
                assert "total_count" in metadata
                assert "returned_count" in metadata
                assert "granularity" in metadata
                assert "limit" in metadata
                assert "offset" in metadata
                assert "query" in metadata

                query = metadata["query"]
                assert "start" in query
                assert "end" in query
                assert "metrics" in query
                assert "wan" in query
            finally:
                server.shutdown()

    def test_timestamp_format_iso8601(self, sample_db: Path):
        """Data timestamps are ISO 8601 strings."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())

                if data["data"]:
                    # Check first record timestamp is ISO 8601
                    ts = data["data"][0]["timestamp"]
                    assert "T" in ts  # ISO 8601 has T separator
                    assert ":" in ts  # Has time component
            finally:
                server.shutdown()


class TestHistoryParamsValidation:
    """Tests for 400 error responses on invalid params."""

    def test_invalid_range_format(self, sample_db: Path):
        """?range=abc returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?range=abc"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_limit_not_integer(self, sample_db: Path):
        """?limit=abc returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?limit=abc"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_offset_not_integer(self, sample_db: Path):
        """?offset=xyz returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?offset=xyz"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()

    def test_invalid_from_timestamp(self, sample_db: Path):
        """?from=not-a-date returns 400."""
        port = find_free_port()
        with patch("wanctl.health_check.DEFAULT_DB_PATH", sample_db):
            server = start_health_server(host="127.0.0.1", port=port, controller=None)

            try:
                url = f"http://127.0.0.1:{port}/metrics/history?from=not-a-date"
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(url, timeout=5)

                assert exc_info.value.code == 400
                data = json.loads(exc_info.value.read().decode())
                assert "error" in data
                exc_info.value.close()
            finally:
                server.shutdown()


class TestHistoryHelperMethods:
    """Unit tests for helper methods used by /metrics/history."""

    def test_parse_duration_hours(self):
        """'1h' parses to 3600 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "1h")
        assert result == timedelta(seconds=3600)

    def test_parse_duration_minutes(self):
        """'30m' parses to 1800 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "30m")
        assert result == timedelta(seconds=1800)

    def test_parse_duration_days(self):
        """'7d' parses to 604800 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "7d")
        assert result == timedelta(seconds=604800)

    def test_parse_duration_weeks(self):
        """'2w' parses to 2 weeks in seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "2w")
        assert result == timedelta(seconds=604800 * 2)

    def test_parse_duration_seconds(self):
        """'60s' parses to 60 seconds."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_duration(handler, "60s")
        assert result == timedelta(seconds=60)

    def test_parse_duration_invalid(self):
        """Invalid format raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_duration(handler, "abc")
        assert "Invalid duration" in str(exc_info.value)

    def test_parse_duration_invalid_unit(self):
        """Invalid unit raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_duration(handler, "5x")
        assert "Invalid duration" in str(exc_info.value)

    def test_parse_iso_timestamp_basic(self):
        """Basic ISO 8601 timestamp parses correctly."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_iso_timestamp(handler, "2026-01-25T14:30:00")
        assert isinstance(result, int)
        assert result > 0

    def test_parse_iso_timestamp_with_timezone(self):
        """ISO 8601 with timezone parses correctly."""
        handler = MagicMock(spec=HealthCheckHandler)
        result = HealthCheckHandler._parse_iso_timestamp(handler, "2026-01-25T14:30:00+00:00")
        assert isinstance(result, int)
        assert result > 0

    def test_parse_iso_timestamp_invalid(self):
        """Invalid timestamp raises ValueError."""
        handler = MagicMock(spec=HealthCheckHandler)
        with pytest.raises(ValueError) as exc_info:
            HealthCheckHandler._parse_iso_timestamp(handler, "not-a-timestamp")
        assert "Invalid timestamp" in str(exc_info.value)

    def test_format_metric_iso8601(self):
        """Unix timestamp is converted to ISO 8601."""
        handler = MagicMock(spec=HealthCheckHandler)
        row = {
            "timestamp": 1737842400,  # Some Unix timestamp
            "wan_name": "spectrum",
            "metric_name": "wanctl_rtt_ms",
            "value": 25.5,
            "labels": None,
            "granularity": "raw",
        }
        result = HealthCheckHandler._format_metric(handler, row)

        assert "T" in result["timestamp"]  # ISO 8601 has T separator
        assert result["wan_name"] == "spectrum"
        assert result["metric_name"] == "wanctl_rtt_ms"
        assert result["value"] == 25.5

    def test_resolve_time_range_with_duration(self):
        """range param resolves to (now - duration, now)."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=timedelta(hours=1),
            from_ts=None,
            to_ts=None,
        )

        assert end_ts > start_ts
        assert (end_ts - start_ts) == 3600  # 1 hour

    def test_resolve_time_range_with_from_to(self):
        """from/to params resolve to specified range."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=None,
            from_ts=1000,
            to_ts=2000,
        )

        assert start_ts == 1000
        assert end_ts == 2000

    def test_resolve_time_range_default(self):
        """No params defaults to last 1 hour."""
        handler = MagicMock(spec=HealthCheckHandler)
        start_ts, end_ts = HealthCheckHandler._resolve_time_range(
            handler,
            range_duration=None,
            from_ts=None,
            to_ts=None,
        )

        assert end_ts > start_ts
        assert (end_ts - start_ts) == 3600  # 1 hour default

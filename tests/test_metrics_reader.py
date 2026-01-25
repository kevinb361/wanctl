"""Unit tests for storage reader module.

Tests for query_metrics, compute_summary, and select_granularity functions.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from wanctl.storage.reader import (
    compute_summary,
    query_metrics,
    select_granularity,
)
from wanctl.storage.schema import create_tables
from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def reset_singleton():
    """Reset the singleton before and after each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test_metrics.db"


@pytest.fixture
def populated_db(reset_singleton, test_db_path: Path) -> Path:
    """Create a database with test data for query tests."""
    writer = MetricsWriter(test_db_path)

    # Create test data spanning multiple timestamps, WANs, and metrics
    base_ts = 1706200000  # Fixed base timestamp for predictable tests

    test_data = [
        # Spectrum WAN - RTT metrics
        (base_ts, "spectrum", "wanctl_rtt_ms", 25.0, {"state": "GREEN"}, "raw"),
        (base_ts + 1, "spectrum", "wanctl_rtt_ms", 26.0, {"state": "GREEN"}, "raw"),
        (base_ts + 2, "spectrum", "wanctl_rtt_ms", 28.0, {"state": "YELLOW"}, "raw"),
        (base_ts + 60, "spectrum", "wanctl_rtt_ms", 24.0, None, "1m"),
        (base_ts + 120, "spectrum", "wanctl_rtt_ms", 25.5, None, "1m"),
        # Spectrum WAN - Rate metrics
        (base_ts, "spectrum", "wanctl_rate_download_mbps", 750.0, None, "raw"),
        (base_ts + 1, "spectrum", "wanctl_rate_download_mbps", 720.0, None, "raw"),
        (base_ts + 2, "spectrum", "wanctl_rate_download_mbps", 680.0, None, "raw"),
        # Spectrum WAN - State metrics
        (base_ts, "spectrum", "wanctl_state", 0.0, {"state": "GREEN"}, "raw"),
        (base_ts + 2, "spectrum", "wanctl_state", 1.0, {"state": "YELLOW"}, "raw"),
        # ATT WAN - RTT metrics
        (base_ts, "att", "wanctl_rtt_ms", 35.0, {"state": "GREEN"}, "raw"),
        (base_ts + 1, "att", "wanctl_rtt_ms", 36.0, {"state": "GREEN"}, "raw"),
        (base_ts + 60, "att", "wanctl_rtt_ms", 34.0, None, "1m"),
        # ATT WAN - Rate metrics
        (base_ts, "att", "wanctl_rate_download_mbps", 18.0, None, "raw"),
        (base_ts + 1, "att", "wanctl_rate_download_mbps", 17.5, None, "raw"),
    ]

    writer.write_metrics_batch(test_data)

    return test_db_path


# =============================================================================
# query_metrics Tests
# =============================================================================


class TestQueryMetricsEmptyCases:
    """Tests for query_metrics with empty/missing data."""

    def test_query_returns_empty_list_when_db_missing(self, tmp_path):
        """Test query returns empty list when database file doesn't exist."""
        nonexistent_db = tmp_path / "nonexistent.db"
        result = query_metrics(db_path=nonexistent_db)
        assert result == []

    def test_query_returns_empty_list_when_no_data_in_range(self, populated_db):
        """Test query returns empty list when no data matches time range."""
        # Query for timestamps way in the future
        result = query_metrics(
            db_path=populated_db,
            start_ts=2000000000,
            end_ts=2000000100,
        )
        assert result == []

    def test_query_returns_empty_list_when_table_missing(self, tmp_path):
        """Test query returns empty list when metrics table doesn't exist."""
        empty_db = tmp_path / "empty.db"
        # Create database without schema
        conn = sqlite3.connect(empty_db)
        conn.close()

        result = query_metrics(db_path=empty_db)
        assert result == []


class TestQueryMetricsTimeFilter:
    """Tests for query_metrics time range filtering."""

    def test_query_filters_by_time_range(self, populated_db):
        """Test query filters results by start_ts and end_ts."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts,
            end_ts=base_ts + 1,  # Only include first 2 seconds
        )

        # Should include all metrics from ts 1706200000 and 1706200001
        timestamps = [r["timestamp"] for r in result]
        assert all(base_ts <= ts <= base_ts + 1 for ts in timestamps)

    def test_query_with_only_start_ts(self, populated_db):
        """Test query with only start_ts filters correctly."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts + 60,  # Only 1m aggregates and later
        )

        # All results should be >= start_ts
        timestamps = [r["timestamp"] for r in result]
        assert all(ts >= base_ts + 60 for ts in timestamps)

    def test_query_with_only_end_ts(self, populated_db):
        """Test query with only end_ts filters correctly."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            end_ts=base_ts + 1,  # Only first 2 timestamps
        )

        # All results should be <= end_ts
        timestamps = [r["timestamp"] for r in result]
        assert all(ts <= base_ts + 1 for ts in timestamps)


class TestQueryMetricsNameFilter:
    """Tests for query_metrics metric name filtering."""

    def test_query_filters_by_metric_names(self, populated_db):
        """Test query filters by list of metric names."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms"],
        )

        # All results should be rtt_ms only
        metric_names = set(r["metric_name"] for r in result)
        assert metric_names == {"wanctl_rtt_ms"}

    def test_query_filters_by_multiple_metric_names(self, populated_db):
        """Test query filters by multiple metric names."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms", "wanctl_state"],
        )

        metric_names = set(r["metric_name"] for r in result)
        assert metric_names == {"wanctl_rtt_ms", "wanctl_state"}

    def test_query_with_nonexistent_metric_returns_empty(self, populated_db):
        """Test query with nonexistent metric name returns empty list."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["nonexistent_metric"],
        )
        assert result == []


class TestQueryMetricsWanFilter:
    """Tests for query_metrics WAN name filtering."""

    def test_query_filters_by_wan_name(self, populated_db):
        """Test query filters by WAN name."""
        result = query_metrics(
            db_path=populated_db,
            wan="spectrum",
        )

        wan_names = set(r["wan_name"] for r in result)
        assert wan_names == {"spectrum"}

    def test_query_filters_by_different_wan(self, populated_db):
        """Test query filters by different WAN name."""
        result = query_metrics(
            db_path=populated_db,
            wan="att",
        )

        wan_names = set(r["wan_name"] for r in result)
        assert wan_names == {"att"}

    def test_query_with_nonexistent_wan_returns_empty(self, populated_db):
        """Test query with nonexistent WAN returns empty list."""
        result = query_metrics(
            db_path=populated_db,
            wan="nonexistent_wan",
        )
        assert result == []


class TestQueryMetricsGranularityFilter:
    """Tests for query_metrics granularity filtering."""

    def test_query_filters_by_granularity(self, populated_db):
        """Test query filters by granularity."""
        result = query_metrics(
            db_path=populated_db,
            granularity="raw",
        )

        granularities = set(r["granularity"] for r in result)
        assert granularities == {"raw"}

    def test_query_filters_by_1m_granularity(self, populated_db):
        """Test query filters by 1m granularity."""
        result = query_metrics(
            db_path=populated_db,
            granularity="1m",
        )

        granularities = set(r["granularity"] for r in result)
        assert granularities == {"1m"}
        assert len(result) > 0


class TestQueryMetricsCombinedFilters:
    """Tests for query_metrics with multiple filters."""

    def test_query_combined_filters(self, populated_db):
        """Test query with time + metric + wan filters combined."""
        base_ts = 1706200000

        result = query_metrics(
            db_path=populated_db,
            start_ts=base_ts,
            end_ts=base_ts + 2,
            metrics=["wanctl_rtt_ms"],
            wan="spectrum",
        )

        # Verify all filters applied
        for row in result:
            assert base_ts <= row["timestamp"] <= base_ts + 2
            assert row["metric_name"] == "wanctl_rtt_ms"
            assert row["wan_name"] == "spectrum"

        # Should have exactly 3 raw RTT readings for spectrum in this range
        assert len(result) == 3


class TestQueryMetricsResultFormat:
    """Tests for query_metrics result format."""

    def test_query_returns_all_columns(self, populated_db):
        """Test query returns all expected columns."""
        result = query_metrics(db_path=populated_db)

        assert len(result) > 0

        # Check first row has all columns
        row = result[0]
        expected_columns = {"timestamp", "wan_name", "metric_name", "value", "labels", "granularity"}
        assert set(row.keys()) == expected_columns

    def test_query_labels_are_json_strings(self, populated_db):
        """Test labels column contains JSON strings or None."""
        result = query_metrics(
            db_path=populated_db,
            metrics=["wanctl_rtt_ms"],
            granularity="raw",
        )

        # Some should have labels, some None
        labeled_rows = [r for r in result if r["labels"] is not None]
        assert len(labeled_rows) > 0

        # Labels should be valid JSON
        for row in labeled_rows:
            labels = json.loads(row["labels"])
            assert isinstance(labels, dict)

    def test_query_results_ordered_by_timestamp_desc(self, populated_db):
        """Test results are ordered by timestamp descending."""
        result = query_metrics(db_path=populated_db)

        timestamps = [r["timestamp"] for r in result]
        assert timestamps == sorted(timestamps, reverse=True)


# =============================================================================
# compute_summary Tests
# =============================================================================


class TestComputeSummaryEmptyCases:
    """Tests for compute_summary with empty/edge case inputs."""

    def test_summary_empty_list_returns_empty_dict(self):
        """Test compute_summary returns empty dict for empty list."""
        result = compute_summary([])
        assert result == {}

    def test_summary_single_value(self):
        """Test compute_summary with single value returns that value for all stats."""
        result = compute_summary([42.5])

        assert result["min"] == 42.5
        assert result["max"] == 42.5
        assert result["avg"] == 42.5
        assert result["p50"] == 42.5
        assert result["p95"] == 42.5
        assert result["p99"] == 42.5


class TestComputeSummarySmallLists:
    """Tests for compute_summary with small lists."""

    def test_summary_two_values(self):
        """Test compute_summary with two values (edge case for quantiles)."""
        result = compute_summary([10.0, 20.0])

        assert result["min"] == 10.0
        assert result["max"] == 20.0
        assert result["avg"] == 15.0
        # Percentiles should be computed (interpolated between the two values)
        assert "p50" in result
        assert "p95" in result
        assert "p99" in result

    def test_summary_three_values(self):
        """Test compute_summary with three values."""
        result = compute_summary([10.0, 20.0, 30.0])

        assert result["min"] == 10.0
        assert result["max"] == 30.0
        assert result["avg"] == 20.0


class TestComputeSummaryManyValues:
    """Tests for compute_summary with larger datasets."""

    def test_summary_many_values_correct_stats(self):
        """Test compute_summary with many values produces correct statistics."""
        # Generate 100 values: 1, 2, 3, ..., 100
        values = list(range(1, 101))
        result = compute_summary([float(v) for v in values])

        assert result["min"] == 1.0
        assert result["max"] == 100.0
        assert result["avg"] == 50.5  # Mean of 1-100
        # p50 should be around 50
        assert 49 <= result["p50"] <= 51
        # p95 should be around 95
        assert 94 <= result["p95"] <= 96
        # p99 should be around 99
        assert 98 <= result["p99"] <= 100

    def test_summary_includes_all_keys(self):
        """Test compute_summary includes all expected keys."""
        result = compute_summary([1.0, 2.0, 3.0, 4.0, 5.0])

        expected_keys = {"min", "max", "avg", "p50", "p95", "p99"}
        assert set(result.keys()) == expected_keys

    def test_summary_with_floats(self):
        """Test compute_summary handles float values correctly."""
        values = [25.5, 26.3, 24.8, 27.1, 25.0]
        result = compute_summary(values)

        assert result["min"] == 24.8
        assert result["max"] == 27.1
        assert 25.5 <= result["avg"] <= 25.8  # Approximate

    def test_summary_with_identical_values(self):
        """Test compute_summary with all identical values."""
        values = [15.0] * 10
        result = compute_summary(values)

        assert result["min"] == 15.0
        assert result["max"] == 15.0
        assert result["avg"] == 15.0
        assert result["p50"] == 15.0
        assert result["p95"] == 15.0
        assert result["p99"] == 15.0


# =============================================================================
# select_granularity Tests
# =============================================================================


class TestSelectGranularity:
    """Tests for select_granularity auto-selection."""

    def test_granularity_under_6h_returns_raw(self):
        """Test time range under 6 hours returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts + (5 * 60 * 60)  # 5 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"

    def test_granularity_exactly_6h_returns_1m(self):
        """Test time range of exactly 6 hours returns '1m'."""
        start_ts = 1706200000
        end_ts = start_ts + (6 * 60 * 60)  # Exactly 6 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "1m"

    def test_granularity_under_24h_returns_1m(self):
        """Test time range under 24 hours (but >= 6h) returns '1m'."""
        start_ts = 1706200000
        end_ts = start_ts + (12 * 60 * 60)  # 12 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "1m"

    def test_granularity_exactly_24h_returns_5m(self):
        """Test time range of exactly 24 hours returns '5m'."""
        start_ts = 1706200000
        end_ts = start_ts + (24 * 60 * 60)  # 24 hours

        result = select_granularity(start_ts, end_ts)
        assert result == "5m"

    def test_granularity_under_7d_returns_5m(self):
        """Test time range under 7 days (but >= 24h) returns '5m'."""
        start_ts = 1706200000
        end_ts = start_ts + (3 * 24 * 60 * 60)  # 3 days

        result = select_granularity(start_ts, end_ts)
        assert result == "5m"

    def test_granularity_exactly_7d_returns_1h(self):
        """Test time range of exactly 7 days returns '1h'."""
        start_ts = 1706200000
        end_ts = start_ts + (7 * 24 * 60 * 60)  # 7 days

        result = select_granularity(start_ts, end_ts)
        assert result == "1h"

    def test_granularity_over_7d_returns_1h(self):
        """Test time range over 7 days returns '1h'."""
        start_ts = 1706200000
        end_ts = start_ts + (30 * 24 * 60 * 60)  # 30 days

        result = select_granularity(start_ts, end_ts)
        assert result == "1h"

    def test_granularity_very_short_range(self):
        """Test very short time range (seconds) returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts + 60  # 1 minute

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"

    def test_granularity_zero_range(self):
        """Test zero time range returns 'raw'."""
        start_ts = 1706200000
        end_ts = start_ts  # Same timestamp

        result = select_granularity(start_ts, end_ts)
        assert result == "raw"

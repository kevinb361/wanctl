"""Unit tests for storage downsampler module."""

import sqlite3
import time
from pathlib import Path

import pytest

from wanctl.storage.downsampler import (
    DOWNSAMPLE_THRESHOLDS,
    MODE_AGGREGATION_METRICS,
    downsample_metrics,
    downsample_to_granularity,
)
from wanctl.storage.schema import create_tables


@pytest.fixture
def test_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a test database with schema."""
    db_path = tmp_path / "test_metrics.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    create_tables(conn)
    return conn


def insert_metrics(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    values: list[float],
    start_timestamp: int,
    interval: int = 1,
    granularity: str = "raw",
) -> None:
    """Insert test metrics at regular intervals.

    Args:
        conn: Database connection
        metric_name: Metric name
        wan_name: WAN identifier
        values: List of values to insert
        start_timestamp: Unix timestamp for first value
        interval: Seconds between values
        granularity: Granularity level
    """
    rows = [
        (start_timestamp + i * interval, wan_name, metric_name, val, None, granularity)
        for i, val in enumerate(values)
    ]
    conn.executemany(
        """
        INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def align_to_bucket(timestamp: int, bucket_seconds: int) -> int:
    """Align timestamp to start of bucket boundary."""
    return (timestamp // bucket_seconds) * bucket_seconds


class TestDownsampleToGranularity:
    """Tests for downsample_to_granularity function."""

    def test_raw_to_1m_basic(self, test_db):
        """Test basic raw -> 1m downsampling."""
        now = int(time.time())
        # Align to minute boundary for predictable bucket count
        start = align_to_bucket(now - 7200, 60)
        values = [10.0 + i * 0.1 for i in range(60)]  # 10.0 to 15.9
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start)

        # Downsample with cutoff 1 hour ago
        cutoff = now - 3600
        rows = downsample_to_granularity(test_db, "raw", "1m", 60, cutoff)

        assert rows == 1  # One minute bucket

        # Verify aggregated row exists
        cursor = test_db.execute(
            "SELECT value, granularity FROM metrics WHERE granularity = '1m'"
        )
        row = cursor.fetchone()
        assert row is not None
        # AVG of 10.0 to 15.9 = 12.95
        assert 12.9 < row[0] < 13.0
        assert row[1] == "1m"

        # Verify raw data was deleted
        cursor = test_db.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity = 'raw'"
        )
        assert cursor.fetchone()[0] == 0

    def test_raw_to_1m_multiple_buckets(self, test_db):
        """Test raw -> 1m with multiple minute buckets."""
        now = int(time.time())
        # Align to minute boundary for predictable bucket count
        start = align_to_bucket(now - 7200, 60)
        values = [15.0] * 180  # 3 minutes of data
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start)

        cutoff = now - 3600
        rows = downsample_to_granularity(test_db, "raw", "1m", 60, cutoff)

        assert rows == 3  # Three minute buckets

        # Verify 3 aggregated rows
        cursor = test_db.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 3

    def test_1m_to_5m(self, test_db):
        """Test 1m -> 5m downsampling."""
        now = int(time.time())
        # Align to 5-minute boundary for predictable bucket count
        start = align_to_bucket(now - (2 * 86400), 300)
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start, interval=60, granularity="1m")

        cutoff = now - 86400  # 1 day ago
        rows = downsample_to_granularity(test_db, "1m", "5m", 300, cutoff)

        assert rows == 1  # One 5-minute bucket

        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '5m'"
        )
        row = cursor.fetchone()
        assert row is not None
        # AVG of 10, 20, 30, 40, 50 = 30
        assert row[0] == 30.0

    def test_5m_to_1h(self, test_db):
        """Test 5m -> 1h downsampling."""
        now = int(time.time())
        # Align to hour boundary for predictable bucket count
        start = align_to_bucket(now - (8 * 86400), 3600)
        values = [100.0] * 12  # 12 x 5min = 1 hour
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start, interval=300, granularity="5m")

        cutoff = now - (7 * 86400)  # 7 days ago
        rows = downsample_to_granularity(test_db, "5m", "1h", 3600, cutoff)

        assert rows == 1

        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '1h'"
        )
        assert cursor.fetchone()[0] == 100.0

    def test_preserves_recent_data(self, test_db):
        """Test that data within threshold is preserved."""
        now = int(time.time())
        # Insert recent raw data (30 minutes ago - within 1 hour threshold)
        start = now - 1800
        values = [15.0] * 60
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start)

        cutoff = now - 3600  # 1 hour ago
        rows = downsample_to_granularity(test_db, "raw", "1m", 60, cutoff)

        assert rows == 0  # Nothing to downsample

        # Raw data should still exist
        cursor = test_db.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity = 'raw'"
        )
        assert cursor.fetchone()[0] == 60

    def test_avg_aggregation_for_rtt(self, test_db):
        """Test AVG aggregation for RTT metrics."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)
        values = [10.0, 20.0, 30.0]  # AVG = 20.0
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", values, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 1
        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 20.0

    def test_avg_aggregation_for_rate(self, test_db):
        """Test AVG aggregation for rate metrics."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)
        values = [100.0, 200.0, 300.0]  # AVG = 200.0
        insert_metrics(test_db, "wanctl_rate_download_mbps", "spectrum", values, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 1
        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 200.0

    def test_mode_aggregation_for_state(self, test_db):
        """Test MODE aggregation for state metrics."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)
        # State values: 0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED
        # 5x GREEN, 3x YELLOW, 2x RED -> MODE = GREEN (0)
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 3.0, 3.0]
        insert_metrics(test_db, "wanctl_state", "spectrum", values, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 1
        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 0.0  # Most common: GREEN

    def test_mode_aggregation_for_steering(self, test_db):
        """Test MODE aggregation for steering_enabled metric."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)
        # More enabled (1) than disabled (0)
        values = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
        insert_metrics(test_db, "wanctl_steering_enabled", "spectrum", values, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 1
        cursor = test_db.execute(
            "SELECT value FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 1.0  # Most common: enabled

    def test_multiple_wans(self, test_db):
        """Test downsampling handles multiple WANs correctly."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)

        # Insert data for two WANs
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", [10.0] * 60, start)
        insert_metrics(test_db, "wanctl_rtt_ms", "att", [20.0] * 60, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 2  # One bucket per WAN

        cursor = test_db.execute(
            "SELECT wan_name, value FROM metrics WHERE granularity = '1m' ORDER BY wan_name"
        )
        rows_data = cursor.fetchall()
        assert rows_data[0] == ("att", 20.0)
        assert rows_data[1] == ("spectrum", 10.0)

    def test_multiple_metrics(self, test_db):
        """Test downsampling handles multiple metrics correctly."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)

        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", [10.0] * 60, start)
        insert_metrics(test_db, "wanctl_rate_download_mbps", "spectrum", [100.0] * 60, start)

        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)

        assert rows == 2  # One bucket per metric

    def test_empty_database(self, test_db):
        """Test downsampling empty database returns 0."""
        now = int(time.time())
        rows = downsample_to_granularity(test_db, "raw", "1m", 60, now - 3600)
        assert rows == 0


class TestDownsampleMetrics:
    """Tests for downsample_metrics function."""

    def test_returns_all_levels(self, test_db):
        """Test that result includes all downsampling levels."""
        results = downsample_metrics(test_db)

        assert "raw->1m" in results
        assert "1m->5m" in results
        assert "5m->1h" in results

    def test_processes_raw_to_1m(self, test_db):
        """Test raw->1m is processed."""
        now = int(time.time())
        # Align to minute boundary
        start = align_to_bucket(now - 7200, 60)
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", [15.0] * 60, start)

        results = downsample_metrics(test_db)

        assert results["raw->1m"] == 1
        cursor = test_db.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity = '1m'"
        )
        assert cursor.fetchone()[0] == 1

    def test_preserves_recent_raw_data(self, test_db):
        """Test that recent raw data is not downsampled."""
        now = int(time.time())
        # Insert raw data 30 minutes ago (within 1 hour threshold)
        start = now - 1800
        insert_metrics(test_db, "wanctl_rtt_ms", "spectrum", [15.0] * 60, start)

        results = downsample_metrics(test_db)

        assert results["raw->1m"] == 0
        cursor = test_db.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity = 'raw'"
        )
        assert cursor.fetchone()[0] == 60

    def test_cascade_downsampling(self, test_db):
        """Test that downsampling cascades through levels."""
        now = int(time.time())

        # Insert 1m data 2 days ago, aligned to 5-minute boundary
        start_1m = align_to_bucket(now - (2 * 86400), 300)
        insert_metrics(
            test_db, "wanctl_rtt_ms", "spectrum",
            [15.0] * 5, start_1m, interval=60, granularity="1m"
        )

        # Insert 5m data 8 days ago, aligned to hour boundary
        start_5m = align_to_bucket(now - (8 * 86400), 3600)
        insert_metrics(
            test_db, "wanctl_rtt_ms", "spectrum",
            [20.0] * 12, start_5m, interval=300, granularity="5m"
        )

        results = downsample_metrics(test_db)

        assert results["1m->5m"] == 1  # 5 minutes -> 1 bucket
        assert results["5m->1h"] == 1  # 1 hour -> 1 bucket


class TestDownsampleThresholds:
    """Tests for DOWNSAMPLE_THRESHOLDS configuration."""

    def test_thresholds_defined(self):
        """Test all expected thresholds are defined."""
        assert "raw_to_1m" in DOWNSAMPLE_THRESHOLDS
        assert "1m_to_5m" in DOWNSAMPLE_THRESHOLDS
        assert "5m_to_1h" in DOWNSAMPLE_THRESHOLDS

    def test_raw_to_1m_config(self):
        """Test raw->1m configuration."""
        config = DOWNSAMPLE_THRESHOLDS["raw_to_1m"]
        assert config["from_granularity"] == "raw"
        assert config["to_granularity"] == "1m"
        assert config["bucket_seconds"] == 60
        assert config["age_seconds"] == 3600  # 1 hour

    def test_1m_to_5m_config(self):
        """Test 1m->5m configuration."""
        config = DOWNSAMPLE_THRESHOLDS["1m_to_5m"]
        assert config["from_granularity"] == "1m"
        assert config["to_granularity"] == "5m"
        assert config["bucket_seconds"] == 300
        assert config["age_seconds"] == 86400  # 1 day

    def test_5m_to_1h_config(self):
        """Test 5m->1h configuration."""
        config = DOWNSAMPLE_THRESHOLDS["5m_to_1h"]
        assert config["from_granularity"] == "5m"
        assert config["to_granularity"] == "1h"
        assert config["bucket_seconds"] == 3600
        assert config["age_seconds"] == 604800  # 7 days


class TestModeAggregationMetrics:
    """Tests for MODE_AGGREGATION_METRICS configuration."""

    def test_state_uses_mode(self):
        """Test wanctl_state uses MODE aggregation."""
        assert "wanctl_state" in MODE_AGGREGATION_METRICS

    def test_steering_enabled_uses_mode(self):
        """Test wanctl_steering_enabled uses MODE aggregation."""
        assert "wanctl_steering_enabled" in MODE_AGGREGATION_METRICS

    def test_rtt_not_in_mode_metrics(self):
        """Test RTT metrics are not in MODE set (use AVG)."""
        assert "wanctl_rtt_ms" not in MODE_AGGREGATION_METRICS
        assert "wanctl_rtt_baseline_ms" not in MODE_AGGREGATION_METRICS
        assert "wanctl_rtt_delta_ms" not in MODE_AGGREGATION_METRICS

    def test_rate_not_in_mode_metrics(self):
        """Test rate metrics are not in MODE set (use AVG)."""
        assert "wanctl_rate_download_mbps" not in MODE_AGGREGATION_METRICS
        assert "wanctl_rate_upload_mbps" not in MODE_AGGREGATION_METRICS

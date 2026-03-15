"""Unit tests for storage schema module."""

import sqlite3

import pytest

from wanctl.storage.schema import (
    BENCHMARKS_SCHEMA,
    METRICS_SCHEMA,
    STORED_METRICS,
    create_tables,
)


class TestStoredMetrics:
    """Tests for STORED_METRICS constant."""

    def test_stored_metrics_has_expected_keys(self):
        """Test STORED_METRICS contains all expected metric names."""
        expected_keys = {
            "wanctl_rtt_ms",
            "wanctl_rtt_baseline_ms",
            "wanctl_rtt_delta_ms",
            "wanctl_rate_download_mbps",
            "wanctl_rate_upload_mbps",
            "wanctl_state",
            "wanctl_steering_enabled",
            "wanctl_wan_zone",
            "wanctl_wan_weight",
            "wanctl_wan_staleness_sec",
        }
        assert set(STORED_METRICS.keys()) == expected_keys

    def test_stored_metrics_values_are_strings(self):
        """Test all STORED_METRICS values are non-empty strings."""
        for key, value in STORED_METRICS.items():
            assert isinstance(value, str), f"{key} value should be string"
            assert len(value) > 0, f"{key} description should not be empty"

    def test_stored_metrics_prometheus_naming(self):
        """Test metric names follow Prometheus naming conventions."""
        for key in STORED_METRICS.keys():
            # Must start with letter or underscore
            assert key[0].isalpha() or key[0] == "_"
            # Only alphanumeric and underscores
            assert all(c.isalnum() or c == "_" for c in key)
            # Should use wanctl_ prefix
            assert key.startswith("wanctl_")


class TestMetricsSchema:
    """Tests for METRICS_SCHEMA constant."""

    def test_schema_is_string(self):
        """Test METRICS_SCHEMA is a non-empty string."""
        assert isinstance(METRICS_SCHEMA, str)
        assert len(METRICS_SCHEMA) > 0

    def test_schema_creates_metrics_table(self):
        """Test schema contains CREATE TABLE for metrics."""
        assert "CREATE TABLE IF NOT EXISTS metrics" in METRICS_SCHEMA

    def test_schema_has_required_columns(self):
        """Test schema defines all required columns."""
        required_columns = [
            "id INTEGER PRIMARY KEY",
            "timestamp INTEGER NOT NULL",
            "wan_name TEXT NOT NULL",
            "metric_name TEXT NOT NULL",
            "value REAL NOT NULL",
            "labels TEXT",
            "granularity TEXT DEFAULT 'raw'",
        ]
        for column in required_columns:
            assert column in METRICS_SCHEMA, f"Missing column: {column}"

    def test_schema_has_indexes(self):
        """Test schema creates all required indexes."""
        required_indexes = [
            "idx_metrics_timestamp",
            "idx_metrics_wan_metric_time",
            "idx_metrics_granularity_time",
        ]
        for index in required_indexes:
            assert index in METRICS_SCHEMA, f"Missing index: {index}"


class TestCreateTables:
    """Tests for create_tables function."""

    @pytest.fixture
    def memory_db(self):
        """Provide an in-memory SQLite connection."""
        conn = sqlite3.connect(":memory:")
        yield conn
        conn.close()

    def test_create_tables_creates_metrics_table(self, memory_db):
        """Test create_tables creates the metrics table."""
        create_tables(memory_db)

        # Check table exists
        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "metrics"

    def test_create_tables_creates_indexes(self, memory_db):
        """Test create_tables creates all indexes."""
        create_tables(memory_db)

        # Get all indexes
        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_metrics%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        expected_indexes = {
            "idx_metrics_timestamp",
            "idx_metrics_wan_metric_time",
            "idx_metrics_granularity_time",
        }
        assert indexes == expected_indexes

    def test_create_tables_idempotent(self, memory_db):
        """Test create_tables can be called multiple times safely."""
        # Call multiple times - should not raise
        create_tables(memory_db)
        create_tables(memory_db)
        create_tables(memory_db)

        # Table should still exist and be functional
        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        assert cursor.fetchone() is not None

    def test_create_tables_table_schema(self, memory_db):
        """Test created table has correct column structure."""
        create_tables(memory_db)

        # Get table info
        cursor = memory_db.execute("PRAGMA table_info(metrics)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "id": "INTEGER",
            "timestamp": "INTEGER",
            "wan_name": "TEXT",
            "metric_name": "TEXT",
            "value": "REAL",
            "labels": "TEXT",
            "granularity": "TEXT",
        }
        assert columns == expected_columns

    def test_create_tables_allows_insert(self, memory_db):
        """Test created table accepts valid inserts."""
        create_tables(memory_db)

        # Insert a test row
        memory_db.execute(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1706200000, "spectrum", "wanctl_rtt_ms", 15.5, None, "raw"),
        )
        memory_db.commit()

        # Verify insert
        cursor = memory_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 1

    def test_create_tables_granularity_default(self, memory_db):
        """Test granularity defaults to 'raw' when not specified."""
        create_tables(memory_db)

        # Insert without granularity
        memory_db.execute(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value)
            VALUES (?, ?, ?, ?)
            """,
            (1706200000, "spectrum", "wanctl_rtt_ms", 15.5),
        )
        memory_db.commit()

        # Verify default
        cursor = memory_db.execute("SELECT granularity FROM metrics")
        assert cursor.fetchone()[0] == "raw"


class TestBenchmarksSchema:
    """Tests for BENCHMARKS_SCHEMA constant and benchmarks table creation."""

    def test_schema_is_string(self):
        """BENCHMARKS_SCHEMA is a non-empty string."""
        assert isinstance(BENCHMARKS_SCHEMA, str)
        assert len(BENCHMARKS_SCHEMA) > 0

    def test_schema_creates_benchmarks_table(self):
        """Schema contains CREATE TABLE for benchmarks."""
        assert "CREATE TABLE IF NOT EXISTS benchmarks" in BENCHMARKS_SCHEMA

    def test_schema_has_required_columns(self):
        """Schema defines all 19 required columns."""
        required = [
            "id INTEGER PRIMARY KEY",
            "timestamp TEXT NOT NULL",
            "wan_name TEXT NOT NULL",
            "download_grade TEXT",
            "upload_grade TEXT",
            "download_latency_avg REAL",
            "download_latency_p50 REAL",
            "download_latency_p95 REAL",
            "download_latency_p99 REAL",
            "upload_latency_avg REAL",
            "upload_latency_p50 REAL",
            "upload_latency_p95 REAL",
            "upload_latency_p99 REAL",
            "download_throughput REAL",
            "upload_throughput REAL",
            "baseline_rtt REAL",
            "server TEXT",
            "duration INTEGER",
            "daemon_running INTEGER",
            "label TEXT",
        ]
        for col in required:
            assert col in BENCHMARKS_SCHEMA, f"Missing column: {col}"

    def test_schema_has_indexes(self):
        """Schema creates timestamp and WAN indexes."""
        assert "idx_benchmarks_timestamp" in BENCHMARKS_SCHEMA
        assert "idx_benchmarks_wan" in BENCHMARKS_SCHEMA

    @pytest.fixture
    def memory_db(self):
        """Provide an in-memory SQLite connection."""
        conn = sqlite3.connect(":memory:")
        yield conn
        conn.close()

    def test_create_tables_creates_benchmarks_table(self, memory_db):
        """create_tables() creates benchmarks table alongside metrics/alerts."""
        create_tables(memory_db)

        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "benchmarks"

    def test_benchmarks_columns(self, memory_db):
        """Benchmarks table has correct column names and types."""
        create_tables(memory_db)

        cursor = memory_db.execute("PRAGMA table_info(benchmarks)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected = {
            "id": "INTEGER",
            "timestamp": "TEXT",
            "wan_name": "TEXT",
            "download_grade": "TEXT",
            "upload_grade": "TEXT",
            "download_latency_avg": "REAL",
            "download_latency_p50": "REAL",
            "download_latency_p95": "REAL",
            "download_latency_p99": "REAL",
            "upload_latency_avg": "REAL",
            "upload_latency_p50": "REAL",
            "upload_latency_p95": "REAL",
            "upload_latency_p99": "REAL",
            "download_throughput": "REAL",
            "upload_throughput": "REAL",
            "baseline_rtt": "REAL",
            "server": "TEXT",
            "duration": "INTEGER",
            "daemon_running": "INTEGER",
            "label": "TEXT",
        }
        assert columns == expected

    def test_benchmarks_indexes(self, memory_db):
        """create_tables() creates both benchmark indexes."""
        create_tables(memory_db)

        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_benchmarks%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert indexes == {"idx_benchmarks_timestamp", "idx_benchmarks_wan"}

    def test_benchmarks_insert(self, memory_db):
        """Benchmarks table accepts valid inserts."""
        create_tables(memory_db)

        memory_db.execute(
            """
            INSERT INTO benchmarks (
                timestamp, wan_name, download_grade, upload_grade,
                download_latency_avg, download_latency_p50, download_latency_p95,
                download_latency_p99, upload_latency_avg, upload_latency_p50,
                upload_latency_p95, upload_latency_p99, download_throughput,
                upload_throughput, baseline_rtt, server, duration,
                daemon_running, label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-03-15T12:00:00+00:00", "spectrum", "A+", "A+",
                3.2, 2.8, 8.1, 12.4, 3.2, 2.8, 8.1, 12.4,
                94.2, 11.3, 23.1, "netperf.bufferbloat.net", 60,
                0, None,
            ),
        )
        memory_db.commit()

        cursor = memory_db.execute("SELECT COUNT(*) FROM benchmarks")
        assert cursor.fetchone()[0] == 1

    def test_benchmarks_idempotent(self, memory_db):
        """create_tables can be called multiple times safely with benchmarks."""
        create_tables(memory_db)
        create_tables(memory_db)
        create_tables(memory_db)

        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'"
        )
        assert cursor.fetchone() is not None

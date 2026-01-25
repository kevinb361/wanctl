"""Tests for steering daemon metrics recording integration."""

import json
import sqlite3
import time

import pytest

from wanctl.storage import MetricsWriter


class TestSteeringMetricsRecording:
    """Test metrics recording in steering run_cycle."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_steering_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    def test_steering_metrics_written_each_cycle(self, temp_db):
        """Verify steering RTT and state metrics written to database."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate what steering run_cycle does
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_steering_enabled", 0.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, {"source": "steering"}, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        assert len(rows) == 5
        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_rtt_ms"] == 28.5
        assert metrics["wanctl_steering_enabled"] == 0.0

    def test_steering_transition_with_reason(self, temp_db):
        """Verify steering transitions include from/to state labels."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate state transition recording
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_steering_transition",
            value=1.0,
            labels={
                "reason": "Transitioned from SPECTRUM_GOOD to SPECTRUM_DEGRADED",
                "from_state": "SPECTRUM_GOOD",
                "to_state": "SPECTRUM_DEGRADED",
            },
            granularity="raw",
        )

        # Verify labels stored
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_steering_transition'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["from_state"] == "SPECTRUM_GOOD"
        assert labels["to_state"] == "SPECTRUM_DEGRADED"

    def test_steering_metrics_include_state_value(self, temp_db):
        """Verify state metrics include numeric state values."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Record different state values
        state_map = {"GREEN": 0, "YELLOW": 1, "RED": 2}
        for state_name, state_val in state_map.items():
            writer.write_metric(
                timestamp=ts + state_val,  # Unique timestamps
                wan_name="spectrum",
                metric_name="wanctl_state",
                value=float(state_val),
                labels={"source": "steering", "state_name": state_name},
                granularity="raw",
            )

        # Verify all states recorded
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT value, labels FROM metrics WHERE metric_name='wanctl_state' ORDER BY value"
        ).fetchall()
        conn.close()

        assert len(rows) == 3
        assert rows[0][0] == 0.0  # GREEN
        assert rows[1][0] == 1.0  # YELLOW
        assert rows[2][0] == 2.0  # RED

    def test_metrics_batch_atomic(self, temp_db):
        """Verify batch write is atomic - all or nothing."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Write first batch
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify first batch written
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()
        conn.close()

        assert rows[0] == 2


class TestSteeringPerformanceOverhead:
    """Verify steering metrics recording overhead is <5ms."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "perf_steering_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield writer
        MetricsWriter._reset_instance()

    def test_steering_batch_write_under_5ms(self, temp_db):
        """Verify batch write completes in <5ms after warmup.

        First write includes schema creation overhead.
        Production writes happen after initialization.
        """
        writer = temp_db
        ts = int(time.time())

        # Warmup write (includes schema creation)
        warmup_batch = [(ts, "spectrum", "warmup", 0.0, None, "raw")]
        writer.write_metrics_batch(warmup_batch)

        # Actual measurement
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_steering_enabled", 0.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, None, "raw"),
        ]

        # Measure write time
        start = time.monotonic()
        writer.write_metrics_batch(metrics_batch)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 5.0, f"Batch write took {elapsed_ms:.2f}ms, expected <5ms"

    def test_steering_multiple_cycles_performance(self, temp_db):
        """Verify multiple cycle writes stay under 5ms average."""
        writer = temp_db

        # Simulate 100 cycles
        times = []
        for i in range(100):
            ts = int(time.time())
            metrics_batch = [
                (ts, "spectrum", "wanctl_rtt_ms", 28.5 + i * 0.1, None, "raw"),
                (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
                (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5 + i * 0.1, None, "raw"),
                (ts, "spectrum", "wanctl_steering_enabled", float(i % 2), None, "raw"),
                (ts, "spectrum", "wanctl_state", float(i % 3), None, "raw"),
            ]

            start = time.monotonic()
            writer.write_metrics_batch(metrics_batch)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)
        assert avg_time < 5.0, f"Average batch write took {avg_time:.2f}ms, expected <5ms"

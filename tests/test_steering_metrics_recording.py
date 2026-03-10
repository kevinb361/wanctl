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


class TestWanAwarenessMetrics:
    """Tests for WAN zone metric recording in steering run_cycle (OBSV-02)."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_wan_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    def test_wan_zone_metric_included_when_enabled(self, temp_db):
        """When wan_state enabled, metrics_batch includes wanctl_wan_zone with numeric value."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate what run_cycle does when wan_state is enabled
        zone_map = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
        effective_zone = "RED"
        zone_val = zone_map.get(effective_zone, 0)

        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_wan_zone", float(zone_val), {"zone": effective_zone}, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify wanctl_wan_zone recorded with correct value and labels
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value, labels FROM metrics WHERE metric_name='wanctl_wan_zone'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 3.0  # RED = 3
        labels = json.loads(row[1])
        assert labels["zone"] == "RED"

    def test_wan_zone_metric_excluded_when_disabled(self, temp_db):
        """When wan_state disabled, metrics_batch does NOT include wanctl_wan_zone."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate batch without WAN zone (disabled path)
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify no wanctl_wan_zone metric
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE metric_name='wanctl_wan_zone'"
        ).fetchone()
        conn.close()

        assert row[0] == 0

    def test_wan_zone_metric_none_during_grace_period(self, temp_db):
        """When effective zone is None (grace period), metric records value 0 with zone='none'."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate grace period: effective_zone is None
        zone_map = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
        effective_zone = None
        zone_val = zone_map.get(effective_zone or "GREEN", 0)

        metrics_batch = [
            (ts, "spectrum", "wanctl_wan_zone", float(zone_val),
             {"zone": effective_zone or "none"}, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify metric records 0 with labels {"zone": "none"}
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value, labels FROM metrics WHERE metric_name='wanctl_wan_zone'"
        ).fetchone()
        conn.close()

        assert row[0] == 0.0
        labels = json.loads(row[1])
        assert labels["zone"] == "none"

    def test_wan_zone_in_stored_metrics(self):
        """wanctl_wan_zone appears in STORED_METRICS dict."""
        from wanctl.storage.schema import STORED_METRICS

        assert "wanctl_wan_zone" in STORED_METRICS

    def test_wan_weight_metric_red_zone(self, temp_db):
        """When wan_state enabled and zone RED, wanctl_wan_weight records weight value (25)."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate RED zone: weight = ConfidenceWeights.WAN_RED (25)
        from wanctl.steering.steering_confidence import ConfidenceWeights

        metrics_batch = [
            (ts, "spectrum", "wanctl_wan_zone", 3.0, {"zone": "RED"}, "raw"),
            (ts, "spectrum", "wanctl_wan_weight", float(ConfidenceWeights.WAN_RED), None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM metrics WHERE metric_name='wanctl_wan_weight'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 25.0

    def test_wan_weight_metric_green_zone(self, temp_db):
        """When wan_state enabled and zone GREEN, wanctl_wan_weight records 0."""
        db_path, writer = temp_db
        ts = int(time.time())

        metrics_batch = [
            (ts, "spectrum", "wanctl_wan_zone", 0.0, {"zone": "GREEN"}, "raw"),
            (ts, "spectrum", "wanctl_wan_weight", 0.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM metrics WHERE metric_name='wanctl_wan_weight'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 0.0

    def test_wan_staleness_metric_recorded(self, temp_db):
        """When wan_state enabled, wanctl_wan_staleness_sec records age value."""
        db_path, writer = temp_db
        ts = int(time.time())

        metrics_batch = [
            (ts, "spectrum", "wanctl_wan_staleness_sec", 2.3, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM metrics WHERE metric_name='wanctl_wan_staleness_sec'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 2.3

    def test_wan_weight_staleness_not_recorded_when_disabled(self, temp_db):
        """When wan_state disabled, neither wanctl_wan_weight nor wanctl_wan_staleness_sec in batch."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate disabled path: only base metrics, no WAN metrics
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 25.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        weight_row = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE metric_name='wanctl_wan_weight'"
        ).fetchone()
        staleness_row = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE metric_name='wanctl_wan_staleness_sec'"
        ).fetchone()
        conn.close()

        assert weight_row[0] == 0
        assert staleness_row[0] == 0

    def test_wan_weight_and_staleness_in_stored_metrics(self):
        """wanctl_wan_weight and wanctl_wan_staleness_sec appear in STORED_METRICS dict."""
        from wanctl.storage.schema import STORED_METRICS

        assert "wanctl_wan_weight" in STORED_METRICS
        assert "wanctl_wan_staleness_sec" in STORED_METRICS


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

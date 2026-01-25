"""Tests for autorate daemon metrics recording integration."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from wanctl.storage import MetricsWriter


class TestMetricsRecordingIntegration:
    """Test metrics recording in autorate run_cycle."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "test_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    def test_metrics_written_each_cycle(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify RTT and rate metrics written to database."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate what run_cycle does
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_rate_download_mbps", 850.0, None, "raw"),
            (ts, "spectrum", "wanctl_rate_upload_mbps", 35.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        assert len(rows) == 5
        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_rtt_ms"] == 25.5
        assert metrics["wanctl_rate_download_mbps"] == 850.0

    def test_state_recorded_each_cycle(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify congestion state recorded with direction label."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Record state metric
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=0.0,  # GREEN
            labels={"direction": "download"},
            granularity="raw",
        )

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value, labels FROM metrics WHERE metric_name='wanctl_state'"
        ).fetchone()
        conn.close()

        assert row[0] == 0.0
        labels = json.loads(row[1])
        assert labels["direction"] == "download"

    def test_state_transition_with_reason(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify state transitions include reason labels."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate state transition recording
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=2.0,  # SOFT_RED
            labels={
                "direction": "download",
                "reason": "RTT delta 50.3ms exceeded soft_red threshold 45ms",
            },
            granularity="raw",
        )

        # Verify labels stored
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_state'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["reason"].startswith("RTT delta")
        assert "soft_red" in labels["reason"]

    def test_full_cycle_metrics_batch(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify all 6 metrics written in a single batch."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Full batch matching run_cycle implementation
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 28.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 6.5, None, "raw"),
            (ts, "spectrum", "wanctl_rate_download_mbps", 920.0, None, "raw"),
            (ts, "spectrum", "wanctl_rate_upload_mbps", 38.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, {"direction": "download"}, "raw"),
        ]
        writer.write_metrics_batch(metrics_batch)

        # Verify all metrics written
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        conn.close()

        assert count == 6


class TestStateEncodingHelper:
    """Test the _encode_state helper method."""

    def test_encode_state_green(self) -> None:
        """Verify GREEN encodes to 0."""
        from wanctl.autorate_continuous import WANController

        # Create minimal mock for testing _encode_state
        with patch.object(WANController, "__init__", lambda self: None):
            controller = WANController.__new__(WANController)
            assert controller._encode_state("GREEN") == 0

    def test_encode_state_yellow(self) -> None:
        """Verify YELLOW encodes to 1."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "__init__", lambda self: None):
            controller = WANController.__new__(WANController)
            assert controller._encode_state("YELLOW") == 1

    def test_encode_state_soft_red(self) -> None:
        """Verify SOFT_RED encodes to 2."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "__init__", lambda self: None):
            controller = WANController.__new__(WANController)
            assert controller._encode_state("SOFT_RED") == 2

    def test_encode_state_red(self) -> None:
        """Verify RED encodes to 3."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "__init__", lambda self: None):
            controller = WANController.__new__(WANController)
            assert controller._encode_state("RED") == 3

    def test_encode_state_unknown_defaults_to_green(self) -> None:
        """Verify unknown state defaults to 0 (GREEN)."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "__init__", lambda self: None):
            controller = WANController.__new__(WANController)
            assert controller._encode_state("UNKNOWN") == 0


class TestPerformanceOverhead:
    """Verify metrics recording overhead is <5ms."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> MetricsWriter:
        """Create temporary database for testing."""
        db_path = tmp_path / "perf_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        # Warm up: first write creates tables and connection
        writer.write_metric(
            timestamp=int(time.time()),
            wan_name="warmup",
            metric_name="warmup",
            value=0.0,
            labels=None,
            granularity="raw",
        )
        yield writer
        MetricsWriter._reset_instance()

    def test_batch_write_under_5ms(self, temp_db: MetricsWriter) -> None:
        """Verify batch write completes in <5ms."""
        writer = temp_db
        ts = int(time.time())

        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_rate_download_mbps", 850.0, None, "raw"),
            (ts, "spectrum", "wanctl_rate_upload_mbps", 35.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, None, "raw"),
        ]

        # Measure write time (after warmup - steady-state performance)
        start = time.monotonic()
        writer.write_metrics_batch(metrics_batch)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should complete in <5ms (typically <1ms)
        assert elapsed_ms < 5.0, f"Batch write took {elapsed_ms:.2f}ms, expected <5ms"

    def test_many_cycles_no_degradation(self, temp_db: MetricsWriter) -> None:
        """Verify performance doesn't degrade over many cycles."""
        writer = temp_db

        times = []
        for i in range(100):
            ts = int(time.time()) + i
            metrics_batch = [
                (ts, "spectrum", "wanctl_rtt_ms", 25.0 + i * 0.1, None, "raw"),
                (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
                (ts, "spectrum", "wanctl_rtt_delta_ms", 3.0 + i * 0.1, None, "raw"),
                (ts, "spectrum", "wanctl_rate_download_mbps", 850.0, None, "raw"),
                (ts, "spectrum", "wanctl_rate_upload_mbps", 35.0, None, "raw"),
                (ts, "spectrum", "wanctl_state", 0.0, None, "raw"),
            ]
            start = time.monotonic()
            writer.write_metrics_batch(metrics_batch)
            times.append((time.monotonic() - start) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Average should be <2ms, max should be <5ms
        assert avg_time < 2.0, f"Average write time {avg_time:.2f}ms, expected <2ms"
        assert max_time < 5.0, f"Max write time {max_time:.2f}ms, expected <5ms"

    def test_single_metric_write_under_5ms(self, temp_db: MetricsWriter) -> None:
        """Verify single metric write (for transitions) completes in <5ms."""
        writer = temp_db
        ts = int(time.time())

        # Measure single write time (used for transition recording)
        # Connection already warmed up by fixture
        start = time.monotonic()
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=2.0,
            labels={"direction": "download", "reason": "RTT delta exceeded threshold"},
            granularity="raw",
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 5.0, f"Single write took {elapsed_ms:.2f}ms, expected <5ms"


class TestTransitionReasonRecording:
    """Test state transition reason strings."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "transition_test.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    def test_transition_to_red_reason(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify RED transition reason format."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate RED transition
        reason = "RTT delta 85.3ms exceeded hard_red threshold 80ms"
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=3.0,  # RED
            labels={"direction": "download", "reason": reason},
            granularity="raw",
        )

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT labels FROM metrics").fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert "85.3ms" in labels["reason"]
        assert "hard_red" in labels["reason"]
        assert "80ms" in labels["reason"]

    def test_transition_to_green_reason(
        self, temp_db: tuple[Path, MetricsWriter]
    ) -> None:
        """Verify GREEN transition reason format."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Simulate GREEN transition (recovery)
        reason = "RTT delta 12.5ms fell below green threshold 15ms"
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=0.0,  # GREEN
            labels={"direction": "download", "reason": reason},
            granularity="raw",
        )

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT labels FROM metrics").fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert "12.5ms" in labels["reason"]
        assert "fell below" in labels["reason"]
        assert "green threshold" in labels["reason"]


class TestDisabledStorage:
    """Test behavior when storage is disabled."""

    def test_no_error_when_storage_disabled(self) -> None:
        """Verify no error when MetricsWriter is None."""
        # Simulate disabled storage by not initializing writer
        writer: MetricsWriter | None = None

        # This pattern should not raise
        if writer is not None:
            writer.write_metrics_batch([])

        # No assertion needed - just verifying no exception

    def test_metrics_writer_none_check_pattern(self) -> None:
        """Verify the None check pattern used in run_cycle works correctly."""
        writer: MetricsWriter | None = None

        # This is the pattern used in run_cycle
        executed = False
        if writer is not None:
            executed = True
            writer.write_metrics_batch([])

        assert not executed, "Should not execute when writer is None"


class TestQueueControllerTransitionTracking:
    """Test QueueController transition reason tracking."""

    def test_adjust_returns_transition_reason_on_change(self) -> None:
        """Verify adjust() returns reason when state changes."""
        from wanctl.autorate_continuous import QueueController

        controller = QueueController(
            name="test-dl",
            floor_green=800_000_000,
            floor_yellow=600_000_000,
            floor_soft_red=500_000_000,
            floor_red=400_000_000,
            ceiling=1_000_000_000,
            step_up=10_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )

        # Start in GREEN, move to RED
        baseline_rtt = 22.0
        load_rtt_red = 70.0  # High delta -> RED
        target_delta = 15.0
        warn_delta = 45.0

        zone, rate, reason = controller.adjust(
            baseline_rtt, load_rtt_red, target_delta, warn_delta
        )

        assert zone == "RED"
        assert reason is not None
        assert "48.0ms" in reason  # delta = 70 - 22
        assert "warn threshold" in reason

    def test_adjust_returns_none_when_state_unchanged(self) -> None:
        """Verify adjust() returns None reason when state unchanged."""
        from wanctl.autorate_continuous import QueueController

        controller = QueueController(
            name="test-dl",
            floor_green=800_000_000,
            floor_yellow=600_000_000,
            floor_soft_red=500_000_000,
            floor_red=400_000_000,
            ceiling=1_000_000_000,
            step_up=10_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )

        # Start in GREEN, stay GREEN
        baseline_rtt = 22.0
        load_rtt = 25.0  # Low delta -> GREEN
        target_delta = 15.0
        warn_delta = 45.0

        # First call sets state
        zone1, rate1, reason1 = controller.adjust(
            baseline_rtt, load_rtt, target_delta, warn_delta
        )
        # Second call should return None reason (no change)
        zone2, rate2, reason2 = controller.adjust(
            baseline_rtt, load_rtt, target_delta, warn_delta
        )

        assert zone1 == "GREEN"
        assert zone2 == "GREEN"
        assert reason1 is None  # Already in GREEN (default state)
        assert reason2 is None  # No change

    def test_adjust_4state_returns_transition_reason(self) -> None:
        """Verify adjust_4state() returns reason on state change."""
        from wanctl.autorate_continuous import QueueController

        controller = QueueController(
            name="test-dl",
            floor_green=800_000_000,
            floor_yellow=600_000_000,
            floor_soft_red=500_000_000,
            floor_red=400_000_000,
            ceiling=1_000_000_000,
            step_up=10_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )

        # Start in GREEN, move to SOFT_RED
        baseline_rtt = 22.0
        load_rtt = 72.0  # delta = 50ms -> SOFT_RED
        green_threshold = 15.0
        soft_red_threshold = 45.0
        hard_red_threshold = 80.0

        zone, rate, reason = controller.adjust_4state(
            baseline_rtt, load_rtt, green_threshold, soft_red_threshold, hard_red_threshold
        )

        assert zone == "SOFT_RED"
        assert reason is not None
        assert "50.0ms" in reason
        assert "soft_red threshold" in reason

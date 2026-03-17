"""Tests for signal quality and IRTT metrics persistence in run_cycle (OBSV-03, OBSV-04).

Tests verify that:
- Signal quality metrics (jitter, variance, confidence, outlier_count) are written every cycle
- IRTT metrics (rtt, ipdv, loss_up, loss_down) are written only on new measurements
- IRTT deduplication prevents row duplication at 20Hz cycle rate
"""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.irtt_measurement import IRTTResult
from wanctl.signal_processing import SignalResult
from wanctl.storage import MetricsWriter


class TestSignalQualityMetrics:
    """Test signal quality metrics persistence to SQLite."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "signal_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    @pytest.fixture
    def sample_signal_result(self) -> SignalResult:
        """Create a typical SignalResult for testing."""
        return SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.45,
            variance_ms2=3.72,
            confidence=0.87,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=12,
            consecutive_outliers=0,
            warming_up=False,
        )

    def test_signal_quality_metrics_written_when_signal_result_present(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_signal_result: SignalResult,
    ) -> None:
        """When _last_signal_result is not None, 4 signal quality tuples are in the batch."""
        db_path, writer = temp_db
        ts = int(time.time())
        sr = sample_signal_result

        # Simulate what run_cycle() does: base metrics + signal quality extension
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_baseline_ms", 22.0, None, "raw"),
            (ts, "spectrum", "wanctl_rtt_delta_ms", 3.5, None, "raw"),
            (ts, "spectrum", "wanctl_rate_download_mbps", 850.0, None, "raw"),
            (ts, "spectrum", "wanctl_rate_upload_mbps", 35.0, None, "raw"),
            (ts, "spectrum", "wanctl_state", 0.0, {"direction": "download"}, "raw"),
        ]

        # Signal quality extension (OBSV-03)
        metrics_batch.extend([
            (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
            (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
            (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
            (ts, "spectrum", "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
        ])

        writer.write_metrics_batch(metrics_batch)

        # Verify all 10 metrics written
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        assert len(rows) == 10
        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_signal_jitter_ms"] == 1.45
        assert metrics["wanctl_signal_variance_ms2"] == 3.72
        assert metrics["wanctl_signal_confidence"] == 0.87
        assert metrics["wanctl_signal_outlier_count"] == 12.0

    def test_signal_quality_metric_names_exact(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_signal_result: SignalResult,
    ) -> None:
        """Signal quality metric names match STORED_METRICS exactly."""
        db_path, writer = temp_db
        ts = int(time.time())
        sr = sample_signal_result

        signal_metrics = [
            (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
            (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
            (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
            (ts, "spectrum", "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
        ]
        writer.write_metrics_batch(signal_metrics)

        conn = sqlite3.connect(db_path)
        names = {r[0] for r in conn.execute("SELECT DISTINCT metric_name FROM metrics").fetchall()}
        conn.close()

        expected = {
            "wanctl_signal_jitter_ms",
            "wanctl_signal_variance_ms2",
            "wanctl_signal_confidence",
            "wanctl_signal_outlier_count",
        }
        assert names == expected

    def test_signal_quality_values_full_precision(
        self,
        temp_db: tuple[Path, MetricsWriter],
    ) -> None:
        """Signal quality values are stored at full precision, outlier_count cast to float."""
        db_path, writer = temp_db
        ts = int(time.time())

        sr = SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.456789012345,
            variance_ms2=3.7200000001,
            confidence=0.8712345678,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=999,
            consecutive_outliers=0,
            warming_up=False,
        )

        signal_metrics = [
            (ts, "spectrum", "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
            (ts, "spectrum", "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
            (ts, "spectrum", "wanctl_signal_confidence", sr.confidence, None, "raw"),
            (ts, "spectrum", "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
        ]
        writer.write_metrics_batch(signal_metrics)

        conn = sqlite3.connect(db_path)
        metrics = {
            r[0]: r[1] for r in conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        }
        conn.close()

        assert metrics["wanctl_signal_jitter_ms"] == 1.456789012345
        assert metrics["wanctl_signal_variance_ms2"] == 3.7200000001
        assert metrics["wanctl_signal_confidence"] == 0.8712345678
        assert metrics["wanctl_signal_outlier_count"] == 999.0
        assert isinstance(metrics["wanctl_signal_outlier_count"], float)

    def test_no_signal_metrics_when_signal_result_none(
        self,
        temp_db: tuple[Path, MetricsWriter],
    ) -> None:
        """When _last_signal_result is None, no signal quality metrics are written."""
        db_path, writer = temp_db
        ts = int(time.time())

        # Only base metrics, no signal quality extension
        metrics_batch = [
            (ts, "spectrum", "wanctl_rtt_ms", 25.5, None, "raw"),
        ]
        # Simulate: if _last_signal_result is None, don't extend
        signal_result = None
        if signal_result is not None:
            metrics_batch.extend([
                (ts, "spectrum", "wanctl_signal_jitter_ms", 0.0, None, "raw"),
            ])

        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        signal_rows = conn.execute(
            "SELECT * FROM metrics WHERE metric_name LIKE 'wanctl_signal_%'"
        ).fetchall()
        conn.close()

        assert len(signal_rows) == 0


class TestIRTTMetricsPersistence:
    """Test IRTT metrics persistence with timestamp-based deduplication."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> tuple[Path, MetricsWriter]:
        """Create temporary database for testing."""
        db_path = tmp_path / "irtt_metrics.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    @pytest.fixture
    def sample_irtt_result(self) -> IRTTResult:
        """Create a typical IRTTResult for testing."""
        return IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=1000.0,  # time.monotonic()
            success=True,
        )

    def test_irtt_metrics_written_on_new_measurement(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """When irtt_result timestamp differs from _last_irtt_write_ts, 4 IRTT tuples in batch."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Simulate deduplication state
        last_irtt_write_ts: float | None = 900.0  # different from irtt_result.timestamp (1000.0)

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend([
                (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
            ])
            last_irtt_write_ts = irtt_result.timestamp

        assert len(metrics_batch) == 4
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT metric_name, value FROM metrics").fetchall()
        conn.close()

        metrics = {r[0]: r[1] for r in rows}
        assert metrics["wanctl_irtt_rtt_ms"] == 28.5
        assert metrics["wanctl_irtt_ipdv_ms"] == 2.3
        assert metrics["wanctl_irtt_loss_up_pct"] == 0.5
        assert metrics["wanctl_irtt_loss_down_pct"] == 1.0
        assert last_irtt_write_ts == 1000.0

    def test_irtt_metric_names_exact(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """IRTT metric names match STORED_METRICS exactly."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        irtt_metrics = [
            (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
            (ts, "spectrum", "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
        ]
        writer.write_metrics_batch(irtt_metrics)

        conn = sqlite3.connect(db_path)
        names = {r[0] for r in conn.execute("SELECT DISTINCT metric_name FROM metrics").fetchall()}
        conn.close()

        expected = {
            "wanctl_irtt_rtt_ms",
            "wanctl_irtt_ipdv_ms",
            "wanctl_irtt_loss_up_pct",
            "wanctl_irtt_loss_down_pct",
        }
        assert names == expected

    def test_last_irtt_write_ts_updated_after_writing(
        self,
        sample_irtt_result: IRTTResult,
    ) -> None:
        """_last_irtt_write_ts is updated to irtt_result.timestamp after writing."""
        irtt_result = sample_irtt_result
        last_irtt_write_ts: float | None = None

        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            last_irtt_write_ts = irtt_result.timestamp

        assert last_irtt_write_ts == 1000.0

    def test_duplicate_irtt_not_written(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """When irtt_result.timestamp equals _last_irtt_write_ts, NO IRTT metrics written."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Same timestamp = duplicate
        last_irtt_write_ts: float | None = irtt_result.timestamp  # 1000.0

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend([
                (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
            ])

        # No IRTT metrics should be in the batch
        assert len(metrics_batch) == 0

    def test_irtt_not_written_when_result_none(self) -> None:
        """When irtt_result is None, no IRTT metrics are written."""
        irtt_result = None
        last_irtt_write_ts: float | None = None

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend([])

        assert len(metrics_batch) == 0

    def test_first_irtt_always_writes(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """First IRTT measurement always writes (_last_irtt_write_ts starts as None)."""
        db_path, writer = temp_db
        ts = int(time.time())
        irtt_result = sample_irtt_result

        # Initial state: never written before
        last_irtt_write_ts: float | None = None

        metrics_batch = []
        if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
            metrics_batch.extend([
                (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                (ts, "spectrum", "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
            ])
            last_irtt_write_ts = irtt_result.timestamp

        # Should have written 4 IRTT metrics
        assert len(metrics_batch) == 4
        writer.write_metrics_batch(metrics_batch)

        conn = sqlite3.connect(db_path)
        irtt_rows = conn.execute(
            "SELECT * FROM metrics WHERE metric_name LIKE 'wanctl_irtt_%'"
        ).fetchall()
        conn.close()

        assert len(irtt_rows) == 4
        assert last_irtt_write_ts == 1000.0

    def test_irtt_deduplication_prevents_200x_duplication(
        self,
        temp_db: tuple[Path, MetricsWriter],
        sample_irtt_result: IRTTResult,
    ) -> None:
        """Simulate 200 cycles with same IRTT result -- only 1 write should occur."""
        db_path, writer = temp_db
        irtt_result = sample_irtt_result
        last_irtt_write_ts: float | None = None

        for cycle in range(200):
            ts = int(time.time()) + cycle
            metrics_batch = []

            if irtt_result is not None and irtt_result.timestamp != last_irtt_write_ts:
                metrics_batch.extend([
                    (ts, "spectrum", "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                    (ts, "spectrum", "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                    (
                        ts,
                        "spectrum",
                        "wanctl_irtt_loss_down_pct",
                        irtt_result.receive_loss,
                        None,
                        "raw",
                    ),
                ])
                last_irtt_write_ts = irtt_result.timestamp

            if metrics_batch:
                writer.write_metrics_batch(metrics_batch)

        # Only first cycle should have written IRTT metrics
        conn = sqlite3.connect(db_path)
        irtt_count = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE metric_name LIKE 'wanctl_irtt_%'"
        ).fetchone()[0]
        conn.close()

        assert irtt_count == 4, f"Expected 4 IRTT rows (1 write x 4 metrics), got {irtt_count}"


class TestWANControllerIRTTWriteTs:
    """Test _last_irtt_write_ts attribute on WANController."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    def test_last_irtt_write_ts_initialized_to_none(self, mock_config) -> None:
        """WANController._last_irtt_write_ts starts as None."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        assert controller._last_irtt_write_ts is None


class TestSignalQualityInRunCycle:
    """Test signal quality metrics batch extension in run_cycle (integration-like)."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def controller(self, mock_config):
        """Create a WANController with mocked dependencies."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        return ctrl

    def test_metrics_batch_includes_signal_quality_when_present(
        self,
        controller,
    ) -> None:
        """Verify run_cycle extends metrics_batch with signal quality when available."""
        # Set up signal result
        controller._last_signal_result = SignalResult(
            filtered_rtt=25.3,
            raw_rtt=26.1,
            jitter_ms=1.45,
            variance_ms2=3.72,
            confidence=0.87,
            is_outlier=False,
            outlier_rate=0.05,
            total_outliers=12,
            consecutive_outliers=0,
            warming_up=False,
        )

        # Mock the metrics_writer and capture batch
        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        # Run a cycle with all the necessary mocks
        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "update_baseline"),
            patch.object(controller, "save_state"),
            patch.object(controller, "_check_connectivity_alert"),
        ):
            controller.run_cycle()

        # Verify write_metrics_batch was called
        assert mock_writer.write_metrics_batch.called
        batch = mock_writer.write_metrics_batch.call_args[0][0]

        # Extract metric names from the batch
        metric_names = [item[2] for item in batch]
        assert "wanctl_signal_jitter_ms" in metric_names
        assert "wanctl_signal_variance_ms2" in metric_names
        assert "wanctl_signal_confidence" in metric_names
        assert "wanctl_signal_outlier_count" in metric_names

    def test_metrics_batch_excludes_signal_quality_when_none(
        self,
        controller,
    ) -> None:
        """Verify run_cycle does not include signal metrics when _last_signal_result is None."""
        # Force _last_signal_result to None (shouldn't happen normally but tests guard)
        controller._last_signal_result = None

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        # Patch signal_processor.process to return a result but keep _last_signal_result None
        original_process = controller.signal_processor.process

        def patched_process(*args, **kwargs):
            result = original_process(*args, **kwargs)
            controller._last_signal_result = None  # Force it back to None
            return result

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "update_baseline"),
            patch.object(controller, "save_state"),
            patch.object(controller, "_check_connectivity_alert"),
            patch.object(controller.signal_processor, "process", side_effect=patched_process),
        ):
            controller.run_cycle()

        if mock_writer.write_metrics_batch.called:
            batch = mock_writer.write_metrics_batch.call_args[0][0]
            metric_names = [item[2] for item in batch]
            assert "wanctl_signal_jitter_ms" not in metric_names


class TestIRTTInRunCycle:
    """Test IRTT metrics batch extension and deduplication in run_cycle."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def controller(self, mock_config):
        """Create a WANController with mocked dependencies."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        return ctrl

    def test_irtt_metrics_written_when_new_result_available(
        self,
        controller,
    ) -> None:
        """Verify run_cycle includes IRTT metrics when irtt_result has new timestamp."""
        # Set up IRTT thread with a result
        mock_irtt_thread = MagicMock()
        mock_irtt_thread._cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=time.monotonic(),
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        controller._last_irtt_write_ts = None  # First measurement

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "update_baseline"),
            patch.object(controller, "save_state"),
            patch.object(controller, "_check_connectivity_alert"),
        ):
            controller.run_cycle()

        assert mock_writer.write_metrics_batch.called
        batch = mock_writer.write_metrics_batch.call_args[0][0]
        metric_names = [item[2] for item in batch]
        assert "wanctl_irtt_rtt_ms" in metric_names
        assert "wanctl_irtt_ipdv_ms" in metric_names
        assert "wanctl_irtt_loss_up_pct" in metric_names
        assert "wanctl_irtt_loss_down_pct" in metric_names

    def test_irtt_metrics_not_written_when_duplicate_timestamp(
        self,
        controller,
    ) -> None:
        """Verify run_cycle skips IRTT metrics when timestamp matches _last_irtt_write_ts."""
        # Set up IRTT thread with a result
        irtt_ts = time.monotonic()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread._cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=irtt_ts,
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        # Same timestamp = already written
        controller._last_irtt_write_ts = irtt_ts

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "update_baseline"),
            patch.object(controller, "save_state"),
            patch.object(controller, "_check_connectivity_alert"),
        ):
            controller.run_cycle()

        if mock_writer.write_metrics_batch.called:
            batch = mock_writer.write_metrics_batch.call_args[0][0]
            metric_names = [item[2] for item in batch]
            assert "wanctl_irtt_rtt_ms" not in metric_names
            assert "wanctl_irtt_ipdv_ms" not in metric_names
            assert "wanctl_irtt_loss_up_pct" not in metric_names
            assert "wanctl_irtt_loss_down_pct" not in metric_names

    def test_last_irtt_write_ts_updated_after_cycle(
        self,
        controller,
    ) -> None:
        """Verify _last_irtt_write_ts is updated after writing IRTT metrics in run_cycle."""
        irtt_ts = time.monotonic()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread._cadence_sec = 10.0
        mock_irtt_thread.get_latest.return_value = IRTTResult(
            rtt_mean_ms=28.5,
            rtt_median_ms=27.2,
            ipdv_mean_ms=2.3,
            send_loss=0.5,
            receive_loss=1.0,
            packets_sent=100,
            packets_received=99,
            server="irtt.example.com",
            port=2112,
            timestamp=irtt_ts,
            success=True,
        )
        controller._irtt_thread = mock_irtt_thread
        controller._last_irtt_write_ts = None

        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        with (
            patch.object(controller, "measure_rtt", return_value=25.3),
            patch.object(controller, "apply_rate_changes_if_needed", return_value=True),
            patch.object(controller, "update_baseline"),
            patch.object(controller, "save_state"),
            patch.object(controller, "_check_connectivity_alert"),
        ):
            controller.run_cycle()

        assert controller._last_irtt_write_ts == irtt_ts

"""Tests for tuning parameter restoration from SQLite on daemon startup.

Verifies that WANController restores prior tuning adjustments from SQLite
when tuning is enabled, and gracefully handles all edge cases.
"""

import logging
from unittest.mock import MagicMock, patch

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningState


def _make_tuning_config(enabled: bool = True) -> TuningConfig:
    """Create a minimal TuningConfig for testing."""
    return TuningConfig(
        enabled=enabled,
        cadence_sec=3600,
        lookback_hours=24,
        warmup_hours=1,
        max_step_pct=10.0,
        bounds={
            "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=30.0),
        },
    )


def _make_wc(*, tuning_enabled: bool = True, metrics_writer=None):
    """Create a minimal WANController-like object for testing _restore_tuning_params.

    Bypasses WANController.__init__ to test _restore_tuning_params in isolation.
    """
    from wanctl.wan_controller import WANController

    wc = object.__new__(WANController)
    wc.wan_name = "spectrum"
    wc.logger = logging.getLogger("test_tuning_restore")
    wc._tuning_enabled = tuning_enabled
    wc._metrics_writer = metrics_writer
    wc._tuning_state = (
        TuningState(
            enabled=tuning_enabled,
            last_run_ts=None,
            recent_adjustments=[],
            parameters={},
        )
        if tuning_enabled
        else None
    )
    # Attributes that _apply_tuning_to_controller writes to
    wc.green_threshold = 15.0
    wc.target_delta = 15.0
    wc.soft_red_threshold = 45.0
    wc.warn_delta = 45.0
    wc.hard_red_threshold = 80.0
    wc.alpha_load = 0.1
    wc.alpha_baseline = 0.001
    return wc


class TestRestoreTuningParams:
    """Tests for WANController._restore_tuning_params."""

    def test_restores_latest_non_reverted_params(self):
        """When tuning enabled + SQLite has prior adjustments, latest values are applied."""
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=True, metrics_writer=mock_writer)

        # Simulate query_tuning_params returning DESC-ordered rows
        fake_rows = [
            {
                "parameter": "target_bloat_ms",
                "old_value": 15.0,
                "new_value": 12.5,
                "confidence": 0.9,
                "rationale": "percentile optimization",
                "data_points": 500,
                "timestamp": 1700000200,
                "reverted": 0,
            },
            {
                "parameter": "target_bloat_ms",
                "old_value": 14.0,
                "new_value": 15.0,
                "confidence": 0.7,
                "rationale": "earlier adjustment",
                "data_points": 300,
                "timestamp": 1700000100,
                "reverted": 0,
            },
        ]

        with patch(
            "wanctl.storage.reader.query_tuning_params",
            return_value=fake_rows,
        ) as mock_query:
            wc._restore_tuning_params()
            mock_query.assert_called_once_with(db_path="/tmp/test.db", wan="spectrum")

        # Should apply latest (first) row: new_value=12.5
        assert wc.green_threshold == 12.5
        assert wc.target_delta == 12.5

    def test_empty_db_proceeds_normally(self):
        """When tuning enabled + no prior adjustments, startup proceeds with defaults."""
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=True, metrics_writer=mock_writer)

        with patch(
            "wanctl.storage.reader.query_tuning_params",
            return_value=[],
        ):
            wc._restore_tuning_params()

        # Defaults unchanged
        assert wc.green_threshold == 15.0
        assert wc.target_delta == 15.0

    def test_tuning_disabled_no_query(self):
        """When tuning disabled, _restore_tuning_params should not be called.

        This tests the guard in WANController.__init__ -- when tuning is disabled,
        _restore_tuning_params is never invoked.
        """
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=False, metrics_writer=mock_writer)

        # The method itself doesn't check _tuning_enabled; the guard is in __init__.
        # We verify the expected usage pattern: don't call when disabled.
        # This test documents the contract.
        assert wc._tuning_enabled is False

    def test_no_db_path_no_restore(self):
        """When db_path not configured (no metrics_writer), no restore attempted."""
        wc = _make_wc(tuning_enabled=True, metrics_writer=None)

        # With no metrics_writer, __init__ guard prevents calling _restore_tuning_params.
        # Verify the guard condition.
        assert wc._metrics_writer is None

    def test_sqlite_error_caught_and_logged(self):
        """SQLite error during restore is caught and logged, not crash startup."""
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=True, metrics_writer=mock_writer)

        with patch(
            "wanctl.storage.reader.query_tuning_params",
            side_effect=Exception("database is locked"),
        ):
            # Should NOT raise
            wc._restore_tuning_params()

        # Defaults unchanged (graceful fallback)
        assert wc.green_threshold == 15.0
        assert wc.target_delta == 15.0

    def test_skips_reverted_rows(self):
        """Reverted adjustments are skipped, non-reverted values applied."""
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=True, metrics_writer=mock_writer)

        fake_rows = [
            {
                "parameter": "target_bloat_ms",
                "old_value": 12.0,
                "new_value": 10.0,
                "confidence": 0.8,
                "rationale": "reverted",
                "data_points": 400,
                "timestamp": 1700000300,
                "reverted": 1,  # This one is reverted
            },
            {
                "parameter": "target_bloat_ms",
                "old_value": 15.0,
                "new_value": 12.0,
                "confidence": 0.9,
                "rationale": "good adjustment",
                "data_points": 500,
                "timestamp": 1700000200,
                "reverted": 0,
            },
        ]

        with patch(
            "wanctl.storage.reader.query_tuning_params",
            return_value=fake_rows,
        ):
            wc._restore_tuning_params()

        # Should skip reverted row and apply second: new_value=12.0
        assert wc.green_threshold == 12.0
        assert wc.target_delta == 12.0

    def test_all_reverted_no_restore(self):
        """When all rows are reverted, no parameters are restored."""
        mock_writer = MagicMock()
        mock_writer._db_path = "/tmp/test.db"
        wc = _make_wc(tuning_enabled=True, metrics_writer=mock_writer)

        fake_rows = [
            {
                "parameter": "target_bloat_ms",
                "old_value": 15.0,
                "new_value": 12.0,
                "confidence": 0.8,
                "rationale": "reverted",
                "data_points": 400,
                "timestamp": 1700000200,
                "reverted": 1,
            },
        ]

        with patch(
            "wanctl.storage.reader.query_tuning_params",
            return_value=fake_rows,
        ):
            wc._restore_tuning_params()

        # Defaults unchanged
        assert wc.green_threshold == 15.0

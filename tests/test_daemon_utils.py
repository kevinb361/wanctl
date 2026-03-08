"""Tests for daemon_utils.py shared helpers.

Covers:
- check_cleanup_deadline() with fast/slow/exceeded deadline scenarios
"""

import logging
from unittest.mock import MagicMock

from wanctl.daemon_utils import check_cleanup_deadline


class TestCheckCleanupDeadline:
    """Tests for check_cleanup_deadline shared helper."""

    def test_fast_step_within_deadline_no_warnings(self) -> None:
        """Fast step within deadline should produce no warnings or errors."""
        mock_logger = MagicMock(spec=logging.Logger)
        # step_start=100.0, now=100.5 -> elapsed=0.5s (fast), deadline=200.0 (within)
        check_cleanup_deadline("fast_step", 100.0, 200.0, 30.0, mock_logger, now=100.5)

        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    def test_slow_step_logs_warning(self) -> None:
        """Step taking >5s should log WARNING."""
        mock_logger = MagicMock(spec=logging.Logger)
        # step_start=100.0, now=106.0 -> elapsed=6.0s (>5.0), deadline=200.0 (within)
        check_cleanup_deadline("slow_step", 100.0, 200.0, 30.0, mock_logger, now=106.0)

        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args[0][0]
        assert "Slow cleanup step" in args
        assert "slow_step" in args
        assert "6.0s" in args
        mock_logger.error.assert_not_called()

    def test_exceeded_deadline_logs_error(self) -> None:
        """Step exceeding deadline should log ERROR."""
        mock_logger = MagicMock(spec=logging.Logger)
        # step_start=100.0, now=102.0 -> elapsed=2.0s (fast), deadline=101.0 (exceeded)
        check_cleanup_deadline("exceeded_step", 100.0, 101.0, 30.0, mock_logger, now=102.0)

        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_called_once()
        args = mock_logger.error.call_args[0][0]
        assert "Cleanup deadline exceeded" in args
        assert "30.0s" in args
        assert "exceeded_step" in args

    def test_slow_and_exceeded_logs_both(self) -> None:
        """Step that is both slow (>5s) AND exceeds deadline should log both."""
        mock_logger = MagicMock(spec=logging.Logger)
        # step_start=100.0, now=107.0 -> elapsed=7.0s (>5.0), deadline=105.0 (exceeded)
        check_cleanup_deadline("bad_step", 100.0, 105.0, 30.0, mock_logger, now=107.0)

        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_called_once()

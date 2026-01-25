"""Unit tests for systemd utilities."""

from unittest.mock import MagicMock, patch

from wanctl.systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_ready,
    notify_status,
    notify_stopping,
    notify_watchdog,
)


class TestIsSystemdAvailable:
    """Tests for is_systemd_available function."""

    def test_returns_true_when_systemd_available(self):
        """Test returns True when _HAVE_SYSTEMD is True."""
        with patch("wanctl.systemd_utils._HAVE_SYSTEMD", True):
            assert is_systemd_available() is True

    def test_returns_false_when_systemd_unavailable(self):
        """Test returns False when _HAVE_SYSTEMD is False."""
        with patch("wanctl.systemd_utils._HAVE_SYSTEMD", False):
            assert is_systemd_available() is False


class TestNotifyReady:
    """Tests for notify_ready function."""

    def test_calls_sd_notify_when_available(self):
        """Test notify_ready calls _sd_notify with READY=1."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_ready()
        mock_notify.assert_called_once_with("READY=1")

    def test_noop_when_sd_notify_none(self):
        """Test notify_ready is no-op when _sd_notify is None."""
        with patch("wanctl.systemd_utils._sd_notify", None):
            # Should not raise
            notify_ready()


class TestNotifyWatchdog:
    """Tests for notify_watchdog function."""

    def test_calls_sd_notify_when_available(self):
        """Test notify_watchdog calls _sd_notify with WATCHDOG=1."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_watchdog()
        mock_notify.assert_called_once_with("WATCHDOG=1")

    def test_noop_when_sd_notify_none(self):
        """Test notify_watchdog is no-op when _sd_notify is None."""
        with patch("wanctl.systemd_utils._sd_notify", None):
            # Should not raise
            notify_watchdog()


class TestNotifyStatus:
    """Tests for notify_status function."""

    def test_calls_sd_notify_with_status_message(self):
        """Test notify_status calls _sd_notify with STATUS=message."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_status("Processing 100 requests/sec")
        mock_notify.assert_called_once_with("STATUS=Processing 100 requests/sec")

    def test_noop_when_sd_notify_none(self):
        """Test notify_status is no-op when _sd_notify is None."""
        with patch("wanctl.systemd_utils._sd_notify", None):
            # Should not raise
            notify_status("some status")

    def test_handles_empty_message(self):
        """Test notify_status handles empty message."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_status("")
        mock_notify.assert_called_once_with("STATUS=")


class TestNotifyStopping:
    """Tests for notify_stopping function."""

    def test_calls_sd_notify_when_available(self):
        """Test notify_stopping calls _sd_notify with STOPPING=1."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_stopping()
        mock_notify.assert_called_once_with("STOPPING=1")

    def test_noop_when_sd_notify_none(self):
        """Test notify_stopping is no-op when _sd_notify is None."""
        with patch("wanctl.systemd_utils._sd_notify", None):
            # Should not raise
            notify_stopping()


class TestNotifyDegraded:
    """Tests for notify_degraded function."""

    def test_calls_sd_notify_with_degraded_prefix(self):
        """Test notify_degraded calls _sd_notify with Degraded prefix."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_degraded("3 consecutive failures")
        mock_notify.assert_called_once_with("STATUS=Degraded - 3 consecutive failures")

    def test_noop_when_sd_notify_none(self):
        """Test notify_degraded is no-op when _sd_notify is None."""
        with patch("wanctl.systemd_utils._sd_notify", None):
            # Should not raise
            notify_degraded("some degradation")

    def test_handles_empty_message(self):
        """Test notify_degraded handles empty message."""
        mock_notify = MagicMock()
        with patch("wanctl.systemd_utils._sd_notify", mock_notify):
            notify_degraded("")
        mock_notify.assert_called_once_with("STATUS=Degraded - ")

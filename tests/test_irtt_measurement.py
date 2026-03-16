"""Unit tests for IRTTMeasurement class and IRTTResult dataclass."""

from __future__ import annotations

import dataclasses
import json
import logging
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from wanctl.irtt_measurement import IRTTMeasurement, IRTTResult

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_IRTT_JSON = {
    "stats": {
        "rtt": {
            "mean": 37_500_000,  # 37.5ms in nanoseconds
            "median": 36_000_000,  # 36.0ms
        },
        "ipdv_round_trip": {
            "mean": 2_000_000,  # 2.0ms
        },
        "upstream_loss_percent": 0.0,
        "downstream_loss_percent": 10.0,
        "packets_sent": 10,
        "packets_received": 9,
    }
}

TEST_CONFIG = {
    "enabled": True,
    "server": "104.200.21.31",
    "port": 2112,
    "duration_sec": 1.0,
    "interval_ms": 100,
}


def _make_logger() -> logging.Logger:
    """Create a test logger."""
    return logging.getLogger("test.irtt")


# ---------------------------------------------------------------------------
# TestIRTTResult
# ---------------------------------------------------------------------------


class TestIRTTResult:
    """Tests for the IRTTResult frozen dataclass."""

    def test_frozen_raises_on_assignment(self) -> None:
        """Test 1: IRTTResult is frozen (assigning rtt_mean_ms raises)."""
        result = IRTTResult(
            rtt_mean_ms=37.5,
            rtt_median_ms=36.0,
            ipdv_mean_ms=2.0,
            send_loss=0.0,
            receive_loss=10.0,
            packets_sent=10,
            packets_received=9,
            server="104.200.21.31",
            port=2112,
            timestamp=1000.0,
            success=True,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.rtt_mean_ms = 99.9  # type: ignore[misc]

    def test_all_fields_present(self) -> None:
        """Test 2: IRTTResult has all 11 expected fields with correct types."""
        result = IRTTResult(
            rtt_mean_ms=37.5,
            rtt_median_ms=36.0,
            ipdv_mean_ms=2.0,
            send_loss=0.0,
            receive_loss=10.0,
            packets_sent=10,
            packets_received=9,
            server="104.200.21.31",
            port=2112,
            timestamp=1000.0,
            success=True,
        )
        assert isinstance(result.rtt_mean_ms, float)
        assert isinstance(result.rtt_median_ms, float)
        assert isinstance(result.ipdv_mean_ms, float)
        assert isinstance(result.send_loss, float)
        assert isinstance(result.receive_loss, float)
        assert isinstance(result.packets_sent, int)
        assert isinstance(result.packets_received, int)
        assert isinstance(result.server, str)
        assert isinstance(result.port, int)
        assert isinstance(result.timestamp, float)
        assert isinstance(result.success, bool)


# ---------------------------------------------------------------------------
# TestMeasure
# ---------------------------------------------------------------------------


class TestMeasure:
    """Tests for IRTTMeasurement.measure() success paths."""

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_returns_irtt_result_on_success(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 3: measure() returns IRTTResult with success=True on valid JSON."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        result = m.measure()
        assert result is not None
        assert isinstance(result, IRTTResult)
        assert result.success is True

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_converts_nanoseconds_to_milliseconds(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 4: measure() divides nanosecond values by 1_000_000."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        result = m.measure()
        assert result is not None
        assert result.rtt_mean_ms == pytest.approx(37.5)
        assert result.rtt_median_ms == pytest.approx(36.0)
        assert result.ipdv_mean_ms == pytest.approx(2.0)

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_extracts_correct_stats_fields(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 5: measure() extracts correct JSON field paths."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        result = m.measure()
        assert result is not None
        # RTT fields
        assert result.rtt_mean_ms == pytest.approx(37.5)
        assert result.rtt_median_ms == pytest.approx(36.0)
        # IPDV round-trip
        assert result.ipdv_mean_ms == pytest.approx(2.0)
        # Loss
        assert result.send_loss == pytest.approx(0.0)
        assert result.receive_loss == pytest.approx(10.0)
        # Packets
        assert result.packets_sent == 10
        assert result.packets_received == 9

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_builds_correct_command(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 6: measure() builds the correct irtt client command."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        m.measure()

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "irtt",
            "client",
            "-o",
            "-",
            "-Q",
            "-d",
            "1.0s",
            "-i",
            "100ms",
            "-l",
            "48",
            "104.200.21.31:2112",
        ]

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_sets_subprocess_timeout(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 7: measure() sets subprocess timeout to duration_sec + 5."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        m.measure()

        mock_run.assert_called_once()
        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 6.0  # 1.0 + 5


# ---------------------------------------------------------------------------
# TestFallback
# ---------------------------------------------------------------------------


class TestFallback:
    """Tests for IRTTMeasurement fallback / failure paths."""

    @patch("wanctl.irtt_measurement.shutil.which")
    def test_measure_returns_none_when_binary_missing(self, mock_which: MagicMock) -> None:
        """Test 8: measure() returns None when binary not found."""
        mock_which.return_value = None
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        assert m.measure() is None

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_returns_none_on_timeout(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 9: measure() returns None on subprocess.TimeoutExpired."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="irtt", timeout=6)
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        assert m.measure() is None

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_returns_none_on_json_decode_error(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 10: measure() returns None when stdout is not valid JSON."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json {{{",
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        assert m.measure() is None

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_returns_none_when_stats_key_missing(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 11: measure() returns None when 'stats' key missing from JSON."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"version": "0.9.0", "no_stats_here": True}),
            stderr="",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        assert m.measure() is None

    def test_measure_returns_none_when_disabled(self) -> None:
        """Test 12: measure() returns None when enabled=False."""
        config = {**TEST_CONFIG, "enabled": False}
        with patch("wanctl.irtt_measurement.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/irtt"
            m = IRTTMeasurement(config=config, logger=_make_logger())
            assert m.measure() is None

    def test_measure_returns_none_when_no_server(self) -> None:
        """Test 13: measure() returns None when server is None."""
        config = {**TEST_CONFIG, "server": None}
        with patch("wanctl.irtt_measurement.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/irtt"
            m = IRTTMeasurement(config=config, logger=_make_logger())
            assert m.measure() is None

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_measure_tries_json_on_nonzero_exit_code(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 14: measure() tries JSON parsing even on non-zero exit code (Pitfall 4)."""
        mock_which.return_value = "/usr/bin/irtt"
        # Non-zero exit but valid JSON in stdout
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="100% packet loss",
        )
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        result = m.measure()
        assert result is not None
        assert result.success is True
        assert result.rtt_mean_ms == pytest.approx(37.5)

    @patch("wanctl.irtt_measurement.shutil.which")
    def test_is_available_false_when_binary_missing(self, mock_which: MagicMock) -> None:
        """Test 15: is_available() returns False when binary missing."""
        mock_which.return_value = None
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())
        assert m.is_available() is False

    @patch("wanctl.irtt_measurement.shutil.which")
    def test_is_available_false_when_disabled(self, mock_which: MagicMock) -> None:
        """Test 16: is_available() returns False when enabled=False."""
        mock_which.return_value = "/usr/bin/irtt"
        config = {**TEST_CONFIG, "enabled": False}
        m = IRTTMeasurement(config=config, logger=_make_logger())
        assert m.is_available() is False

    @patch("wanctl.irtt_measurement.shutil.which")
    def test_is_available_false_when_no_server(self, mock_which: MagicMock) -> None:
        """Test 17: is_available() returns False when server=None."""
        mock_which.return_value = "/usr/bin/irtt"
        config = {**TEST_CONFIG, "server": None}
        m = IRTTMeasurement(config=config, logger=_make_logger())
        assert m.is_available() is False


# ---------------------------------------------------------------------------
# TestLogging
# ---------------------------------------------------------------------------


class TestLogging:
    """Tests for log level management on failures and recovery."""

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_first_failure_logs_warning(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test 18: First failure logs at WARNING level."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="irtt", timeout=6)
        logger = _make_logger()
        with patch.object(logger, "warning") as mock_warn:
            m = IRTTMeasurement(config=TEST_CONFIG, logger=logger)
            # Clear the init warning call (binary found, no warning)
            mock_warn.reset_mock()
            m.measure()
            mock_warn.assert_called_once()
            assert "IRTT measurement failed" in mock_warn.call_args[0][0]

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_second_failure_logs_debug(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test 19: Second consecutive failure logs at DEBUG (not WARNING)."""
        mock_which.return_value = "/usr/bin/irtt"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="irtt", timeout=6)
        logger = _make_logger()
        with (
            patch.object(logger, "warning") as mock_warn,
            patch.object(logger, "debug") as mock_debug,
        ):
            m = IRTTMeasurement(config=TEST_CONFIG, logger=logger)
            mock_warn.reset_mock()
            mock_debug.reset_mock()
            # First failure -> WARNING
            m.measure()
            # Second failure -> DEBUG
            m.measure()
            # warning called once (first failure only)
            assert mock_warn.call_count == 1
            # debug called at least once (second failure)
            debug_calls = [
                c for c in mock_debug.call_args_list if "IRTT measurement failed" in str(c)
            ]
            assert len(debug_calls) >= 1

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_recovery_logs_info_with_count(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 20: Recovery after failures logs at INFO with consecutive failure count."""
        mock_which.return_value = "/usr/bin/irtt"
        logger = _make_logger()
        m = IRTTMeasurement(config=TEST_CONFIG, logger=logger)

        # Two failures
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="irtt", timeout=6)
        m.measure()
        m.measure()

        # Recovery
        mock_run.side_effect = None
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        with patch.object(logger, "info") as mock_info:
            result = m.measure()
            assert result is not None
            assert result.success is True
            info_calls = [
                c for c in mock_info.call_args_list if "recovered" in str(c) and "2" in str(c)
            ]
            assert len(info_calls) == 1

    @patch("wanctl.irtt_measurement.shutil.which")
    @patch("wanctl.irtt_measurement.subprocess.run")
    def test_recovery_resets_failure_tracking(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test 21: Recovery resets _first_failure_logged and _consecutive_failures."""
        mock_which.return_value = "/usr/bin/irtt"
        m = IRTTMeasurement(config=TEST_CONFIG, logger=_make_logger())

        # Fail once
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="irtt", timeout=6)
        m.measure()
        assert m._consecutive_failures == 1
        assert m._first_failure_logged is True

        # Recover
        mock_run.side_effect = None
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_IRTT_JSON),
            stderr="",
        )
        m.measure()
        assert m._consecutive_failures == 0
        assert m._first_failure_logged is False

    @patch("wanctl.irtt_measurement.shutil.which")
    def test_binary_missing_logs_warning_with_apt_hint(self, mock_which: MagicMock) -> None:
        """Test 22: Binary missing at init logs WARNING with 'apt install' hint."""
        mock_which.return_value = None
        logger = _make_logger()
        with patch.object(logger, "warning") as mock_warn:
            IRTTMeasurement(config=TEST_CONFIG, logger=logger)
            mock_warn.assert_called_once()
            msg = mock_warn.call_args[0][0]
            assert "not found" in msg.lower() or "IRTT binary" in msg
            assert "apt install" in msg.lower() or "sudo apt" in msg.lower()

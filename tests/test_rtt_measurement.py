"""Tests for RTTMeasurement class in rtt_measurement module."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from wanctl.rtt_measurement import RTTAggregationStrategy, RTTMeasurement


class TestPingHostsConcurrent:
    """Tests for RTTMeasurement.ping_hosts_concurrent() method."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def rtt_measurement(self, mock_logger):
        """Create an RTTMeasurement instance with mocked logger."""
        return RTTMeasurement(
            logger=mock_logger,
            timeout_ping=1,
            aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        )

    @pytest.fixture
    def mock_subprocess(self):
        """Create a mock for subprocess.run."""
        with patch("wanctl.rtt_measurement.subprocess.run") as mock:
            yield mock

    def test_returns_list_of_rtts(self, rtt_measurement, mock_subprocess):
        """Should return list of successful RTT values."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "64 bytes from 8.8.8.8: time=12.3 ms"

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert len(rtts) == 2
        assert all(isinstance(rtt, float) for rtt in rtts)

    def test_empty_hosts_returns_empty_list(self, rtt_measurement):
        """Should return empty list for empty hosts."""
        result = rtt_measurement.ping_hosts_concurrent([])
        assert result == []

    def test_partial_failures_return_successful_only(self, rtt_measurement, mock_subprocess):
        """Should return only successful pings when some fail."""
        # First ping succeeds, second fails
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="64 bytes from 8.8.8.8: time=12.3 ms"),
            Mock(returncode=1, stdout=""),
        ]

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert len(rtts) == 1
        assert rtts[0] == pytest.approx(12.3)

    def test_all_failures_return_empty_list(self, rtt_measurement, mock_subprocess):
        """Should return empty list when all pings fail."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert rtts == []

    def test_timeout_handled_gracefully(self, rtt_measurement, mock_subprocess):
        """Should handle subprocess timeout without crashing."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=3)

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8"], timeout=0.1)

        assert rtts == []

    def test_single_host_works(self, rtt_measurement, mock_subprocess):
        """Should work with a single host."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "64 bytes from 8.8.8.8: time=15.7 ms"

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8"])

        assert len(rtts) == 1
        assert rtts[0] == pytest.approx(15.7)

    def test_three_hosts_for_median_of_three(self, rtt_measurement, mock_subprocess):
        """Should work with three hosts (median-of-three scenario)."""
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="64 bytes from 8.8.8.8: time=10.0 ms"),
            Mock(returncode=0, stdout="64 bytes from 1.1.1.1: time=12.0 ms"),
            Mock(returncode=0, stdout="64 bytes from 9.9.9.9: time=14.0 ms"),
        ]

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1", "9.9.9.9"])

        assert len(rtts) == 3
        # All three RTTs should be present
        assert 10.0 in [pytest.approx(r, abs=0.1) for r in rtts]
        assert 12.0 in [pytest.approx(r, abs=0.1) for r in rtts]
        assert 14.0 in [pytest.approx(r, abs=0.1) for r in rtts]

    def test_count_parameter_passed_to_ping_host(self, rtt_measurement):
        """Should pass count parameter to ping_host calls."""
        with patch.object(rtt_measurement, "ping_host") as mock_ping:
            mock_ping.return_value = 10.0

            rtt_measurement.ping_hosts_concurrent(["8.8.8.8"], count=5)

            mock_ping.assert_called_once_with("8.8.8.8", 5)

    def test_exception_in_ping_logged_and_continues(self, rtt_measurement, mock_logger):
        """Should log exceptions and continue processing other hosts."""
        with patch.object(rtt_measurement, "ping_host") as mock_ping:
            # First ping raises, second succeeds
            mock_ping.side_effect = [Exception("Network error"), 15.0]

            rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

            # Should get one result from successful ping
            assert len(rtts) == 1
            assert rtts[0] == 15.0
            # Should have logged the exception
            mock_logger.debug.assert_called()


class TestParsesPingOutput:
    """Tests for parsing ping output in context of concurrent pings."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def rtt_measurement(self, mock_logger):
        """Create an RTTMeasurement instance."""
        return RTTMeasurement(
            logger=mock_logger,
            timeout_ping=1,
            aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        )

    def test_various_ping_output_formats(self, rtt_measurement):
        """Should parse various ping output formats correctly."""
        from wanctl.rtt_measurement import parse_ping_output

        # Standard Linux ping format
        output1 = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3 ms"
        assert parse_ping_output(output1) == [12.3]

        # Format without space before ms
        output2 = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3ms"
        # The regex should still find time=12.3
        result = parse_ping_output(output2)
        assert len(result) == 1
        assert result[0] == pytest.approx(12.3)

        # Multiple lines
        output3 = """64 bytes from 8.8.8.8: time=10.0 ms
64 bytes from 8.8.8.8: time=11.0 ms
64 bytes from 8.8.8.8: time=12.0 ms"""
        assert parse_ping_output(output3) == [10.0, 11.0, 12.0]

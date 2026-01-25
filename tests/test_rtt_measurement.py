"""Tests for RTTMeasurement class in rtt_measurement module."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from wanctl.rtt_measurement import (
    RTTAggregationStrategy,
    RTTMeasurement,
    parse_ping_output,
)


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


class TestParsePingOutputEdgeCases:
    """Tests for parse_ping_output edge cases - lines 46, 50, 60-68."""

    # Empty and missing data tests

    def test_empty_string_returns_empty_list(self):
        """Empty string input returns empty list (line 46)."""
        assert parse_ping_output("") == []

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only input returns empty list."""
        assert parse_ping_output("   \n  ") == []
        assert parse_ping_output("\t\n\r") == []

    def test_no_time_marker_returns_empty(self):
        """Lines without 'time=' marker return empty list (line 50)."""
        # Various ping-like output but no actual RTT
        output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
--- 8.8.8.8 ping statistics ---
0 packets transmitted, 0 received, 100% packet loss"""
        assert parse_ping_output(output) == []

    # Fallback parsing tests (lines 59-68)

    def test_fallback_parsing_no_space_before_ms(self):
        """Fallback parsing handles 'time=12.3ms' without space (lines 60-64)."""
        # The regex pattern _RTT_PATTERN = r"time=([0-9.]+)" should match
        # but if somehow a format breaks regex, fallback kicks in
        output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3ms"
        result = parse_ping_output(output)
        assert len(result) == 1
        assert result[0] == pytest.approx(12.3)

    def test_fallback_parsing_invalid_value_logs(self):
        """Invalid float value is logged if logger provided (lines 65-68)."""
        mock_logger = MagicMock()
        # Create line with time= but malformed value
        # Need a line that has "time=" but the regex fails and fallback also fails
        output = "reply from 8.8.8.8: time=invalid ms"
        result = parse_ping_output(output, logger_instance=mock_logger)
        assert result == []
        mock_logger.debug.assert_called_once()
        # Verify the error was logged
        call_args = mock_logger.debug.call_args[0][0]
        assert "Failed to parse RTT" in call_args

    def test_fallback_parsing_index_error_handled(self):
        """Malformed 'time=' at end of line handles IndexError (line 65)."""
        # Line ends with "time=" but no value after it
        output = "malformed line: time="
        result = parse_ping_output(output)
        # Should handle gracefully (IndexError caught)
        assert result == []

    # Logger integration tests

    def test_parse_with_logger_logs_failures(self):
        """Logger.debug is called on parse failure (lines 67-68)."""
        mock_logger = MagicMock()
        # Create a line that will fail parsing
        output = "64 bytes: time=not_a_number ms"
        parse_ping_output(output, logger_instance=mock_logger)
        mock_logger.debug.assert_called()

    def test_parse_without_logger_no_crash(self):
        """logger_instance=None works without error (line 67 condition)."""
        # Parse failure without logger should not crash
        output = "64 bytes: time=abc"
        result = parse_ping_output(output, logger_instance=None)
        assert result == []

    # Multiple samples tests

    def test_parse_multiple_lines_extracts_all(self):
        """Multi-line output returns all RTTs."""
        output = """64 bytes from 8.8.8.8: time=10.0 ms
64 bytes from 8.8.8.8: time=15.5 ms
64 bytes from 8.8.8.8: time=20.0 ms
64 bytes from 8.8.8.8: time=12.5 ms"""
        result = parse_ping_output(output)
        assert result == [10.0, 15.5, 20.0, 12.5]

    def test_parse_mixed_valid_invalid_lines(self):
        """Valid lines extracted, invalid lines skipped."""
        output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: time=10.0 ms
Request timeout for icmp_seq 2
64 bytes from 8.8.8.8: time=12.0 ms
--- 8.8.8.8 ping statistics ---"""
        result = parse_ping_output(output)
        assert result == [10.0, 12.0]

"""Tests for RTTMeasurement class in rtt_measurement module."""

from unittest.mock import MagicMock, patch

import icmplib
import pytest

from wanctl.rtt_measurement import (
    RTTAggregationStrategy,
    RTTMeasurement,
    parse_ping_output,
)


def make_host_result(address="8.8.8.8", rtts=None, is_alive=True):
    """Build a mock icmplib Host object for testing."""
    host = MagicMock()
    host.address = address
    if rtts is None:
        rtts = [12.3]
    host.rtts = rtts
    host.min_rtt = min(rtts) if rtts else 0.0
    host.avg_rtt = sum(rtts) / len(rtts) if rtts else 0.0
    host.max_rtt = max(rtts) if rtts else 0.0
    host.packets_sent = len(rtts) if is_alive else 1
    host.packets_received = len(rtts) if is_alive else 0
    host.packet_loss = 0.0 if is_alive else 1.0
    host.is_alive = is_alive
    host.jitter = 0.0
    return host


class TestPingHostsWithResults:
    """Tests for RTTMeasurement.ping_hosts_with_results() method."""

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

    def test_empty_hosts_returns_empty_dict(self, rtt_measurement):
        """Empty hosts list returns empty dict."""
        result = rtt_measurement.ping_hosts_with_results([])
        assert result == {}

    def test_all_hosts_succeed(self, rtt_measurement):
        """All hosts succeed: each mapped to RTT float."""
        with patch.object(rtt_measurement, "ping_host") as mock_ping:
            mock_ping.side_effect = [10.0, 20.0, 30.0]
            result = rtt_measurement.ping_hosts_with_results(["8.8.8.8", "1.1.1.1", "9.9.9.9"])
        assert len(result) == 3
        assert result["8.8.8.8"] == 10.0
        assert result["1.1.1.1"] == 20.0
        assert result["9.9.9.9"] == 30.0

    def test_some_hosts_fail(self, rtt_measurement):
        """Some hosts fail: failed hosts mapped to None."""
        with patch.object(rtt_measurement, "ping_host") as mock_ping:
            mock_ping.side_effect = [10.0, None, 30.0]
            result = rtt_measurement.ping_hosts_with_results(["8.8.8.8", "1.1.1.1", "9.9.9.9"])
        assert result["8.8.8.8"] == 10.0
        assert result["1.1.1.1"] is None
        assert result["9.9.9.9"] == 30.0

    def test_all_hosts_fail(self, rtt_measurement):
        """All hosts fail: all mapped to None."""
        with patch.object(rtt_measurement, "ping_host") as mock_ping:
            mock_ping.return_value = None
            result = rtt_measurement.ping_hosts_with_results(["8.8.8.8", "1.1.1.1"])
        assert result["8.8.8.8"] is None
        assert result["1.1.1.1"] is None

    def test_timeout_marks_remaining_as_none(self, rtt_measurement):
        """Timed-out hosts are mapped to None."""
        import time

        def slow_ping(*args, **kwargs):
            time.sleep(10)
            return 10.0

        with patch.object(rtt_measurement, "ping_host", side_effect=slow_ping):
            result = rtt_measurement.ping_hosts_with_results(["8.8.8.8"], timeout=0.01)
        assert result["8.8.8.8"] is None


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
    def mock_icmplib_ping(self):
        """Create a mock for icmplib.ping."""
        with patch("wanctl.rtt_measurement.icmplib.ping") as mock:
            yield mock

    def test_returns_list_of_rtts(self, rtt_measurement, mock_icmplib_ping):
        """Should return list of successful RTT values."""
        mock_icmplib_ping.return_value = make_host_result(rtts=[12.3])

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert len(rtts) == 2
        assert all(isinstance(rtt, float) for rtt in rtts)

    def test_empty_hosts_returns_empty_list(self, rtt_measurement):
        """Should return empty list for empty hosts."""
        result = rtt_measurement.ping_hosts_concurrent([])
        assert result == []

    def test_partial_failures_return_successful_only(self, rtt_measurement, mock_icmplib_ping):
        """Should return only successful pings when some fail."""
        # First ping succeeds, second fails
        mock_icmplib_ping.side_effect = [
            make_host_result(rtts=[12.3]),
            make_host_result(is_alive=False),
        ]

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert len(rtts) == 1
        assert rtts[0] == pytest.approx(12.3)

    def test_all_failures_return_empty_list(self, rtt_measurement, mock_icmplib_ping):
        """Should return empty list when all pings fail."""
        mock_icmplib_ping.return_value = make_host_result(is_alive=False)

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1"])

        assert rtts == []

    def test_timeout_handled_gracefully(self, rtt_measurement, mock_icmplib_ping):
        """Should handle icmplib timeout without crashing."""
        mock_icmplib_ping.side_effect = icmplib.ICMPLibError

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8"], timeout=0.1)

        assert rtts == []

    def test_single_host_works(self, rtt_measurement, mock_icmplib_ping):
        """Should work with a single host."""
        mock_icmplib_ping.return_value = make_host_result(rtts=[15.7])

        rtts = rtt_measurement.ping_hosts_concurrent(["8.8.8.8"])

        assert len(rtts) == 1
        assert rtts[0] == pytest.approx(15.7)

    def test_three_hosts_for_median_of_three(self, rtt_measurement, mock_icmplib_ping):
        """Should work with three hosts (median-of-three scenario)."""
        mock_icmplib_ping.side_effect = [
            make_host_result(rtts=[10.0]),
            make_host_result(rtts=[12.0]),
            make_host_result(rtts=[14.0]),
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


class TestAggregationStrategies:
    """Tests for RTTMeasurement._aggregate_rtts and all 4 strategies (lines 216-228)."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_average_strategy(self, mock_logger):
        """AVERAGE strategy returns mean of samples (line 219-220)."""
        rtt = RTTMeasurement(
            logger=mock_logger,
            aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        )
        result = rtt._aggregate_rtts([10.0, 20.0, 30.0])
        assert result == pytest.approx(20.0)

    def test_median_strategy(self, mock_logger):
        """MEDIAN strategy returns median of samples (lines 221-222)."""
        rtt = RTTMeasurement(
            logger=mock_logger,
            aggregation_strategy=RTTAggregationStrategy.MEDIAN,
        )
        result = rtt._aggregate_rtts([10.0, 20.0, 100.0])
        assert result == pytest.approx(20.0)  # Middle value

    def test_min_strategy(self, mock_logger):
        """MIN strategy returns smallest value (lines 223-224)."""
        rtt = RTTMeasurement(
            logger=mock_logger,
            aggregation_strategy=RTTAggregationStrategy.MIN,
        )
        result = rtt._aggregate_rtts([15.0, 5.0, 25.0])
        assert result == pytest.approx(5.0)

    def test_max_strategy(self, mock_logger):
        """MAX strategy returns largest value (lines 225-226)."""
        rtt = RTTMeasurement(
            logger=mock_logger,
            aggregation_strategy=RTTAggregationStrategy.MAX,
        )
        result = rtt._aggregate_rtts([15.0, 5.0, 25.0])
        assert result == pytest.approx(25.0)

    def test_empty_list_raises_value_error(self, mock_logger):
        """Empty list raises ValueError (lines 215-216)."""
        rtt = RTTMeasurement(
            logger=mock_logger,
            aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        )
        with pytest.raises(ValueError, match="Cannot aggregate empty RTT list"):
            rtt._aggregate_rtts([])

    def test_single_value_all_strategies(self, mock_logger):
        """All strategies return same result for single value."""
        for strategy in RTTAggregationStrategy:
            rtt = RTTMeasurement(
                logger=mock_logger,
                aggregation_strategy=strategy,
            )
            result = rtt._aggregate_rtts([42.5])
            assert result == pytest.approx(42.5), f"Strategy {strategy} failed"


class TestPingHostEdgeCases:
    """Tests for ping_host edge cases using icmplib."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_icmplib_ping(self):
        """Create a mock for icmplib.ping."""
        with patch("wanctl.rtt_measurement.icmplib.ping") as mock:
            yield mock

    def test_icmplib_ping_called_with_correct_params(self, mock_logger, mock_icmplib_ping):
        """Verify icmplib.ping is called with correct parameters."""
        mock_icmplib_ping.return_value = make_host_result(rtts=[10.0])

        rtt = RTTMeasurement(
            logger=mock_logger,
            timeout_ping=2,
        )
        rtt.ping_host("8.8.8.8", count=3)

        mock_icmplib_ping.assert_called_once_with(
            address="8.8.8.8",
            count=3,
            interval=0,
            timeout=2,
            privileged=True,
            source=None,
        )

    def test_no_rtt_samples_returns_none_logs_warning(self, mock_logger, mock_icmplib_ping):
        """Empty RTT list logs warning, returns None."""
        mock_icmplib_ping.return_value = make_host_result(rtts=[], is_alive=True)
        # Override is_alive since make_host_result sets packets_received=0 for empty rtts
        mock_icmplib_ping.return_value.is_alive = True

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "No RTT samples" in mock_logger.warning.call_args[0][0]

    def test_log_sample_stats_logs_debug(self, mock_logger, mock_icmplib_ping):
        """log_sample_stats=True logs min/max/count."""
        mock_icmplib_ping.return_value = make_host_result(rtts=[10.0, 20.0, 30.0])

        rtt = RTTMeasurement(
            logger=mock_logger,
            log_sample_stats=True,
        )
        rtt.ping_host("8.8.8.8", count=3)

        # Find the debug call that contains sample stats
        debug_calls = mock_logger.debug.call_args_list
        stats_logged = any("min=" in str(call) and "max=" in str(call) for call in debug_calls)
        assert stats_logged, "Sample stats (min/max) not logged"

    def test_generic_exception_logged(self, mock_logger, mock_icmplib_ping):
        """Non-icmplib exception caught and logged."""
        mock_icmplib_ping.side_effect = OSError("Network unreachable")

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Ping error" in mock_logger.error.call_args[0][0]

    def test_not_alive_logs_warning(self, mock_logger, mock_icmplib_ping):
        """Host not alive (no response) logs warning."""
        mock_icmplib_ping.return_value = make_host_result(is_alive=False)

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "failed" in mock_logger.warning.call_args[0][0].lower()

    def test_icmplib_name_lookup_error(self, mock_logger, mock_icmplib_ping):
        """NameLookupError caught and logged as warning."""
        mock_icmplib_ping.side_effect = icmplib.NameLookupError("nonexistent.host")

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("nonexistent.host")

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "DNS" in mock_logger.warning.call_args[0][0]


class TestIcmplibErrorHandling:
    """Tests for icmplib-specific error handling in ping_host."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_icmplib_ping(self):
        """Create a mock for icmplib.ping."""
        with patch("wanctl.rtt_measurement.icmplib.ping") as mock:
            yield mock

    def test_socket_permission_error_logs_error(self, mock_logger, mock_icmplib_ping):
        """SocketPermissionError logs error about CAP_NET_RAW."""
        mock_icmplib_ping.side_effect = icmplib.SocketPermissionError(privileged=True)

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.error.assert_called_once()
        assert "CAP_NET_RAW" in mock_logger.error.call_args[0][0]

    def test_icmplib_error_logs_error(self, mock_logger, mock_icmplib_ping):
        """ICMPLibError logs error."""
        mock_icmplib_ping.side_effect = icmplib.ICMPLibError

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("8.8.8.8")

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Ping error" in mock_logger.error.call_args[0][0]

    def test_name_lookup_error_logs_warning(self, mock_logger, mock_icmplib_ping):
        """NameLookupError logs warning about DNS."""
        mock_icmplib_ping.side_effect = icmplib.NameLookupError("bad.host")

        rtt = RTTMeasurement(logger=mock_logger)
        result = rtt.ping_host("bad.host")

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "DNS" in mock_logger.warning.call_args[0][0]


class TestIcmplibInHotPath:
    """Test that ping_host uses icmplib directly."""

    def test_uses_icmplib_not_subprocess(self):
        """Verify that ping_host uses icmplib.ping (not subprocess)."""
        mock_logger = MagicMock()
        rtt = RTTMeasurement(logger=mock_logger)

        with patch("wanctl.rtt_measurement.icmplib.ping") as mock_icmplib:
            mock_icmplib.return_value = make_host_result(rtts=[10.0])
            rtt.ping_host("8.8.8.8")

            # icmplib should be called
            mock_icmplib.assert_called_once()


class TestPingHostsConcurrentEdgeCases:
    """Tests for ping_hosts_concurrent edge cases - lines 275-276."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_concurrent_timeout_logs_debug(self, mock_logger):
        """concurrent.futures.TimeoutError logged at debug level (lines 275-276)."""

        rtt = RTTMeasurement(logger=mock_logger)

        # Mock ping_host to hang indefinitely (simulate slow ping)
        def slow_ping(*args, **kwargs):
            import time

            time.sleep(10)  # Will exceed timeout
            return 10.0

        with patch.object(rtt, "ping_host", side_effect=slow_ping):
            result = rtt.ping_hosts_concurrent(["8.8.8.8"], timeout=0.01)

        # Should return empty (timeout before any result)
        assert result == []
        # Debug message about timeout should be logged
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("timeout" in call.lower() for call in debug_calls)

    def test_none_results_filtered(self, mock_logger):
        """ping_host returning None excluded from results (line 271)."""
        rtt = RTTMeasurement(logger=mock_logger)

        # Mock ping_host to return mix of values and None
        with patch.object(rtt, "ping_host") as mock_ping:
            mock_ping.side_effect = [10.0, None, 20.0]

            result = rtt.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1", "9.9.9.9"])

        # Only non-None values should be returned
        assert len(result) == 2
        assert 10.0 in result
        assert 20.0 in result
        assert None not in result

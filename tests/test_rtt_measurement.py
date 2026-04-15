"""Tests for RTTMeasurement class in rtt_measurement module."""

import dataclasses
import statistics
import threading
import time
from unittest.mock import MagicMock, patch

import icmplib
import pytest

from tests.helpers import make_host_result
from wanctl.rtt_measurement import (
    BackgroundRTTThread,
    RTTAggregationStrategy,
    RTTCycleStatus,
    RTTMeasurement,
    RTTSnapshot,
    parse_ping_output,
)


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
        stats_logged = any("min=" in str(c) and "max=" in str(c) for c in debug_calls)
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
        debug_calls = [str(c) for c in mock_logger.debug.call_args_list]
        assert any("timeout" in c.lower() for c in debug_calls)

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


class TestRTTSnapshot:
    """Tests for RTTSnapshot frozen dataclass."""

    def test_frozen_dataclass(self):
        """RTTSnapshot is immutable (frozen)."""
        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"8.8.8.8": 10.0, "1.1.1.1": 12.0},
            timestamp=100.0,
            measurement_ms=42.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.rtt_ms = 99.0  # type: ignore[misc]

    def test_fields_accessible(self):
        """All fields accessible with correct values."""
        hosts = {"8.8.8.8": 10.0, "1.1.1.1": 12.0, "9.9.9.9": 11.0}
        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results=hosts,
            timestamp=500.0,
            measurement_ms=35.0,
        )
        assert snap.rtt_ms == 11.0
        assert snap.per_host_results == hosts
        assert snap.timestamp == 500.0
        assert snap.measurement_ms == 35.0
        assert snap.active_hosts == ()
        assert snap.successful_hosts == ()

    def test_optional_host_tuples_accessible(self):
        """Precomputed host tuples are exposed when producer populates them."""
        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"8.8.8.8": 10.0, "1.1.1.1": None},
            timestamp=500.0,
            measurement_ms=35.0,
            active_hosts=("8.8.8.8", "1.1.1.1"),
            successful_hosts=("8.8.8.8",),
        )
        assert snap.active_hosts == ("8.8.8.8", "1.1.1.1")
        assert snap.successful_hosts == ("8.8.8.8",)


class TestBackgroundRTTThread:
    """Tests for BackgroundRTTThread lifecycle, caching, and staleness."""

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Mock RTTMeasurement with ping_host returning 10.0."""
        m = MagicMock(spec=RTTMeasurement)
        m.ping_host.return_value = 10.0
        return m

    @pytest.fixture
    def shutdown_event(self):
        """Real threading.Event for shutdown."""
        return threading.Event()

    @pytest.fixture
    def mock_logger(self):
        """Mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_pool(self):
        """Mock ThreadPoolExecutor."""
        pool = MagicMock()
        return pool

    def test_get_latest_returns_none_before_start(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """get_latest() returns None before any measurement."""
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )
        assert thread.get_latest() is None

    def test_cycle_status_is_none_before_first_cycle(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """Producer contract: get_cycle_status() returns None before _run() has executed.

        Pins the first-cycle sentinel documented in get_cycle_status().
        Mirrors test_get_latest_returns_none_before_start for the parallel
        cycle-status surface introduced in Plan 187-01.
        """
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )
        assert thread.get_cycle_status() is None
        assert thread._last_cycle_status is None

    def test_lifecycle_start_stop(
        self, mock_rtt_measurement, shutdown_event, mock_logger
    ):
        """Thread starts alive, stops cleanly on shutdown_event."""
        import concurrent.futures

        real_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            # Make ping_host return immediately
            mock_rtt_measurement.ping_host.return_value = 10.0

            thread = BackgroundRTTThread(
                rtt_measurement=mock_rtt_measurement,
                hosts_fn=lambda: ["8.8.8.8"],
                shutdown_event=shutdown_event,
                logger=mock_logger,
                pool=real_pool,
            )
            thread.start()
            assert thread._thread is not None
            assert thread._thread.is_alive()

            shutdown_event.set()
            thread.stop()
            assert not thread._thread.is_alive()
        finally:
            real_pool.shutdown(wait=False)

    def test_caching_updates_after_measurement(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """After measurement, get_latest() returns RTTSnapshot with correct rtt_ms."""
        # Mock the pool to simulate concurrent pings
        future_a = MagicMock()
        future_a.result.return_value = 10.0
        future_b = MagicMock()
        future_b.result.return_value = 12.0
        future_c = MagicMock()
        future_c.result.return_value = 11.0

        mock_pool.submit.side_effect = [future_a, future_b, future_c]

        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )

        _original_wait = shutdown_event.wait  # noqa: F841

        def wait_then_stop(timeout=None):
            """Allow one iteration then signal shutdown."""
            shutdown_event.set()
            return True

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future_a, future_b, future_c}, set()),
        ):
            with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
                thread._run()

        snap = thread.get_latest()
        assert snap is not None
        assert snap.rtt_ms == statistics.median([10.0, 12.0, 11.0])
        assert len(snap.per_host_results) == 3
        assert snap.active_hosts == ("8.8.8.8", "1.1.1.1", "9.9.9.9")
        assert set(snap.successful_hosts) == {"8.8.8.8", "1.1.1.1", "9.9.9.9"}
        assert snap.timestamp > 0
        assert snap.measurement_ms >= 0

    def test_stale_data_preserved_on_all_failures(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """If all pings fail, _cached is NOT overwritten."""
        known_snap = RTTSnapshot(
            rtt_ms=10.0,
            per_host_results={"8.8.8.8": 10.0},
            timestamp=time.monotonic(),
            measurement_ms=5.0,
        )
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8", "1.1.1.1"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )
        thread._cached = known_snap  # Pre-set known snapshot

        # All futures return None (failed pings)
        future_a = MagicMock()
        future_a.result.return_value = None
        future_b = MagicMock()
        future_b.result.return_value = None
        mock_pool.submit.side_effect = [future_a, future_b]

        def wait_then_stop(timeout=None):
            shutdown_event.set()
            return True

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future_a, future_b}, set()),
        ):
            with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
                thread._run()

        # Should still be the same object
        assert thread._cached is known_snap

    def test_cycle_status_published_on_zero_success_preserves_cached(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """Producer contract: a zero-success cycle publishes RTTCycleStatus AND preserves _cached.

        This is the combined Phase 187 publish witness and the Phase 132
        stale-prefer-none non-regression witness, pinned at the producer.
        Mirrors test_stale_data_preserved_on_all_failures' harness.
        """
        known_snap = RTTSnapshot(
            rtt_ms=10.0,
            per_host_results={"8.8.8.8": 10.0},
            timestamp=time.monotonic(),
            measurement_ms=5.0,
        )
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8", "1.1.1.1"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )
        thread._cached = known_snap  # Pre-set known snapshot

        future_a = MagicMock()
        future_a.result.return_value = None
        future_b = MagicMock()
        future_b.result.return_value = None
        mock_pool.submit.side_effect = [future_a, future_b]

        def wait_then_stop(timeout=None):
            shutdown_event.set()
            return True

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future_a, future_b}, set()),
        ):
            with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
                thread._run()

        # Phase 132 non-regression: _cached MUST still be the same object.
        assert thread._cached is known_snap
        # And the public accessor MUST also still return that same object
        # -- tightens the non-overwrite guarantee at the consumer-visible
        # surface, not just the private attribute.
        assert thread.get_latest() is known_snap

        # Phase 187 producer contract: zero-success cycle publishes status.
        status = thread.get_cycle_status()
        assert status is not None
        assert isinstance(status, RTTCycleStatus)
        assert status.successful_count == 0
        assert status.active_hosts == ("8.8.8.8", "1.1.1.1")
        assert status.successful_hosts == ()
        assert status.cycle_timestamp > 0

    def test_cycle_status_published_on_successful_cycle(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """Producer contract: a successful cycle publishes RTTCycleStatus with the current hosts.

        Mirrors test_caching_updates_after_measurement's harness so the
        new assertions run against the same proven _run() exercise path.
        """
        future_a = MagicMock()
        future_a.result.return_value = 10.0
        future_b = MagicMock()
        future_b.result.return_value = 12.0
        future_c = MagicMock()
        future_c.result.return_value = 11.0

        mock_pool.submit.side_effect = [future_a, future_b, future_c]

        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )

        def wait_then_stop(timeout=None):
            shutdown_event.set()
            return True

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future_a, future_b, future_c}, set()),
        ):
            with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
                thread._run()

        status = thread.get_cycle_status()
        assert status is not None
        assert isinstance(status, RTTCycleStatus)
        assert status.successful_count == 3
        assert status.active_hosts == ("8.8.8.8", "1.1.1.1", "9.9.9.9")
        # Order-agnostic set comparison: concurrent.futures.wait makes no
        # guarantee about completion order, so successful_hosts (built from
        # iteration over the completed set) can reach the producer in any
        # order. We pin membership with a set and pin cardinality with
        # len() to lock the full contract without asserting a spurious
        # ordering.
        assert set(status.successful_hosts) == {"8.8.8.8", "1.1.1.1", "9.9.9.9"}
        assert len(status.successful_hosts) == 3
        assert status.cycle_timestamp > 0
        # Producer contract: a successful cycle ALSO updates _cached, and
        # the published status must agree with the cached snapshot's hosts.
        # RTTSnapshot carries active_hosts as a tuple[str, ...] (see
        # src/wanctl/rtt_measurement.py lines 90-104) and is populated
        # with tuple(hosts) on the successful-cycle path (line 478), so
        # this cross-check is a stable extra witness of the publish-site
        # agreement between _last_cycle_status and _cached.
        snap = thread.get_latest()
        assert snap is not None
        assert status.active_hosts == snap.active_hosts

    def test_cadence_adjustment(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """Sleep time adjusts for measurement duration: sleep = max(0, cadence - elapsed)."""
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
            cadence_sec=0.05,  # 50ms cadence
        )

        future = MagicMock()
        future.result.return_value = 10.0
        mock_pool.submit.return_value = future

        # Track the wait timeout values
        wait_timeouts: list[float] = []

        def wait_then_stop(timeout=None):
            """Capture timeout and signal shutdown."""
            if timeout is not None:
                wait_timeouts.append(timeout)
            shutdown_event.set()
            return True

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future}, set()),
        ):
            # Mock perf_counter to simulate 30ms measurement
            with patch("wanctl.rtt_measurement.time.perf_counter", side_effect=[0.0, 0.030]):
                with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
                    thread._run()

        # Should have computed sleep = max(0, 0.05 - 0.030) = 0.02
        assert len(wait_timeouts) == 1
        assert wait_timeouts[0] == pytest.approx(0.02, abs=0.005)

    def test_persistent_pool_not_recreated(
        self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
    ):
        """_ping_with_persistent_pool uses self._pool.submit, not creating a new pool."""
        thread = BackgroundRTTThread(
            rtt_measurement=mock_rtt_measurement,
            hosts_fn=lambda: ["8.8.8.8"],
            shutdown_event=shutdown_event,
            logger=mock_logger,
            pool=mock_pool,
        )

        future = MagicMock()
        future.result.return_value = 10.0
        mock_pool.submit.return_value = future

        with patch(
            "wanctl.rtt_measurement.concurrent.futures.wait",
            return_value=({future}, set()),
        ):
            thread._ping_with_persistent_pool(["8.8.8.8"])

        # Should have used the provided pool
        mock_pool.submit.assert_called_once()


class TestMeasureRTTNonBlocking:
    """Integration tests for WANController.measure_rtt() with BackgroundRTTThread."""

    @pytest.fixture
    def mock_wan_controller(self):
        """Create a minimal mock WANController with the fields measure_rtt needs."""
        wc = MagicMock()
        wc.wan_name = "spectrum"
        wc.logger = MagicMock()
        wc._reflector_scorer = MagicMock()
        wc._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        wc._persist_reflector_events = MagicMock()
        return wc

    def test_measure_rtt_reads_from_background_thread(self, mock_wan_controller):
        """measure_rtt() reads from background thread and returns rtt_ms."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic(),
            measurement_ms=30.0,
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap

        result = WANController.measure_rtt(mock_wan_controller)
        assert result == 11.0
        # Should record per-host results for quality scoring
        mock_wan_controller._reflector_scorer.record_results.assert_called_once_with(
            {"a": True, "b": True, "c": True}
        )

    def test_measure_rtt_stale_hard_fail(self, mock_wan_controller):
        """RTT data >5s old returns None (hard fail per D-04)."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0},
            timestamp=time.monotonic() - 6.0,
            measurement_ms=30.0,
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap

        result = WANController.measure_rtt(mock_wan_controller)
        assert result is None
        mock_wan_controller.logger.warning.assert_called()
        assert "stale" in mock_wan_controller.logger.warning.call_args[0][0].lower()

    def test_measure_rtt_stale_soft_warning(self, mock_wan_controller):
        """RTT data 0.5-5s old returns value but logs warning."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0},
            timestamp=time.monotonic() - 1.0,
            measurement_ms=30.0,
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap

        result = WANController.measure_rtt(mock_wan_controller)
        assert result == 11.0
        mock_wan_controller.logger.debug.assert_called()
        debug_calls = [str(c) for c in mock_wan_controller.logger.debug.call_args_list]
        assert any("aging" in c.lower() for c in debug_calls)

    def test_measure_rtt_no_snapshot_returns_none(self, mock_wan_controller):
        """No snapshot yet (thread starting) returns None."""
        from wanctl.wan_controller import WANController

        mock_wan_controller._rtt_thread.get_latest.return_value = None

        result = WANController.measure_rtt(mock_wan_controller)
        assert result is None
        mock_wan_controller.logger.warning.assert_called()

    def test_measure_rtt_fallback_blocking_when_no_thread(self, mock_wan_controller):
        """When _rtt_thread is None, falls back to _measure_rtt_blocking."""
        from wanctl.wan_controller import WANController

        mock_wan_controller._rtt_thread = None
        mock_wan_controller._measure_rtt_blocking = MagicMock(return_value=15.0)

        result = WANController.measure_rtt(mock_wan_controller)
        assert result == 15.0
        mock_wan_controller._measure_rtt_blocking.assert_called_once()

"""Unit tests for wanctl.calibrate CLI tool."""

import argparse
from datetime import datetime
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from wanctl.calibrate import (
    CalibrationResult,
    binary_search_optimal_rate,
    check_netperf_server,
    check_ssh_connectivity,
    generate_config,
    main,
    measure_baseline_rtt,
    measure_throughput_download,
    measure_throughput_upload,
    run_calibration,
    set_cake_limit,
)

# =============================================================================
# TEST HELPERS
# =============================================================================


def parse_args_safely(args: list[str]) -> argparse.Namespace:
    """Helper to parse args without sys.exit on success.

    Creates a parser with the same arguments as main() for testing.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--wan-name", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--user", default="admin")
    parser.add_argument("--ssh-key")
    parser.add_argument("--netperf-host", default="netperf.bufferbloat.net")
    parser.add_argument("--ping-host", default="1.1.1.1")
    parser.add_argument("--download-queue")
    parser.add_argument("--upload-queue")
    parser.add_argument("--target-bloat", type=float, default=10.0)
    parser.add_argument("--output-dir", default="/etc/wanctl")
    parser.add_argument("--skip-binary-search", action="store_true")
    return parser.parse_args(args)


# Sample ping output for tests
PING_OUTPUT_SUCCESS = """
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=12.3 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=11.8 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=57 time=12.1 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 11.800/12.066/12.300/0.205 ms
"""

PING_OUTPUT_NO_RTT = """
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2000ms
"""

NETPERF_OUTPUT_SUCCESS = """
MIGRATED TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to netperf.bufferbloat.net () port 0 AF_INET
Recv   Send    Send
Socket Socket  Message  Elapsed
Size   Size    Size     Time     Throughput
bytes  bytes   bytes    secs.    10^6bits/sec

 87380  65536  65536    15.00     245.73
"""


# =============================================================================
# TEST ARGUMENT PARSING
# =============================================================================


class TestArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_missing_wan_name_raises_error(self):
        """Test that missing --wan-name raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args_safely(["--router", "192.168.1.1"])

    def test_missing_router_raises_error(self):
        """Test that missing --router raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args_safely(["--wan-name", "wan1"])

    def test_required_args_both_provided(self):
        """Test that both required args succeed."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.wan_name == "wan1"
        assert args.router == "192.168.1.1"

    def test_user_default_is_admin(self):
        """Test that --user defaults to 'admin'."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.user == "admin"

    def test_netperf_host_default(self):
        """Test that --netperf-host has correct default."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.netperf_host == "netperf.bufferbloat.net"

    def test_ping_host_default(self):
        """Test that --ping-host defaults to 1.1.1.1."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.ping_host == "1.1.1.1"

    def test_target_bloat_default(self):
        """Test that --target-bloat defaults to 10.0."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.target_bloat == 10.0

    def test_output_dir_default(self):
        """Test that --output-dir defaults to /etc/wanctl."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.output_dir == "/etc/wanctl"

    def test_user_override(self):
        """Test that --user override works."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--user", "custom_user"
        ])
        assert args.user == "custom_user"

    def test_ssh_key_accepts_path(self):
        """Test that --ssh-key accepts a path."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--ssh-key", "/path/to/key"
        ])
        assert args.ssh_key == "/path/to/key"

    def test_download_queue_override(self):
        """Test that --download-queue sets custom queue name."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--download-queue", "custom-dl-queue"
        ])
        assert args.download_queue == "custom-dl-queue"

    def test_upload_queue_override(self):
        """Test that --upload-queue sets custom queue name."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--upload-queue", "custom-ul-queue"
        ])
        assert args.upload_queue == "custom-ul-queue"

    def test_target_bloat_accepts_float(self):
        """Test that --target-bloat accepts float value."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--target-bloat", "15.5"
        ])
        assert args.target_bloat == 15.5

    def test_skip_binary_search_sets_flag(self):
        """Test that --skip-binary-search sets flag True."""
        args = parse_args_safely([
            "--wan-name", "wan1",
            "--router", "192.168.1.1",
            "--skip-binary-search"
        ])
        assert args.skip_binary_search is True

    def test_skip_binary_search_default_false(self):
        """Test that --skip-binary-search defaults to False."""
        args = parse_args_safely(["--wan-name", "wan1", "--router", "192.168.1.1"])
        assert args.skip_binary_search is False

    def test_all_optional_args_combined(self):
        """Test all optional arguments together."""
        args = parse_args_safely([
            "--wan-name", "cable",
            "--router", "10.0.0.1",
            "--user", "root",
            "--ssh-key", "/root/.ssh/id_ed25519",
            "--netperf-host", "custom.netperf.server",
            "--ping-host", "8.8.8.8",
            "--download-queue", "DL-Cable",
            "--upload-queue", "UL-Cable",
            "--target-bloat", "8.0",
            "--output-dir", "/tmp/wanctl",
            "--skip-binary-search"
        ])
        assert args.wan_name == "cable"
        assert args.router == "10.0.0.1"
        assert args.user == "root"
        assert args.ssh_key == "/root/.ssh/id_ed25519"
        assert args.netperf_host == "custom.netperf.server"
        assert args.ping_host == "8.8.8.8"
        assert args.download_queue == "DL-Cable"
        assert args.upload_queue == "UL-Cable"
        assert args.target_bloat == 8.0
        assert args.output_dir == "/tmp/wanctl"
        assert args.skip_binary_search is True


# =============================================================================
# TEST CALIBRATION RESULT DATACLASS
# =============================================================================


class TestCalibrationResult:
    """Tests for CalibrationResult dataclass."""

    def test_to_dict_serialization(self):
        """Test that to_dict() serializes all fields correctly."""
        result = CalibrationResult(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=12.5,
            raw_download_mbps=500.0,
            raw_upload_mbps=50.0,
            optimal_download_mbps=450.0,
            optimal_upload_mbps=45.0,
            download_bloat_ms=8.5,
            upload_bloat_ms=7.2,
            floor_download_mbps=90.0,
            floor_upload_mbps=9.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        d = result.to_dict()

        assert d["wan_name"] == "wan1"
        assert d["router_host"] == "192.168.1.1"
        assert d["router_user"] == "admin"
        assert d["baseline_rtt_ms"] == 12.5
        assert d["raw_download_mbps"] == 500.0
        assert d["raw_upload_mbps"] == 50.0
        assert d["optimal_download_mbps"] == 450.0
        assert d["optimal_upload_mbps"] == 45.0
        assert d["download_bloat_ms"] == 8.5
        assert d["upload_bloat_ms"] == 7.2
        assert d["floor_download_mbps"] == 90.0
        assert d["floor_upload_mbps"] == 9.0
        assert d["timestamp"] == "2026-01-25T10:00:00"
        assert d["target_bloat_ms"] == 10.0

    def test_dataclass_creates_valid_instance(self):
        """Test that dataclass creates a valid instance with all fields."""
        result = CalibrationResult(
            wan_name="fiber",
            router_host="10.0.0.1",
            router_user="root",
            baseline_rtt_ms=5.0,
            raw_download_mbps=1000.0,
            raw_upload_mbps=100.0,
            optimal_download_mbps=950.0,
            optimal_upload_mbps=95.0,
            download_bloat_ms=3.0,
            upload_bloat_ms=2.5,
            floor_download_mbps=190.0,
            floor_upload_mbps=19.0,
            timestamp="2026-01-25T12:00:00",
            target_bloat_ms=5.0,
        )

        assert result.wan_name == "fiber"
        assert result.baseline_rtt_ms == 5.0
        assert isinstance(result.raw_download_mbps, float)

    def test_to_dict_returns_all_fields(self):
        """Test that to_dict includes all 14 fields."""
        result = CalibrationResult(
            wan_name="test",
            router_host="host",
            router_user="user",
            baseline_rtt_ms=1.0,
            raw_download_mbps=1.0,
            raw_upload_mbps=1.0,
            optimal_download_mbps=1.0,
            optimal_upload_mbps=1.0,
            download_bloat_ms=1.0,
            upload_bloat_ms=1.0,
            floor_download_mbps=1.0,
            floor_upload_mbps=1.0,
            timestamp="ts",
            target_bloat_ms=1.0,
        )

        d = result.to_dict()
        expected_keys = {
            "wan_name", "router_host", "router_user",
            "baseline_rtt_ms", "raw_download_mbps", "raw_upload_mbps",
            "optimal_download_mbps", "optimal_upload_mbps",
            "download_bloat_ms", "upload_bloat_ms",
            "floor_download_mbps", "floor_upload_mbps",
            "timestamp", "target_bloat_ms"
        }
        assert set(d.keys()) == expected_keys

    def test_timestamp_format_preserved(self):
        """Test that timestamp format is preserved in to_dict."""
        iso_timestamp = datetime.now().isoformat()
        result = CalibrationResult(
            wan_name="t",
            router_host="h",
            router_user="u",
            baseline_rtt_ms=1.0,
            raw_download_mbps=1.0,
            raw_upload_mbps=1.0,
            optimal_download_mbps=1.0,
            optimal_upload_mbps=1.0,
            download_bloat_ms=1.0,
            upload_bloat_ms=1.0,
            floor_download_mbps=1.0,
            floor_upload_mbps=1.0,
            timestamp=iso_timestamp,
            target_bloat_ms=1.0,
        )

        assert result.to_dict()["timestamp"] == iso_timestamp


# =============================================================================
# TEST CONNECTIVITY
# =============================================================================


class TestConnectivity:
    """Tests for SSH and netperf connectivity functions."""

    @patch("wanctl.calibrate.subprocess.run")
    def check_ssh_connectivity_success(self, mock_run):
        """Test SSH connectivity returns True on success."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        result = check_ssh_connectivity("192.168.1.1", "admin")
        assert result is True
        assert mock_run.called

    @patch("wanctl.calibrate.subprocess.run")
    def check_ssh_connectivity_failure(self, mock_run):
        """Test SSH connectivity returns False on failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Connection refused")
        result = check_ssh_connectivity("192.168.1.1", "admin")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_ssh_connectivity_timeout(self, mock_run):
        """Test SSH connectivity returns False on timeout."""
        mock_run.side_effect = TimeoutExpired(cmd="ssh", timeout=5)
        result = check_ssh_connectivity("192.168.1.1", "admin")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_ssh_connectivity_with_ssh_key(self, mock_run):
        """Test SSH connectivity includes -i flag with SSH key."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        result = check_ssh_connectivity("192.168.1.1", "admin", ssh_key="/path/to/key")
        assert result is True
        # Verify -i and key path appear in the command
        call_args = mock_run.call_args[0][0]  # First positional arg is the command list
        assert "-i" in call_args
        assert "/path/to/key" in call_args

    @patch("wanctl.calibrate.subprocess.run")
    def check_ssh_connectivity_generic_exception(self, mock_run):
        """Test SSH connectivity returns False on generic exception."""
        mock_run.side_effect = OSError("Network unreachable")
        result = check_ssh_connectivity("192.168.1.1", "admin")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_netperf_server_success(self, mock_run):
        """Test netperf server returns True on success."""
        mock_run.return_value = MagicMock(returncode=0, stdout=NETPERF_OUTPUT_SUCCESS, stderr="")
        result = check_netperf_server("netperf.bufferbloat.net")
        assert result is True

    @patch("wanctl.calibrate.subprocess.run")
    def check_netperf_server_failure(self, mock_run):
        """Test netperf server returns False on failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Connection refused")
        result = check_netperf_server("netperf.bufferbloat.net")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_netperf_server_not_installed(self, mock_run):
        """Test netperf server returns False when netperf not installed."""
        mock_run.side_effect = FileNotFoundError("netperf not found")
        result = check_netperf_server("netperf.bufferbloat.net")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_netperf_server_timeout(self, mock_run):
        """Test netperf server returns False on timeout."""
        mock_run.side_effect = TimeoutExpired(cmd="netperf", timeout=30)
        result = check_netperf_server("netperf.bufferbloat.net")
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def check_netperf_server_generic_exception(self, mock_run):
        """Test netperf server returns False on generic exception."""
        mock_run.side_effect = OSError("Network unreachable")
        result = check_netperf_server("netperf.bufferbloat.net")
        assert result is False


# =============================================================================
# TEST MEASUREMENT
# =============================================================================


class TestMeasurement:
    """Tests for RTT and throughput measurement functions."""

    @patch("wanctl.calibrate.subprocess.run")
    def test_measure_baseline_rtt_success(self, mock_run):
        """Test baseline RTT measurement returns float on success."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_SUCCESS, stderr=""
        )
        result = measure_baseline_rtt("1.1.1.1")
        # Should return minimum RTT (11.8 from sample)
        assert result is not None
        assert isinstance(result, float)
        assert result == pytest.approx(11.8, rel=0.01)

    @patch("wanctl.calibrate.subprocess.run")
    def test_measure_baseline_rtt_failure(self, mock_run):
        """Test baseline RTT measurement returns None on ping failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ping: unknown host")
        result = measure_baseline_rtt("invalid.host")
        assert result is None

    @patch("wanctl.calibrate.subprocess.run")
    def test_measure_baseline_rtt_timeout(self, mock_run):
        """Test baseline RTT measurement returns None on timeout."""
        mock_run.side_effect = TimeoutExpired(cmd="ping", timeout=30)
        result = measure_baseline_rtt("1.1.1.1")
        assert result is None

    @patch("wanctl.calibrate.subprocess.run")
    def test_measure_baseline_rtt_no_samples(self, mock_run):
        """Test baseline RTT measurement returns None when no RTT values parsed."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_NO_RTT, stderr=""
        )
        result = measure_baseline_rtt("1.1.1.1")
        assert result is None

    @patch("wanctl.calibrate.subprocess.run")
    def test_measure_baseline_rtt_generic_exception(self, mock_run):
        """Test baseline RTT measurement returns None on generic exception."""
        mock_run.side_effect = OSError("ping failed")
        result = measure_baseline_rtt("1.1.1.1")
        assert result is None

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.subprocess.run")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_download(self, mock_sleep, mock_run, mock_popen):
        """Test download throughput measurement returns tuple."""
        # Mock netperf process
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (NETPERF_OUTPUT_SUCCESS, "")
        mock_popen.return_value = mock_proc

        # Mock ping result
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_SUCCESS, stderr=""
        )

        throughput, bloat = measure_throughput_download(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert isinstance(throughput, float)
        assert isinstance(bloat, float)
        # Throughput from sample is 245.73
        assert throughput == pytest.approx(245.73, rel=0.01)
        # Bloat should be median RTT (12.1) - baseline (10.0) = 2.1
        assert bloat >= 0

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.subprocess.run")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_upload(self, mock_sleep, mock_run, mock_popen):
        """Test upload throughput measurement returns tuple."""
        # Mock netperf process
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (NETPERF_OUTPUT_SUCCESS, "")
        mock_popen.return_value = mock_proc

        # Mock ping result
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_SUCCESS, stderr=""
        )

        throughput, bloat = measure_throughput_upload(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert isinstance(throughput, float)
        assert isinstance(bloat, float)
        assert throughput == pytest.approx(245.73, rel=0.01)
        assert bloat >= 0

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_download_exception(self, mock_sleep, mock_popen):
        """Test download throughput measurement returns (0.0, 0.0) on exception."""
        mock_popen.side_effect = OSError("Failed to start netperf")

        throughput, bloat = measure_throughput_download(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert throughput == 0.0
        assert bloat == 0.0

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_upload_exception(self, mock_sleep, mock_popen):
        """Test upload throughput measurement returns (0.0, 0.0) on exception."""
        mock_popen.side_effect = OSError("Failed to start netperf")

        throughput, bloat = measure_throughput_upload(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert throughput == 0.0
        assert bloat == 0.0

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.subprocess.run")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_download_no_ping_rtts(self, mock_sleep, mock_run, mock_popen):
        """Test download throughput with no ping RTT values returns zero bloat."""
        # Mock netperf process
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (NETPERF_OUTPUT_SUCCESS, "")
        mock_popen.return_value = mock_proc

        # Mock ping result with no RTT values
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_NO_RTT, stderr=""
        )

        throughput, bloat = measure_throughput_download(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert throughput == pytest.approx(245.73, rel=0.01)
        assert bloat == 0.0

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.subprocess.run")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_download_fallback_pattern(self, mock_sleep, mock_run, mock_popen):
        """Test download throughput parses fallback Mbps pattern."""
        # Mock netperf process with alternative output format
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Throughput: 123.45 Mbps", "")
        mock_popen.return_value = mock_proc

        # Mock ping result
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_SUCCESS, stderr=""
        )

        throughput, bloat = measure_throughput_download(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert throughput == pytest.approx(123.45, rel=0.01)


# =============================================================================
# TEST BINARY SEARCH
# =============================================================================


class TestBinarySearch:
    """Tests for binary search algorithm for optimal rate discovery."""

    @patch("wanctl.calibrate.subprocess.run")
    def test_set_cake_limit_success(self, mock_run):
        """Test set_cake_limit returns True on success."""
        mock_run.return_value = MagicMock(returncode=0)
        result = set_cake_limit(
            "192.168.1.1", "admin", "WAN-Download", 100_000_000
        )
        assert result is True

    @patch("wanctl.calibrate.subprocess.run")
    def test_set_cake_limit_failure(self, mock_run):
        """Test set_cake_limit returns False on failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = set_cake_limit(
            "192.168.1.1", "admin", "WAN-Download", 100_000_000
        )
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def test_set_cake_limit_exception(self, mock_run):
        """Test set_cake_limit returns False on exception."""
        mock_run.side_effect = OSError("SSH failed")
        result = set_cake_limit(
            "192.168.1.1", "admin", "WAN-Download", 100_000_000
        )
        assert result is False

    @patch("wanctl.calibrate.subprocess.run")
    def test_set_cake_limit_with_ssh_key(self, mock_run):
        """Test set_cake_limit includes -i flag with SSH key."""
        mock_run.return_value = MagicMock(returncode=0)
        result = set_cake_limit(
            "192.168.1.1", "admin", "WAN-Download", 100_000_000,
            ssh_key="/path/to/key"
        )
        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "-i" in call_args
        assert "/path/to/key" in call_args

    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.time.sleep")
    def test_binary_search_converges(self, mock_sleep, mock_measure, mock_set_limit):
        """Test binary search converges to optimal rate."""
        mock_set_limit.return_value = True
        # Return values where bloat is below target (10ms)
        mock_measure.return_value = (100.0, 5.0)  # throughput=100, bloat=5ms

        best_rate, best_bloat = binary_search_optimal_rate(
            direction="download",
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            queue_name="WAN-Download",
            min_rate=50.0,
            max_rate=200.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            iterations=3,
        )

        assert isinstance(best_rate, float)
        assert isinstance(best_bloat, float)
        # Since bloat (5.0) < target (10.0), rate should converge upward
        assert best_rate > 50.0

    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.time.sleep")
    def test_binary_search_skips_on_limit_failure(self, mock_sleep, mock_measure, mock_set_limit):
        """Test binary search skips iteration when set_cake_limit fails."""
        mock_set_limit.return_value = False  # Limit setting fails
        mock_measure.return_value = (100.0, 5.0)

        best_rate, best_bloat = binary_search_optimal_rate(
            direction="download",
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            queue_name="WAN-Download",
            min_rate=50.0,
            max_rate=200.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            iterations=3,
        )

        # Best rate should remain at minimum (no successful iterations)
        assert best_rate == 50.0
        # Measure should never be called since limit setting failed
        assert not mock_measure.called

    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.measure_throughput_upload")
    @patch("wanctl.calibrate.time.sleep")
    def test_binary_search_upload_direction(self, mock_sleep, mock_measure, mock_set_limit):
        """Test binary search works for upload direction."""
        mock_set_limit.return_value = True
        mock_measure.return_value = (20.0, 8.0)

        best_rate, best_bloat = binary_search_optimal_rate(
            direction="upload",
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            queue_name="WAN-Upload",
            min_rate=5.0,
            max_rate=50.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            iterations=2,
        )

        assert isinstance(best_rate, float)
        assert mock_measure.called

    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.time.sleep")
    def test_binary_search_decreases_on_high_bloat(self, mock_sleep, mock_measure, mock_set_limit):
        """Test binary search decreases rate when bloat exceeds target."""
        mock_set_limit.return_value = True
        # Return bloat above target (15ms > 10ms target)
        mock_measure.return_value = (100.0, 15.0)

        best_rate, best_bloat = binary_search_optimal_rate(
            direction="download",
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            queue_name="WAN-Download",
            min_rate=50.0,
            max_rate=200.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            iterations=3,
        )

        # Best rate should remain at minimum since bloat always exceeds target
        # and we only update best_rate when bloat <= target
        assert best_rate == 50.0


# =============================================================================
# TEST CONFIG GENERATION
# =============================================================================


class TestConfigGeneration:
    """Tests for configuration file generation."""

    def test_generate_config_success(self, tmp_path):
        """Test generate_config creates valid YAML file."""
        result = CalibrationResult(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=12.5,
            raw_download_mbps=500.0,
            raw_upload_mbps=50.0,
            optimal_download_mbps=450.0,
            optimal_upload_mbps=45.0,
            download_bloat_ms=8.5,
            upload_bloat_ms=7.2,
            floor_download_mbps=90.0,
            floor_upload_mbps=9.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        output_path = tmp_path / "wan1.yaml"
        success = generate_config(result, output_path)

        assert success is True
        assert output_path.exists()

        import yaml
        with open(output_path) as f:
            content = f.read()
            # Skip header comments and parse YAML
            yaml_start = content.find("wan_name:")
            config = yaml.safe_load(content[yaml_start:])

        assert config["wan_name"] == "wan1"
        assert config["router"]["host"] == "192.168.1.1"
        assert config["router"]["user"] == "admin"
        assert "continuous_monitoring" in config
        assert "queues" in config

    def test_generate_config_fiber_detection(self, tmp_path):
        """Test config detects fiber connection (low baseline RTT)."""
        result = CalibrationResult(
            wan_name="fiber",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=8.0,  # < 15ms = fiber
            raw_download_mbps=1000.0,
            raw_upload_mbps=100.0,
            optimal_download_mbps=950.0,
            optimal_upload_mbps=95.0,
            download_bloat_ms=3.0,
            upload_bloat_ms=2.5,
            floor_download_mbps=190.0,
            floor_upload_mbps=19.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=5.0,
        )

        output_path = tmp_path / "fiber.yaml"
        generate_config(result, output_path)

        import yaml
        with open(output_path) as f:
            content = f.read()
            yaml_start = content.find("wan_name:")
            config = yaml.safe_load(content[yaml_start:])

        # Fiber should have alpha_baseline = 0.01
        assert config["continuous_monitoring"]["thresholds"]["alpha_baseline"] == 0.01

    def test_generate_config_cable_detection(self, tmp_path):
        """Test config detects cable connection (medium baseline RTT)."""
        result = CalibrationResult(
            wan_name="cable",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=25.0,  # 15-35ms = cable
            raw_download_mbps=300.0,
            raw_upload_mbps=30.0,
            optimal_download_mbps=270.0,
            optimal_upload_mbps=27.0,
            download_bloat_ms=8.0,
            upload_bloat_ms=7.0,
            floor_download_mbps=54.0,
            floor_upload_mbps=5.4,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        output_path = tmp_path / "cable.yaml"
        generate_config(result, output_path)

        import yaml
        with open(output_path) as f:
            content = f.read()
            yaml_start = content.find("wan_name:")
            config = yaml.safe_load(content[yaml_start:])

        # Cable should have alpha_baseline = 0.02
        assert config["continuous_monitoring"]["thresholds"]["alpha_baseline"] == 0.02

    def test_generate_config_dsl_detection(self, tmp_path):
        """Test config detects DSL connection (high baseline RTT)."""
        result = CalibrationResult(
            wan_name="dsl",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=45.0,  # >= 35ms = DSL
            raw_download_mbps=50.0,
            raw_upload_mbps=10.0,
            optimal_download_mbps=45.0,
            optimal_upload_mbps=9.0,
            download_bloat_ms=12.0,
            upload_bloat_ms=10.0,
            floor_download_mbps=10.0,
            floor_upload_mbps=2.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=15.0,
        )

        output_path = tmp_path / "dsl.yaml"
        generate_config(result, output_path)

        import yaml
        with open(output_path) as f:
            content = f.read()
            yaml_start = content.find("wan_name:")
            config = yaml.safe_load(content[yaml_start:])

        # DSL should have alpha_baseline = 0.015
        assert config["continuous_monitoring"]["thresholds"]["alpha_baseline"] == 0.015

    def test_generate_config_permission_error(self, tmp_path):
        """Test generate_config returns False on permission error."""
        result = CalibrationResult(
            wan_name="test",
            router_host="host",
            router_user="user",
            baseline_rtt_ms=10.0,
            raw_download_mbps=100.0,
            raw_upload_mbps=10.0,
            optimal_download_mbps=90.0,
            optimal_upload_mbps=9.0,
            download_bloat_ms=5.0,
            upload_bloat_ms=4.0,
            floor_download_mbps=18.0,
            floor_upload_mbps=1.8,
            timestamp="ts",
            target_bloat_ms=10.0,
        )

        # Use a path that will fail (nonexistent parent with no permission to create)
        # Mocking open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            success = generate_config(result, tmp_path / "test.yaml")

        assert success is False

    def test_generate_config_includes_metadata_header(self, tmp_path):
        """Test config file includes calibration metadata in header comments."""
        result = CalibrationResult(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=12.5,
            raw_download_mbps=500.0,
            raw_upload_mbps=50.0,
            optimal_download_mbps=450.0,
            optimal_upload_mbps=45.0,
            download_bloat_ms=8.5,
            upload_bloat_ms=7.2,
            floor_download_mbps=90.0,
            floor_upload_mbps=9.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        output_path = tmp_path / "wan1.yaml"
        generate_config(result, output_path)

        with open(output_path) as f:
            content = f.read()

        # Header should contain key calibration info
        assert "Auto-generated by calibration tool" in content
        assert "Baseline RTT:" in content
        assert "Raw download:" in content


# =============================================================================
# TEST MAIN ENTRY POINT
# =============================================================================


class TestMain:
    """Tests for main() entry point function."""

    @patch("sys.argv", ["calibrate", "--wan-name", "wan1", "--router", "192.168.1.1"])
    @patch("wanctl.calibrate.register_signal_handlers")
    @patch("wanctl.calibrate.run_calibration")
    def test_main_success(self, mock_run_cal, mock_signals):
        """Test main() returns 0 on successful calibration."""
        mock_run_cal.return_value = MagicMock()  # Valid result
        result = main()
        assert result == 0
        mock_signals.assert_called_once_with(include_sigterm=False)

    @patch("sys.argv", ["calibrate", "--wan-name", "wan1", "--router", "192.168.1.1"])
    @patch("wanctl.calibrate.register_signal_handlers")
    @patch("wanctl.calibrate.run_calibration")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_main_failure(self, mock_shutdown, mock_run_cal, mock_signals):
        """Test main() returns 1 on calibration failure."""
        mock_run_cal.return_value = None  # Failure
        mock_shutdown.return_value = False  # Not interrupted
        result = main()
        assert result == 1

    @patch("sys.argv", ["calibrate", "--wan-name", "wan1", "--router", "192.168.1.1"])
    @patch("wanctl.calibrate.register_signal_handlers")
    @patch("wanctl.calibrate.run_calibration")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_main_sigint(self, mock_shutdown, mock_run_cal, mock_signals):
        """Test main() returns 130 when shutdown requested (SIGINT)."""
        mock_run_cal.return_value = None
        mock_shutdown.return_value = True  # Interrupted
        result = main()
        assert result == 130  # Standard SIGINT exit code

    @patch("sys.argv", ["calibrate", "--wan-name", "wan1", "--router", "192.168.1.1"])
    @patch("wanctl.calibrate.register_signal_handlers")
    @patch("wanctl.calibrate.run_calibration")
    def test_main_registers_signal_handlers(self, mock_run_cal, mock_signals):
        """Test main() registers signal handlers with include_sigterm=False."""
        mock_run_cal.return_value = MagicMock()
        main()
        mock_signals.assert_called_once_with(include_sigterm=False)

    @patch("sys.argv", [
        "calibrate",
        "--wan-name", "cable",
        "--router", "10.0.0.1",
        "--user", "root",
        "--ssh-key", "/path/to/key",
        "--target-bloat", "15.0",
        "--skip-binary-search"
    ])
    @patch("wanctl.calibrate.register_signal_handlers")
    @patch("wanctl.calibrate.run_calibration")
    def test_main_passes_args_to_run_calibration(self, mock_run_cal, mock_signals):
        """Test main() passes all arguments to run_calibration."""
        mock_run_cal.return_value = MagicMock()
        main()

        mock_run_cal.assert_called_once()
        call_kwargs = mock_run_cal.call_args[1]
        assert call_kwargs["wan_name"] == "cable"
        assert call_kwargs["router_host"] == "10.0.0.1"
        assert call_kwargs["router_user"] == "root"
        assert call_kwargs["ssh_key"] == "/path/to/key"
        assert call_kwargs["target_bloat"] == 15.0
        assert call_kwargs["skip_binary_search"] is True


# =============================================================================
# TEST STEP HELPERS
# =============================================================================


class TestStepHelpers:
    """Tests for calibration step helper functions."""

    @patch("wanctl.calibrate.check_ssh_connectivity")
    def test_step_connectivity_ssh_failure(self, mock_ssh):
        """Test _step_connectivity_tests returns (False, False) on SSH failure."""
        from wanctl.calibrate import _step_connectivity_tests

        mock_ssh.return_value = False
        success, skip_throughput = _step_connectivity_tests(
            "192.168.1.1", "admin", None, "netperf.test"
        )
        assert success is False
        assert skip_throughput is False

    @patch("wanctl.calibrate.check_ssh_connectivity")
    @patch("wanctl.calibrate.check_netperf_server")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_connectivity_netperf_failure(self, mock_shutdown, mock_netperf, mock_ssh):
        """Test _step_connectivity_tests returns (True, True) on netperf failure."""
        from wanctl.calibrate import _step_connectivity_tests

        mock_ssh.return_value = True
        mock_shutdown.return_value = False
        mock_netperf.return_value = False
        success, skip_throughput = _step_connectivity_tests(
            "192.168.1.1", "admin", None, "netperf.test"
        )
        assert success is True
        assert skip_throughput is True  # Skip throughput since netperf failed

    @patch("wanctl.calibrate.check_ssh_connectivity")
    @patch("wanctl.calibrate.check_netperf_server")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_connectivity_full_success(self, mock_shutdown, mock_netperf, mock_ssh):
        """Test _step_connectivity_tests returns (True, False) on full success."""
        from wanctl.calibrate import _step_connectivity_tests

        mock_ssh.return_value = True
        mock_shutdown.return_value = False
        mock_netperf.return_value = True
        success, skip_throughput = _step_connectivity_tests(
            "192.168.1.1", "admin", None, "netperf.test"
        )
        assert success is True
        assert skip_throughput is False

    @patch("wanctl.calibrate.check_ssh_connectivity")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_connectivity_interrupt_after_ssh(self, mock_shutdown, mock_ssh):
        """Test _step_connectivity_tests returns (False, False) on interrupt."""
        from wanctl.calibrate import _step_connectivity_tests

        mock_ssh.return_value = True
        mock_shutdown.return_value = True  # Interrupted
        success, skip_throughput = _step_connectivity_tests(
            "192.168.1.1", "admin", None, "netperf.test"
        )
        assert success is False
        assert skip_throughput is False

    @patch("wanctl.calibrate.measure_baseline_rtt")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_baseline_rtt_interrupt(self, mock_shutdown, mock_measure):
        """Test _step_baseline_rtt returns None on interrupt."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = 12.5
        mock_shutdown.return_value = True  # Interrupted
        result = _step_baseline_rtt("1.1.1.1")
        assert result is None

    @patch("wanctl.calibrate.measure_baseline_rtt")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_baseline_rtt_success(self, mock_shutdown, mock_measure):
        """Test _step_baseline_rtt returns RTT value on success."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = 12.5
        mock_shutdown.return_value = False
        result = _step_baseline_rtt("1.1.1.1")
        assert result == 12.5

    def test_step_raw_throughput_skipped(self):
        """Test _step_raw_throughput returns defaults when skip_throughput=True."""
        from wanctl.calibrate import _step_raw_throughput

        result = _step_raw_throughput(
            "netperf.test", "1.1.1.1", 10.0, skip_throughput=True
        )
        assert result == (100.0, 20.0, 0.0, 0.0)

    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.measure_throughput_upload")
    @patch("wanctl.calibrate.is_shutdown_requested")
    @patch("wanctl.calibrate.time.sleep")
    def test_step_raw_throughput_success(self, mock_sleep, mock_shutdown, mock_upload, mock_download):
        """Test _step_raw_throughput returns measured values."""
        from wanctl.calibrate import _step_raw_throughput

        mock_download.return_value = (500.0, 15.0)
        mock_upload.return_value = (50.0, 10.0)
        mock_shutdown.return_value = False

        result = _step_raw_throughput(
            "netperf.test", "1.1.1.1", 10.0, skip_throughput=False
        )
        assert result == (500.0, 50.0, 15.0, 10.0)

    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_raw_throughput_interrupt(self, mock_shutdown, mock_download):
        """Test _step_raw_throughput returns None on interrupt."""
        from wanctl.calibrate import _step_raw_throughput

        mock_download.return_value = (500.0, 15.0)
        mock_shutdown.return_value = True  # Interrupted after download

        result = _step_raw_throughput(
            "netperf.test", "1.1.1.1", 10.0, skip_throughput=False
        )
        assert result is None


# =============================================================================
# TEST RUN CALIBRATION INTEGRATION
# =============================================================================


class TestRunCalibration:
    """Integration tests for run_calibration function."""

    @patch("wanctl.calibrate._step_connectivity_tests")
    @patch("wanctl.calibrate._step_baseline_rtt")
    @patch("wanctl.calibrate._step_raw_throughput")
    @patch("wanctl.calibrate._step_binary_search")
    @patch("wanctl.calibrate._step_display_summary")
    @patch("wanctl.calibrate._step_save_results")
    def test_run_calibration_returns_result(
        self, mock_save, mock_display, mock_binary, mock_raw, mock_rtt, mock_conn
    ):
        """Test run_calibration returns CalibrationResult on success."""
        mock_conn.return_value = (True, False)  # Success, don't skip throughput
        mock_rtt.return_value = 12.5
        mock_raw.return_value = (500.0, 50.0, 15.0, 10.0)
        mock_binary.return_value = (450.0, 45.0, 8.0, 7.0)
        mock_save.return_value = True

        result = run_calibration(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
        )

        assert result is not None
        assert isinstance(result, CalibrationResult)
        assert result.wan_name == "wan1"
        assert result.baseline_rtt_ms == 12.5
        assert result.optimal_download_mbps == 450.0

    @patch("wanctl.calibrate._step_connectivity_tests")
    def test_run_calibration_returns_none_on_connectivity_failure(self, mock_conn):
        """Test run_calibration returns None when connectivity fails."""
        mock_conn.return_value = (False, False)  # Failed

        result = run_calibration(
            wan_name="wan1",
            router_host="192.168.1.1",
        )

        assert result is None

    @patch("wanctl.calibrate._step_connectivity_tests")
    @patch("wanctl.calibrate._step_baseline_rtt")
    def test_run_calibration_returns_none_on_rtt_failure(self, mock_rtt, mock_conn):
        """Test run_calibration returns None when RTT measurement fails."""
        mock_conn.return_value = (True, False)
        mock_rtt.return_value = None  # Failed

        result = run_calibration(
            wan_name="wan1",
            router_host="192.168.1.1",
        )

        assert result is None

    @patch("wanctl.calibrate._step_connectivity_tests")
    @patch("wanctl.calibrate._step_baseline_rtt")
    @patch("wanctl.calibrate._step_raw_throughput")
    def test_run_calibration_returns_none_on_throughput_failure(
        self, mock_raw, mock_rtt, mock_conn
    ):
        """Test run_calibration returns None when throughput measurement fails."""
        mock_conn.return_value = (True, False)
        mock_rtt.return_value = 12.5
        mock_raw.return_value = None  # Failed (interrupt)

        result = run_calibration(
            wan_name="wan1",
            router_host="192.168.1.1",
        )

        assert result is None

    @patch("wanctl.calibrate._step_connectivity_tests")
    @patch("wanctl.calibrate._step_baseline_rtt")
    @patch("wanctl.calibrate._step_raw_throughput")
    @patch("wanctl.calibrate._step_binary_search")
    def test_run_calibration_returns_none_on_binary_search_interrupt(
        self, mock_binary, mock_raw, mock_rtt, mock_conn
    ):
        """Test run_calibration returns None when binary search is interrupted."""
        mock_conn.return_value = (True, False)
        mock_rtt.return_value = 12.5
        mock_raw.return_value = (500.0, 50.0, 15.0, 10.0)
        mock_binary.return_value = None  # Interrupted

        result = run_calibration(
            wan_name="wan1",
            router_host="192.168.1.1",
        )

        assert result is None


# =============================================================================
# TEST MORE STEP HELPERS (For higher coverage)
# =============================================================================


class TestStepBinarySearch:
    """Tests for _step_binary_search helper function."""

    def test_step_binary_search_skipped_by_flag(self):
        """Test _step_binary_search returns skipped values when flag is set."""
        from wanctl.calibrate import _step_binary_search

        result = _step_binary_search(
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            download_queue="DL",
            upload_queue="UL",
            raw_download=500.0,
            raw_upload=50.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            ssh_key=None,
            skip_binary_search=True,  # Skip!
            skip_throughput=False,
            download_bloat_raw=15.0,
            upload_bloat_raw=10.0,
        )

        # Should return 90% of raw values
        assert result == (450.0, 45.0, 15.0, 10.0)

    def test_step_binary_search_skipped_by_throughput_skip(self):
        """Test _step_binary_search returns skipped values when throughput skipped."""
        from wanctl.calibrate import _step_binary_search

        result = _step_binary_search(
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            download_queue="DL",
            upload_queue="UL",
            raw_download=100.0,
            raw_upload=20.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            ssh_key=None,
            skip_binary_search=False,
            skip_throughput=True,  # Skip!
            download_bloat_raw=0.0,
            upload_bloat_raw=0.0,
        )

        # Should return 90% of raw values
        assert result == (90.0, 18.0, 0.0, 0.0)

    @patch("wanctl.calibrate.binary_search_optimal_rate")
    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.is_shutdown_requested")
    @patch("wanctl.calibrate.time.sleep")
    def test_step_binary_search_full_execution(
        self, mock_sleep, mock_shutdown, mock_set_limit, mock_binary_search
    ):
        """Test _step_binary_search executes binary search for both directions."""
        from wanctl.calibrate import _step_binary_search

        mock_shutdown.return_value = False
        mock_set_limit.return_value = True
        # Return different values for download and upload
        mock_binary_search.side_effect = [
            (450.0, 8.0),  # Download result
            (45.0, 7.0),   # Upload result
        ]

        result = _step_binary_search(
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            download_queue="DL",
            upload_queue="UL",
            raw_download=500.0,
            raw_upload=50.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            ssh_key=None,
            skip_binary_search=False,
            skip_throughput=False,
            download_bloat_raw=15.0,
            upload_bloat_raw=10.0,
        )

        assert result == (450.0, 45.0, 8.0, 7.0)
        assert mock_binary_search.call_count == 2

    @patch("wanctl.calibrate.binary_search_optimal_rate")
    @patch("wanctl.calibrate.set_cake_limit")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_binary_search_interrupt_after_download(
        self, mock_shutdown, mock_set_limit, mock_binary_search
    ):
        """Test _step_binary_search returns None when interrupted after download."""
        from wanctl.calibrate import _step_binary_search

        # Interrupted after download binary search completes
        mock_shutdown.return_value = True
        mock_set_limit.return_value = True
        mock_binary_search.return_value = (450.0, 8.0)

        result = _step_binary_search(
            netperf_host="netperf.test",
            ping_host="1.1.1.1",
            router_host="192.168.1.1",
            router_user="admin",
            download_queue="DL",
            upload_queue="UL",
            raw_download=500.0,
            raw_upload=50.0,
            baseline_rtt=10.0,
            target_bloat=10.0,
            ssh_key=None,
            skip_binary_search=False,
            skip_throughput=False,
            download_bloat_raw=15.0,
            upload_bloat_raw=10.0,
        )

        assert result is None


class TestStepDisplaySummary:
    """Tests for _step_display_summary helper function."""

    def test_step_display_summary_executes(self, capsys):
        """Test _step_display_summary prints summary."""
        from wanctl.calibrate import _step_display_summary

        result = CalibrationResult(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=12.5,
            raw_download_mbps=500.0,
            raw_upload_mbps=50.0,
            optimal_download_mbps=450.0,
            optimal_upload_mbps=45.0,
            download_bloat_ms=8.5,
            upload_bloat_ms=7.2,
            floor_download_mbps=90.0,
            floor_upload_mbps=9.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        _step_display_summary(result)

        captured = capsys.readouterr()
        assert "12.5" in captured.out  # Baseline RTT
        assert "500.0" in captured.out  # Raw download
        assert "450.0" in captured.out  # Optimal download


class TestStepSaveResults:
    """Tests for _step_save_results helper function."""

    def test_step_save_results_creates_files(self, tmp_path):
        """Test _step_save_results creates config and JSON files."""
        from wanctl.calibrate import _step_save_results

        result = CalibrationResult(
            wan_name="wan1",
            router_host="192.168.1.1",
            router_user="admin",
            baseline_rtt_ms=12.5,
            raw_download_mbps=500.0,
            raw_upload_mbps=50.0,
            optimal_download_mbps=450.0,
            optimal_upload_mbps=45.0,
            download_bloat_ms=8.5,
            upload_bloat_ms=7.2,
            floor_download_mbps=90.0,
            floor_upload_mbps=9.0,
            timestamp="2026-01-25T10:00:00",
            target_bloat_ms=10.0,
        )

        success = _step_save_results(result, str(tmp_path))

        assert success is True
        assert (tmp_path / "wan1.yaml").exists()
        assert (tmp_path / "wan1_calibration.json").exists()

    def test_step_save_results_json_content(self, tmp_path):
        """Test _step_save_results writes correct JSON content."""
        import json

        from wanctl.calibrate import _step_save_results

        result = CalibrationResult(
            wan_name="test",
            router_host="host",
            router_user="user",
            baseline_rtt_ms=10.0,
            raw_download_mbps=100.0,
            raw_upload_mbps=10.0,
            optimal_download_mbps=90.0,
            optimal_upload_mbps=9.0,
            download_bloat_ms=5.0,
            upload_bloat_ms=4.0,
            floor_download_mbps=18.0,
            floor_upload_mbps=1.8,
            timestamp="ts",
            target_bloat_ms=10.0,
        )

        _step_save_results(result, str(tmp_path))

        with open(tmp_path / "test_calibration.json") as f:
            data = json.load(f)

        assert data["wan_name"] == "test"
        assert data["baseline_rtt_ms"] == 10.0


class TestBaselineRttConnectionDetection:
    """Tests for connection type detection based on baseline RTT."""

    @patch("wanctl.calibrate.measure_baseline_rtt")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_baseline_rtt_fiber_detection(self, mock_shutdown, mock_measure, capsys):
        """Test _step_baseline_rtt detects fiber connection (low RTT)."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = 8.0  # < 15ms = fiber
        mock_shutdown.return_value = False

        result = _step_baseline_rtt("1.1.1.1")

        assert result == 8.0
        captured = capsys.readouterr()
        assert "fiber" in captured.out.lower()

    @patch("wanctl.calibrate.measure_baseline_rtt")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_baseline_rtt_cable_detection(self, mock_shutdown, mock_measure, capsys):
        """Test _step_baseline_rtt detects cable connection (medium RTT)."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = 25.0  # 15-35ms = cable
        mock_shutdown.return_value = False

        result = _step_baseline_rtt("1.1.1.1")

        assert result == 25.0
        captured = capsys.readouterr()
        assert "cable" in captured.out.lower()

    @patch("wanctl.calibrate.measure_baseline_rtt")
    @patch("wanctl.calibrate.is_shutdown_requested")
    def test_step_baseline_rtt_dsl_detection(self, mock_shutdown, mock_measure, capsys):
        """Test _step_baseline_rtt detects DSL connection (high RTT)."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = 45.0  # >= 35ms = DSL
        mock_shutdown.return_value = False

        result = _step_baseline_rtt("1.1.1.1")

        assert result == 45.0
        captured = capsys.readouterr()
        assert "dsl" in captured.out.lower()

    @patch("wanctl.calibrate.measure_baseline_rtt")
    def test_step_baseline_rtt_failure(self, mock_measure):
        """Test _step_baseline_rtt returns None on measurement failure."""
        from wanctl.calibrate import _step_baseline_rtt

        mock_measure.return_value = None

        result = _step_baseline_rtt("1.1.1.1")

        assert result is None


class TestRawThroughputInterruptPaths:
    """Tests for raw throughput interrupt paths."""

    @patch("wanctl.calibrate.measure_throughput_download")
    @patch("wanctl.calibrate.measure_throughput_upload")
    @patch("wanctl.calibrate.is_shutdown_requested")
    @patch("wanctl.calibrate.time.sleep")
    def test_step_raw_throughput_interrupt_after_upload(
        self, mock_sleep, mock_shutdown, mock_upload, mock_download
    ):
        """Test _step_raw_throughput returns None when interrupted after upload."""
        from wanctl.calibrate import _step_raw_throughput

        mock_download.return_value = (500.0, 15.0)
        mock_upload.return_value = (50.0, 10.0)
        # First call returns False (after download), second call returns True (after upload)
        mock_shutdown.side_effect = [False, True]

        result = _step_raw_throughput(
            "netperf.test", "1.1.1.1", 10.0, skip_throughput=False
        )

        assert result is None


class TestUploadThroughputFallbackPattern:
    """Test upload throughput fallback pattern parsing."""

    @patch("wanctl.calibrate.subprocess.Popen")
    @patch("wanctl.calibrate.subprocess.run")
    @patch("wanctl.calibrate.time.sleep")
    def test_measure_throughput_upload_fallback_pattern(self, mock_sleep, mock_run, mock_popen):
        """Test upload throughput parses fallback Mbps pattern."""
        # Mock netperf process with alternative output format
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Throughput: 98.76 Mbps", "")
        mock_popen.return_value = mock_proc

        # Mock ping result
        mock_run.return_value = MagicMock(
            returncode=0, stdout=PING_OUTPUT_SUCCESS, stderr=""
        )

        throughput, bloat = measure_throughput_upload(
            "netperf.bufferbloat.net", "1.1.1.1", baseline_rtt=10.0
        )

        assert throughput == pytest.approx(98.76, rel=0.01)

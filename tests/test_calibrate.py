"""Unit tests for wanctl.calibrate CLI tool."""

import argparse
from datetime import datetime
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from wanctl.calibrate import (
    CalibrationResult,
    binary_search_optimal_rate,
    generate_config,
    main,
    measure_baseline_rtt,
    measure_throughput_download,
    measure_throughput_upload,
    run_calibration,
    set_cake_limit,
    test_netperf_server,
    test_ssh_connectivity,
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

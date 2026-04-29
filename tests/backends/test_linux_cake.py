"""Tests for LinuxCakeBackend implementation.

BACK-01, BACK-02, BACK-03, BACK-04: Linux CAKE qdisc backend tests.

Coverage targets:
- LinuxCakeBackend constructor and from_config: 100%
- _run_tc helper with all error paths: 100%
- set_bandwidth with bps-to-kbit conversion: 100%
- get_bandwidth with JSON parsing: 100%
- get_queue_stats base 5 + extended 4 + per-tin parsing: 100%
- Mangle rule no-op stubs: 100%
- test_connection tc binary and CAKE presence: 100%
- initialize_cake tc qdisc replace: 100%
- validate_cake readback verification: 100%
"""

import json
import logging
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from wanctl.backends.base import RouterBackend
from wanctl.backends.linux_cake import LinuxCakeBackend

# =============================================================================
# Test data: realistic tc -j -s qdisc show output
# =============================================================================

SAMPLE_CAKE_JSON = json.dumps(
    [
        {
            "kind": "cake",
            "handle": "8001:",
            "parent": "ffff:fff1",
            "bytes": 123456789,
            "packets": 987654,
            "drops": 42,
            "overlimits": 100,
            "requeues": 0,
            "backlog": 1500,
            "qlen": 3,
            "memory_used": 2097152,
            "memory_limit": 33554432,
            "capacity_estimate": 500000000,
            "options": {
                "bandwidth": 500000000,
                "diffserv": "diffserv4",
                "overhead": 18,
                "rtt": 100000,
                "split_gso": True,
                "nat": False,
                "wash": False,
                "ingress": True,
                "ack-filter": "ack-filter",
                "memlimit": 33554432,
            },
            "tins": [
                {  # Bulk (index 0)
                    "threshold_rate": 125000000,
                    "sent_bytes": 10000,
                    "sent_packets": 100,
                    "drops": 2,
                    "ecn_mark": 1,
                    "ack_drops": 0,
                    "backlog_bytes": 0,
                    "peak_delay_us": 5000,
                    "avg_delay_us": 2000,
                    "base_delay_us": 500,
                    "sparse_flows": 3,
                    "bulk_flows": 1,
                    "unresponsive_flows": 0,
                },
                {  # BestEffort (index 1)
                    "threshold_rate": 250000000,
                    "sent_bytes": 50000,
                    "sent_packets": 500,
                    "drops": 5,
                    "ecn_mark": 3,
                    "ack_drops": 0,
                    "backlog_bytes": 500,
                    "peak_delay_us": 3000,
                    "avg_delay_us": 1000,
                    "base_delay_us": 200,
                    "sparse_flows": 10,
                    "bulk_flows": 2,
                    "unresponsive_flows": 0,
                },
                {  # Video (index 2)
                    "threshold_rate": 375000000,
                    "sent_bytes": 80000,
                    "sent_packets": 300,
                    "drops": 0,
                    "ecn_mark": 0,
                    "ack_drops": 0,
                    "backlog_bytes": 1000,
                    "peak_delay_us": 1000,
                    "avg_delay_us": 500,
                    "base_delay_us": 100,
                    "sparse_flows": 5,
                    "bulk_flows": 0,
                    "unresponsive_flows": 0,
                },
                {  # Voice (index 3)
                    "threshold_rate": 500000000,
                    "sent_bytes": 5000,
                    "sent_packets": 50,
                    "drops": 0,
                    "ecn_mark": 0,
                    "ack_drops": 0,
                    "backlog_bytes": 0,
                    "peak_delay_us": 200,
                    "avg_delay_us": 100,
                    "base_delay_us": 50,
                    "sparse_flows": 2,
                    "bulk_flows": 0,
                    "unresponsive_flows": 0,
                },
            ],
        }
    ]
)

SAMPLE_CAKE_NOSTAT_JSON = json.dumps(
    [
        {
            "kind": "cake",
            "options": {
                "bandwidth": 500000000,
                "diffserv": "diffserv4",
                "overhead": 18,
                "rtt": 100000,
                "split_gso": True,
            },
        }
    ]
)

SAMPLE_NON_CAKE_JSON = json.dumps([{"kind": "fq_codel", "handle": "0:"}])

SAMPLE_CAKE_EMPTY_TINS_JSON = json.dumps(
    [
        {
            "kind": "cake",
            "bytes": 0,
            "packets": 0,
            "drops": 0,
            "backlog": 0,
            "qlen": 0,
            "memory_used": 0,
            "memory_limit": 0,
            "capacity_estimate": 0,
            "options": {"bandwidth": 100000000},
            "tins": [],
        }
    ]
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def backend(mock_logger):
    """Create LinuxCakeBackend with mock logger."""
    return LinuxCakeBackend(interface="eth0", logger=mock_logger)


# =============================================================================
# TestLinuxCakeBackendInit
# =============================================================================


class TestLinuxCakeBackendInit:
    """Constructor and from_config tests."""

    def test_init_stores_interface(self, mock_logger):
        b = LinuxCakeBackend(interface="eth0", logger=mock_logger)
        assert b.interface == "eth0"

    def test_init_default_timeout(self, mock_logger):
        b = LinuxCakeBackend(interface="eth0", logger=mock_logger)
        assert b.tc_timeout == 5.0

    def test_init_custom_timeout(self, mock_logger):
        b = LinuxCakeBackend(interface="eth0", logger=mock_logger, tc_timeout=3.0)
        assert b.tc_timeout == 3.0

    def test_init_logger_provided(self, mock_logger):
        b = LinuxCakeBackend(interface="eth0", logger=mock_logger)
        assert b.logger is mock_logger

    def test_init_logger_default(self):
        b = LinuxCakeBackend(interface="eth0")
        assert b.logger is not None

    def test_is_subclass_of_router_backend(self):
        assert issubclass(LinuxCakeBackend, RouterBackend)

    def test_from_config_download(self):
        config = MagicMock()
        config.data = {
            "cake_params": {
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
            "timeouts": {"tc_command": 3.0},
        }
        b = LinuxCakeBackend.from_config(config, direction="download")
        assert b.interface == "enp9s0"
        assert b.tc_timeout == 3.0

    def test_from_config_upload(self):
        config = MagicMock()
        config.data = {
            "cake_params": {
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        }
        b = LinuxCakeBackend.from_config(config, direction="upload")
        assert b.interface == "enp8s0"

    def test_from_config_default_direction(self):
        config = MagicMock()
        config.data = {
            "cake_params": {
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        }
        b = LinuxCakeBackend.from_config(config)
        assert b.interface == "enp9s0"  # default is download

    def test_from_config_missing_interface_raises(self):
        config = MagicMock()
        config.data = {"cake_params": {"upload_interface": "enp8s0"}}
        with pytest.raises(ValueError, match="download_interface"):
            LinuxCakeBackend.from_config(config, direction="download")

    def test_from_config_default_timeout(self):
        config = MagicMock()
        config.data = {"cake_params": {"download_interface": "enp9s0"}}
        b = LinuxCakeBackend.from_config(config)
        assert b.tc_timeout == 5.0


# =============================================================================
# TestRunTc
# =============================================================================


class TestRunTc:
    """_run_tc helper tests."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_run_tc_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["tc", "qdisc", "show"], returncode=0, stdout="ok", stderr=""
        )
        rc, out, err = backend._run_tc(["qdisc", "show"])
        assert rc == 0
        assert out == "ok"
        assert err == ""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_run_tc_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["tc"], returncode=1, stdout="", stderr="error msg"
        )
        rc, out, err = backend._run_tc(["qdisc", "show"])
        assert rc == 1
        assert err == "error msg"

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_run_tc_timeout(self, mock_run, backend):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tc", timeout=5)
        rc, out, err = backend._run_tc(["qdisc", "show"])
        assert rc == -1
        assert err == "timeout"

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_run_tc_file_not_found(self, mock_run, backend):
        mock_run.side_effect = FileNotFoundError()
        rc, out, err = backend._run_tc(["qdisc", "show"])
        assert rc == -1
        assert err == "tc not found"

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_run_tc_builds_correct_command(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend._run_tc(["qdisc", "show", "dev", "eth0"])
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["tc", "qdisc", "show", "dev", "eth0"]


# =============================================================================
# TestSetBandwidth (BACK-01)
# =============================================================================


class TestSetBandwidth:
    """set_bandwidth tests -- BACK-01."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = backend.set_bandwidth("ignored", 500_000_000)
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "bandwidth" in cmd
        assert "500000kbit" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_converts_bps_to_kbit(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.set_bandwidth("q", 500_000_000)
        cmd = mock_run.call_args[0][0]
        assert "500000kbit" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        result = backend.set_bandwidth("q", 500_000_000)
        assert result is False

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_ignores_queue_param(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.set_bandwidth("WAN-Download-1", 100_000_000)
        cmd = mock_run.call_args[0][0]
        # Queue name should NOT appear in command, interface should
        assert "WAN-Download-1" not in cmd
        assert "eth0" in cmd


# =============================================================================
# TestGetBandwidth
# =============================================================================


class TestGetBandwidth:
    """get_bandwidth tests."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_bandwidth_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_NOSTAT_JSON, stderr=""
        )
        result = backend.get_bandwidth("q")
        assert result == 500000000

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_bandwidth_no_cake(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_NON_CAKE_JSON, stderr=""
        )
        result = backend.get_bandwidth("q")
        assert result is None

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_bandwidth_tc_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        result = backend.get_bandwidth("q")
        assert result is None

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_bandwidth_invalid_json(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not json", stderr=""
        )
        result = backend.get_bandwidth("q")
        assert result is None


# =============================================================================
# TestGetQueueStats (BACK-02, BACK-04)
# =============================================================================


class TestGetQueueStats:
    """get_queue_stats tests -- BACK-02, BACK-04."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_base_fields(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        assert stats["packets"] == 987654
        assert stats["bytes"] == 123456789
        assert stats["dropped"] == 42
        assert stats["queued_packets"] == 3
        assert stats["queued_bytes"] == 1500

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_extended_fields(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        assert stats["memory_used"] == 2097152
        assert stats["memory_limit"] == 33554432
        assert stats["capacity_estimate"] == 500000000

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_ecn_marked_sum(self, mock_run, backend):
        """ecn_marked is sum of per-tin ecn_mark values: 1+3+0+0=4."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        assert stats["ecn_marked"] == 4

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_tin_count(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        assert len(stats["tins"]) == 4

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_tin_field_mapping(self, mock_run, backend):
        """Verify D-05 field name mapping: tc 'drops' -> 'dropped_packets', 'ecn_mark' -> 'ecn_marked_packets'."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        # Bulk tin (index 0)
        assert stats["tins"][0]["dropped_packets"] == 2
        assert stats["tins"][0]["ecn_marked_packets"] == 1
        # BestEffort tin (index 1)
        assert stats["tins"][1]["dropped_packets"] == 5
        assert stats["tins"][1]["ecn_marked_packets"] == 3

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_tin_all_fields(self, mock_run, backend):
        """Verify all 11 D-05 fields present in per-tin dict."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        expected_fields = {
            "sent_bytes",
            "sent_packets",
            "dropped_packets",
            "ecn_marked_packets",
            "backlog_bytes",
            "peak_delay_us",
            "avg_delay_us",
            "base_delay_us",
            "sparse_flows",
            "bulk_flows",
            "unresponsive_flows",
        }
        assert set(stats["tins"][0].keys()) == expected_fields

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_avg_and_base_delay_round_trip_from_sample_json(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_JSON, stderr=""
        )

        stats = backend.get_queue_stats("q")

        assert stats is not None
        assert stats["tins"][0]["avg_delay_us"] == 2000
        assert stats["tins"][0]["base_delay_us"] == 500
        assert stats["tins"][1]["avg_delay_us"] == 1000
        assert stats["tins"][1]["base_delay_us"] == 200

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        result = backend.get_queue_stats("q")
        assert result is None

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_no_cake(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_NON_CAKE_JSON, stderr=""
        )
        result = backend.get_queue_stats("q")
        assert result is None

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_get_queue_stats_empty_tins(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_EMPTY_TINS_JSON, stderr=""
        )
        stats = backend.get_queue_stats("q")
        assert stats is not None
        assert stats["tins"] == []
        assert stats["ecn_marked"] == 0


# =============================================================================
# TestMangleRuleStubs (D-02)
# =============================================================================


class TestMangleRuleStubs:
    """Mangle rule no-op stub tests -- D-02."""

    def test_enable_rule_returns_true(self, backend):
        assert backend.enable_rule("any comment") is True

    def test_disable_rule_returns_true(self, backend):
        assert backend.disable_rule("any comment") is True

    def test_is_rule_enabled_returns_none(self, backend):
        assert backend.is_rule_enabled("any comment") is None


# =============================================================================
# TestTestConnection (D-10)
# =============================================================================


class TestTestConnection:
    """test_connection tests -- D-10."""

    @patch("wanctl.backends.linux_cake.shutil.which", return_value="/usr/sbin/tc")
    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_connection_success(self, mock_run, mock_which, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_NOSTAT_JSON, stderr=""
        )
        assert backend.test_connection() is True

    @patch("wanctl.backends.linux_cake.shutil.which", return_value=None)
    def test_connection_no_tc_binary(self, mock_which, backend):
        assert backend.test_connection() is False

    @patch("wanctl.backends.linux_cake.shutil.which", return_value="/usr/sbin/tc")
    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_connection_tc_error(self, mock_run, mock_which, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        assert backend.test_connection() is False

    @patch("wanctl.backends.linux_cake.shutil.which", return_value="/usr/sbin/tc")
    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_connection_no_cake_qdisc(self, mock_run, mock_which, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_NON_CAKE_JSON, stderr=""
        )
        assert backend.test_connection() is False


# =============================================================================
# TestInitializeCake (BACK-03, D-06)
# =============================================================================


class TestInitializeCake:
    """initialize_cake tests -- BACK-03, D-06."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = backend.initialize_cake({"bandwidth": "500000kbit"})
        assert result is True
        assert backend._last_bandwidth_bps == 500_000_000

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        result = backend.initialize_cake({"bandwidth": "500000kbit"})
        assert result is False
        assert backend._last_bandwidth_bps is None


class TestSetBandwidthCaching:
    """set_bandwidth no-op skip tests."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_skips_noop_after_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        assert backend.set_bandwidth("", 500_000_000) is True
        assert backend.set_bandwidth("", 500_000_000) is True

        assert mock_run.call_count == 1

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_updates_cache_on_success(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        assert backend.set_bandwidth("", 500_000_000) is True
        assert backend._last_bandwidth_bps == 500_000_000

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_set_bandwidth_skips_same_kbit_rate(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        assert backend.set_bandwidth("", 500_000_100) is True
        assert backend.set_bandwidth("", 500_000_900) is True

        assert mock_run.call_count == 1
        assert backend._last_bandwidth_bps == 500_000_000

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_bandwidth_param(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"bandwidth": "500000kbit"})
        cmd = mock_run.call_args[0][0]
        assert "bandwidth" in cmd
        assert "500000kbit" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_diffserv_param(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"diffserv": "diffserv4"})
        cmd = mock_run.call_args[0][0]
        assert "diffserv4" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_boolean_flags(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake(
            {
                "split-gso": True,
                "ingress": True,
                "ecn": True,
            }
        )
        cmd = mock_run.call_args[0][0]
        assert "split-gso" in cmd
        assert "ingress" in cmd
        # ecn excluded -- not supported by iproute2-6.15.0, CAKE default anyway
        assert "ecn" not in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_uses_replace(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"bandwidth": "100000kbit"})
        cmd = mock_run.call_args[0][0]
        assert "replace" in cmd
        assert "add" not in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_overhead_keyword_standalone(self, mock_run, backend):
        """overhead_keyword produces standalone token, not key-value pair (D-09)."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"overhead_keyword": "docsis"})
        cmd = mock_run.call_args[0][0]
        assert "docsis" in cmd
        # Must NOT produce "overhead docsis" as consecutive elements
        for i, token in enumerate(cmd[:-1]):
            if token == "overhead":
                assert cmd[i + 1] != "docsis", "overhead_keyword must be standalone, not key-value"

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_overhead_keyword_bridged_ptm(self, mock_run, backend):
        """bridged-ptm keyword expands to ptm + overhead 22."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"overhead_keyword": "bridged-ptm"})
        cmd = mock_run.call_args[0][0]
        assert "ptm" in cmd
        assert "overhead" in cmd
        assert "22" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_overhead_keyword_priority(self, mock_run, backend):
        """overhead_keyword takes priority over numeric overhead when both present."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"overhead_keyword": "docsis", "overhead": 99})
        cmd = mock_run.call_args[0][0]
        assert "docsis" in cmd
        assert "99" not in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_numeric_overhead_fallback(self, mock_run, backend):
        """Numeric overhead still works when overhead_keyword absent (backward compat)."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake({"overhead": 18})
        cmd = mock_run.call_args[0][0]
        assert "overhead" in cmd
        assert "18" in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_full_spectrum_upload(self, mock_run, backend):
        """Full Spectrum upload param set from builder produces correct tc command."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake(
            {
                "diffserv": "diffserv4",
                "split-gso": True,
                "ack-filter": True,
                "ingress": False,
                "ecn": False,
                "overhead_keyword": "docsis",
                "memlimit": "32mb",
                "rtt": "100ms",
                "bandwidth": "500000kbit",
            }
        )
        cmd = mock_run.call_args[0][0]
        # All expected tokens present
        assert "bandwidth" in cmd
        assert "500000kbit" in cmd
        assert "diffserv4" in cmd
        assert "docsis" in cmd
        assert "memlimit" in cmd
        assert "32mb" in cmd
        assert "rtt" in cmd
        assert "100ms" in cmd
        assert "split-gso" in cmd
        assert "ack-filter" in cmd
        # Falsy flags NOT in cmd
        assert "ingress" not in cmd
        assert "ecn" not in cmd

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_initialize_cake_full_att_download(self, mock_run, backend):
        """Full ATT download param set from builder produces correct tc command."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend.initialize_cake(
            {
                "diffserv": "diffserv4",
                "split-gso": True,
                "ack-filter": False,
                "ingress": True,
                "ecn": True,
                "overhead_keyword": "bridged-ptm",
                "memlimit": "32mb",
                "rtt": "100ms",
                "bandwidth": "300000kbit",
            }
        )
        cmd = mock_run.call_args[0][0]
        # All expected tokens present
        assert "bandwidth" in cmd
        assert "300000kbit" in cmd
        assert "diffserv4" in cmd
        assert "ptm" in cmd
        assert "22" in cmd
        assert "memlimit" in cmd
        assert "32mb" in cmd
        assert "rtt" in cmd
        assert "100ms" in cmd
        assert "split-gso" in cmd
        assert "ingress" in cmd
        # ecn excluded -- not supported by iproute2-6.15.0, CAKE default anyway
        assert "ecn" not in cmd
        # Upload-only flag NOT in cmd
        assert "ack-filter" not in cmd
        assert "no-ack-filter" in cmd


# =============================================================================
# TestCakeParamsIntegration (CAKE-05, CAKE-06, CAKE-10)
# =============================================================================


class TestCakeParamsIntegration:
    """Integration tests: build_cake_params -> initialize_cake pipeline."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_builder_output_accepted_by_initialize_cake(self, mock_run, backend):
        """build_cake_params output feeds directly into initialize_cake (rc=0)."""
        from wanctl.cake_params import build_cake_params

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        params = build_cake_params("upload", {"overhead": "docsis"}, 500000)
        result = backend.initialize_cake(params)
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "docsis" in cmd
        assert "500000kbit" in cmd

    def test_builder_readback_matches_expected(self):
        """build_expected_readback produces correct numeric types for validate_cake."""
        from wanctl.cake_params import build_cake_params, build_expected_readback

        params = build_cake_params("upload", {"overhead": "docsis"}, 500000)
        readback = build_expected_readback(params)
        assert readback["overhead"] == 18
        assert readback["diffserv"] == "diffserv4"
        assert readback["rtt"] == 100_000
        assert readback["memlimit"] == 33_554_432


# =============================================================================
# TestValidateCake (BACK-03, D-07)
# =============================================================================


class TestValidateCake:
    """validate_cake tests -- BACK-03, D-07."""

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_validate_cake_all_match(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_NOSTAT_JSON, stderr=""
        )
        result = backend.validate_cake({"diffserv": "diffserv4", "overhead": 18})
        assert result is True

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_validate_cake_mismatch(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_CAKE_NOSTAT_JSON, stderr=""
        )
        result = backend.validate_cake({"overhead": 22})
        assert result is False

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_validate_cake_no_cake(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=SAMPLE_NON_CAKE_JSON, stderr=""
        )
        result = backend.validate_cake({"diffserv": "diffserv4"})
        assert result is False

    @patch("wanctl.backends.linux_cake.subprocess.run")
    def test_validate_cake_tc_failure(self, mock_run, backend):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        result = backend.validate_cake({"diffserv": "diffserv4"})
        assert result is False

"""Tests for NetlinkCakeBackend implementation.

NLNK-01, NLNK-02, NLNK-03, NLNK-04: Netlink CAKE backend tests.

Coverage targets:
- NetlinkCakeBackend constructor and from_config: 100%
- _get_ipr singleton lifecycle and reconnect: 100%
- set_bandwidth netlink path + bps-to-kbit conversion: 100%
- set_bandwidth fallback on NetlinkError/OSError: 100%
- get_bandwidth netlink read + fallback: 100%
- get_queue_stats netlink per-tin stats parsing: 100%
- get_queue_stats fallback and edge cases: 100%
- initialize_cake param mapping + fallback: 100%
- validate_cake readback + fallback: 100%
- test_connection netlink path + fallback: 100%
- close() resource cleanup: 100%
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from wanctl.backends.linux_cake import LinuxCakeBackend
from wanctl.backends.netlink_cake import NetlinkCakeBackend

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_ipr():
    """Create mock IPRoute instance."""
    ipr = MagicMock()
    ipr.link_lookup.return_value = [42]
    ipr.tc.return_value = None  # success for change/replace
    return ipr


@pytest.fixture
def backend(mock_logger):
    """Create NetlinkCakeBackend with mock logger."""
    return NetlinkCakeBackend(interface="eth0", logger=mock_logger)


# =============================================================================
# TestNetlinkCakeBackendInit
# =============================================================================


class TestNetlinkCakeBackendInit:
    """Constructor and inheritance tests."""

    def test_inherits_linux_cake_backend(self):
        assert issubclass(NetlinkCakeBackend, LinuxCakeBackend)

    def test_init_stores_interface(self, mock_logger):
        b = NetlinkCakeBackend(interface="eth0", logger=mock_logger)
        assert b.interface == "eth0"

    def test_init_ipr_is_none(self, mock_logger):
        b = NetlinkCakeBackend(interface="eth0", logger=mock_logger)
        assert b._ipr is None

    def test_init_ifindex_is_none(self, mock_logger):
        b = NetlinkCakeBackend(interface="eth0", logger=mock_logger)
        assert b._ifindex is None

    def test_init_default_timeout(self, mock_logger):
        b = NetlinkCakeBackend(interface="eth0", logger=mock_logger)
        assert b.tc_timeout == 5.0

    def test_init_custom_timeout(self, mock_logger):
        b = NetlinkCakeBackend(interface="eth0", logger=mock_logger, tc_timeout=3.0)
        assert b.tc_timeout == 3.0


# =============================================================================
# TestIPRouteLifecycle (NLNK-02)
# =============================================================================


class TestIPRouteLifecycle:
    """Singleton IPRoute lifecycle and reconnect tests -- NLNK-02."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_creates_iproute_on_first_call(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        result = backend._get_ipr()
        assert result is mock_instance
        MockIPRoute.assert_called_once_with(groups=0)

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_returns_same_instance_on_subsequent_calls(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        first = backend._get_ipr()
        second = backend._get_ipr()
        assert first is second
        MockIPRoute.assert_called_once()

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_resolves_ifindex(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend._get_ipr()
        assert backend._ifindex == 42
        mock_instance.link_lookup.assert_called_once_with(ifname="eth0")

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_reconnects_when_ipr_is_none(self, MockIPRoute, backend):
        mock_instance1 = MagicMock()
        mock_instance1.link_lookup.return_value = [42]
        mock_instance2 = MagicMock()
        mock_instance2.link_lookup.return_value = [42]
        MockIPRoute.side_effect = [mock_instance1, mock_instance2]

        first = backend._get_ipr()
        backend._ipr = None  # simulate failure reset
        second = backend._get_ipr()
        assert first is not second
        assert MockIPRoute.call_count == 2

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_raises_oserror_when_interface_not_found(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = []
        MockIPRoute.return_value = mock_instance

        with pytest.raises(OSError, match="Interface eth0 not found"):
            backend._get_ipr()

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_ipr_creates_with_groups_zero(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend._get_ipr()
        MockIPRoute.assert_called_once_with(groups=0)

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_close_calls_ipr_close(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend._get_ipr()
        backend.close()
        mock_instance.close.assert_called_once()
        assert backend._ipr is None

    def test_close_when_ipr_is_none(self, backend):
        """close() is safe to call when no IPRoute exists."""
        backend.close()  # should not raise
        assert backend._ipr is None


# =============================================================================
# TestSetBandwidth (NLNK-01)
# =============================================================================


class TestSetBandwidth:
    """set_bandwidth netlink success path tests -- NLNK-01."""

    def test_set_bandwidth_initial_apply_state(self, backend):
        assert backend._last_apply_started_monotonic is None
        assert backend._last_apply_finished_monotonic is None
        assert backend._last_apply_was_kernel_write is False

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_calls_tc_change(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        result = backend.set_bandwidth("", 500_000_000)
        assert result is True
        mock_instance.tc.assert_called_once_with(
            "change", kind="cake", index=42, bandwidth="500000kbit"
        )

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_converts_bps_to_kbit(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.set_bandwidth("q", 100_000_000)
        mock_instance.tc.assert_called_once_with(
            "change", kind="cake", index=42, bandwidth="100000kbit"
        )

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_returns_true_on_success(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        result = backend.set_bandwidth("q", 500_000_000)
        assert result is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_populates_apply_overlap_timestamps_on_success(
        self, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_000) is True
        assert backend._last_apply_started_monotonic is not None
        assert backend._last_apply_finished_monotonic is not None
        assert backend._last_apply_started_monotonic <= backend._last_apply_finished_monotonic
        assert backend._last_apply_was_kernel_write is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_logs_debug_on_success(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.set_bandwidth("q", 500_000_000)
        backend.logger.debug.assert_called()

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_skips_noop_after_success(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_000) is True
        assert backend.set_bandwidth("q", 500_000_000) is True

        mock_instance.tc.assert_called_once_with(
            "change", kind="cake", index=42, bandwidth="500000kbit"
        )

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_populates_apply_overlap_timestamps_on_skip(
        self, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_000) is True
        backend._last_apply_started_monotonic = -1.0
        backend._last_apply_finished_monotonic = -1.0
        backend._last_apply_was_kernel_write = True

        assert backend.set_bandwidth("q", 500_000_000) is True
        assert backend._last_apply_started_monotonic is not None
        assert backend._last_apply_finished_monotonic is not None
        assert backend._last_apply_started_monotonic != -1.0
        assert backend._last_apply_finished_monotonic != -1.0
        assert backend._last_apply_started_monotonic <= backend._last_apply_finished_monotonic
        assert backend._last_apply_was_kernel_write is False

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_skips_same_kbit_rate(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_100) is True
        assert backend.set_bandwidth("q", 500_000_900) is True

        mock_instance.tc.assert_called_once_with(
            "change", kind="cake", index=42, bandwidth="500000kbit"
        )
        assert backend._last_bandwidth_bps == 500_000_000

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_set_bandwidth_kernel_write_flag_transitions_skip_to_success(
        self, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_000) is True
        assert backend._last_apply_was_kernel_write is True

        assert backend.set_bandwidth("q", 500_000_000) is True
        assert backend._last_apply_was_kernel_write is False

        assert backend.set_bandwidth("q", 600_000_000) is True
        assert backend._last_apply_was_kernel_write is True


# =============================================================================
# TestSetBandwidthFallback (NLNK-03)
# =============================================================================


class TestSetBandwidthFallback:
    """set_bandwidth fallback to subprocess on netlink failure -- NLNK-03."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_set_bandwidth_populates_apply_overlap_timestamps_on_fallback(
        self, mock_super_set, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        from pyroute2.netlink.exceptions import NetlinkError

        mock_instance.tc.side_effect = NetlinkError(1, "test")
        MockIPRoute.return_value = mock_instance

        assert backend.set_bandwidth("q", 500_000_000) is True
        mock_super_set.assert_called_once_with("q", 500_000_000)
        assert backend._last_apply_started_monotonic is not None
        assert backend._last_apply_finished_monotonic is not None
        assert backend._last_apply_started_monotonic <= backend._last_apply_finished_monotonic
        assert backend._last_apply_was_kernel_write is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_fallback_on_netlink_error(self, mock_super_set, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # Import the real exception
        from pyroute2.netlink.exceptions import NetlinkError

        mock_instance.tc.side_effect = NetlinkError(22)  # EINVAL
        MockIPRoute.return_value = mock_instance

        result = backend.set_bandwidth("q", 500_000_000)
        assert result is True
        mock_super_set.assert_called_once_with("q", 500_000_000)

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_fallback_on_oserror(self, mock_super_set, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("socket closed")
        MockIPRoute.return_value = mock_instance

        result = backend.set_bandwidth("q", 500_000_000)
        assert result is True
        mock_super_set.assert_called_once_with("q", 500_000_000)

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_fallback_nulls_ipr_for_reconnect(self, mock_super_set, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        backend.set_bandwidth("q", 500_000_000)
        assert backend._ipr is None

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_fallback_logs_warning(self, mock_super_set, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        backend.set_bandwidth("q", 500_000_000)
        backend.logger.warning.assert_called()
        warning_msg = backend.logger.warning.call_args[0][0]
        assert "falling back to subprocess" in warning_msg

    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_fallback_on_get_ipr_oserror(self, mock_super_set, backend):
        """_get_ipr() OSError (interface not found) triggers fallback, not crash."""
        with patch("wanctl.backends.netlink_cake.IPRoute") as MockIPRoute:
            mock_instance = MagicMock()
            mock_instance.link_lookup.return_value = []  # interface not found
            MockIPRoute.return_value = mock_instance

            result = backend.set_bandwidth("q", 500_000_000)
            assert result is True
            mock_super_set.assert_called_once()


# =============================================================================
# TestGetBandwidth (NLNK-01)
# =============================================================================


class TestGetBandwidth:
    """get_bandwidth netlink read and fallback tests -- NLNK-01."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_get_bandwidth_reads_from_netlink(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # Mock tc dump response: msg with nested attrs for CAKE
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: {
            "TCA_KIND": "cake",
            "TCA_OPTIONS": MagicMock(
                get_attr=lambda k: 62500000 if k == "TCA_CAKE_BASE_RATE64" else None
            ),
        }.get(key)
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        result = backend.get_bandwidth("q")
        # 62500000 bytes/sec * 8 = 500000000 bps
        assert result == 500_000_000

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_bandwidth", return_value=500_000_000)
    def test_get_bandwidth_falls_back_on_netlink_failure(
        self, mock_super_get, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("socket error")
        MockIPRoute.return_value = mock_instance

        result = backend.get_bandwidth("q")
        assert result == 500_000_000
        mock_super_get.assert_called_once_with("q")

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_bandwidth", return_value=500_000_000)
    def test_get_bandwidth_fallback_nulls_ipr(self, mock_super_get, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("socket error")
        MockIPRoute.return_value = mock_instance

        backend.get_bandwidth("q")
        assert backend._ipr is None


# =============================================================================
# TestInitializeCake (NLNK-01)
# =============================================================================


class TestInitializeCake:
    """initialize_cake netlink param mapping and fallback tests -- NLNK-01."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_calls_tc_replace(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        result = backend.initialize_cake({"bandwidth": "500000kbit"})
        assert result is True
        call_args = mock_instance.tc.call_args
        assert call_args[0][0] == "replace"
        assert call_args[1]["kind"] == "cake"
        assert call_args[1]["index"] == 42
        assert call_args[1]["bandwidth"] == "500000kbit"
        assert backend._last_bandwidth_bps == 500_000_000

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_diffserv(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"diffserv": "diffserv4"})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("diffserv_mode") == "diffserv4"

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "initialize_cake", return_value=True)
    def test_initialize_cake_docsis_falls_back_to_subprocess(self, mock_super_init, MockIPRoute, backend):
        """overhead_keyword falls back to subprocess tc (pyroute2 can't handle keywords like docsis)."""
        result = backend.initialize_cake({"overhead_keyword": "docsis"})
        assert result is True
        mock_super_init.assert_called_once_with({"overhead_keyword": "docsis"})

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_boolean_flags(self, MockIPRoute, backend):
        """Boolean flags: split-gso, ack-filter, ingress map to pyroute2 kwargs."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({
            "split-gso": True,
            "ack-filter": True,
            "ingress": True,
        })
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("split_gso") is True
        assert call_kwargs.get("ack_filter") is True
        assert call_kwargs.get("ingress") is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_numeric_overhead(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"overhead": 18})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("overhead") == 18

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_mpu(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"mpu": 64})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("mpu") == 64

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_memlimit(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"memlimit": "33554432"})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("memlimit") == 33554432

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_rtt(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"rtt": "100ms"})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("rtt") == 100000  # 100ms -> 100000us

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "initialize_cake", return_value=True)
    def test_initialize_cake_falls_back_on_netlink_failure(
        self, mock_super_init, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        result = backend.initialize_cake({"bandwidth": "500000kbit"})
        assert result is True
        mock_super_init.assert_called_once_with({"bandwidth": "500000kbit"})

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "initialize_cake", return_value=True)
    def test_initialize_cake_fallback_nulls_ipr(
        self, mock_super_init, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"bandwidth": "500000kbit"})
        assert backend._ipr is None


# =============================================================================
# TestValidateCake (NLNK-01)
# =============================================================================


class TestValidateCake:
    """validate_cake netlink readback and fallback tests -- NLNK-01."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_validate_cake_reads_via_netlink(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # Build mock message with options
        mock_options = MagicMock()
        mock_options.get_attr.side_effect = lambda k: {
            "TCA_CAKE_DIFFSERV_MODE": 1,  # netlink returns int enum (diffserv4=1)
            "TCA_CAKE_OVERHEAD": 18,
        }.get(k)
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: {
            "TCA_KIND": "cake",
            "TCA_OPTIONS": mock_options,
        }.get(key)
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        result = backend.validate_cake({"diffserv": "diffserv4", "overhead": 18})
        assert result is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "validate_cake", return_value=True)
    def test_validate_cake_falls_back_on_netlink_failure(
        self, mock_super_validate, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        result = backend.validate_cake({"diffserv": "diffserv4"})
        assert result is True
        mock_super_validate.assert_called_once_with({"diffserv": "diffserv4"})

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "validate_cake", return_value=True)
    def test_validate_cake_fallback_nulls_ipr(
        self, mock_super_validate, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        backend.validate_cake({"diffserv": "diffserv4"})
        assert backend._ipr is None


# =============================================================================
# TestTestConnection (NLNK-01)
# =============================================================================


class TestTestConnection:
    """test_connection netlink path and fallback tests."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_connection_success_via_netlink(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: "cake" if key == "TCA_KIND" else None
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        assert backend.test_connection() is True

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "test_connection", return_value=True)
    def test_connection_falls_back_on_netlink_failure(
        self, mock_super_test, MockIPRoute, backend
    ):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = []  # no interface
        MockIPRoute.return_value = mock_instance

        result = backend.test_connection()
        assert result is True
        mock_super_test.assert_called_once()


# =============================================================================
# TestFromConfig
# =============================================================================


class TestFromConfig:
    """from_config factory method tests."""

    def test_from_config_returns_netlink_backend(self):
        config = MagicMock()
        config.data = {
            "cake_params": {
                "download_interface": "enp9s0",
                "upload_interface": "enp8s0",
            },
            "timeouts": {"tc_command": 3.0},
        }
        b = NetlinkCakeBackend.from_config(config, direction="download")
        assert isinstance(b, NetlinkCakeBackend)
        assert b.interface == "enp9s0"
        assert b.tc_timeout == 3.0

    def test_from_config_upload_direction(self):
        config = MagicMock()
        config.data = {
            "cake_params": {
                "download_interface": "enp9s0",
                "upload_interface": "enp8s0",
            },
        }
        b = NetlinkCakeBackend.from_config(config, direction="upload")
        assert isinstance(b, NetlinkCakeBackend)
        assert b.interface == "enp8s0"

    def test_from_config_missing_interface_raises(self):
        config = MagicMock()
        config.data = {"cake_params": {"upload_interface": "enp8s0"}}
        with pytest.raises(ValueError, match="download_interface"):
            NetlinkCakeBackend.from_config(config, direction="download")

    def test_from_config_default_timeout(self):
        config = MagicMock()
        config.data = {"cake_params": {"download_interface": "enp9s0"}}
        b = NetlinkCakeBackend.from_config(config)
        assert b.tc_timeout == 5.0


# =============================================================================
# TestPyroute2NotAvailable (graceful import failure)
# =============================================================================


class TestPyroute2NotAvailable:
    """Tests for when pyroute2 is not installed."""

    @patch("wanctl.backends.netlink_cake._pyroute2_available", False)
    @patch.object(LinuxCakeBackend, "set_bandwidth", return_value=True)
    def test_set_bandwidth_falls_back_when_pyroute2_unavailable(
        self, mock_super_set, backend
    ):
        result = backend.set_bandwidth("q", 500_000_000)
        assert result is True
        mock_super_set.assert_called_once()

    @patch("wanctl.backends.netlink_cake._pyroute2_available", False)
    @patch.object(LinuxCakeBackend, "get_bandwidth", return_value=500_000_000)
    def test_get_bandwidth_falls_back_when_pyroute2_unavailable(
        self, mock_super_get, backend
    ):
        result = backend.get_bandwidth("q")
        assert result == 500_000_000
        mock_super_get.assert_called_once()


# =============================================================================
# Mock helpers for get_queue_stats netlink response
# =============================================================================

# Per-tin data matching SAMPLE_CAKE_JSON from test_linux_cake_backend.py
_TIN_DATA = [
    {  # Bulk (index 0)
        "TCA_CAKE_TIN_STATS_SENT_BYTES64": 10000,
        "TCA_CAKE_TIN_STATS_SENT_PACKETS": 100,
        "TCA_CAKE_TIN_STATS_DROPPED_PACKETS": 2,
        "TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS": 1,
        "TCA_CAKE_TIN_STATS_BACKLOG_BYTES": 0,
        "TCA_CAKE_TIN_STATS_PEAK_DELAY_US": 5000,
        "TCA_CAKE_TIN_STATS_AVG_DELAY_US": 2000,
        "TCA_CAKE_TIN_STATS_BASE_DELAY_US": 500,
        "TCA_CAKE_TIN_STATS_SPARSE_FLOWS": 3,
        "TCA_CAKE_TIN_STATS_BULK_FLOWS": 1,
        "TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS": 0,
    },
    {  # BestEffort (index 1)
        "TCA_CAKE_TIN_STATS_SENT_BYTES64": 50000,
        "TCA_CAKE_TIN_STATS_SENT_PACKETS": 500,
        "TCA_CAKE_TIN_STATS_DROPPED_PACKETS": 5,
        "TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS": 3,
        "TCA_CAKE_TIN_STATS_BACKLOG_BYTES": 500,
        "TCA_CAKE_TIN_STATS_PEAK_DELAY_US": 3000,
        "TCA_CAKE_TIN_STATS_AVG_DELAY_US": 1000,
        "TCA_CAKE_TIN_STATS_BASE_DELAY_US": 200,
        "TCA_CAKE_TIN_STATS_SPARSE_FLOWS": 10,
        "TCA_CAKE_TIN_STATS_BULK_FLOWS": 2,
        "TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS": 0,
    },
    {  # Video (index 2)
        "TCA_CAKE_TIN_STATS_SENT_BYTES64": 80000,
        "TCA_CAKE_TIN_STATS_SENT_PACKETS": 300,
        "TCA_CAKE_TIN_STATS_DROPPED_PACKETS": 0,
        "TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS": 0,
        "TCA_CAKE_TIN_STATS_BACKLOG_BYTES": 1000,
        "TCA_CAKE_TIN_STATS_PEAK_DELAY_US": 1000,
        "TCA_CAKE_TIN_STATS_AVG_DELAY_US": 500,
        "TCA_CAKE_TIN_STATS_BASE_DELAY_US": 100,
        "TCA_CAKE_TIN_STATS_SPARSE_FLOWS": 5,
        "TCA_CAKE_TIN_STATS_BULK_FLOWS": 0,
        "TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS": 0,
    },
    {  # Voice (index 3)
        "TCA_CAKE_TIN_STATS_SENT_BYTES64": 5000,
        "TCA_CAKE_TIN_STATS_SENT_PACKETS": 50,
        "TCA_CAKE_TIN_STATS_DROPPED_PACKETS": 0,
        "TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS": 0,
        "TCA_CAKE_TIN_STATS_BACKLOG_BYTES": 0,
        "TCA_CAKE_TIN_STATS_PEAK_DELAY_US": 200,
        "TCA_CAKE_TIN_STATS_AVG_DELAY_US": 100,
        "TCA_CAKE_TIN_STATS_BASE_DELAY_US": 50,
        "TCA_CAKE_TIN_STATS_SPARSE_FLOWS": 2,
        "TCA_CAKE_TIN_STATS_BULK_FLOWS": 0,
        "TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS": 0,
    },
]


def _make_mock_tin(tin_data: dict) -> MagicMock:
    """Build a mock pyroute2 tin stats nla object."""
    tin = MagicMock()
    tin.get_attr.side_effect = lambda key: tin_data.get(key)
    return tin


def _make_mock_tins_container(tin_data_list: list[dict]) -> MagicMock:
    """Build a mock TCA_CAKE_STATS_TIN_STATS container."""
    tins_by_index = {}
    for i, td in enumerate(tin_data_list, start=1):  # pyroute2 tins are 1-indexed
        tins_by_index[f"TCA_CAKE_TIN_STATS_{i}"] = _make_mock_tin(td)
    container = MagicMock()
    container.get_attr.side_effect = lambda key: tins_by_index.get(key)
    return container


def _make_mock_stats_app(
    memory_used: int = 2097152,
    memory_limit: int = 33554432,
    capacity_estimate: int = 500000000,
    tin_data_list: list[dict] | None = None,
) -> MagicMock:
    """Build a mock TCA_STATS_APP nla object."""
    if tin_data_list is None:
        tin_data_list = _TIN_DATA
    tins_container = _make_mock_tins_container(tin_data_list) if tin_data_list else None
    app_attrs = {
        "TCA_CAKE_STATS_MEMORY_USED": memory_used,
        "TCA_CAKE_STATS_MEMORY_LIMIT": memory_limit,
        "TCA_CAKE_STATS_CAPACITY_ESTIMATE64": capacity_estimate,
        "TCA_CAKE_STATS_TIN_STATS": tins_container,
    }
    app = MagicMock()
    app.get_attr.side_effect = lambda key: app_attrs.get(key)
    return app


def _make_mock_stats2(
    packets: int = 987654,
    bytes_val: int = 123456789,
    drops: int = 42,
    qlen: int = 3,
    backlog: int = 1500,
    app: MagicMock | None = None,
) -> MagicMock:
    """Build a mock TCA_STATS2 nla object."""
    basic = {"bytes": bytes_val, "packets": packets}
    queue = {"drops": drops, "qlen": qlen, "backlog": backlog}
    if app is None:
        app = _make_mock_stats_app()
    stats2_attrs = {
        "TCA_STATS_BASIC": basic,
        "TCA_STATS_QUEUE": queue,
        "TCA_STATS_APP": app,
    }
    stats2 = MagicMock()
    stats2.get_attr.side_effect = lambda key: stats2_attrs.get(key)
    return stats2


def _make_mock_cake_dump_msg(stats2: MagicMock | None = None) -> MagicMock:
    """Build mock pyroute2 tcmsg for CAKE stats matching SAMPLE_CAKE_JSON values."""
    if stats2 is None:
        stats2 = _make_mock_stats2()
    msg_attrs = {
        "TCA_KIND": "cake",
        "TCA_STATS2": stats2,
    }
    msg = MagicMock()
    msg.get_attr.side_effect = lambda key: msg_attrs.get(key)
    return msg


# =============================================================================
# TestGetQueueStats (NLNK-04)
# =============================================================================


class TestGetQueueStats:
    """get_queue_stats netlink per-tin stats parsing tests -- NLNK-04."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_returns_dict_with_all_base_fields(self, MockIPRoute, backend):
        """get_queue_stats returns dict with packets, bytes, dropped, queued_packets, queued_bytes."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert result["packets"] == 987654
        assert result["bytes"] == 123456789
        assert result["dropped"] == 42
        assert result["queued_packets"] == 3
        assert result["queued_bytes"] == 1500

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_returns_extended_fields(self, MockIPRoute, backend):
        """get_queue_stats returns memory_used, memory_limit, capacity_estimate."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert result["memory_used"] == 2097152
        assert result["memory_limit"] == 33554432
        assert result["capacity_estimate"] == 500000000

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_returns_tins_list_with_4_entries(self, MockIPRoute, backend):
        """get_queue_stats returns tins list with 4 entries (diffserv4)."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert len(result["tins"]) == 4

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_per_tin_field_mapping(self, MockIPRoute, backend):
        """Per-tin fields are mapped correctly from TCA attributes."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        # Check Bulk tin (index 0)
        tin0 = result["tins"][0]
        assert tin0["sent_bytes"] == 10000
        assert tin0["sent_packets"] == 100
        assert tin0["dropped_packets"] == 2
        assert tin0["ecn_marked_packets"] == 1
        assert tin0["backlog_bytes"] == 0
        assert tin0["peak_delay_us"] == 5000
        assert tin0["avg_delay_us"] == 2000
        assert tin0["base_delay_us"] == 500
        assert tin0["sparse_flows"] == 3
        assert tin0["bulk_flows"] == 1
        assert tin0["unresponsive_flows"] == 0

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_per_tin_has_11_fields_each(self, MockIPRoute, backend):
        """Each tin dict has exactly 11 fields."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        expected_keys = {
            "sent_bytes", "sent_packets", "dropped_packets",
            "ecn_marked_packets", "backlog_bytes", "peak_delay_us",
            "avg_delay_us", "base_delay_us", "sparse_flows",
            "bulk_flows", "unresponsive_flows",
        }
        for tin in result["tins"]:
            assert set(tin.keys()) == expected_keys

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_avg_and_base_delay_round_trip_from_tca_attrs(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")

        assert result is not None
        assert result["tins"][0]["avg_delay_us"] == 2000
        assert result["tins"][0]["base_delay_us"] == 500

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_ecn_marked_equals_sum_of_tin_ecn(self, MockIPRoute, backend):
        """ecn_marked is sum of ecn_marked_packets across all tins (1+3+0+0=4)."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert result["ecn_marked"] == 4
        # Verify it equals the sum
        total = sum(t["ecn_marked_packets"] for t in result["tins"])
        assert result["ecn_marked"] == total

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_queue_stats", return_value={"packets": 1})
    def test_fallback_on_netlink_error(self, mock_super_stats, MockIPRoute, backend):
        """get_queue_stats falls back to super().get_queue_stats() on NetlinkError."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        from pyroute2.netlink.exceptions import NetlinkError

        mock_instance.tc.side_effect = NetlinkError(22)
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result == {"packets": 1}
        mock_super_stats.assert_called_once_with("q")

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_queue_stats", return_value={"packets": 1})
    def test_fallback_on_oserror(self, mock_super_stats, MockIPRoute, backend):
        """get_queue_stats falls back on OSError (socket death)."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("socket died")
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result == {"packets": 1}
        mock_super_stats.assert_called_once_with("q")

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_queue_stats", return_value={"packets": 1})
    def test_fallback_nulls_ipr(self, mock_super_stats, MockIPRoute, backend):
        """Fallback nulls _ipr for reconnect on next call."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.side_effect = OSError("broken")
        MockIPRoute.return_value = mock_instance

        backend.get_queue_stats("q")
        assert backend._ipr is None

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_no_cake_qdisc_returns_none(self, MockIPRoute, backend):
        """get_queue_stats returns None when no CAKE qdisc found."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # Return a non-CAKE message
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: {
            "TCA_KIND": "fq_codel",
        }.get(key)
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is None

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_empty_tins_returns_empty_list(self, MockIPRoute, backend):
        """get_queue_stats handles empty tins list gracefully (0 tins -> empty list)."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        app = _make_mock_stats_app(tin_data_list=[])
        stats2 = _make_mock_stats2(app=app)
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg(stats2=stats2)]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert result["tins"] == []
        assert result["ecn_marked"] == 0

    @patch("wanctl.backends.netlink_cake.IPRoute")
    @patch.object(LinuxCakeBackend, "get_queue_stats", return_value={"packets": 1})
    def test_missing_stats2_fallback(self, mock_super_stats, MockIPRoute, backend):
        """get_queue_stats falls back when TCA_STATS2 is missing."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # CAKE message with no TCA_STATS2
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: {
            "TCA_KIND": "cake",
            "TCA_STATS2": None,
        }.get(key)
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result == {"packets": 1}
        mock_super_stats.assert_called_once_with("q")

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_missing_app_returns_zero_extended_fields(self, MockIPRoute, backend):
        """get_queue_stats returns 0 for extended fields when TCA_STATS_APP is None."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        # Stats2 with no app
        stats2_attrs = {
            "TCA_STATS_BASIC": {"bytes": 100, "packets": 10},
            "TCA_STATS_QUEUE": {"drops": 0, "qlen": 0, "backlog": 0},
            "TCA_STATS_APP": None,
        }
        mock_stats2 = MagicMock()
        mock_stats2.get_attr.side_effect = lambda key: stats2_attrs.get(key)
        mock_msg = MagicMock()
        mock_msg.get_attr.side_effect = lambda key: {
            "TCA_KIND": "cake",
            "TCA_STATS2": mock_stats2,
        }.get(key)
        mock_instance.tc.return_value = [mock_msg]
        MockIPRoute.return_value = mock_instance

        result = backend.get_queue_stats("q")
        assert result is not None
        assert result["memory_used"] == 0
        assert result["memory_limit"] == 0
        assert result["capacity_estimate"] == 0
        assert result["tins"] == []
        assert result["ecn_marked"] == 0


# =============================================================================
# TestStatsContractParity (NLNK-04)
# =============================================================================

# SAMPLE_CAKE_JSON from test_linux_cake_backend.py (same values)
_SAMPLE_CAKE_JSON = json.dumps(
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
            "options": {"bandwidth": 500000000},
            "tins": [
                {
                    "sent_bytes": 10000,
                    "sent_packets": 100,
                    "drops": 2,
                    "ecn_mark": 1,
                    "backlog_bytes": 0,
                    "peak_delay_us": 5000,
                    "avg_delay_us": 2000,
                    "base_delay_us": 500,
                    "sparse_flows": 3,
                    "bulk_flows": 1,
                    "unresponsive_flows": 0,
                },
                {
                    "sent_bytes": 50000,
                    "sent_packets": 500,
                    "drops": 5,
                    "ecn_mark": 3,
                    "backlog_bytes": 500,
                    "peak_delay_us": 3000,
                    "avg_delay_us": 1000,
                    "base_delay_us": 200,
                    "sparse_flows": 10,
                    "bulk_flows": 2,
                    "unresponsive_flows": 0,
                },
                {
                    "sent_bytes": 80000,
                    "sent_packets": 300,
                    "drops": 0,
                    "ecn_mark": 0,
                    "backlog_bytes": 1000,
                    "peak_delay_us": 1000,
                    "avg_delay_us": 500,
                    "base_delay_us": 100,
                    "sparse_flows": 5,
                    "bulk_flows": 0,
                    "unresponsive_flows": 0,
                },
                {
                    "sent_bytes": 5000,
                    "sent_packets": 50,
                    "drops": 0,
                    "ecn_mark": 0,
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


class TestStatsContractParity:
    """Contract parity: netlink stats dict matches subprocess stats dict -- NLNK-04."""

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_netlink_keys_match_subprocess_keys(self, MockIPRoute, backend):
        """Netlink get_queue_stats returns identical dict keys as subprocess path."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        netlink_result = backend.get_queue_stats("q")

        # Get subprocess result via LinuxCakeBackend
        sub_backend = LinuxCakeBackend(interface="eth0")
        with patch.object(sub_backend, "_run_tc", return_value=(0, _SAMPLE_CAKE_JSON, "")):
            subprocess_result = sub_backend.get_queue_stats("q")

        assert netlink_result is not None
        assert subprocess_result is not None
        assert set(netlink_result.keys()) == set(subprocess_result.keys())

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_netlink_tin_keys_match_subprocess_tin_keys(self, MockIPRoute, backend):
        """Per-tin dict keys from netlink match subprocess path exactly."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        netlink_result = backend.get_queue_stats("q")

        sub_backend = LinuxCakeBackend(interface="eth0")
        with patch.object(sub_backend, "_run_tc", return_value=(0, _SAMPLE_CAKE_JSON, "")):
            subprocess_result = sub_backend.get_queue_stats("q")

        assert netlink_result is not None
        assert subprocess_result is not None
        assert len(netlink_result["tins"]) > 0
        assert len(subprocess_result["tins"]) > 0
        assert set(netlink_result["tins"][0].keys()) == set(subprocess_result["tins"][0].keys())

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_netlink_values_match_subprocess_values(self, MockIPRoute, backend):
        """Netlink stats values match subprocess stats for identical CAKE state."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        mock_instance.tc.return_value = [_make_mock_cake_dump_msg()]
        MockIPRoute.return_value = mock_instance

        netlink_result = backend.get_queue_stats("q")

        sub_backend = LinuxCakeBackend(interface="eth0")
        with patch.object(sub_backend, "_run_tc", return_value=(0, _SAMPLE_CAKE_JSON, "")):
            subprocess_result = sub_backend.get_queue_stats("q")

        assert netlink_result is not None
        assert subprocess_result is not None
        # Compare base fields
        for key in ("packets", "bytes", "dropped", "queued_packets", "queued_bytes"):
            assert netlink_result[key] == subprocess_result[key], f"Mismatch on {key}"
        # Compare extended fields
        for key in ("memory_used", "memory_limit", "capacity_estimate", "ecn_marked"):
            assert netlink_result[key] == subprocess_result[key], f"Mismatch on {key}"
        # Compare per-tin values
        for i, (nl_tin, sp_tin) in enumerate(
            zip(netlink_result["tins"], subprocess_result["tins"], strict=True)
        ):
            for key in nl_tin:
                assert nl_tin[key] == sp_tin[key], f"Mismatch on tin[{i}].{key}"

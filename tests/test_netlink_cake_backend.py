"""Tests for NetlinkCakeBackend implementation.

NLNK-01, NLNK-02, NLNK-03: Netlink CAKE backend tests.

Coverage targets:
- NetlinkCakeBackend constructor and from_config: 100%
- _get_ipr singleton lifecycle and reconnect: 100%
- set_bandwidth netlink path + bps-to-kbit conversion: 100%
- set_bandwidth fallback on NetlinkError/OSError: 100%
- get_bandwidth netlink read + fallback: 100%
- initialize_cake param mapping + fallback: 100%
- validate_cake readback + fallback: 100%
- test_connection netlink path + fallback: 100%
- close() resource cleanup: 100%
"""

import logging
from unittest.mock import MagicMock, PropertyMock, patch

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
    def test_set_bandwidth_logs_debug_on_success(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.set_bandwidth("q", 500_000_000)
        backend.logger.debug.assert_called()


# =============================================================================
# TestSetBandwidthFallback (NLNK-03)
# =============================================================================


class TestSetBandwidthFallback:
    """set_bandwidth fallback to subprocess on netlink failure -- NLNK-03."""

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

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_diffserv(self, MockIPRoute, backend):
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"diffserv": "diffserv4"})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("diffserv_mode") == "diffserv4"

    @patch("wanctl.backends.netlink_cake.IPRoute")
    def test_initialize_cake_maps_docsis_overhead(self, MockIPRoute, backend):
        """overhead_keyword 'docsis' maps to overhead=-1 in pyroute2."""
        mock_instance = MagicMock()
        mock_instance.link_lookup.return_value = [42]
        MockIPRoute.return_value = mock_instance

        backend.initialize_cake({"overhead_keyword": "docsis"})
        call_kwargs = mock_instance.tc.call_args[1]
        assert call_kwargs.get("overhead") == -1

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
        assert call_kwargs.get("rtt") == "100ms"

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
            "TCA_CAKE_DIFFSERV_MODE": "diffserv4",
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

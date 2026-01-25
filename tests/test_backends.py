"""Tests for backend abstraction layer.

BACK-05, BACK-06: Backend base class and RouterOS implementation tests.

Coverage targets:
- RouterBackend abstract class: 100%
- RouterOSBackend implementation: 100%
- All method delegation and error handling: 100%
"""

import logging
from abc import ABC
from unittest.mock import MagicMock, patch

import pytest

from wanctl.backends.base import RouterBackend
from wanctl.backends.routeros import RouterOSBackend


# =============================================================================
# Concrete implementation for testing abstract base
# =============================================================================


class ConcreteBackend(RouterBackend):
    """Minimal concrete implementation for testing abstract base."""

    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        return True

    def get_bandwidth(self, queue: str) -> int | None:
        return 1000000

    def get_queue_stats(self, queue: str) -> dict | None:
        return {"packets": 100, "bytes": 1000}

    def enable_rule(self, comment: str) -> bool:
        return True

    def disable_rule(self, comment: str) -> bool:
        return True

    def is_rule_enabled(self, comment: str) -> bool | None:
        return True


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_ssh():
    """Create mock RouterOSSSH."""
    ssh = MagicMock()
    ssh.run_cmd.return_value = (0, "", "")
    return ssh


@pytest.fixture
def backend(mock_ssh):
    """Create RouterOSBackend with mocked SSH."""
    with patch("wanctl.backends.routeros.RouterOSSSH") as mock_class:
        mock_class.return_value = mock_ssh
        backend = RouterOSBackend(
            host="192.168.1.1",
            user="admin",
            ssh_key="/path/to/key",
        )
    backend.ssh = mock_ssh
    return backend


# =============================================================================
# TestRouterBackend - Abstract base class tests
# =============================================================================


class TestRouterBackend:
    """Tests for RouterBackend abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """RouterBackend() raises TypeError - cannot instantiate ABC."""
        with pytest.raises(TypeError):
            RouterBackend()

    def test_concrete_can_instantiate(self) -> None:
        """ConcreteBackend() works when all abstract methods implemented."""
        backend = ConcreteBackend()
        assert isinstance(backend, RouterBackend)

    def test_logger_provided(self, mock_logger) -> None:
        """Uses provided logger when specified."""
        backend = ConcreteBackend(logger=mock_logger)
        assert backend.logger is mock_logger

    def test_logger_default(self) -> None:
        """Creates default logger when none provided."""
        backend = ConcreteBackend()
        assert backend.logger is not None
        assert isinstance(backend.logger, logging.Logger)

    def test_reset_queue_counters_default_true(self) -> None:
        """Default reset_queue_counters returns True."""
        backend = ConcreteBackend()
        result = backend.reset_queue_counters("test-queue")
        assert result is True

    def test_test_connection_default_true(self) -> None:
        """Default test_connection returns True."""
        backend = ConcreteBackend()
        result = backend.test_connection()
        assert result is True

    def test_from_config_not_implemented(self) -> None:
        """Base from_config raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            RouterBackend.from_config(MagicMock())


# =============================================================================
# TestRouterOSBackendInit - RouterOSBackend initialization tests
# =============================================================================


class TestRouterOSBackendInit:
    """Tests for RouterOSBackend initialization."""

    def test_from_config_creates_backend(self) -> None:
        """from_config creates instance with correct params."""
        config = MagicMock()
        config.router = {
            "host": "192.168.88.1",
            "user": "api_user",
            "ssh_key": "/etc/wanctl/ssh/key",
        }
        config.timeouts = {"ssh_command": 25}

        with patch("wanctl.backends.routeros.RouterOSSSH") as mock_ssh_class:
            backend = RouterOSBackend.from_config(config)

            mock_ssh_class.assert_called_once_with(
                host="192.168.88.1",
                user="api_user",
                ssh_key="/etc/wanctl/ssh/key",
                timeout=25,
                logger=backend.logger,
            )

    def test_from_config_default_timeout(self) -> None:
        """Uses 15 when config.timeouts missing."""
        config = MagicMock(spec=["router"])
        config.router = {
            "host": "192.168.88.1",
            "user": "admin",
            "ssh_key": "/path/to/key",
        }

        with patch("wanctl.backends.routeros.RouterOSSSH") as mock_ssh_class:
            backend = RouterOSBackend.from_config(config)

            call_kwargs = mock_ssh_class.call_args[1]
            assert call_kwargs["timeout"] == 15

    def test_from_config_custom_timeout(self) -> None:
        """Uses config.timeouts['ssh_command'] when specified."""
        config = MagicMock()
        config.router = {
            "host": "192.168.88.1",
            "user": "admin",
            "ssh_key": "/path/to/key",
        }
        config.timeouts = {"ssh_command": 45}

        with patch("wanctl.backends.routeros.RouterOSSSH") as mock_ssh_class:
            backend = RouterOSBackend.from_config(config)

            call_kwargs = mock_ssh_class.call_args[1]
            assert call_kwargs["timeout"] == 45


# =============================================================================
# TestSetBandwidth - set_bandwidth tests
# =============================================================================


class TestSetBandwidth:
    """Tests for RouterOSBackend.set_bandwidth method."""

    def test_set_bandwidth_success(self, backend, mock_ssh) -> None:
        """Returns True on rc=0."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.set_bandwidth("WAN-Download-1", 100000000)

        assert result is True

    def test_set_bandwidth_failure(self, backend, mock_ssh) -> None:
        """Returns False on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "queue not found")

        result = backend.set_bandwidth("NonexistentQueue", 100000000)

        assert result is False

    def test_set_bandwidth_runs_correct_command(self, backend, mock_ssh) -> None:
        """SSH gets correct command string."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        backend.set_bandwidth("WAN-Download-1", 50000000)

        call_args = mock_ssh.run_cmd.call_args[0]
        assert '/queue/tree/set [find name="WAN-Download-1"] max-limit=50000000' in call_args[0]


# =============================================================================
# TestGetBandwidth - get_bandwidth tests
# =============================================================================


class TestGetBandwidth:
    """Tests for RouterOSBackend.get_bandwidth method."""

    def test_get_bandwidth_success(self, backend, mock_ssh) -> None:
        """Parses max-limit from output."""
        mock_ssh.run_cmd.return_value = (
            0,
            "name=WAN-Download-1 max-limit=100000000 parent=global",
            "",
        )

        result = backend.get_bandwidth("WAN-Download-1")

        assert result == 100000000

    def test_get_bandwidth_failure(self, backend, mock_ssh) -> None:
        """Returns None on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "error")

        result = backend.get_bandwidth("BadQueue")

        assert result is None

    def test_get_bandwidth_unlimited(self, backend, mock_ssh) -> None:
        """Returns 0 for max-limit=0 (unlimited)."""
        mock_ssh.run_cmd.return_value = (
            0,
            "name=WAN-Download-1 max-limit=0 parent=global",
            "",
        )

        result = backend.get_bandwidth("WAN-Download-1")

        assert result == 0

    def test_get_bandwidth_no_max_limit_field(self, backend, mock_ssh) -> None:
        """Returns 0 when max-limit field not in output (unlimited)."""
        mock_ssh.run_cmd.return_value = (
            0,
            "name=WAN-Download-1 parent=global",
            "",
        )

        result = backend.get_bandwidth("WAN-Download-1")

        assert result == 0

    def test_get_bandwidth_unparseable(self, backend, mock_ssh) -> None:
        """Returns None when max-limit exists but can't be parsed."""
        mock_ssh.run_cmd.return_value = (
            0,
            "name=WAN-Download-1 max-limit=abc parent=global",
            "",
        )

        result = backend.get_bandwidth("WAN-Download-1")

        assert result is None


# =============================================================================
# TestGetQueueStats - get_queue_stats tests
# =============================================================================


class TestGetQueueStats:
    """Tests for RouterOSBackend.get_queue_stats method."""

    def test_get_queue_stats_success(self, backend, mock_ssh) -> None:
        """Parses stats from output."""
        mock_ssh.run_cmd.return_value = (
            0,
            "name=WAN-Download-1 packets=1234 bytes=567890 dropped=5 "
            "queued-packets=10 queued-bytes=15000",
            "",
        )

        result = backend.get_queue_stats("WAN-Download-1")

        assert result is not None
        assert result["packets"] == 1234
        assert result["bytes"] == 567890
        assert result["dropped"] == 5
        assert result["queued_packets"] == 10
        assert result["queued_bytes"] == 15000

    def test_get_queue_stats_failure(self, backend, mock_ssh) -> None:
        """Returns None on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "queue not found")

        result = backend.get_queue_stats("BadQueue")

        assert result is None


# =============================================================================
# TestEnableRule - enable_rule tests
# =============================================================================


class TestEnableRule:
    """Tests for RouterOSBackend.enable_rule method."""

    def test_enable_rule_success(self, backend, mock_ssh) -> None:
        """Returns True on rc=0."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.enable_rule("ADAPTIVE: Steer to secondary")

        assert result is True

    def test_enable_rule_failure(self, backend, mock_ssh) -> None:
        """Returns False on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "rule not found")

        result = backend.enable_rule("NonexistentRule")

        assert result is False

    def test_enable_rule_runs_correct_command(self, backend, mock_ssh) -> None:
        """SSH gets correct command string."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        backend.enable_rule("ADAPTIVE: Steer to secondary")

        call_args = mock_ssh.run_cmd.call_args[0]
        assert '/ip/firewall/mangle/enable [find comment="ADAPTIVE: Steer to secondary"]' in call_args[0]


# =============================================================================
# TestDisableRule - disable_rule tests
# =============================================================================


class TestDisableRule:
    """Tests for RouterOSBackend.disable_rule method."""

    def test_disable_rule_success(self, backend, mock_ssh) -> None:
        """Returns True on rc=0."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.disable_rule("ADAPTIVE: Steer to secondary")

        assert result is True

    def test_disable_rule_failure(self, backend, mock_ssh) -> None:
        """Returns False on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "rule not found")

        result = backend.disable_rule("NonexistentRule")

        assert result is False

    def test_disable_rule_runs_correct_command(self, backend, mock_ssh) -> None:
        """SSH gets correct command string."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        backend.disable_rule("ADAPTIVE: Steer to secondary")

        call_args = mock_ssh.run_cmd.call_args[0]
        assert '/ip/firewall/mangle/disable [find comment="ADAPTIVE: Steer to secondary"]' in call_args[0]


# =============================================================================
# TestIsRuleEnabled - is_rule_enabled tests
# =============================================================================


class TestIsRuleEnabled:
    """Tests for RouterOSBackend.is_rule_enabled method."""

    def test_is_rule_enabled_true(self, backend, mock_ssh) -> None:
        """Returns True when not disabled (no X flag)."""
        mock_ssh.run_cmd.return_value = (
            0,
            "0 ;;; ADAPTIVE: Steer to secondary\n   chain=prerouting action=mark-routing",
            "",
        )

        result = backend.is_rule_enabled("ADAPTIVE: Steer to secondary")

        assert result is True

    def test_is_rule_enabled_false(self, backend, mock_ssh) -> None:
        """Returns False when X flag present (disabled)."""
        mock_ssh.run_cmd.return_value = (
            0,
            "0 X ;;; ADAPTIVE: Steer to secondary\n   chain=prerouting action=mark-routing",
            "",
        )

        result = backend.is_rule_enabled("ADAPTIVE: Steer to secondary")

        assert result is False

    def test_is_rule_enabled_not_found(self, backend, mock_ssh) -> None:
        """Returns None when empty output (rule not found)."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.is_rule_enabled("NonexistentRule")

        assert result is None

    def test_is_rule_enabled_error(self, backend, mock_ssh) -> None:
        """Returns None on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "error")

        result = backend.is_rule_enabled("SomeRule")

        assert result is None


# =============================================================================
# TestResetQueueCounters - reset_queue_counters tests
# =============================================================================


class TestResetQueueCounters:
    """Tests for RouterOSBackend.reset_queue_counters method."""

    def test_reset_queue_counters_success(self, backend, mock_ssh) -> None:
        """Returns True on rc=0."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.reset_queue_counters("WAN-Download-1")

        assert result is True

    def test_reset_queue_counters_failure(self, backend, mock_ssh) -> None:
        """Returns False on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "queue not found")

        result = backend.reset_queue_counters("BadQueue")

        assert result is False

    def test_reset_queue_counters_runs_correct_command(self, backend, mock_ssh) -> None:
        """SSH gets correct command string."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        backend.reset_queue_counters("WAN-Download-1")

        call_args = mock_ssh.run_cmd.call_args[0]
        assert '/queue/tree/reset-counters [find name="WAN-Download-1"]' in call_args[0]


# =============================================================================
# TestTestConnection - test_connection tests
# =============================================================================


class TestTestConnection:
    """Tests for RouterOSBackend.test_connection method."""

    def test_test_connection_success(self, backend, mock_ssh) -> None:
        """Returns True when identity command succeeds."""
        mock_ssh.run_cmd.return_value = (0, "name: Router-1", "")

        result = backend.test_connection()

        assert result is True

    def test_test_connection_failure_rc(self, backend, mock_ssh) -> None:
        """Returns False on rc!=0."""
        mock_ssh.run_cmd.return_value = (1, "", "connection failed")

        result = backend.test_connection()

        assert result is False

    def test_test_connection_failure_empty(self, backend, mock_ssh) -> None:
        """Returns False on empty output (even with rc=0)."""
        mock_ssh.run_cmd.return_value = (0, "", "")

        result = backend.test_connection()

        assert result is False

    def test_test_connection_runs_correct_command(self, backend, mock_ssh) -> None:
        """SSH gets correct identity command."""
        mock_ssh.run_cmd.return_value = (0, "name: Router", "")

        backend.test_connection()

        call_args = mock_ssh.run_cmd.call_args[0]
        assert "/system/identity/print" in call_args[0]

"""Tests for RouterOS SSH client - routeros_ssh module.

BACK-03, BACK-04: SSH client tests for connection management, command execution,
error handling, and reconnection logic.

Coverage targets:
- Constructor and from_config: 100%
- Connection management: 100%
- Command execution (run_cmd): 100%
- Error handling: 100%
- Resource cleanup (close): 100%
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from wanctl.routeros_ssh import RouterOSSSH


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_ssh_client():
    """Create mock paramiko SSHClient with active transport."""
    client = MagicMock(spec=paramiko.SSHClient)
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport

    # Mock exec_command return values
    stdin = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.read.return_value = b"output"
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    client.exec_command.return_value = (stdin, stdout, stderr)

    return client


@pytest.fixture
def ssh_client(mock_ssh_client, tmp_path):
    """Create SSH client with mocked paramiko."""
    # Create dummy key file
    key_file = tmp_path / "test_key"
    key_file.touch()

    with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
        mock_class.return_value = mock_ssh_client
        client = RouterOSSSH(
            host="192.168.1.1",
            user="admin",
            ssh_key=str(key_file),
        )
    return client


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return MagicMock(spec=logging.Logger)


# =============================================================================
# TestRouterOSSSHInit - Constructor tests
# =============================================================================


class TestRouterOSSSHInit:
    """Tests for RouterOSSSH constructor."""

    def test_stores_host(self, tmp_path) -> None:
        """Host attribute is set correctly."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        assert client.host == "10.0.0.1"

    def test_stores_user(self, tmp_path) -> None:
        """User attribute is set correctly."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="routeros_user",
            ssh_key=str(key_file),
        )

        assert client.user == "routeros_user"

    def test_stores_ssh_key(self, tmp_path) -> None:
        """SSH key attribute is set correctly."""
        key_file = tmp_path / "my_private_key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        assert client.ssh_key == str(key_file)

    def test_default_timeout_15(self, tmp_path) -> None:
        """Timeout defaults to 15 seconds when not specified."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        assert client.timeout == 15

    def test_custom_timeout(self, tmp_path) -> None:
        """Custom timeout is stored correctly."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
            timeout=30,
        )

        assert client.timeout == 30

    def test_logger_provided(self, tmp_path, mock_logger) -> None:
        """Uses provided logger when specified."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
            logger=mock_logger,
        )

        assert client.logger is mock_logger

    def test_logger_default(self, tmp_path) -> None:
        """Creates default logger when none provided."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        assert client.logger is not None
        assert isinstance(client.logger, logging.Logger)

    def test_client_initially_none(self, tmp_path) -> None:
        """Internal _client is None before connection."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        assert client._client is None


# =============================================================================
# TestFromConfig - from_config class method tests
# =============================================================================


class TestFromConfig:
    """Tests for RouterOSSSH.from_config class method."""

    def test_from_config_basic(self, mock_logger) -> None:
        """Creates client from config object with correct attributes."""
        config = MagicMock()
        config.router_host = "192.168.88.1"
        config.router_user = "api_user"
        config.ssh_key = "/etc/wanctl/ssh/router.key"
        config.timeout_ssh_command = 20

        client = RouterOSSSH.from_config(config, mock_logger)

        assert client.host == "192.168.88.1"
        assert client.user == "api_user"
        assert client.ssh_key == "/etc/wanctl/ssh/router.key"
        assert client.timeout == 20
        assert client.logger is mock_logger

    def test_from_config_default_timeout(self, mock_logger) -> None:
        """Uses 15 when timeout_ssh_command not specified."""
        config = MagicMock(spec=["router_host", "router_user", "ssh_key"])
        config.router_host = "192.168.88.1"
        config.router_user = "admin"
        config.ssh_key = "/path/to/key"

        client = RouterOSSSH.from_config(config, mock_logger)

        assert client.timeout == 15

    def test_from_config_custom_timeout(self, mock_logger) -> None:
        """Uses timeout_ssh_command from config when specified."""
        config = MagicMock()
        config.router_host = "192.168.88.1"
        config.router_user = "admin"
        config.ssh_key = "/path/to/key"
        config.timeout_ssh_command = 45

        client = RouterOSSSH.from_config(config, mock_logger)

        assert client.timeout == 45


# =============================================================================
# TestGetKnownHostsPath - _get_known_hosts_path tests
# =============================================================================


class TestGetKnownHostsPath:
    """Tests for _get_known_hosts_path method."""

    def test_known_hosts_path_returns_path(self, ssh_client) -> None:
        """Returns Path object for known_hosts file."""
        result = ssh_client._get_known_hosts_path()

        assert isinstance(result, Path)
        assert result.name == "known_hosts"

    def test_known_hosts_path_creates_ssh_dir(self, tmp_path) -> None:
        """Creates ~/.ssh directory if it doesn't exist."""
        # Create client with mocked home directory
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        # Patch Path.home() to return our temp directory
        with patch.object(Path, "home", return_value=tmp_path):
            result = client._get_known_hosts_path()

            ssh_dir = tmp_path / ".ssh"
            assert ssh_dir.exists()
            assert ssh_dir.is_dir()

    def test_known_hosts_path_creates_file(self, tmp_path) -> None:
        """Creates known_hosts file if it doesn't exist."""
        key_file = tmp_path / "key"
        key_file.touch()

        client = RouterOSSSH(
            host="10.0.0.1",
            user="admin",
            ssh_key=str(key_file),
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = client._get_known_hosts_path()

            assert result.exists()
            assert result.is_file()


# =============================================================================
# TestConnection - Connection management tests
# =============================================================================


class TestConnection:
    """Tests for SSH connection management."""

    def test_connect_creates_client(self, tmp_path, mock_ssh_client) -> None:
        """_connect creates SSHClient instance."""
        key_file = tmp_path / "key"
        key_file.touch()

        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
            mock_class.return_value = mock_ssh_client

            client = RouterOSSSH(
                host="192.168.1.1",
                user="admin",
                ssh_key=str(key_file),
            )
            client._connect()

            mock_class.assert_called_once()
            assert client._client is mock_ssh_client

    def test_connect_loads_host_keys(self, tmp_path, mock_ssh_client) -> None:
        """_connect calls load_system_host_keys and load_host_keys."""
        key_file = tmp_path / "key"
        key_file.touch()

        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
            mock_class.return_value = mock_ssh_client

            client = RouterOSSSH(
                host="192.168.1.1",
                user="admin",
                ssh_key=str(key_file),
            )
            client._connect()

            mock_ssh_client.load_system_host_keys.assert_called_once()
            mock_ssh_client.load_host_keys.assert_called_once()

    def test_connect_sets_reject_policy(self, tmp_path, mock_ssh_client) -> None:
        """_connect sets RejectPolicy for host key validation."""
        key_file = tmp_path / "key"
        key_file.touch()

        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
            mock_class.return_value = mock_ssh_client

            client = RouterOSSSH(
                host="192.168.1.1",
                user="admin",
                ssh_key=str(key_file),
            )
            client._connect()

            mock_ssh_client.set_missing_host_key_policy.assert_called_once()
            call_args = mock_ssh_client.set_missing_host_key_policy.call_args
            assert isinstance(call_args[0][0], paramiko.RejectPolicy)

    def test_connect_calls_connect(self, tmp_path, mock_ssh_client) -> None:
        """_connect calls connect with correct parameters."""
        key_file = tmp_path / "key"
        key_file.touch()

        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
            mock_class.return_value = mock_ssh_client

            client = RouterOSSSH(
                host="192.168.1.1",
                user="admin",
                ssh_key=str(key_file),
            )
            client._connect()

            mock_ssh_client.connect.assert_called_once_with(
                hostname="192.168.1.1",
                username="admin",
                key_filename=str(key_file),
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )

    def test_is_connected_false_when_no_client(self, ssh_client) -> None:
        """_is_connected returns False when _client is None."""
        ssh_client._client = None

        assert ssh_client._is_connected() is False

    def test_is_connected_false_when_no_transport(self, ssh_client, mock_ssh_client) -> None:
        """_is_connected returns False when get_transport returns None."""
        ssh_client._client = mock_ssh_client
        mock_ssh_client.get_transport.return_value = None

        assert ssh_client._is_connected() is False

    def test_is_connected_false_when_inactive(self, ssh_client, mock_ssh_client) -> None:
        """_is_connected returns False when transport is inactive."""
        ssh_client._client = mock_ssh_client
        transport = MagicMock()
        transport.is_active.return_value = False
        mock_ssh_client.get_transport.return_value = transport

        assert ssh_client._is_connected() is False

    def test_is_connected_true_when_active(self, ssh_client, mock_ssh_client) -> None:
        """_is_connected returns True when transport is active."""
        ssh_client._client = mock_ssh_client
        transport = MagicMock()
        transport.is_active.return_value = True
        mock_ssh_client.get_transport.return_value = transport

        assert ssh_client._is_connected() is True

    def test_ensure_connected_connects_when_disconnected(
        self, ssh_client, mock_ssh_client
    ) -> None:
        """_ensure_connected calls _connect when not connected."""
        ssh_client._client = None

        with patch.object(ssh_client, "_connect") as mock_connect:
            ssh_client._ensure_connected()
            mock_connect.assert_called_once()

    def test_ensure_connected_noop_when_connected(self, ssh_client, mock_ssh_client) -> None:
        """_ensure_connected doesn't reconnect when already connected."""
        ssh_client._client = mock_ssh_client
        transport = MagicMock()
        transport.is_active.return_value = True
        mock_ssh_client.get_transport.return_value = transport

        with patch.object(ssh_client, "_connect") as mock_connect:
            ssh_client._ensure_connected()
            mock_connect.assert_not_called()

    def test_ensure_connected_reconnects_on_lost_connection(
        self, ssh_client, mock_ssh_client
    ) -> None:
        """_ensure_connected reconnects when transport is inactive."""
        ssh_client._client = mock_ssh_client
        transport = MagicMock()
        transport.is_active.return_value = False
        mock_ssh_client.get_transport.return_value = transport

        with patch.object(ssh_client, "_connect") as mock_connect:
            ssh_client._ensure_connected()
            mock_connect.assert_called_once()
            mock_ssh_client.close.assert_called_once()

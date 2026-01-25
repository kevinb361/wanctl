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

    def test_ensure_connected_handles_close_exception(
        self, ssh_client, mock_ssh_client
    ) -> None:
        """_ensure_connected ignores exception during close before reconnect."""
        ssh_client._client = mock_ssh_client
        transport = MagicMock()
        transport.is_active.return_value = False
        mock_ssh_client.get_transport.return_value = transport
        # Simulate close() throwing exception
        mock_ssh_client.close.side_effect = Exception("Close failed")

        with patch.object(ssh_client, "_connect") as mock_connect:
            # Should not raise despite close() exception
            ssh_client._ensure_connected()
            mock_connect.assert_called_once()


# =============================================================================
# TestRunCmd - Command execution tests
# =============================================================================


class TestRunCmd:
    """Tests for run_cmd method."""

    def test_run_cmd_success(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd returns (0, stdout, stderr) on success."""
        ssh_client._client = mock_ssh_client

        # Setup mock for exec_command
        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b"output data"
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/queue tree print", capture=True)

        assert rc == 0
        assert out == "output data"
        assert err == ""

    def test_run_cmd_capture_true(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd returns decoded output when capture=True."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b"test output"
        stderr.read.return_value = b"test error"
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/test", capture=True)

        assert out == "test output"
        assert err == "test error"

    def test_run_cmd_capture_false(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd returns empty strings when capture=False but drains channels."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b"ignored output"
        stderr.read.return_value = b"ignored error"
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/test", capture=False)

        assert rc == 0
        assert out == ""
        assert err == ""
        # Verify channels were still drained
        stdout.read.assert_called_once()
        stderr.read.assert_called_once()

    def test_run_cmd_custom_timeout(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd passes timeout to exec_command."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b""
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        ssh_client.run_cmd("/test", timeout=30)

        mock_ssh_client.exec_command.assert_called_once()
        call_kwargs = mock_ssh_client.exec_command.call_args[1]
        assert call_kwargs["timeout"] == 30

    def test_run_cmd_nonzero_exit(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd returns non-zero exit status."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b""
        stderr.read.return_value = b"error: command failed"
        stdout.channel.recv_exit_status.return_value = 1
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/bad command", capture=True)

        assert rc == 1
        assert err == "error: command failed"

    def test_run_cmd_ensures_connected(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd calls _ensure_connected before exec."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b""
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        with patch.object(ssh_client, "_ensure_connected") as mock_ensure:
            ssh_client.run_cmd("/test")
            mock_ensure.assert_called_once()

    def test_run_cmd_ssh_exception_clears_client(self, ssh_client, mock_ssh_client) -> None:
        """SSHException during run_cmd sets _client to None."""
        ssh_client._client = mock_ssh_client
        mock_ssh_client.exec_command.side_effect = paramiko.SSHException("Connection lost")

        with pytest.raises(paramiko.SSHException):
            ssh_client.run_cmd("/test")

        assert ssh_client._client is None

    def test_run_cmd_ssh_exception_raises(self, ssh_client, mock_ssh_client) -> None:
        """SSHException propagates after clearing client."""
        ssh_client._client = mock_ssh_client
        mock_ssh_client.exec_command.side_effect = paramiko.SSHException("Connection lost")

        with pytest.raises(paramiko.SSHException, match="Connection lost"):
            ssh_client.run_cmd("/test")

    def test_run_cmd_decodes_utf8(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd decodes output with utf-8."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        # Unicode characters in output
        stdout.read.return_value = "test \u2713 pass".encode("utf-8")
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/test", capture=True)

        assert "\u2713" in out
        assert "pass" in out

    def test_run_cmd_handles_decode_errors(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd uses errors='replace' for bad bytes."""
        ssh_client._client = mock_ssh_client

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        # Invalid UTF-8 bytes
        stdout.read.return_value = b"test \xff\xfe output"
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        rc, out, err = ssh_client.run_cmd("/test", capture=True)

        # Should not raise, and should contain replacement characters
        assert rc == 0
        assert "test" in out
        assert "output" in out

    def test_run_cmd_uses_default_timeout(self, ssh_client, mock_ssh_client) -> None:
        """run_cmd uses self.timeout when timeout param is None."""
        ssh_client._client = mock_ssh_client
        ssh_client.timeout = 20  # Set a specific default

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b""
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        ssh_client.run_cmd("/test")

        call_kwargs = mock_ssh_client.exec_command.call_args[1]
        assert call_kwargs["timeout"] == 20

    def test_run_cmd_logs_debug_output(self, ssh_client, mock_ssh_client, mock_logger) -> None:
        """run_cmd logs stdout at DEBUG level when enabled."""
        ssh_client._client = mock_ssh_client
        ssh_client.logger = mock_logger
        # Enable DEBUG level
        mock_logger.isEnabledFor.return_value = True

        stdin = MagicMock()
        stdout = MagicMock()
        stderr = MagicMock()
        stdout.read.return_value = b"test output"
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (stdin, stdout, stderr)

        ssh_client.run_cmd("/test", capture=True)

        # Verify debug was called with stdout content
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("test output" in call for call in debug_calls)


# =============================================================================
# TestClose - Resource cleanup tests
# =============================================================================


class TestClose:
    """Tests for close method."""

    def test_close_closes_client(self, ssh_client, mock_ssh_client) -> None:
        """close() calls _client.close()."""
        ssh_client._client = mock_ssh_client

        ssh_client.close()

        mock_ssh_client.close.assert_called_once()

    def test_close_sets_client_none(self, ssh_client, mock_ssh_client) -> None:
        """close() sets _client to None after closing."""
        ssh_client._client = mock_ssh_client

        ssh_client.close()

        assert ssh_client._client is None

    def test_close_safe_when_no_client(self, ssh_client) -> None:
        """close() doesn't raise when _client is None."""
        ssh_client._client = None

        # Should not raise
        ssh_client.close()

        assert ssh_client._client is None

    def test_close_safe_on_exception(self, ssh_client, mock_ssh_client) -> None:
        """close() handles exception during close without raising."""
        ssh_client._client = mock_ssh_client
        mock_ssh_client.close.side_effect = Exception("Close failed")

        # Should not raise
        ssh_client.close()

        # Client should still be set to None
        assert ssh_client._client is None

    def test_close_logs_debug(self, ssh_client, mock_ssh_client, mock_logger) -> None:
        """close() logs debug message on successful close."""
        ssh_client._client = mock_ssh_client
        ssh_client.logger = mock_logger

        ssh_client.close()

        mock_logger.debug.assert_called()

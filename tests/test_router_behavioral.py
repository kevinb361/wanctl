"""Reduced-mock behavioral tests for router communication layer.

"Reduced-mock" means: only the network transport layer is mocked (requests.Session
for REST, paramiko.SSHClient for SSH). All internal command parsing, ID resolution,
response handling, and error propagation runs as REAL code.

This catches bugs that fully-mocked tests miss: command parsing errors,
response format mismatches, error propagation failures.
"""

import json
import logging
from io import BytesIO
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from wanctl.router_client import FailoverRouterClient
from wanctl.routeros_rest import RouterOSREST
from wanctl.routeros_ssh import RouterOSSSH


@pytest.fixture
def logger() -> logging.Logger:
    """Return a real logger."""
    return logging.getLogger("test_router_behavioral")


# =============================================================================
# RouterOSREST behavioral tests
# =============================================================================


class TestRouterOSRESTBehavioral:
    """Tests exercising real RouterOSREST code with only HTTP transport mocked."""

    def _make_rest_client(
        self, mock_session_cls: MagicMock, logger: logging.Logger
    ) -> RouterOSREST:
        """Create RouterOSREST with mocked requests.Session."""
        with patch("wanctl.routeros_rest.requests.Session", mock_session_cls):
            return RouterOSREST(
                host="10.10.99.1",
                user="admin",
                password="testpass",  # pragma: allowlist secret
                port=443,
                verify_ssl=True,
                timeout=15,
                logger=logger,
            )

    def test_queue_tree_print_returns_realistic_json(self, logger):
        """run_cmd("/queue tree print") with realistic JSON list returns (0, json_str, "")."""
        realistic_response = [
            {
                ".id": "*1",
                "name": "WAN-Download-Spectrum",
                "queue": "cake/diffserv4",
                "max-limit": "920000000",
                "parent": "global",
            },
            {
                ".id": "*2",
                "name": "WAN-Upload-Spectrum",
                "queue": "cake/diffserv4",
                "max-limit": "40000000",
                "parent": "global",
            },
        ]

        mock_session_cls = MagicMock()
        mock_session = mock_session_cls.return_value
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = realistic_response
        mock_session.get.return_value = mock_response

        client = self._make_rest_client(mock_session_cls, logger)
        rc, stdout, stderr = client.run_cmd("/queue tree print")

        assert rc == 0
        assert stderr == ""
        parsed = json.loads(stdout)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "WAN-Download-Spectrum"

    def test_queue_tree_set_resolves_id_then_patches(self, logger):
        """run_cmd for queue tree set resolves queue ID via GET, then PATCHes."""
        # GET response for finding queue ID
        find_response = MagicMock()
        find_response.ok = True
        find_response.json.return_value = [
            {".id": "*1", "name": "WAN-Download", "max-limit": "920000000"}
        ]

        # PATCH response for update
        patch_response = MagicMock()
        patch_response.ok = True

        mock_session_cls = MagicMock()
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = find_response
        mock_session.patch.return_value = patch_response

        client = self._make_rest_client(mock_session_cls, logger)
        cmd = '/queue tree set [find name="WAN-Download"] queue=cake/diffserv4 max-limit=500000000'
        rc, stdout, stderr = client.run_cmd(cmd)

        assert rc == 0
        # Verify GET was called to resolve queue ID
        mock_session.get.assert_called()
        # Verify PATCH was called with the resolved ID
        mock_session.patch.assert_called_once()
        call_args = mock_session.patch.call_args
        assert "*1" in call_args[0][0]  # URL contains the queue ID

    def test_set_queue_limit_resolves_and_patches(self, logger):
        """set_queue_limit("WAN-Download", 500000000) resolves ID and PATCHes."""
        find_response = MagicMock()
        find_response.ok = True
        find_response.json.return_value = [
            {".id": "*3", "name": "WAN-Download", "max-limit": "920000000"}
        ]

        patch_response = MagicMock()
        patch_response.ok = True

        mock_session_cls = MagicMock()
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = find_response
        mock_session.patch.return_value = patch_response

        client = self._make_rest_client(mock_session_cls, logger)
        result = client.set_queue_limit("WAN-Download", 500_000_000)

        assert result is True
        # Verify PATCH sent correct max-limit
        patch_call = mock_session.patch.call_args
        assert patch_call[1]["json"]["max-limit"] == "500000000"

    def test_http_401_returns_error(self, logger):
        """run_cmd returns (1, "", error_msg) when HTTP returns 401 Unauthorized."""
        mock_session_cls = MagicMock()
        mock_session = mock_session_cls.return_value

        error_response = MagicMock()
        error_response.ok = False
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        mock_session.get.return_value = error_response

        client = self._make_rest_client(mock_session_cls, logger)
        rc, stdout, stderr = client.run_cmd("/queue tree print")

        assert rc == 1
        assert stdout == ""

    def test_connection_error_returns_error(self, logger):
        """run_cmd returns (1, "", ...) when requests.ConnectionError is raised."""
        import requests

        mock_session_cls = MagicMock()
        mock_session = mock_session_cls.return_value
        mock_session.get.side_effect = requests.ConnectionError("Connection refused")

        client = self._make_rest_client(mock_session_cls, logger)
        rc, stdout, stderr = client.run_cmd("/queue tree print")

        assert rc == 1
        assert stdout == ""
        # Error is caught at _handle_queue_tree_print level and returns None,
        # which run_cmd translates to "Command failed" -- the important thing
        # is that no exception propagates to the caller
        assert stderr != ""


# =============================================================================
# RouterOSSSH behavioral tests
# =============================================================================


class TestRouterOSSSHBehavioral:
    """Tests exercising real RouterOSSSH code with only paramiko transport mocked."""

    @staticmethod
    def _setup_channel(mock_ssh_instance: MagicMock, stdout_data: str, exit_status: int = 0):
        """Configure mock SSH instance to return realistic channel data."""
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()

        # Channel with exit status
        mock_channel = MagicMock()
        mock_channel.recv_exit_status.return_value = exit_status
        mock_stdout.channel = mock_channel

        # Stdout/stderr read returns
        mock_stdout.read.return_value = stdout_data.encode("utf-8")
        mock_stderr.read.return_value = b""

        mock_ssh_instance.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        # Transport must appear active for _is_connected check
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_ssh_instance.get_transport.return_value = mock_transport

    def test_ssh_run_cmd_with_realistic_output(self, logger):
        """run_cmd("/queue tree print") with realistic RouterOS text output."""
        realistic_output = (
            "Flags: X - disabled, I - invalid\n"
            ' 0    name="WAN-Download-Spectrum" parent=global packet-mark="" '
            "queue=cake/diffserv4 max-limit=920M\n"
            ' 1    name="WAN-Upload-Spectrum" parent=global packet-mark="" '
            "queue=cake/diffserv4 max-limit=40M\n"
        )

        # Patch paramiko.SSHClient at the module level so _connect() gets the mock
        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_paramiko_cls:
            mock_ssh_instance = mock_paramiko_cls.return_value

            # Configure realistic channel output
            self._setup_channel(mock_ssh_instance, realistic_output, exit_status=0)

            client = RouterOSSSH(
                host="10.10.99.1",
                user="admin",
                ssh_key="/tmp/test.key",
                timeout=15,
                logger=logger,
            )
            rc, stdout, stderr = client.run_cmd("/queue tree print", capture=True)

        assert rc == 0
        assert "WAN-Download-Spectrum" in stdout
        assert "WAN-Upload-Spectrum" in stdout

    def test_ssh_timeout_returns_error(self, logger):
        """run_cmd raises SSHException after retries when paramiko channel times out."""
        import paramiko

        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_paramiko_cls:
            mock_ssh_instance = mock_paramiko_cls.return_value

            # Transport appears active so _is_connected succeeds
            mock_transport = MagicMock()
            mock_transport.is_active.return_value = True
            mock_ssh_instance.get_transport.return_value = mock_transport

            # exec_command raises SSHException (timeout)
            mock_ssh_instance.exec_command.side_effect = paramiko.SSHException("Timeout")

            client = RouterOSSSH(
                host="10.10.99.1",
                user="admin",
                ssh_key="/tmp/test.key",
                timeout=15,
                logger=logger,
            )

            # SSHException is retryable, so after max retries it should re-raise
            with pytest.raises(paramiko.SSHException):
                client.run_cmd("/queue tree print")


# =============================================================================
# FailoverRouterClient behavioral tests
# =============================================================================


class TestFailoverRouterClientBehavioral:
    """Tests exercising real FailoverRouterClient failover with realistic responses."""

    def test_failover_from_rest_to_ssh(self, logger):
        """REST ConnectionError triggers failover to SSH with realistic responses."""
        # Create config with all needed attributes
        config = MagicMock()
        config.router_transport = "rest"
        config.router_host = "10.10.99.1"
        config.router_user = "admin"
        config.router_password = "testpass"  # pragma: allowlist secret
        config.router_port = 443
        config.router_verify_ssl = True
        config.ssh_key = "/tmp/test.key"
        config.timeout_ssh_command = 15

        # Mock REST client to raise ConnectionError
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST connection refused")

        # Mock SSH client to return realistic success
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, '{"status": "ok"}', "")

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
            # First call creates REST (primary), second creates SSH (fallback)
            mock_create.side_effect = [mock_rest, mock_ssh]

            failover_client = FailoverRouterClient(
                config=config,
                logger=logger,
                primary_transport="rest",
                fallback_transport="ssh",
            )

            rc, stdout, stderr = failover_client.run_cmd("/queue tree print", capture=True)

        assert rc == 0
        assert "ok" in stdout
        # Verify REST was tried first then SSH was used
        mock_rest.run_cmd.assert_called_once()
        mock_ssh.run_cmd.assert_called_once()

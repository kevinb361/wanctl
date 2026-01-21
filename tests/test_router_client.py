"""Tests for router_client module - transport selection and failover.

TEST-03: REST-to-SSH automatic failover tests.

These tests prove the safety invariant that REST API failures automatically
fall back to SSH transport, preventing daemon crashes when REST API is
temporarily unavailable.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from wanctl.router_client import (
    FailoverRouterClient,
    get_router_client,
    get_router_client_with_failover,
)


class TestGetRouterClient:
    """Tests for basic get_router_client factory."""

    def test_ssh_transport_selection(self) -> None:
        """SSH transport selected when config specifies ssh."""
        config = MagicMock()
        config.router_transport = "ssh"
        logger = MagicMock(spec=logging.Logger)

        with patch("wanctl.router_client.RouterOSSSH") as mock_ssh:
            mock_ssh.from_config.return_value = MagicMock()
            get_router_client(config, logger)
            mock_ssh.from_config.assert_called_once_with(config, logger)

    def test_rest_transport_selection(self) -> None:
        """REST transport selected when config specifies rest."""
        config = MagicMock()
        config.router_transport = "rest"
        logger = MagicMock(spec=logging.Logger)

        # RouterOSREST is imported inside get_router_client, so patch at source
        with patch("wanctl.routeros_rest.RouterOSREST") as mock_rest:
            mock_rest.from_config.return_value = MagicMock()
            get_router_client(config, logger)
            mock_rest.from_config.assert_called_once_with(config, logger)

    def test_invalid_transport_raises(self) -> None:
        """Invalid transport raises ValueError."""
        config = MagicMock()
        config.router_transport = "invalid"
        logger = MagicMock(spec=logging.Logger)

        with pytest.raises(ValueError, match="Unsupported router transport"):
            get_router_client(config, logger)


class TestFailoverRouterClient:
    """Tests for FailoverRouterClient automatic failover behavior.

    SAFETY INVARIANT: REST API failure must automatically fall back to SSH.
    This prevents daemon crashes when REST API is temporarily unavailable.
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock config for tests."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger for tests."""
        return MagicMock(spec=logging.Logger)

    def test_rest_failure_triggers_ssh_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """REST API failure should trigger automatic SSH fallback.

        This is the primary safety test (TEST-03). It proves:
        1. ConnectionError on REST triggers failover
        2. SSH client is created as fallback
        3. Command succeeds via SSH
        4. Warning is logged for operational visibility
        """
        # Setup: REST client that fails, SSH client that succeeds
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST connection failed")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "output", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            # First call creates REST (fails), second creates SSH (succeeds)
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            rc, stdout, stderr = client.run_cmd("/queue tree print")

            assert rc == 0
            assert stdout == "output"
            # Verify SSH was used as fallback
            mock_ssh.run_cmd.assert_called_once()
            # Verify warning was logged
            mock_logger.warning.assert_called()

    def test_timeout_triggers_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """TimeoutError should also trigger SSH fallback."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = TimeoutError("REST timeout")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "success", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            rc, stdout, stderr = client.run_cmd("/interface print")

            assert rc == 0
            mock_ssh.run_cmd.assert_called_once()

    def test_oserror_triggers_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """OSError (socket errors) should trigger SSH fallback."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = OSError("Network unreachable")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            rc, stdout, stderr = client.run_cmd("/system identity print")

            assert rc == 0
            mock_ssh.run_cmd.assert_called_once()

    def test_subsequent_calls_use_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """After failover, subsequent calls use fallback transport.

        Once failover occurs, the client should stick to SSH until close().
        This avoids repeated REST failures and logging noise.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)

            # First call triggers failover
            client.run_cmd("/first")
            # Second call should use fallback directly
            client.run_cmd("/second")
            # Third call should also use fallback
            client.run_cmd("/third")

            # SSH should have been called 3 times
            assert mock_ssh.run_cmd.call_count == 3
            # REST should only have been tried once
            assert mock_rest.run_cmd.call_count == 1

    def test_primary_success_no_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """When primary succeeds, fallback is never created."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.return_value = (0, "rest output", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.return_value = mock_rest

            client = get_router_client_with_failover(mock_config, mock_logger)
            rc, stdout, stderr = client.run_cmd("/queue tree print")

            assert rc == 0
            assert stdout == "rest output"
            # Only one transport created (REST)
            assert mock_create.call_count == 1

    def test_close_closes_both_transports(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """close() should close both primary and fallback clients."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            client.run_cmd("/test")  # Triggers failover
            client.close()

            mock_rest.close.assert_called_once()
            mock_ssh.close.assert_called_once()

    def test_close_safe_when_no_clients_created(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """close() should be safe when no clients were created."""
        client = get_router_client_with_failover(mock_config, mock_logger)
        # Should not raise
        client.close()

    def test_failover_logs_warning(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Failover should log warning with transport names."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST failed")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            client.run_cmd("/test")

            # Verify warning mentions both transports
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any(
                "rest" in call.lower() and "ssh" in call.lower()
                for call in warning_calls
            )

    def test_custom_transport_order(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Can specify SSH as primary and REST as fallback."""
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = ConnectionError("SSH down")

        mock_rest = MagicMock()
        mock_rest.run_cmd.return_value = (0, "rest ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.side_effect = [mock_ssh, mock_rest]

            # SSH as primary, REST as fallback
            client = get_router_client_with_failover(
                mock_config, mock_logger, primary="ssh", fallback="rest"
            )
            rc, stdout, stderr = client.run_cmd("/test")

            assert rc == 0
            assert stdout == "rest ok"
            # Verify SSH was tried first, then REST
            assert mock_ssh.run_cmd.call_count == 1
            mock_rest.run_cmd.assert_called_once()

    def test_fallback_client_lazy_creation(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Fallback client is only created when primary fails.

        Ensures we don't waste resources creating SSH connections
        when REST works fine.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport") as mock_create:
            mock_create.return_value = mock_rest

            client = get_router_client_with_failover(mock_config, mock_logger)

            # Multiple successful calls
            client.run_cmd("/cmd1")
            client.run_cmd("/cmd2")
            client.run_cmd("/cmd3")

            # Only one transport created (REST), no fallback
            assert mock_create.call_count == 1
            # Verify it was the primary (rest)
            mock_create.assert_called_once_with("rest", mock_config, mock_logger)


class TestFailoverRouterClientInit:
    """Tests for FailoverRouterClient initialization."""

    def test_default_transports(self) -> None:
        """Default primary is REST, default fallback is SSH."""
        config = MagicMock()
        logger = MagicMock(spec=logging.Logger)

        client = FailoverRouterClient(config, logger)

        assert client.primary_transport == "rest"
        assert client.fallback_transport == "ssh"

    def test_custom_transports(self) -> None:
        """Can customize primary and fallback transports."""
        config = MagicMock()
        logger = MagicMock(spec=logging.Logger)

        client = FailoverRouterClient(
            config, logger, primary_transport="ssh", fallback_transport="rest"
        )

        assert client.primary_transport == "ssh"
        assert client.fallback_transport == "rest"

    def test_initial_state(self) -> None:
        """Initial state: no clients created, not using fallback."""
        config = MagicMock()
        logger = MagicMock(spec=logging.Logger)

        client = FailoverRouterClient(config, logger)

        assert client._primary_client is None
        assert client._fallback_client is None
        assert client._using_fallback is False

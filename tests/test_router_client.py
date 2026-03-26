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
    clear_router_password,
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
        config = MagicMock()
        config.router_transport = "rest"
        return config

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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
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

    def test_failover_logs_warning(self, mock_config: MagicMock, mock_logger: MagicMock) -> None:
        """Failover should log warning with transport names."""
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST failed")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ok", "")

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
            mock_create.side_effect = [mock_rest, mock_ssh]

            client = get_router_client_with_failover(mock_config, mock_logger)
            client.run_cmd("/test")

            # Verify warning mentions both transports
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("rest" in call.lower() and "ssh" in call.lower() for call in warning_calls)

    def test_custom_transport_order_via_config(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Config.router_transport="ssh" uses SSH as primary, REST as fallback.

        LOOP-02/CLEAN-04: config.router_transport is authoritative for
        transport selection. The factory reads it instead of hardcoded defaults.
        """
        mock_config.router_transport = "ssh"
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = ConnectionError("SSH down")

        mock_rest = MagicMock()
        mock_rest.run_cmd.return_value = (0, "rest ok", "")

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
            mock_create.side_effect = [mock_ssh, mock_rest]

            # Factory reads config.router_transport="ssh" -> SSH primary, REST fallback
            client = get_router_client_with_failover(mock_config, mock_logger)
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

        with patch("wanctl.router_client._create_transport_with_password") as mock_create:
            mock_create.return_value = mock_rest

            client = get_router_client_with_failover(mock_config, mock_logger)

            # Multiple successful calls
            client.run_cmd("/cmd1")
            client.run_cmd("/cmd2")
            client.run_cmd("/cmd3")

            # Only one transport created (REST), no fallback
            assert mock_create.call_count == 1
            # Verify it was the primary (rest) -- password is the resolved value
            call_args = mock_create.call_args[0]
            assert call_args[0] == "rest"
            assert call_args[1] is mock_config


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


class TestFactoryConfigDriven:
    """Tests for get_router_client_with_failover reading config.router_transport.

    LOOP-02/CLEAN-04: The factory must read config.router_transport to determine
    primary transport. Fallback is automatically the opposite transport.
    """

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger for tests."""
        return MagicMock(spec=logging.Logger)

    def test_factory_reads_config_transport_rest(self, mock_logger: MagicMock) -> None:
        """config.router_transport="rest" -> primary="rest", fallback="ssh"."""
        config = MagicMock()
        config.router_transport = "rest"

        client = get_router_client_with_failover(config, mock_logger)

        assert client.primary_transport == "rest"
        assert client.fallback_transport == "ssh"

    def test_factory_reads_config_transport_ssh(self, mock_logger: MagicMock) -> None:
        """config.router_transport="ssh" -> primary="ssh", fallback="rest"."""
        config = MagicMock()
        config.router_transport = "ssh"

        client = get_router_client_with_failover(config, mock_logger)

        assert client.primary_transport == "ssh"
        assert client.fallback_transport == "rest"

    def test_factory_no_transport_attr_defaults_rest(self, mock_logger: MagicMock) -> None:
        """Config without router_transport attr defaults to primary="rest"."""
        # Use a plain object without router_transport attribute
        config = type("Config", (), {})()

        client = get_router_client_with_failover(config, mock_logger)

        assert client.primary_transport == "rest"
        assert client.fallback_transport == "ssh"

    def test_factory_no_primary_fallback_params(self, mock_logger: MagicMock) -> None:
        """Factory no longer accepts primary/fallback params -- config is authoritative."""
        config = MagicMock()
        config.router_transport = "rest"

        # Factory should only accept (config, logger) -- no primary/fallback kwargs
        import inspect

        sig = inspect.signature(get_router_client_with_failover)
        param_names = list(sig.parameters.keys())
        assert "primary" not in param_names, "Factory should not accept 'primary' param"
        assert "fallback" not in param_names, "Factory should not accept 'fallback' param"


class TestFailoverReprobe:
    """Tests for periodic re-probe of primary transport after failover.

    LOOP-03: After failover to SSH, client periodically re-probes REST.
    When REST recovers, client transparently restores it as primary.
    Re-probe uses backoff: 30s initial, 2x factor, 300s max.
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock config for tests."""
        config = MagicMock()
        config.router_transport = "rest"
        return config

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger for tests."""
        return MagicMock(spec=logging.Logger)

    def _create_failover_client_in_fallback(
        self,
        mock_config: MagicMock,
        mock_logger: MagicMock,
        mock_create: MagicMock,
        primary_client: MagicMock,
        fallback_client: MagicMock,
    ) -> FailoverRouterClient:
        """Helper: create client and trigger failover to put it in fallback mode."""
        mock_create.side_effect = [primary_client, fallback_client]
        client = get_router_client_with_failover(mock_config, mock_logger)
        # Trigger failover
        client.run_cmd("/trigger-failover")
        return client

    def test_reprobe_after_interval(self, mock_config: MagicMock, mock_logger: MagicMock) -> None:
        """After 30s in fallback mode, run_cmd re-probes primary transport.

        Uses time.monotonic to track interval. After interval elapses,
        the next run_cmd should attempt primary before falling back.
        """
        mock_rest = MagicMock()
        # First call fails (triggers failover), re-probe also fails
        mock_rest.run_cmd.side_effect = [
            ConnectionError("REST down"),
            ConnectionError("REST still down"),
        ]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            # Time sequence: failover at t=100, then run_cmd at t=131 (31s later, > 30s interval)
            mock_time.monotonic.side_effect = [
                100.0,  # failover: self._last_probe_time = 100.0
                131.0,  # run_cmd: check interval -> 131 - 100 = 31 > 30, probe
                131.0,  # _try_restore_primary: self._last_probe_time = now
            ]

            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            # Reset call counts after failover setup
            mock_rest.run_cmd.reset_mock()
            mock_rest.run_cmd.side_effect = ConnectionError("REST still down")

            # Create a fresh primary client for re-probe
            reprobe_primary = MagicMock()
            reprobe_primary.run_cmd.side_effect = ConnectionError("REST still down")
            mock_create.side_effect = [reprobe_primary]

            # This call should attempt re-probe (31s > 30s interval)
            rc, stdout, stderr = client.run_cmd("/test-reprobe")

            assert rc == 0
            assert stdout == "ssh ok"
            # Primary was re-probed (new client created and tried)
            reprobe_primary.run_cmd.assert_called_once()

    def test_reprobe_restores_primary(self, mock_config: MagicMock, mock_logger: MagicMock) -> None:
        """Successful re-probe restores primary, subsequent calls use primary.

        When primary succeeds on re-probe, _using_fallback is set to False
        and future calls go through primary without re-probing.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [
                100.0,  # failover timestamp
                131.0,  # run_cmd check -> 31s elapsed > 30s
                131.0,  # _try_restore_primary timestamp update
            ]

            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            # Re-probe primary succeeds
            reprobe_primary = MagicMock()
            reprobe_primary.run_cmd.return_value = (0, "rest restored", "")
            mock_create.side_effect = [reprobe_primary]

            rc, stdout, stderr = client.run_cmd("/test-restore")

            assert rc == 0
            assert stdout == "rest restored"
            assert client._using_fallback is False

            # Subsequent call uses primary (no re-probe needed)
            reprobe_primary.run_cmd.return_value = (0, "rest again", "")
            rc2, stdout2, _ = client.run_cmd("/next-cmd")
            assert stdout2 == "rest again"

    def test_reprobe_failure_stays_on_fallback(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Failed re-probe stays on fallback, command succeeds via SSH.

        When re-probe fails, the actual command still executes on fallback.
        No exception propagated to caller.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [
                100.0,  # failover
                131.0,  # run_cmd check -> probe due
                131.0,  # _try_restore_primary timestamp
            ]

            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            # Re-probe fails
            reprobe_primary = MagicMock()
            reprobe_primary.run_cmd.side_effect = ConnectionError("REST still down")
            mock_create.side_effect = [reprobe_primary]

            rc, stdout, stderr = client.run_cmd("/test-stays-fallback")

            assert rc == 0
            assert stdout == "ssh ok"
            assert client._using_fallback is True

    def test_reprobe_backoff(self, mock_config: MagicMock, mock_logger: MagicMock) -> None:
        """After failed probe, interval doubles: 30 -> 60 -> 120 -> 240 -> 300 (cap).

        Backoff prevents hammering a broken REST API.
        """
        from wanctl.router_client import (
            _REPROBE_INITIAL_INTERVAL,
            _REPROBE_MAX_INTERVAL,
        )

        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            # Failover
            mock_time.monotonic.return_value = 100.0
            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            assert client._probe_interval == _REPROBE_INITIAL_INTERVAL  # 30

            # First failed re-probe: 30 -> 60
            mock_time.monotonic.return_value = 200.0  # way past interval
            reprobe1 = MagicMock()
            reprobe1.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe1]
            client.run_cmd("/probe1")
            assert client._probe_interval == 60.0

            # Second failed re-probe: 60 -> 120
            mock_time.monotonic.return_value = 300.0
            reprobe2 = MagicMock()
            reprobe2.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe2]
            client.run_cmd("/probe2")
            assert client._probe_interval == 120.0

            # Third: 120 -> 240
            mock_time.monotonic.return_value = 500.0
            reprobe3 = MagicMock()
            reprobe3.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe3]
            client.run_cmd("/probe3")
            assert client._probe_interval == 240.0

            # Fourth: 240 -> 300 (capped)
            mock_time.monotonic.return_value = 800.0
            reprobe4 = MagicMock()
            reprobe4.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe4]
            client.run_cmd("/probe4")
            assert client._probe_interval == _REPROBE_MAX_INTERVAL  # 300

            # Fifth: stays at 300 (already capped)
            mock_time.monotonic.return_value = 1200.0
            reprobe5 = MagicMock()
            reprobe5.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe5]
            client.run_cmd("/probe5")
            assert client._probe_interval == 300.0

    def test_reprobe_success_resets_backoff(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """After restoration, probe interval resets to initial 30s.

        If primary fails again later, backoff starts fresh.
        """
        from wanctl.router_client import _REPROBE_INITIAL_INTERVAL

        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            # Failover
            mock_time.monotonic.return_value = 100.0
            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            # Failed re-probe to increase interval
            mock_time.monotonic.return_value = 200.0
            reprobe_fail = MagicMock()
            reprobe_fail.run_cmd.side_effect = ConnectionError("fail")
            mock_create.side_effect = [reprobe_fail]
            client.run_cmd("/fail-probe")
            assert client._probe_interval == 60.0  # backed off

            # Successful re-probe restores primary and resets interval
            mock_time.monotonic.return_value = 300.0
            reprobe_ok = MagicMock()
            reprobe_ok.run_cmd.return_value = (0, "rest back", "")
            mock_create.side_effect = [reprobe_ok]
            client.run_cmd("/success-probe")

            assert client._using_fallback is False
            assert client._probe_interval == _REPROBE_INITIAL_INTERVAL  # reset to 30

    def test_no_reprobe_before_interval(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Within interval window, primary is NOT retried -- fallback used directly.

        This prevents unnecessary probing on every single run_cmd call.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            # Failover at t=100
            mock_time.monotonic.return_value = 100.0
            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            mock_ssh.run_cmd.reset_mock()
            create_call_count_after_failover = mock_create.call_count

            # Call at t=110 (10s later, < 30s interval) -- should NOT re-probe
            mock_time.monotonic.return_value = 110.0
            rc, stdout, stderr = client.run_cmd("/within-interval")

            assert rc == 0
            assert stdout == "ssh ok"
            # No new transport created (no re-probe attempt)
            assert mock_create.call_count == create_call_count_after_failover
            mock_ssh.run_cmd.assert_called_once()

    def test_reprobe_does_not_disrupt_command(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Even if probe fails, the actual command succeeds via fallback.

        No exception propagated to caller from failed re-probe.
        The command result comes from fallback, not the failed probe.
        """
        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "fallback result", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create,
            patch("wanctl.router_client._time") as mock_time,
        ):
            mock_time.monotonic.return_value = 100.0
            client = self._create_failover_client_in_fallback(
                mock_config, mock_logger, mock_create, mock_rest, mock_ssh
            )

            mock_ssh.run_cmd.reset_mock()

            # Re-probe fails with various error types
            mock_time.monotonic.return_value = 200.0
            reprobe = MagicMock()
            reprobe.run_cmd.side_effect = TimeoutError("REST timeout")
            mock_create.side_effect = [reprobe]

            # Command still succeeds via fallback
            rc, stdout, stderr = client.run_cmd("/important-cmd")

            assert rc == 0
            assert stdout == "fallback result"
            mock_ssh.run_cmd.assert_called_once_with("/important-cmd", capture=False, timeout=None)


class TestClearRouterPassword:
    """Tests for clear_router_password helper and FailoverRouterClient password resolution.

    SECR-01: Plaintext passwords must not linger on Config objects after
    router clients are constructed.
    """

    def test_clear_router_password_sets_empty(self) -> None:
        """After clear_router_password(config), config.router_password == ''."""
        config = MagicMock()
        config.router_password = "supersecret"  # pragma: allowlist secret

        clear_router_password(config)

        assert config.router_password == ""

    def test_clear_router_password_attr_still_exists(self) -> None:
        """After clearing, hasattr(config, 'router_password') is True but value is ''."""
        config = MagicMock()
        config.router_password = "supersecret"  # pragma: allowlist secret

        clear_router_password(config)

        assert hasattr(config, "router_password")
        assert config.router_password == ""

    def test_clear_router_password_no_attr(self) -> None:
        """clear_router_password is safe when config has no router_password attr."""
        config = type("Config", (), {})()

        # Should not raise
        clear_router_password(config)

    def test_failover_client_resolves_password_at_init(self) -> None:
        """FailoverRouterClient stores resolved password at __init__ time."""
        config = MagicMock()
        config.router_transport = "rest"
        config.router_password = "init_pass"  # pragma: allowlist secret
        logger = MagicMock(spec=logging.Logger)

        client = FailoverRouterClient(config, logger)

        assert client._resolved_password == "init_pass"

    def test_failover_client_resolves_env_var_password(self) -> None:
        """FailoverRouterClient resolves ${ENV_VAR} syntax at init."""
        config = MagicMock()
        config.router_transport = "rest"
        config.router_password = "${TEST_ROUTER_PW}"
        logger = MagicMock(spec=logging.Logger)

        with patch.dict("os.environ", {"TEST_ROUTER_PW": "env_resolved"}):
            client = FailoverRouterClient(config, logger)

        assert client._resolved_password == "env_resolved"

    def test_failover_client_reprobe_after_password_cleared(self) -> None:
        """Re-probe creates working transport even after config password is cleared.

        This is the key SECR-01 test: password is eagerly resolved at init,
        so clearing config.router_password does not break re-probe.
        """
        config = MagicMock()
        config.router_transport = "rest"
        config.router_host = "10.10.99.1"
        config.router_user = "admin"
        config.router_password = "secret_pass"  # pragma: allowlist secret
        config.router_port = 443
        config.router_verify_ssl = True
        config.timeout_ssh_command = 15
        logger = MagicMock(spec=logging.Logger)

        mock_rest = MagicMock()
        mock_rest.run_cmd.side_effect = ConnectionError("REST down")

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "ssh ok", "")

        with (
            patch("wanctl.router_client._create_transport_with_password") as mock_create_pw,
            patch("wanctl.router_client._time") as mock_time,
        ):
            mock_create_pw.side_effect = [mock_rest, mock_ssh]
            mock_time.monotonic.return_value = 100.0

            client = FailoverRouterClient(config, logger)
            # Trigger failover
            client.run_cmd("/trigger")

            # Clear the config password (simulating daemon behavior)
            clear_router_password(config)
            assert config.router_password == ""

            # Re-probe: should still work because password was resolved at init
            mock_time.monotonic.return_value = 200.0
            reprobe_rest = MagicMock()
            reprobe_rest.run_cmd.return_value = (0, "rest restored", "")
            mock_create_pw.side_effect = [reprobe_rest]

            rc, stdout, stderr = client.run_cmd("/after-clear")

            assert rc == 0
            assert stdout == "rest restored"
            # Verify the resolved password was used, not the cleared config password
            for call_args in mock_create_pw.call_args_list:
                if call_args[0][0] == "rest":  # transport type
                    assert call_args[0][2] == "secret_pass"  # password arg

    def test_get_router_client_unaffected(self) -> None:
        """get_router_client (non-failover) continues to work normally.

        It eagerly creates a transport, so password clearing is not relevant.
        """
        config = MagicMock()
        config.router_transport = "rest"
        logger = MagicMock(spec=logging.Logger)

        with patch("wanctl.routeros_rest.RouterOSREST") as mock_rest:
            mock_rest.from_config.return_value = MagicMock()
            client = get_router_client(config, logger)
            mock_rest.from_config.assert_called_once_with(config, logger)
            assert client is not None

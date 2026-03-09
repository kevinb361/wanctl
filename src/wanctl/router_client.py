"""Router client factory for wanctl.

This module provides a unified interface for selecting the appropriate
router communication method based on configuration.

Supported transports:
- rest: REST API via HTTPS (default) - uses password authentication, 2x faster
- ssh: SSH via paramiko - uses SSH keys

Usage:
    from wanctl.router_client import get_router_client

    # From config
    client = get_router_client(config, logger)

    # Execute command
    rc, stdout, stderr = client.run_cmd("/queue tree print")

    # Clean up
    client.close()

Failover usage:
    from wanctl.router_client import get_router_client_with_failover

    # Client with automatic REST-to-SSH failover
    client = get_router_client_with_failover(config, logger)

    # If REST fails, automatically retries with SSH
    rc, stdout, stderr = client.run_cmd("/queue tree print")

Configuration (in YAML):
    router:
      transport: "rest"  # or "ssh"
      host: "10.10.99.1"
      user: "admin"

      # For SSH transport
      ssh_key: "/etc/wanctl/ssh/router.key"

      # For REST transport
      password: "${ROUTER_PASSWORD}"  # env var reference
      port: 443
      verify_ssl: true
"""

import logging
import time as _time
from typing import TYPE_CHECKING, Any, Union

from wanctl.routeros_ssh import RouterOSSSH

if TYPE_CHECKING:
    from wanctl.routeros_rest import RouterOSREST

# Type alias for router clients
RouterClient = Union[RouterOSSSH, "RouterOSREST"]


def get_router_client(config: Any, logger: logging.Logger) -> RouterClient:
    """Factory function to create the appropriate router client.

    Selects between SSH (paramiko) and REST API based on config.

    Args:
        config: Configuration object with router settings.
                Must have router transport type (defaults to 'rest').
        logger: Logger instance

    Returns:
        RouterOSSSH or RouterOSREST instance

    Raises:
        ValueError: If transport type is not supported
    """
    # Get transport type from config
    transport = getattr(config, "router_transport", "rest")

    if transport == "ssh":
        logger.debug("Using SSH transport (paramiko)")
        return RouterOSSSH.from_config(config, logger)

    elif transport == "rest":
        from wanctl.routeros_rest import RouterOSREST

        logger.debug("Using REST API transport")
        return RouterOSREST.from_config(config, logger)

    else:
        raise ValueError(f"Unsupported router transport: {transport}")


def _create_transport(transport: str, config: Any, logger: logging.Logger) -> RouterClient:
    """Create transport client by name.

    Internal helper for FailoverRouterClient.

    Args:
        transport: Transport type ("ssh" or "rest")
        config: Configuration object with router settings
        logger: Logger instance

    Returns:
        RouterClient instance

    Raises:
        ValueError: If transport type is not supported
    """
    if transport == "ssh":
        return RouterOSSSH.from_config(config, logger)
    elif transport == "rest":
        from wanctl.routeros_rest import RouterOSREST

        return RouterOSREST.from_config(config, logger)
    else:
        raise ValueError(f"Unsupported transport: {transport}")


# Re-probe constants: after failover, periodically try primary transport
_REPROBE_INITIAL_INTERVAL = 30.0  # seconds before first re-probe
_REPROBE_MAX_INTERVAL = 300.0  # max backoff (5 minutes)
_REPROBE_BACKOFF_FACTOR = 2.0


class FailoverRouterClient:
    """Router client wrapper with automatic REST-to-SSH failover.

    Wraps primary transport (REST) and falls back to secondary (SSH) on failure.
    Logs transport switches for operational visibility.

    This provides resilience against transient REST API failures without
    crashing the daemon. Once failover occurs, subsequent commands use
    the fallback transport until close() is called.

    Usage:
        client = get_router_client_with_failover(config, logger)
        rc, stdout, stderr = client.run_cmd("/queue tree print")

    Failover triggers:
        - ConnectionError: Network unreachable, connection refused
        - TimeoutError: REST API timeout
        - OSError: Other socket/network errors
    """

    def __init__(
        self,
        config: Any,
        logger: logging.Logger,
        primary_transport: str = "rest",
        fallback_transport: str = "ssh",
    ):
        """Initialize failover router client.

        Args:
            config: Configuration object with router settings
            logger: Logger instance
            primary_transport: Primary transport ("rest" or "ssh"), default "rest"
            fallback_transport: Fallback transport ("rest" or "ssh"), default "ssh"
        """
        self.config = config
        self.logger = logger
        self.primary_transport = primary_transport
        self.fallback_transport = fallback_transport
        self._primary_client: RouterClient | None = None
        self._fallback_client: RouterClient | None = None
        self._using_fallback = False
        # Re-probe state: track when to retry primary after failover
        self._last_probe_time: float = 0.0
        self._probe_interval: float = _REPROBE_INITIAL_INTERVAL

    def _get_primary(self) -> RouterClient:
        """Get or create primary transport client."""
        if self._primary_client is None:
            self._primary_client = _create_transport(
                self.primary_transport, self.config, self.logger
            )
        return self._primary_client

    def _get_fallback(self) -> RouterClient:
        """Get or create fallback transport client."""
        if self._fallback_client is None:
            self.logger.warning(
                f"Creating fallback {self.fallback_transport} transport "
                f"(primary {self.primary_transport} failed)"
            )
            self._fallback_client = _create_transport(
                self.fallback_transport, self.config, self.logger
            )
        return self._fallback_client

    def _try_restore_primary(
        self, cmd: str, capture: bool, timeout: int | None
    ) -> tuple[int, str, str] | None:
        """Attempt to restore primary transport during fallback.

        Returns command result if primary succeeded, None if probe failed or not due.
        """
        now = _time.monotonic()
        if now - self._last_probe_time < self._probe_interval:
            return None  # Not time yet

        self._last_probe_time = now

        # Close stale primary client (may have old broken connection)
        if self._primary_client is not None:
            try:
                self._primary_client.close()
            except Exception:
                pass
            self._primary_client = None

        try:
            result = self._get_primary().run_cmd(cmd, capture=capture, timeout=timeout)
            # Primary succeeded -- restore it
            self.logger.info(
                f"Primary transport ({self.primary_transport}) restored successfully"
            )
            self._using_fallback = False
            self._probe_interval = _REPROBE_INITIAL_INTERVAL  # reset backoff
            return result
        except (ConnectionError, TimeoutError, OSError) as e:
            self.logger.debug(
                f"Primary re-probe failed: {e}. "
                f"Next probe in {self._probe_interval * _REPROBE_BACKOFF_FACTOR:.0f}s"
            )
            # Backoff probe interval
            self._probe_interval = min(
                self._probe_interval * _REPROBE_BACKOFF_FACTOR,
                _REPROBE_MAX_INTERVAL,
            )
            # Primary client is broken, clear it
            if self._primary_client is not None:
                try:
                    self._primary_client.close()
                except Exception:
                    pass
                self._primary_client = None
            return None

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        """Execute command with automatic failover.

        Args:
            cmd: RouterOS command to execute
            capture: Whether to capture output (passed to underlying transport)
            timeout: Command timeout in seconds (passed to underlying transport)

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if self._using_fallback:
            # Periodically try to restore primary
            result = self._try_restore_primary(cmd, capture, timeout)
            if result is not None:
                return result
            return self._get_fallback().run_cmd(cmd, capture=capture, timeout=timeout)

        try:
            return self._get_primary().run_cmd(cmd, capture=capture, timeout=timeout)
        except (ConnectionError, TimeoutError, OSError) as e:
            self.logger.warning(
                f"Primary transport ({self.primary_transport}) failed: {e}. "
                f"Switching to fallback ({self.fallback_transport})"
            )
            self._using_fallback = True
            self._last_probe_time = _time.monotonic()  # start probe timer
            self._probe_interval = _REPROBE_INITIAL_INTERVAL  # reset interval
            return self._get_fallback().run_cmd(cmd, capture=capture, timeout=timeout)

    def close(self) -> None:
        """Close all transport connections.

        Safe to call multiple times or when clients not created.
        """
        if self._primary_client:
            self._primary_client.close()
        if self._fallback_client:
            self._fallback_client.close()


def get_router_client_with_failover(
    config: Any,
    logger: logging.Logger,
) -> FailoverRouterClient:
    """Factory for router client with automatic failover.

    Creates a FailoverRouterClient that reads config.router_transport to
    determine the primary transport. Fallback is automatically the opposite.

    Config.router_transport controls transport selection:
    - "rest" (default): REST primary, SSH fallback
    - "ssh": SSH primary, REST fallback

    Args:
        config: Configuration object with router_transport attribute
                (defaults to "rest" if attribute missing)
        logger: Logger instance

    Returns:
        FailoverRouterClient with automatic failover capability
    """
    primary = getattr(config, "router_transport", "rest")
    fallback = "ssh" if primary == "rest" else "rest"
    return FailoverRouterClient(config, logger, primary, fallback)


__all__ = [
    "get_router_client",
    "get_router_client_with_failover",
    "FailoverRouterClient",
    "RouterClient",
    "_REPROBE_INITIAL_INTERVAL",
    "_REPROBE_MAX_INTERVAL",
    "_REPROBE_BACKOFF_FACTOR",
]

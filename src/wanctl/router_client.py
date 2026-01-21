"""Router client factory for wanctl.

This module provides a unified interface for selecting the appropriate
router communication method based on configuration.

Supported transports:
- ssh: SSH via paramiko (default) - uses SSH keys
- rest: REST API via HTTPS - uses password authentication

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
      transport: "ssh"  # or "rest"
      host: "10.10.99.1"
      user: "admin"

      # For SSH transport
      ssh_key: "/etc/wanctl/ssh/router.key"

      # For REST transport
      password: "${ROUTER_PASSWORD}"  # env var reference
      port: 443
      verify_ssl: false
"""

import logging
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
                Must have router transport type (defaults to 'ssh').
        logger: Logger instance

    Returns:
        RouterOSSSH or RouterOSREST instance

    Raises:
        ValueError: If transport type is not supported
    """
    # Get transport type from config
    transport = getattr(config, "router_transport", "ssh")

    if transport == "ssh":
        logger.debug("Using SSH transport (paramiko)")
        return RouterOSSSH.from_config(config, logger)

    elif transport == "rest":
        from wanctl.routeros_rest import RouterOSREST

        logger.debug("Using REST API transport")
        return RouterOSREST.from_config(config, logger)

    else:
        raise ValueError(f"Unsupported router transport: {transport}")


def _create_transport(
    transport: str, config: Any, logger: logging.Logger
) -> RouterClient:
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

    def run_cmd(self, cmd: str) -> tuple[int, str, str]:
        """Execute command with automatic failover.

        Args:
            cmd: RouterOS command to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if self._using_fallback:
            return self._get_fallback().run_cmd(cmd)

        try:
            return self._get_primary().run_cmd(cmd)
        except (ConnectionError, TimeoutError, OSError) as e:
            self.logger.warning(
                f"Primary transport ({self.primary_transport}) failed: {e}. "
                f"Switching to fallback ({self.fallback_transport})"
            )
            self._using_fallback = True
            return self._get_fallback().run_cmd(cmd)

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
    primary: str = "rest",
    fallback: str = "ssh",
) -> FailoverRouterClient:
    """Factory for router client with automatic failover.

    Creates a FailoverRouterClient that wraps the primary transport and
    automatically switches to the fallback transport on connection failures.

    Args:
        config: Configuration object with router settings
        logger: Logger instance
        primary: Primary transport ("rest" or "ssh"), default "rest"
        fallback: Fallback transport ("rest" or "ssh"), default "ssh"

    Returns:
        FailoverRouterClient with automatic failover capability
    """
    return FailoverRouterClient(config, logger, primary, fallback)


__all__ = [
    "get_router_client",
    "get_router_client_with_failover",
    "FailoverRouterClient",
    "RouterClient",
]

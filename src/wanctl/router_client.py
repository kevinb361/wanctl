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


__all__ = ["get_router_client", "RouterClient"]

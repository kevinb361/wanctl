"""Router backend abstraction for wanctl.

Factory function selects backend based on config.router_transport:
- "rest" or "ssh": RouterOSBackend (Mikrotik)
- "linux-cake": LinuxCakeBackend (local tc CAKE)
"""

from typing import Any

from wanctl.backends.base import RouterBackend
from wanctl.backends.linux_cake import LinuxCakeBackend
from wanctl.backends.routeros import RouterOSBackend


def get_backend(config: Any) -> RouterBackend:
    """Factory function to create the appropriate backend.

    Routes on config.router_transport attribute:
    - "rest" or "ssh" -> RouterOSBackend
    - "linux-cake" -> LinuxCakeBackend

    Args:
        config: Configuration object. Must have router_transport attribute
                (defaults to "rest" if missing).

    Returns:
        RouterBackend instance for the configured transport.

    Raises:
        ValueError: If transport is not supported.
    """
    transport = getattr(config, "router_transport", "rest")

    if transport in ("rest", "ssh"):
        return RouterOSBackend.from_config(config)
    elif transport == "linux-cake":
        return LinuxCakeBackend.from_config(config)
    else:
        raise ValueError(f"Unsupported router transport: {transport}")


__all__ = ["RouterBackend", "RouterOSBackend", "LinuxCakeBackend", "get_backend"]

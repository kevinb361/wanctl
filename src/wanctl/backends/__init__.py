"""Router backend abstraction for wanctl.

Factory function selects backend based on config.router_transport:
- "rest" or "ssh": RouterOSBackend (Mikrotik)
- "linux-cake": LinuxCakeBackend (local tc CAKE via subprocess)
- "linux-cake-netlink": NetlinkCakeBackend (local tc CAKE via pyroute2 netlink)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wanctl.backends.base import RouterBackend

if TYPE_CHECKING:
    from wanctl.config_base import BaseConfig
from wanctl.backends.linux_cake import LinuxCakeBackend
from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter
from wanctl.backends.netlink_cake import NetlinkCakeBackend
from wanctl.backends.routeros import RouterOSBackend


def get_backend(config: BaseConfig) -> RouterBackend:
    """Factory function to create the appropriate backend.

    Routes on config.router_transport attribute:
    - "rest" or "ssh" -> RouterOSBackend
    - "linux-cake" -> LinuxCakeBackend
    - "linux-cake-netlink" -> NetlinkCakeBackend

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
    if transport == "linux-cake":
        return LinuxCakeBackend.from_config(config)
    if transport == "linux-cake-netlink":
        return NetlinkCakeBackend.from_config(config)
    raise ValueError(f"Unsupported router transport: {transport}")


__all__ = [
    "RouterBackend",
    "RouterOSBackend",
    "LinuxCakeBackend",
    "NetlinkCakeBackend",
    "LinuxCakeAdapter",
    "get_backend",
]

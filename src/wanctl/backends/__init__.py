"""Router backend abstraction for wanctl.

This module provides an abstract interface for router backends,
allowing wanctl to support different router platforms.

Currently supported:
- RouterOS (Mikrotik)

Future backends can be added by implementing the RouterBackend interface.

Usage:
    from wanctl.backends import get_backend

    backend = get_backend(config)
    backend.set_bandwidth("WAN-Download-1", 500_000_000)
    stats = backend.get_queue_stats("WAN-Download-1")
"""

from wanctl.backends.base import RouterBackend
from wanctl.backends.routeros import RouterOSBackend


def get_backend(config) -> RouterBackend:
    """Factory function to create the appropriate backend.

    Args:
        config: Configuration object containing router settings.
                Must have router.type field (defaults to 'routeros').

    Returns:
        RouterBackend instance for the configured router type.

    Raises:
        ValueError: If router type is not supported.
    """
    router_type = config.router.get('type', 'routeros')

    if router_type == 'routeros':
        return RouterOSBackend.from_config(config)
    else:
        raise ValueError(f"Unsupported router type: {router_type}")


__all__ = ['RouterBackend', 'RouterOSBackend', 'get_backend']

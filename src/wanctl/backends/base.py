"""Abstract base class for router backends.

This module defines the interface that all router backends must implement.
The goal is to support multiple router platforms (RouterOS, OpenWrt, pfSense, etc.)
without changing the core wanctl logic.

Design principles:
1. Keep the interface minimal - only methods actually needed by wanctl
2. Use primitive types for portability (int, str, dict, bool)
3. All methods must handle errors gracefully (return None/False on failure)
4. Logging is the backend's responsibility

To add a new backend:
1. Create a new module in cake/backends/ (e.g., openwrt.py)
2. Implement the RouterBackend abstract class
3. Add the backend to __init__.py get_backend() factory
4. Document config schema for the new router type
"""

import logging
from abc import ABC, abstractmethod


class RouterBackend(ABC):
    """Abstract base class for router backends.

    All router backends must implement these methods to be compatible
    with wanctl's autorate and steering systems.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the backend with an optional logger.

        Args:
            logger: Logger instance. If None, creates a null logger.
        """
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        """Set the max-limit on a queue/shaper.

        This is the primary control method - adjusts bandwidth limits
        based on congestion state.

        Args:
            queue: Queue/shaper name (e.g., "WAN-Download-1")
            rate_bps: Bandwidth limit in bits per second

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_bandwidth(self, queue: str) -> int | None:
        """Get the current max-limit on a queue/shaper.

        Used for verification after setting limits.

        Args:
            queue: Queue/shaper name

        Returns:
            Current bandwidth limit in bps, or None on error
        """
        pass

    @abstractmethod
    def get_queue_stats(self, queue: str) -> dict | None:
        """Get statistics for a queue (packets, bytes, drops, queue depth).

        Used by the multi-signal congestion detection system.

        Args:
            queue: Queue/shaper name

        Returns:
            Dict with keys: packets, bytes, dropped, queued_packets, queued_bytes
            Returns None on error.

        Example return:
            {
                'packets': 1234567,
                'bytes': 987654321,
                'dropped': 42,
                'queued_packets': 5,
                'queued_bytes': 7500
            }
        """
        pass

    @abstractmethod
    def enable_rule(self, comment: str) -> bool:
        """Enable a firewall/mangle rule by comment.

        Used by the steering system to activate traffic redirection.

        Args:
            comment: Rule comment/identifier

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def disable_rule(self, comment: str) -> bool:
        """Disable a firewall/mangle rule by comment.

        Used by the steering system to deactivate traffic redirection.

        Args:
            comment: Rule comment/identifier

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def is_rule_enabled(self, comment: str) -> bool | None:
        """Check if a firewall/mangle rule is enabled.

        Args:
            comment: Rule comment/identifier

        Returns:
            True if enabled, False if disabled, None if not found or error
        """
        pass

    def reset_queue_counters(self, queue: str) -> bool:
        """Reset statistics counters for a queue.

        Optional method - default implementation does nothing.
        Some routers may not support counter reset.

        Args:
            queue: Queue/shaper name

        Returns:
            True if successful or not implemented, False on error
        """
        return True

    def test_connection(self) -> bool:
        """Test connectivity to the router.

        Used for health checks and prerequisite validation.

        Returns:
            True if router is reachable and responding, False otherwise
        """
        # Default implementation - subclasses should override
        return True

    @classmethod
    def from_config(cls, config) -> 'RouterBackend':
        """Factory method to create backend from config object.

        Args:
            config: Configuration object with router settings

        Returns:
            Configured RouterBackend instance

        Raises:
            ValueError: If required config fields are missing
        """
        raise NotImplementedError("Subclasses must implement from_config")

"""Shared test factory functions and utilities.

Plain helper functions used across multiple test files. For pytest fixtures,
use conftest.py files instead.
"""

import socket
from unittest.mock import MagicMock


def find_free_port() -> int:
    """Find an available TCP port on localhost for test HTTP servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_host_result(
    address: str = "8.8.8.8",
    rtts: list[float] | None = None,
    is_alive: bool = True,
) -> MagicMock:
    """Build a mock icmplib Host object for testing.

    Args:
        address: IP address for the mock host.
        rtts: List of RTT values in ms. Defaults to [12.3].
        is_alive: Whether the host is reachable.

    Returns:
        MagicMock mimicking an icmplib Host.
    """
    host = MagicMock()
    host.address = address
    if rtts is None:
        rtts = [12.3]
    host.rtts = rtts
    host.min_rtt = min(rtts) if rtts else 0.0
    host.avg_rtt = sum(rtts) / len(rtts) if rtts else 0.0
    host.max_rtt = max(rtts) if rtts else 0.0
    host.packets_sent = len(rtts) if is_alive else 1
    host.packets_received = len(rtts) if is_alive else 0
    host.packet_loss = 0.0 if is_alive else 1.0
    host.is_alive = is_alive
    host.jitter = 0.0
    return host

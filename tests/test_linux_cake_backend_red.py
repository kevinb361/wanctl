"""RED phase: Minimal failing test for LinuxCakeBackend import and ABC compliance."""

from wanctl.backends.linux_cake import LinuxCakeBackend
from wanctl.backends.base import RouterBackend


def test_import():
    """LinuxCakeBackend can be imported."""
    assert LinuxCakeBackend is not None


def test_is_subclass():
    """LinuxCakeBackend is a RouterBackend subclass."""
    assert issubclass(LinuxCakeBackend, RouterBackend)


def test_instantiate():
    """LinuxCakeBackend can be instantiated with interface name."""
    backend = LinuxCakeBackend(interface="eth0")
    assert backend.interface == "eth0"

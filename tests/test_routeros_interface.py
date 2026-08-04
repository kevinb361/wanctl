"""Contracts for the native RouterOS command-dispatch adapter."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from wanctl.routeros_interface import RouterOS


def test_set_limits_keeps_retry_and_fallback_inside_watchdog_budget() -> None:
    router = object.__new__(RouterOS)
    router.config = SimpleNamespace(
        wan_name="fiber",
        queue_down="WAN-Download",
        queue_up="WAN-Upload",
    )
    router.logger = MagicMock()
    router.client = MagicMock()
    router.client.run_cmd.return_value = (0, "", "")

    assert router.set_limits("fiber", 500_000_000, 20_000_000) is True

    _cmd, kwargs = router.client.run_cmd.call_args
    assert kwargs == {"timeout": 5}

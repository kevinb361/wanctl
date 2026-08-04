"""REM-007 queued-rate recovery and connectivity-honesty regressions."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wanctl.autorate_continuous import (
    _notify_watchdog_with_distinction,
    _track_cycle_failures,
)
from wanctl.wan_controller import WANController


@pytest.fixture
def controller(mock_autorate_config):
    router = MagicMock()
    router.needs_rate_limiting = False
    router.set_limits.return_value = True
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=router,
            rtt_measurement=MagicMock(),
            logger=MagicMock(),
        )
    return ctrl


def _prime_pending(controller, dl=700_000_000, ul=30_000_000):
    controller.last_applied_dl_rate = 500_000_000
    controller.last_applied_ul_rate = 20_000_000
    controller.pending_rates.queue(dl, ul)


def test_direct_unreachable_queue_preserves_outage_without_router_io(controller):
    controller.router_connectivity.record_failure(ConnectionError("router down"))
    before = controller.router_connectivity.to_dict()

    applied = controller.apply_rate_changes_if_needed(500_000_000, 20_000_000)

    assert applied is True
    assert controller.router.set_limits.call_count == 0
    assert controller.pending_rates.has_pending() is True
    after = controller.router_connectivity.to_dict()
    for field in (
        "is_reachable",
        "consecutive_failures",
        "last_failure_type",
        "last_failure_time",
    ):
        assert after[field] == before[field]


def test_unreachable_cycle_uses_real_probe_and_recovers_on_contact(controller):
    controller.router_connectivity.record_failure(ConnectionError("router down"))
    controller.router.set_limits.return_value = True

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is False
    controller.router.set_limits.assert_called_once_with(
        wan="TestWAN", down_bps=500_000_000, up_bps=20_000_000
    )
    assert controller.pending_rates.has_pending() is False
    assert controller.router_connectivity.is_reachable is True
    assert controller.router_connectivity.consecutive_failures == 0
    info_messages = [str(call) for call in controller.logger.info.call_args_list]
    assert not any("after reconnection" in message for message in info_messages)


def test_reachable_unchanged_no_io_does_not_fabricate_success(controller):
    controller.last_applied_dl_rate = 500_000_000
    controller.last_applied_ul_rate = 20_000_000
    controller.router_connectivity.record_success = MagicMock(
        wraps=controller.router_connectivity.record_success
    )

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is False
    controller.router_connectivity.record_success.assert_not_called()
    controller.router.set_limits.assert_not_called()


def test_false_pending_replay_stays_pending_and_records_failure(controller):
    _prime_pending(controller)
    controller.router.set_limits.return_value = False

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is True
    assert controller.pending_rates.has_pending() is True
    assert controller.router_connectivity.is_reachable is False
    assert controller.router_connectivity.consecutive_failures == 1


def test_exception_pending_replay_stays_pending_and_records_failure(controller):
    _prime_pending(controller)
    controller.router.set_limits.side_effect = OSError("router write failed")

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is True
    assert controller.pending_rates.has_pending() is True
    assert controller.router_connectivity.is_reachable is False
    assert controller.router_connectivity.consecutive_failures == 1


def test_successful_pending_replay_clears_pending_and_records_contact(controller):
    _prime_pending(controller)
    controller.router_connectivity.record_success = MagicMock(
        wraps=controller.router_connectivity.record_success
    )

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is False
    assert controller.pending_rates.has_pending() is False
    controller.router_connectivity.record_success.assert_called_once_with()
    controller.router.set_limits.assert_called_once_with(
        wan="TestWAN", down_bps=700_000_000, up_bps=30_000_000
    )


def test_pending_already_effective_clears_without_fabricating_contact(controller):
    _prime_pending(controller, dl=500_000_000, ul=20_000_000)
    controller.router_connectivity.record_success = MagicMock(
        wraps=controller.router_connectivity.record_success
    )

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is False
    assert controller.pending_rates.has_pending() is False
    controller.router_connectivity.record_success.assert_not_called()
    controller.router.set_limits.assert_not_called()


def test_stale_pending_discard_is_no_io_and_preserves_connectivity(controller):
    _prime_pending(controller)
    controller.pending_rates.queued_at = time.monotonic() - 120
    controller.router_connectivity.record_success = MagicMock(
        wraps=controller.router_connectivity.record_success
    )

    router_failed, _ = controller._run_router_communication(500_000_000, 20_000_000)

    assert router_failed is False
    assert controller.pending_rates.has_pending() is False
    controller.router_connectivity.record_success.assert_not_called()
    controller.router.set_limits.assert_not_called()


def test_watchdog_distinguishes_router_only_failure_until_surrender() -> None:
    logger = MagicMock()
    connectivity = SimpleNamespace(
        is_reachable=False,
        last_failure_type="network_unreachable",
    )
    continuous = SimpleNamespace(
        wan_controllers=[
            {
                "controller": SimpleNamespace(router_connectivity=connectivity),
                "logger": logger,
            }
        ]
    )

    with (
        patch("wanctl.autorate_continuous.notify_watchdog") as notify,
        patch("wanctl.autorate_continuous.notify_degraded") as degraded,
    ):
        failures = 0
        watchdog_enabled = True
        for _ in range(2):
            failures, watchdog_enabled = _track_cycle_failures(
                continuous, False, failures, watchdog_enabled
            )
            _notify_watchdog_with_distinction(
                continuous, False, failures, watchdog_enabled
            )

        assert watchdog_enabled is True
        assert notify.call_count == 2
        degraded.assert_not_called()

        failures, watchdog_enabled = _track_cycle_failures(
            continuous, False, failures, watchdog_enabled
        )
        _notify_watchdog_with_distinction(
            continuous, False, failures, watchdog_enabled
        )

        assert failures == 3
        assert watchdog_enabled is False
        assert notify.call_count == 2
        assert degraded.call_count == 2


def test_watchdog_does_not_mask_auth_failure_as_router_only() -> None:
    connectivity = SimpleNamespace(
        is_reachable=False,
        last_failure_type="auth_failure",
    )
    continuous = SimpleNamespace(
        wan_controllers=[
            {
                "controller": SimpleNamespace(router_connectivity=connectivity),
                "logger": MagicMock(),
            }
        ]
    )

    with patch("wanctl.autorate_continuous.notify_watchdog") as notify:
        _notify_watchdog_with_distinction(continuous, False, 1, True)

    notify.assert_not_called()

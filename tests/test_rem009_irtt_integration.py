"""REM-009 first-class IRTT controller and health integration regressions."""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wanctl.health_check import HealthCheckHandler
from wanctl.rtt_backend import RttSample
from wanctl.rtt_backend_factory import build_rtt_backend
from wanctl.rtt_measurement import RTTCycleStatus, RTTMeasurement
from wanctl.wan_controller import WANController


@pytest.fixture
def controller(mock_autorate_config):
    mock_autorate_config.ping_hosts = ["192.0.2.1", "192.0.2.2", "192.0.2.3"]
    router = MagicMock()
    router.needs_rate_limiting = False
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=router,
            rtt_measurement=MagicMock(),
            logger=MagicMock(),
        )
    ctrl._reflector_scorer = MagicMock()
    ctrl._reflector_scorer.has_pending_events.return_value = False
    return ctrl


def _install_irtt_backend(controller, *, sample: RttSample | None) -> MagicMock:
    thread = MagicMock()
    thread.get_latest.return_value = sample
    thread.get_cycle_status.return_value = None
    thread.cadence_sec = 10.0
    controller._rtt_thread = thread
    controller._rtt_thread_started_ts = time.monotonic()
    controller._rtt_backend_status = SimpleNamespace(
        backend_active="irtt",
        fell_back=False,
        fallback_count=0,
        irtt_config={"server": "198.51.100.50"},
        controller_measurement=SimpleNamespace(source_ip="192.0.2.10"),
    )
    return thread


def test_distinct_irtt_target_bypasses_icmp_scorer_and_drives_health(controller) -> None:
    target = "198.51.100.50"
    sample = RttSample(
        rtt_ms=24.0,
        per_host_results={target: 24.0},
        timestamp=time.monotonic(),
        measurement_ms=0.0,
        active_hosts=(target,),
        successful_hosts=(target,),
        backend="irtt",
        source_ip=target,
        per_host_loss={target: 0.0},
    )
    _install_irtt_backend(controller, sample=sample)

    assert controller.measure_rtt() == 24.0
    controller._reflector_scorer.record_results.assert_not_called()

    health_data = controller.get_health_data()
    measurement = HealthCheckHandler.__new__(HealthCheckHandler)._build_measurement_section(
        health_data
    )
    assert measurement["active_reflector_hosts"] == [target]
    assert measurement["successful_reflector_hosts"] == [target]
    assert measurement["state"] == "healthy"
    assert measurement["backend_active"] == "irtt"
    assert measurement["backend"] == "irtt"
    assert measurement["source_ip"] == "192.0.2.10"
    assert measurement["target"] == target


def test_failed_irtt_burst_collapses_cached_success_at_controller_boundary(controller) -> None:
    target = "198.51.100.50"
    cached = RttSample(
        rtt_ms=24.0,
        per_host_results={target: 24.0},
        timestamp=time.monotonic(),
        measurement_ms=0.0,
        active_hosts=(target,),
        successful_hosts=(target,),
        backend="irtt",
        source_ip=target,
        per_host_loss={target: 0.0},
    )
    thread = _install_irtt_backend(controller, sample=cached)
    thread.get_cycle_status.return_value = RTTCycleStatus(
        successful_count=0,
        active_hosts=(target,),
        successful_hosts=(),
        cycle_timestamp=time.monotonic(),
    )

    # The cached RTT remains bounded input, but current-cycle attribution is
    # explicitly collapsed rather than continuing to claim target success.
    assert controller.measure_rtt() == 24.0
    health_data = controller.get_health_data()
    measurement = HealthCheckHandler.__new__(HealthCheckHandler)._build_measurement_section(
        health_data
    )
    assert measurement["state"] == "collapsed"
    assert measurement["successful_count"] == 0
    assert measurement["successful_reflector_hosts"] == []


def test_irtt_cold_start_waits_without_icmp_scorer_or_failure_warning(controller) -> None:
    _install_irtt_backend(controller, sample=None)
    controller.logger.reset_mock()

    assert controller._initial_rtt_sample_pending() is True
    assert controller.measure_rtt() is None
    controller._reflector_scorer.record_results.assert_not_called()
    assert any(
        "Waiting for initial irtt RTT sample" in str(call)
        for call in controller.logger.info.call_args_list
    )
    assert not any(
        "No RTT data available" in str(call)
        for call in controller.logger.warning.call_args_list
    )


def test_misconfigured_irtt_request_falls_back_honestly_to_icmp(
    mock_autorate_config,
) -> None:
    mock_autorate_config.data = {
        "measurement": {"backend": "irtt"},
        "irtt": {"enabled": True, "server": None},
    }

    handle = build_rtt_backend(
        mock_autorate_config,
        source_ip="192.0.2.10",
        logger=logging.getLogger("test-rem009-fallback"),
        wan_key="test",
    )

    assert isinstance(handle.backend, RTTMeasurement)
    assert handle.backend_active == "icmplib"
    assert handle.fell_back is True
    assert handle.fallback_count == 1

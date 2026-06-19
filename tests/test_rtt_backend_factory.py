"""Phase 242 RED contracts for RTT backend factory loud fallback.

These tests intentionally import the factory that Plan 02 will add.  Until
``wanctl.rtt_backend_factory.build_rtt_backend`` exists, this file is RED by
collection/import failure, not by syntax error.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from wanctl.fping_measurement import FpingMeasurement, FpingThread
from wanctl.rtt_backend import RttSample
from wanctl.rtt_backend_factory import build_rtt_backend
from wanctl.rtt_measurement import BackgroundRTTThread, RTTCycleStatus, RTTMeasurement, RTTSnapshot
from wanctl.wan_controller import WANController


class FactoryConfig:
    """Minimal config object exposing the fields factory/controller tests need."""

    def __getattr__(self, name: str):
        """Return conservative defaults for WANController init fields outside this contract."""
        if name.startswith("_"):
            return False
        if name.endswith("_config") or name in {"data", "storage_config", "alerting_config"}:
            return {}
        if name.endswith("_hosts") or name.endswith("_targets"):
            return []
        if (
            name.startswith(("enable_", "use_", "check_"))
            or name.endswith("_enabled")
            or name in {"docsis_mode", "fusion_enabled"}
        ):
            return False
        if name.endswith(("_ms", "_sec", "_seconds", "_pct")) or "rtt" in name:
            return 1.0
        if name.endswith(("_cycles", "_count")):
            return 1
        return 0

    def __init__(self, *, backend: str | None = None, fping: dict[str, object] | None = None) -> None:
        measurement: dict[str, object] = {}
        if backend is not None:
            measurement["backend"] = backend
        if fping is not None:
            measurement["fping"] = fping
        self.data = {"measurement": measurement} if measurement else {}

        self.timeout_ping = 1
        self.ping_source_ip = "192.0.2.10"
        self.ping_hosts = ["198.51.100.10", "198.51.100.11", "198.51.100.12"]
        self.cycle_interval_ms = 50
        self.baseline_rtt_initial = 20.0
        self.baseline_rtt_min = 5.0
        self.baseline_rtt_max = 200.0
        self.download_floor_green = 100_000_000
        self.download_floor_yellow = 90_000_000
        self.download_floor_soft_red = 80_000_000
        self.download_floor_red = 70_000_000
        self.download_ceiling = 200_000_000
        self.download_step_up = 1_000_000
        self.download_factor_down = 0.85
        self.download_factor_down_yellow = 0.95
        self.download_green_required = 5
        self.upload_floor_green = 10_000_000
        self.upload_floor_yellow = 9_000_000
        self.upload_floor_red = 8_000_000
        self.upload_ceiling = 20_000_000
        self.upload_step_up = 1_000_000
        self.upload_factor_down = 0.85
        self.upload_factor_down_yellow = 0.95
        self.upload_green_required = 5
        self.dwell_cycles = 3
        self.deadband_ms = 3.0
        self.target_bloat_ms = 15.0
        self.warn_bloat_ms = 45.0
        self.hard_red_bloat_ms = 80.0
        self.accel_threshold_ms = 50.0
        self.accel_confirm_cycles = 3
        self.baseline_update_threshold_ms = 3.0
        self.alpha_baseline = 0.1
        self.alpha_load = 0.2
        self.metrics_enabled = False
        self.fallback_mode = "graceful_degradation"
        self.fallback_max_cycles = 3
        self.fallback_check_gateway = True
        self.fallback_gateway_ip = "192.0.2.1"
        self.fallback_check_tcp = False
        self.fallback_tcp_targets = []
        self.warning_threshold_pct = 60.0
        self.cake_stats_cadence_sec = 0.25
        self.storage_config = {}
        self.alerting_config = {}
        self.irtt_config = {"enabled": False}
        self.fusion_enabled = False
        self.fusion_config = {"enabled": False, "icmp_weight": 1.0}
        self.reflector_quality_config = {
            "min_score": 0.5,
            "window_size": 5,
            "probe_interval_sec": 60.0,
            "recovery_count": 2,
        }
        self.owd_asymmetry_config = {"ratio_threshold": 3.0}
        self.asymmetry_gate_config = {
            "enabled": False,
            "damping_factor": 0.5,
            "min_ratio": 3.0,
            "confirm_readings": 2,
            "staleness_sec": 5.0,
        }
        self.tuning_config = SimpleNamespace(enabled=False)
        self.cake_signal_config = SimpleNamespace(enabled=False)


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test_rtt_backend_factory")


def _build(
    *,
    backend: str | None = None,
    fping: dict[str, object] | None = None,
    wan_key: str = "spectrum",
    logger: logging.Logger | None = None,
):
    return build_rtt_backend(
        FactoryConfig(backend=backend, fping=fping),
        "192.0.2.10",
        logger or logging.getLogger("test_rtt_backend_factory"),
        wan_key=wan_key,
    )


def _patch_fping_present(path: str | None):
    return (
        patch("wanctl.rtt_backend_factory.shutil.which", return_value=path),
        patch("wanctl.fping_measurement.shutil.which", return_value=path),
    )


def _make_controller(handle) -> WANController:
    router = MagicMock()
    router.needs_rate_limiting = False
    router.rate_limit_params = {}
    with patch.object(WANController, "load_state"):
        controller = WANController(
            wan_name="spectrum",
            config=FactoryConfig(backend="fping"),
            router=router,
            rtt_measurement=handle.controller_measurement,
            logger=logging.getLogger("test_rtt_backend_factory.controller"),
            rtt_thread_factory=handle,
        )
    return controller


def test_fallback_is_loud(caplog: pytest.LogCaptureFixture, logger: logging.Logger) -> None:
    """FALL-02: fping absent falls back loudly: WARN + per-WAN counter + signal."""
    with _patch_fping_present(None)[0], _patch_fping_present(None)[1], caplog.at_level(logging.WARNING):
        handle = _build(backend="fping", logger=logger)

    assert isinstance(handle.backend, RTTMeasurement)
    assert any(record.levelno == logging.WARNING and "fping" in record.message for record in caplog.records)
    assert handle.fallback_count >= 1
    assert handle.fell_back is True
    assert handle.backend_active == "icmplib"


def test_fallback_builds_icmplib(logger: logging.Logger) -> None:
    """FALL-01: fping selected but binary absent constructs icmplib, not FpingMeasurement."""
    with _patch_fping_present(None)[0], _patch_fping_present(None)[1]:
        handle = _build(backend="fping", logger=logger)

    assert isinstance(handle.backend, RTTMeasurement)
    assert not isinstance(handle.backend, FpingMeasurement)
    assert handle.backend is handle.controller_measurement


def test_fping_selected_builds_fping(caplog: pytest.LogCaptureFixture, logger: logging.Logger) -> None:
    """FALL-01: fping present + selected builds fping without warning/fallback."""
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1], caplog.at_level(logging.WARNING):
        handle = _build(backend="fping", logger=logger)

    assert isinstance(handle.backend, FpingMeasurement)
    assert handle.fell_back is False
    assert handle.backend_active == "fping"
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_default_icmplib(caplog: pytest.LogCaptureFixture, logger: logging.Logger) -> None:
    """Absent measurement.backend follows validator semantics: icmplib, no fallback WARN."""
    with caplog.at_level(logging.WARNING):
        handle = _build(logger=logger)

    assert isinstance(handle.backend, RTTMeasurement)
    assert handle.fell_back is False
    assert handle.backend_active == "icmplib"
    assert handle.fallback_count == 0
    assert not caplog.records


def test_controller_measurement_is_rttmeasurement(logger: logging.Logger) -> None:
    """Cycle-2 HIGH: controller helper paths at wan_controller.py:1269/:1474/:3127 use icmplib.

    Under fping selection the background backend may be FpingMeasurement, but
    WANController.rtt_measurement must still expose ping_hosts_with_results(),
    ping_host(), and satisfy ReflectorScorer.maybe_probe(now, rtt_measurement).
    """
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", logger=logger)

    assert isinstance(handle.controller_measurement, RTTMeasurement)
    assert not isinstance(handle.controller_measurement, FpingMeasurement)
    controller = _make_controller(handle)
    controller.rtt_measurement.ping_host = MagicMock(return_value=12.0)
    controller.rtt_measurement.ping_hosts_with_results = MagicMock(return_value={"198.51.100.10": 12.0})
    controller._reflector_scorer._hosts = ["198.51.100.10"]
    controller._reflector_scorer._deprioritized = {"198.51.100.10"}
    controller._reflector_scorer._last_probe_time = {"198.51.100.10": 0.0}

    controller.verify_local_connectivity()
    controller._measure_rtt_blocking()
    controller._reflector_scorer.maybe_probe(time.monotonic() + 10_000, controller.rtt_measurement)


@pytest.mark.parametrize("fping_config, expected", [({}, 10.0), ({"cadence_sec": 8.0}, 8.0)])
def test_fping_uses_resolved_cadence(
    fping_config: dict[str, object], expected: float, logger: logging.Logger
) -> None:
    """Cycle-3 HIGH: fping branch ignores controller cadence.

    WANController cadence comes from wan_controller.py:90/:1105-1110 and is
    commonly 0.25s. Fping timeout comes from fping_measurement.py:57 and
    FpingThread rejects timeout >= cadence at :299, so make_thread must use the
    resolved measurement.fping.cadence_sec instead.
    """
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", fping=fping_config, logger=logger)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        thread = handle.make_thread(
            lambda: ["198.51.100.10"], threading.Event(), pool=pool, cadence_sec=0.25
        )

    assert handle.fping_cadence_sec == expected
    assert thread.cadence_sec == expected
    assert not isinstance(thread, BackgroundRTTThread)
    assert callable(thread.get_cycle_status)
    assert thread.get_cycle_status() is None
    assert handle.backend_active == "fping"
    assert handle.fell_back is False


def test_start_background_rtt_keeps_fping_active(logger: logging.Logger) -> None:
    """Cycle-3 HIGH keeper: real start_background_rtt path keeps fping active.

    This drives WANController.start_background_rtt(), whose controller cadence is
    defined at wan_controller.py:90/:1105-1110, proving the live path installs the
    fping adapter instead of passing 0.25s to raw FpingThread and falling back.
    """
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", fping={"cadence_sec": 8.0}, logger=logger)
    controller = _make_controller(handle)
    shutdown = threading.Event()

    try:
        controller.start_background_rtt(shutdown)
        assert handle.backend_active == "fping"
        assert controller._rtt_thread is not None
        assert not isinstance(controller._rtt_thread, BackgroundRTTThread)
        assert not isinstance(controller._rtt_thread, FpingThread)
        assert callable(controller._rtt_thread.get_cycle_status)
    finally:
        shutdown.set()
        if controller._rtt_thread is not None:
            controller._rtt_thread.stop()
        if getattr(controller, "_rtt_pool", None) is not None:
            controller._rtt_pool.shutdown(wait=True)


def test_fping_constructed_without_scorer(logger: logging.Logger) -> None:
    """Cycle-3 MEDIUM: fping must not double-feed the reflector scorer in 242."""
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", logger=logger)

    assert isinstance(handle.backend, FpingMeasurement)
    assert handle.backend._scorer is None


@pytest.mark.parametrize("binary_path", [None, "/usr/bin/fping"])
def test_thread_protocol_contract(binary_path: str | None, logger: logging.Logger) -> None:
    """Cycle-1 HIGH: make_thread output exposes the protocol measure_rtt consumes."""
    with _patch_fping_present(binary_path)[0], _patch_fping_present(binary_path)[1]:
        handle = _build(backend="fping", logger=logger)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        thread = handle.make_thread(
            lambda: ["198.51.100.10"], threading.Event(), pool=pool, cadence_sec=0.25
        )

    for method in ("start", "stop", "get_latest", "get_cycle_status", "get_profile_stats"):
        assert callable(getattr(thread, method))
    assert hasattr(thread, "cadence_sec")
    status = thread.get_cycle_status()
    assert status is None or isinstance(status, RTTCycleStatus)
    latest = thread.get_latest()
    assert latest is None or all(
        hasattr(latest, attr)
        for attr in ("rtt_ms", "per_host_results", "timestamp", "active_hosts", "successful_hosts")
    )


def test_fping_selected_measure_rtt_no_attributeerror(logger: logging.Logger) -> None:
    """Factory-produced fping background samples do not feed ReflectorScorer."""
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", logger=logger)
    controller = _make_controller(handle)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        controller._rtt_thread = handle.make_thread(
            lambda: ["h1", "h2"], threading.Event(), pool=pool, cadence_sec=0.25
        )
    controller._rtt_thread._fping_thread._cached_result = RttSample(
        rtt_ms=12.5,
        per_host_results={"h1": 12.5, "h2": None},
        timestamp=time.monotonic(),
        measurement_ms=1.0,
        active_hosts=("h1", "h2"),
        successful_hosts=("h1",),
        backend="fping",
        source_ip="192.0.2.10",
    )
    controller._reflector_scorer.record_results = MagicMock()

    assert controller.measure_rtt() == 12.5
    controller._reflector_scorer.record_results.assert_not_called()
    assert controller._zero_success_blackout_cycles == 0
    assert controller._last_active_reflector_hosts == ["h1", "h2"]
    assert controller._last_successful_reflector_hosts == ["h1"]


def test_fping_measure_rtt_allows_expected_cadence_gap(logger: logging.Logger) -> None:
    """A cached fping sample inside the producer cadence window remains usable.

    Regression for the Phase 248.1 canary: default fping cadence is 10s while
    the controller loop runs every 50ms. The old fixed 5s hard-stale cutoff made
    the loop repeatedly reject healthy cached fping samples before the next
    expected background burst.
    """
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", fping={"cadence_sec": 10.0}, logger=logger)
    controller = _make_controller(handle)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        controller._rtt_thread = handle.make_thread(
            lambda: ["h1", "h2"], threading.Event(), pool=pool, cadence_sec=0.25
        )
    fping_thread = cast(Any, controller._rtt_thread)._fping_thread
    fping_thread._cached_result = RttSample(
        rtt_ms=12.5,
        per_host_results={"h1": 12.5, "h2": None},
        timestamp=time.monotonic() - 6.0,
        measurement_ms=1.0,
        active_hosts=("h1", "h2"),
        successful_hosts=("h1",),
        backend="fping",
        source_ip="192.0.2.10",
    )
    controller._reflector_scorer.record_results = MagicMock()

    assert controller.measure_rtt() == 12.5
    controller._reflector_scorer.record_results.assert_not_called()
    assert controller._last_active_reflector_hosts == ["h1", "h2"]
    assert controller._last_successful_reflector_hosts == ["h1"]


def test_fping_measure_rtt_rejects_beyond_cadence_grace(logger: logging.Logger) -> None:
    """A truly stale fping sample still fails instead of being trusted forever."""
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1]:
        handle = _build(backend="fping", fping={"cadence_sec": 10.0}, logger=logger)
    controller = _make_controller(handle)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        controller._rtt_thread = handle.make_thread(
            lambda: ["h1", "h2"], threading.Event(), pool=pool, cadence_sec=0.25
        )
    fping_thread = cast(Any, controller._rtt_thread)._fping_thread
    fping_thread._cached_result = RttSample(
        rtt_ms=12.5,
        per_host_results={"h1": 12.5, "h2": None},
        timestamp=time.monotonic() - 16.0,
        measurement_ms=1.0,
        active_hosts=("h1", "h2"),
        successful_hosts=("h1",),
        backend="fping",
        source_ip="192.0.2.10",
    )
    controller._reflector_scorer.record_results = MagicMock()

    assert controller.measure_rtt() is None
    controller._reflector_scorer.record_results.assert_not_called()


def test_icmplib_background_snapshot_still_updates_reflector_scorer(logger: logging.Logger) -> None:
    """Normal icmplib background snapshots still feed ReflectorScorer."""
    handle = _build(logger=logger)
    controller = _make_controller(handle)

    class IcmplibThread:
        cadence_sec = 0.25

        def get_latest(self):
            return RTTSnapshot(
                rtt_ms=11.0,
                per_host_results={"h1": 11.0, "h2": None},
                timestamp=time.monotonic(),
                measurement_ms=1.0,
                active_hosts=("h1", "h2"),
                successful_hosts=("h1",),
            )

        def get_cycle_status(self):
            return None

        def get_profile_stats(self):
            return {}

        def start(self):
            return None

        def stop(self):
            return None

    controller._rtt_thread = IcmplibThread()
    controller._reflector_scorer.record_results = MagicMock()

    assert controller.measure_rtt() == 11.0
    controller._reflector_scorer.record_results.assert_called_once_with({"h1": True, "h2": False})


def test_fping_timeout_ge_cadence_falls_back(caplog: pytest.LogCaptureFixture, logger: logging.Logger) -> None:
    """Genuine fping timeout>=cadence misconfig falls back loudly instead of crashing."""
    with _patch_fping_present("/usr/bin/fping")[0], _patch_fping_present("/usr/bin/fping")[1], caplog.at_level(logging.WARNING):
        handle = _build(backend="fping", fping={"cadence_sec": 1.0}, logger=logger)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            thread = handle.make_thread(
                lambda: ["198.51.100.10"], threading.Event(), pool=pool, cadence_sec=0.25
            )

    assert isinstance(handle.backend, RTTMeasurement)
    assert not isinstance(handle.backend, FpingMeasurement)
    assert isinstance(thread, BackgroundRTTThread)
    assert handle.fell_back is True
    assert handle.backend_active == "icmplib"
    assert any("fping" in record.message and record.levelno >= logging.WARNING for record in caplog.records)

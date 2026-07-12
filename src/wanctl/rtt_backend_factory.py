"""RTT backend factory with loud, per-WAN fping fallback.

Phase 242 keeps backend selection in one construction module so call sites do
not branch on backend type.  The factory probe below is the authoritative
selection check for ``fping`` availability; ``FpingMeasurement`` also probes
``shutil.which("fping")`` internally and that subordinate probe is tolerated so
the Phase 241 backend remains byte-frozen.

Scope note for 242: fping feeds only the background driver thread consumed by
``WANController.measure_rtt()``.  Controller helper paths such as gateway
checks, blocking fallback, and reflector scorer probes keep using the separate
icmplib ``controller_measurement``.  The fping object is therefore constructed
without a scorer key so it cannot double-feed reflector scoring; loss-aware
controller/scorer semantics are deferred to Phase 245.

The icmplib construction intentionally mirrors autorate's historical
AVERAGE/log_sample_stats=True shape.  Steering's older MEDIAN shape is a
Phase-245 decision point; adding a strategy parameter here would broaden 242's
scope without changing current live behavior.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import logging
import shutil
import threading
from collections.abc import Callable
from typing import Any, Protocol, cast

from wanctl.check_config_validators import MEASUREMENT_BACKENDS
from wanctl.fping_measurement import FpingMeasurement, FpingThread
from wanctl.irtt_thread import IRTTThread
from wanctl.rtt_backend import (
    IrttRttBackend,
    RttBackend,
    RttSample,
    sample_from_irtt_result,
)
from wanctl.rtt_measurement import (
    BackgroundRTTThread,
    RTTAggregationStrategy,
    RTTCycleStatus,
    RTTMeasurement,
    RTTSnapshot,
)

_FALLBACK_WARNED: set[tuple[str, str]] = set()


class RttDriverThread(Protocol):
    """Common background-thread shape consumed by WANController.measure_rtt()."""

    @property
    def cadence_sec(self) -> float: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def get_latest(self) -> RTTSnapshot | RttSample | None: ...
    def get_cycle_status(self) -> RTTCycleStatus | None: ...
    def get_profile_stats(self) -> dict[str, object]: ...


class _FpingDriverThread:
    """Adapt FpingThread to the RttDriverThread protocol."""

    def __init__(self, fping_thread: FpingThread) -> None:
        self._fping_thread = fping_thread

    @property
    def cadence_sec(self) -> float:
        return self._fping_thread.cadence_sec

    def start(self) -> None:
        self._fping_thread.start()

    def stop(self) -> None:
        self._fping_thread.stop()

    def get_latest(self) -> RttSample | None:
        sample = self._fping_thread.get_latest()
        if sample is None:
            return None
        return sample

    def get_cycle_status(self) -> RTTCycleStatus | None:
        return None

    def get_profile_stats(self) -> dict[str, object]:
        return self._fping_thread.get_profile_stats()


class _IrttDriverThread:
    """Adapt IRTTThread to the RttDriverThread protocol.

    IRTTThread caches IRTTResult internally; this adapter converts to
    RttSample via sample_from_irtt_result() on each get_latest() call.
    """

    def __init__(self, irtt_thread: IRTTThread) -> None:
        self._irtt_thread = irtt_thread

    @property
    def cadence_sec(self) -> float:
        return self._irtt_thread.cadence_sec

    def start(self) -> None:
        self._irtt_thread.start()

    def stop(self) -> None:
        self._irtt_thread.stop()

    def get_latest(self) -> RttSample | None:
        result = self._irtt_thread.get_latest()
        if result is None:
            return None
        return sample_from_irtt_result(result)

    def get_cycle_status(self) -> RTTCycleStatus | None:
        return None

    def get_profile_stats(self) -> dict[str, object]:
        return self._irtt_thread.get_profile_stats()


@dataclasses.dataclass(slots=True)
class RttBackendHandle:
    """Constructed backend plus deferred background-thread builder."""

    backend: RttBackend
    controller_measurement: RTTMeasurement
    backend_active: str
    fell_back: bool
    fallback_count: int
    fping_cadence_sec: float
    irtt_cadence_sec: float
    irtt_config: dict | None
    _logger: logging.Logger
    _wan_key: str

    def make_thread(
        self,
        hosts_fn: Callable[[], list[str]],
        shutdown_event: threading.Event,
        *,
        pool: concurrent.futures.ThreadPoolExecutor | None = None,
        cadence_sec: float,
    ) -> RttDriverThread:
        """Build the concrete driver only after pool and hosts_fn exist.

        The icmplib path uses the caller-supplied controller cadence.  The fping
        and irtt paths deliberately ignore that value and use their own cadences
        resolved at factory time.
        """
        if self.backend_active == "irtt":
            if self.irtt_config is None:
                raise ValueError("irtt backend requested but no IRTT config")
            irtt_backend = cast(IrttRttBackend, self.backend)
            irtt_thread = IRTTThread(
                irtt_backend._measurement,
                cadence_sec=self.irtt_cadence_sec,
                shutdown_event=shutdown_event,
                logger=self._logger,
            )
            return _IrttDriverThread(irtt_thread)

        if self.backend_active == "fping":
            try:
                fping_thread = FpingThread(
                    self.backend,  # type: ignore[arg-type]
                    hosts_fn,
                    cadence_sec=self.fping_cadence_sec,
                    shutdown_event=shutdown_event,
                    logger=self._logger,
                )
            except ValueError as exc:
                self._warn_once(
                    "timeout-fallback",
                    f"fping backend disabled for {self._wan_key}: {exc}; falling back to icmplib",
                )
                self.fallback_count += 1
                self.fell_back = True
                self.backend_active = "icmplib"
                self.backend = self.controller_measurement
            else:
                return _FpingDriverThread(fping_thread)

        if pool is None:
            raise ValueError("pool is required when building an icmplib RTT thread")
        return BackgroundRTTThread(
            rtt_measurement=self.controller_measurement,
            hosts_fn=hosts_fn,
            shutdown_event=shutdown_event,
            logger=self._logger,
            pool=pool,
            cadence_sec=cadence_sec,
        )

    def _warn_once(self, reason: str, message: str) -> None:
        key = (self._wan_key, reason)
        if key in _FALLBACK_WARNED:
            return
        _FALLBACK_WARNED.add(key)
        self._logger.warning(message)


def build_rtt_backend(
    config: Any,
    source_ip: str | None,
    logger: logging.Logger,
    *,
    wan_key: str,
) -> RttBackendHandle:
    """Resolve and construct the configured RTT backend handle."""
    measurement_config = (getattr(config, "data", {}).get("measurement", {}) or {})
    requested = measurement_config.get("backend", "icmplib")
    if requested not in MEASUREMENT_BACKENDS:
        msg = f"Unknown measurement.backend: {requested!r}. Must be one of: {list(MEASUREMENT_BACKENDS)}"
        raise ValueError(msg)

    fping_config = measurement_config.get("fping", {}) or {}
    fping_cadence_sec = float(fping_config.get("cadence_sec", 10.0))

    # IRTT config — lives under the top-level 'irtt' key in WAN config
    irtt_config = (getattr(config, "data", {}).get("irtt", {}) or {})
    irtt_cadence_sec = float(irtt_config.get("cadence_sec", 10.0))

    if requested == "irtt":
        irtt_enabled = irtt_config.get("enabled", False)
        irtt_server = irtt_config.get("server")
        if not irtt_enabled or not irtt_server:
            logger.warning(
                f"irtt backend requested for {wan_key} but irtt is not configured or enabled; "
                f"falling back to icmplib"
            )
            return _build_icmplib_handle(
                config, source_ip, logger, wan_key, fping_cadence_sec, fell_back=False
            )
        irtt_backend = IrttRttBackend(irtt_config, logger)
        controller_measurement = _build_controller_measurement(config, source_ip, logger)
        return RttBackendHandle(
            backend=irtt_backend,
            controller_measurement=controller_measurement,
            backend_active="irtt",
            fell_back=False,
            fallback_count=0,
            fping_cadence_sec=fping_cadence_sec,
            irtt_cadence_sec=irtt_cadence_sec,
            irtt_config=irtt_config,
            _logger=logger,
            _wan_key=wan_key,
        )

    if requested == "fping" and shutil.which("fping") is not None:
        fping_backend = FpingMeasurement(_fping_measurement_config(fping_config, source_ip), logger)
        controller_measurement = _build_controller_measurement(config, source_ip, logger)
        return RttBackendHandle(
            backend=fping_backend,
            controller_measurement=controller_measurement,
            backend_active="fping",
            fell_back=False,
            fallback_count=0,
            fping_cadence_sec=fping_cadence_sec,
            irtt_cadence_sec=0.0,
            irtt_config=None,
            _logger=logger,
            _wan_key=wan_key,
        )

    controller_measurement = _build_controller_measurement(config, source_ip, logger)
    fell_back = requested == "fping"
    return _build_icmplib_handle(
        config, source_ip, logger, wan_key, fping_cadence_sec, fell_back
    )


def _build_icmplib_handle(
    config: Any,
    source_ip: str | None,
    logger: logging.Logger,
    wan_key: str,
    fping_cadence_sec: float,
    fell_back: bool,
) -> RttBackendHandle:
    """Build an icmplib RttBackendHandle (used for default and fallback paths)."""
    controller_measurement = _build_controller_measurement(config, source_ip, logger)
    handle = RttBackendHandle(
        backend=controller_measurement,
        controller_measurement=controller_measurement,
        backend_active="icmplib",
        fell_back=fell_back,
        fallback_count=1 if fell_back else 0,
        fping_cadence_sec=fping_cadence_sec,
        irtt_cadence_sec=0.0,
        irtt_config=None,
        _logger=logger,
        _wan_key=wan_key,
    )
    if fell_back:
        handle._warn_once(
            "binary-absent",
            f"fping selected for {wan_key} but fping binary was not found; falling back to icmplib",
        )
    return handle


def _build_controller_measurement(
    config: Any,
    source_ip: str | None,
    logger: logging.Logger,
) -> RTTMeasurement:
    return RTTMeasurement(
        logger,
        timeout_ping=config.timeout_ping,
        aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        log_sample_stats=True,
        source_ip=source_ip,
    )


def _fping_measurement_config(fping_config: dict[str, object], source_ip: str | None) -> dict[str, object]:
    """Return FpingMeasurement config, intentionally omitting any scorer key."""
    allowed = {"count", "period_ms", "loss_fail_threshold", "timeout_grace_sec"}
    out = {key: fping_config[key] for key in allowed if key in fping_config}
    out["source_ip"] = source_ip
    return out

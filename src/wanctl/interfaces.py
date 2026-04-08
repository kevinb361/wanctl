"""Interface protocols for wanctl module boundaries.

All Protocol definitions live here (D-02). Implementations satisfy
protocols via structural subtyping -- no inheritance required (D-01).

These protocols define the public interfaces for cross-module
communication. Modules should depend on these protocols rather than
reaching into private attributes of concrete implementations.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Health endpoint protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class HealthDataProvider(Protocol):
    """Component that provides health endpoint data.

    Implemented by WANController, QueueController, and SteeringDaemon
    to expose health-relevant state without cross-module private access.
    """

    def get_health_data(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Configuration reload protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Reloadable(Protocol):
    """Component with hot-reload support via SIGUSR1.

    Implemented by WANController to consolidate multiple private
    _reload_*() calls into a single public entry point.
    """

    def reload(self) -> None: ...


# ---------------------------------------------------------------------------
# Tuning protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class TunableController(Protocol):
    """Controller exposing tunable parameters.

    Implemented by WANController to provide a single-call accessor
    for all tunable values (sigma_threshold, fusion_icmp_weight,
    reflector_min_score, etc.) without two-level deep private access.
    """

    def get_current_params(self) -> dict[str, float]: ...


# ---------------------------------------------------------------------------
# Thread lifecycle protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ThreadManager(Protocol):
    """Component managing background threads.

    Implemented by WANController to expose a clean shutdown interface
    for the orchestrator without reaching into _rtt_thread / _rtt_pool.
    """

    def shutdown_threads(self) -> None: ...


# ---------------------------------------------------------------------------
# Router client protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class RouterClient(Protocol):
    """Router client for CAKE audit tools.

    Satisfied by RouterOSREST and RouterOSRESTWithFailover.
    Used by check_cake.py and check_cake_fix.py.
    """

    def run_cmd(
        self, cmd: str, capture: bool = ..., timeout: int | None = ...
    ) -> tuple[int, str, str]: ...

    def get_queue_stats(self, queue_name: str) -> dict | None: ...

    def get_queue_types(self, type_name: str) -> dict | None: ...

    def set_queue_type_params(self, type_name: str, params: dict[str, str]) -> bool: ...

    def find_mangle_rule_id(self, comment: str) -> str | None: ...

    def test_connection(self) -> bool: ...


# ---------------------------------------------------------------------------
# Alert formatting protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class AlertFormatter(Protocol):
    """Protocol for alert formatters. Duck-typing compatible."""

    def format(
        self,
        alert_type: str,
        severity: str,
        wan_name: str,
        details: dict[str, Any],
        *,
        mention_role_id: str | None = ...,
        mention_severity: str = ...,
    ) -> dict[str, Any]: ...

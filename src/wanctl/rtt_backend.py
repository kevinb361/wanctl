"""RTT backend seam contracts and sample value types.

This module is intentionally small and acyclic.  The legacy
``RTTSnapshot`` type is imported only for type checking at module load and
inside ``RttSample.to_snapshot()`` at runtime, so importing this module does
not force ``rtt_measurement`` to load.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from wanctl.irtt_measurement import IRTTResult
    from wanctl.rtt_measurement import RTTSnapshot


@runtime_checkable
class RttBackend(Protocol):
    """RTT measurement backend contract.

    Implemented structurally by ``RTTMeasurement`` for the default icmplib
    path; future fping work in Phase 241 and the IRTT adapter seam satisfy
    this same shape.

    ``None`` means no host yielded a successful measurement, matching the
    existing all-fail behavior where the background thread keeps stale cached
    data and ``WANController.measure_rtt()`` returns no new snapshot.  A
    returned ``RttSample`` always carries a real, non-``None`` ``rtt_ms``.
    """

    def probe(self, hosts: list[str]) -> RttSample | None: ...


@dataclasses.dataclass(frozen=True, slots=True)
class RttSample:
    """Immutable RTT sample with legacy snapshot fields plus backend metadata.

    The first six fields are intentionally identical to ``RTTSnapshot`` in
    order and type.  ``per_host_loss`` values are loss percentages per host:
    ``0.0`` means no loss, ``100.0`` means total loss, and ``None`` means the
    loss was not measured.
    """

    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float
    measurement_ms: float
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
    backend: str = "icmplib"
    source_ip: str | None = None
    per_host_loss: dict[str, float | None] = dataclasses.field(default_factory=dict)

    def to_snapshot(self) -> RTTSnapshot:
        """Return a legacy ``RTTSnapshot`` containing only subset fields."""
        from wanctl.rtt_measurement import RTTSnapshot

        return RTTSnapshot(
            rtt_ms=self.rtt_ms,
            per_host_results=self.per_host_results,
            timestamp=self.timestamp,
            measurement_ms=self.measurement_ms,
            active_hosts=self.active_hosts,
            successful_hosts=self.successful_hosts,
        )


def sample_from_irtt_result(result: IRTTResult) -> RttSample:
    """Map an IRTT result into an ``RttSample`` without I/O or side effects.

    ``rtt_median_ms`` becomes the sample RTT, ``server`` becomes the source
    identity and per-host key, and the host loss percentage is the larger of
    IRTT's send and receive loss percentages.  Using the larger percent keeps
    the single seam field conservative while preserving the documented
    0.0-to-100.0 percent unit.
    """

    combined_loss_percent = max(result.send_loss, result.receive_loss)
    return RttSample(
        rtt_ms=result.rtt_median_ms,
        per_host_results={result.server: result.rtt_median_ms},
        timestamp=result.timestamp,
        measurement_ms=0.0,
        active_hosts=(result.server,),
        successful_hosts=(result.server,) if result.success else (),
        backend="irtt",
        source_ip=result.server,
        per_host_loss={result.server: combined_loss_percent},
    )


class IrttRttBackend:
    """Unwired IRTT backend adapter placeholder for deferred migration."""

    def probe(self, hosts: list[str]) -> RttSample | None:
        """Defer live IRTT probing until IRTT-MIG-01."""
        raise NotImplementedError("IRTT-MIG-01")

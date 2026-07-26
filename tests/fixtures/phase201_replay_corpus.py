"""Public-safe Phase 201 replay corpus builders.

The original replay consumed site-specific captures from the private planning
tree. Tests use deterministic synthetic surrogates so a clean public checkout
exercises the same controller states without publishing operational evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

ATTEMPT3_SYNTHETIC_CYCLES = 885


@dataclass(frozen=True)
class ReplaySample:
    ts: str
    baseline_rtt_ms: float | None
    load_rtt_ms: float | None
    upload_state: str
    upload_current_rate_mbps: float
    cake_backlog_bytes: int | None
    cake_cold_start: bool | None


def load_attempt3_trace() -> list[ReplaySample]:
    """Return a deterministic RED-heavy surrogate for the private Attempt 3 capture."""
    return synthesize_sustained_load_trace(
        cycles=ATTEMPT3_SYNTHETIC_CYCLES,
        baseline_rtt_ms=22.0,
        peak_delta_ms=100.0,
        ramp_cycles=10,
        backlog_bytes=8000,
    )


def load_attempt2_trace() -> list[ReplaySample]:
    """The optional secondary private corpus has no public surrogate."""
    return []


def synthesize_sustained_load_trace(
    cycles: int = 60,
    baseline_rtt_ms: float = 22.0,
    peak_delta_ms: float = 30.0,
    ramp_cycles: int = 10,
    backlog_bytes: int = 8000,
) -> list[ReplaySample]:
    out: list[ReplaySample] = []
    for i in range(cycles):
        if i < ramp_cycles:
            delta = peak_delta_ms * (i / ramp_cycles)
        else:
            delta = peak_delta_ms
        out.append(
            ReplaySample(
                ts=f"synthetic-{i:04d}",
                baseline_rtt_ms=baseline_rtt_ms,
                load_rtt_ms=baseline_rtt_ms + delta,
                upload_state="GREEN",
                upload_current_rate_mbps=18.0,
                cake_backlog_bytes=backlog_bytes,
                cake_cold_start=False,
            )
        )
    return out


def synthesize_idle_trace(
    cycles: int = 60,
    baseline_rtt_ms: float = 22.0,
    jitter_ms: float = 0.5,
) -> list[ReplaySample]:
    out: list[ReplaySample] = []
    for i in range(cycles):
        delta = jitter_ms if (i % 2 == 0) else 0.0
        out.append(
            ReplaySample(
                ts=f"idle-{i:04d}",
                baseline_rtt_ms=baseline_rtt_ms,
                load_rtt_ms=baseline_rtt_ms + delta,
                upload_state="GREEN",
                upload_current_rate_mbps=18.0,
                cake_backlog_bytes=0,
                cake_cold_start=False,
            )
        )
    return out

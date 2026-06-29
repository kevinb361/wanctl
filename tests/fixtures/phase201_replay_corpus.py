"""Phase 201 replay corpus loader and synthetic-trace generator.

Single source of truth for replay-test inputs. All Phase 201 test files
that need historical or synthetic UL traces import from this module.

Origin: RESEARCH.md Section 8 (Replay-Test Corpus); PATTERNS.md
'tests/test_phase_201_replay.py (NEW)'.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE200_ARCHIVE = REPO_ROOT / ".planning/milestones/v1.41-phases/200-per-direction-rtt-bloat-thresholds"
ATTEMPT3_NDJSON_PATH = PHASE200_ARCHIVE / "canary/20260504T133207Z/loaded_capture.ndjson"
ATTEMPT3_VERDICT_PATH = PHASE200_ARCHIVE / "canary/20260504T133207Z/verdict.json"
ATTEMPT2_NDJSON_PATH = PHASE200_ARCHIVE / "canary/20260503T215734Z/loaded_capture.ndjson"


@dataclass(frozen=True)
class ReplaySample:
    ts: str
    baseline_rtt_ms: float | None
    load_rtt_ms: float | None
    upload_state: str
    upload_current_rate_mbps: float
    cake_backlog_bytes: int | None
    cake_cold_start: bool | None


def _parse_line(raw: str) -> ReplaySample | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    wans = obj.get("wans") or []
    if not wans:
        return None
    w = wans[0]
    ul = w.get("upload") or {}
    cs = (w.get("cake_signal") or {}).get("upload") or {}
    return ReplaySample(
        ts=obj.get("sampled_at_utc", ""),
        baseline_rtt_ms=w.get("baseline_rtt_ms"),
        load_rtt_ms=w.get("load_rtt_ms"),
        upload_state=ul.get("state", ""),
        upload_current_rate_mbps=float(ul.get("current_rate_mbps") or 0.0),
        cake_backlog_bytes=cs.get("backlog_bytes"),
        cake_cold_start=cs.get("cold_start"),
    )


def _load_ndjson(path: Path) -> list[ReplaySample]:
    if not path.exists():
        return []
    out: list[ReplaySample] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            sample = _parse_line(line)
            if sample is not None:
                out.append(sample)
    return out


def load_attempt3_trace() -> list[ReplaySample]:
    return _load_ndjson(ATTEMPT3_NDJSON_PATH)


def load_attempt2_trace() -> list[ReplaySample]:
    return _load_ndjson(ATTEMPT2_NDJSON_PATH)


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

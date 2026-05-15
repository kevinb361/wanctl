"""Phase 206 deterministic golden replay corpus.

Single source of truth for tests/test_phase_206_replay.py and
scripts/phase206-ab-replay.py. Fixture provenance:
.planning/phases/206-a-b-replay-harness-rollback-gates/golden-fixture-provenance.md (Plan 03).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_NDJSON = Path(__file__).resolve().parent / "phase206_golden_capture.ndjson"


@dataclass(frozen=True)
class GoldenSample:
    ts: str
    baseline_rtt_ms: float
    load_rtt_ms: float
    cake_avg_delay_us: int
    cake_base_delay_us: int


def _parse_line(raw: str) -> GoldenSample | None:
    raw = raw.strip()
    if not raw:
        return None
    obj = json.loads(raw)
    return GoldenSample(
        ts=obj["ts"],
        baseline_rtt_ms=float(obj["baseline_rtt_ms"]),
        load_rtt_ms=float(obj["load_rtt_ms"]),
        cake_avg_delay_us=int(obj["cake_avg_delay_us"]),
        cake_base_delay_us=int(obj["cake_base_delay_us"]),
    )


def load_golden(path: Path | None = None) -> list[GoldenSample]:
    target = path if path is not None else GOLDEN_NDJSON
    if not target.exists():
        raise FileNotFoundError(f"Committed fixture missing: {target}")
    out: list[GoldenSample] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            sample = _parse_line(line)
            if sample is not None:
                out.append(sample)
    return out

"""Deterministic synthetic NDJSON generator for Phase 203 aggregator tests.

Produces tests/fixtures/phase_203_synthetic_capture.ndjson byte-identically on
every run (fixed random seed). The drift-detection test in
tests/test_phase_203_replay.py re-invokes generate_synthetic_ndjson() and asserts
the checked-in fixture matches.

Hand-authored row sequence exercises all 12 zone/cause matrix cells, each default
bucket boundary, first-row exclusion, null delta filtering, and multi-cause
dual-attribution.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42

# Format: (last_zone, load_rtt_delta_us, dwell_hold_lifetime,
# backlog_recovery_lifetime, other_lifetime, comment). Lifetime values are
# monotonic across the complete sequence.
ROW_CATALOG: list[tuple[str, int | None, int, int, int, str]] = [
    ("GREEN", 142, 0, 0, 0, "first row, excluded from _by_zone_cause"),
    ("GREEN", 0, 1, 0, 0, "GREEN dwell_hold bucket [0,1000)"),
    ("GREEN", 1500, 2, 0, 0, "GREEN dwell_hold bucket [1000,3000)"),
    ("GREEN", 4000, 3, 0, 0, "GREEN dwell_hold bucket [3000,6000)"),
    ("GREEN", 8000, 4, 0, 0, "GREEN dwell_hold bucket [6000,10000)"),
    ("GREEN", 100, 4, 1, 0, "GREEN backlog_recovery bucket [0,1000)"),
    ("GREEN", 2200, 4, 2, 0, "GREEN backlog_recovery bucket [1000,3000)"),
    ("GREEN", 4500, 4, 3, 0, "GREEN backlog_recovery bucket [3000,6000)"),
    ("GREEN", 500, 4, 3, 1, "GREEN other bucket [0,1000)"),
    ("GREEN", 1500, 4, 3, 2, "GREEN other bucket [1000,3000)"),
    ("GREEN", 4000, 4, 3, 3, "GREEN other bucket [3000,6000)"),
    ("YELLOW", 12000, 5, 3, 3, "YELLOW dwell_hold bucket [10000,15000)"),
    ("YELLOW", 15000, 6, 3, 3, "YELLOW dwell_hold boundary"),
    ("YELLOW", 18000, 7, 3, 3, "YELLOW dwell_hold bucket [15000,20000)"),
    ("YELLOW", 22000, 7, 4, 3, "YELLOW backlog_recovery bucket [20000,30000)"),
    ("YELLOW", 28000, 7, 5, 3, "YELLOW backlog_recovery bucket [20000,30000)"),
    ("YELLOW", 16000, 7, 6, 3, "YELLOW backlog_recovery bucket [15000,20000)"),
    ("YELLOW", 12500, 7, 6, 4, "YELLOW other bucket [10000,15000)"),
    ("YELLOW", 17500, 7, 6, 5, "YELLOW other bucket [15000,20000)"),
    ("YELLOW", 19999, 7, 6, 6, "YELLOW other bucket [15000,20000)"),
    ("YELLOW", 21000, 8, 7, 6, "MULTI dwell+backlog dual-attributed"),
    ("SOFT_RED", 32000, 9, 7, 6, "SOFT_RED dwell_hold bucket [30000,45000)"),
    ("SOFT_RED", 40000, 10, 7, 6, "SOFT_RED dwell_hold bucket [30000,45000)"),
    ("SOFT_RED", 35000, 11, 7, 6, "SOFT_RED dwell_hold bucket [30000,45000)"),
    ("SOFT_RED", 33000, 11, 8, 6, "SOFT_RED backlog_recovery bucket"),
    ("SOFT_RED", 44000, 11, 9, 6, "SOFT_RED backlog_recovery bucket"),
    ("SOFT_RED", 30000, 11, 10, 6, "SOFT_RED backlog_recovery boundary"),
    ("SOFT_RED", 38000, 11, 10, 7, "SOFT_RED other bucket"),
    ("SOFT_RED", 42000, 11, 10, 8, "SOFT_RED other bucket"),
    ("SOFT_RED", 31000, 11, 10, 9, "SOFT_RED other bucket"),
    ("RED", 50000, 12, 10, 9, "RED dwell_hold bucket [45000,60000)"),
    ("RED", 70000, 13, 10, 9, "RED dwell_hold bucket [60000,100000)"),
    ("RED", 90000, 14, 10, 9, "RED dwell_hold bucket [60000,100000)"),
    ("RED", 65000, 14, 11, 9, "RED backlog_recovery bucket [60000,100000)"),
    ("RED", 80000, 14, 12, 9, "RED backlog_recovery bucket [60000,100000)"),
    ("RED", 55000, 14, 13, 9, "RED backlog_recovery bucket [45000,60000)"),
    ("RED", 75000, 14, 13, 10, "RED other bucket [60000,100000)"),
    ("RED", 250000, 14, 13, 11, "RED other top boundary"),
    ("RED", 350000, 14, 13, 12, "RED other overflow"),
    ("GREEN", None, 14, 13, 12, "null delta sample 1"),
    ("GREEN", None, 14, 13, 12, "null delta sample 2"),
    ("GREEN", None, 14, 13, 12, "null delta sample 3"),
]


def generate_synthetic_ndjson() -> str:
    """Emit deterministic NDJSON content matching ROW_CATALOG."""
    rng = random.Random(SEED)
    lines: list[str] = []
    for i, (zone, delta_us, dwell_hold, backlog_recovery, other, _comment) in enumerate(
        ROW_CATALOG
    ):
        row = {
            "t_wall": f"2026-05-06T00:{i // 60:02d}:{i % 60:02d}Z",
            "t_monotonic": float(i),
            "version": "1.43-dev",
            "status": "healthy",
            "floor_hit_cycles_total": rng.randint(0, 5),
            "suppressions_per_min": rng.randint(0, 30),
            "max_delay_delta_us": rng.randint(0, 1000),
            "red_streak": 0 if zone in ("GREEN", "YELLOW") else rng.randint(0, 3),
            "zone_trace_tail": [zone] * 5,
            "headroom_state": "AVAILABLE" if zone == "GREEN" else "DEGRADED",
            "headroom_exhausted_streak": 0,
            "anti_windup_triggers": 0,
            "rtt_integral_ms_s": round(rng.uniform(0.0, 5.0), 3),
            "docsis_mode_active": True,
            "red_decay_step_pct": 0.02,
            "red_decay_delta_max_pct": 0.10,
            "load_rtt_ms": None if delta_us is None else round(12.0 + delta_us / 1000.0, 2),
            "baseline_rtt_ms": 12.0 if delta_us is not None else None,
            "load_rtt_delta_us": delta_us,
            "last_zone": zone,
            "ul_suppressions_completed_window_count": dwell_hold + backlog_recovery + other,
            "ul_suppressions_completed_window_by_cause": {
                "dwell_hold": dwell_hold,
                "backlog_recovery": backlog_recovery,
                "other": other,
            },
            "ul_suppressions_lifetime_by_cause": {
                "dwell_hold": dwell_hold,
                "backlog_recovery": backlog_recovery,
                "other": other,
            },
        }
        lines.append(json.dumps(row, sort_keys=True))
    return "\n".join(lines) + "\n"


def write_fixture(out_path: Path) -> None:
    out_path.write_text(generate_synthetic_ndjson(), encoding="utf-8")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    write_fixture(repo_root / "tests" / "fixtures" / "phase_203_synthetic_capture.ndjson")

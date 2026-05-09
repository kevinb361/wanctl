"""Deterministic synthetic NDJSON generator for Phase 204 distribution tests.

Produces tests/fixtures/phase_204_synthetic_capture.ndjson byte-identically.
The sequence exercises explicit window-boundary detection with decreasing,
equal, zero, and mixed-cause completed-window snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path

BOUNDARY_WINDOWS: dict[int, tuple[int, dict[str, int]]] = {
    10: (68, {"dwell_hold": 68, "backlog_recovery": 0, "other": 0}),
    20: (20, {"dwell_hold": 12, "backlog_recovery": 8, "other": 0}),
    30: (120, {"dwell_hold": 70, "backlog_recovery": 50, "other": 0}),
    40: (0, {"dwell_hold": 0, "backlog_recovery": 0, "other": 0}),
    50: (68, {"dwell_hold": 68, "backlog_recovery": 0, "other": 0}),
    60: (68, {"dwell_hold": 68, "backlog_recovery": 0, "other": 0}),
    70: (25, {"dwell_hold": 0, "backlog_recovery": 0, "other": 25}),
}


def generate_synthetic_ndjson() -> str:
    """Emit an 80-row CALIB-01 fixture with seven completed windows."""
    total = 0
    by_cause = {"dwell_hold": 0, "backlog_recovery": 0, "other": 0}
    window_epoch = 0.0
    lifetime_by_cause = {"dwell_hold": 0, "backlog_recovery": 0, "other": 0}
    lines: list[str] = []
    for i in range(80):
        if i in BOUNDARY_WINDOWS:
            total, by_cause = BOUNDARY_WINDOWS[i]
            window_epoch = float(i)
            for cause, count in by_cause.items():
                lifetime_by_cause[cause] += count
        zone = ("GREEN", "YELLOW", "SOFT_RED", "RED")[(i // 20) % 4]
        row = {
            "t_wall": f"2026-05-07T00:{i // 60:02d}:{i % 60:02d}Z",
            "t_monotonic": float(i),
            "version": "1.43.0",
            "status": "healthy",
            "floor_hit_cycles_total": 0,
            "suppressions_per_min": 0,
            "max_delay_delta_us": 0,
            "red_streak": 0,
            "zone_trace_tail": [zone] * 5,
            "headroom_state": "AVAILABLE",
            "headroom_exhausted_streak": 0,
            "anti_windup_triggers": 0,
            "rtt_integral_ms_s": 0.0,
            "docsis_mode_active": True,
            "red_decay_step_pct": 0.02,
            "red_decay_delta_max_pct": 0.10,
            "load_rtt_ms": 12.0,
            "baseline_rtt_ms": 12.0,
            "load_rtt_delta_us": 0,
            "last_zone": zone,
            "ul_hysteresis_window_start_epoch": window_epoch,
            "ul_suppressions_completed_window_count": total,
            "ul_suppressions_completed_window_by_cause": dict(by_cause),
            "ul_suppressions_lifetime_by_cause": dict(lifetime_by_cause),
        }
        lines.append(json.dumps(row, sort_keys=True))
    return "\n".join(lines) + "\n"


def write_fixture(out_path: Path) -> None:
    out_path.write_text(generate_synthetic_ndjson(), encoding="utf-8")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    write_fixture(repo_root / "tests" / "fixtures" / "phase_204_synthetic_capture.ndjson")

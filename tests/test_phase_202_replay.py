"""METRIC-03 replay tests for v1.43 Phase 202.

Pins the codex re-aggregation oracle for the v1.42 reference soak's
completed-window suppression distribution against the offline aggregation
of the published `suppressions_per_min` column. Plus synthetic-trace
unit tests exercising the Plan 202-01 reset_window snapshot machinery.

Fixture path is the v1.42 milestone directory — REQUIREMENTS.md/ROADMAP.md
cite a repo-root-relative form that is incorrect; the canonical location
is under `.planning/milestones/v1.42-phases/201-.../soak/...`.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOAK_CAPTURE_NDJSON = (
    REPO_ROOT
    / ".planning"
    / "milestones"
    / "v1.42-phases"
    / "201-docsis-aware-ul-congestion-control"
    / "soak"
    / "20260505T132736Z"
    / "soak-capture.ndjson"
)

# Codex oracle (markdown-cited in 201-VERIFICATION.md and 201-17 closeout PLAN).
# METRIC-03 mechanically verifies these against the offline aggregation here.
ORACLE_PEAK_MEAN_APPROX = 13.9
ORACLE_PEAK_MEAN_TOL = 0.5
ORACLE_P95 = 41
ORACLE_MAX = 124
ORACLE_OBSERVED_RESET_WINDOWS = 1331


def aggregate_completed_windows(snapshots: list[int]) -> list[int]:
    """Detect 60s window resets and return per-window completed totals.

    Algorithm: walk the sequence. Whenever snapshots[i] < snapshots[i-1],
    the previous sample (snapshots[i-1]) is the just-completed window's
    total. Equality means no boundary crossed. Partial first/last windows
    (no preceding or following reset) are discarded.

    Independently consistent with `suppression-stats.json::window_count`
    from the v1.42 reference soak (1,439 completed windows over 84,117
    samples ≈ 58.5 samples per window @ 1Hz capture).
    """
    if len(snapshots) < 2:
        return []
    out: list[int] = []
    for i in range(1, len(snapshots)):
        if snapshots[i] < snapshots[i - 1]:
            out.append(int(snapshots[i - 1]))
    return out


def _percentile(values: list[int], p: float) -> float:
    """Return NumPy-default linear percentile without requiring NumPy."""
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    fraction = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


class TestAggregateCompletedWindows:
    def test_helper_basic_resets(self) -> None:
        assert aggregate_completed_windows([0, 1, 2, 3, 0, 5, 7, 0, 1]) == [3, 7]

    def test_helper_empty(self) -> None:
        assert aggregate_completed_windows([]) == []

    def test_helper_single_sample(self) -> None:
        assert aggregate_completed_windows([5]) == []

    def test_helper_monotone_no_resets(self) -> None:
        assert aggregate_completed_windows([0, 1, 2, 3, 4]) == []

    def test_helper_equality_is_not_reset(self) -> None:
        assert aggregate_completed_windows([0, 5, 5, 0, 7]) == [5]

    def test_helper_reset_at_end(self) -> None:
        assert aggregate_completed_windows([0, 3, 0]) == [3]


class TestCompletedWindowOracle:
    def test_completed_window_aggregation_matches_codex_oracle(self) -> None:
        """METRIC-03: completed-window counts re-aggregated from
        soak/20260505T132736Z match codex oracle: peak mean ~13.9/min,
        p95=41, max=124.
        """
        if not SOAK_CAPTURE_NDJSON.exists():
            pytest.skip(f"reference soak fixture absent at {SOAK_CAPTURE_NDJSON}")
        snapshots: list[int] = []
        with SOAK_CAPTURE_NDJSON.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                val = row.get("suppressions_per_min")
                if val is None:
                    continue
                snapshots.append(int(val))
        window_counts = aggregate_completed_windows(snapshots)
        # The reset detector observes windows where the live counter drops.
        # `suppression-stats.json::window_count=1439` is a nominal elapsed-window
        # count, while zero-suppression windows leave no decreasing edge in the
        # `suppressions_per_min` snapshot sequence. The oracle distribution below
        # is over the 1,331 observable completed suppression windows.
        assert len(window_counts) == ORACLE_OBSERVED_RESET_WINDOWS
        mean = statistics.fmean(window_counts)
        assert mean == pytest.approx(
            ORACLE_PEAK_MEAN_APPROX, abs=ORACLE_PEAK_MEAN_TOL
        ), f"mean {mean} drifted from codex oracle {ORACLE_PEAK_MEAN_APPROX}"
        assert _percentile(window_counts, 95) == ORACLE_P95
        assert max(window_counts) == ORACLE_MAX


class TestRecordSuppressionSyntheticTrace:
    def _make_qc(self):
        from wanctl.queue_controller import QueueController

        return QueueController(
            name="upload",
            floor_green=8_000_000,
            floor_yellow=8_000_000,
            floor_soft_red=8_000_000,
            floor_red=8_000_000,
            ceiling=18_000_000,
            step_up=5_000_000,
            factor_down=0.90,
            factor_down_yellow=1.0,
            green_required=3,
            dwell_cycles=3,
            deadband_ms=3.0,
            consecutive_yellow_decay_clamp=40,
        )

    def test_first_window_snapshot(self) -> None:
        qc = self._make_qc()
        for _ in range(11):
            qc._record_suppression("dwell_hold")
        for _ in range(4):
            qc._record_suppression("backlog_recovery")
        assert qc._window_suppressions_by_cause == {
            "dwell_hold": 11,
            "backlog_recovery": 4,
            "other": 0,
        }
        assert qc._lifetime_suppressions_by_cause == {
            "dwell_hold": 11,
            "backlog_recovery": 4,
            "other": 0,
        }
        assert qc._last_completed_window_total == 0
        ret = qc.reset_window()
        # Q1: helper does NOT advance _window_suppressions; only the
        # dwell-hold callsite advances the legacy live counter, and this
        # synthetic trace exercises the helper directly.
        assert ret == 0
        assert qc._last_completed_window_total == 15
        assert qc._last_completed_window_by_cause == {
            "dwell_hold": 11,
            "backlog_recovery": 4,
            "other": 0,
        }
        assert qc._window_suppressions_by_cause == {
            "dwell_hold": 0,
            "backlog_recovery": 0,
            "other": 0,
        }
        assert qc._lifetime_suppressions_by_cause == {
            "dwell_hold": 11,
            "backlog_recovery": 4,
            "other": 0,
        }

    def test_second_window_lifetime_is_monotonic(self) -> None:
        qc = self._make_qc()
        # First window: 11 dwell + 4 backlog.
        for _ in range(11):
            qc._record_suppression("dwell_hold")
        for _ in range(4):
            qc._record_suppression("backlog_recovery")
        qc.reset_window()

        # Second window: 3 dwell + 2 backlog.
        for _ in range(3):
            qc._record_suppression("dwell_hold")
        for _ in range(2):
            qc._record_suppression("backlog_recovery")
        qc.reset_window()
        assert qc._last_completed_window_total == 5
        assert qc._last_completed_window_by_cause == {
            "dwell_hold": 3,
            "backlog_recovery": 2,
            "other": 0,
        }
        assert qc._lifetime_suppressions_by_cause == {
            "dwell_hold": 14,
            "backlog_recovery": 6,
            "other": 0,
        }

"""Phase 203 capture-projection contract tests (OBSV-05, OBSV-07 capture side).

Validates that scripts/soak-capture.sh's jq projection emits the eight new
Phase 203 keys with correct values when fed a synthesized /health payload.
Does NOT require a live daemon, a soak fixture, or network access.

The test extracts the projection from the script body so a future edit to
the script is exercised here automatically (no double source of truth).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = REPO_ROOT / "scripts" / "soak-capture.sh"


def _extract_projection(script_path: Path) -> str:
    """Slice the jq object literal out of the capture script.

    Returns the text between the first '{' and the matching closing '}' that
    appears on a line containing only whitespace + '}' + the closing quote.
    Conservative: relies on the script keeping the v1.42 layout (jq '{...}').
    """
    text = script_path.read_text()
    # The projection lives inside `jq -c ... '{ ... }'`. Match the '{' that
    # follows the opening quote and capture until the matching '}' before the
    # script redirects jq output (append in v1.43, temp file in HRDN-02).
    match = re.search(r"jq\s+-c[^']*'(\{.*?\})'\s*(?:<[^>]+)?\s*(?:>>|>)", text, re.DOTALL)
    if match is None:
        raise RuntimeError(
            "Could not extract jq projection from scripts/soak-capture.sh; "
            "did the script structure change?"
        )
    return match.group(1)


SYNTHETIC_HEALTHY = {
    "version": "1.43-dev",
    "status": "healthy",
    "wans": [
        {
            "name": "synthetic-wan",
            "load_rtt_ms": 18.42,
            "baseline_rtt_ms": 12.0,
            "upload": {
                "floor_hit_cycles_total": 0,
                "max_delay_delta_us": 56,
                "red_streak": 0,
                "rtt_integral_ms_s": 2.293,
                "docsis_mode_active": True,
                "red_decay_step_pct": 0.02,
                "red_decay_delta_max_pct": 0.10,
                "headroom_state": "AVAILABLE",
                "headroom_exhausted_streak": 0,
                "anti_windup_triggers": 0,
                "zone_trace": ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"],
                "hysteresis": {
                    "suppressions_per_min": 17,
                    "last_zone": "GREEN",
                    "window_start_epoch": 1730000000,
                    "suppressions_completed_window_count": 13,
                    "suppressions_completed_window_by_cause": {
                        "dwell_hold": 13,
                        "backlog_recovery": 0,
                        "other": 0,
                    },
                    "suppressions_lifetime_by_cause": {
                        "dwell_hold": 13,
                        "backlog_recovery": 0,
                        "other": 0,
                    },
                },
            },
        }
    ],
}


def _run_projection(health_payload: dict) -> dict:
    """Run the capture script's jq projection against a synthesized /health blob.

    Substitutes the runtime jq vars ($twall, $tmono) via --arg/--argjson so the
    projection runs without the surrounding bash loop.
    """
    if shutil.which("jq") is None:
        pytest.skip("jq not on PATH; required for capture-projection contract test")
    projection = _extract_projection(CAPTURE_SCRIPT)
    result = subprocess.run(
        [
            "jq",
            "-c",
            "--arg",
            "twall",
            "2026-05-06T00:00:00Z",
            "--argjson",
            "tmono",
            "0",
            projection,
        ],
        input=json.dumps(health_payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class TestNewFieldsProjection:
    """OBSV-05: the eight new Phase 203 keys are emitted with correct values."""

    def test_load_rtt_delta_us_computed_correctly(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        # (18.42 - 12.0) * 1000 = 6420.0 → floor → 6420
        assert row["load_rtt_delta_us"] == 6420

    def test_load_rtt_ms_and_baseline_rtt_ms_passed_through(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        assert row["load_rtt_ms"] == pytest.approx(18.42)
        assert row["baseline_rtt_ms"] == pytest.approx(12.0)

    def test_last_zone_projected(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        assert row["last_zone"] == "GREEN"

    def test_ul_suppression_fields_projected_with_prefix(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        assert row["ul_suppressions_completed_window_count"] == 13
        assert row["ul_suppressions_completed_window_by_cause"] == {
            "dwell_hold": 13,
            "backlog_recovery": 0,
            "other": 0,
        }
        assert row["ul_suppressions_lifetime_by_cause"] == {
            "dwell_hold": 13,
            "backlog_recovery": 0,
            "other": 0,
        }

    def test_new_fields_present_complete_set(self) -> None:
        """All eight new keys appear on every row (boundary marker added post-d44e2fd)."""
        row = _run_projection(SYNTHETIC_HEALTHY)
        for key in (
            "load_rtt_ms",
            "baseline_rtt_ms",
            "load_rtt_delta_us",
            "last_zone",
            "ul_hysteresis_window_start_epoch",
            "ul_suppressions_completed_window_count",
            "ul_suppressions_completed_window_by_cause",
            "ul_suppressions_lifetime_by_cause",
        ):
            assert key in row, f"missing new Phase 203 key: {key}"


class TestV142KeysPreserved:
    """SAFE-07 / OBSV-08 implication: v1.42 keys remain byte-identical."""

    def test_v142_keys_all_present(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        for key in (
            "t_wall",
            "t_monotonic",
            "version",
            "status",
            "floor_hit_cycles_total",
            "suppressions_per_min",
            "max_delay_delta_us",
            "red_streak",
            "zone_trace_tail",
            "headroom_state",
            "headroom_exhausted_streak",
            "anti_windup_triggers",
            "rtt_integral_ms_s",
            "docsis_mode_active",
            "red_decay_step_pct",
            "red_decay_delta_max_pct",
        ):
            assert key in row, f"v1.42 key dropped: {key}"

    def test_zone_trace_tail_is_last_5(self) -> None:
        row = _run_projection(SYNTHETIC_HEALTHY)
        # SYNTHETIC_HEALTHY has 5 zones in zone_trace; tail is the last 5.
        assert row["zone_trace_tail"] == ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"]


class TestNullHandling:
    """Gray-area decision #8: null source fields → null delta, no crash."""

    def test_null_load_rtt_ms_yields_null_delta(self) -> None:
        payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
        payload["wans"][0]["load_rtt_ms"] = None
        row = _run_projection(payload)
        assert row["load_rtt_delta_us"] is None

    def test_null_baseline_rtt_ms_yields_null_delta(self) -> None:
        payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
        payload["wans"][0]["baseline_rtt_ms"] = None
        row = _run_projection(payload)
        assert row["load_rtt_delta_us"] is None


class TestNegativeDelta:
    """Realistic case: load_rtt below baseline (sub-baseline measurement)."""

    def test_negative_delta_floored_correctly(self) -> None:
        payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
        payload["wans"][0]["load_rtt_ms"] = 11.5
        payload["wans"][0]["baseline_rtt_ms"] = 12.0
        row = _run_projection(payload)
        # (11.5 - 12.0) * 1000 = -500.0 → floor → -500
        assert row["load_rtt_delta_us"] == -500

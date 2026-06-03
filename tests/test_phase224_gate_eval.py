from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phase224-gate-eval.py"
SPEC = importlib.util.spec_from_file_location("phase224_gate_eval", MODULE_PATH)
assert SPEC is not None
phase224_gate_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phase224_gate_eval)


def _hash(value: str) -> str:
    return value * 64


def _health(*, status: str = "healthy", rtt_age: float = 1.2, time_in_state: float = 60.0):
    return {
        "version": "1.45.0",
        "status": status,
        "decision": {
            "last_transition_time": "2026-06-03T03:00:00Z",
            "time_in_state_seconds": time_in_state,
        },
        "rtt_source": {
            "current": "autorate_health",
            "last_successful": "autorate_health",
            "last_measurement_age_sec": rtt_age,
        },
    }


def _spine(
    *,
    captured_at: str = "2026-06-03T03:15:00Z",
    binary_match: bool = True,
    only_new_match: bool = True,
    spectrum_match: bool = True,
    deployed_sha256: str | None = None,
    baseline_sha256: str | None = None,
):
    deployed = deployed_sha256 or _hash("a")
    baseline = baseline_sha256 or deployed
    return {
        "captured_at": captured_at,
        "target_host": "cake-shaper",
        "raw_health_path": "/tmp/raw-health.json",
        "health": {},
        "spine": {
            "binary_on_off": {
                "enabled": True,
                "rule_present": binary_match,
                "match": binary_match,
            },
            "only_new_connections": {
                "live_selector": {},
                "expected_selector": {},
                "match": only_new_match,
            },
            "spectrum_state_not_written_by_daemon": {
                "method": "code-fingerprint",
                "daemon_source_path": "/opt/wanctl/steering/daemon.py",
                "deployed_sha256": deployed,
                "baseline_sha256": baseline,
                "match": spectrum_match,
                "read_error": None,
            },
        },
    }


def _evaluate(health=None, spine=None, **kwargs):
    return phase224_gate_eval.evaluate(
        health_payload=health or _health(),
        spine_payload=spine or _spine(),
        expected_version="1.45.0",
        snapshot="evidence/snapshot-a/example",
        observation_start_ts=kwargs.pop("observation_start_ts", "2026-06-03T03:00:00Z"),
        observation_end_ts=kwargs.pop("observation_end_ts", "2026-06-03T03:15:00Z"),
        **kwargs,
    )


def test_all_gates_pass_returns_kept_aligned_at_end_of_window():
    verdict = _evaluate()

    assert verdict["outcome"] == "kept_aligned"
    assert verdict["rollback_trigger"] is None
    assert verdict["window_end_reached"] is True


def test_all_gates_pass_before_window_end_returns_continue_observation():
    verdict = _evaluate(
        spine=_spine(captured_at="2026-06-03T03:14:59Z"),
        observation_end_ts="2026-06-03T03:15:00Z",
    )

    assert verdict["outcome"] == "continue_observation"
    assert verdict["window_end_reached"] is False


def test_restart_window_binary_violation_does_not_trigger_rollback():
    verdict = _evaluate(
        health=_health(time_in_state=0.25),
        spine=_spine(captured_at="2026-06-03T03:00:00.250000Z", binary_match=False),
        observation_start_ts="2026-06-03T03:00:00Z",
        observation_end_ts="2026-06-03T03:15:00Z",
    )

    gate = verdict["gates"]["gate_binary_on_off"]
    assert verdict["outcome"] == "continue_observation"
    assert verdict["rollback_trigger"] is None
    assert gate["verdict"] == "restart_window_symptom"
    assert gate["restart_window_symptom"] is True


def test_steady_state_binary_violation_triggers_rollback():
    verdict = _evaluate(
        spine=_spine(captured_at="2026-06-03T03:01:00Z", binary_match=False),
        observation_start_ts="2026-06-03T03:00:00Z",
    )

    assert verdict["outcome"] == "rollback"
    assert verdict["rollback_trigger"] == "gate_binary_on_off"


def test_rtt_source_stale_triggers_rollback():
    verdict = _evaluate(health=_health(rtt_age=10.0))

    assert verdict["outcome"] == "rollback"
    assert verdict["rollback_trigger"] == "gate_rtt_source_fresh"


def test_rtt_source_fresh_passes():
    verdict = _evaluate(health=_health(rtt_age=1.2))

    assert verdict["gates"]["gate_rtt_source_fresh"]["verdict"] == "pass"


def test_health_input_as_canary_check_summary_array_fails_explicitly():
    with pytest.raises(phase224_gate_eval.GateEvalError, match="raw /health JSON"):
        _evaluate(health=[{"target": "steering", "service": "health", "result": "PASS", "detail": "ok"}])


def test_spectrum_state_fingerprint_match_passes():
    verdict = _evaluate(
        spine=_spine(
            deployed_sha256="aaaa" + "b" * 60,
            baseline_sha256="aaaa" + "b" * 60,
            spectrum_match=True,
        )
    )

    assert verdict["gates"]["gate_spectrum_state_not_written_by_daemon"]["verdict"] == "pass"


def test_spectrum_state_fingerprint_mismatch_triggers_rollback_even_in_restart_window():
    verdict = _evaluate(
        health=_health(time_in_state=0.25),
        spine=_spine(
            captured_at="2026-06-03T03:00:00.250000Z",
            deployed_sha256=_hash("a"),
            baseline_sha256=_hash("b"),
            spectrum_match=False,
        ),
        observation_start_ts="2026-06-03T03:00:00Z",
        observation_end_ts="2026-06-03T03:15:00Z",
    )

    gate = verdict["gates"]["gate_spectrum_state_not_written_by_daemon"]
    assert verdict["outcome"] == "rollback"
    assert verdict["rollback_trigger"] == "gate_spectrum_state_not_written_by_daemon"
    assert gate["verdict"] == "fail"
    assert gate["restart_window_symptom"] is False


def test_spectrum_state_legacy_file_absence_shape_fails_fast():
    legacy = _spine()
    legacy["spine"]["spectrum_state_not_written_by_daemon"] = {
        "match": True,
    }

    with pytest.raises(phase224_gate_eval.GateEvalError, match="code-fingerprint"):
        _evaluate(spine=legacy)

"""Offline regression tests for scripts/phase200-saturation-canary.sh helpers.

Uses the script's --self-test mode (added in Plan 200-11) instead of fragile
sed-range extraction. Codex MEDIUM finding (200-REVIEWS.md): bash functions
end with `}`, not `}}`, so range-based sourcing of a function fragment from
within the operational script is unsafe.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "phase200-saturation-canary.sh"


def _run_summarize_baseline(ndjson_text: str, label: str = "test") -> dict:
    """Invoke the script's summarize_baseline() helper via --self-test."""
    in_ndjson = REPO_ROOT / "tests" / "_phase200_in.ndjson"
    out_json = REPO_ROOT / "tests" / "_phase200_out.json"
    in_ndjson.write_text(ndjson_text)
    try:
        subprocess.run(
            [
                "bash",
                str(SCRIPT),
                "--self-test",
                "summarize_baseline",
                str(in_ndjson),
                str(out_json),
                label,
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return json.loads(out_json.read_text())
    finally:
        in_ndjson.unlink(missing_ok=True)
        out_json.unlink(missing_ok=True)


def _make_health_line(baseline_rtt_ms):
    return json.dumps({"wans": [{"baseline_rtt_ms": baseline_rtt_ms}]})


def test_self_test_usage_exits_clean():
    """--self-test with no further args prints usage and exits 0."""
    result = subprocess.run(
        ["bash", str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "summarize_baseline" in result.stdout


def test_summarize_baseline_extracts_numeric_rtt_values():
    rtts = [18.0, 19.5, 17.2, 21.0, 18.8]
    ndjson = "\n".join(_make_health_line(r) for r in rtts) + "\n"
    result = _run_summarize_baseline(ndjson)
    assert result["sample_count"] == 5
    assert result["baseline_rtt_ms"]["min"] == 17.2
    assert result["baseline_rtt_ms"]["max"] == 21.0


def test_summarize_baseline_handles_all_null_baseline():
    ndjson = "\n".join(_make_health_line(None) for _ in range(3)) + "\n"
    result = _run_summarize_baseline(ndjson)
    assert result["sample_count"] == 0
    assert result["baseline_rtt_ms"]["min"] is None


def test_summarize_baseline_rejects_old_broken_path():
    """Regression: the previous bug nested baseline_rtt_ms under .wans[0].rtt."""
    nested = json.dumps({"wans": [{"rtt": {"baseline_rtt_ms": 18.0}}]})
    ndjson = (nested + "\n") * 3
    result = _run_summarize_baseline(ndjson)
    # Path is correct now; OLD-shape input produces no samples.
    assert result["sample_count"] == 0


def _run_validate_remote_yaml_path(path: str) -> tuple[int, str]:
    """Drive validate_remote_yaml_path via --self-test mode.

    Round-2 HIGH (WR-02 test ordering): the previous tests pointed
    PHASE200_SPECTRUM_HEALTH_URL at http://127.0.0.1:1/health to reach the
    path validator in live mode. The script's health preflight runs BEFORE
    the path validator, so live-mode tests aborted with
    health_unreachable_or_shape_invalid and never reached the gate under
    test (false-green: tests passed by erroring out at the wrong stage).
    --self-test mode bypasses the preflight and invokes the validator
    function directly, so tests assert the validator's actual behavior.
    """
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--self-test", "validate_remote_yaml_path", path],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return proc.returncode, proc.stderr


def test_remote_yaml_path_rejects_metacharacters():
    # Path component (after user@host:) — contains a `;` shell metachar.
    rc, err = _run_validate_remote_yaml_path("/etc/wanctl/spectrum.yaml; rm -rf /")
    assert rc == 2
    assert "remote_yaml_path_unsafe" in err or "safe chars only" in err


def test_remote_yaml_path_rejects_relative_path():
    rc, err = _run_validate_remote_yaml_path("etc/wanctl/spectrum.yaml")
    assert rc == 2
    assert "remote_yaml_path_unsafe" in err or "safe chars only" in err


def test_remote_yaml_path_rejects_command_substitution():
    """Round-2 HIGH augment: $() shell-substitution must be rejected."""
    rc, err = _run_validate_remote_yaml_path("/etc/wanctl/$(rm -rf /).yaml")
    assert rc == 2
    assert "remote_yaml_path_unsafe" in err or "safe chars only" in err


def test_remote_yaml_path_rejects_dot_dot():
    """Round-2 HIGH augment: traversal-like relative path (does not start with /)."""
    rc, err = _run_validate_remote_yaml_path("../etc/passwd")
    assert rc == 2


def test_remote_yaml_path_accepts_safe_absolute_path():
    """Safe path passes validator; exit code 0."""
    rc, err = _run_validate_remote_yaml_path("/etc/wanctl/spectrum.yaml")
    assert rc == 0
    assert "remote_yaml_path_unsafe" not in err


# Phase 201 Wave 0 RED scaffolding — Plan 201-02 stubs.
# Implementation lands in Plans 201-03 (config/validator),
# 201-04 (controller core), 201-05 (telemetry / wan_controller),
# 201-07 (predeploy gate), 201-08 (canary extension).


def _run_phase201_self_test(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--self-test", name, *args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode == 0 and "unknown self-test" in proc.stdout.lower():
        pytest.skip(f"Wave 0 stub — implementation in Plan 201-08: {name}")
    if proc.returncode != 0 and "unknown self-test" in (proc.stdout + proc.stderr).lower():
        pytest.skip(f"Wave 0 stub — implementation in Plan 201-08: {name}")
    return proc


class TestPhase201Preflight:
    def test_env_yaml_docsis_mode_match_pass(self):
        result = _run_phase201_self_test("phase201-preflight", "docsis_match")
        assert result.returncode == 0

    def test_env_yaml_docsis_mode_mismatch_aborts(self):
        result = _run_phase201_self_test("phase201-preflight", "docsis_mismatch")
        assert result.returncode == 2
        assert "docsis_mode" in result.stderr + result.stdout

    def test_env_yaml_setpoint_mbps_mismatch_aborts(self):
        result = _run_phase201_self_test("phase201-preflight", "setpoint_mismatch")
        assert result.returncode == 2
        assert "setpoint" in result.stderr + result.stdout

    def test_health_docsis_key_absent_aborts(self):
        result = _run_phase201_self_test("phase201-health", "absent")
        assert result.returncode == 2
        assert "health_docsis_key_absent" in result.stderr + result.stdout

    def test_health_docsis_false_aborts(self):
        result = _run_phase201_self_test("phase201-health", "false")
        assert result.returncode == 2
        assert "health_docsis_false" in result.stderr + result.stdout

    def test_remote_python_yaml_missing_aborts(self):
        result = _run_phase201_self_test("phase201-remote-python-yaml", "missing")
        assert result.returncode == 2
        assert "remote_python_yaml_missing" in result.stderr + result.stdout

    def test_health_docsis_invalid_aborts(self):
        result = _run_phase201_self_test("phase201-health", "invalid")
        assert result.returncode == 2
        assert "health_docsis_invalid" in result.stderr + result.stdout


class TestPhase201EnvFailClosed:
    def test_missing_docsis_mode_env_aborts(self):
        result = _run_phase201_self_test("phase201-env", "missing_docsis_mode")
        assert result.returncode == 2

    def test_missing_setpoint_mbps_env_aborts(self):
        result = _run_phase201_self_test("phase201-env", "missing_setpoint_mbps")
        assert result.returncode == 2

    def test_both_legacy_and_docsis_env_set_aborts(self):
        result = _run_phase201_self_test("phase201-env", "legacy_and_docsis")
        assert result.returncode == 2

    def test_legacy_mode_only_ok(self):
        result = _run_phase201_self_test("phase201-env", "legacy_only")
        assert result.returncode == 0


class TestPhase201CounterDeltaVerdict:
    def _json_for(self, name: str) -> tuple[int, dict]:
        result = _run_phase201_self_test(name)
        return result.returncode, json.loads(result.stdout)

    def test_counter_delta_pass(self):
        rc, verdict = self._json_for("phase201-counter-delta-pass")
        assert rc == 0
        assert verdict["verdict"] == "pass"
        assert verdict["floor_hit_cycles_total_delta_loaded_window"] == 0
        assert verdict["primary_gate"] == "floor_hit_cycles_total_delta_loaded_window"
        assert verdict["primary_gate_value"] == 0

    def test_counter_delta_primary_fail(self):
        rc, verdict = self._json_for("phase201-counter-delta-primary-fail")
        assert rc == 1
        assert verdict["verdict"] == "fail"
        assert verdict["floor_hit_cycles_total_delta_loaded_window"] == 4
        assert verdict["reason"].startswith("primary_gate_floor_hit_cycles_delta")

    def test_counter_delta_secondary_disagreement_fails(self):
        rc, verdict = self._json_for("phase201-counter-delta-secondary-disagreement")
        assert rc == 1
        assert verdict["verdict"] == "fail"
        assert verdict["reason"].startswith("secondary_gate_disagreement")

    def test_counter_delta_both_fail(self):
        rc, verdict = self._json_for("phase201-counter-delta-both-fail")
        assert rc == 1
        assert verdict["verdict"] == "fail"
        assert verdict["reason"] == "ul_floor_hits_during_load_4_counter_delta_4"

    def test_counter_delta_field_missing_aborts(self):
        rc, verdict = self._json_for("phase201-counter-delta-field-missing")
        assert rc == 2
        assert verdict["verdict"] == "abort"
        assert verdict["reason"] == "phase201_floor_hit_counter_field_missing"

    def test_counter_delta_negative_aborts(self):
        rc, verdict = self._json_for("phase201-counter-delta-negative")
        assert rc == 2
        assert verdict["verdict"] == "abort"
        assert verdict["reason"] == "phase201_floor_hit_counter_delta_negative"

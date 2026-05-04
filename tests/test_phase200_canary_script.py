"""Offline regression tests for scripts/phase200-saturation-canary.sh helpers.

Uses the script's --self-test mode (added in Plan 200-11) instead of fragile
sed-range extraction. Codex MEDIUM finding (200-REVIEWS.md): bash functions
end with `}`, not `}}`, so range-based sourcing of a function fragment from
within the operational script is unsafe.
"""

import json
import subprocess
from pathlib import Path

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

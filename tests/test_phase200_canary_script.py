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

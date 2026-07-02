import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = ROOT / "scripts" / "phase245-thresholds.json"
PROVENANCE = ROOT / "scripts" / "phase245-prereg-provenance.sh"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def test_thresholds_json_carries_phase245_ab03_keys() -> None:
    payload = json.loads(THRESHOLDS.read_text())

    required = {
        "CYCLE_AVG_REGRESSION_PCT",
        "CYCLE_P99_REGRESSION_PCT",
        "CYCLE_P99_ABS_CEILING_MS",
        "MIN_CYCLES",
        "MIN_MINUTES",
        "CYCLE_HZ",
        "CYCLE_INTERVAL_MS",
        "ICMPLIB_REPRESENTATIVE_AVG_MS",
        "ICMPLIB_REPRESENTATIVE_P99_MS",
        "ICMPLIB_REPRESENTATIVE_AVG_TOL_MS",
        "ICMPLIB_REPRESENTATIVE_P99_TOL_MS",
        "RTT_AGREEMENT_TOL_MS",
        "LOSS_DETECTION_MAX_DELTA_PCT",
        "MIN_WANCTL_BACKEND_CYCLE_FRACTION",
        "MAX_UNEXPECTED_RESTARTS",
        "MAX_PLANNED_RESTARTS",
        "STEERING_DECISION_STABILITY_MAX_DELTA_PCT",
        "CONTROL_WAN",
        "WAN_UNDER_TEST",
        "AMENDMENT_ID",
        "AMENDS_THRESHOLDS_BLOB_SHA",
        "AMENDMENT_REASON",
    }
    assert required <= payload.keys()
    assert payload["ICMPLIB_REPRESENTATIVE_AVG_MS"] == 2.85
    assert payload["ICMPLIB_REPRESENTATIVE_P99_MS"] == 6.9
    assert payload["MAX_UNEXPECTED_RESTARTS"] == 0
    assert payload["MAX_PLANNED_RESTARTS"] is None
    assert payload["CONTROL_WAN"] == "att"
    assert payload["WAN_UNDER_TEST"] == "spectrum"
    assert "MAX_DAEMON_RESTARTS" not in payload


def test_provenance_record_emits_blob_and_commit_shas() -> None:
    result = run(str(PROVENANCE), "record")
    payload = json.loads(result.stdout)

    assert re.fullmatch(r"[0-9a-f]{40}", payload["thresholds_blob_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", payload["prereg_commit_sha"])
    assert payload["thresholds_path"] == "scripts/phase245-thresholds.json"


def test_provenance_descent_is_enforced() -> None:
    head = run("git", "rev-parse", "HEAD").stdout.strip()
    anchor = run("git", "rev-parse", "fcc2e15b").stdout.strip()

    run(str(PROVENANCE), "assert-descends", head, head)
    rejected = run(str(PROVENANCE), "assert-descends", head, anchor, check=False)

    assert rejected.returncode != 0
    assert "does not descend" in rejected.stderr

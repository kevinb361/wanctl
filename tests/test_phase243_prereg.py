import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = ROOT / "scripts" / "phase243-thresholds.json"
PREREG = ROOT / ".planning" / "phases" / "243-cycle-budget-benchmark-gate" / "243-BENCHMARK-PREREGISTRATION.md"
PROVENANCE = ROOT / "scripts" / "phase243-prereg-provenance.sh"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_thresholds_json_carries_frozen_preregistration_keys() -> None:
    payload = json.loads(THRESHOLDS.read_text())

    required = {
        "CYCLE_AVG_REGRESSION_PCT",
        "CYCLE_P99_REGRESSION_PCT",
        "CYCLE_P99_ABS_CEILING_MS",
        "CPU_DELTA_PCT_POINTS",
        "ZOMBIES_MAX",
        "TASKS_BOUND",
        "STALL_GAP_MS",
        "MIN_CYCLES",
        "MIN_MINUTES",
        "CYCLE_HZ",
        "CYCLE_INTERVAL_MS",
        "ICMPLIB_REPRESENTATIVE_AVG_TOL_MS",
        "ICMPLIB_REPRESENTATIVE_P99_TOL_MS",
        "CPU_NORMALIZATION",
    }
    assert required <= payload.keys()
    assert payload["CPU_NORMALIZATION"] == "per_core"


def test_preregistration_markdown_references_thresholds_single_source() -> None:
    text = PREREG.read_text()

    assert "phase243-thresholds.json" in text
    assert "HARD validity" in text
    assert "input_error" in text


def test_provenance_record_emits_blob_and_commit_shas() -> None:
    result = run(str(PROVENANCE), "record")
    payload = json.loads(result.stdout)

    assert re.fullmatch(r"[0-9a-f]{40}", payload["thresholds_blob_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", payload["prereg_commit_sha"])
    assert payload["thresholds_path"] == "scripts/phase243-thresholds.json"


def test_provenance_descent_is_enforced() -> None:
    head = run("git", "rev-parse", "HEAD").stdout.strip()
    anchor = run("git", "rev-parse", "fcc2e15b").stdout.strip()

    run(str(PROVENANCE), "assert-descends", head, head)
    rejected = run(str(PROVENANCE), "assert-descends", head, anchor, check=False)

    assert rejected.returncode != 0
    assert "does not descend" in rejected.stderr

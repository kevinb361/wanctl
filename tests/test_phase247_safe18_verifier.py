import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase247-safe18-boundary-check.sh"
EVIDENCE = (
    ROOT
    / ".planning"
    / "phases"
    / "247-fping-shadow-capture-phase-245-evidence-review"
    / "evidence"
    / "safe18-boundary-247.json"
)
D01_BOUNDARY_FILES = [
    "src/wanctl/autorate_continuous.py",
    "src/wanctl/rtt_backend_factory.py",
]
PHASE_CLOSE_ANCHOR = "e090a200"


def run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "SKIP_DOC_CHECK": "1"},
    )


def load_evidence() -> dict:
    result = run(["bash", str(VERIFIER)])
    assert result.returncode == 0, result.stderr
    assert EVIDENCE.exists()
    return json.loads(EVIDENCE.read_text())


class TestSafe18Verifier:
    def test_script_exists(self):
        assert VERIFIER.exists()
        assert os.access(VERIFIER, os.X_OK)

    def test_static_contract(self):
        text = VERIFIER.read_text()
        assert 'ANCHOR="e090a200"' in text
        assert "set -euo pipefail" in text
        assert "safe18-boundary-247.json" in text
        assert "autorate_continuous.py" in text
        assert "rtt_backend_factory.py" in text
        assert "changed_files_vs_anchor" in text
        assert "anchor_sha" in text
        assert "head_sha" in text
        assert "git diff --quiet HEAD" in text

    def test_clean_tree_exits_zero(self):
        result = run(["bash", str(VERIFIER)])
        assert result.returncode == 0, result.stderr

    def test_clean_tree_writes_evidence(self):
        result = run(["bash", str(VERIFIER)])
        assert result.returncode == 0, result.stderr
        assert EVIDENCE.exists()

    def test_evidence_json_passed_true(self):
        data = load_evidence()
        assert data["passed"] is True

    def test_evidence_json_verdict_pass(self):
        data = load_evidence()
        assert data["safe18_verdict"] == "pass"

    def test_evidence_records_full_shas(self):
        data = load_evidence()
        assert len(data["anchor_sha"]) == 40
        assert len(data["head_sha"]) == 40
        assert all(ch in "0123456789abcdef" for ch in data["anchor_sha"])
        assert all(ch in "0123456789abcdef" for ch in data["head_sha"])
        assert data["changed_files_vs_anchor"] == []

    def test_protected_list_includes_d01_boundary(self):
        data = load_evidence()
        protected = set(data["protected_files"])
        assert len(protected) == 9
        for path in D01_BOUNDARY_FILES:
            assert path in protected

    def test_anchor_is_pinned(self):
        assert PHASE_CLOSE_ANCHOR == "e090a200"

    def test_self_test_detects_violation(self):
        result = run(["bash", str(VERIFIER), "--self-test"])
        assert result.returncode == 0, result.stderr
        assert "self-test passed" in result.stdout

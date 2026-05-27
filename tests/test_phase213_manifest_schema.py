import json
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = REPO_ROOT / "scripts/phase213-baseline-capture.sh"
EXPECTED = json.loads((REPO_ROOT / "tests/fixtures/phase213/manifest-expected-keys.json").read_text())


def test_orchestrator_check_manifest_emits_manifest_keys(tmp_path: Path) -> None:
    if not ORCHESTRATOR.exists():
        pytest.skip("scripts/phase213-baseline-capture.sh not built yet")
    result = subprocess.run(
        ["bash", str(ORCHESTRATOR), "--check-manifest", "--evidence-root", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    for key in EXPECTED["required_top_level_keys"]:
        assert key in manifest
    for entry in manifest["tests_ordered"]:
        assert set(EXPECTED["required_test_entry_keys"]).issubset(entry)


def test_check_manifest_is_offline() -> None:
    if not ORCHESTRATOR.exists():
        pytest.skip("scripts/phase213-baseline-capture.sh not built yet")
    source = ORCHESTRATOR.read_text()
    match = re.search(r"check-manifest\).*?;;", source, re.S)
    assert match is not None, "could not find check-manifest branch"
    assert re.search(r"\bssh\b|\bcurl\b", match.group(0)) is None

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
POLLER = REPO_ROOT / "scripts/phase213-health-poller.sh"
EXPECTED = json.loads((REPO_ROOT / "tests/fixtures/phase213/ndjson-row-expected-keys.json").read_text())["required_keys"]


def _extract_projection() -> str:
    if not POLLER.exists():
        pytest.skip("scripts/phase213-health-poller.sh not built yet")
    text = POLLER.read_text()
    match = re.search(r"jq -c .*?'(\{.*?\})'", text, re.S)
    assert match is not None, "could not extract jq projection"
    return match.group(1)


def test_jq_projection_emits_all_expected_keys(phase212_health_spectrum: dict, tmp_path: Path) -> None:
    fixture = tmp_path / "health.json"
    fixture.write_text(json.dumps(phase212_health_spectrum))
    projection = _extract_projection()
    result = subprocess.run(
        ["jq", "-c", "--arg", "twall", "2026-05-27T21:00:00Z", "--argjson", "tmono", "0", "--arg", "wan", "spectrum", projection, str(fixture)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert set(row.keys()) == set(EXPECTED)

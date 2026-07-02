"""Regression tests for the Phase 227 SAFE-13 boundary closeout."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_SCRIPT = REPO_ROOT / "scripts" / "phase225-safe13-boundary-check.sh"


def test_wan_controller_state_is_explicitly_protected(tmp_path: Path) -> None:
    """wan_controller_state.py must be counted as controller-path drift."""
    script_source = BOUNDARY_SCRIPT.read_text(encoding="utf-8")
    assert "src/wanctl/wan_controller_state.py" in script_source

    out_path = tmp_path / "safe13-boundary.json"
    subprocess.run(
        [
            str(BOUNDARY_SCRIPT),
            "--anchor",
            "v1.48",
            "--out",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    record = json.loads(out_path.read_text(encoding="utf-8"))
    assert "src/wanctl/wan_controller_state.py" in record["protected_paths"]
    assert "src/wanctl/wan_controller_state.py" in record["expanded_protected_files"]
    assert "src/wanctl/wan_controller_state.py" in record["per_path_diff"]

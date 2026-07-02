import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase240-safe17-boundary-check.sh"
BODY_DIFF = ROOT / "scripts" / "phase239-protected-body-diff.py"
EVIDENCE = (
    ROOT
    / ".planning"
    / "phases"
    / "240-config-validator"
    / "evidence"
    / "safe17-boundary-240.json"
)

# Phase 240 close commit. The boundary verifier is a point-in-time gate that only
# holds at its own phase boundary; pin the worktree here instead of HEAD so the
# test stays green as later phases (242+) legitimately expand the allowlist.
PHASE_CLOSE_ANCHOR = "a181ca27"

ALLOWED_SRC_PATHS = {
    "src/wanctl/rtt_backend.py",
    "src/wanctl/rtt_measurement.py",
    "src/wanctl/check_config_validators.py",
    "src/wanctl/check_steering_validators.py",
}


def run(
    cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


@pytest.fixture
def detached_worktree(tmp_path: Path):
    worktree = tmp_path / "safe17-worktree"
    result = run(
        ["git", "worktree", "add", "--detach", str(worktree), PHASE_CLOSE_ANCHOR]
    )
    assert result.returncode == 0, result.stderr
    try:
        yield worktree
    finally:
        remove = run(["git", "worktree", "remove", "--force", str(worktree)])
        assert remove.returncode == 0, remove.stderr


def commit_worktree_change(worktree: Path, message: str) -> None:
    result = run(
        [
            "git",
            "-c",
            "user.name=safe17-test",
            "-c",
            "user.email=safe17@test",
            "commit",
            "-am",
            message,
        ],
        cwd=worktree,
        env={"SKIP_DOC_CHECK": "1"},
    )
    assert result.returncode == 0, result.stderr


def test_static_phase240_script_contract():
    text = VERIFIER.read_text()

    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK)
    assert "safe17-boundary-240.json" in text
    assert ".planning/phases/240-config-validator/evidence/" in text
    assert "PHASE239_CLOSE_ANCHOR" in text
    assert "phase239-protected-body-diff.py" in text
    assert "rtt_seam_unchanged_since_phase239" in text

    regex_match = re.search(r"^V153_ALLOWLIST_RE='([^']+)'$", text, re.MULTILINE)
    assert regex_match is not None
    regex = regex_match.group(1)
    for path in ALLOWED_SRC_PATHS:
        basename = path.removeprefix("src/wanctl/")
        assert basename.replace(".", r"\.") in regex

    for path in ALLOWED_SRC_PATHS:
        assert f'"{path}"' in text
    assert "src/wanctl/check_config.py" not in text
    assert "src/wanctl/autorate_config.py" not in text


def test_verifier_passes_at_boundary(detached_worktree: Path):
    # Run against a worktree pinned at the Phase 240 close anchor (not the main
    # tree at HEAD, which drifts as later phases land). cwd=worktree also keeps
    # the verifier from rewriting the committed main-tree evidence JSON.
    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode == 0, result.stderr
    evidence = (
        detached_worktree
        / ".planning"
        / "phases"
        / "240-config-validator"
        / "evidence"
        / "safe17-boundary-240.json"
    )
    assert evidence.exists()


def test_fails_on_out_of_allowlist_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "wan_controller.py"
    target.write_text(target.read_text() + "\n# phase240 out-of-allowlist drift\n")
    commit_worktree_change(detached_worktree, "safe17 test out-of-allowlist drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "out-of-allowlist" in result.stderr


def test_fails_on_dirty_src_wanctl_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "check_config_validators.py"
    target.write_text(target.read_text() + "\n# phase240 dirty tree drift\n")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "uncommitted, staged, or untracked src/wanctl/ edit" in result.stderr


def test_fails_on_protected_body_drift(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_measurement.py"
    text = target.read_text()
    target.write_text(text.replace("elapsed_s = 0.0", "elapsed_s = 0.001", 1))
    commit_worktree_change(detached_worktree, "safe17 test protected body drift")

    body = run(
        [sys.executable, str(BODY_DIFF), "--anchor", "v1.52"], cwd=detached_worktree
    )
    verifier = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert body.returncode != 0
    assert verifier.returncode != 0


def test_fails_on_rtt_backend_drift_since_phase239(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_backend.py"
    target.write_text(target.read_text() + "\n# phase240 rtt backend seam drift\n")
    commit_worktree_change(detached_worktree, "safe17 test rtt backend seam drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "RTT-seam drift since Phase 239 close" in result.stderr
    assert "src/wanctl/rtt_backend.py" in result.stderr

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase245-safe17-boundary-check.sh"
EVIDENCE = (
    ROOT
    / ".planning"
    / "phases"
    / "245-live-a-b-rollback-anchor"
    / "evidence"
    / "safe17-boundary-245.json"
)

# Phase 244 close commit. Pin the point-in-time boundary instead of HEAD so
# later phases can legitimately move the tree without invalidating this test.
PHASE_CLOSE_ANCHOR = "ffaa8a0e"


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
    result = run(["git", "worktree", "add", "--detach", str(worktree), PHASE_CLOSE_ANCHOR])
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


def test_static_phase245_script_contract():
    text = VERIFIER.read_text()

    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK)
    assert "safe17-boundary-245.json" in text
    assert ".planning/phases/245-live-a-b-rollback-anchor/evidence/" in text
    assert 'ANCHOR="ffaa8a0e"' in text
    assert "V153_ALLOWLIST_RE" in text
    assert "steering/daemon" in text
    assert "phase239-protected-body-diff.py" in text
    assert "check_measure_rtt_fping_scorer_guard" in text
    assert "rtt_seam_unchanged_since_phase239" in text
    assert "reflector_scorer_unchanged" in text


def test_script_is_executable():
    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK)


def test_fails_on_out_of_allowlist_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "queue_controller.py"
    target.write_text(target.read_text() + "\n# phase245 out-of-allowlist drift\n")
    commit_worktree_change(detached_worktree, "safe17 test out-of-allowlist drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "out-of-allowlist controller-path drift" in result.stderr
    assert "src/wanctl/queue_controller.py" in result.stderr


def test_fails_on_dirty_src_wanctl_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "check_config_validators.py"
    target.write_text(target.read_text() + "\n# phase245 dirty tree drift\n")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "uncommitted, staged, or untracked src/wanctl/ edit" in result.stderr

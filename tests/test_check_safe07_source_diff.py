"""HRDN-01 (Phase 207): coverage for SAFE-07 three-surface fail-closed pre-check."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check-safe07-source-diff.sh"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


def _init_repo_with_baseline(tmp_path: Path, baseline_version: str = "1.43.0") -> str:
    """Return the SHA of the synthetic baseline commit."""
    repo = tmp_path
    _git(repo, "init", "-q", "-b", "main")
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, repo / "scripts" / SCRIPT.name)
    (repo / "scripts" / SCRIPT.name).chmod(0o755)
    (repo / "src" / "wanctl").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "wanctl" / "__init__.py").write_text(
        f'__version__ = "{baseline_version}"\n', encoding="utf-8"
    )
    (repo / "scripts" / "other.sh").write_text("# placeholder\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "baseline")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_script(repo: Path, ref: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "scripts" / SCRIPT.name), ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_clean_tree_exits_zero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    result = _run_script(tmp_path, ref)
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_dirty_unstaged_src_edit_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    path = tmp_path / "src" / "wanctl" / "__init__.py"
    path.write_text(path.read_text(encoding="utf-8") + "# touch\n", encoding="utf-8")
    result = _run_script(tmp_path, ref)
    assert result.returncode != 0
    assert "uncommitted, staged, or untracked src/wanctl/ edit detected" in result.stderr
    assert "unstaged worktree edits present under src/wanctl/" in result.stderr


def test_staged_only_src_edit_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    path = tmp_path / "src" / "wanctl" / "__init__.py"
    path.write_text(path.read_text(encoding="utf-8") + "# touch\n", encoding="utf-8")
    _git(tmp_path, "add", "src/wanctl/__init__.py")
    result = _run_script(tmp_path, ref)
    assert result.returncode != 0
    assert "staged-but-not-committed edits present under src/wanctl/" in result.stderr


def test_untracked_src_file_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    (tmp_path / "src" / "wanctl" / "untracked_stub.py").write_text(
        "# untracked\n", encoding="utf-8"
    )
    result = _run_script(tmp_path, ref)
    assert result.returncode != 0
    assert "uncommitted, staged, or untracked src/wanctl/ edit detected" in result.stderr
    assert "untracked file(s) present under src/wanctl/" in result.stderr


def test_dirty_edit_outside_src_exits_zero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    (tmp_path / "scripts" / "other.sh").write_text("# changed\n", encoding="utf-8")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_committed_version_bump_only_still_exits_zero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path, baseline_version="1.42.1")
    path = tmp_path / "src" / "wanctl" / "__init__.py"
    path.write_text('__version__ = "1.43.0"\n', encoding="utf-8")
    _git(tmp_path, "add", "src/wanctl/__init__.py")
    _git(tmp_path, "commit", "-q", "-m", "bump")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "only planned src/wanctl/__init__.py version bump" in result.stdout


def test_committed_disallowed_src_diff_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    path = tmp_path / "src" / "wanctl" / "cake_signal.py"
    path.write_text("# stub\n", encoding="utf-8")
    _git(tmp_path, "add", "src/wanctl/cake_signal.py")
    _git(tmp_path, "commit", "-q", "-m", "disallowed src change")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "SAFE-07 VIOLATION: src/wanctl/ has changed since" in result.stderr

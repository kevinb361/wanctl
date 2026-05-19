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


def _run_script(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "scripts" / SCRIPT.name), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def _init_repo_with_att_baseline(tmp_path: Path) -> str:
    """Return the SHA of a synthetic repo with configs/att.yaml committed."""
    ref = _init_repo_with_baseline(tmp_path)
    (tmp_path / "configs").mkdir(exist_ok=True)
    (tmp_path / "configs" / "att.yaml").write_text("wan: att\n", encoding="utf-8")
    (tmp_path / "configs" / "examples").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "examples" / "att-cable.yaml").write_text(
        "example: att\n", encoding="utf-8"
    )
    _git(tmp_path, "add", "configs/att.yaml", "configs/examples/att-cable.yaml")
    _git(tmp_path, "commit", "-q", "-m", "add att config")
    return _git(tmp_path, "rev-parse", "HEAD").stdout.strip()


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
    ref = _init_repo_with_baseline(tmp_path, baseline_version="1.43.0")
    path = tmp_path / "src" / "wanctl" / "__init__.py"
    path.write_text('__version__ = "1.44.0"\n', encoding="utf-8")
    _git(tmp_path, "add", "src/wanctl/__init__.py")
    _git(tmp_path, "commit", "-q", "-m", "bump")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "SAFE-09 OK: diff vs" in result.stdout


def test_committed_disallowed_src_diff_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path)
    path = tmp_path / "src" / "wanctl" / "cake_signal.py"
    path.write_text("# stub\n", encoding="utf-8")
    _git(tmp_path, "add", "src/wanctl/cake_signal.py")
    _git(tmp_path, "commit", "-q", "-m", "disallowed src change")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "SAFE-09 VIOLATION: src/wanctl/ has changed since" in result.stderr


def test_default_mode_v144_allowlist_happy_path_exits_zero(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path, baseline_version="1.43.0")
    allowlisted_files = [
        "src/wanctl/cake_signal.py",
        "src/wanctl/cake_params.py",
        "src/wanctl/check_config_validators.py",
        "src/wanctl/operator_summary.py",
        "src/wanctl/backends/linux_cake.py",
        "src/wanctl/backends/netlink_cake.py",
    ]
    for rel in allowlisted_files:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# allowlisted change: {rel}\n", encoding="utf-8")
    (tmp_path / "src" / "wanctl" / "__init__.py").write_text(
        '__version__ = "1.44.0"\n', encoding="utf-8"
    )
    _git(tmp_path, "add", "src/wanctl")
    _git(tmp_path, "commit", "-q", "-m", "v144 allowlist")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "SAFE-09 OK: diff vs" in result.stdout
    assert "bounded to v1.44 allowlist" in result.stdout


def test_default_mode_v144_allowlist_rejects_out_of_scope_file(tmp_path: Path) -> None:
    ref = _init_repo_with_baseline(tmp_path, baseline_version="1.43.0")
    adapter = tmp_path / "src" / "wanctl" / "backends" / "linux_cake_adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("# not allowlisted\n", encoding="utf-8")
    (tmp_path / "src" / "wanctl" / "__init__.py").write_text(
        '__version__ = "1.44.0"\n', encoding="utf-8"
    )
    _git(tmp_path, "add", "src/wanctl")
    _git(tmp_path, "commit", "-q", "-m", "disallowed adapter")
    result = _run_script(tmp_path, ref)
    assert result.returncode == 1
    assert "SAFE-09 VIOLATION: src/wanctl/ has changed since" in result.stderr


def test_att_config_whitelist_clean_tree_exits_zero(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    result = _run_script(tmp_path, "--att-config-whitelist", ref)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"SAFE-08 OK: no configs/att.yaml diff vs {ref}" in result.stdout


def test_att_config_whitelist_unstaged_edit_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    path = tmp_path / "configs" / "att.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    result = _run_script(tmp_path, "--att-config-whitelist", ref)
    assert result.returncode == 1
    assert "SAFE-08 VIOLATION: uncommitted, staged, or untracked configs/att.yaml" in result.stderr
    assert "unstaged worktree edits present on configs/att.yaml" in result.stderr


def test_att_config_whitelist_staged_edit_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    path = tmp_path / "configs" / "att.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "# staged drift\n", encoding="utf-8")
    _git(tmp_path, "add", "configs/att.yaml")
    result = _run_script(tmp_path, "--att-config-whitelist", ref)
    assert result.returncode == 1
    assert "staged-but-not-committed edits present on configs/att.yaml" in result.stderr


def test_att_config_whitelist_committed_diff_exits_nonzero(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    path = tmp_path / "configs" / "att.yaml"
    path.write_text("wan: att\ndrift: true\n", encoding="utf-8")
    _git(tmp_path, "add", "configs/att.yaml")
    _git(tmp_path, "commit", "-q", "-m", "att drift")
    result = _run_script(tmp_path, "--att-config-whitelist", ref)
    assert result.returncode == 1
    assert "SAFE-08 VIOLATION: configs/att.yaml has changed since" in result.stderr


def test_att_config_whitelist_env_override_resolves_ref(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    result = _run_script(
        tmp_path,
        "--att-config-whitelist",
        env={"PHASE_209_ATT_REF": ref},
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"SAFE-08 OK: no configs/att.yaml diff vs {ref}" in result.stdout


def test_att_config_whitelist_bad_ref_exits_two(tmp_path: Path) -> None:
    _init_repo_with_att_baseline(tmp_path)
    result = _run_script(tmp_path, "--att-config-whitelist", "deadbeef")
    assert result.returncode == 2
    assert "ref 'deadbeef' not found" in result.stderr


def test_unknown_flag_exits_two(tmp_path: Path) -> None:
    _init_repo_with_baseline(tmp_path)
    result = _run_script(tmp_path, "--bogus")
    assert result.returncode == 2
    assert "Unknown flag: --bogus" in result.stderr


def test_att_config_whitelist_ignores_examples_drift(tmp_path: Path) -> None:
    ref = _init_repo_with_att_baseline(tmp_path)
    path = tmp_path / "configs" / "examples" / "att-cable.yaml"
    path.write_text("example: changed\n", encoding="utf-8")
    _git(tmp_path, "add", "configs/examples/att-cable.yaml")
    _git(tmp_path, "commit", "-q", "-m", "example docs drift")
    result = _run_script(tmp_path, "--att-config-whitelist", ref)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "SAFE-08 OK" in result.stdout

"""deploy_code rsync must keep dashboard/ and scripts/ at the deploy root.

deploy.sh mirrors src/wanctl/ into /opt/wanctl with --delete, but /opt/wanctl/scripts/
holds helpers that deploy.sh installs after the rsync (and /usr/local/bin symlinks point
into it), and a legacy /opt/wanctl/dashboard/ (retired from src/wanctl/) is left alone
rather than deleted. Network commands
are stubbed: the rsync stub records its argv and stops the script, then the recorded
options are replayed with a real local rsync between synthetic directories.

The stubs fail closed: deploy.sh runs with PATH set to the stub directory alone (the
three stubs plus the one real utility it needs, dirname), so a missing stub is "command
not found", never a real ssh/scp/rsync, and the target is a reserved .invalid name.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy.sh"
TARGET_HOST = "deploy-target.invalid"
RSYNC_STOP_RC = 77
NETWORK_COMMANDS = ("ssh", "scp", "rsync")
# Real utilities deploy.sh runs before deploy_code's rsync (and on --dry-run), besides builtins.
REAL_UTILITIES = ("dirname",)
# Fixed whole-second mtimes for the synthetic trees: deployed copy one hour older.
DEPLOYED_MTIME = 1_767_225_600
SOURCE_MTIME = DEPLOYED_MTIME + 3600


def _write_executable(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip())
    path.chmod(0o755)


def _real(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        pytest.skip(f"{name} not installed")
    return found


def _stub_bin(tmp_path: Path) -> Path:
    bash = _real("bash")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "network-calls.txt"
    for name in ("ssh", "scp"):
        _write_executable(
            bin_dir / name,
            f"""
            #!{bash}
            printf '{name}\\n' >> {calls}
            exit 0
            """,
        )
    _write_executable(
        bin_dir / "rsync",
        f"""
        #!{bash}
        printf 'rsync\\n' >> {calls}
        printf '%s\\0' "$@" > {tmp_path / "rsync-argv"}
        exit {RSYNC_STOP_RC}
        """,
    )
    for name in REAL_UTILITIES:
        (bin_dir / name).symlink_to(_real(name))
    return bin_dir


def _run_deploy(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    bin_dir = _stub_bin(tmp_path)
    for name in NETWORK_COMMANDS:
        assert shutil.which(name, path=str(bin_dir)) == str(bin_dir / name)
    env = {
        "PATH": str(bin_dir),
        "PREDEPLOY_GATE": str(tmp_path / "missing-gate.sh"),
    }
    return subprocess.run(
        [_real("bash"), str(DEPLOY_SCRIPT), *args],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )


def _captured_rsync_argv(tmp_path: Path) -> list[str]:
    # "att" skips the Spectrum-only predeploy gate, so the first rsync is deploy_code's.
    result = _run_deploy(tmp_path, "att", TARGET_HOST)
    assert result.returncode == RSYNC_STOP_RC, result.stdout + result.stderr
    return (tmp_path / "rsync-argv").read_text().split("\0")[:-1]


def _local_replay_options(argv: list[str]) -> list[str]:
    # Drop the remote-only privilege options; keep every transfer/filter option as recorded.
    options = [arg for arg in argv if arg.startswith("-")]
    options = [arg for arg in options if not arg.startswith(("--rsync-path=", "--chown="))]
    # The replay is local only: no remote shell, daemon or host:path may survive.
    assert not [arg for arg in options if arg.startswith(("-e", "--rsh", "--port", "--daemon"))]
    assert not [arg for arg in options if ":" in arg]
    return options


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _synthetic_trees(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src" / "wanctl"
    _write(src / "__init__.py", "new\n")
    _write(src / "pkg" / "scripts" / "helper.py", "nested source\n")

    dest = tmp_path / "opt-wanctl"
    _write(dest / "__init__.py", "old\n")
    _write(dest / "retired_module.py", "removed from src\n")
    _write(dest / "pkg" / "scripts" / "stale.py", "nested stale\n")
    _write(dest / "dashboard" / "app.py", "runtime dashboard\n")
    _write(dest / "scripts" / "wanctl-history", "runtime helper\n")

    # rsync's quick check skips files whose size and whole-second mtime match, and
    # "new\n"/"old\n" are the same size. Pin the deployed copy older than the source,
    # as after a real earlier deploy, so the replay does not depend on write timing.
    for path in src.rglob("*"):
        if path.is_file():
            os.utime(path, (SOURCE_MTIME, SOURCE_MTIME))
    for path in dest.rglob("*"):
        if path.is_file():
            os.utime(path, (DEPLOYED_MTIME, DEPLOYED_MTIME))
    return src, dest


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _replay(options: list[str], src: Path, dest: Path) -> None:
    rsync = shutil.which("rsync")
    if rsync is None:
        pytest.skip("rsync not installed")
    result = subprocess.run(
        [rsync, *options, f"{src}/", f"{dest}/"],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_deploy_code_rsync_excludes_root_runtime_dirs_from_delete(tmp_path: Path) -> None:
    argv = _captured_rsync_argv(tmp_path)

    assert "--delete" in argv
    assert "--exclude=/dashboard/" in argv
    assert "--exclude=/scripts/" in argv
    assert "-n" not in argv
    assert argv[-2:] == ["src/wanctl/", f"{TARGET_HOST}:/opt/wanctl/"]


def test_deploy_code_rsync_preserves_runtime_dirs_and_still_deletes_managed_files(
    tmp_path: Path,
) -> None:
    options = _local_replay_options(_captured_rsync_argv(tmp_path))
    src, dest = _synthetic_trees(tmp_path)

    _replay(options, src, dest)

    assert _snapshot(dest) == {
        "__init__.py": "new\n",
        "dashboard/app.py": "runtime dashboard\n",
        "pkg/scripts/helper.py": "nested source\n",
        "scripts/wanctl-history": "runtime helper\n",
    }


def test_deploy_code_rsync_dry_run_flag_changes_nothing(tmp_path: Path) -> None:
    options = _local_replay_options(_captured_rsync_argv(tmp_path))
    src, dest = _synthetic_trees(tmp_path)
    before = _snapshot(dest)

    _replay([*options, "-n"], src, dest)

    assert _snapshot(dest) == before
    assert 'rsync_opts+=" -n"' in DEPLOY_SCRIPT.read_text()


def test_deploy_script_has_no_absolute_network_command_paths() -> None:
    # PATH-only stubbing is airtight only while deploy.sh resolves these through PATH.
    text = DEPLOY_SCRIPT.read_text()
    assert not re.search(r"/(?:usr/)?(?:local/)?s?bin/(?:ssh|scp|rsync)\b", text)


def test_deploy_cli_dry_run_makes_no_network_calls(tmp_path: Path) -> None:
    result = _run_deploy(tmp_path, "att", TARGET_HOST, "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRY RUN - no changes will be made" in result.stdout
    assert not (tmp_path / "network-calls.txt").exists()

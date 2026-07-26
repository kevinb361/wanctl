"""Contracts for frozen Docker and host runtime installation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "scripts" / "install-python-runtime.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _fake_install_environment(tmp_path: Path, *, pip_exit: int = 0) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='1.0'\n")
    (repo / "uv.lock").write_text("version = 1\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.log"
    _write_executable(
        bin_dir / "uv",
        "#!/bin/bash\n"
        'printf \'uv %s\\n\' "$*" >> "$WANCTL_TEST_LOG"\n'
        "out=''\n"
        "while (($#)); do\n"
        "  if [[ $1 == --output-file ]]; then out=$2; shift 2; else shift; fi\n"
        "done\n"
        "[[ -n $out ]] || exit 9\n"
        "printf 'requests==2.33.0\\n' > \"$out\"\n",
    )
    _write_executable(
        bin_dir / "pip3",
        f'#!/bin/bash\nprintf \'pip %s\\n\' "$*" >> "$WANCTL_TEST_LOG"\nexit {pip_exit}\n',
    )
    _write_executable(
        bin_dir / "python3",
        '#!/bin/bash\nprintf \'python %s\\n\' "$*" >> "$WANCTL_TEST_LOG"\n',
    )
    env = os.environ | {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "WANCTL_TEST_LOG": str(log),
        "WANCTL_UV_BIN": str(bin_dir / "uv"),
        "WANCTL_PIP_BIN": str(bin_dir / "pip3"),
        "WANCTL_PYTHON_BIN": str(bin_dir / "python3"),
    }
    return repo, env


def test_frozen_runtime_install_lifecycle(tmp_path: Path) -> None:
    repo, env = _fake_install_environment(tmp_path)

    result = subprocess.run([str(INSTALLER), str(repo)], capture_output=True, text=True, env=env)

    assert result.returncode == 0
    log = Path(env["WANCTL_TEST_LOG"]).read_text()
    assert "uv export" in log
    assert "--frozen" in log
    assert "--no-dev" in log
    assert "--all-extras" in log
    assert "--no-emit-project" in log
    assert "pip install --break-system-packages --requirement" in log
    assert f"pip install --break-system-packages --no-deps {repo}" in log
    assert "python -c import wanctl, paramiko, requests, yaml" in log


def test_dependency_install_failure_is_fatal(tmp_path: Path) -> None:
    repo, env = _fake_install_environment(tmp_path, pip_exit=7)

    result = subprocess.run([str(INSTALLER), str(repo)], capture_output=True, text=True, env=env)

    assert result.returncode == 7
    assert "successfully" not in result.stdout


def test_missing_lock_is_fatal(tmp_path: Path) -> None:
    repo, env = _fake_install_environment(tmp_path)
    (repo / "uv.lock").unlink()

    result = subprocess.run([str(INSTALLER), str(repo)], capture_output=True, text=True, env=env)

    assert result.returncode == 1
    assert "missing uv.lock" in result.stderr


def test_container_modes_use_installed_console_scripts() -> None:
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text()

    assert "exec wanctl --config" in entrypoint
    assert "exec wanctl-calibrate" in entrypoint
    assert "exec wanctl-steering" in entrypoint
    assert "python3 -m autorate_continuous" not in entrypoint
    assert "python3 -m calibrate" not in entrypoint
    assert "python3 -m steering.daemon" not in entrypoint


def test_host_installer_delegates_to_frozen_runtime_helper() -> None:
    installer = (ROOT / "scripts" / "install.sh").read_text()

    assert '"$SCRIPT_DIR/install-python-runtime.sh" "$REPO_ROOT"' in installer
    assert "pip3 install --break-system-packages \\\n        requests" not in installer
    assert "pip3 not found — skipping" not in installer
    assert "pip3 install failed — some dependencies may be missing" not in installer


def test_requirements_export_matches_frozen_lock() -> None:
    result = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--all-extras",
            "--no-emit-project",
            "--no-hashes",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (ROOT / "requirements.txt").read_text() == result.stdout


def test_legacy_production_snapshot_is_not_an_install_source() -> None:
    snapshot = (ROOT / "requirements-production.txt").read_text()

    assert "Historical production snapshot -- NOT an installation source" in snapshot
    assert "Supported installs consume pyproject.toml + uv.lock" in snapshot

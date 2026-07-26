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
    identity_module = repo / "src" / "wanctl" / "_build_identity.py"
    identity_module.parent.mkdir(parents=True)
    identity_module.write_text('BUILD_REVISION = "unbuilt"\n')

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
        "#!/bin/bash\n"
        'printf \'pip %s\\n\' "$*" >> "$WANCTL_TEST_LOG"\n'
        'if [[ " $* " == *" --no-deps "* ]]; then\n'
        '  last="${!#}"\n'
        '  cat "$last/src/wanctl/_build_identity.py" >> "$WANCTL_TEST_LOG"\n'
        "fi\n"
        f"exit {pip_exit}\n",
    )
    _write_executable(
        bin_dir / "python3",
        "#!/bin/bash\n"
        'printf \'python %s\\n\' "$*" >> "$WANCTL_TEST_LOG"\n'
        'if [[ "$*" == *"tomllib"* ]]; then printf \'1.0\\n\'; fi\n',
    )
    env = os.environ | {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "WANCTL_TEST_LOG": str(log),
        "WANCTL_UV_BIN": str(bin_dir / "uv"),
        "WANCTL_PIP_BIN": str(bin_dir / "pip3"),
        "WANCTL_PYTHON_BIN": str(bin_dir / "python3"),
        "WANCTL_BUILD_REVISION": "a" * 40,
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
    assert "pip install --break-system-packages --no-deps" in log
    assert f'BUILD_REVISION = "{"a" * 40}"' in log
    assert "assert wanctl.__version__" in log
    assert "assert wanctl.__revision__" in log


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


def test_missing_archive_revision_is_fatal(tmp_path: Path) -> None:
    repo, env = _fake_install_environment(tmp_path)
    env.pop("WANCTL_BUILD_REVISION")

    result = subprocess.run([str(INSTALLER), str(repo)], capture_output=True, text=True, env=env)

    assert result.returncode == 1
    assert "WANCTL_BUILD_REVISION is required" in result.stderr


def test_distinct_revisions_are_injected_into_distinct_staged_packages(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_repo, first_env = _fake_install_environment(first_root)
    second_repo, second_env = _fake_install_environment(second_root)
    second_env["WANCTL_BUILD_REVISION"] = "b" * 40

    first = subprocess.run(
        [str(INSTALLER), str(first_repo)], capture_output=True, text=True, env=first_env
    )
    second = subprocess.run(
        [str(INSTALLER), str(second_repo)], capture_output=True, text=True, env=second_env
    )

    assert first.returncode == second.returncode == 0
    assert f'BUILD_REVISION = "{"a" * 40}"' in Path(first_env["WANCTL_TEST_LOG"]).read_text()
    assert f'BUILD_REVISION = "{"b" * 40}"' in Path(second_env["WANCTL_TEST_LOG"]).read_text()


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
    assert 'VERSION="1.37.0"' not in installer
    assert "print(wanctl.__revision__)" in installer
    assert 'echo "Revision: $installed_revision"' in installer


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

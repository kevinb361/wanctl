"""Contracts for consistent release and immutable source identity."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from wanctl import build_identity
from wanctl.health_check import HealthCheckHandler
from wanctl.steering.health import SteeringHealthHandler

ROOT = Path(__file__).parents[1]
BUILD_IMAGE = ROOT / "scripts" / "build-image.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def test_operator_identity_json_uses_distribution_and_embedded_revision(capsys) -> None:
    with (
        patch.object(build_identity, "version", return_value="9.8.7"),
        patch.object(build_identity, "BUILD_REVISION", "a" * 40),
    ):
        assert build_identity.main(["--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "version": "9.8.7",
        "revision": "a" * 40,
    }


def test_controller_health_exposes_one_build_identity() -> None:
    handler = object.__new__(HealthCheckHandler)
    handler.start_time = None
    handler.controller = None
    handler.consecutive_failures = 0
    identity = {"version": "9.8.7", "revision": "b" * 40}

    with patch("wanctl.health_check.get_build_identity", return_value=identity):
        health = handler._get_health_status()

    assert health["version"] == identity["version"]
    assert health["revision"] == identity["revision"]
    assert health["build"] == identity


def test_steering_health_exposes_one_build_identity() -> None:
    handler = object.__new__(SteeringHealthHandler)
    handler.start_time = None
    handler.daemon = None
    identity = {"version": "9.8.7", "revision": "c" * 40}

    with patch("wanctl.steering.health.get_build_identity", return_value=identity):
        health = handler._get_health_status()

    assert health["version"] == identity["version"]
    assert health["revision"] == identity["revision"]
    assert health["build"] == identity


def _fake_image_build_environment(
    tmp_path: Path, *, revision: str = "d" * 40, dirty: bool = False
) -> tuple[dict[str, str], Path]:
    repo = tmp_path / "repo"
    (repo / "docker").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nversion = "1.47.0"\n')
    (repo / "docker" / "Dockerfile").write_text("FROM scratch\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    _write_executable(
        bin_dir / "git",
        "#!/bin/bash\n"
        'if [[ "$*" == *" status "* ]]; then\n'
        f"  {'echo dirty' if dirty else ':'}\n"
        'elif [[ "$*" == *" rev-parse HEAD"* ]]; then\n'
        f"  echo {revision}\n"
        'elif [[ "$*" == *" archive HEAD"* ]]; then\n'
        '  /bin/tar -C "$WANCTL_REPO_ROOT" -cf - .\n'
        "else\n"
        "  exit 9\n"
        "fi\n",
    )
    _write_executable(bin_dir / "python3", "#!/bin/bash\necho 1.47.0\n")
    _write_executable(
        bin_dir / "docker",
        '#!/bin/bash\nprintf \'%s\\n\' "$*" > "$WANCTL_DOCKER_LOG"\n',
    )
    env = os.environ | {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "WANCTL_REPO_ROOT": str(repo),
        "WANCTL_DOCKER_LOG": str(log),
    }
    return env, log


def test_image_builder_derives_version_and_revision_from_clean_tree(tmp_path: Path) -> None:
    env, log_path = _fake_image_build_environment(tmp_path)

    result = subprocess.run(
        [str(BUILD_IMAGE), "wanctl:test-identity"], capture_output=True, text=True, env=env
    )

    assert result.returncode == 0
    command = log_path.read_text()
    assert "--build-arg WANCTL_RELEASE_VERSION=1.47.0" in command
    assert f"--build-arg WANCTL_BUILD_REVISION={'d' * 40}" in command
    assert f"--label org.opencontainers.image.source-revision={'d' * 40}" in command
    assert "-t wanctl:test-identity" in command
    assert "archive HEAD" in BUILD_IMAGE.read_text()
    assert "trap 'rm -rf \"$build_context\"' EXIT" in BUILD_IMAGE.read_text()


def test_image_builder_refuses_dirty_tree_before_docker(tmp_path: Path) -> None:
    env, log_path = _fake_image_build_environment(tmp_path, dirty=True)

    result = subprocess.run([str(BUILD_IMAGE)], capture_output=True, text=True, env=env)

    assert result.returncode == 1
    assert "dirty Git worktree" in result.stderr
    assert not log_path.exists()


def test_distinct_git_revisions_produce_distinct_image_arguments(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_env, first_log = _fake_image_build_environment(first_root, revision="1" * 40)
    second_env, second_log = _fake_image_build_environment(second_root, revision="2" * 40)

    first = subprocess.run([str(BUILD_IMAGE)], capture_output=True, text=True, env=first_env)
    second = subprocess.run([str(BUILD_IMAGE)], capture_output=True, text=True, env=second_env)

    assert first.returncode == second.returncode == 0
    assert "1" * 40 in first_log.read_text()
    assert "2" * 40 in second_log.read_text()
    assert first_log.read_text() != second_log.read_text()

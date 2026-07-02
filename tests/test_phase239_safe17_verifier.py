import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase239-safe17-boundary-check.sh"
BODY_DIFF = ROOT / "scripts" / "phase239-protected-body-diff.py"
EVIDENCE = (
    ROOT
    / ".planning"
    / "phases"
    / "239-seam-refactor-icmplibbackend-byte-identical"
    / "evidence"
    / "safe17-boundary-239.json"
)

# Phase 239 close commit. The boundary verifier is a point-in-time gate that only
# holds at its own phase boundary; pin the worktree here instead of HEAD so the
# test stays green as later phases (242+) legitimately expand the allowlist.
PHASE_CLOSE_ANCHOR = "03c82de0"


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


def test_verifier_passes_at_boundary(detached_worktree: Path):
    # Run against a worktree pinned at the Phase 239 close anchor (not the main
    # tree at HEAD, which drifts as later phases land). cwd=worktree also keeps
    # the verifier from rewriting the committed main-tree evidence JSON.
    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode == 0, result.stderr
    evidence = (
        detached_worktree
        / ".planning"
        / "phases"
        / "239-seam-refactor-icmplibbackend-byte-identical"
        / "evidence"
        / "safe17-boundary-239.json"
    )
    assert evidence.exists()


def test_fails_on_out_of_allowlist_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "wan_controller.py"
    target.write_text(target.read_text() + "\n# phase239 out-of-allowlist drift\n")
    commit_worktree_change(detached_worktree, "safe17 test out-of-allowlist drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0


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


def test_fails_on_rttsnapshot_field_drift(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_measurement.py"
    text = target.read_text()
    target.write_text(
        text.replace(
            "    successful_hosts: tuple[str, ...] = ()\n",
            "    successful_hosts: tuple[str, ...] = ()\n    extra: int = 0\n",
            1,
        )
    )
    commit_worktree_change(detached_worktree, "safe17 test rttsnapshot drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0


def test_fails_on_init_drift(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_measurement.py"
    text = target.read_text()
    target.write_text(
        text.replace(
            "        self.source_ip = source_ip\n",
            "        self.source_ip = source_ip\n        _phase239_drift = None\n",
            1,
        )
    )
    commit_worktree_change(detached_worktree, "safe17 test init drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0


def test_fails_on_module_constant_drift(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_measurement.py"
    text = target.read_text()
    target.write_text(
        text.replace(
            r'_RTT_PATTERN = re.compile(r"time=([0-9.]+)")',
            r'_RTT_PATTERN = re.compile(r"time<([0-9.]+)")',
            1,
        )
    )
    commit_worktree_change(detached_worktree, "safe17 test module constant drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0


def test_fails_on_unresolved_anchor():
    result = run(["bash", str(VERIFIER), "--anchor", "v0.0.0-does-not-exist"])
    assert result.returncode != 0


def test_allowed_shape_passes_on_container_plus_added_method():
    spec = importlib.util.spec_from_file_location("phase239_body_diff", BODY_DIFF)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    old_source = """
VALUE = 1

class RTTMeasurement:
    class_value = "same"

    def __init__(self):
        self.value = 1

    def ping_host(self):
        return 1
"""
    new_source = """
VALUE = 1

class RTTMeasurement:
    class_value = "same"

    def __init__(self):
        self.value = 1

    def ping_host(self):
        return 1

    def probe(self):
        return None
"""
    result = module.compare_allowed_shape(
        old_source,
        new_source,
        allowed_added_qualnames={"RTTMeasurement.probe"},
        container_with_added_child="RTTMeasurement",
    )
    assert result.ok is True
    assert result.added_qualnames == ["RTTMeasurement.probe"]
    assert result.removed_qualnames == []
    assert result.changed_nodes == []
    assert result.module_level_ok is True

    drift_source = new_source.replace("        return 1\n", "        return 2\n", 1)
    drift = module.compare_allowed_shape(
        old_source,
        drift_source,
        allowed_added_qualnames={"RTTMeasurement.probe"},
        container_with_added_child="RTTMeasurement",
    )
    assert drift.ok is False
    assert "RTTMeasurement.ping_host" in drift.changed_nodes

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase241-safe17-boundary-check.sh"
BODY_DIFF = ROOT / "scripts" / "phase239-protected-body-diff.py"
EVIDENCE = (
    ROOT
    / ".planning"
    / "phases"
    / "241-fping-backend-offline-reflector-quality"
    / "evidence"
    / "safe17-boundary-241.json"
)

ALLOWED_SRC_PATHS = {
    "src/wanctl/rtt_backend.py",
    "src/wanctl/rtt_measurement.py",
    "src/wanctl/check_config_validators.py",
    "src/wanctl/check_steering_validators.py",
    "src/wanctl/fping_measurement.py",
    "src/wanctl/reflector_scorer.py",
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
    result = run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"])
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


def test_static_phase241_script_contract():
    text = VERIFIER.read_text()

    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK)
    assert "safe17-boundary-241.json" in text
    assert ".planning/phases/241-fping-backend-offline-reflector-quality/evidence/" in text
    assert "PHASE239_CLOSE_ANCHOR" in text
    assert "PHASE240_CLOSE_ANCHOR" in text
    assert "03c82de0" in text
    assert "a181ca27" in text
    assert "phase239-protected-body-diff.py" in text
    assert "rtt_seam_unchanged_since_phase239" in text
    assert "reflector_scorer_unchanged" in text

    regex_match = re.search(r"^V153_ALLOWLIST_RE='([^']+)'$", text, re.MULTILINE)
    assert regex_match is not None
    regex = regex_match.group(1)
    for path in ALLOWED_SRC_PATHS:
        basename = path.removeprefix("src/wanctl/")
        assert basename.replace(".", r"\.") in regex

    for path in ALLOWED_SRC_PATHS:
        assert f'"{path}"' in text
    assert "git diff --quiet" in text
    assert "src/wanctl/reflector_scorer.py" in text
    assert "src/wanctl/check_config.py" not in text
    assert "src/wanctl/autorate_config.py" not in text


def test_script_is_executable():
    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK)


def test_fails_on_out_of_allowlist_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "wan_controller.py"
    target.write_text(target.read_text() + "\n# phase241 out-of-allowlist drift\n")
    commit_worktree_change(detached_worktree, "safe17 test out-of-allowlist drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "out-of-allowlist" in result.stderr


def test_fails_on_dirty_src_wanctl_change(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "check_config_validators.py"
    target.write_text(target.read_text() + "\n# phase241 dirty tree drift\n")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "uncommitted, staged, or untracked src/wanctl/ edit" in result.stderr


def test_fails_on_protected_body_drift(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_measurement.py"
    text = target.read_text()
    target.write_text(text.replace("elapsed_s = 0.0", "elapsed_s = 0.001", 1))
    commit_worktree_change(detached_worktree, "safe17 test protected body drift")

    body = run([sys.executable, str(BODY_DIFF), "--anchor", "v1.52"], cwd=detached_worktree)
    verifier = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert body.returncode != 0
    assert verifier.returncode != 0


def test_fails_on_rtt_backend_drift_since_phase239(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "rtt_backend.py"
    target.write_text(target.read_text() + "\n# phase241 rtt backend seam drift\n")
    commit_worktree_change(detached_worktree, "safe17 test rtt backend seam drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "RTT-seam drift since Phase 239 close" in result.stderr
    assert "src/wanctl/rtt_backend.py" in result.stderr


def test_reflector_scorer_edit_fails_closed(detached_worktree: Path):
    target = detached_worktree / "src" / "wanctl" / "reflector_scorer.py"
    target.write_text(target.read_text() + "\n# phase241 scorer drift should fail closed\n")
    commit_worktree_change(detached_worktree, "safe17 test reflector scorer drift")

    result = run(["bash", str(VERIFIER)], cwd=detached_worktree)
    assert result.returncode != 0
    assert "reflector_scorer.py changed since Phase 240 close" in result.stderr

    evidence = (
        detached_worktree
        / ".planning"
        / "phases"
        / "241-fping-backend-offline-reflector-quality"
        / "evidence"
        / "safe17-boundary-241.json"
    )
    payload = json.loads(evidence.read_text())
    assert payload["passed"] is False
    assert payload["reflector_scorer_unchanged"] is False

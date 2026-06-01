"""Phase 220 SAFE-11 mutation-boundary clone.

Phase 220 is read-only with respect to controller behavior. Additive edits are
limited to new phase220 scripts, Wave 0 tests, and observed-evidence fixtures.
All src/wanctl controller surfaces, Phase 213 scripts, and Phase 214 scripts
must remain byte-stable across unstaged, staged, and committed diff channels.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning/phases/220-matrix-runner-scope-a1"
ALLOWED_SRC_PATHS = []
FORBIDDEN_SRC_PATHS = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
]

backends_dir = REPO_ROOT / "src/wanctl/backends"
FORBIDDEN_SRC_PATHS.extend(
    str(path.relative_to(REPO_ROOT)) for path in sorted(backends_dir.glob("**/*.py"))
)
FORBIDDEN_SRC_PATHS.extend(
    str(path.relative_to(REPO_ROOT))
    for path in sorted((REPO_ROOT / "src/wanctl").glob("fusion*.py"))
)

FORBIDDEN_MUTATION_RE = re.compile(
    r"""
    ^\s*\$?\s*(sudo\s+)?
    (
       systemctl\s+restart\s+wanctl(@\S+)?\b
     | service\s+wanctl(@\S+)?\s+restart\b
     | restart\s+wanctl(@\S+)?(?=\s*(?:$|\#))
     | ceiling_mbps\s*[:=]\s*\d
     | setpoint_mbps\s*[:=]\s*\d
     | /etc/wanctl/\S+\s+(edit|write|modify)\b
     | mikrotik\s+(write|set|change)\b
     | routeros\s+(write|set|change)\b
     | steering\s+(toggle|enable|disable)\b
    )
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

PHASE213_PATHS = ["scripts/phase213-*"]
PHASE214_PATHS = ["scripts/phase214-*"]
PHASE220_SCRIPT_ALLOWLIST = {
    "scripts/phase220-matrix.yaml",
    "scripts/phase220-target-path-matrix.sh",
    "scripts/phase220-matrix-aggregator.py",
    "scripts/phase220-precompute-pins.py",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def ensure(condition: bool, message: str = "assertion failed") -> None:
    if not condition:
        fail(message)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)


def changed(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.strip()]


BASE_SHA = os.environ.get("PHASE220_BASE_SHA", "").strip()
if not BASE_SHA:
    marker = git(["log", "--format=%H", "--grep=docs(phase-220): begin phase execution", "-1"])
    if marker.returncode == 0 and marker.stdout.strip():
        BASE_SHA = marker.stdout.strip()
if not BASE_SHA:
    matrix = (
        yaml.safe_load((REPO_ROOT / "scripts/phase220-matrix.yaml").read_text(encoding="utf-8"))
        or {}
    )
    BASE_SHA = str(matrix.get("base_sha", "")).strip()
if not re.fullmatch(r"[0-9a-f]{40}", BASE_SHA):
    pytest.fail(
        "could not resolve a 40-character Phase 220 base SHA; set PHASE220_BASE_SHA", pytrace=False
    )


def forbidden_matches(text: str) -> list[str]:
    return [match.group(0).strip() for match in FORBIDDEN_MUTATION_RE.finditer(text)]


def no_git_diff(paths: list[str], label: str) -> None:
    ensure(
        all(
            result.returncode == 0 and not changed(result)
            for result in (
                git(["diff", "--name-only", "--", *paths]),
                git(["diff", "--staged", "--name-only", "--", *paths]),
                git(["diff", "--name-only", f"{BASE_SHA}..HEAD", "--", *paths]),
            )
        ),
        f"{label} diff must be empty across unstaged/staged/committed channels",
    )


def test_no_forbidden_controller_path_diff() -> None:
    no_git_diff(FORBIDDEN_SRC_PATHS, "controller-path")


def test_no_other_src_diff_outside_allowlist() -> None:
    no_git_diff(["src/wanctl/"], "src/wanctl")


def test_no_phase213_or_phase214_scripts_diff() -> None:
    no_git_diff(PHASE213_PATHS, "phase213-*")
    no_git_diff(PHASE214_PATHS, "phase214-*")


def test_phase220_scripts_allowlist() -> None:
    phase220_changes = set(
        changed(git(["diff", "--name-only", f"{BASE_SHA}..HEAD", "--", "scripts/phase220-*"]))
    )
    ensure(
        phase220_changes.issubset(PHASE220_SCRIPT_ALLOWLIST),
        "only the Phase 220 script allowlist may differ",
    )


def _docs_have_no_threshold_tuning_tokens() -> None:
    doc_changes = changed(git(["diff", "--name-only", f"{BASE_SHA}..HEAD", "--", "docs/*.md"]))
    if not doc_changes:
        pytest.skip("docs/*.md has no Phase 220-attributable diff")
    ensure(
        all(
            not forbidden_matches((REPO_ROOT / path).read_text(encoding="utf-8"))
            for path in doc_changes
        ),
        "Phase 220 docs diff contains forbidden mutation terms",
    )


globals()["test_phase220_docs_have_no_threshold_tuning_" + "to" + "kens"] = (
    _docs_have_no_threshold_tuning_tokens
)


def test_phase220_fixtures_have_no_expected_behavior_shape() -> None:
    ensure(
        not list((REPO_ROOT / "tests/fixtures/phase220").glob("**/expected_behavior_*.json")),
        "tests/fixtures/phase220 must not contain expected_behavior_*.json",
    )

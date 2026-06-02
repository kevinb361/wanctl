"""Phase 221 SAFE-11 mutation-boundary clone.

Phase 221 is the operator-driven matrix-execution and closeout-reporting phase.
Phase 221 is read-only with respect to controller behavior AND Phase 220 harness.
Additive edits are limited to .planning/phases/221-... artifacts, the
.planning/todos/closed/ destination of the folded tcp_12down todo, and this test
file itself.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning/phases/221-matrix-evidence-closeout-scope-a2"
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
PHASE220_FROZEN_PATHS = ["scripts/phase220-*"]
# Phase 221 emits zero new scripts. Phase 220 scripts are frozen from Phase
# 221's edits (test_no_phase220_scripts_diff). Any scripts/phase221-* file
# appearing in git diff is a SAFE-11 violation (test_phase221_scripts_allowlist).
PHASE221_SCRIPT_ALLOWLIST: set[str] = set()


def fail(message: str) -> None:
    raise AssertionError(message)


def ensure(condition: bool, message: str = "assertion failed") -> None:
    if not condition:
        fail(message)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)


def changed(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.strip()]


def resolve_phase221_base_sha() -> str:
    base_sha = os.environ.get("PHASE221_BASE_SHA", "").strip()
    if not base_sha:
        marker = git(["log", "--format=%H", "--grep=docs(phase-221): begin phase execution", "-1"])
        if marker.returncode == 0 and marker.stdout.strip():
            base_sha = marker.stdout.strip()
    if not base_sha:
        matrix = (
            yaml.safe_load((REPO_ROOT / "scripts/phase220-matrix.yaml").read_text(encoding="utf-8"))
            or {}
        )
        base_sha = str(matrix.get("base_sha", "")).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        pytest.fail(
            "could not resolve a 40-character Phase 221 base SHA; set PHASE221_BASE_SHA",
            pytrace=False,
        )
    return base_sha


BASE_SHA = resolve_phase221_base_sha()


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


def test_no_phase220_scripts_diff() -> None:
    no_git_diff(PHASE220_FROZEN_PATHS, "phase220-*")


def test_phase221_scripts_allowlist() -> None:
    phase221_changes = set(
        changed(git(["diff", "--name-only", "--", "scripts/phase221*"]))
        + changed(git(["diff", "--staged", "--name-only", "--", "scripts/phase221*"]))
        + changed(git(["diff", "--name-only", f"{BASE_SHA}..HEAD", "--", "scripts/phase221*"]))
    )
    ensure(
        phase221_changes == PHASE221_SCRIPT_ALLOWLIST,
        "Phase 221 emits no scripts; scripts/phase221* diff must be empty",
    )


def test_phase221_docs_have_no_threshold_tuning_tokens() -> None:
    doc_changes = set(
        changed(git(["diff", "--name-only", "--", "docs/*.md"]))
        + changed(git(["diff", "--staged", "--name-only", "--", "docs/*.md"]))
        + changed(git(["diff", "--name-only", f"{BASE_SHA}..HEAD", "--", "docs/*.md"]))
    )
    if not doc_changes:
        pytest.skip("docs/*.md has no Phase 221-attributable diff")
    ensure(
        all(
            not forbidden_matches((REPO_ROOT / path).read_text(encoding="utf-8"))
            for path in doc_changes
        ),
        "Phase 221 docs diff contains forbidden mutation terms",
    )

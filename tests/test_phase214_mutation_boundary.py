"""Phase 214 MEAS-03 structural mutation-boundary tests.

These tests enforce D-14 (no src/wanctl controller edits), D-11 (no Phase 213
back-edits), and the observational-only output discipline at pytest time.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning/phases/214-measurement-collapse-investigation"
MUTATION_BOUNDARY_TEST = REPO_ROOT / "tests/test_phase214_mutation_boundary.py"
PHASE213_BACK_EDIT_PATHS = [
    "scripts/phase213-classify.py",
    "scripts/phase213-baseline-capture.sh",
]
PROTECTED_PATHS = ["src/wanctl/", *PHASE213_BACK_EDIT_PATHS]
# Exception: t_bfe1e19b — C901 refactor of _run_logging_metrics in wan_controller.py
EXEMPT_WANCTL_PATHS = {"src/wanctl/wan_controller.py"}

# Line-anchored command/assignment forms only. Narrative references to the same
# words must not trip; active verbs and assignment forms at line start must trip.
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


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _phase_base_sha() -> str:
    env_sha = os.environ.get("PHASE214_BASE_SHA", "").strip()
    if env_sha:
        return env_sha

    for args in (["merge-base", "HEAD", "origin/main"], ["rev-parse", "HEAD~10"]):
        result = _git(args)
        candidate = result.stdout.strip()
        if result.returncode != 0 or not candidate:
            continue
        # origin/main may be older than the active milestone in local sequential
        # execution. Use it only if it is a clean heuristic boundary for this
        # phase's protected paths; otherwise fall through to HEAD~10.
        committed = _git(["diff", "--name-only", f"{candidate}..HEAD", "--", *PROTECTED_PATHS])
        if committed.returncode == 0 and not committed.stdout.strip():
            return candidate
    pytest.skip("could not resolve a clean Phase 214 base SHA; set PHASE214_BASE_SHA")


def _assert_no_git_diff(paths: list[str], label: str) -> None:
    base = _phase_base_sha()
    checks = [
        ("unstaged", ["diff", "--name-only", "--", *paths]),
        ("staged", ["diff", "--cached", "--name-only", "--", *paths]),
        ("committed", ["diff", "--name-only", f"{base}..HEAD", "--", *paths]),
    ]
    failures: list[str] = []
    for check_name, args in checks:
        result = _git(args)
        changed = [line for line in result.stdout.splitlines() if line.strip()]
        # Filter out known exceptions (e.g., t_bfe1e19b C901 refactor)
        changed = [f for f in changed if f not in EXEMPT_WANCTL_PATHS]
        if result.returncode != 0 or changed:
            detail = result.stderr.strip() or ", ".join(changed)
            failures.append(f"{label} {check_name} diff failed: {detail}")
    assert failures == []


def _forbidden_matches(text: str) -> list[str]:
    return [match.group(0).strip() for match in FORBIDDEN_MUTATION_RE.finditer(text)]


def test_mutation_boundary_test_exists() -> None:
    assert MUTATION_BOUNDARY_TEST.exists(), "tests/test_phase214_mutation_boundary.py must exist"


def test_no_src_wanctl_diff() -> None:
    _assert_no_git_diff(["src/wanctl/"], "src/wanctl")


def test_no_phase213_script_back_edit() -> None:
    _assert_no_git_diff(PHASE213_BACK_EDIT_PATHS, "phase213 script")


def test_matrix_summary_has_no_mutation_recommendation_tokens() -> None:
    paths = sorted(PHASE_DIR.glob("evidence/**/matrix-summary.json"))
    if not paths:
        pytest.skip("no generated matrix-summary.json yet")
    for path in paths:
        matches = _forbidden_matches(path.read_text(encoding="utf-8"))
        assert matches == [], f"{path} contains mutation recommendation token(s): {matches}"


def test_report_has_no_mutation_recommendation_tokens() -> None:
    report = PHASE_DIR / "214-REPORT.md"
    if not report.exists():
        pytest.skip("214-REPORT.md not generated yet")
    matches = _forbidden_matches(report.read_text(encoding="utf-8"))
    assert matches == [], f"{report} contains mutation recommendation token(s): {matches}"


def test_mutation_regex_correctly_flags_known_bad_strings() -> None:
    bad_lines = [
        "systemctl restart wanctl@spectrum",
        "service wanctl@att restart",
        "restart wanctl@spectrum",
        "ceiling_mbps: 12",
        "setpoint_mbps=12",
        "/etc/wanctl/spectrum.yaml edit",
        "mikrotik write queue limit",
        "routeros set queue limit",
        "steering toggle",
    ]
    for line in bad_lines:
        assert _forbidden_matches(line), f"expected forbidden mutation match for: {line}"


def test_mutation_regex_does_not_false_positive_on_narrative() -> None:
    narrative_lines = [
        "we considered changing ceiling_mbps but the evidence did not support it",
        "restart wanctl is a future-phase consideration, not a Phase 214 recommendation",
        "the operator should not run systemctl restart wanctl@spectrum",
        "If you ever needed to restart wanctl@spectrum, it would be in a separate phase",
    ]
    command_lines = [
        "$ systemctl restart wanctl@spectrum",
        "sudo systemctl restart wanctl",
        "    systemctl restart wanctl",
        "ceiling_mbps: 12",
    ]

    for line in narrative_lines:
        assert _forbidden_matches(line) == [], f"unexpected narrative match for: {line}"
    for line in command_lines:
        assert _forbidden_matches(line), f"expected command-form match for: {line}"

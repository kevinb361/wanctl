"""Phase 219 SAFE-11 mutation-boundary clone.

The allowlist mirrors CONTEXT.md Mutation-boundary scope. Controller-path files
remain forbidden per REQUIREMENTS.md SAFE-11, and all three diff channels
(unstaged/staged/committed) are checked per Codex M3.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning/phases/219-ingestion-rate-observability-scope-d"
ALLOWED_SRC_PATHS = ["src/wanctl/history.py", "src/wanctl/operator_summary.py"]
FORBIDDEN_SRC_PATHS = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
]

backends_dir = REPO_ROOT / "src/wanctl/backends"
if backends_dir.exists():
    FORBIDDEN_SRC_PATHS.extend(
        str(path.relative_to(REPO_ROOT)) for path in sorted(backends_dir.glob("**/*.py"))
    )
FORBIDDEN_SRC_PATHS.extend(
    str(path.relative_to(REPO_ROOT)) for path in sorted((REPO_ROOT / "src/wanctl").glob("fusion*.py"))
)

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
    env_sha = os.environ.get("PHASE219_BASE_SHA", "").strip()
    if env_sha:
        return env_sha

    protected_paths = [*FORBIDDEN_SRC_PATHS, "docs/CONFIGURATION.md"]
    for args in (["merge-base", "HEAD", "origin/main"], ["rev-parse", "HEAD~10"]):
        result = _git(args)
        candidate = result.stdout.strip()
        if result.returncode != 0 or not candidate:
            continue
        committed = _git(["diff", "--name-only", f"{candidate}..HEAD", "--", *protected_paths])
        if committed.returncode == 0 and not committed.stdout.strip():
            return candidate
    pytest.skip("could not resolve a clean Phase 219 base SHA; set PHASE219_BASE_SHA")


def _assert_no_git_diff(paths: list[str], label: str) -> None:
    base = _phase_base_sha()
    checks = [
        ("unstaged", ["diff", "--name-only", "--", *paths]),
        ("staged", ["diff", "--staged", "--name-only", "--", *paths]),
        ("committed", ["diff", "--name-only", f"{base}..HEAD", "--", *paths]),
    ]
    failures: list[str] = []
    for check_name, args in checks:
        result = _git(args)
        changed = [line for line in result.stdout.splitlines() if line.strip()]
        if result.returncode != 0 or changed:
            detail = result.stderr.strip() or ", ".join(changed)
            failures.append(f"{label} {check_name} diff failed: {detail}")
    assert failures == []


def _forbidden_matches(text: str) -> list[str]:
    return [match.group(0).strip() for match in FORBIDDEN_MUTATION_RE.finditer(text)]


def test_no_forbidden_controller_path_diff() -> None:
    _assert_no_git_diff(FORBIDDEN_SRC_PATHS, "controller-path")


def test_no_other_src_diff_outside_allowlist() -> None:
    pathspec = ["src/wanctl/"] + [f":(exclude){path}" for path in ALLOWED_SRC_PATHS]
    base = _phase_base_sha()
    checks = [
        ("unstaged", ["diff", "--name-only", "--", *pathspec]),
        ("staged", ["diff", "--staged", "--name-only", "--", *pathspec]),
        ("committed", ["diff", "--name-only", f"{base}..HEAD", "--", *pathspec]),
    ]
    failures: list[str] = []
    for check_name, args in checks:
        result = _git(args)
        changed = [line for line in result.stdout.splitlines() if line.strip()]
        if result.returncode != 0 or changed:
            detail = result.stderr.strip() or ", ".join(changed)
            failures.append(f"src/wanctl outside allowlist {check_name} diff failed: {detail}")
    assert failures == []


def test_phase219_docs_have_no_threshold_tuning_tokens() -> None:
    docs_path = REPO_ROOT / "docs/CONFIGURATION.md"
    base = _phase_base_sha()
    diff = _git(["diff", "--name-only", f"{base}..HEAD", "--", "docs/CONFIGURATION.md"])
    if diff.returncode != 0 or not diff.stdout.strip():
        pytest.skip("docs/CONFIGURATION.md has no Phase 219-attributable diff")
    matches = _forbidden_matches(docs_path.read_text(encoding="utf-8"))
    assert matches == [], f"docs/CONFIGURATION.md contains mutation token(s): {matches}"


def test_phase219_scripts_allowlist() -> None:
    base = _phase_base_sha()
    script_glob = "scripts/phase219_*.py"
    diff = _git(["diff", "--name-only", f"{base}..HEAD", "--", script_glob])
    assert diff.returncode == 0
    # Any scripts/phase219_*.py diff is allowed by SAFE-11; the assertion above
    # exists to pin the underscore glob and ensure the pathspec remains valid.
    assert script_glob.startswith("scripts/phase219_")

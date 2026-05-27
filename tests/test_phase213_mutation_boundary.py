import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE213_SCRIPTS = [
    Path("scripts/phase213-baseline-capture.sh"),
    Path("scripts/phase213-health-poller.sh"),
    Path("scripts/phase213-browse-loop.sh"),
    Path("scripts/phase213-alert-window.sh"),
    Path("scripts/phase213-steering-snapshot.sh"),
    Path("scripts/phase213-classify.py"),
]

FORBIDDEN = [
    r"\bsystemctl\s+restart\s+wanctl@",
    r"\bsystemctl\s+(start|stop)\s+wanctl",
    r">\s*/etc/wanctl/.*\.ya?ml",
    r"\bdeploy(_clean|_steering)?\.sh\b",
    r"\binstall(-systemd)?\.sh\b",
    r"ssh\s+\S+\s+[\"']?\s*/system/script\b|/ip/cake/|/queue/tree/",
    r"\bsteering-(enable|disable)\b",
    r"\bwanctl\s+steering\s+toggle\b",
]


def strip_comments(body: str) -> str:
    """Strip shell comments and heredoc bodies before mutation-token scanning."""
    kept: list[str] = []
    heredoc_end: str | None = None
    for line in body.splitlines():
        if heredoc_end is not None:
            if line.strip() == heredoc_end:
                heredoc_end = None
            continue
        if line.lstrip().startswith("#"):
            continue
        match = re.search(r"<<[-]?['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line)
        if match:
            heredoc_end = match.group(1)
            kept.append(line)
            continue
        kept.append(line)
    return "\n".join(kept)


def _matches(body: str) -> list[str]:
    stripped = strip_comments(body)
    return [pat for pat in FORBIDDEN if re.search(pat, stripped)]


@pytest.mark.parametrize("script_path", PHASE213_SCRIPTS)
def test_no_forbidden_mutation_tokens_per_script(script_path: Path) -> None:
    path = REPO_ROOT / script_path
    if not path.exists():
        pytest.skip(f"{script_path} not built yet")

    matches = _matches(path.read_text())
    assert matches == [], f"{script_path} contains forbidden mutation pattern(s): {matches}"


def test_legitimate_doc_fixture_does_not_trip_guard() -> None:
    path = REPO_ROOT / "tests/fixtures/phase213/mutation-fixtures/legitimate-doc.sh"
    assert _matches(path.read_text()) == []


def test_forbidden_fixture_does_trip_guard() -> None:
    path = REPO_ROOT / "tests/fixtures/phase213/mutation-fixtures/forbidden-restart.sh"
    matches = _matches(path.read_text())
    assert r"\bsystemctl\s+restart\s+wanctl@" in matches

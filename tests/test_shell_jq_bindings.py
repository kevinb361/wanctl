"""jq `as` bindings in shell scripts must parse the same under jq 1.7 and jq 1.8.

jq 1.8.0 changed the precedence of binding syntax against unary and binary operators (jq NEWS, "Fix precedence of
binding syntax", #3053 #3326). `X + 1 as $n | body` binds `$n` to `X + 1` under jq 1.8 but parses as
`X + (1 as $n | body)` under earlier releases, so `$n` is 1 there. The capacity sweep's Prometheus coverage check hit
exactly this on a CI runner ("expected 1 points, got 9") while passing locally under jq 1.8.1.

A binding is unambiguous in both grammars when its left side is a single term: a parenthesized or bracketed
expression, a function call, `.` or a plain path. The local jq cannot reproduce the old parse, so this checks the
source form instead of running jq.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((REPO_ROOT / "scripts").glob("*.sh"))

BINDING = re.compile(r"\s+as\s+\$[A-Za-z_]")
# left side ending in ")" or "]", or a bare `.` / `.path` right after a pipe, paren, bracket, semicolon or line start
SINGLE_TERM = re.compile(
    r"(?:[)\]]|(?:^|[\s(|\[;])\.(?:[A-Za-z_][A-Za-z0-9_]*)?(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$"
)


def _ambiguous_bindings(text: str) -> list[str]:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in BINDING.finditer(line):
            if not SINGLE_TERM.search(line[: m.start()]):
                found.append(f"{n}: {line.strip()}")
    return found


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_jq_bindings_have_a_single_term_left_side(script: Path) -> None:
    assert _ambiguous_bindings(script.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("line", "ambiguous"),
    [
        ("| (($e - $s) / $st | floor) + 1 as $want", True),
        ("| . + 2 as $x | -$x", True),
        ("| ((($e - $s) / $st | floor) + 1) as $want", False),
        ("| map([(.[0] | tonumber)]) as $v", False),
        ("[ .[] | .wans[0].baseline_rtt_ms ] as $rtts", False),
        ("map(. as $c | $c)", False),
        ("| .metadata as $m", False),
    ],
)
def test_checker_tells_ambiguous_from_single_term(line: str, ambiguous: bool) -> None:
    assert bool(_ambiguous_bindings(line)) is ambiguous

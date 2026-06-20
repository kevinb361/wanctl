"""Validate deterministic read-only RouterOS command files."""
from __future__ import annotations

import re
import sys
from pathlib import Path

READ_ONLY_ROUTEROS_OBJECTS = (
    "/ip route print",
    "/ip/route/print",
    "/tool netwatch print",
    "/tool/netwatch/print",
    "/system script print",
    "/system/script/print",
)

FORBIDDEN_SUBSTRINGS = (
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    ">",
    "<",
)

FORBIDDEN_ROUTEROS_ACTIONS = (
    " set ",
    " add ",
    " remove ",
    " enable ",
    " disable ",
    " run ",
    " import ",
    " reset ",
    "/set",
    "/add",
    "/remove",
    "/enable",
    "/disable",
    "/run",
    "/import",
    "/reset",
)

PREFIX = "COMMAND:"


def iter_commands(path: Path) -> list[str]:
    commands: list[str] = []
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        if not raw.startswith(PREFIX):
            raise ValueError(f"line {line_no}: executable line must start with COMMAND:")
        command = raw.removeprefix(PREFIX).strip()
        if not command:
            raise ValueError(f"line {line_no}: empty COMMAND line")
        commands.append(command)
    if not commands:
        raise ValueError("no COMMAND lines found")
    return commands


def _normalized_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip())


def _starts_with_read_object(command: str, read_object: str) -> bool:
    if not command.startswith(read_object):
        return False
    if len(command) == len(read_object):
        return True
    return command[len(read_object)] in {" ", "/"}


def validate_command(command: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in command:
            raise ValueError(f"rejected shell metacharacter {token!r}: {command}")

    normalized = _normalized_command(command)
    lowered = f" {normalized.lower()} "
    slash_lowered = normalized.lower()
    for token in FORBIDDEN_ROUTEROS_ACTIONS:
        if token.startswith("/"):
            if token in slash_lowered:
                raise ValueError(f"rejected RouterOS mutating action {token!r}: {command}")
        elif token in lowered:
            raise ValueError(f"rejected RouterOS mutating action {token!r}: {command}")

    normalized_lower = normalized.lower()
    if not any(
        _starts_with_read_object(normalized_lower, read_object)
        for read_object in READ_ONLY_ROUTEROS_OBJECTS
    ):
        raise ValueError(
            "command does not start with a recognized read-only RouterOS object: "
            f"{command}"
        )


def validate_path(path: Path) -> int:
    commands = iter_commands(path)
    for command in commands:
        validate_command(command)
    print("READONLY_COMMANDS_VALIDATED")
    return 0


def self_test() -> int:
    bad_commands = [
        "/ip route disable 0",
        "/tool netwatch print; id",
        '/log print where message~"/ip route print"',
    ]
    for command in bad_commands:
        try:
            validate_command(command)
        except ValueError:
            continue
        print(f"SELF_TEST_FAILED accepted mutating command: {command}", file=sys.stderr)
        return 1
    print("READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED")
    return 0


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    if len(argv) != 1:
        print(f"usage: {Path(sys.argv[0]).name} <command-file>|--self-test", file=sys.stderr)
        return 2
    try:
        return validate_path(Path(argv[0]))
    except (OSError, ValueError) as exc:
        print(f"READONLY_COMMANDS_REJECTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

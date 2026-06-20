#!/usr/bin/env python3
"""Validate Phase 257 deterministic read-only command files."""
from __future__ import annotations

import sys
from pathlib import Path

ALLOWED_COMMANDS = {
    "ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health'",
    "ssh cake-shaper 'systemctl is-active steering.service'",
    "ssh cake-shaper 'systemctl show steering.service --property=NRestarts,ExecMainStartTimestamp,ExecStart,WorkingDirectory --no-pager'",
    'ssh cake-shaper \'journalctl -u steering.service --since "-15 minutes" --no-pager\'',
    "ssh cake-shaper 'curl -fsS http://10.10.110.223:9101/health'",
    "ssh cake-shaper 'curl -fsS http://10.10.110.227:9101/health'",
    'ssh cake-shaper \'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system identity print"\'',
    'ssh cake-shaper \'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/tool netwatch print detail"\'',
    'ssh cake-shaper \'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/system script print detail"\'',
    'ssh cake-shaper \'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/ip route print detail"\'',
}

FORBIDDEN_SUBSTRINGS = (
    ';',
    '&&',
    '||',
    '|',
    '`',
    '$(',
    '>',
    '<',
)

FORBIDDEN_ROUTEROS_ACTIONS = (
    ' set ',
    ' add ',
    ' remove ',
    ' enable ',
    ' disable ',
    ' run ',
    ' import ',
    ' reset ',
    '/set',
    '/add',
    '/remove',
    '/enable',
    '/disable',
    '/run',
    '/import',
    '/reset',
)

PREFIX = 'COMMAND:'


def iter_commands(path: Path) -> list[str]:
    commands: list[str] = []
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        if not raw.startswith(PREFIX):
            raise ValueError(f'line {line_no}: executable line must start with COMMAND:')
        command = raw.removeprefix(PREFIX).strip()
        if not command:
            raise ValueError(f'line {line_no}: empty COMMAND line')
        commands.append(command)
    if not commands:
        raise ValueError('no COMMAND lines found')
    return commands


def validate_command(command: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in command:
            raise ValueError(f'rejected shell metacharacter {token!r}: {command}')
    lowered = f' {command.lower()} '
    slash_lowered = command.lower()
    for token in FORBIDDEN_ROUTEROS_ACTIONS:
        if token.startswith('/'):
            if token in slash_lowered:
                raise ValueError(f'rejected RouterOS mutating action {token!r}: {command}')
        elif token in lowered:
            raise ValueError(f'rejected RouterOS mutating action {token!r}: {command}')
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f'command is not in Phase 257 read-only allowlist: {command}')


def validate_path(path: Path) -> int:
    commands = iter_commands(path)
    for command in commands:
        validate_command(command)
    print('READONLY_COMMANDS_VALIDATED')
    return 0


def self_test() -> int:
    bad_commands = [
        'ssh cake-shaper \'sudo -n ssh -i /etc/wanctl/ssh/router.key -o BatchMode=yes -o StrictHostKeyChecking=yes admin@10.10.99.1 "/ip route disable 0"\'',
        "ssh cake-shaper 'curl -fsS http://127.0.0.1:9102/health; id'",
    ]
    for command in bad_commands:
        try:
            validate_command(command)
        except ValueError:
            continue
        print(f'SELF_TEST_FAILED accepted mutating command: {command}', file=sys.stderr)
        return 1
    print('READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED')
    return 0


def main(argv: list[str]) -> int:
    if argv == ['--self-test']:
        return self_test()
    if len(argv) != 1:
        print(f'usage: {Path(sys.argv[0]).name} <command-file>|--self-test', file=sys.stderr)
        return 2
    try:
        return validate_path(Path(argv[0]))
    except (OSError, ValueError) as exc:
        print(f'READONLY_COMMANDS_REJECTED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

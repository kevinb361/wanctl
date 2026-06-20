"""Tests for read-only RouterOS command validator."""
from __future__ import annotations

from pathlib import Path

import pytest

from wanctl.readonly_validator import (
    iter_commands,
    self_test,
    validate_command,
    validate_path,
)


@pytest.mark.parametrize(
    "command",
    [
        "/ip route print detail",
        "/ip/route/print",
        "/tool netwatch print detail",
        "/tool/netwatch/print",
        "/system script print detail",
        "/system/script/print",
        "/ip   route   print   detail",
    ],
)
def test_validate_command_accepts_read_only_routeros_objects(command: str) -> None:
    validate_command(command)


@pytest.mark.parametrize(
    "command, message",
    [
        ("/ip route disable 0", "mutating action"),
        ("/tool netwatch print; id", "shell metacharacter"),
        ("/system resource print", "recognized read-only RouterOS object"),
        ('/log print where message~"/ip route print"', "recognized read-only RouterOS object"),
    ],
)
def test_validate_command_rejects_unsafe_or_unknown_commands(
    command: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_command(command)


def test_iter_commands_reads_command_prefixed_lines(tmp_path: Path) -> None:
    command_file = tmp_path / "commands.txt"
    command_file.write_text(
        "COMMAND: /ip route print\n\nCOMMAND: /tool netwatch print detail\n"
    )

    assert iter_commands(command_file) == [
        "/ip route print",
        "/tool netwatch print detail",
    ]


def test_validate_path_accepts_command_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    command_file = tmp_path / "commands.txt"
    command_file.write_text(
        "COMMAND: /ip route print\n"
        "COMMAND: /tool netwatch print\n"
        "COMMAND: /system script print\n"
    )

    assert validate_path(command_file) == 0
    assert "READONLY_COMMANDS_VALIDATED" in capsys.readouterr().out


def test_self_test_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert self_test() == 0
    assert "READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED" in capsys.readouterr().out

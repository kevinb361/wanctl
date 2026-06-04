from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase227-qdisc-verify.sh"


def _cake(mode: str) -> str:
    return f"""
qdisc cake 8001: root refcnt 2 bandwidth 920Mbit {mode} wash
 Sent 123 bytes 4 pkt (dropped 0, overlimits 0 requeues 0)
 Tin 0
  pkts 4
"""


def _run_with_inputs(tmp_path: Path, router_text: str, modem_text: str, expected: str = "diffserv4") -> subprocess.CompletedProcess[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    router = tmp_path / "router.txt"
    modem = tmp_path / "modem.txt"
    out = tmp_path / "proof.json"
    router.write_text(router_text, encoding="utf-8")
    modem.write_text(modem_text, encoding="utf-8")
    return subprocess.run(
        [
            str(SCRIPT),
            "--expected-mode",
            expected,
            "--router-input",
            str(router),
            "--modem-input",
            str(modem),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_dry_run_reports_expected_mode_without_ssh() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--expected-mode", "diffserv4", "--dry-run"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "expected_mode=diffserv4" in result.stdout
    assert "no SSH performed" in result.stdout


def test_matching_besteffort_and_diffserv4_modes_pass(tmp_path: Path) -> None:
    best = _run_with_inputs(tmp_path / "best", _cake("besteffort"), _cake("besteffort"), expected="besteffort")
    diff = _run_with_inputs(tmp_path / "diff", _cake("diffserv4"), _cake("diffserv4"), expected="diffserv4")

    assert best.returncode == 0, best.stderr
    assert "router=besteffort modem=besteffort" in best.stdout
    assert diff.returncode == 0, diff.stderr
    assert "router=diffserv4 modem=diffserv4" in diff.stdout


def test_wrong_mode_fails_closed_and_writes_proof(tmp_path: Path) -> None:
    result = _run_with_inputs(tmp_path, _cake("diffserv3"), _cake("diffserv4"), expected="diffserv4")

    assert result.returncode != 0
    assert "expected diffserv4 got diffserv3" in result.stderr
    proof = json.loads((tmp_path / "proof.json").read_text(encoding="utf-8"))
    assert proof["router_got"] == "diffserv3"
    assert proof["modem_got"] == "diffserv4"
    assert proof["match"] is False


def test_no_cake_fails_closed(tmp_path: Path) -> None:
    result = _run_with_inputs(tmp_path, "qdisc fq_codel 0: root\n", _cake("diffserv4"))

    assert result.returncode != 0
    assert "got no_cake" in result.stderr


def test_two_cake_lines_are_ambiguous_and_fail_closed(tmp_path: Path) -> None:
    result = _run_with_inputs(tmp_path, _cake("diffserv4") + _cake("besteffort"), _cake("diffserv4"))

    assert result.returncode != 0
    assert "got ambiguous" in result.stderr


def test_missing_device_or_empty_output_fails_closed(tmp_path: Path) -> None:
    missing = _run_with_inputs(tmp_path / "missing", "Cannot find device spec-router\n", _cake("diffserv4"))
    empty = _run_with_inputs(tmp_path / "empty", "", _cake("diffserv4"))

    assert missing.returncode != 0
    assert "got missing" in missing.stderr
    assert empty.returncode != 0
    assert "got missing" in empty.stderr


def test_simulated_ssh_failure_fails_closed(tmp_path: Path) -> None:
    out = tmp_path / "proof.json"
    result = subprocess.run(
        [str(SCRIPT), "--expected-mode", "diffserv4", "--simulate-ssh-failed", "--out", str(out)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0
    assert "got ssh_failed" in result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))
    assert proof["router_got"] == "ssh_failed"
    assert proof["modem_got"] == "ssh_failed"


def test_unsafe_interface_name_refuses_before_ssh() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--expected-mode", "diffserv4", "--router-iface", "spec-router';id", "--simulate-ssh-failed"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 2
    assert "unsafe interface name" in result.stderr

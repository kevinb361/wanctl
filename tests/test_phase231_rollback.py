from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "phase231-rollback.sh"


def run_script(
    *args: str,
    tmp_path: Path | None = None,
    external_writer_state: str = "active",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if tmp_path is not None:
        shim_dir = tmp_path / "bin"
        shim_dir.mkdir(exist_ok=True)
        log = tmp_path / "ssh.log"
        ssh = shim_dir / "ssh"
        ssh.write_text(
            f"""#!/bin/bash
printf '%s\n' "$*" >> {log}
payload="$*"
if [[ "$payload" == *"bash -s"* ]]; then
  cat >> {tmp_path / "payload.log"}
  printf '%s\n' 'ok'
elif [[ "$payload" == *"systemctl cat cake-autorate-att.service"* ]]; then
  printf '%s\n' 'Conflicts=wanctl@att.service'
elif [[ "$payload" == *"systemctl cat cake-autorate-spectrum.service"* ]]; then
  printf '%s\n' 'Conflicts=wanctl@spectrum.service'
elif [[ "$payload" == *"systemctl is-active cake-autorate-att.service"* ]]; then
  printf '%s\n' '{external_writer_state}'
elif [[ "$payload" == *"systemctl is-active cake-autorate-spectrum.service"* ]]; then
  printf '%s\n' '{external_writer_state}'
elif [[ "$payload" == *"systemctl is-enabled wanctl@"* ]]; then
  printf '%s\n' 'disabled'
elif [[ "$payload" == *"wanctl@att.service"* && "$payload" == *"is-active"* ]]; then
  printf '%s\n' 'inactive'
elif [[ "$payload" == *"wanctl@spectrum.service"* && "$payload" == *"is-active"* ]]; then
  printf '%s\n' 'inactive'
elif [[ "$payload" == *"silicom-bypass-watchdog@att.service"* && "$payload" == *"is-active"* ]]; then
  printf '%s\n' 'inactive'
elif [[ "$payload" == *"systemctl is-active"* ]]; then
  printf '%s\n' 'active'
else
  printf '%s\n' 'ok'
fi
exit 0
""",
            encoding="utf-8",
        )
        ssh.chmod(0o755)
        env["PATH"] = f"{shim_dir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def assert_no_mutation_commands(log_text: str) -> None:
    assert not re.search(r"systemctl\b.*\b(enable|disable|restart|start|stop)\b", log_text)
    assert not re.search(r"tc\b.*\bqdisc\b.*\b(replace|add|del)\b", log_text)


def test_confirm_requires_operator_approval_before_remote_call(tmp_path: Path) -> None:
    result = run_script("--wan", "att", "--confirm", tmp_path=tmp_path)

    assert result.returncode != 0
    assert "requires --i-have-operator-approval" in result.stderr
    log = tmp_path / "ssh.log"
    assert not log.exists() or log.read_text(encoding="utf-8") == ""


def test_dry_run_att_renders_units_bpctl_and_no_ssh_mutation(tmp_path: Path) -> None:
    result = run_script("--wan", "att", "--dry-run", tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "silicom-bypass-watchdog-cake-autorate-att.service" in result.stdout
    assert "wanctl@att.service" in result.stdout
    assert "silicom-bypass-watchdog@att.service" in result.stdout
    assert "att-router" in result.stdout
    assert "./bpctl_util att-modem set_disc off" in result.stdout
    log = tmp_path / "ssh.log"
    assert not log.exists() or log.read_text(encoding="utf-8") == ""


def test_dry_run_spectrum_leaves_watchdog_untouched(tmp_path: Path) -> None:
    result = run_script("--wan", "spectrum", "--dry-run", tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "cake-autorate-spectrum-state-bridge.service" in result.stdout
    assert "wanctl@spectrum.service" in result.stdout
    assert "spec-router" in result.stdout
    assert "spec-modem" in result.stdout
    assert "disable --now cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service" in result.stdout
    assert "disable --now silicom-bypass-watchdog@spectrum.service" not in result.stdout
    assert "enable --now silicom-bypass-watchdog@spectrum.service" not in result.stdout


def test_dry_run_renders_return_to_cake_sequences() -> None:
    att = run_script("--wan", "att", "--dry-run")
    spectrum = run_script("--wan", "spectrum", "--dry-run")

    assert "Return-to-cake sequence" in att.stdout
    assert "cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service" in att.stdout
    assert "cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service" in spectrum.stdout
    assert "/usr/local/sbin/cake-autorate-att-qdisc-init" in att.stdout
    assert "/usr/local/sbin/cake-autorate-spectrum-qdisc-init" in spectrum.stdout


def test_preflight_json_shape_att(tmp_path: Path) -> None:
    out = tmp_path / "rollback-preflight-att.json"
    result = run_script("--wan", "att", "--preflight", "--out", str(out), tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    names = {check["name"]: check for check in payload["checks"]}
    assert payload["proof_type"] == "phase231-rollback-preflight"
    assert payload["read_only"] is True
    assert names["native_instance_disabled"]["raw_stdout"] == "disabled\n"
    assert "att_bpctl_executable" in names
    assert "att_watchdog_env_present" in names
    assert "rollback_sequence" in payload
    assert "return_to_cake_sequence" in payload
    assert "sudo tc qdisc replace dev att-router" in payload["rollback_sequence"]


def test_confirm_remote_payload_is_fail_fast_and_verify_fails_closed(tmp_path: Path) -> None:
    """Prove CR-01 fail-fast payload and fail-closed external writer check via shim only."""

    result = run_script("--wan", "att", "--confirm", "--i-have-operator-approval", tmp_path=tmp_path)

    assert result.returncode == 1
    assert "ROLLBACK VERIFY FAILED: cake-autorate-att.service is still active" in result.stderr
    payload = (tmp_path / "payload.log").read_text(encoding="utf-8")
    assert payload.splitlines()[0] == "set -euo pipefail"
    assert "sudo systemctl disable --now cake-autorate-att.service" in payload
    assert "sudo tc qdisc replace dev att-router" in payload


def test_confirm_bash_s_argv_excludes_dash_n(tmp_path: Path) -> None:
    result = run_script("--wan", "att", "--confirm", "--i-have-operator-approval", tmp_path=tmp_path)

    assert result.returncode == 1
    log_lines = (tmp_path / "ssh.log").read_text(encoding="utf-8").splitlines()
    bash_s_line = next(line for line in log_lines if "bash -s" in line)
    assert not re.search(r"(^|\s)-n(\s|$)", bash_s_line)
    assert any(" -n " in f" {line} " and "systemctl is-active" in line for line in log_lines)


def test_confirm_external_writer_activating_fails_closed(tmp_path: Path) -> None:
    result = run_script(
        "--wan",
        "att",
        "--confirm",
        "--i-have-operator-approval",
        tmp_path=tmp_path,
        external_writer_state="activating",
    )

    assert result.returncode == 1
    assert "ROLLBACK VERIFY FAILED: cake-autorate-att.service is still activating" in result.stderr


def test_confirm_external_writer_check_ordering(tmp_path: Path) -> None:
    result = run_script(
        "--wan",
        "att",
        "--confirm",
        "--i-have-operator-approval",
        tmp_path=tmp_path,
        external_writer_state="inactive",
    )

    assert result.returncode == 1
    assert "ROLLBACK VERIFY FAILED: wanctl@att.service is-active=inactive" in result.stderr
    assert "HEALTH FAIL" not in result.stderr


def test_preflight_command_log_is_read_only(tmp_path: Path) -> None:
    out = tmp_path / "rollback-preflight-att.json"
    result = run_script("--wan", "att", "--preflight", "--out", str(out), tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "ssh.log").read_text(encoding="utf-8")
    assert_no_mutation_commands(log_text)
    assert "systemctl is-active" in log_text


def test_dry_run_command_log_is_read_only(tmp_path: Path) -> None:
    result = run_script("--wan", "att", "--dry-run", tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    log = tmp_path / "ssh.log"
    log_text = log.read_text(encoding="utf-8") if log.exists() else ""
    assert_no_mutation_commands(log_text)


def test_script_does_not_reference_phase226_restore() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "phase226-restore.sh" not in text


def test_confirm_gating_and_confirm_path_are_explicit_in_source() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "OPERATOR_APPROVAL" in text
    assert "run_confirm" in text
    assert "REFUSED: --confirm requires --i-have-operator-approval" in text
    assert "sudo systemctl disable --now" in text
    assert "sudo tc qdisc replace" in text

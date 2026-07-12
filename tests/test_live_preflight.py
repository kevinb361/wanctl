from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "live_preflight.py"


def test_live_preflight_help_does_not_touch_network() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "Read-only live preflight" in result.stdout
    assert "ssh" not in result.stderr.lower()


def test_live_preflight_static_remote_commands_are_read_only() -> None:
    text = SCRIPT.read_text()
    forbidden = [
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl enable ",
        "systemctl disable",
        "systemctl mask",
        "tc qdisc replace",
        "tc qdisc change",
        "sed -i",
        "kill -",
    ]
    remote_commands = text.split("READ_ONLY_REMOTE_COMMANDS = [", 1)[1].split(
        "]\n\nMUTATION_TOKENS", 1
    )[0]
    for token in forbidden:
        assert token not in remote_commands

    assert "mutation_mode_available" in text
    assert "False" in text
    assert "phase231-rollback.sh" in text
    assert "--dry-run" in text
    assert "--confirm" not in " ".join(
        line for line in text.splitlines() if "phase231-rollback.sh" in line and "cmd =" in line
    )


def test_live_preflight_writes_passed_json_with_fake_ssh(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_ssh = bin_dir / "ssh"
    fake_ssh.write_text(
        textwrap.dedent(
            r'''
            #!/usr/bin/env bash
            set -euo pipefail
            cmd="${!#}"
            case "$cmd" in
              "hostname -f || hostname") echo "cake-shaper.home.arpa" ;;
              "date -u +%Y-%m-%dT%H:%M:%SZ") echo "2026-07-12T14:45:00Z" ;;
              "systemctl is-active wanctl@spectrum.service || true"|"systemctl is-active wanctl@att.service || true") echo "inactive" ;;
              "systemctl is-active "*) echo "active" ;;
              "systemctl is-enabled "*) echo "enabled" ;;
              "systemctl cat cake-autorate-spectrum.service") echo "[Unit]"; echo "Conflicts=wanctl@spectrum.service" ;;
              "systemctl cat cake-autorate-att.service") echo "[Unit]"; echo "Conflicts=wanctl@att.service" ;;
              "sudo -n test -f /etc/wanctl/spectrum.yaml"|"sudo -n test -f /etc/wanctl/att.yaml"|"test -f /opt/wanctl/autorate_continuous.py") exit 0 ;;
              "curl -fsS --max-time 5 http://127.0.0.1:9102/health") echo '{"status":"healthy","route_management":{"mode":"active","active_owner":"wanctl","guard":{"status":"ok","conflict_count":0}}}' ;;
              "curl -fsS --max-time 5 http://10.10.110.223:9101/health") echo '{"status":"healthy","wan":"spectrum"}' ;;
              "curl -fsS --max-time 5 http://10.10.110.227:9101/health") echo '{"status":"healthy","wan":"att"}' ;;
              *) echo "unexpected command: $cmd" >&2; exit 99 ;;
            esac
            '''
        ).lstrip()
    )
    fake_ssh.chmod(0o755)
    out = tmp_path / "proof.json"
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "WANCTL_PREFLIGHT_FIXED_TIME": "2026-07-12T14:45:00Z",
    }

    result = subprocess.run(
        ["python3", str(SCRIPT), "--ssh-host", "cake-shaper", "--out", str(out)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(out.read_text())
    assert payload["proof_type"] == "wanctl-live-preflight"
    assert payload["read_only"] is True
    assert payload["mutation_mode_available"] is False
    assert payload["overall_pass"] is True
    assert payload["summary"]["route_management_mode"] == "active"
    assert payload["summary"]["route_guard_status"] == "ok"
    assert payload["summary"]["route_conflict_count"] == 0
    assert any(check["name"] == "rollback_dry_run_spectrum" for check in payload["checks"])
    assert all("--confirm" not in check["command"] for check in payload["checks"])

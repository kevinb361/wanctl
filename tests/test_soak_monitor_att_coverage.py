from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOAK = REPO_ROOT / "scripts" / "soak-monitor.sh"


def test_soak_monitor_scans_live_att_units() -> None:
    text = SOAK.read_text(encoding="utf-8")

    assert "cake-autorate-att.service" in text
    assert "cake-autorate-att-state-bridge.service" in text
    assert "silicom-bypass-watchdog@att.service" in text


def test_soak_monitor_mode_detection_not_spectrum_hardcoded() -> None:
    text = SOAK.read_text(encoding="utf-8")

    assert "is_external_cake_mode" in text


def test_soak_monitor_external_units_for_att_has_watchdog() -> None:
    text = SOAK.read_text(encoding="utf-8")

    assert "external_units_for" in text
    assert "silicom-bypass-watchdog@att.service" in text


def test_soak_monitor_json_aggregate_units_external_mode(tmp_path: Path) -> None:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    ssh = shim_dir / "ssh"
    ssh.write_text(
        """#!/bin/bash
payload="$*"
if [[ "$payload" == *curl* ]]; then
    printf '%s\n' '{"status":"healthy","version":"test","uptime_seconds":1,"consecutive_failures":0,"source":"cake-autorate-state-bridge","wans":[{"download":{"state":"GREEN","qdisc_bandwidth":"x"},"upload":{"state":"GREEN","qdisc_bandwidth":"x"},"cake_signal":{"download":{}}}]}'
    exit 0
fi
if [[ "$payload" == *journalctl* ]]; then
    printf '0\n'
    exit 0
fi
if [[ "$payload" == *"systemctl is-active cake-autorate-"* ]]; then
    exit 0
fi
if [[ "$payload" == *"sudo -n python3"* ]]; then
    exit 1
fi
exit 0
""",
        encoding="utf-8",
    )
    ssh.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SOAK), "--json"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PATH": f"{shim_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    service_group = next(item for item in payload if item.get("service_group") == "all-claimed-services")
    units = service_group["units"]
    assert "cake-autorate-att.service" in units
    assert "cake-autorate-att-state-bridge.service" in units
    assert "silicom-bypass-watchdog@att.service" in units
    assert units.count("steering.service") == 1
    assert "wanctl@att.service" not in units


def test_soak_monitor_shellcheck_clean() -> None:
    if not shutil.which("shellcheck"):
        import pytest

        pytest.skip("shellcheck not installed")
    result = subprocess.run(
        ["shellcheck", "-S", "error", str(SOAK)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()

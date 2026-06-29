from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "phase231-migration-held.sh"


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_script_exists_and_exposes_required_checks_and_flags() -> None:
    text = script_text()

    assert "bridge_health" in text
    assert "metrics_ingestion" in text
    assert "no_sustained_errors" in text
    assert "qdisc_envelope" in text
    assert "--wan" in text
    assert "--json" in text
    assert "--window-hours" in text


def test_objective_c3_rule_and_utc_since_are_declared() -> None:
    text = script_text()

    assert "C3_MAX_TOTAL" in text
    assert "C3_MAX_DISTINCT_HOURS" in text
    assert "C3_CLEAN_TRAILING_HOURS" in text
    assert "2026-06-08 00:00:00 UTC" in text


def test_c3_unit_sets_cover_external_mode_superset() -> None:
    text = script_text()

    assert "silicom-bypass-watchdog@spectrum.service" in text
    assert "silicom-bypass-watchdog-cake-autorate-att.service" in text
    assert text.count("steering.service") >= 2


def test_envelope_values_are_parsed_from_repo_configs() -> None:
    text = script_text()

    assert "configs/cake-autorate/config.%s.sh" in text
    assert "min_dl_shaper_rate_kbps" in text
    assert "max_dl_shaper_rate_kbps" in text
    assert "base_ul_shaper_rate_kbps" in text
    assert "500000" not in text
    assert "600000" not in text
    assert "95000" not in text


def test_tc_bandwidth_unit_conversion_handles_expected_units() -> None:
    text = script_text()

    assert '"bit": 0.001' in text
    assert '"Kbit": 1' in text
    assert '"Mbit": 1000' in text
    assert '"Gbit": 1000000' in text


def test_timeout_flags_and_fail_closed_exit_are_present() -> None:
    text = script_text()

    assert "ConnectTimeout=10" in text
    assert "--max-time 10" in text
    assert re.search(r'exit_code=1', text)
    assert re.search(r'exit "\$exit_code"', text)


def test_remote_payloads_are_read_only() -> None:
    text = script_text()

    assert not re.search(r"systemctl\s+(start|stop|restart|enable|disable)", text)
    assert not re.search(r"tc\s+qdisc\s+(replace|add|del)", text)
    assert "sqlite3 -readonly" in text
    assert "SELECT COUNT(*) FROM metrics" in text
    assert "tc qdisc show" in text
    assert "journalctl -u" in text


def test_help_exits_without_network_access() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0
    assert "Read-only SOAK-01 evaluator" in result.stdout
    assert "ssh" not in result.stderr.lower()


def test_shellcheck_clean_if_available() -> None:
    if not shutil.which("shellcheck"):
        import pytest

        pytest.skip("shellcheck not installed")
    result = subprocess.run(
        ["shellcheck", "-S", "error", str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts/phase213-alert-window.sh"
DB = REPO_ROOT / "tests/fixtures/phase213/alerts-test.db"


def _expected_count(start: int, end: int) -> int:
    conn = sqlite3.connect(DB)
    try:
        return conn.execute("SELECT COUNT(*) FROM alerts WHERE timestamp BETWEEN ? AND ?", (start, end)).fetchone()[0]
    finally:
        conn.close()


def _run_local_db(tmp_path: Path, start: int, end: int) -> dict:
    if not SCRIPT.exists():
        pytest.skip("scripts/phase213-alert-window.sh not built yet")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--local-db", str(DB), "--start", str(start), "--end", str(end), "--output-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp_path / "alerts-spectrum.json").read_text())


def test_alert_window_local_db_window_a_returns_expected_rows(tmp_path: Path) -> None:
    payload = _run_local_db(tmp_path, 1717000000, 1717000060)
    assert set(payload.keys()) == {"wan", "db", "present", "rows", "summary"}
    assert len(payload["rows"]) == _expected_count(1717000000, 1717000060)
    assert sum(row["count"] for row in payload["summary"]) == len(payload["rows"])


def test_alert_window_local_db_window_b(tmp_path: Path) -> None:
    payload = _run_local_db(tmp_path, 1717000100, 1717000160)
    assert len(payload["rows"]) == _expected_count(1717000100, 1717000160)
    assert sum(row["count"] for row in payload["summary"]) == len(payload["rows"])


def test_alert_window_local_db_no_ssh_invoked() -> None:
    if not SCRIPT.exists():
        pytest.skip("scripts/phase213-alert-window.sh not built yet")
    source = SCRIPT.read_text()
    local_branch = source.split("--local-db", 1)[-1].split(";;", 1)[0]
    assert "ssh " not in local_branch

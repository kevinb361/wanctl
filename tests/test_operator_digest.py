"""Tests for wanctl operator digest mode."""

import json
import sqlite3
import sys
import time
from pathlib import Path

from wanctl.operator_summary import _format_digest_line, _query_digest_rows, main
from wanctl.storage.schema import ALERTS_SCHEMA


def _create_alerts_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(ALERTS_SCHEMA)
    now = int(time.time())
    conn.executemany(
        """
        INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                now - 3600,
                "hard_red_dl",
                "critical",
                "spectrum",
                json.dumps({"delta_ms": 82.5}),
            ),
            (
                now - 1800,
                "hard_red_ul",
                "critical",
                "spectrum",
                json.dumps({"delta_ms": 91.0}),
            ),
            (
                now - 900,
                "hard_red_dl",
                "critical",
                "spectrum",
                json.dumps({"delta_ms": 87.0}),
            ),
        ],
    )
    conn.commit()
    conn.close()


def test_format_digest_line_counts_events_and_range() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(ALERTS_SCHEMA)
    now = int(time.time())
    conn.executemany(
        """
        INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (now - 3600, "hard_red_dl", "critical", "spectrum", json.dumps({"delta_ms": 80.0})),
            (now - 1200, "hard_red_ul", "critical", "spectrum", json.dumps({"delta_ms": 95.0})),
            (now - 600, "hard_red_dl", "critical", "spectrum", json.dumps({"delta_ms": 88.0})),
        ],
    )

    rows = _query_digest_rows(conn)
    line = _format_digest_line("spectrum", rows)

    assert "spectrum: dl=2 ul=1" in line
    assert "range=" in line
    assert "peak_delta_ms=95.0" in line


def test_format_digest_line_zero_events_is_clean() -> None:
    assert _format_digest_line("att", []) == "att: no hard_red events in last 24h"


def test_main_digest_outputs_per_wan_summary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    db_path = tmp_path / "metrics-spectrum.db"
    _create_alerts_db(db_path)

    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_path],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    assert main() == 0
    output = capsys.readouterr().out

    assert "spectrum: dl=2 ul=1" in output
    assert "range=" in output
    assert "peak_delta_ms=91.0" in output

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


def _create_db_without_alerts_table(path: Path) -> None:
    """Create a DB that opens fine but lacks alerts, proving query errors bubble."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
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


def test_digest_skips_unreadable_db(tmp_path: Path, monkeypatch, capsys) -> None:
    """TOOL-03: one bad DB skips with stable prefix; good DBs still print."""
    good_db = tmp_path / "metrics-spectrum.db"
    _create_alerts_db(good_db)
    bad_db = tmp_path / "metrics-att.db"

    real_connect = sqlite3.connect

    def fake_connect(target, *args, **kwargs):
        target_str = str(target)
        if "metrics-att" in target_str:
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr("wanctl.operator_summary.sqlite3.connect", fake_connect)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [good_db, bad_db],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc == 0, "D-16: skipping unreadable DB is not a failure"
    captured = capsys.readouterr()
    assert "spectrum" in captured.out
    assert "operator-summary digest: skipped" in captured.err
    assert "wan=att" in captured.err
    assert "db=" in captured.err


def test_digest_all_unreadable_exits_zero_with_hint(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """TOOL-03 / D-16: every DB unreadable exits 0 with sudo hint."""
    db_a = tmp_path / "metrics-spectrum.db"
    db_b = tmp_path / "metrics-att.db"

    def fake_connect(target, *args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr("wanctl.operator_summary.sqlite3.connect", fake_connect)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_a, db_b],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "no readable WAN DBs - try sudo" in captured.err


def test_digest_skips_on_output_write_oserror(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """TOOL-03: one stdout OSError skips that line; remaining DBs still print."""
    good_db = tmp_path / "metrics-spectrum.db"
    bad_db = tmp_path / "metrics-att.db"
    _create_alerts_db(good_db)
    _create_alerts_db(bad_db)

    import builtins

    real_print = builtins.print
    state = {"failed_once": False}

    def fake_print(*args, file=None, **kwargs):
        if (file is None or file is sys.stdout) and not state["failed_once"]:
            state["failed_once"] = True
            raise OSError("disk full")
        return real_print(*args, file=file, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [good_db, bad_db],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc == 0, "one write succeeded → not a total failure"
    captured = capsys.readouterr()
    assert "operator-summary digest: skipped" in captured.err
    assert "(write)" in captured.err


def test_digest_missing_alerts_table_bubbles_not_skipped(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """TOOL-03 / codex HIGH: query-time OperationalError is not a skip."""
    db_path = tmp_path / "metrics-spectrum.db"
    _create_db_without_alerts_table(db_path)

    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_path],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc != 0, "schema corruption MUST surface as a real failure, not a skip"
    captured = capsys.readouterr()
    assert "operator-summary digest: skipped" not in captured.err, (
        f"missing-table case must NOT be classified as skip; stderr was: {captured.err!r}"
    )


def test_digest_all_writes_fail_emits_distinct_message(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """TOOL-03: readable DBs with no successful writes get distinct failure."""
    db_a = tmp_path / "metrics-spectrum.db"
    db_b = tmp_path / "metrics-att.db"
    _create_alerts_db(db_a)
    _create_alerts_db(db_b)

    import builtins

    real_print = builtins.print

    def fake_print(*args, file=None, **kwargs):
        if file is None or file is sys.stdout:
            raise OSError("disk full")
        return real_print(*args, file=file, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_a, db_b],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc == 1, "every output write failed → command-level failure"
    captured = capsys.readouterr()
    assert "operator-summary digest: all output writes failed" in captured.err
    assert "no readable WAN DBs" not in captured.err


def test_digest_discovery_oserror_caught(tmp_path: Path, monkeypatch, capsys) -> None:
    """TOOL-03: discover_wan_dbs() OSError gets stable discovery-failed prefix."""

    def fake_discover():
        raise OSError("permission denied scanning /var/lib/wanctl")

    monkeypatch.setattr("wanctl.operator_summary.discover_wan_dbs", fake_discover)
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    rc = main()
    assert rc == 1
    captured = capsys.readouterr()
    assert "operator-summary digest: discovery failed" in captured.err

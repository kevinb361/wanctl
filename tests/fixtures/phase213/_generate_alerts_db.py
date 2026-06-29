#!/usr/bin/env python3
"""Generate the Phase 213 synthetic alerts fixture DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from wanctl.storage.schema import create_tables

FIXTURE_DB = Path("tests/fixtures/phase213/alerts-test.db")


def main() -> None:
    FIXTURE_DB.parent.mkdir(parents=True, exist_ok=True)
    if FIXTURE_DB.exists():
        FIXTURE_DB.unlink()
    conn = sqlite3.connect(FIXTURE_DB)
    create_tables(conn)
    rows = [
        (1717000000, "cake_drop_high", "warning", "spectrum", '{"window":"A","sample":1}', "sent"),
        (1717000015, "flapping_dl", "warning", "spectrum", '{"window":"A","sample":2}', "sent"),
        (1717000030, "headroom_exhausted", "error", "att", '{"window":"A","sample":3}', "sent"),
        (1717000060, "cake_drop_high", "error", "att", '{"window":"A","sample":4}', "sent"),
        (1717000100, "cake_drop_high", "warning", "spectrum", '{"window":"B","sample":5}', "sent"),
        (1717000120, "flapping_dl", "error", "spectrum", '{"window":"B","sample":6}', "sent"),
        (1717000140, "headroom_exhausted", "warning", "att", '{"window":"B","sample":7}', "sent"),
        (1717000160, "flapping_dl", "warning", "att", '{"window":"B","sample":8}', "sent"),
    ]
    conn.executemany(
        """
        INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details, delivery_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()

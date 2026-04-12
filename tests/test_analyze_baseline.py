import sqlite3
from pathlib import Path

import pytest

from wanctl.storage.schema import create_tables


def _create_metrics_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    rows = [
        (1_700_000_000, "spectrum", "wanctl_cake_drop_rate", 1.0, '{"direction":"download"}', "raw"),
        (1_700_000_010, "spectrum", "wanctl_cake_drop_rate", 2.0, '{"direction":"upload"}', "raw"),
        (1_700_000_020, "spectrum", "wanctl_cake_backlog_bytes", 10.0, '{"direction":"download"}', "raw"),
        (1_700_000_030, "spectrum", "wanctl_cake_peak_delay_us", 20.0, '{"direction":"upload"}', "raw"),
        (1_700_000_040, "spectrum", "wanctl_state", 0.0, "", "raw"),
        (1_700_000_050, "spectrum", "wanctl_state", 1.0, "", "raw"),
    ]
    conn.executemany(
        """
        INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_module_exports_main_and_analyze_baseline() -> None:
    from wanctl.analyze_baseline import analyze_baseline, main

    assert callable(main)
    assert callable(analyze_baseline)


def test_main_help_exits_zero(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from wanctl.analyze_baseline import main

    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Analyze CAKE signal baseline" in captured.out


def test_analyze_baseline_returns_expected_structure(tmp_path: Path) -> None:
    from wanctl.analyze_baseline import analyze_baseline

    db_path = tmp_path / "metrics.db"
    _create_metrics_db(db_path)

    result = analyze_baseline(db_path, hours=24, wan="spectrum")

    assert result["hours"] == 24
    assert result["total_rows"] >= 1
    assert "summaries" in result
    assert "wanctl_cake_drop_rate" in result["summaries"]

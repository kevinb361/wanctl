import sqlite3
from pathlib import Path

import pytest

from wanctl.storage.schema import create_tables


def _create_metrics_db(db_path: Path, rows: list[tuple[int, str, str, float, str, str]]) -> None:
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    conn.executemany(
        """
        INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_discover_wan_dbs_returns_sorted_per_wan_files(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import discover_wan_dbs

    (tmp_path / "metrics-spectrum.db").touch()
    (tmp_path / "metrics-att.db").touch()

    result = discover_wan_dbs(tmp_path)

    assert result == [
        tmp_path / "metrics-att.db",
        tmp_path / "metrics-spectrum.db",
    ]


def test_discover_wan_dbs_falls_back_to_legacy_db(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import discover_wan_dbs

    legacy = tmp_path / "metrics.db"
    legacy.touch()

    assert discover_wan_dbs(tmp_path) == [legacy]


def test_discover_wan_dbs_returns_empty_when_nothing_found(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import discover_wan_dbs

    assert discover_wan_dbs(tmp_path) == []


def test_discover_wan_dbs_prefers_per_wan_files_over_legacy(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import discover_wan_dbs

    (tmp_path / "metrics-spectrum.db").touch()
    (tmp_path / "metrics-att.db").touch()
    (tmp_path / "metrics.db").touch()

    assert discover_wan_dbs(tmp_path) == [
        tmp_path / "metrics-att.db",
        tmp_path / "metrics-spectrum.db",
    ]


def test_query_all_wans_merges_rows_sorted_by_timestamp(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import query_all_wans
    from wanctl.storage.reader import query_metrics

    db_a = tmp_path / "metrics-spectrum.db"
    db_b = tmp_path / "metrics-att.db"
    _create_metrics_db(
        db_a,
        [(200, "spectrum", "wanctl_rtt_ms", 2.0, "", "raw")],
    )
    _create_metrics_db(
        db_b,
        [(100, "att", "wanctl_rtt_ms", 1.0, "", "raw")],
    )

    results = query_all_wans(query_metrics, db_paths=[db_a, db_b])

    assert [row["timestamp"] for row in results] == [100, 200]
    assert [row["wan_name"] for row in results] == ["att", "spectrum"]


def test_query_all_wans_continues_when_one_db_is_unreadable(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    from wanctl.storage.db_utils import query_all_wans
    from wanctl.storage.reader import query_metrics

    good_db = tmp_path / "metrics-spectrum.db"
    bad_db = tmp_path / "metrics-att.db"
    _create_metrics_db(
        good_db,
        [(100, "spectrum", "wanctl_rtt_ms", 1.0, "", "raw")],
    )
    bad_db.write_bytes(b"not sqlite")

    results = query_all_wans(query_metrics, db_paths=[good_db, bad_db])

    assert len(results) == 1
    assert results[0]["wan_name"] == "spectrum"
    assert "Failed to query metrics-att.db" in caplog.text


def test_query_all_wans_keeps_overlapping_timestamps_from_each_db(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import query_all_wans
    from wanctl.storage.reader import query_metrics

    db_a = tmp_path / "metrics-spectrum.db"
    db_b = tmp_path / "metrics-att.db"
    _create_metrics_db(
        db_a,
        [(100, "spectrum", "wanctl_rtt_ms", 1.0, "", "raw")],
    )
    _create_metrics_db(
        db_b,
        [(100, "att", "wanctl_rtt_ms", 2.0, "", "raw")],
    )

    results = query_all_wans(query_metrics, db_paths=[db_a, db_b])

    assert len(results) == 2
    assert {row["wan_name"] for row in results} == {"spectrum", "att"}


def test_history_main_with_explicit_db_skips_auto_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import wanctl.history as history

    db_path = tmp_path / "metrics.db"
    db_path.touch()

    def _discover_should_not_run() -> list[Path]:
        raise AssertionError("discover_wan_dbs should not run when --db is provided")

    monkeypatch.setattr(history, "discover_wan_dbs", _discover_should_not_run)
    monkeypatch.setattr(history, "_resolve_time_range", lambda _args: (0, 1))
    monkeypatch.setattr(history, "query_all_wans", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "sys.argv",
        ["wanctl-history", "--db", str(db_path), "--last", "1h"],
    )

    assert history.main() == 0


def test_query_all_wans_returns_empty_when_all_dbs_fail(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import query_all_wans
    from wanctl.storage.reader import query_metrics

    bad_a = tmp_path / "metrics-spectrum.db"
    bad_b = tmp_path / "metrics-att.db"
    bad_a.write_bytes(b"broken")
    bad_b.write_bytes(b"broken")

    assert query_all_wans(query_metrics, db_paths=[bad_a, bad_b]) == []


def test_query_all_wans_does_not_swallow_programmer_errors(tmp_path: Path) -> None:
    from wanctl.storage.db_utils import query_all_wans

    db_path = tmp_path / "metrics-spectrum.db"
    db_path.touch()

    def _buggy_query(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise TypeError("bug")

    with pytest.raises(TypeError, match="bug"):
        query_all_wans(_buggy_query, db_paths=[db_path])


def test_history_main_returns_one_when_no_databases_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import wanctl.history as history

    monkeypatch.setattr(history, "discover_wan_dbs", lambda: [])
    monkeypatch.setattr("sys.argv", ["wanctl-history", "--last", "1h"])

    assert history.main() == 1

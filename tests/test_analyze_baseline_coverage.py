from pathlib import Path

import pytest

from wanctl import analyze_baseline as mod


class _AllFailed(list):
    all_failed = True


def _cake_rows() -> list[dict[str, object]]:
    return [
        {"metric_name": "wanctl_cake_drop_rate", "labels": "direction=download", "value": 1.0},
        {"metric_name": "wanctl_cake_drop_rate", "labels": "direction=download", "value": 3.0},
        {"metric_name": "wanctl_cake_drop_rate", "labels": "direction=upload", "value": 2.0},
        {"metric_name": "wanctl_cake_total_drop_rate", "labels": "", "value": 4.0},
    ]


def test_analyze_baseline_empty_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "query_metrics", lambda **kwargs: [])

    result = mod.analyze_baseline(tmp_path / "metrics.db", hours=1, wan="att")

    assert result == {"error": "No CAKE metrics found", "rows": 0}


def test_check_detection_events_counts_transitions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        mod,
        "query_metrics",
        lambda **kwargs: [
            {"timestamp": 1, "value": 0.0},
            {"timestamp": 2, "value": 0.0},
            {"timestamp": 3, "value": 1.0},
            {"timestamp": 4, "value": 0.0},
        ],
    )

    result = mod.check_detection_events(tmp_path / "metrics.db", hours=1, wan="att")

    assert result["state_samples"] == 4
    assert result["state_transitions"] == 2
    assert len(result["events"]) == 4


def test_analyze_baseline_multi_db_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "query_all_wans", lambda *args, **kwargs: _cake_rows())

    result = mod._analyze_baseline_multi_db([Path("a.db"), Path("b.db")], hours=2, wan="att")

    assert result["hours"] == 2
    assert result["total_rows"] == 4
    summaries = result["summaries"]
    assert summaries["wanctl_cake_drop_rate"]["download"]["count"] == 2
    assert summaries["wanctl_cake_drop_rate"]["upload"]["count"] == 1
    assert summaries["wanctl_cake_total_drop_rate"]["unknown"]["count"] == 1


def test_analyze_baseline_multi_db_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "query_all_wans", lambda *args, **kwargs: [])

    result = mod._analyze_baseline_multi_db([Path("a.db")], hours=2, wan="att")

    assert result == {"error": "No CAKE metrics found", "rows": 0}


def test_analyze_baseline_multi_db_all_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "query_all_wans", lambda *args, **kwargs: _AllFailed())

    result = mod._analyze_baseline_multi_db([Path("a.db")], hours=2, wan="att")

    assert result == {
        "error": "All metrics databases failed to read",
        "rows": 0,
        "all_failed": True,
    }


def test_detection_events_multi_db_all_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "query_all_wans", lambda *args, **kwargs: _AllFailed())

    result = mod._check_detection_events_multi_db([Path("a.db")], hours=2, wan="att")

    assert result == {"error": "All metrics databases failed to read", "state_samples": 0}


def test_detection_events_multi_db_counts_and_limits_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"timestamp": i, "value": float(i % 2)} for i in range(12)]
    monkeypatch.setattr(mod, "query_all_wans", lambda *args, **kwargs: rows)

    result = mod._check_detection_events_multi_db([Path("a.db")], hours=2, wan="att")

    assert result["state_samples"] == 12
    assert result["state_transitions"] == 11
    assert result["events"] == rows[:10]


def test_main_errors_when_explicit_db_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    missing = tmp_path / "missing.db"
    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline", "--db", str(missing)])

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    assert f"ERROR: Database not found: {missing}" in capsys.readouterr().err


def test_main_errors_when_discovery_finds_no_databases(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline"])
    monkeypatch.setattr(mod, "discover_wan_dbs", lambda: [])

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    assert "ERROR: No metrics databases found" in capsys.readouterr().err


def test_main_prints_success_without_transitions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db_path = tmp_path / "metrics.db"
    db_path.touch()
    monkeypatch.setattr(
        "sys.argv",
        ["wanctl-analyze-baseline", "--db", str(db_path), "--hours", "3", "--wan", "att"],
    )
    monkeypatch.setattr(
        mod,
        "_analyze_baseline_multi_db",
        lambda *args, **kwargs: {
            "total_rows": 2,
            "summaries": {
                "metric": {
                    "download": {
                        "count": 2,
                        "avg": 1.5,
                        "p50": 1.5,
                        "p99": 1.99,
                        "min": 1.0,
                        "max": 2.0,
                    },
                    "upload": {"count": 1},
                }
            },
        },
    )
    monkeypatch.setattr(
        mod,
        "_check_detection_events_multi_db",
        lambda *args, **kwargs: {"state_samples": 2, "state_transitions": 0, "events": []},
    )

    mod.main()

    output = capsys.readouterr().out
    assert "Database:" in output
    assert "WAN filter: att" in output
    assert "avg=1.5000" in output
    assert "avg=N/A" in output
    assert "PASS: No state transitions" in output


def test_main_prints_discovered_dbs_and_transition_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline"])
    monkeypatch.setattr(mod, "discover_wan_dbs", lambda: [Path("a.db"), Path("b.db")])
    monkeypatch.setattr(
        mod,
        "_analyze_baseline_multi_db",
        lambda *args, **kwargs: {"total_rows": 1, "summaries": {}},
    )
    monkeypatch.setattr(
        mod,
        "_check_detection_events_multi_db",
        lambda *args, **kwargs: {
            "state_samples": 2,
            "state_transitions": 1,
            "events": [{"timestamp": 123, "value": 1.0}],
        },
    )

    mod.main()

    output = capsys.readouterr().out
    assert "Databases: a.db, b.db" in output
    assert "WARNING: State transitions" in output
    assert "ts=123 value=1.0" in output


def test_main_exits_on_baseline_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db_path = tmp_path / "metrics.db"
    db_path.touch()
    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline", "--db", str(db_path)])
    monkeypatch.setattr(
        mod,
        "_analyze_baseline_multi_db",
        lambda *args, **kwargs: {"error": "nope"},
    )

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    assert "ERROR: nope" in capsys.readouterr().out


def test_main_exits_on_events_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db_path = tmp_path / "metrics.db"
    db_path.touch()
    monkeypatch.setattr("sys.argv", ["wanctl-analyze-baseline", "--db", str(db_path)])
    monkeypatch.setattr(
        mod,
        "_analyze_baseline_multi_db",
        lambda *args, **kwargs: {"total_rows": 1, "summaries": {}},
    )
    monkeypatch.setattr(
        mod,
        "_check_detection_events_multi_db",
        lambda *args, **kwargs: {"error": "events failed"},
    )

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    assert "ERROR: events failed" in capsys.readouterr().out

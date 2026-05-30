"""Phase 219 Wave 0 tests for bucketed ingestion-rate history output."""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

from wanctl.history import main
from wanctl.storage.writer import MetricsWriter


BASE_TS = 1767225600
METRIC_NAMES = (
    "wanctl_rtt_ms",
    "wanctl_state",
    "wanctl_signal_jitter_ms",
    "wanctl_cake_drop_rate",
)
ROW_FIELD_SET = {
    "wan_name",
    "wan_db",
    "table_name",
    "window_seconds",
    "row_count",
    "rows_per_sec",
    "_snapshot_unix",
    "_snapshot_age_sec",
}


class TestIngestionRateBucketed:
    """Golden JSON pins for the Phase 219 ingestion-rate envelope."""

    def _ts_arg(self, ts: int) -> str:
        return datetime.fromtimestamp(ts).isoformat()

    def _seed_metrics(
        self,
        db_path: Path,
        *,
        wan_name: str = "spectrum",
        seconds: int = 60,
    ) -> None:
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path=db_path)
        for metric_name in METRIC_NAMES:
            for i in range(seconds):
                writer.write_metric(
                    timestamp=BASE_TS + i,
                    wan_name=wan_name,
                    metric_name=metric_name,
                    value=1.0,
                )
        writer.close()
        MetricsWriter._reset_instance()

    def _run_history(
        self,
        monkeypatch: pytest.MonkeyPatch,
        db_path: Path,
        *extra_args: str,
        to_ts: int = BASE_TS + 60,
    ) -> None:
        monkeypatch.setattr("wanctl.history.time.time", lambda: float(to_ts))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wanctl-history",
                "--ingestion-rate",
                *extra_args,
                "--json",
                "--from",
                self._ts_arg(BASE_TS),
                "--to",
                self._ts_arg(to_ts),
                "--db",
                str(db_path),
            ],
        )

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_schema_version_pinned(self, tmp_path, monkeypatch, capsys):
        """New-mode JSON pins schema_version=1 and deterministic snapshots."""
        db_path = tmp_path / "metrics-spectrum.db"
        self._seed_metrics(db_path)
        self._run_history(monkeypatch, db_path, "--by-table")

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["rows"], list)
        assert len(payload["rows"]) == 4
        for row in payload["rows"]:
            assert set(row) == ROW_FIELD_SET
            assert row["_snapshot_unix"] == BASE_TS + 60
            assert row["wan_name"] == "spectrum"
            assert row["row_count"] == 60
            assert row["window_seconds"] == 60

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_by_table_emits_per_metric_row(self, tmp_path, monkeypatch, capsys):
        """--by-table emits one non-null table_name row per metric_name."""
        db_path = tmp_path / "metrics-spectrum.db"
        self._seed_metrics(db_path)
        self._run_history(monkeypatch, db_path, "--by-table")

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        rows = payload["rows"]
        assert all(row["table_name"] is not None for row in rows)
        assert {row["table_name"] for row in rows} == set(METRIC_NAMES)
        assert all(row["row_count"] == 60 for row in rows)

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_rolling_emits_one_row_per_window(self, tmp_path, monkeypatch, capsys):
        """--rolling without --by-table emits one row per requested window."""
        db_path = tmp_path / "metrics-spectrum.db"
        self._seed_metrics(db_path, seconds=600)
        self._run_history(
            monkeypatch,
            db_path,
            "--rolling=60,300",
            to_ts=BASE_TS + 600,
        )

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["rows"]) == 2
        assert {row["window_seconds"] for row in payload["rows"]} == {60, 300}

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_by_table_and_rolling_cartesian(self, tmp_path, monkeypatch, capsys):
        """--by-table plus --rolling emits metric_name x window rows."""
        db_path = tmp_path / "metrics-spectrum.db"
        self._seed_metrics(db_path, seconds=600)
        self._run_history(
            monkeypatch,
            db_path,
            "--by-table",
            "--rolling=60,300",
            to_ts=BASE_TS + 600,
        )

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["rows"]) == 8
        pairs = {(row["table_name"], row["window_seconds"]) for row in payload["rows"]}
        assert pairs == {(metric_name, window) for metric_name in METRIC_NAMES for window in (60, 300)}

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_per_db_read_failure_emits_null_row(self, tmp_path, monkeypatch, capsys):
        """Per-DB-level null, NOT per-metric-level null, on DB read failure."""
        spectrum_db = tmp_path / "metrics-spectrum.db"
        att_db = tmp_path / "metrics-att.db"
        self._seed_metrics(spectrum_db, wan_name="spectrum")
        self._seed_metrics(att_db, wan_name="att")
        real_connect = sqlite3.connect

        def flaky_connect(db_uri, *args, **kwargs):
            if str(spectrum_db) in str(db_uri):
                raise sqlite3.DatabaseError("synthetic spectrum read failure")
            return real_connect(db_uri, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", flaky_connect)
        monkeypatch.setattr("wanctl.history.time.time", lambda: float(BASE_TS + 60))
        monkeypatch.setattr("wanctl.history.discover_wan_dbs", lambda: [spectrum_db, att_db])
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wanctl-history",
                "--ingestion-rate",
                "--by-table",
                "--json",
                "--from",
                self._ts_arg(BASE_TS),
                "--to",
                self._ts_arg(BASE_TS + 60),
            ],
        )

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        spectrum_rows = [row for row in payload["rows"] if row["wan_name"] == "spectrum"]
        att_rows = [row for row in payload["rows"] if row["wan_name"] == "att"]
        assert spectrum_rows == [
            {
                "wan_name": "spectrum",
                "wan_db": str(spectrum_db),
                "table_name": None,
                "window_seconds": 60,
                "row_count": None,
                "rows_per_sec": None,
                "_snapshot_unix": BASE_TS + 60,
                "_snapshot_age_sec": 0,
            }
        ]
        assert len(att_rows) == 4
        assert all(row["row_count"] is not None for row in att_rows)

    @pytest.mark.xfail(reason="Wave 1 helper not yet implemented", strict=False)
    def test_default_mode_back_compat_v1_44_envelope(self, tmp_path, monkeypatch, capsys):
        """Default --ingestion-rate --json keeps the v1.44 envelope per D-17."""
        db_path = tmp_path / "metrics-spectrum.db"
        self._seed_metrics(db_path)
        self._run_history(monkeypatch, db_path)

        assert main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {"window", "generated_at", "totals", "wans"}
        assert "schema_version" not in payload
        assert "rows" not in payload
        assert isinstance(payload["wans"], list)
        assert len(payload["wans"]) == 1

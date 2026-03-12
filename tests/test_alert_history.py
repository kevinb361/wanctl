"""Tests for alert history query and CLI --alerts flag."""

import json
import sqlite3
import sys
from datetime import datetime

import pytest

from wanctl.storage.reader import query_alerts
from wanctl.storage.schema import create_tables

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def alert_db(tmp_path):
    """Create a temporary database with alerts test data."""
    db_path = tmp_path / "test_alerts.db"
    conn = sqlite3.connect(str(db_path))
    create_tables(conn)

    now = int(datetime.now().timestamp())

    # Insert test alerts
    alerts = [
        (
            now - 3600,
            "congestion_sustained",
            "warning",
            "spectrum",
            '{"direction": "download", "zone": "SOFT_RED"}',
            "delivered",
        ),
        (
            now - 1800,
            "congestion_sustained",
            "critical",
            "spectrum",
            '{"direction": "download", "zone": "RED"}',
            "delivered",
        ),
        (
            now - 900,
            "congestion_recovered",
            "recovery",
            "spectrum",
            '{"direction": "download", "duration_sec": 900}',
            "delivered",
        ),
        (
            now - 600,
            "steering_activated",
            "warning",
            "spectrum",
            '{"reason": "congestion"}',
            "pending",
        ),
        (
            now - 300,
            "connectivity_offline",
            "critical",
            "att",
            '{"consecutive_failures": 5}',
            "failed",
        ),
    ]
    for ts, atype, sev, wan, details, status in alerts:
        conn.execute(
            "INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details, delivery_status) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, atype, sev, wan, details, status),
        )
    conn.commit()
    conn.close()

    return db_path, now


# =============================================================================
# query_alerts() UNIT TESTS
# =============================================================================


class TestQueryAlerts:
    """Tests for query_alerts() function in reader.py."""

    def test_returns_list_of_dicts_with_all_fields(self, alert_db):
        """query_alerts() returns list of dicts with id, timestamp, alert_type, severity, wan_name, details, delivery_status."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path)
        assert isinstance(results, list)
        assert len(results) == 5
        row = results[0]
        assert "id" in row
        assert "timestamp" in row
        assert "alert_type" in row
        assert "severity" in row
        assert "wan_name" in row
        assert "details" in row
        assert "delivery_status" in row

    def test_filters_by_start_ts_and_end_ts(self, alert_db):
        """query_alerts() filters by start_ts and end_ts."""
        db_path, now = alert_db
        # Only get alerts from last 1000 seconds
        results = query_alerts(db_path=db_path, start_ts=now - 1000, end_ts=now)
        # Should include alerts at -900, -600, -300 but not -3600, -1800
        assert len(results) == 3

    def test_filters_by_alert_type(self, alert_db):
        """query_alerts() filters by alert_type."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, alert_type="congestion_sustained")
        assert len(results) == 2
        for r in results:
            assert r["alert_type"] == "congestion_sustained"

    def test_filters_by_wan_name(self, alert_db):
        """query_alerts() filters by wan_name."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, wan="att")
        assert len(results) == 1
        assert results[0]["wan_name"] == "att"

    def test_returns_empty_list_for_missing_database(self, tmp_path):
        """query_alerts() returns empty list for missing database."""
        db_path = tmp_path / "nonexistent.db"
        results = query_alerts(db_path=db_path)
        assert results == []

    def test_returns_empty_list_for_empty_table(self, tmp_path):
        """query_alerts() returns empty list for empty table."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)
        conn.close()
        results = query_alerts(db_path=db_path)
        assert results == []

    def test_orders_by_timestamp_desc(self, alert_db):
        """query_alerts() orders by timestamp DESC (newest first)."""
        db_path, now = alert_db
        results = query_alerts(db_path=db_path)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_parses_details_json_into_dict(self, alert_db):
        """query_alerts() parses details JSON string into dict."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, alert_type="congestion_sustained")
        # Should be parsed from JSON string to dict
        for r in results:
            assert isinstance(r["details"], dict)
            assert "direction" in r["details"]


# =============================================================================
# CLI --alerts FLAG TESTS
# =============================================================================


class TestAlertsCLI:
    """Tests for --alerts CLI flag in history.py."""

    def test_alerts_flag_triggers_alert_query_mode(self, alert_db, monkeypatch, capsys):
        """CLI --alerts flag triggers alert query mode (not metrics)."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "2h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        # Should show alert-specific columns, not metric columns
        assert "Type" in captured.out
        assert "Severity" in captured.out

    def test_alerts_last_1h_filters_by_time_range(self, alert_db, monkeypatch, capsys):
        """CLI --alerts --last 1h filters alerts by time range."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "1h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        # Alerts at -3600 is exactly at boundary, -1800 is within
        # Should have some alerts (those within 1h)
        assert (
            "congestion" in captured.out.lower()
            or "steering" in captured.out.lower()
            or "connectivity" in captured.out.lower()
        )

    def test_alerts_json_output(self, alert_db, monkeypatch, capsys):
        """CLI --alerts --json outputs JSON array of alert records."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys,
            "argv",
            ["wanctl-history", "--alerts", "--last", "2h", "--json", "--db", str(db_path)],
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "alert_type" in data[0]
        assert "severity" in data[0]

    def test_alerts_no_results_message(self, tmp_path, monkeypatch, capsys):
        """CLI --alerts with no results prints 'No alerts found' message."""
        from wanctl.history import main

        # Create empty DB with tables
        db_path = tmp_path / "empty_alerts.db"
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)
        conn.close()

        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "1h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "No alerts found" in captured.out

    def test_alerts_table_format_columns(self, alert_db, monkeypatch, capsys):
        """CLI --alerts table format shows Timestamp, Type, Severity, WAN, Details columns."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "2h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "Timestamp" in captured.out
        assert "Type" in captured.out
        assert "Severity" in captured.out
        assert "WAN" in captured.out
        assert "Details" in captured.out

"""Tests for query_tuning_params() in storage/reader.py."""

import sqlite3

import pytest

from wanctl.storage.schema import TUNING_PARAMS_SCHEMA


SAMPLE_ROWS = [
    # (timestamp, wan_name, parameter, old_value, new_value, confidence, rationale, data_points, reverted)
    (100, "Spectrum", "target_bloat_ms", 5.0, 5.5, 0.85, "p50 shift", 1440, 0),
    (200, "ATT", "target_bloat_ms", 4.0, 4.3, 0.78, "p50 drift", 1200, 0),
    (300, "Spectrum", "fusion_icmp_weight", 0.7, 0.65, 0.91, "IRTT more stable", 800, 0),
]


def _create_test_db(tmp_path, rows):
    """Create a test database with tuning_params rows."""
    db_path = tmp_path / "test_metrics.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(TUNING_PARAMS_SCHEMA)
    for row in rows:
        conn.execute(
            "INSERT INTO tuning_params "
            "(timestamp, wan_name, parameter, old_value, new_value, confidence, rationale, data_points, reverted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    conn.commit()
    conn.close()
    return db_path


class TestQueryTuningParams:
    """Tests for query_tuning_params reader function."""

    def test_returns_empty_no_db(self, tmp_path):
        """Nonexistent database path returns empty list."""
        from wanctl.storage.reader import query_tuning_params

        result = query_tuning_params(db_path=tmp_path / "nonexistent.db")
        assert result == []

    def test_returns_all_records(self, tmp_path):
        """Query with no filters returns all rows."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path)
        assert len(result) == 3

    def test_filters_by_wan(self, tmp_path):
        """Filter by wan name returns only matching rows."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path, wan="Spectrum")
        assert len(result) == 2
        assert all(r["wan_name"] == "Spectrum" for r in result)

    def test_filters_by_time_range(self, tmp_path):
        """Filter by start_ts and end_ts returns only matching rows."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path, start_ts=150, end_ts=250)
        assert len(result) == 1
        assert result[0]["timestamp"] == 200

    def test_filters_by_parameter(self, tmp_path):
        """Filter by parameter name returns only matching rows."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path, parameter="fusion_icmp_weight")
        assert len(result) == 1
        assert result[0]["parameter"] == "fusion_icmp_weight"

    def test_order_desc(self, tmp_path):
        """Results are ordered by timestamp descending."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path)
        timestamps = [r["timestamp"] for r in result]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_dict_keys(self, tmp_path):
        """Each result dict has all expected keys."""
        from wanctl.storage.reader import query_tuning_params

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        result = query_tuning_params(db_path=db_path)
        expected_keys = {
            "id",
            "timestamp",
            "wan_name",
            "parameter",
            "old_value",
            "new_value",
            "confidence",
            "rationale",
            "data_points",
            "reverted",
        }
        for r in result:
            assert set(r.keys()) == expected_keys

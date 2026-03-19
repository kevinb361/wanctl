"""Tests for --tuning flag and tuning formatters in history.py."""

import json
import sqlite3
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

from wanctl.storage.schema import TUNING_PARAMS_SCHEMA


SAMPLE_ROWS = [
    # (timestamp, wan_name, parameter, old_value, new_value, confidence, rationale, data_points, reverted)
    (1700000000, "Spectrum", "target_bloat_ms", 5.0, 5.5, 0.85, "p50 shift detected", 1440, 0),
    (1700003600, "ATT", "fusion_icmp_weight", 0.7, 0.65, 0.91, "IRTT more stable", 800, 0),
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


# =============================================================================
# FORMAT TUNING TABLE TESTS
# =============================================================================


class TestFormatTuningTable:
    """Tests for format_tuning_table formatter."""

    def test_formats_table_with_headers(self):
        """Table output contains expected column headers."""
        from wanctl.history import format_tuning_table

        records = [
            {
                "timestamp": 1700000000,
                "parameter": "target_bloat_ms",
                "old_value": 5.0,
                "new_value": 5.5,
                "wan_name": "Spectrum",
                "confidence": 0.85,
                "rationale": "p50 shift",
                "reverted": 0,
            },
            {
                "timestamp": 1700003600,
                "parameter": "fusion_icmp_weight",
                "old_value": 0.7,
                "new_value": 0.65,
                "wan_name": "ATT",
                "confidence": 0.91,
                "rationale": "IRTT stable",
                "reverted": 0,
            },
        ]
        output = format_tuning_table(records)
        assert "Timestamp" in output
        assert "Parameter" in output
        assert "Old" in output
        assert "New" in output
        assert "WAN" in output
        assert "Rationale" in output

    def test_reverted_row_marked(self):
        """Reverted records show [REVERT] indicator."""
        from wanctl.history import format_tuning_table

        records = [
            {
                "timestamp": 1700000000,
                "parameter": "target_bloat_ms",
                "old_value": 5.5,
                "new_value": 5.0,
                "wan_name": "Spectrum",
                "confidence": 1.0,
                "rationale": "congestion rate exceeded",
                "reverted": 1,
            },
        ]
        output = format_tuning_table(records)
        assert "REVERT" in output

    def test_truncates_long_rationale(self):
        """Rationale longer than 60 chars is truncated with ellipsis."""
        from wanctl.history import format_tuning_table

        long_rationale = "x" * 80
        records = [
            {
                "timestamp": 1700000000,
                "parameter": "target_bloat_ms",
                "old_value": 5.0,
                "new_value": 5.5,
                "wan_name": "Spectrum",
                "confidence": 0.85,
                "rationale": long_rationale,
                "reverted": 0,
            },
        ]
        output = format_tuning_table(records)
        assert "..." in output
        # Full 80-char string should NOT appear
        assert long_rationale not in output


# =============================================================================
# FORMAT TUNING JSON TESTS
# =============================================================================


class TestFormatTuningJson:
    """Tests for format_tuning_json formatter."""

    def test_valid_json(self):
        """Output is valid JSON parseable by json.loads."""
        from wanctl.history import format_tuning_json

        records = [
            {
                "timestamp": 1700000000,
                "parameter": "target_bloat_ms",
                "old_value": 5.0,
                "new_value": 5.5,
                "wan_name": "Spectrum",
                "confidence": 0.85,
                "rationale": "p50 shift",
                "data_points": 1440,
                "reverted": 0,
            },
        ]
        output = format_tuning_json(records)
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_includes_timestamp_iso(self):
        """Output includes timestamp_iso key with ISO format."""
        from wanctl.history import format_tuning_json

        records = [
            {
                "timestamp": 1700000000,
                "parameter": "target_bloat_ms",
                "old_value": 5.0,
                "new_value": 5.5,
                "wan_name": "Spectrum",
                "confidence": 0.85,
                "rationale": "p50 shift",
                "data_points": 1440,
                "reverted": 0,
            },
        ]
        output = format_tuning_json(records)
        parsed = json.loads(output)
        assert "timestamp_iso" in parsed[0]
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(parsed[0]["timestamp_iso"])


# =============================================================================
# --TUNING FLAG TESTS
# =============================================================================


class TestTuningFlag:
    """Tests for --tuning CLI flag integration."""

    def test_parser_has_tuning_flag(self):
        """create_parser() produces parser that accepts --tuning."""
        from wanctl.history import create_parser

        parser = create_parser()
        args = parser.parse_args(["--tuning"])
        assert args.tuning is True

    def test_tuning_no_results(self, tmp_path, capsys):
        """--tuning with empty db prints informative message."""
        from wanctl.history import main

        # Create empty db with tuning_params table
        db_path = _create_test_db(tmp_path, [])
        with patch("sys.argv", ["wanctl-history", "--tuning", "--db", str(db_path)]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "No tuning adjustments found" in captured.out

    def test_tuning_with_results(self, tmp_path, capsys):
        """--tuning with data prints table output."""
        from wanctl.history import main

        db_path = _create_test_db(tmp_path, SAMPLE_ROWS)
        with patch(
            "sys.argv",
            ["wanctl-history", "--tuning", "--last", "99999d", "--db", str(db_path)],
        ):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "target_bloat_ms" in captured.out
        assert "Spectrum" in captured.out

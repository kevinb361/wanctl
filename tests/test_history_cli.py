"""Tests for wanctl-history CLI tool."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from wanctl.history import (
    create_parser,
    format_summary,
    format_table,
    format_timestamp,
    format_value,
    main,
    parse_duration,
    parse_timestamp,
)
from wanctl.storage.writer import MetricsWriter

# =============================================================================
# DURATION PARSING TESTS
# =============================================================================


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_parse_duration_seconds(self):
        """Seconds (s) are parsed correctly."""
        assert parse_duration("30s") == timedelta(seconds=30)

    def test_parse_duration_minutes(self):
        """Minutes (m) are parsed correctly."""
        assert parse_duration("30m") == timedelta(minutes=30)

    def test_parse_duration_hours(self):
        """Hours (h) are parsed correctly."""
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("24h") == timedelta(hours=24)

    def test_parse_duration_days(self):
        """Days (d) are parsed correctly."""
        assert parse_duration("7d") == timedelta(days=7)

    def test_parse_duration_weeks(self):
        """Weeks (w) are parsed correctly."""
        assert parse_duration("2w") == timedelta(weeks=2)

    def test_parse_duration_case_insensitive(self):
        """Duration parsing is case insensitive."""
        assert parse_duration("1H") == timedelta(hours=1)
        assert parse_duration("7D") == timedelta(days=7)

    def test_parse_duration_invalid_raises(self):
        """Invalid duration format raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid duration"):
            parse_duration("invalid")

    def test_parse_duration_missing_unit_raises(self):
        """Duration without unit raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid duration"):
            parse_duration("30")

    def test_parse_duration_invalid_unit_raises(self):
        """Duration with invalid unit raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid duration"):
            parse_duration("30x")


# =============================================================================
# TIMESTAMP PARSING TESTS
# =============================================================================


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_timestamp_iso8601(self):
        """ISO 8601 format is parsed correctly."""
        ts = parse_timestamp("2026-01-25T14:30:00")
        expected = datetime(2026, 1, 25, 14, 30, 0)
        assert ts == int(expected.timestamp())

    def test_parse_timestamp_datetime_format(self):
        """YYYY-MM-DD HH:MM format is parsed correctly."""
        ts = parse_timestamp("2026-01-25 14:30")
        expected = datetime(2026, 1, 25, 14, 30, 0)
        assert ts == int(expected.timestamp())

    def test_parse_timestamp_datetime_with_seconds(self):
        """YYYY-MM-DD HH:MM:SS format is parsed correctly."""
        ts = parse_timestamp("2026-01-25 14:30:45")
        expected = datetime(2026, 1, 25, 14, 30, 45)
        assert ts == int(expected.timestamp())

    def test_parse_timestamp_invalid_raises(self):
        """Invalid timestamp format raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid timestamp"):
            parse_timestamp("not-a-timestamp")

    def test_parse_timestamp_invalid_date_raises(self):
        """Invalid date raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid timestamp"):
            parse_timestamp("2026-13-45 25:99")


# =============================================================================
# OUTPUT FORMATTING TESTS
# =============================================================================


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_format_timestamp_local_time(self):
        """Timestamps are formatted in local time."""
        # Create a known timestamp
        dt = datetime(2026, 1, 25, 14, 32, 5)
        ts = int(dt.timestamp())
        result = format_timestamp(ts)
        assert result == "2026-01-25 14:32:05"


class TestFormatValue:
    """Tests for format_value function."""

    def test_format_value_integer(self):
        """Integer values have no decimal places."""
        assert format_value(25.0) == "25"

    def test_format_value_simple_decimal(self):
        """Simple decimals are preserved."""
        assert format_value(25.5) == "25.5"

    def test_format_value_trailing_zeros_removed(self):
        """Trailing zeros are removed."""
        assert format_value(25.100) == "25.1"

    def test_format_value_precision_limited(self):
        """Precision is limited to 3 decimal places."""
        assert format_value(25.12345) == "25.123"

    def test_format_value_small_decimal(self):
        """Small decimals are handled correctly."""
        assert format_value(0.123) == "0.123"


class TestFormatTable:
    """Tests for format_table function."""

    def test_table_output_has_headers(self):
        """Table output includes headers."""
        results = [
            {
                "timestamp": 1737830000,
                "metric_name": "wanctl_rtt_ms",
                "value": 15.5,
                "wan_name": "spectrum",
                "labels": None,
                "granularity": "raw",
            }
        ]
        table = format_table(results)
        assert "Timestamp" in table
        assert "Metric" in table
        assert "Value" in table

    def test_verbose_adds_extra_columns(self):
        """Verbose mode adds wan, labels, granularity columns."""
        results = [
            {
                "timestamp": 1737830000,
                "metric_name": "wanctl_rtt_ms",
                "value": 15.5,
                "wan_name": "spectrum",
                "labels": "test=1",
                "granularity": "raw",
            }
        ]
        table = format_table(results, verbose=True)
        assert "WAN" in table
        assert "Labels" in table
        assert "Granularity" in table
        assert "spectrum" in table
        assert "test=1" in table
        assert "raw" in table

    def test_table_formats_values_correctly(self):
        """Table formats timestamps and values correctly."""
        results = [
            {
                "timestamp": 1737830000,
                "metric_name": "wanctl_rtt_ms",
                "value": 15.5,
                "wan_name": "spectrum",
                "labels": None,
                "granularity": "raw",
            }
        ]
        table = format_table(results)
        assert "wanctl_rtt_ms" in table
        assert "15.5" in table


class TestFormatSummary:
    """Tests for format_summary function."""

    def test_summary_output_shows_statistics(self):
        """Summary output shows min/max/avg/p50/p95/p99."""
        results = [
            {"metric_name": "wanctl_rtt_ms", "value": 10.0},
            {"metric_name": "wanctl_rtt_ms", "value": 20.0},
            {"metric_name": "wanctl_rtt_ms", "value": 30.0},
        ]
        summary = format_summary(results)
        assert "min:" in summary
        assert "max:" in summary
        assert "avg:" in summary
        assert "p50:" in summary
        assert "p95:" in summary
        assert "p99:" in summary

    def test_summary_groups_by_metric(self):
        """Summary groups results by metric name."""
        results = [
            {"metric_name": "wanctl_rtt_ms", "value": 10.0},
            {"metric_name": "wanctl_rate_mbps", "value": 100.0},
        ]
        summary = format_summary(results)
        assert "wanctl_rtt_ms" in summary
        assert "wanctl_rate_mbps" in summary

    def test_state_summary_shows_percentages(self):
        """State metrics show percentage distribution."""
        results = [
            {"metric_name": "wanctl_state", "value": 1.0},  # GREEN
            {"metric_name": "wanctl_state", "value": 1.0},  # GREEN
            {"metric_name": "wanctl_state", "value": 2.0},  # YELLOW
        ]
        summary = format_summary(results)
        assert "GREEN" in summary
        assert "YELLOW" in summary
        # 2 out of 3 are GREEN = 66.7%
        assert "66.7%" in summary

    def test_summary_shows_sample_count(self):
        """Summary shows number of samples per metric."""
        results = [
            {"metric_name": "wanctl_rtt_ms", "value": 10.0},
            {"metric_name": "wanctl_rtt_ms", "value": 20.0},
        ]
        summary = format_summary(results)
        assert "2 samples" in summary


# =============================================================================
# ARGUMENT PARSER TESTS
# =============================================================================


class TestArgumentParser:
    """Tests for argument parser configuration."""

    def test_default_time_range_is_1h(self, monkeypatch):
        """Default time range is 1 hour when no args provided."""
        parser = create_parser()
        args = parser.parse_args([])
        # No --last provided means None
        assert args.last is None
        assert args.from_ts is None
        assert args.to_ts is None
        # main() applies default 1h when all are None

    def test_last_argument_parsed(self):
        """--last argument is parsed as duration."""
        parser = create_parser()
        args = parser.parse_args(["--last", "2h"])
        assert args.last == timedelta(hours=2)

    def test_from_to_arguments_parsed(self):
        """--from and --to arguments are parsed as timestamps."""
        parser = create_parser()
        args = parser.parse_args([
            "--from", "2026-01-25 14:00",
            "--to", "2026-01-25 15:00"
        ])
        assert args.from_ts is not None
        assert args.to_ts is not None

    def test_metrics_filter_argument(self):
        """--metrics argument is stored as string."""
        parser = create_parser()
        args = parser.parse_args(["--metrics", "wanctl_rtt_ms,wanctl_state"])
        assert args.metrics == "wanctl_rtt_ms,wanctl_state"

    def test_wan_filter_argument(self):
        """--wan argument is stored correctly."""
        parser = create_parser()
        args = parser.parse_args(["--wan", "spectrum"])
        assert args.wan == "spectrum"

    def test_json_flag(self):
        """--json flag is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["--json"])
        assert args.json_output is True

    def test_summary_flag(self):
        """--summary flag is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["--summary"])
        assert args.summary is True

    def test_verbose_flag(self):
        """-v/--verbose flag is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True


# =============================================================================
# INTEGRATION TESTS WITH TEMP DATABASE
# =============================================================================


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with test data."""
    db_path = tmp_path / "test_metrics.db"

    # Reset singleton to ensure we use the new path
    MetricsWriter._reset_instance()

    # Create writer and populate with test data
    writer = MetricsWriter(db_path=db_path)

    # Add recent data (within last hour)
    now = int(datetime.now().timestamp())
    for i in range(10):
        ts = now - (i * 60)  # Every minute
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=15.0 + i,
        )
        writer.write_metric(
            timestamp=ts,
            wan_name="spectrum",
            metric_name="wanctl_state",
            value=1.0,  # GREEN
        )

    # Add data for different WAN
    for i in range(5):
        ts = now - (i * 60)
        writer.write_metric(
            timestamp=ts,
            wan_name="att",
            metric_name="wanctl_rtt_ms",
            value=25.0 + i,
        )

    writer.close()

    yield db_path

    # Clean up singleton after test
    MetricsWriter._reset_instance()


class TestIntegration:
    """Integration tests with temporary database."""

    def test_query_last_1h_returns_recent_data(self, temp_db):
        """Query with --last 1h returns recent data."""
        result = subprocess.run(
            [sys.executable, "-m", "wanctl.history", "--last", "1h", "--db", str(temp_db)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "wanctl_rtt_ms" in result.stdout
        assert "wanctl_state" in result.stdout

    def test_query_with_metrics_filter(self, temp_db):
        """Query with --metrics filter returns only specified metrics."""
        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--metrics", "wanctl_rtt_ms",
                "--db", str(temp_db),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "wanctl_rtt_ms" in result.stdout
        assert "wanctl_state" not in result.stdout

    def test_query_with_wan_filter(self, temp_db):
        """Query with --wan filter returns only specified WAN."""
        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--wan", "att",
                "--db", str(temp_db),
                "-v",  # Need verbose to see WAN column
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "att" in result.stdout
        # Should not have spectrum-only metrics (state was only for spectrum)
        lines = result.stdout.strip().split("\n")
        # All data lines should have att
        for line in lines[2:]:  # Skip header lines
            if line.strip():
                assert "spectrum" not in line

    def test_json_output_is_valid_json(self, temp_db):
        """JSON output is valid JSON."""
        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--json",
                "--db", str(temp_db),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "timestamp" in data[0]
        assert "metric_name" in data[0]
        assert "value" in data[0]

    def test_summary_output(self, temp_db):
        """Summary output shows statistics."""
        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--summary",
                "--db", str(temp_db),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "min:" in result.stdout
        assert "max:" in result.stdout
        assert "avg:" in result.stdout

    def test_from_to_range_works(self, temp_db):
        """Query with --from/--to works correctly."""
        now = datetime.now()
        from_time = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        to_time = now.strftime("%Y-%m-%d %H:%M")

        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--from", from_time,
                "--to", to_time,
                "--db", str(temp_db),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "wanctl_rtt_ms" in result.stdout


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_database_shows_helpful_message(self, tmp_path):
        """Missing database shows helpful error message."""
        db_path = tmp_path / "nonexistent.db"
        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--db", str(db_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Database not found" in result.stderr
        assert "Run wanctl to generate data" in result.stderr

    def test_invalid_duration_shows_error(self):
        """Invalid duration shows error message."""
        result = subprocess.run(
            [sys.executable, "-m", "wanctl.history", "--last", "invalid"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Invalid duration" in result.stderr

    def test_empty_results_shows_message_exit_0(self, tmp_path):
        """Empty results show message and exit 0."""
        # Reset singleton and create empty database
        MetricsWriter._reset_instance()
        db_path = tmp_path / "empty.db"
        writer = MetricsWriter(db_path=db_path)
        # Write old data outside query range so database exists but query returns nothing
        old_ts = int(datetime.now().timestamp()) - 86400 * 30  # 30 days ago
        writer.write_metric(
            timestamp=old_ts,
            wan_name="test",
            metric_name="wanctl_rtt_ms",
            value=10.0,
        )
        writer.close()
        MetricsWriter._reset_instance()

        result = subprocess.run(
            [
                sys.executable, "-m", "wanctl.history",
                "--last", "1h",
                "--db", str(db_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "No data found" in result.stdout


# =============================================================================
# MAIN FUNCTION TESTS
# =============================================================================


class TestMain:
    """Tests for main() function."""

    def test_main_with_temp_db(self, temp_db, monkeypatch):
        """main() returns 0 with valid database."""
        monkeypatch.setattr(sys, "argv", [
            "wanctl-history", "--last", "1h", "--db", str(temp_db)
        ])
        assert main() == 0

    def test_main_missing_db_returns_1(self, tmp_path, monkeypatch):
        """main() returns 1 when database is missing."""
        db_path = tmp_path / "nonexistent.db"
        monkeypatch.setattr(sys, "argv", [
            "wanctl-history", "--last", "1h", "--db", str(db_path)
        ])
        assert main() == 1

    def test_main_default_time_range(self, temp_db, monkeypatch, capsys):
        """main() uses default 1h time range when no args."""
        monkeypatch.setattr(sys, "argv", [
            "wanctl-history", "--db", str(temp_db)
        ])
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        # Should have output (data exists)
        assert "wanctl" in captured.out or "No data" in captured.out

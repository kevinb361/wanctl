"""Nyquist validation tests for Phase 52: Operational Resilience.

These tests fill behavioral gaps identified during validation audit.
Each test maps to a specific OPS requirement.
"""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def reset_singleton():
    """Reset the MetricsWriter singleton before and after each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test_metrics.db"


class TestOPS02LogicalCorruption:
    """OPS-02: Verify MetricsWriter detects logical corruption via PRAGMA integrity_check.

    Existing tests cover garbage-byte corruption (DatabaseError on connect).
    This test covers the distinct path where the file is a valid SQLite database
    but integrity_check returns non-'ok' (logical corruption).
    """

    def test_logical_corruption_detected_and_rebuilt(self, reset_singleton, test_db_path):
        """When integrity_check returns non-ok, DB is renamed .corrupt and rebuilt."""
        # Create a valid SQLite DB first
        test_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(test_db_path)
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.execute("INSERT INTO dummy VALUES (1)")
        conn.close()

        writer = MetricsWriter(test_db_path)

        # Mock _open_connection to return a connection where integrity_check
        # reports corruption but the connection itself succeeds
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_result = MagicMock()
        mock_result.__getitem__ = MagicMock(return_value="*** in table dummy: row count mismatch")

        def selective_execute(sql, *args, **kwargs):
            if "integrity_check" in str(sql):
                result = MagicMock()
                result.fetchone.return_value = ("*** in table dummy: row count mismatch",)
                return result
            return MagicMock()

        mock_conn.execute = MagicMock(side_effect=selective_execute)

        # Track whether _rebuild_database was called
        original_rebuild = writer._rebuild_database
        rebuild_called = False

        def mock_rebuild():
            nonlocal rebuild_called
            rebuild_called = True
            return original_rebuild()

        with patch.object(writer, "_open_connection", return_value=mock_conn):
            with patch.object(writer, "_rebuild_database", side_effect=mock_rebuild):
                writer._connect_and_validate()

        assert rebuild_called, (
            "Expected _rebuild_database to be called when integrity_check returns non-ok result"
        )

    def test_logical_corruption_closes_old_connection(self, reset_singleton, test_db_path):
        """When integrity_check fails, the corrupt connection is closed before rebuild."""
        test_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(test_db_path)
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        writer = MetricsWriter(test_db_path)

        mock_conn = MagicMock(spec=sqlite3.Connection)

        def selective_execute(sql, *args, **kwargs):
            if "integrity_check" in str(sql):
                result = MagicMock()
                result.fetchone.return_value = ("data corruption detected",)
                return result
            return MagicMock()

        mock_conn.execute = MagicMock(side_effect=selective_execute)

        with (
            patch.object(writer, "_open_connection", return_value=mock_conn),
            patch.object(writer, "_rebuild_database", return_value=MagicMock()),
        ):
            writer._connect_and_validate()

        mock_conn.close.assert_called_once()


class TestOPS04CryptographyPin:
    """OPS-04: Verify cryptography dependency is pinned to patch CVE-2026-26007."""

    def test_cryptography_version_meets_minimum(self):
        """Installed cryptography version is at least 46.0.5 (CVE fix)."""
        import cryptography

        version_parts = [int(x) for x in cryptography.__version__.split(".")]
        # Must be >= 46.0.5
        assert version_parts >= [46, 0, 5], (
            f"cryptography {cryptography.__version__} is below 46.0.5 (CVE-2026-26007 fix)"
        )

    def test_cryptography_pinned_in_pyproject(self):
        """pyproject.toml pins cryptography >= 46.0.5."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()
        assert "cryptography>=46.0.5" in content, "cryptography>=46.0.5 not found in pyproject.toml"

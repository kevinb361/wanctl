"""Storage subpackage test fixtures.

Fixtures specific to MetricsWriter, schema, retention, downsampler,
maintenance, and config snapshot tests.
"""

import sqlite3
from pathlib import Path

import pytest

from wanctl.storage.schema import create_tables
from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def reset_metrics_singleton():
    """Reset MetricsWriter singleton before and after each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def test_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a test database with schema."""
    db_path = tmp_path / "test_metrics.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    create_tables(conn)
    return conn

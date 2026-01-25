"""
Database Schema - SQLite tables and metric definitions for time-series storage.

Provides Prometheus-compatible metric naming and efficient indexing for
time-series queries.
"""

import sqlite3
from typing import Any

# Prometheus-compatible metric names and descriptions
STORED_METRICS: dict[str, str] = {
    "wanctl_rtt_ms": "Current RTT measurement in milliseconds",
    "wanctl_rtt_baseline_ms": "Baseline RTT in milliseconds (frozen during load)",
    "wanctl_rtt_delta_ms": "RTT delta from baseline in milliseconds",
    "wanctl_rate_download_mbps": "Current download rate limit in Mbps",
    "wanctl_rate_upload_mbps": "Current upload rate limit in Mbps",
    "wanctl_state": "Congestion state (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED)",
    "wanctl_steering_enabled": "Steering active status (0=disabled, 1=enabled)",
}

# SQL schema for metrics table with indexes for time-series queries
METRICS_SCHEMA: str = """
-- Metrics table for time-series data
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    wan_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    labels TEXT,
    granularity TEXT DEFAULT 'raw'
);

-- Index for time-range queries
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
    ON metrics(timestamp);

-- Composite index for filtered time-range queries by WAN and metric
CREATE INDEX IF NOT EXISTS idx_metrics_wan_metric_time
    ON metrics(wan_name, metric_name, timestamp);

-- Index for granularity-based queries (raw, 1m, 5m, 1h)
CREATE INDEX IF NOT EXISTS idx_metrics_granularity_time
    ON metrics(granularity, timestamp);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes from the schema.

    Args:
        conn: SQLite database connection

    Note:
        Uses IF NOT EXISTS so safe to call multiple times.
    """
    conn.executescript(METRICS_SCHEMA)
    conn.commit()

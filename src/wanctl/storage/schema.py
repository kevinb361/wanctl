"""
Database Schema - SQLite tables and metric definitions for time-series storage.

Provides Prometheus-compatible metric naming and efficient indexing for
time-series queries.
"""

import sqlite3

# Prometheus-compatible metric names and descriptions
STORED_METRICS: dict[str, str] = {
    "wanctl_rtt_ms": "Current RTT measurement in milliseconds",
    "wanctl_rtt_baseline_ms": "Baseline RTT in milliseconds (frozen during load)",
    "wanctl_rtt_delta_ms": "RTT delta from baseline in milliseconds",
    "wanctl_rate_download_mbps": "Current download rate limit in Mbps",
    "wanctl_rate_upload_mbps": "Current upload rate limit in Mbps",
    "wanctl_state": "Congestion state (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED)",
    "wanctl_steering_enabled": "Steering active status (0=disabled, 1=enabled)",
    "wanctl_wan_zone": "WAN congestion zone from autorate (0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED)",
    "wanctl_wan_weight": "WAN confidence weight applied (0 when GREEN/None, config weight when RED/SOFT_RED)",
    "wanctl_wan_staleness_sec": "WAN state file age in seconds (-1 when inaccessible)",
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

# SQL schema for alerts table with indexes for querying alert history
ALERTS_SCHEMA: str = """
-- Alerts table for alert event persistence
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    wan_name TEXT NOT NULL,
    details TEXT,
    delivery_status TEXT DEFAULT 'pending'
);

-- Index for time-range queries on alerts
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
    ON alerts(timestamp);

-- Composite index for querying alerts by type and WAN
CREATE INDEX IF NOT EXISTS idx_alerts_type_wan
    ON alerts(alert_type, wan_name, timestamp);
"""


# SQL schema for benchmarks table storing bufferbloat benchmark results
BENCHMARKS_SCHEMA: str = """
-- Benchmarks table for bufferbloat benchmark results
CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    wan_name TEXT NOT NULL,
    download_grade TEXT,
    upload_grade TEXT,
    download_latency_avg REAL,
    download_latency_p50 REAL,
    download_latency_p95 REAL,
    download_latency_p99 REAL,
    upload_latency_avg REAL,
    upload_latency_p50 REAL,
    upload_latency_p95 REAL,
    upload_latency_p99 REAL,
    download_throughput REAL,
    upload_throughput REAL,
    baseline_rtt REAL,
    server TEXT,
    duration INTEGER,
    daemon_running INTEGER NOT NULL DEFAULT 0,
    label TEXT
);

-- Index for time-range queries on benchmarks
CREATE INDEX IF NOT EXISTS idx_benchmarks_timestamp
    ON benchmarks(timestamp);

-- Composite index for WAN + time queries
CREATE INDEX IF NOT EXISTS idx_benchmarks_wan
    ON benchmarks(wan_name, timestamp);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes from the schema.

    Args:
        conn: SQLite database connection

    Note:
        Uses IF NOT EXISTS so safe to call multiple times.
    """
    conn.executescript(METRICS_SCHEMA)
    conn.executescript(ALERTS_SCHEMA)
    conn.executescript(BENCHMARKS_SCHEMA)
    conn.commit()

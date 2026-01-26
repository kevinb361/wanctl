"""
Storage Module - Time-Series Metrics Persistence

SQLite-based storage for historical metrics data with Prometheus-compatible naming.
Supports configurable retention and downsampling for efficient storage.

Components:
- schema.py: Database schema and metric definitions
- writer.py: Thread-safe MetricsWriter singleton
- reader.py: Read-only query functions for CLI/API
- retention.py: Cleanup of expired data
- downsampler.py: Granularity reduction as data ages

Usage:
    from wanctl.storage import MetricsWriter, STORED_METRICS
    from wanctl.storage import cleanup_old_metrics, downsample_metrics
    from wanctl.storage import query_metrics, compute_summary, select_granularity
"""

from wanctl.storage.config_snapshot import record_config_snapshot
from wanctl.storage.downsampler import (
    DOWNSAMPLE_THRESHOLDS,
    downsample_metrics,
)
from wanctl.storage.maintenance import run_startup_maintenance
from wanctl.storage.reader import (
    compute_summary,
    query_metrics,
    select_granularity,
)
from wanctl.storage.retention import (
    BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    cleanup_old_metrics,
    vacuum_if_needed,
)
from wanctl.storage.schema import METRICS_SCHEMA, STORED_METRICS, create_tables
from wanctl.storage.writer import DEFAULT_DB_PATH, MetricsWriter

__all__ = [
    # Writer
    "MetricsWriter",
    "DEFAULT_DB_PATH",
    # Reader
    "query_metrics",
    "compute_summary",
    "select_granularity",
    # Config snapshot
    "record_config_snapshot",
    # Schema
    "METRICS_SCHEMA",
    "STORED_METRICS",
    "create_tables",
    # Retention
    "cleanup_old_metrics",
    "vacuum_if_needed",
    "DEFAULT_RETENTION_DAYS",
    "BATCH_SIZE",
    # Downsampling
    "downsample_metrics",
    "DOWNSAMPLE_THRESHOLDS",
    # Maintenance
    "run_startup_maintenance",
]

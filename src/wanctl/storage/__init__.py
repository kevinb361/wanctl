"""
Storage Module - Time-Series Metrics Persistence

SQLite-based storage for historical metrics data with Prometheus-compatible naming.
Supports configurable retention and downsampling for efficient storage.

Components:
- schema.py: Database schema and metric definitions
- writer.py: Thread-safe MetricsWriter singleton

Usage:
    from wanctl.storage import MetricsWriter, STORED_METRICS
"""

from wanctl.storage.schema import METRICS_SCHEMA, STORED_METRICS, create_tables
from wanctl.storage.writer import MetricsWriter

__all__ = [
    "MetricsWriter",
    "METRICS_SCHEMA",
    "STORED_METRICS",
    "create_tables",
]

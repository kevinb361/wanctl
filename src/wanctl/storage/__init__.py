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

# Exports populated after implementation
__all__: list[str] = []

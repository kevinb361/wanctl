"""Tests for bounded runtime/storage pressure helpers."""

from wanctl.runtime_pressure import (
    build_runtime_section,
    build_storage_section,
    classify_memory_status,
    get_storage_file_snapshot,
)


def test_get_storage_file_snapshot_missing_path_is_bounded(tmp_path):
    snapshot = get_storage_file_snapshot(tmp_path / "missing.db")

    assert snapshot == {
        "db_bytes": 0,
        "wal_bytes": 0,
        "shm_bytes": 0,
        "total_bytes": 0,
        "db_exists": False,
        "wal_exists": False,
        "shm_exists": False,
    }


def test_build_storage_section_classifies_wal_pressure():
    section = build_storage_section(
        {
            "pending_writes": 0,
            "queue_drained_total": 1,
            "queue_error_total": 0,
            "write_success_total": 1,
            "write_failure_total": 0,
            "write_lock_failure_total": 0,
            "write_volume_total": 4,
            "write_last_duration_ms": 1.0,
            "write_max_duration_ms": 1.0,
            "checkpoint": {
                "busy": 0,
                "wal_pages": 0,
                "checkpointed_pages": 0,
                "maintenance_lock_skipped_total": 0,
            },
        },
        {
            "db_bytes": 10,
            "wal_bytes": 150 * 1024 * 1024,
            "shm_bytes": 0,
            "total_bytes": 150 * 1024 * 1024 + 10,
            "db_exists": True,
            "wal_exists": True,
            "shm_exists": False,
        },
    )

    assert section["files"]["wal_bytes"] == 150 * 1024 * 1024
    assert section["status"] == "warning"


def test_build_storage_section_ignores_historical_queue_errors_when_current_pressure_is_ok():
    section = build_storage_section(
        {
            "pending_writes": 1,
            "queue_drained_total": 100,
            "queue_error_total": 40,
            "write_success_total": 100,
            "write_failure_total": 0,
            "write_lock_failure_total": 0,
            "write_volume_total": 100,
            "write_last_duration_ms": 1.0,
            "write_max_duration_ms": 5.0,
            "checkpoint": {
                "busy": 0,
                "wal_pages": 0,
                "checkpointed_pages": 0,
                "maintenance_lock_skipped_total": 0,
            },
        },
        {
            "db_bytes": 1024,
            "wal_bytes": 8 * 1024 * 1024,
            "shm_bytes": 0,
            "total_bytes": 1024 + 8 * 1024 * 1024,
            "db_exists": True,
            "wal_exists": True,
            "shm_exists": False,
        },
    )

    assert section["queue"]["error_total"] == 40
    assert section["status"] == "ok"


def test_build_runtime_section_combines_memory_and_cycle_status():
    runtime = build_runtime_section(
        process_role="autorate",
        rss_bytes=300 * 1024 * 1024,
        cycle_status="ok",
    )

    assert runtime["process"] == "autorate"
    assert runtime["memory_status"] == "warning"
    assert runtime["status"] == "warning"


def test_classify_memory_status_handles_unknown():
    assert classify_memory_status(None) == "unknown"

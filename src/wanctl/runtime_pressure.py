"""Bounded runtime and storage pressure helpers for health and metrics surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

RSS_WARNING_BYTES = 256 * 1024 * 1024
RSS_CRITICAL_BYTES = 512 * 1024 * 1024
SWAP_WARNING_BYTES = 128 * 1024 * 1024
SWAP_CRITICAL_BYTES = 1024 * 1024 * 1024
WAL_WARNING_BYTES = 128 * 1024 * 1024
WAL_CRITICAL_BYTES = 256 * 1024 * 1024
PENDING_WRITES_WARNING = 5
PENDING_WRITES_CRITICAL = 20


_STATUS_ORDER = {"ok": 0, "warning": 1, "critical": 2, "unknown": 3}


def _max_status(*statuses: str) -> str:
    known = [s for s in statuses if s in _STATUS_ORDER]
    if not known:
        return "unknown"
    return max(known, key=lambda s: _STATUS_ORDER[s])


def read_process_resident_memory_bytes(status_path: str = "/proc/self/status") -> int | None:
    """Read current resident set size from /proc/self/status."""
    rss_bytes, _ = read_process_memory_status(status_path)
    return rss_bytes


def read_process_memory_status(status_path: str = "/proc/self/status") -> tuple[int | None, int | None]:
    """Read current resident and swap usage from /proc/self/status."""
    try:
        rss_bytes: int | None = None
        swap_bytes: int | None = None
        for line in Path(status_path).read_text().splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2:
                    rss_bytes = int(parts[1]) * 1024
            elif line.startswith("VmSwap:"):
                parts = line.split()
                if len(parts) >= 2:
                    swap_bytes = int(parts[1]) * 1024
    except (FileNotFoundError, PermissionError, ValueError, OSError):
        return None, None
    return rss_bytes, swap_bytes


def classify_memory_status(rss_bytes: int | None) -> str:
    """Classify RSS pressure into ok/warning/critical/unknown."""
    if rss_bytes is None:
        return "unknown"
    if rss_bytes >= RSS_CRITICAL_BYTES:
        return "critical"
    if rss_bytes >= RSS_WARNING_BYTES:
        return "warning"
    return "ok"


def classify_swap_status(swap_bytes: int | None) -> str:
    """Classify swap pressure into ok/warning/critical/unknown."""
    if swap_bytes is None:
        return "unknown"
    if swap_bytes >= SWAP_CRITICAL_BYTES:
        return "critical"
    if swap_bytes >= SWAP_WARNING_BYTES:
        return "warning"
    return "ok"


def get_storage_file_snapshot(db_path: str | Path | None) -> dict[str, Any]:
    """Return bounded DB/WAL/SHM file size snapshot."""
    if not db_path:
        return {
            "db_bytes": 0,
            "wal_bytes": 0,
            "shm_bytes": 0,
            "total_bytes": 0,
            "db_exists": False,
            "wal_exists": False,
            "shm_exists": False,
        }

    base = Path(db_path)
    wal = Path(f"{base}-wal")
    shm = Path(f"{base}-shm")

    def _size(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    db_bytes = _size(base)
    wal_bytes = _size(wal)
    shm_bytes = _size(shm)
    return {
        "db_bytes": db_bytes,
        "wal_bytes": wal_bytes,
        "shm_bytes": shm_bytes,
        "total_bytes": db_bytes + wal_bytes + shm_bytes,
        "db_exists": base.exists(),
        "wal_exists": wal.exists(),
        "shm_exists": shm.exists(),
    }


def classify_storage_status(storage: dict[str, Any], files: dict[str, Any]) -> str:
    """Classify storage pressure from bounded queue/write/file signals."""
    pending_writes = int(storage.get("pending_writes", 0) or 0)
    lock_failures = int(storage.get("writes", {}).get("lock_failure_total", 0) or 0)
    checkpoint_busy = int(storage.get("checkpoint", {}).get("busy", 0) or 0)
    wal_bytes = int(files.get("wal_bytes", 0) or 0)

    if (
        lock_failures > 0
        or checkpoint_busy > 0
        or pending_writes >= PENDING_WRITES_CRITICAL
        or wal_bytes >= WAL_CRITICAL_BYTES
    ):
        return "critical"
    # queue.error_total is a lifetime counter of past deferred write exceptions.
    # It remains useful for diagnosis, but it is not a current-pressure signal.
    if (
        pending_writes >= PENDING_WRITES_WARNING
        or wal_bytes >= WAL_WARNING_BYTES
    ):
        return "warning"
    return "ok"


def build_runtime_section(
    *,
    process_role: str,
    rss_bytes: int | None,
    swap_bytes: int | None = None,
    cycle_status: str | None,
) -> dict[str, Any]:
    """Build bounded runtime pressure section."""
    memory_status = classify_memory_status(rss_bytes)
    swap_status = classify_swap_status(swap_bytes) if swap_bytes is not None else "ok"
    overall_status = _max_status(memory_status, swap_status, cycle_status or "ok")
    return {
        "process": process_role,
        "rss_bytes": rss_bytes,
        "swap_bytes": swap_bytes,
        "memory_status": memory_status,
        "swap_status": swap_status,
        "cycle_status": cycle_status,
        "status": overall_status,
    }


def build_storage_section(
    storage: dict[str, Any] | None, files: dict[str, Any] | None
) -> dict[str, Any]:
    """Build bounded storage section with queue/write/file status."""
    storage_data = storage if isinstance(storage, dict) else {}
    file_data = files if isinstance(files, dict) else {}
    raw_checkpoint = storage_data.get("checkpoint")
    checkpoint: dict[str, Any] = raw_checkpoint if isinstance(raw_checkpoint, dict) else {}
    section = {
        "pending_writes": int(storage_data.get("pending_writes", 0) or 0),
        "queue": {
            "drained_total": int(storage_data.get("queue_drained_total", 0) or 0),
            "error_total": int(storage_data.get("queue_error_total", 0) or 0),
        },
        "writes": {
            "success_total": int(storage_data.get("write_success_total", 0) or 0),
            "failure_total": int(storage_data.get("write_failure_total", 0) or 0),
            "lock_failure_total": int(storage_data.get("write_lock_failure_total", 0) or 0),
            "volume_total": int(storage_data.get("write_volume_total", 0) or 0),
            "last_duration_ms": storage_data.get("write_last_duration_ms"),
            "max_duration_ms": storage_data.get("write_max_duration_ms"),
        },
        "checkpoint": {
            "busy": int(checkpoint.get("busy", 0) or 0),
            "wal_pages": int(checkpoint.get("wal_pages", 0) or 0),
            "checkpointed_pages": int(checkpoint.get("checkpointed_pages", 0) or 0),
            "maintenance_lock_skipped_total": int(
                checkpoint.get("maintenance_lock_skipped_total", 0) or 0
            ),
        },
        "files": {
            "db_bytes": int(file_data.get("db_bytes", 0) or 0),
            "wal_bytes": int(file_data.get("wal_bytes", 0) or 0),
            "shm_bytes": int(file_data.get("shm_bytes", 0) or 0),
            "total_bytes": int(file_data.get("total_bytes", 0) or 0),
            "db_exists": bool(file_data.get("db_exists", False)),
            "wal_exists": bool(file_data.get("wal_exists", False)),
            "shm_exists": bool(file_data.get("shm_exists", False)),
        },
    }
    section["status"] = classify_storage_status(section, file_data)
    return section

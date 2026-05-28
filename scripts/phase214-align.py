#!/usr/bin/env python3
"""Phase 214 per-second multi-source alignment joiner.

Reads a .flent.gz artifact, 1Hz /health NDJSON, pre-pulled journal events,
and optional alert rows, then emits one aligned row per integer second across
the flent window plus pre/post buffers.

Invariants: stdlib-only; no wanctl imports; fail closed on missing flent ping
series and malformed health time keys; reuses phase214-extract.py's
FlentExtractionError class rather than redefining it.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_EXTRACT_PATH = Path(__file__).resolve().parent / "phase214-extract.py"
if "phase214_extract" in sys.modules:
    _phase214_extract = sys.modules["phase214_extract"]
else:
    _spec = importlib.util.spec_from_file_location("phase214_extract", _EXTRACT_PATH)
    if _spec is None or _spec.loader is None:  # pragma: no cover - importlib guard
        raise ImportError(f"Unable to load {_EXTRACT_PATH}")
    _phase214_extract = importlib.util.module_from_spec(_spec)
    sys.modules["phase214_extract"] = _phase214_extract
    _spec.loader.exec_module(_phase214_extract)

FlentExtractionError = _phase214_extract.FlentExtractionError
extract_flent_latency = _phase214_extract.extract_flent_latency

PING_SERIES = "Ping (ms) ICMP"
ROW_SCHEMA_KEYS = [
    "t_unix",
    "in_flent_window",
    "ping_count",
    "ping_max_ms",
    "ping_mean_ms",
    "health_status",
    "download_state",
    "download_state_reason",
    "measurement_state",
    "measurement_successful_count",
    "measurement_stale",
    "measurement_staleness_sec",
    "signal_outlier_rate",
    "signal_confidence",
    "signal_warming_up",
    "baseline_rtt_ms",
    "load_rtt_ms",
    "load_rtt_delta_us",
    "cake_dl_peak_delay_us",
    "cake_dl_drop_rate",
    "cake_dl_backlog_suppressed_count",
    "arb_active_primary_signal",
    "arb_refractory_active",
    "arb_rtt_confidence",
    "irtt_rtt_mean_ms",
    "irtt_loss_up_pct",
    "irtt_loss_down_pct",
    "irtt_asymmetry_ratio",
    "journal_events",
    "alerts_in_second",
]
HEALTH_FIELDS = [
    "download_state",
    "download_state_reason",
    "measurement_state",
    "measurement_successful_count",
    "measurement_stale",
    "measurement_staleness_sec",
    "signal_outlier_rate",
    "signal_confidence",
    "signal_warming_up",
    "baseline_rtt_ms",
    "load_rtt_ms",
    "load_rtt_delta_us",
    "cake_dl_peak_delay_us",
    "cake_dl_drop_rate",
    "cake_dl_backlog_suppressed_count",
    "arb_active_primary_signal",
    "arb_refractory_active",
    "arb_rtt_confidence",
    "irtt_rtt_mean_ms",
    "irtt_loss_up_pct",
    "irtt_loss_down_pct",
    "irtt_asymmetry_ratio",
]


class AlignmentError(RuntimeError):
    """Raised when required alignment inputs are absent or unreadable."""


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    """Read one JSON object per non-blank line; missing file returns []."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _read_flent_pings(path: Path) -> dict[int, list[float]]:
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)
    raw = data.get("raw_values") if isinstance(data, dict) else None
    series = raw.get(PING_SERIES) if isinstance(raw, dict) else None
    if not isinstance(series, list) or not series:
        raise FlentExtractionError(f"{path}: raw_values['{PING_SERIES}'] missing or empty")

    pings_by_sec: dict[int, list[float]] = {}
    for sample in series:
        if not isinstance(sample, dict) or "t" not in sample or "val" not in sample:
            continue
        pings_by_sec.setdefault(int(sample["t"]), []).append(float(sample["val"]))
    if not pings_by_sec:
        raise FlentExtractionError(f"{path}: ping series has no usable 't'/'val' entries")
    return pings_by_sec


def _health_second(path: Path, row: dict[str, Any]) -> int:
    value = row.get("t_wall")
    if not isinstance(value, str) or not value:
        raise AlignmentError(f"health row missing t_wall: {row}")
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError as exc:
        raise AlignmentError(f"{path}: health row unparsable t_wall: {row}") from exc


def _bucket_by_ts(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    buckets: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict) or "ts" not in row:
            continue
        try:
            buckets.setdefault(int(float(row["ts"])), []).append(row)
        except (TypeError, ValueError):
            continue
    return buckets


def _within_tolerance(buckets: dict[int, list[dict[str, Any]]], t_unix: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for bucket in (t_unix - 1, t_unix, t_unix + 1):
        for row in buckets.get(bucket, []):
            marker = id(row)
            if marker not in seen:
                out.append(row)
                seen.add(marker)
    return out


def _project_health(row: dict[str, Any] | None) -> dict[str, Any]:
    projected = {field: None for field in HEALTH_FIELDS}
    projected["health_status"] = None
    if row is None:
        return projected
    projected["health_status"] = row.get("status")
    for field in HEALTH_FIELDS:
        projected[field] = row.get(field)
    return projected


def align_window(
    flent_path: Path,
    health_ndjson: Path,
    journal_lines: list[dict[str, Any]],
    alerts_window: list[dict[str, Any]],
    flent_t0_unix: float,
    flent_end_unix: float,
    pre_buf_sec: int = 10,
    post_buf_sec: int = 10,
) -> list[dict[str, Any]]:
    """Return aligned rows for each integer second across the buffered window."""
    pings_by_sec = _read_flent_pings(flent_path)
    health_rows: dict[int, dict[str, Any]] = {}
    for row in _read_ndjson(health_ndjson):
        health_rows[_health_second(health_ndjson, row)] = row

    journal_by_sec = _bucket_by_ts(journal_lines)
    alerts_by_sec = _bucket_by_ts(alerts_window)

    rows: list[dict[str, Any]] = []
    start = int(flent_t0_unix) - pre_buf_sec
    end = int(flent_end_unix) + post_buf_sec
    for t_unix in range(start, end + 1):
        pings = pings_by_sec.get(t_unix, [])
        row: dict[str, Any] = {
            "t_unix": t_unix,
            "in_flent_window": flent_t0_unix <= t_unix <= flent_end_unix,
            "ping_count": len(pings),
            "ping_max_ms": max(pings) if pings else None,
            "ping_mean_ms": (sum(pings) / len(pings)) if pings else None,
        }
        row.update(_project_health(health_rows.get(t_unix)))
        row["journal_events"] = _within_tolerance(journal_by_sec, t_unix)
        row["alerts_in_second"] = _within_tolerance(alerts_by_sec, t_unix)
        rows.append({key: row[key] for key in ROW_SCHEMA_KEYS})
    return rows


def _read_alerts(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        rows = data.get("alerts")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [key for key in ROW_SCHEMA_KEYS if key not in {"journal_events", "alerts_in_second"}]
    fieldnames.extend(["journal_event_count", "journal_first_message", "alert_count"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            journal_events = row.get("journal_events") or []
            first_message = ""
            if journal_events:
                first = journal_events[0]
                first_message = str(first.get("message") or first.get("MESSAGE") or "")[:120]
            flat = {key: row.get(key) for key in fieldnames if key in row}
            flat["journal_event_count"] = len(journal_events)
            flat["journal_first_message"] = first_message
            flat["alert_count"] = len(row.get("alerts_in_second") or [])
            writer.writerow(flat)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flent-gz", required=True, type=Path)
    parser.add_argument("--health-ndjson", required=True, type=Path)
    parser.add_argument("--journal-ndjson", type=Path)
    parser.add_argument("--alerts-json", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--pre-buf-sec", type=int, default=10)
    parser.add_argument("--post-buf-sec", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        latency = extract_flent_latency(args.flent_gz)
        flent_t0_unix = datetime.fromisoformat(latency["window_start_utc"]).timestamp()
        flent_end_unix = datetime.fromisoformat(latency["window_end_utc"]).timestamp()
        rows = align_window(
            args.flent_gz,
            args.health_ndjson,
            _read_ndjson(args.journal_ndjson) if args.journal_ndjson else [],
            _read_alerts(args.alerts_json),
            flent_t0_unix,
            flent_end_unix,
            args.pre_buf_sec,
            args.post_buf_sec,
        )
    except (FlentExtractionError, AlignmentError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_csv:
        _write_csv(args.output_csv, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

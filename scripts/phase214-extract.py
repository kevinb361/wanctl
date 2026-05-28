#!/usr/bin/env python3
"""Phase 214 flent latency/throughput extractor.

Reads a .flent.gz artifact, extracts ping latency from
raw_values['Ping (ms) ICMP'] (the authoritative raw samples, not the binned
results series), and extracts TCP download throughput from the documented
results key fallback chain. Fails closed with FlentExtractionError when expected
series are missing or empty; it never returns zero for a missing series.

Invariants: stdlib-only; no wanctl imports; no Phase 213 back-edits; D-09/D-10
fail-closed extraction for Phase 214 measurement-collapse analysis.
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PING_SERIES = "Ping (ms) ICMP"
THROUGHPUT_KEYS = ("TCP download sum", "TCP totals", "TCP download avg")


class FlentExtractionError(RuntimeError):
    """Raised when expected flent series is missing or empty (D-10 fail-closed)."""


def _load_flent(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise FlentExtractionError(f"{path}: flent payload is not a JSON object")
    return data


def _parse_flent_time(path: Path, value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise FlentExtractionError(f"{path}: metadata.T0/TIME missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FlentExtractionError(f"{path}: metadata.T0/TIME is not ISO8601: {value}") from exc


def _numeric_values(series: Any) -> list[float]:
    if not isinstance(series, list):
        return []
    return [float(value) for value in series if isinstance(value, (int, float))]


def extract_flent_latency(path: Path) -> dict[str, Any]:
    """Return raw ping p50/p95/p99 latency (ms) plus flent run window.

    Raises FlentExtractionError if raw_values['Ping (ms) ICMP'] is missing or
    empty, if no usable 'val' entries exist, or if metadata.T0/TIME is missing.

    PERCENTILE CONTRACT (MED-11; canonical Phase 214 definition): Phase 214
    computes percentiles from the sorted raw-values list using p50 index n//2,
    p95 index min(n-1, int(n*0.95)), and p99 index min(n-1, int(n*0.99)). This
    is stdlib-only and intentionally does not use numpy-style interpolation.

    window_end_utc is an ISO8601 string computed from metadata.T0/TIME plus
    metadata.TOTAL_LENGTH (or LENGTH fallback) seconds.
    """
    data = _load_flent(path)
    raw = data.get("raw_values")
    series = raw.get(PING_SERIES) if isinstance(raw, dict) else None
    if not isinstance(series, list) or not series:
        raise FlentExtractionError(f"{path}: raw_values['{PING_SERIES}'] missing or empty")

    values = [float(sample["val"]) for sample in series if isinstance(sample, dict) and "val" in sample]
    if not values:
        raise FlentExtractionError(f"{path}: ping series has no usable 'val' entries")
    values.sort()
    n = len(values)

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        raise FlentExtractionError(f"{path}: metadata.T0/TIME missing")
    t0 = _parse_flent_time(path, meta.get("T0") or meta.get("TIME"))
    try:
        length_sec = float(meta.get("TOTAL_LENGTH") or meta.get("LENGTH") or 0)
    except (TypeError, ValueError) as exc:
        raise FlentExtractionError(f"{path}: metadata.TOTAL_LENGTH/LENGTH is not numeric") from exc

    series_meta = meta.get("SERIES_META")
    ping_meta = series_meta.get(PING_SERIES) if isinstance(series_meta, dict) else {}
    ping_command = ping_meta.get("COMMAND") if isinstance(ping_meta, dict) else None

    return {
        "p50_ms": values[n // 2],
        "p95_ms": values[min(n - 1, int(n * 0.95))],
        "p99_ms": values[min(n - 1, int(n * 0.99))],
        "min_ms": min(values),
        "max_ms": max(values),
        "mean_ms": statistics.mean(values),
        "sample_count": n,
        "window_start_utc": t0.isoformat(),
        "window_end_utc": (t0 + timedelta(seconds=length_sec)).isoformat(),
        "ping_command": ping_command,
    }


def extract_flent_throughput(path: Path) -> dict[str, Any]:
    """Return TCP download throughput stats from the documented fallback chain."""
    data = _load_flent(path)
    results = data.get("results")
    if not isinstance(results, dict):
        raise FlentExtractionError(f"{path}: results missing or not an object")

    for key in THROUGHPUT_KEYS:
        values = _numeric_values(results.get(key))
        if values:
            values.sort()
            n = len(values)
            return {
                "throughput_median_mbps": statistics.median(values),
                "throughput_p95_mbps": values[min(n - 1, int(n * 0.95))],
                "throughput_max_mbps": values[-1],
                "sample_count": n,
                "series_key_used": key,
            }
    raise FlentExtractionError(f"{path}: no usable TCP download series found")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flent-gz", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        out = {
            "latency": extract_flent_latency(args.flent_gz),
            "throughput": extract_flent_throughput(args.flent_gz),
        }
    except FlentExtractionError as exc:
        print(f"FlentExtractionError: {exc}", file=sys.stderr)
        return 1

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ruff: noqa: N999
"""Roll up Phase 243 Cycle timing NDJSON into per-arm profile JSON.

This is a thin wrapper over profiling_collector_json.py's label and statistics
contract with Phase 243 additions: invocation provenance, parse counters, and
inter-cycle STALL gap detection.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from profiling_collector_json import build_profile, canonical_label

STALL_GAP_THRESHOLD_MS = 100.0


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_ndjson_with_counters(
    stream: TextIO,
) -> tuple[dict[str, list[float]], dict[str, int], dict[str, object]]:
    """Parse Cycle timing records, preserving collector-compatible samples."""
    samples: dict[str, list[float]] = {}
    counters = {
        "lines_seen": 0,
        "json_decode_failures": 0,
        "cycle_records": 0,
        "timestamped_records": 0,
    }
    timestamps: list[datetime] = []

    for line in stream:
        counters["lines_seen"] += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            counters["json_decode_failures"] += 1
            continue

        if record.get("message") != "Cycle timing":
            continue

        counters["cycle_records"] += 1
        timestamp = _parse_timestamp(record.get("timestamp"))
        if timestamp is not None:
            counters["timestamped_records"] += 1
            timestamps.append(timestamp)

        for key, value in record.items():
            if not key.endswith("_ms") or not isinstance(value, int | float):
                continue
            samples.setdefault(canonical_label(key), []).append(float(value))

    return samples, counters, build_stall_profile(timestamps)


def build_stall_profile(timestamps: list[datetime]) -> dict[str, object]:
    gaps: list[float] = []
    events: list[dict[str, float | int]] = []
    for index, (previous, current) in enumerate(
        zip(timestamps, timestamps[1:], strict=False), start=1
    ):
        gap_ms = round((current - previous).total_seconds() * 1000.0, 3)
        gaps.append(gap_ms)
        if gap_ms > STALL_GAP_THRESHOLD_MS:
            events.append({"index": index, "gap_ms": gap_ms})

    return {
        "gap_threshold_ms": STALL_GAP_THRESHOLD_MS,
        "stall_event_count": len(events),
        "stall_events": events,
        "max_gap_ms": max(gaps) if gaps else 0.0,
    }


def open_input(path: str | None) -> TextIO:
    if path is None or path == "-":
        return sys.stdin
    return Path(path).open("r", encoding="utf-8")


def write_output(profile: dict[str, object], output: str | None) -> None:
    payload = json.dumps(profile, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Roll up Phase 243 Cycle timing NDJSON into per-arm profile JSON."
    )
    parser.add_argument("input", nargs="?", help="NDJSON path, or '-' / omitted for stdin.")
    parser.add_argument("--input", dest="input_flag", help="Synonym for positional input.")
    parser.add_argument("--output", help="Path to write profile JSON; omitted writes stdout.")
    parser.add_argument(
        "--invocation-id",
        required=True,
        help="Required _SYSTEMD_INVOCATION_ID captured for this benchmark arm.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.invocation_id.strip():
        print("ERROR: --invocation-id must be non-empty", file=sys.stderr)
        return 2

    input_path = args.input_flag or args.input
    try:
        with open_input(input_path) as stream:
            samples, counters, stall = parse_ndjson_with_counters(stream)
        if counters["cycle_records"] == 0:
            print("ERROR: no Cycle timing records in input", file=sys.stderr)
            return 2
        profile: dict[str, object] = build_profile(samples)
        if "autorate_cycle_total" not in profile:
            print("ERROR: no autorate_cycle_total samples in input", file=sys.stderr)
            return 2
        profile["invocation_id"] = args.invocation_id
        profile["parse_counters"] = counters
        profile["stall"] = stall
        write_output(profile, args.output)
    except Exception as exc:  # pragma: no cover - unexpected CLI failure path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

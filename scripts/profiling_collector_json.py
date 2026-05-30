#!/usr/bin/env python3
"""Convert wanctl JSON Cycle timing NDJSON into profiling collector JSON.

Canonical invocation:
    python scripts/profiling_collector_json.py \
        .planning/perf/capture/spectrum_debug.ndjson \
        --output .planning/perf/v1.45-baseline-spectrum-<date>.profile.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

# See .planning/phases/217-production-cycle-budget-baseline/217-RESEARCH.md
# §"Capture & Analysis Data Path (recommended)" for the data-path contract.


def canonical_label(json_key: str) -> str:
    """Reconstruct canonical autorate_* label from a Cycle timing *_ms key."""
    suffix = json_key.removesuffix("_ms")
    return f"autorate_{suffix}"


def calculate_statistics(samples: list[float]) -> dict[str, float | int]:
    """Calculate collector-compatible stats using sorted-index percentiles."""
    sorted_samples = sorted(samples)
    count = len(sorted_samples)
    p50_idx = min(count - 1, count // 2)
    p95_idx = min(count - 1, int(count * 0.95))
    p99_idx = min(count - 1, int(count * 0.99))

    return {
        "count": count,
        "min_ms": round(min(sorted_samples), 3),
        "p50_ms": round(sorted_samples[p50_idx], 3),
        "avg_ms": round(sum(sorted_samples) / count, 3),
        "max_ms": round(max(sorted_samples), 3),
        "p95_ms": round(sorted_samples[p95_idx], 3),
        "p99_ms": round(sorted_samples[p99_idx], 3),
    }


def parse_ndjson(stream: TextIO) -> tuple[dict[str, list[float]], int]:
    """Parse Cycle timing records from NDJSON into per-label sample lists."""
    samples: dict[str, list[float]] = {}
    cycle_records = 0

    for line in stream:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if record.get("message") != "Cycle timing":
            continue

        cycle_records += 1
        for key, value in record.items():
            if not key.endswith("_ms") or not isinstance(value, int | float):
                continue
            label = canonical_label(key)
            samples.setdefault(label, []).append(float(value))

    return samples, cycle_records


def build_profile(samples: dict[str, list[float]]) -> dict[str, dict[str, float | int]]:
    """Build the profiling_collector.py --output json compatible object."""
    return {label: calculate_statistics(values) for label, values in samples.items() if values}


def open_input(path: str | None) -> TextIO:
    """Open the input path, or stdin for absent / '-' inputs."""
    if path is None or path == "-":
        return sys.stdin
    return Path(path).open("r", encoding="utf-8")


def write_output(profile: dict[str, dict[str, float | int]], output: str | None) -> None:
    """Write profile JSON to output path or stdout."""
    payload = json.dumps(profile, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Convert wanctl JSON Cycle timing NDJSON into profiling JSON."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="NDJSON path to read, or '-' / omitted for stdin.",
    )
    parser.add_argument(
        "--input",
        dest="input_flag",
        help="NDJSON path to read; synonymous with positional input.",
    )
    parser.add_argument(
        "--output",
        help="Path to write profile JSON; omitted writes to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the NDJSON collector CLI."""
    args = parse_args(argv)
    input_path = args.input_flag or args.input

    try:
        with open_input(input_path) as stream:
            samples, cycle_records = parse_ndjson(stream)
        if cycle_records == 0:
            print("ERROR: no Cycle timing records in input", file=sys.stderr)
            return 2
        profile = build_profile(samples)
        if "autorate_cycle_total" not in profile:
            print("ERROR: no autorate_cycle_total samples in input", file=sys.stderr)
            return 2
        write_output(profile, args.output)
    except Exception as exc:  # pragma: no cover - unexpected CLI failure path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

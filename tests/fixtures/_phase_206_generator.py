#!/usr/bin/env python3
"""One-shot build tool for tests/fixtures/phase206_golden_capture.ndjson. Source: /home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/ (per Locked Decision D1; see golden-fixture-provenance.md for the full date-substitution rationale). Stdlib only — gzip + json + argparse + pathlib. Per-row cake_avg_delay_us / cake_base_delay_us are consumed by scripts/phase206-ab-replay.py via _replay_samples (Plan 01 Task 2)."""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = Path(
    "/home/kevin/flent-results/cake-shaper-920-rrul/"
    "cake-shaper-920-rrul-20260429-231547"
)
DEFAULT_OUT = REPO_ROOT / "tests/fixtures/phase206_golden_capture.ndjson"
PING_SERIES_KEYS = ("Ping (ms) ICMP", "Ping (ms) UDP BE", "Ping (ms) avg")


def _numeric_values(series: object) -> list[float]:
    if not isinstance(series, list):
        return []
    return [float(v) for v in series if isinstance(v, (int, float))]


def _load_flent(path: Path) -> dict:
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)
    results = data.get("results", {})
    if not isinstance(results, dict):
        raise TypeError(f"{path}: results is not a dict")
    return results


def _select_ping_series(results: dict) -> list[float]:
    for key in PING_SERIES_KEYS:
        values = _numeric_values(results.get(key))
        if values:
            return values
    raise ValueError(
        "no numeric ping series found; tried " + ", ".join(PING_SERIES_KEYS)
    )


def _baseline_rtt_ms(values: list[float]) -> float:
    first_window = max(1, int(len(values) * 0.05))
    nonzero = [v for v in values[:first_window] if v > 0.0]
    if not nonzero:
        raise ValueError("first 5% of ping series has no non-zero numeric values")
    return min(nonzero)


def _stride_to_limit(values: list[float], max_samples: int) -> list[float]:
    if len(values) <= max_samples:
        return values
    step = len(values) / max_samples
    return [values[int(i * step)] for i in range(max_samples)]


def build_rows(source_dir: Path, max_samples: int, min_samples: int) -> list[dict]:
    pattern = str(source_dir / "rrul-*.flent.gz")
    matches = sorted(Path(p) for p in glob.glob(pattern))
    if not matches:
        raise ValueError(f"no rrul-*.flent.gz files found under {source_dir}")

    results = _load_flent(matches[0])
    values = _stride_to_limit(_select_ping_series(results), max_samples)
    if len(values) < min_samples:
        raise ValueError(
            f"only {len(values)} samples after filtering; expected at least {min_samples}"
        )
    baseline = _baseline_rtt_ms(values)

    rows = []
    for i, load_rtt_ms in enumerate(values):
        cake_avg_delay_us = max(0, round((load_rtt_ms - baseline) * 1000))
        rows.append(
            {
                "ts": f"{i:06d}",
                "baseline_rtt_ms": baseline,
                "load_rtt_ms": load_rtt_ms,
                "cake_avg_delay_us": cake_avg_delay_us,
                "cake_base_delay_us": 0,
            }
        )
    return rows


def write_rows(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-samples", type=int, default=1024)
    parser.add_argument("--min-samples", type=int, default=24)
    args = parser.parse_args(argv)

    try:
        rows = build_rows(args.source_dir, args.max_samples, args.min_samples)
        write_rows(rows, args.out)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

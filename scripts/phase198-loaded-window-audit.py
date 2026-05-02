#!/usr/bin/env python3
"""Phase 198 per-run loaded-window queue-primary coverage audit.

Reads (a) a /health 1Hz NDJSON sampler trace as PRIMARY evidence and (b) a
raw SQLite PSV (canonical wanctl header
``sampled_utc|timestamp|wan_name|metric_name|value``) as SECONDARY /
cross-correlation evidence. Emits a pass|fail verdict per the Phase 197 audit
predicate, applied to a single 30s flent window.

Sample-count threshold is tuned to 1 Hz health sampling (>=25 of 30 expected
samples). Persisted SQLite raw rate is ~0.83 rows/sec across the controller,
far below 20 Hz cycle rate due to downsampling, so PSV cannot meet a
500-sample floor in 30s; see 198-REVIEWS.md HIGH-2.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


AUDIT_PREDICATE_PATH = (
    ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/"
    "soak/cake-primary/primary-signal-audit-phase197.md"
)


def _nested_get(obj: dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1.0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "queue"}
    return False


def _resolve_bool(
    sample: dict[str, Any], paths: list[tuple[str, str]]
) -> tuple[bool, str]:
    for path, kind in paths:
        value = _nested_get(sample, path) if "." in path else sample.get(path)
        if value is None:
            continue
        if kind == "queue_signal":
            return value == "queue", path
        return _truthy(value), path
    return False, "unresolved:false"


def _spectrum_health_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Select the Spectrum WAN sub-payload from a /health top-level sample.

    Production /health nests per-WAN state under `wans[]`; legacy fixtures
    placed `signal_arbitration` etc. at the root. Return the spectrum entry
    when present, fall back to wans[0], then to the sample itself.
    """
    wans = sample.get("wans")
    if isinstance(wans, list) and wans:
        for wan in wans:
            if isinstance(wan, dict) and wan.get("name") == "spectrum":
                return wan
        if isinstance(wans[0], dict):
            return wans[0]
    return sample


def _read_health(
    path: Path, start: int, end: int
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    resolution = {
        "queue_primary_active": "unresolved:false",
        "refractory_active": "unresolved:false",
        "dwell_bypass_active": "unresolved:false",
    }

    # Actual Phase 197 /health shape is signal_arbitration.active_primary_signal
    # and signal_arbitration.refractory_active (see src/wanctl/health_check.py).
    # The state/arbitration/top-level paths below keep fixture compatibility.
    queue_paths = [
        ("signal_arbitration.active_primary_signal", "queue_signal"),
        ("state.queue_primary_active", "bool"),
        ("arbitration.active_primary", "bool"),
        ("queue_primary_active", "bool"),
    ]
    refractory_paths = [
        ("signal_arbitration.refractory_active", "bool"),
        ("state.refractory_active", "bool"),
        ("arbitration.refractory_active", "bool"),
        ("refractory_active", "bool"),
    ]
    dwell_paths = [
        ("state.dwell_bypass_active", "bool"),
        ("dwell.bypass_active", "bool"),
        ("download.hysteresis.dwell_bypass_active", "bool"),
        ("dwell_bypassed", "bool"),
        ("dwell_bypass_active", "bool"),
    ]

    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            try:
                sampled_utc = float(sample["sampled_utc"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"{path}:{line_no}: missing numeric sampled_utc"
                ) from exc
            if not (start <= sampled_utc <= end):
                continue
            health_sample = _spectrum_health_sample(sample)
            queue, queue_path = _resolve_bool(health_sample, queue_paths)
            refractory, refractory_path = _resolve_bool(health_sample, refractory_paths)
            dwell, dwell_path = _resolve_bool(health_sample, dwell_paths)
            if resolution["queue_primary_active"] == "unresolved:false":
                resolution["queue_primary_active"] = queue_path
            if resolution["refractory_active"] == "unresolved:false":
                resolution["refractory_active"] = refractory_path
            if resolution["dwell_bypass_active"] == "unresolved:false":
                resolution["dwell_bypass_active"] = dwell_path
            rows.append(
                {
                    "queue_primary_active": queue,
                    "refractory_active": refractory,
                    "dwell_bypass_active": dwell,
                }
            )
    return rows, resolution


def _read_psv(path: Path, start: int, end: int) -> dict[int, dict[str, float]]:
    grouped: dict[int, dict[str, float]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="|")
        expected = ["sampled_utc", "timestamp", "wan_name", "metric_name", "value"]
        if reader.fieldnames != expected:
            raise ValueError(
                f"{path}: expected PSV header {'|'.join(expected)}, got {reader.fieldnames}"
            )
        for row in reader:
            if row.get("wan_name") != "spectrum":
                continue
            try:
                ts = int(float(row["timestamp"]))
                value = float(row["value"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: invalid PSV row {row!r}") from exc
            if start <= ts <= end:
                grouped[ts][row["metric_name"]] = value
    return grouped


def audit(args: argparse.Namespace) -> dict[str, Any]:
    health_rows, resolution = _read_health(
        Path(args.health_ndjson), args.flent_window_start, args.flent_window_end
    )
    grouped_psv = _read_psv(
        Path(args.psv), args.flent_window_start, args.flent_window_end
    )

    health_sample_count = len(health_rows)
    health_queue_primary_samples = sum(r["queue_primary_active"] for r in health_rows)
    health_refractory_samples = sum(r["refractory_active"] for r in health_rows)
    health_dwell_bypass_samples = sum(r["dwell_bypass_active"] for r in health_rows)
    health_non_queue = sum(not r["queue_primary_active"] for r in health_rows)
    health_non_queue_during_refractory = sum(
        (not r["queue_primary_active"]) and r["refractory_active"] for r in health_rows
    )
    queue_primary_health_pct = (
        100.0 * health_queue_primary_samples / max(health_sample_count, 1)
    )

    sqlite_queue_samples = 0
    sqlite_queue_via_refractory = 0
    sqlite_non_queue = 0
    for metrics in grouped_psv.values():
        active = metrics.get("wanctl_arbitration_active_primary")
        refractory = metrics.get("wanctl_arbitration_refractory_active", 0.0)
        if active == 1.0:
            sqlite_queue_samples += 1
        elif active == 2.0 and refractory == 1.0:
            sqlite_queue_via_refractory += 1
        else:
            sqlite_non_queue += 1
    sqlite_sample_count = len(grouped_psv)
    queue_primary_sqlite_pct = (
        100.0
        * (sqlite_queue_samples + sqlite_queue_via_refractory)
        / max(sqlite_sample_count, 1)
    )

    health_count_ok = health_sample_count >= args.min_health_samples
    coverage_ok = queue_primary_health_pct >= args.min_coverage_pct
    no_unexplained_fallback = health_non_queue == 0
    verdict = (
        "pass"
        if health_count_ok and coverage_ok and no_unexplained_fallback
        else "fail"
    )

    return {
        "phase": 198,
        "run": args.run,
        "audit_predicate_path": AUDIT_PREDICATE_PATH,
        "primary_evidence_kind": "health_ndjson_1hz",
        "secondary_evidence_kind": "sqlite_psv_persisted_raw",
        "health_ndjson_path": args.health_ndjson,
        "psv_path": args.psv,
        "flent_window": {
            "start_epoch": args.flent_window_start,
            "end_epoch": args.flent_window_end,
            "duration_seconds": args.flent_window_end - args.flent_window_start,
        },
        "health_field_resolution": resolution,
        "health_sample_count": health_sample_count,
        "health_queue_primary_samples": health_queue_primary_samples,
        "health_refractory_samples": health_refractory_samples,
        "health_dwell_bypass_samples": health_dwell_bypass_samples,
        "health_non_queue": health_non_queue,
        "health_non_queue_during_refractory": health_non_queue_during_refractory,
        "non_queue_samples": health_non_queue,
        "queue_primary_health_pct": queue_primary_health_pct,
        "sqlite_sample_count": sqlite_sample_count,
        "sqlite_queue_samples": sqlite_queue_samples,
        "sqlite_queue_via_refractory": sqlite_queue_via_refractory,
        "sqlite_non_queue": sqlite_non_queue,
        "queue_primary_sqlite_pct": queue_primary_sqlite_pct,
        "min_health_samples_threshold": args.min_health_samples,
        "min_coverage_pct_threshold": args.min_coverage_pct,
        "health_count_ok": health_count_ok,
        "coverage_ok": coverage_ok,
        "no_unexplained_fallback": no_unexplained_fallback,
        "verdict": verdict,
        "decision": (
            "Health primary evidence supports loaded-window queue-primary closure."
            if verdict == "pass"
            else "Health primary evidence does not support loaded-window queue-primary closure."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-ndjson", required=True)
    parser.add_argument("--psv", required=True)
    parser.add_argument("--flent-window-start", type=int, required=True)
    parser.add_argument("--flent-window-end", type=int, required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-health-samples", type=int, default=25)
    parser.add_argument("--min-coverage-pct", type=float, default=95.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "Phase 198 loaded-window audit run "
        f"{args.run}: {result['verdict']} "
        f"(health_samples={result['health_sample_count']}, "
        f"queue_primary_health_pct={result['queue_primary_health_pct']:.2f}, "
        f"non_queue_samples={result['non_queue_samples']})",
        file=sys.stderr,
    )
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

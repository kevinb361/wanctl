#!/usr/bin/env python3
"""Phase 206 A/B replay harness. Drives QueueController twice against tests/fixtures/phase206_golden_capture.ndjson (pre: 940M diffserv4 nowash; post: 920M besteffort wash) and emits a schema-v1 A/B summary JSON. Reuses tests.test_phase_193_replay._replay and tests.test_phase_206_replay._replay_samples by import (intentional tests.* import — this script is CI-only invocation; if ever packaged for /opt/wanctl runtime, these helpers would migrate to wanctl.testing.replay). With --flent-gz-pre and --flent-gz-post, also parses real RRUL p99/throughput/jitter from flent artifacts and reports meta.metric_source='flent'. Stdlib only."""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from wanctl.queue_controller import QueueController
from tests.fixtures.phase206_replay_corpus import GOLDEN_NDJSON, GoldenSample, load_golden
from tests.test_phase_193_replay import _fresh_controller, _replay  # REUSE — do not redefine
from tests.test_phase_206_replay import _replay_samples, _snap_for  # C2 fix

SCHEMA_VERSION = 1
DEFAULT_FIXTURE = GOLDEN_NDJSON
TOOL_VERSION = "phase206-ab-replay/1.1"
PING_SERIES_KEYS = ("Ping (ms) ICMP", "Ping (ms) UDP BE", "Ping (ms) avg")
EXIT_SUCCESS = 0
EXIT_ABORT = 2


def _post_controller() -> QueueController:
    return _fresh_controller("spectrum")  # already 920M


def _pre_controller() -> QueueController:
    c = _fresh_controller("spectrum")
    c.ceiling = 940_000_000
    c.current_rate = 940_000_000
    return c


def _numeric_values(series: object) -> list[float]:
    if not isinstance(series, list):
        return []
    return [float(v) for v in series if isinstance(v, (int, float))]


def _parse_flent_rrul(path: Path) -> dict[str, float | str]:
    """Parse RRUL metrics from a flent .flent.gz file.

    Returns a dict with rrul_p99_latency_ms, throughput_mbps, jitter_ms.
    Raises ValueError on malformed input.
    """
    try:
        with gzip.open(path, "rt") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"flent parse failed for {path}: {e}") from e
    results = data.get("results", {})
    if not isinstance(results, dict):
        raise ValueError(f"flent parse failed for {path}: results is not a dict")

    ping_values: list[float] = []
    for key in PING_SERIES_KEYS:
        ping_values = _numeric_values(results.get(key))
        if ping_values:
            break
    if not ping_values:
        raise ValueError(f"flent parse failed for {path}: no ping series with numeric data")
    if len(ping_values) < 2:
        raise ValueError(f"flent parse failed for {path}: ping series has fewer than 2 numeric values")

    qs = statistics.quantiles(ping_values, n=100, method="inclusive")
    p99 = qs[98]
    p50 = qs[49]

    tput_mbps = 0.0
    for key, series in results.items():
        if isinstance(key, str) and key.startswith("TCP") and isinstance(series, list):
            tail = [v for v in series if isinstance(v, (int, float))]
            if tail:
                tput_mbps += float(tail[-1])
    if tput_mbps == 0.0:
        print(f"INFO: no TCP throughput series found in {path}", file=sys.stderr)

    return {
        "rrul_p99_latency_ms": p99,
        "throughput_mbps": tput_mbps,
        "jitter_ms": p99 - p50,
        "_source": str(path),
    }


def _zone_distribution(zones: list[str]) -> dict[str, int]:
    dist = {"GREEN": 0, "YELLOW": 0, "SOFT_RED": 0, "RED": 0}
    for zone in zones:
        dist[zone] = dist.get(zone, 0) + 1
    return dist


def _rate_apply_count(rates: list[int]) -> int:
    return sum(1 for i in range(1, len(rates)) if rates[i] != rates[i - 1])


def _stats_mbps(rates: list[int]) -> tuple[float, float, float]:
    if not rates:
        return 0.0, 0.0, 0.0
    mean = statistics.mean(rates) / 1_000_000.0
    if len(rates) >= 2:
        p99 = statistics.quantiles(rates, n=100, method="inclusive")[98] / 1_000_000.0
        stdev = statistics.stdev(rates) / 1_000_000.0
    else:
        p99 = float(rates[0]) / 1_000_000.0
        stdev = 0.0
    return mean, p99, stdev


def _git_head_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _build_side(
    samples: list[GoldenSample],
    layout: str,
    controller: QueueController,
    config: dict[str, object],
    flent: dict[str, float | str] | None,
) -> dict[str, Any]:
    result = _replay_samples(samples, layout, controller)
    zones = result["zones"]
    rates = result["rates"]
    mean_mbps, p99_mbps, stdev_mbps = _stats_mbps(rates)
    side: dict[str, Any] = {
        "config": config,
        "controller_mean_rate_mbps": mean_mbps,
        "controller_rate_p99_mbps": p99_mbps,
        "controller_rate_stddev_mbps": stdev_mbps,
        "rate_trace_mbps": [r / 1_000_000.0 for r in rates],
        "zone_sequence": zones,
        "zone_distribution": _zone_distribution(zones),
        "rate_apply_count": _rate_apply_count(rates),
    }
    if flent is not None:
        side["rrul_p99_latency_ms"] = flent["rrul_p99_latency_ms"]
        side["throughput_mbps"] = flent["throughput_mbps"]
        side["jitter_ms"] = flent["jitter_ms"]
    return side


def _delta(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, pre_value in pre.items():
        post_value = post.get(key)
        if not isinstance(pre_value, (int, float)) or not isinstance(post_value, (int, float)):
            continue
        absolute = float(post_value) - float(pre_value)
        percent = (absolute / float(pre_value) * 100.0) if pre_value else 0.0
        out[key] = {"absolute": absolute, "percent": percent}
    return out


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit Phase 206 schema-v1 A/B replay JSON")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=Path("-"))
    parser.add_argument("--flent-gz-pre", type=Path)
    parser.add_argument("--flent-gz-post", type=Path)
    return parser.parse_args(argv)


def _resolve_existing(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file: {resolved}")
    return resolved


def _emit(summary: dict[str, Any], out_path: Path) -> None:
    payload = json.dumps(summary, indent=2) + "\n"
    if str(out_path) == "-":
        sys.stdout.write(payload)
        return
    resolved = out_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if bool(args.flent_gz_pre) != bool(args.flent_gz_post):
        print("ERROR: --flent-gz-pre and --flent-gz-post must be supplied together", file=sys.stderr)
        return EXIT_ABORT

    try:
        fixture_path = _resolve_existing(args.fixture, "fixture")
        fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        samples = load_golden(fixture_path)
        if args.flent_gz_pre and args.flent_gz_post:
            flent_pre = _parse_flent_rrul(_resolve_existing(args.flent_gz_pre, "flent pre"))
            flent_post = _parse_flent_rrul(_resolve_existing(args.flent_gz_post, "flent post"))
            metric_source = "flent"
        else:
            flent_pre = None
            flent_post = None
            metric_source = "controller_replay"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ABORT

    pre = _build_side(
        samples,
        "diffserv4",
        _pre_controller(),
        {"ceiling_mbps": 940, "diffserv": "diffserv4", "allow_wash": False},
        flent_pre,
    )
    post = _build_side(
        samples,
        "besteffort",
        _post_controller(),
        {"ceiling_mbps": 920, "diffserv": "besteffort", "allow_wash": True},
        flent_post,
    )

    if metric_source == "flent" and flent_pre is not None and flent_post is not None:
        pre_p99 = float(flent_pre["rrul_p99_latency_ms"])
        post_p99 = float(flent_post["rrul_p99_latency_ms"])
        pct = ((post_p99 - pre_p99) / pre_p99 * 100.0) if pre_p99 else 0.0
        gates = {
            "rrul_p99_latency_regression_pct_threshold": 5.0,
            "rrul_p99_latency_regression_pct_actual": pct,
            "rrul_p99_latency_breach": pct > 5.0,
        }
    else:
        gates = {
            "rrul_p99_latency_regression_pct_threshold": 5.0,
            "rrul_p99_latency_regression_pct_actual": None,
            "rrul_p99_latency_breach": None,
        }

    _lineage_import_guard = (_replay, _snap_for)
    assert _lineage_import_guard

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": 206,
        "fixture_provenance": str(fixture_path),
        "fixture_sha256": fixture_sha256,
        "meta": {
            "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "head_sha": _git_head_sha(),
            "tool_version": TOOL_VERSION,
            "metric_source": metric_source,
        },
        "pre": pre,
        "post": post,
        "delta": _delta(pre, post),
        "gates": gates,
    }
    _emit(summary, args.out)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

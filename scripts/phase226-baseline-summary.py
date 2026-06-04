#!/usr/bin/env python3
"""Phase 226 baseline summary helper.

Parses per-run CAKE ``tc -s qdisc`` before/during/after triples and continuous
Spectrum health windows into the baseline JSON/Markdown shape consumed by the
v1.49 A/B gates.  The counter semantics are deliberately delta-based: CAKE tin
counters are cumulative since qdisc creation, so the per-run value is
``during - before`` with ``after - before`` retained as a cross-check.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


TIN_RE = re.compile(r"^\s*Tin\s+(?P<name>\S+)")
KV_RE = re.compile(r"(?P<key>Sent|Dropped|Backlog)\s+(?P<value>[0-9]+)")
DELAY_RE = re.compile(r"(?P<label>Avge|Peak)\s+delay\s+(?P<value>[0-9.]+)(?P<unit>us|ms|s)")


@dataclass(frozen=True)
class TinCounters:
    name: str
    packets: int = 0
    drops: int = 0
    backlog_bytes: int = 0
    avg_delay_ms: float = 0.0
    peak_delay_ms: float = 0.0


def _to_ms(value: str, unit: str) -> float:
    raw = float(value)
    if unit == "us":
        return raw / 1000.0
    if unit == "s":
        return raw * 1000.0
    return raw


def parse_tc_qdisc(text: str) -> dict[str, TinCounters]:
    """Parse CAKE tin counters from ``tc -s qdisc show`` text."""
    tins: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for line in text.splitlines():
        tin_match = TIN_RE.match(line)
        if tin_match:
            current = tin_match.group("name")
            tins.setdefault(current, {"name": current})
            continue
        if current is None:
            continue
        kv_match = KV_RE.search(line)
        if kv_match:
            key = kv_match.group("key")
            value = int(kv_match.group("value"))
            if key == "Sent":
                tins[current]["packets"] = value
            elif key == "Dropped":
                tins[current]["drops"] = value
            elif key == "Backlog":
                tins[current]["backlog_bytes"] = value
        delay_match = DELAY_RE.search(line)
        if delay_match:
            label = delay_match.group("label")
            ms = _to_ms(delay_match.group("value"), delay_match.group("unit"))
            if label == "Avge":
                tins[current]["avg_delay_ms"] = ms
            elif label == "Peak":
                tins[current]["peak_delay_ms"] = ms
    return {name: TinCounters(**values) for name, values in tins.items()}


def _delta(cur: int, before: int) -> int:
    return max(0, cur - before)


def compute_tin_deltas(
    before: dict[str, TinCounters],
    during: dict[str, TinCounters],
    after: dict[str, TinCounters],
) -> dict[str, dict[str, Any]]:
    """Compute per-run during-before deltas with after-before cross-checks."""
    rows: dict[str, dict[str, Any]] = {}
    for tin in sorted(set(before) | set(during) | set(after)):
        b = before.get(tin, TinCounters(name=tin))
        d = during.get(tin, TinCounters(name=tin))
        a = after.get(tin, TinCounters(name=tin))
        rows[tin] = {
            "tin": tin,
            "packets_delta": _delta(d.packets, b.packets),
            "drops_delta": _delta(d.drops, b.drops),
            "backlog_bytes_delta": _delta(d.backlog_bytes, b.backlog_bytes),
            "after_packets_delta": _delta(a.packets, b.packets),
            "after_drops_delta": _delta(a.drops, b.drops),
            "after_backlog_bytes_delta": _delta(a.backlog_bytes, b.backlog_bytes),
            "avg_delay_ms": d.avg_delay_ms,
            "peak_delay_ms": d.peak_delay_ms,
            "after_minus_before_ge_during": (
                _delta(a.packets, b.packets) >= _delta(d.packets, b.packets)
                and _delta(a.drops, b.drops) >= _delta(d.drops, b.drops)
                and _delta(a.backlog_bytes, b.backlog_bytes) >= _delta(d.backlog_bytes, b.backlog_bytes)
            ),
        }
    return rows


def parse_health_window(path: Path) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            samples.append(json.loads(line))
    if not samples:
        return {
            "sample_count": 0,
            "duration_s": 0.0,
            "restart_rate": 0.0,
            "transition_rate": 0.0,
            "floor_hit_cycles": 0,
            "soft_red_dwell_s": 0.0,
            "max_gap_s": None,
            "health_up": False,
        }

    def ts(sample: dict[str, Any]) -> float:
        return float(sample.get("sampled_unix") or sample.get("timestamp_unix") or sample.get("ts") or 0)

    times = [ts(sample) for sample in samples]
    duration = max(times) - min(times) if len(times) > 1 else float(len(samples))
    duration = max(duration, 1.0)
    max_gap = max((b - a for a, b in zip(times, times[1:])), default=0.0)
    restarts = 0
    floor_hits = 0
    soft_red_dwell = 0.0
    states: list[str] = []
    last_restart: float | int | None = None

    for sample in samples:
        restart_value = sample.get("restart_count") or sample.get("daemon_restart_count")
        if restart_value is None:
            restart_value = sample.get("process", {}).get("restart_count") if isinstance(sample.get("process"), dict) else None
        if isinstance(restart_value, (int, float)):
            if last_restart is not None and restart_value > last_restart:
                restarts += int(restart_value - last_restart)
            last_restart = restart_value

        wans = sample.get("wans")
        spectrum = None
        if isinstance(wans, list):
            spectrum = next((wan for wan in wans if wan.get("name") == "spectrum"), None)
        if spectrum is None and isinstance(sample.get("spectrum"), dict):
            spectrum = sample["spectrum"]
        if spectrum is None:
            spectrum = sample

        state = (
            spectrum.get("pressure_state")
            or spectrum.get("state")
            or spectrum.get("download", {}).get("state", "")
        )
        states.append(str(state))
        upload = spectrum.get("upload", {}) if isinstance(spectrum.get("upload"), dict) else {}
        floor_hits += int(upload.get("floor_hit_cycles") or spectrum.get("floor_hit_cycles") or 0)

    transitions = sum(1 for a, b in zip(states, states[1:]) if a != b)
    for prev, cur, nxt in zip(times, states, times[1:]):
        if cur == "SOFT_RED":
            soft_red_dwell += max(0.0, nxt - prev)
    return {
        "sample_count": len(samples),
        "duration_s": duration,
        "restart_rate": restarts / duration,
        "transition_rate": transitions / duration,
        "floor_hit_cycles": floor_hits,
        "soft_red_dwell_s": soft_red_dwell,
        "max_gap_s": max_gap,
        "health_up": True,
    }


def _read_tc(path: Path) -> dict[str, TinCounters]:
    return parse_tc_qdisc(path.read_text(encoding="utf-8", errors="replace"))


def _mean(values: list[float | int]) -> float:
    return float(mean(values)) if values else 0.0


def _spread(values: list[float]) -> dict[str, float]:
    if not values:
        return {"tin_queue_delay_spread_ms": 0.0, "stddev_ms": 0.0}
    return {
        "tin_queue_delay_spread_ms": float(max(values) - min(values)),
        "stddev_ms": float(pstdev(values)) if len(values) > 1 else 0.0,
    }


def _flent_p99_ms(path: Path) -> float | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception:
        return None
    series: list[float] = []
    for key, values in (data.get("results") or {}).items():
        if "ping" in key.lower() and isinstance(values, list):
            series.extend(float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    if not series:
        return None
    series.sort()
    idx = min(len(series) - 1, math.ceil(len(series) * 0.99) - 1)
    return series[idx]


def build_summary(capture_dir: Path) -> dict[str, Any]:
    runs = sorted(path for path in capture_dir.glob("run-*") if path.is_dir())
    by_iface: dict[str, dict[str, list[dict[str, Any]]]] = {}
    windows: list[dict[str, Any]] = []
    rrul_p99s: list[float] = []
    for run_dir in runs:
        for iface in ("spec-router", "spec-modem"):
            before = _read_tc(run_dir / f"tc-qdisc-{iface}.before.txt")
            during = _read_tc(run_dir / f"tc-qdisc-{iface}.during.txt")
            after = _read_tc(run_dir / f"tc-qdisc-{iface}.after.txt")
            deltas = compute_tin_deltas(before, during, after)
            for tin, row in deltas.items():
                by_iface.setdefault(iface, {}).setdefault(tin, []).append(row)
        health_path = run_dir / "health.window.ndjson"
        if health_path.exists():
            windows.append(parse_health_window(health_path))
        rrul = _flent_p99_ms(run_dir / f"flent-rrul.{run_dir.name[-2:]}.flent.gz")
        if rrul is not None:
            rrul_p99s.append(rrul)

    interfaces: dict[str, Any] = {}
    for iface, tins in by_iface.items():
        interfaces[iface] = {}
        for tin, rows in tins.items():
            delays = [float(row["avg_delay_ms"]) for row in rows]
            interfaces[iface][tin] = {
                "runs": rows,
                "mean_packets_delta": _mean([row["packets_delta"] for row in rows]),
                "mean_drops_delta": _mean([row["drops_delta"] for row in rows]),
                "mean_backlog_bytes_delta": _mean([row["backlog_bytes_delta"] for row in rows]),
                "mean_delay_delta_ms": _mean(delays),
                **_spread(delays),
            }

    duration = _mean([window["duration_s"] for window in windows]) or 1.0
    baseline_window = {
        "restart_rate": _mean([window["restart_rate"] for window in windows]),
        "transition_rate": _mean([window["transition_rate"] for window in windows]),
        "floor_hit_cycles": int(sum(window["floor_hit_cycles"] for window in windows)),
        "soft_red_dwell_s": sum(float(window["soft_red_dwell_s"]) for window in windows),
        "mean_window_duration_s": duration,
        "windows": windows,
    }
    return {
        "phase": 226,
        "schema_version": 1,
        "run_count": len(runs),
        "interfaces": interfaces,
        "baseline_window": baseline_window,
        "rrul_p99_latency_under_load_ms_mean": _mean(rrul_p99s),
        "provenance": {"D-07": "RRUL plus unmarked reference flows", "D-08": "3 runs x 60s mean plus spread"},
    }


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Phase 226 Baseline Summary",
        "",
        "Provenance: D-07 RRUL + concurrent unmarked UDP/TCP references; D-08 3 runs x 60s with mean + spread.",
        "",
        "## Per-tin DELTA table",
        "",
        "| Interface | Tin | Mean packets DELTA | Mean drops DELTA | Mean backlog DELTA bytes | Mean DELTA delay ms | tin_queue_delay_spread_ms | Stddev ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for iface, tins in sorted(summary["interfaces"].items()):
        for tin, row in sorted(tins.items()):
            lines.append(
                f"| {iface} | {tin} | {row['mean_packets_delta']:.3f} | {row['mean_drops_delta']:.3f} | "
                f"{row['mean_backlog_bytes_delta']:.3f} | {row['mean_delay_delta_ms']:.3f} | "
                f"{row['tin_queue_delay_spread_ms']:.3f} | {row['stddev_ms']:.3f} |"
            )
    bw = summary["baseline_window"]
    lines.extend([
        "",
        "## baseline_window",
        "",
        f"- restart_rate: {bw['restart_rate']:.6f}",
        f"- transition_rate: {bw['transition_rate']:.6f}",
        f"- floor_hit_cycles: {bw['floor_hit_cycles']}",
        f"- soft_red_dwell_s: {bw['soft_red_dwell_s']:.3f}",
        "",
        "## RRUL latency-under-load headline",
        "",
        f"- D-01 p99 latency-under-load mean: {summary['rrul_p99_latency_under_load_ms_mean']:.3f} ms",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.output_json or args.capture_dir / "baseline-summary.json"
    out_md = args.output_md or args.capture_dir / "BASELINE-SUMMARY.md"
    summary = build_summary(args.capture_dir)
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(summary, out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

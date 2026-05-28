#!/usr/bin/env python3
"""Phase 214 aligned-window driver classifier.

Reads the aligned-window JSON emitted by phase214-align.py, applies the six
MEAS-02 evidence drivers, extracts flent latency through the Phase 214
fail-closed extractor, and emits per-window signal-sheet JSON/Markdown.

Invariants: stdlib-only; no production package imports; observational-only
output per D-12/D-13; no controller field additions, threshold tuning,
production mutation recommendations, or Phase 213 back-edits (D-11).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

DRIVER_P99_FAIL_MS = 1000
DRIVER_P99_PASS_MS = 500
DRIVER_REFLECTOR_LOSS_MIN_CYCLES = 1
DRIVER_REFLECTOR_LOSS_LOW_SUCCESS_RUN = 3
DRIVER_STALE_RTT_MIN_CYCLES = 3
DRIVER_CAKE_PEAK_DELAY_US = 50000
JOURNAL_PROTO_DIVERGENCE_REGEX = r"(?i)(ICMP|UDP)\s+deprioritized|Fusion healer.*->\s*suspended"
JOURNAL_REFLECTOR_FAIL_REGEX = r"Ping to \S+ failed"
JOURNAL_REFLECTOR_DEPRIORITIZED_REGEX = r"Reflector \S+ deprioritized"
DRIVER_NAMES = [
    "reflector_loss",
    "icmp_udp_divergence",
    "stale_cached_rtt",
    "steering_behavior",
    "cake_queue_mismatch",
    "external_path",
]

_EXTRACT_PATH = Path(__file__).resolve().parent / "phase214-extract.py"
_spec = importlib.util.spec_from_file_location("phase214_extract", _EXTRACT_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - importlib guard
    raise ImportError(f"Unable to load {_EXTRACT_PATH}")
_phase214_extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_phase214_extract)

FlentExtractionError = _phase214_extract.FlentExtractionError
extract_flent_latency = _phase214_extract.extract_flent_latency


def _base_driver(fired: bool = False, evidence: str = "no matching evidence", score: int = 0, first_unix: int | None = None) -> dict[str, Any]:
    return {"fired": fired, "evidence": evidence, "score": score, "first_unix": first_unix}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _message(event: dict[str, Any]) -> str:
    return str(event.get("message") or event.get("MESSAGE") or "")


def _event_unix(event: dict[str, Any], fallback: int | None = None) -> int | None:
    for key in ("ts", "t_unix"):
        try:
            return int(float(event[key]))
        except (KeyError, TypeError, ValueError):
            pass
    raw = event.get("__REALTIME_TIMESTAMP")
    try:
        return int(int(str(raw)) / 1_000_000)
    except (TypeError, ValueError):
        return fallback


def _events(rows: list[dict[str, Any]]) -> list[tuple[int | None, dict[str, Any]]]:
    out: list[tuple[int | None, dict[str, Any]]] = []
    for row in rows:
        row_ts = _int(row.get("t_unix"))
        for event in row.get("journal_events") or []:
            if isinstance(event, dict):
                out.append((_event_unix(event, row_ts), event))
    return out


def _analyze_reflector_loss(rows: list[dict[str, Any]]) -> dict[str, Any]:
    zero_rows = [row for row in rows if _int(row.get("measurement_successful_count")) == 0]
    low_run = 0
    max_low_run = 0
    zero_run = 0
    max_zero_run = 0
    for row in rows:
        count = _int(row.get("measurement_successful_count"))
        if count is not None and count <= 1:
            low_run += 1
        else:
            low_run = 0
        max_low_run = max(max_low_run, low_run)
        if count == 0:
            zero_run += 1
        else:
            zero_run = 0
        max_zero_run = max(max_zero_run, zero_run)

    reflector_events: list[tuple[int | None, dict[str, Any]]] = []
    deprioritized_events: list[tuple[int | None, dict[str, Any]]] = []
    for ts, event in _events(rows):
        msg = _message(event)
        if re.search(JOURNAL_REFLECTOR_FAIL_REGEX, msg):
            reflector_events.append((ts, event))
        if re.search(JOURNAL_REFLECTOR_DEPRIORITIZED_REGEX, msg):
            deprioritized_events.append((ts, event))

    rolling_ips = False
    sorted_events = sorted((ts, event) for ts, event in reflector_events if ts is not None)
    for idx, (start_ts, _) in enumerate(sorted_events):
        ips: set[str] = set()
        for ts, event in sorted_events[idx:]:
            if ts - start_ts > 10:
                break
            match = re.search(r"Ping to (\S+) failed", _message(event))
            if match:
                ips.add(match.group(1))
        if len(ips) >= 3:
            rolling_ips = True
            break

    fired = bool(zero_rows) or max_low_run >= DRIVER_REFLECTOR_LOSS_LOW_SUCCESS_RUN or rolling_ips or bool(deprioritized_events)
    score = len(zero_rows) + len(reflector_events) + len(deprioritized_events)
    if max_low_run >= DRIVER_REFLECTOR_LOSS_LOW_SUCCESS_RUN:
        score += max_low_run
    first_candidates = [_int(row.get("t_unix")) for row in zero_rows]
    first_candidates.extend(ts for ts, _event in reflector_events + deprioritized_events if ts is not None)
    evidence = (
        f"{len(zero_rows)} zero-success cycles; max low-success run {max_low_run}; "
        f"{len(reflector_events)} reflector fail events; {len(deprioritized_events)} reflector deprioritization events"
    )
    driver = _base_driver(fired, evidence if fired else "no reflector-loss evidence", score if fired else 0, min(first_candidates) if first_candidates else None)
    driver["consecutive_zero_cycles"] = max_zero_run
    driver["total_zero_cycles"] = len(zero_rows)
    return driver


def _analyze_icmp_udp_divergence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    proto_events = [(ts, event) for ts, event in _events(rows) if re.search(JOURNAL_PROTO_DIVERGENCE_REGEX, _message(event))]
    load_values = [_num(row.get("load_rtt_ms")) for row in rows if _num(row.get("load_rtt_ms")) is not None]
    stable_load = bool(load_values) and max(load_values) - min(load_values) < 5
    irtt_missing_rows = [row for row in rows if row.get("irtt_rtt_mean_ms") is None]
    secondary_fired = stable_load and bool(irtt_missing_rows)
    fired = bool(proto_events) or secondary_fired
    score = len(proto_events) + (len(irtt_missing_rows) if secondary_fired else 0)
    first_candidates = [ts for ts, _event in proto_events if ts is not None]
    first_candidates.extend(_int(row.get("t_unix")) for row in irtt_missing_rows if _int(row.get("t_unix")) is not None)
    evidence = f"{len(proto_events)} protocol divergence journal events; {len(irtt_missing_rows) if secondary_fired else 0} IRTT-missing stable-load cycles"
    return _base_driver(fired, evidence if fired else "no ICMP/UDP divergence evidence", score if fired else 0, min(first_candidates) if first_candidates else None)


def _analyze_stale_cached_rtt(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stale_rows = [row for row in rows if row.get("measurement_stale") is True]
    unchanged_stale = 0
    for prev, cur in zip(rows, rows[1:], strict=False):
        cur_staleness = _num(cur.get("measurement_staleness_sec")) or 0.0
        if cur_staleness > 0.5 and _num(prev.get("load_rtt_ms")) == _num(cur.get("load_rtt_ms")):
            unchanged_stale += 1
    fired = len(stale_rows) >= DRIVER_STALE_RTT_MIN_CYCLES or unchanged_stale > 0
    score = len(stale_rows) + unchanged_stale
    first = min((_int(row.get("t_unix")) for row in stale_rows if _int(row.get("t_unix")) is not None), default=None)
    evidence = f"{len(stale_rows)} stale cycles; {unchanged_stale} stale unchanged-load pairs"
    return _base_driver(fired, evidence if fired else "no stale cached RTT evidence", score if fired else 0, first)


def _analyze_steering_behavior(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = []
    for ts, event in _events(rows):
        unit = str(event.get("_SYSTEMD_UNIT") or event.get("unit") or "")
        if unit == "steering.service" or "steering" in _message(event).lower():
            events.append((ts, event))
    alerts = []
    for row in rows:
        for alert in row.get("alerts_in_second") or []:
            if isinstance(alert, dict) and str(alert.get("alert_type") or alert.get("type") or "").startswith("steering_"):
                alerts.append((_int(row.get("t_unix")), alert))
    fired = bool(events or alerts)
    first = min((ts for ts, _obj in events + alerts if ts is not None), default=None)
    evidence = f"{len(events)} steering journal events; {len(alerts)} steering alerts"
    return _base_driver(fired, evidence if fired else "no steering behavior evidence", len(events) + len(alerts) if fired else 0, first)


def _analyze_cake_queue_mismatch(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [row for row in rows if (_num(row.get("cake_dl_peak_delay_us")) or 0) > DRIVER_CAKE_PEAK_DELAY_US and row.get("download_state") == "GREEN"]
    first = min((_int(row.get("t_unix")) for row in matches if _int(row.get("t_unix")) is not None), default=None)
    evidence = f"{len(matches)} GREEN cycles with CAKE DL peak delay above {DRIVER_CAKE_PEAK_DELAY_US}us"
    return _base_driver(bool(matches), evidence if matches else "no CAKE queue mismatch evidence", len(matches), first)


def _analyze_external_path(rows: list[dict[str, Any]], prior_fired: bool) -> dict[str, Any]:
    outlier_values = [_num(row.get("signal_outlier_rate")) for row in rows if _num(row.get("signal_outlier_rate")) is not None]
    mean_outlier = sum(outlier_values) / len(outlier_values) if outlier_values else 0.0
    fired = not prior_fired and mean_outlier <= 0.1
    return _base_driver(fired, f"no signal driver matched; mean signal_outlier_rate={mean_outlier:.3f}" if fired else "not evaluated because another driver fired", 0, _int(rows[0].get("t_unix")) if fired else None)


def classify(aligned_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply all six drivers to in-window rows and return primary + ranked evidence."""
    in_window = [row for row in aligned_rows if row.get("in_flent_window")]
    if not in_window:
        return {"primary_driver": None, "ranked": [], "drivers": {}}

    drivers: dict[str, dict[str, Any]] = {
        "reflector_loss": _analyze_reflector_loss(in_window),
        "icmp_udp_divergence": _analyze_icmp_udp_divergence(in_window),
        "stale_cached_rtt": _analyze_stale_cached_rtt(in_window),
        "steering_behavior": _analyze_steering_behavior(in_window),
        "cake_queue_mismatch": _analyze_cake_queue_mismatch(in_window),
    }
    drivers["external_path"] = _analyze_external_path(in_window, any(driver["fired"] for driver in drivers.values()))
    ranked = [name for name, _driver in sorted(((name, driver) for name, driver in drivers.items() if driver["fired"]), key=lambda item: (-int(item[1].get("score") or 0), item[0]))]
    primary_driver = ranked[0] if ranked else "external_path"
    return {"primary_driver": primary_driver, "ranked": ranked, "drivers": drivers}


def verdict_for_window(latency: dict[str, Any], drivers: dict[str, dict[str, Any]]) -> str:
    """Return pass/fail/ambiguous per D-06 boundaries."""
    p99 = float(latency["p99_ms"])
    if p99 < DRIVER_P99_PASS_MS and not drivers.get("reflector_loss", {}).get("fired") and not drivers.get("icmp_udp_divergence", {}).get("fired"):
        return "pass"
    if p99 > DRIVER_P99_FAIL_MS and any(driver.get("fired") for driver in drivers.values()):
        return "fail"
    return "ambiguous"


def _evidence_summary(classification: dict[str, Any]) -> str:
    primary = classification.get("primary_driver")
    if primary is None:
        return "No in-window aligned rows were available to classify."
    driver = classification.get("drivers", {}).get(primary, {})
    return f"Primary driver {primary}: {driver.get('evidence', 'no evidence summary')}"


def build_signal_sheet(
    aligned_rows: list[dict[str, Any]],
    latency: dict[str, Any],
    drivers: dict[str, Any],
    verdict: str,
    window_label: str,
    run_dir: str,
    wan: str = "spectrum",
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Roll up classifier output, verdict, metadata, and signal disposition."""
    classification = drivers if "primary_driver" in drivers else {"drivers": drivers, "ranked": [], "primary_driver": None}
    latency_keys = ["p50_ms", "p95_ms", "p99_ms", "sample_count", "mean_ms", "min_ms", "max_ms", "window_start_utc", "window_end_utc"]
    signal_disposition = "form_b" if verdict == "fail" else "none"
    return {
        "phase": 214,
        "run_dir": run_dir,
        "started_utc": str(latency.get("window_start_utc") or ""),
        "ended_utc": str(latency.get("window_end_utc") or ""),
        "window": window_label,
        "wan": wan,
        "artifact_paths": artifact_paths or {},
        "latency": {key: latency.get(key) for key in latency_keys if key in latency},
        "verdict": verdict,
        "primary_driver": classification.get("primary_driver"),
        "ranked": classification.get("ranked", []),
        "drivers": classification.get("drivers", {}),
        "signal_disposition": signal_disposition,
        "evidence_summary": _evidence_summary(classification),
        "aligned_row_count": len(aligned_rows),
    }


def write_markdown(signal_sheet: dict[str, Any], out_md: Path) -> None:
    """Emit an operator-facing per-window signal sheet."""
    lines = [
        "# Phase 214 Signal Sheet",
        "",
        f"Run: `{signal_sheet['run_dir']}`",
        f"Window: `{signal_sheet['window']}`",
        f"WAN: `{signal_sheet['wan']}`",
        f"Verdict: `{signal_sheet['verdict']}`",
        f"Primary driver: `{signal_sheet['primary_driver']}`",
        "",
        "## Latency",
        "",
        "```json",
        json.dumps(signal_sheet["latency"], indent=2, sort_keys=True),
        "```",
        "",
        "## Ranked Drivers",
        "",
    ]
    for name in signal_sheet.get("ranked", []):
        driver = signal_sheet["drivers"].get(name, {})
        lines.append(f"- `{name}` score={driver.get('score', 0)} — {driver.get('evidence', '')}")
    if not signal_sheet.get("ranked"):
        lines.append("- No ranked driver evidence.")
    lines.extend(["", "## Evidence Summary", "", signal_sheet.get("evidence_summary", ""), "", "## Signal Disposition", ""])
    if signal_sheet["verdict"] == "fail":
        lines.extend(
            [
                "Form B: this offline signal-sheet rule records the reproduced measurement-quality driver as observational evidence only.",
                "Form C: a future alert design is recommended for operator visibility, also observational and deferred to a follow-up phase.",
                "Form A: a health degraded-quality field is a future-phase implementation candidate, NOT implemented in Phase 214.",
            ]
        )
    else:
        lines.append("No signal change needed for this window; the classifier remains observational and records the evidence only.")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aligned-window", required=True, type=Path)
    parser.add_argument("--flent-gz", required=True, type=Path)
    parser.add_argument("--health-ndjson", type=Path)
    parser.add_argument("--journal-ndjson", type=Path)
    parser.add_argument("--window-label", required=True, choices=["off-peak", "daytime", "prime-time", "att-contrast"])
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--wan", default="spectrum", choices=["spectrum", "att"])
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        aligned_rows = json.loads(args.aligned_window.read_text(encoding="utf-8"))
        if not isinstance(aligned_rows, list):
            raise TypeError("aligned-window JSON must be a list")
        latency = extract_flent_latency(args.flent_gz)
        classification = classify([row for row in aligned_rows if isinstance(row, dict)])
        verdict = verdict_for_window(latency, classification.get("drivers", {}))
    except (FlentExtractionError, OSError, json.JSONDecodeError, TypeError) as exc:
        prefix = "FlentExtractionError" if isinstance(exc, FlentExtractionError) else type(exc).__name__
        print(f"{prefix}: {exc}", file=sys.stderr)
        return 1

    artifact_paths = {
        "flent_gz": str(args.flent_gz),
        "health_ndjson": str(args.health_ndjson) if args.health_ndjson else "",
        "journal_ndjson": str(args.journal_ndjson) if args.journal_ndjson else "",
        "aligned_window_json": str(args.aligned_window),
    }
    run_dir = args.run_dir or args.aligned_window.parent.name
    sheet = build_signal_sheet(aligned_rows, latency, classification, verdict, args.window_label, run_dir, args.wan, artifact_paths)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(sheet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(sheet, args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

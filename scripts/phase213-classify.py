#!/usr/bin/env python3
"""Phase 213 offline signal-sheet emitter.

Reads a Phase 213 per-run evidence tree (RUN-<ts>/<wan>/<test>/) containing
health NDJSON, alert-window JSON, steering pre/post snapshots, normalized flent
artifacts, and browse CSV rows. Emits signal-sheet.json and signal-sheet.md
inside the run dir per MEDIUM-5.

Invariants: stdlib-only; no wanctl imports; D-13 hybrid signal sheet, D-14 raw
steering evidence only, D-15 ranked next-phase recommendation, MEDIUM-1 six
bucket coverage, and MEDIUM-2 upload ceiling/plan caps sourced from
configs/<wan>.yaml or row metadata, never from Spectrum-specific arithmetic.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

BUCKET_1_PCT_AT_CEILING = 0.80
BUCKET_2_TIME_TO_GREEN_SEC = 30
BUCKET_2_PEAK_DELAY_US = 50000
BUCKET_3_OUTLIER_RATE_MAX = 0.30
BUCKET_3_P99_VS_MEDIAN_MULT = 5
BUCKET_5_PCT_REFRACTORY_ACTIVE = 0.05
BUCKET_5_BACKLOG_SUPPRESSED_DELTA = 100
BUCKET_6_THROUGHPUT_DROP_PCT = 0.30
BUCKET_6_TTFB_P99_MS = 2000
BUCKET_6_OUTLIER_RATE_MAX = 0.10

BUCKET_KEYS = [
    "upload_ceiling_setpoint",
    "download_recovery_lag",
    "measurement_collapse",
    "steering_drift",
    "refractory_semantics",
    "external_isp",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_wan_config(wan_name: str) -> dict[str, dict[str, float]]:
    path = _repo_root() / "configs" / f"{wan_name}.yaml"
    out: dict[str, dict[str, float]] = {"upload": {}, "download": {}, "plan": {}}
    section: str | None = None
    in_monitoring = False
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^continuous_monitoring:\s*$", line):
            in_monitoring = True
            section = None
            continue
        if not in_monitoring:
            continue
        if re.match(r"^[A-Za-z_].*:\s*$", line):
            break
        m_section = re.match(r"^\s{2}(upload|download):\s*$", line)
        if m_section:
            section = m_section.group(1)
            continue
        m_value = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([0-9.]+)", line)
        if section and m_value:
            key, value = m_value.groups()
            try:
                out[section][key] = float(value)
            except ValueError:
                pass
    if "ceiling_mbps" in out["download"]:
        out["plan"]["download_mbps"] = out["download"]["ceiling_mbps"]
    if "ceiling_mbps" in out["upload"]:
        out["plan"]["upload_mbps"] = out["upload"]["ceiling_mbps"]
    return out


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _all_health_rows(run_dir: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for wan_dir in run_dir.iterdir() if run_dir.exists() else []:
        if not wan_dir.is_dir():
            continue
        for test_dir in wan_dir.iterdir():
            if test_dir.is_dir():
                rows: list[dict[str, Any]] = []
                for ndjson in test_dir.glob("health-*.ndjson"):
                    rows.extend(_read_ndjson(ndjson))
                out[(wan_dir.name, test_dir.name)] = rows
    return out


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * q))))
    return float(values[idx])


def _bucket(flagged: bool, rows: list[dict[str, Any]], note: str) -> dict[str, Any]:
    return {"flagged": bool(flagged), "evidence_rows": rows, "operator_note": note}


def analyze_upload_ceiling(data: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for (wan, test), rows in data.items():
        if test != "tcp_upload" or not rows:
            continue
        config = _read_wan_config(wan)
        # Ceiling sourced from configs/<wan>.yaml upload.ceiling_mbps (or row metadata) per MEDIUM-2.
        ceiling = rows[0].get("upload_ceiling_mbps") or config.get("upload", {}).get("ceiling_mbps")
        if ceiling is None:
            continue
        at_ceiling = [r for r in rows if float(r.get("upload_rate_mbps") or 0) >= float(ceiling) - 0.5]
        pct = len(at_ceiling) / max(len(rows), 1)
        evidence.append({"wan": wan, "test": test, "upload_ceiling_mbps": ceiling, "pct_samples_at_ceiling": round(pct, 4), "sample_count": len(rows)})
    flagged = any(r["pct_samples_at_ceiling"] > BUCKET_1_PCT_AT_CEILING for r in evidence)
    return _bucket(flagged, evidence, "Upload samples pegged near configured per-WAN ceiling." if flagged else "No upload ceiling peg detected.")


def analyze_download_recovery(data: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for (wan, test), rows in data.items():
        if test not in {"tcp_12down", "rrul"} or not rows:
            continue
        last_red_idx = None
        green_after = None
        for idx, row in enumerate(rows):
            if str(row.get("download_state")) in {"RED", "SOFT_RED"}:
                last_red_idx = idx
                green_after = None
            elif last_red_idx is not None and str(row.get("download_state")) == "GREEN":
                if float(row.get("download_green_streak") or 0) >= float(row.get("download_green_required") or 0):
                    green_after = idx - last_red_idx
                    break
        delays = [float(r.get("cake_dl_peak_delay_us") or 0) for r in rows]
        peak_p99 = _pct(delays, 0.99)
        lag = float(green_after or 0)
        evidence.append({"wan": wan, "test": test, "time_to_green_after_red_sec": lag, "cake_dl_peak_delay_us_p99": peak_p99})
    flagged = any(r["time_to_green_after_red_sec"] > BUCKET_2_TIME_TO_GREEN_SEC or r["cake_dl_peak_delay_us_p99"] > BUCKET_2_PEAK_DELAY_US for r in evidence)
    return _bucket(flagged, evidence, "Download recovery lag or CAKE delay exceeded threshold." if flagged else "No download recovery lag threshold exceeded.")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _flent_summary(test_dir: Path) -> dict[str, float]:
    candidates = [test_dir / "flent-summary.json"] + list(test_dir.glob("flent/flent-summary.json")) + list(test_dir.glob("flent/*summary*.json"))
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict):
            if isinstance(data.get("throughput"), dict):
                tp = data["throughput"]
                return {
                    "throughput_p99": float(tp.get("p99") or tp.get("p99_mbps") or 0),
                    "throughput_median": float(tp.get("median") or tp.get("median_mbps") or 0),
                    "plan_mbps": float(tp.get("plan_mbps") or 0),
                }
            out: dict[str, float] = {}
            for key in ("throughput_p99", "throughput_median", "median_mbps", "p99_mbps", "plan_mbps"):
                if key in data and isinstance(data[key], (int, float)):
                    out[key] = float(data[key])
            if out:
                return out
    return {}


def analyze_measurement_collapse(run_dir: Path, data: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for (wan, test), rows in data.items():
        if not rows:
            continue
        outlier = max(float(r.get("signal_outlier_rate") or 0) for r in rows)
        summary = _flent_summary(run_dir / wan / test)
        p99 = summary.get("throughput_p99") or summary.get("p99_mbps") or 0.0
        median = summary.get("throughput_median") or summary.get("median_mbps") or 0.0
        evidence.append({"wan": wan, "test": test, "signal_outlier_rate_max": outlier, "flent_p99": p99, "flent_median": median})
    flagged = any(r["signal_outlier_rate_max"] > BUCKET_3_OUTLIER_RATE_MAX and r["flent_median"] > 0 and r["flent_p99"] > r["flent_median"] * BUCKET_3_P99_VS_MEDIAN_MULT for r in evidence)
    return _bucket(flagged, evidence, "Measurement outliers and flent distribution spread suggest collapse." if flagged else "No measurement-collapse threshold crossed.")


def _counter(obj: Any, key: str) -> float:
    if not isinstance(obj, dict):
        return 0.0
    val = obj.get(key)
    if isinstance(val, (int, float)):
        return float(val)
    total = 0.0
    for child in obj.values():
        total += _counter(child, key)
    return total


def analyze_steering_drift(run_dir: Path) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for test_dir in run_dir.glob("*/*"):
        if not test_dir.is_dir():
            continue
        pre = _read_json(test_dir / "steering-pre-state.redacted.json") or _read_json(test_dir / "steering-pre-health.json")
        post = _read_json(test_dir / "steering-post-state.redacted.json") or _read_json(test_dir / "steering-post-health.json")
        if pre is None and post is None:
            continue
        wan = test_dir.parent.name
        test = test_dir.name
        row = {
            "wan": wan,
            "test": test,
            "pre_post_state_transition": f"{_state_string(pre)} -> {_state_string(post)}",
            "red_count_delta": _counter(post, "red_count") - _counter(pre, "red_count"),
            "good_count_delta": _counter(post, "good_count") - _counter(pre, "good_count"),
            "cake_read_failures_delta": _counter(post, "cake_read_failures") - _counter(pre, "cake_read_failures"),
            "green_rtt_ms": _nested_key(post, "green_rtt_ms"),
            "yellow_rtt_ms": _nested_key(post, "yellow_rtt_ms"),
            "red_rtt_ms": _nested_key(post, "red_rtt_ms"),
            "red_samples_required": _nested_key(post, "red_samples_required"),
            "green_samples_required": _nested_key(post, "green_samples_required"),
        }
        evidence.append(row)
    flagged = any(r["pre_post_state_transition"].split(" -> ")[0] != r["pre_post_state_transition"].split(" -> ")[1] or r["red_count_delta"] or r["good_count_delta"] or r["cake_read_failures_delta"] for r in evidence)
    return _bucket(flagged, evidence, "Raw steering state/counter delta observed; threshold names are recorded only." if flagged else "No raw steering transition or counter delta observed.")


def _state_string(obj: Any) -> str:
    if not isinstance(obj, dict):
        return "missing"
    for key in ("state", "status", "active_wan", "decision"):
        val = obj.get(key)
        if isinstance(val, str):
            return val
    return "present"


def _nested_key(obj: Any, key: str) -> Any:
    if not isinstance(obj, dict):
        return None
    if key in obj:
        return obj[key]
    for child in obj.values():
        val = _nested_key(child, key)
        if val is not None:
            return val
    return None


def analyze_refractory(data: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for (wan, test), rows in data.items():
        if not rows:
            continue
        refractory = sum(1 for r in rows if bool(r.get("arb_refractory_active"))) / len(rows)
        vals = [float(r.get("cake_dl_backlog_suppressed_count") or 0) + float(r.get("cake_ul_backlog_suppressed_count") or 0) for r in rows]
        delta = (max(vals) - min(vals)) if vals else 0.0
        evidence.append({"wan": wan, "test": test, "pct_samples_refractory_active": round(refractory, 4), "backlog_suppressed_delta": delta})
    flagged = any(r["pct_samples_refractory_active"] > BUCKET_5_PCT_REFRACTORY_ACTIVE or r["backlog_suppressed_delta"] > BUCKET_5_BACKLOG_SUPPRESSED_DELTA for r in evidence)
    return _bucket(flagged, evidence, "Refractory/backlog suppression activity observed during test windows." if flagged else "No refractory threshold crossed.")


def _browse_ttfb_p99(test_dir: Path) -> float:
    path = test_dir / "browse.curl.csv"
    if not path.exists():
        return 0.0
    vals: list[float] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                vals.append(float(row.get("time_starttransfer") or 0) * 1000)
            except ValueError:
                pass
    return _pct(vals, 0.99)


def analyze_external_isp(run_dir: Path, data: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for (wan, test), rows in data.items():
        cfg = _read_wan_config(wan)
        plan_dl = cfg.get("plan", {}).get("download_mbps") or 0.0
        summary = _flent_summary(run_dir / wan / test)
        plan_dl = summary.get("plan_mbps") or plan_dl
        median = summary.get("throughput_median") or summary.get("median_mbps") or 0.0
        drop = ((plan_dl - median) / plan_dl) if plan_dl and median else 0.0
        ttfb = max(_browse_ttfb_p99(run_dir / wan / test), _browse_ttfb_p99(run_dir / wan / "browse"))
        outlier = max([float(r.get("signal_outlier_rate") or 0) for r in rows] or [0.0])
        evidence.append({"wan": wan, "test": test, "flent_throughput_drop_pct_vs_plan": round(drop, 4), "curl_ttfb_p99_ms": ttfb, "signal_outlier_rate_max": outlier})
    flagged = any(r["flent_throughput_drop_pct_vs_plan"] > BUCKET_6_THROUGHPUT_DROP_PCT and r["curl_ttfb_p99_ms"] > BUCKET_6_TTFB_P99_MS and r["signal_outlier_rate_max"] < BUCKET_6_OUTLIER_RATE_MAX for r in evidence)
    return _bucket(flagged, evidence, "Throughput/TTFB degradation with clean signal points toward external ISP/path." if flagged else "No external-ISP AND-gate crossed.")


def recommend(buckets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mapping = {
        "upload_ceiling_setpoint": 215,
        "download_recovery_lag": 214,
        "measurement_collapse": 214,
        "steering_drift": 216,
        "refractory_semantics": 216,
        "external_isp": 214,
    }
    priority = ["upload_ceiling_setpoint", "download_recovery_lag", "measurement_collapse", "steering_drift", "refractory_semantics", "external_isp"]
    flagged = [k for k in priority if buckets[k]["flagged"]]
    if not flagged:
        return {"primary": 214, "runners_up": [215, 216], "rationale": "No bucket flagged; start with measurement-collapse investigation if user experience remains bad."}
    primary = mapping[flagged[0]]
    runners = []
    for key in flagged[1:]:
        phase = mapping[key]
        if phase != primary and phase not in runners:
            runners.append(phase)
    for phase in (214, 215, 216):
        if phase != primary and phase not in runners:
            runners.append(phase)
    return {"primary": primary, "runners_up": runners, "rationale": f"Primary bucket: {flagged[0]}"}


def build_signal_sheet(run_dir: Path) -> dict[str, Any]:
    data = _all_health_rows(run_dir)
    buckets = {
        "upload_ceiling_setpoint": analyze_upload_ceiling(data),
        "download_recovery_lag": analyze_download_recovery(data),
        "measurement_collapse": analyze_measurement_collapse(run_dir, data),
        "steering_drift": analyze_steering_drift(run_dir),
        "refractory_semantics": analyze_refractory(data),
        "external_isp": analyze_external_isp(run_dir, data),
    }
    return {
        "phase": 213,
        "run_dir": str(run_dir),
        "buckets": buckets,
        "recommended_next_phase": recommend(buckets),
        "threshold_constants": {name: value for name, value in globals().items() if name.startswith("BUCKET_")},
    }


def write_markdown(sheet: dict[str, Any], path: Path) -> None:
    lines = ["# Phase 213 Signal Sheet", "", f"Run dir: `{sheet['run_dir']}`", "", "## Buckets", ""]
    for key, value in sheet["buckets"].items():
        status = "FLAGGED" if value["flagged"] else "clear"
        lines += [f"### {key}: {status}", "", value["operator_note"], "", "```json", json.dumps(value["evidence_rows"][:10], indent=2, sort_keys=True), "```", ""]
    rec = sheet["recommended_next_phase"]
    lines += ["## Recommended Next Phase", "", f"Primary: Phase {rec['primary']}", f"Runners-up: {rec['runners_up']}", rec["rationale"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=False)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sheet = build_signal_sheet(Path(args.run_dir))
    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(sheet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(sheet, Path(args.output_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

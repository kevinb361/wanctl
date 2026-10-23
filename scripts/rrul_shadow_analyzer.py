#!/usr/bin/env python3
"""Shadow analyzer for the evening cap sweeps of scripts/rrul-slot.sh: per hour of day, which download cap would be
recommended, and why.

SHADOW ONLY. The output is a dated recommendation file (JSON + Markdown). Nothing reads it automatically, and this
script changes no controller, shaper or ceiling setting. Applying a table to the live ceiling is a separate, reviewed
step (phase 3) with its own approval.

Inputs (read-only):
- rrul.csv (schema rrul-v1, single runs at the configured ceiling) and rrul-v2.csv (rrul-v2: single runs and sweeps)
  in the rrul-slot data dir.
- Optionally ("passive evidence") the controller's 15 s metrics from Prometheus through a read-only query command
  (`CMD range EXPR START END STEP` printing the API's .data.result JSON), summarized per hour of day.

Rule, per hour of day (Central), over sweep rows from the last --window-days days:
- A row is usable when it is complete, its sweep's restore is ok, and its sweep's pre-window household rate is known
  and at most --max-household-mbit. Other rows are counted and named, never used.
- The pre-window household rate of a sweep is pre_dl_mbit of its first run (sweep_order 1/N): all Spectrum CAKE
  download traffic in the 5 min before the sweep's own load. It can still include an earlier test that ended inside
  those 5 min (the idle gate looks at less than that), which only makes it higher. Later runs' pre windows contain the
  previous held run, so their pre_dl_mbit is not household context. A household change during the sweep is not seen.
  household_dl_mbit (in-window CAKE bytes minus flent's goodput) is not used: under load it also holds retransmissions
  and protocol overhead of the test itself, so it overstates household traffic.
- Each cap is compared with the control (780) of the SAME sweep. Over the --last-n most recent sweeps where both are
  usable, the cap "wins" a sweep when its loaded ICMP p99 is at least --win-frac lower than the control's.
- A cap qualifies when it has at least --min-wins wins, the median of its p99 over those sweeps is at most
  --p99-target-ms, it lies within [--cap-min, --cap-max] and below the control, and it had no breach-stop in the window.
- The recommendation is the highest qualifying cap; otherwise the control, with the reasons. Hours without sweep
  evidence stay at the control.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
V1_COLUMNS = [
    "schema",
    "label",
    "status",
    "reason",
    "start_utc",
    "local_date",
    "local_time",
    "local_tz",
    "dow",
    "dl_mbit",
    "ul_mbit",
    "icmp_median_ms",
    "icmp_p99_ms",
    "icmp_loss_pct",
    "icmp_sent",
    "icmp_lost",
    "shaped_dl_min_mbit",
    "shaped_dl_max_mbit",
    "shaped_ul_min_mbit",
    "shaped_ul_max_mbit",
    "max_dl_config_kbps",
    "run",
]
V2_EXTRA = [
    "mode",
    "tested_cap",
    "sweep_id",
    "sweep_order",
    "restore",
    "household_dl_mbit",
    "pre_dl_mbit",
    "rtt_delta_avg_ms",
    "rtt_delta_max_ms",
    "pre_rtt_delta_avg_ms",
    "pre_rtt_delta_max_ms",
    "nongreen_frac",
    "pre_nongreen_frac",
    "dl_drops",
    "pre_dl_drops",
    "peak_delay_ms",
    "pre_peak_delay_ms",
]
V2_COLUMNS = V1_COLUMNS + V2_EXTRA

# Passive evidence: 5-minute aggregates of the controller's 15 s metrics (advisor hourly.py, 2026-10-22).
W = 'wan="spectrum"'
D = 'wan="spectrum",direction="download"'
PASSIVE_QUERIES = {
    "traffic_mbit": f"sum(rate(cake_tin_sent_bytes_total{{{D}}}[5m]))*8/1e6",
    "rtt_delta_avg_ms": f"avg_over_time(cake_rtt_delta_ms{{{W}}}[5m])",
    "rtt_delta_max_ms": f"max_over_time(cake_rtt_delta_ms{{{W}}}[5m])",
    "rate_min_mbit": f"min_over_time(cake_shaped_rate_bps{{{D}}}[5m])/1e6",
    "nongreen_frac": f"avg_over_time((cake_congestion_state{{{D}}} > bool 0)[5m:15s])",
    "peak_delay_ms": f"max(max_over_time(cake_tin_peak_delay_seconds{{{D}}}[5m]))*1000",
}
PASSIVE_STEP = 300
PASSIVE_CHUNK = 14 * 86400
PROM_TIMEOUT = 60


class InputError(Exception):
    """A data file that cannot be read as an rrul schema."""


@dataclass
class Row:
    status: str
    start: int
    local_date: date
    hour: int
    mode: str
    cap: str  # "adaptive" or Mbit
    sweep: str
    order: str  # sweep: "N/M", position in the run order
    restore: str
    p99: float | None
    dl: float | None
    pre_dl: float | None


@dataclass
class Settings:
    window_days: int = 14
    last_n: int = 5
    p99_target_ms: float = 100.0
    win_frac: float = 0.30
    min_wins: int = 2
    cap_min: int = 450
    cap_max: int = 780
    control: int = 780
    max_household_mbit: float = 20.0


@dataclass
class HourResult:
    hour: int
    recommended_mbit: int
    basis: str
    reasons: list[str] = field(default_factory=list)
    caps: dict[str, dict] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)
    adaptive: dict = field(default_factory=dict)
    passive: dict = field(default_factory=dict)


def _num(value: str) -> float | None:
    try:
        x = float(value)
    except ValueError:
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def read_rows(path: Path) -> list[Row]:
    """Rows of one rrul.csv (v1) or rrul-v2.csv file; a missing file has none. Never writes."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header == V1_COLUMNS:
            columns = V1_COLUMNS
        elif header == V2_COLUMNS:
            columns = V2_COLUMNS
        else:
            raise InputError(f"{path}: header is neither rrul-v1 nor rrul-v2")
        rows = []
        for n, values in enumerate(reader, start=2):
            if len(values) != len(columns):
                raise InputError(f"{path}:{n}: {len(values)} fields, expected {len(columns)}")
            r = dict(zip(columns, values, strict=True))
            try:
                local_date = date.fromisoformat(r["local_date"])
                hour = int(r["local_time"].split(":")[0])
                start = int(r["start_utc"])
            except ValueError as exc:
                raise InputError(f"{path}:{n}: {exc}") from exc
            rows.append(
                Row(
                    status=r["status"],
                    start=start,
                    local_date=local_date,
                    hour=hour,
                    mode=r.get("mode") or "single",
                    cap=r.get("tested_cap") or "adaptive",
                    sweep=r.get("sweep_id", ""),
                    order=r.get("sweep_order", ""),
                    restore=r.get("restore", ""),
                    p99=_num(r["icmp_p99_ms"]),
                    dl=_num(r["dl_mbit"]),
                    pre_dl=_num(r.get("pre_dl_mbit", "")),
                )
            )
    return rows


def sweep_household(rows: list[Row]) -> dict[str, float | None]:
    """Pre-window household rate per sweep id: pre_dl_mbit of the sweep's first run, None when unknown."""
    return {r.sweep: r.pre_dl for r in rows if r.mode == "sweep" and r.order.startswith("1/")}


def exclusion(row: Row, s: Settings, household: dict[str, float | None]) -> str | None:
    """Why a sweep row cannot be used as cap evidence, or None."""
    if row.status != "complete":
        return f"status-{row.status}"
    if row.restore != "ok":
        return "restore-not-ok"
    if row.p99 is None:
        return "no-p99"
    hh = household.get(row.sweep)
    if hh is None:
        return "no-household-context"
    if hh > s.max_household_mbit:
        return "high-household"
    return None


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 1) if xs else None


def analyze_hour(
    hour: int, rows: list[Row], s: Settings, household: dict[str, float | None]
) -> HourResult:
    res = HourResult(hour=hour, recommended_mbit=s.control, basis="control")
    adaptive = [
        r for r in rows if r.mode == "single" and r.status == "complete" and r.p99 is not None
    ]
    if adaptive:
        res.adaptive = {
            "runs": len(adaptive),
            "p99_median_ms": _median([r.p99 for r in adaptive if r.p99 is not None]),
            "dl_median_mbit": _median([r.dl for r in adaptive if r.dl is not None]),
        }
    sweep_rows = [r for r in rows if r.mode == "sweep"]
    if not sweep_rows:
        res.reasons.append("no sweep evidence in the window; control kept")
        return res

    usable: dict[str, dict[str, Row]] = {}
    breaches: dict[str, int] = {}
    for r in sweep_rows:
        why = exclusion(r, s, household)
        if r.status == "breach-stop":
            breaches[r.cap] = breaches.get(r.cap, 0) + 1
        if why:
            res.excluded[why] = res.excluded.get(why, 0) + 1
            continue
        usable.setdefault(r.sweep, {})[r.cap] = r

    control = str(s.control)
    qualifying = []
    caps = sorted(
        {r.cap for r in sweep_rows if r.cap != control and r.cap.isdigit()}, key=int, reverse=True
    )
    for cap in caps:
        mbit = int(cap)
        info: dict = {"breach_stops": breaches.get(cap, 0)}
        res.caps[cap] = info
        if not (s.cap_min <= mbit <= s.cap_max) or mbit >= s.control:
            info["verdict"] = f"outside {s.cap_min}-{min(s.cap_max, s.control - 1)} Mbit; ignored"
            continue
        paired = sorted(
            (sw for sw in usable.values() if cap in sw and control in sw),
            key=lambda sw: sw[control].start,
        )[-s.last_n :]
        p99s = [sw[cap].p99 for sw in paired if sw[cap].p99 is not None]
        wins = sum(
            1
            for sw in paired
            if sw[cap].p99 is not None
            and sw[control].p99 is not None
            and sw[cap].p99 <= (1 - s.win_frac) * sw[control].p99
        )
        info.update(
            paired_sweeps=len(paired),
            wins=wins,
            p99_median_ms=_median(p99s),
            control_p99_median_ms=_median(
                [sw[control].p99 for sw in paired if sw[control].p99 is not None]
            ),
            dl_median_mbit=_median([sw[cap].dl for sw in paired if sw[cap].dl is not None]),
        )
        problems = []
        if wins < s.min_wins:
            problems.append(
                f"{wins} of {len(paired)} paired sweeps won by >= {s.win_frac:.0%} (need {s.min_wins})"
            )
        if info["p99_median_ms"] is None or info["p99_median_ms"] > s.p99_target_ms:
            problems.append(
                f"median p99 {info['p99_median_ms']} ms above target {s.p99_target_ms:g} ms"
            )
        if info["breach_stops"]:
            problems.append(f"{info['breach_stops']} breach-stop(s) at this cap")
        info["verdict"] = "qualifies" if not problems else "; ".join(problems)
        if not problems:
            qualifying.append(mbit)

    if qualifying:
        best = max(qualifying)
        res.recommended_mbit = best
        res.basis = "sweep"
        res.reasons.append(
            f"{best} Mbit: highest cap with >= {s.min_wins} clear wins over the {control} control and median p99 "
            f"<= {s.p99_target_ms:g} ms"
        )
    else:
        res.reasons.append("no cap qualifies; control kept")
    if res.excluded:
        res.reasons.append(
            "excluded rows: " + ", ".join(f"{k} x{v}" for k, v in sorted(res.excluded.items()))
        )
    return res


def passive_evidence(prom_cmd: str, end: int, days: int) -> tuple[dict[int, dict], str]:
    """Per-hour p50/p95 of PASSIVE_QUERIES over the last DAYS days, or ({}, reason) if unavailable."""
    start = end - days * 86400
    by_hour: dict[int, dict[str, list[float]]] = {}
    for name, expr in PASSIVE_QUERIES.items():
        s = start
        while s < end:
            e = min(end, s + PASSIVE_CHUNK)
            try:
                proc = subprocess.run(
                    [prom_cmd, "range", expr, str(s), str(e), str(PASSIVE_STEP)],
                    capture_output=True,
                    text=True,
                    timeout=PROM_TIMEOUT,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return {}, f"{name}: {type(exc).__name__}"
            if proc.returncode != 0:
                return {}, f"{name}: query exit {proc.returncode}"
            try:
                series = json.loads(proc.stdout or "[]")
                points = [(int(float(t)), _num(str(v))) for one in series for t, v in one["values"]]
            except (ValueError, KeyError, TypeError) as exc:
                return {}, f"{name}: unparsable result ({exc})"
            for t, v in points:
                if v is not None:
                    hour = datetime.fromtimestamp(t, CT).hour
                    by_hour.setdefault(hour, {}).setdefault(name, []).append(v)
            s = e
    out: dict[int, dict] = {}
    for hour, metrics in by_hour.items():
        out[hour] = {"samples": max(len(v) for v in metrics.values())}
        for name, values in metrics.items():
            values.sort()
            out[hour][f"{name}_p50"] = round(values[len(values) // 2], 3)
            out[hour][f"{name}_p95"] = round(
                values[min(len(values) - 1, int(0.95 * len(values)))], 3
            )
    return out, "ok"


def analyze(rows: list[Row], s: Settings, day: date, passive: dict[int, dict]) -> list[HourResult]:
    first = day - timedelta(days=s.window_days - 1)
    window = [r for r in rows if first <= r.local_date <= day]
    # from all rows: a sweep's first run may fall in an earlier hour or day than its other runs
    household = sweep_household(rows)
    results = []
    for hour in range(24):
        res = analyze_hour(hour, [r for r in window if r.hour == hour], s, household)
        res.passive = passive.get(hour, {})
        results.append(res)
    return results


def render_markdown(report: dict) -> str:
    s = report["settings"]
    lines = [
        f"# Shadow cap recommendation — {report['date']} (Central)",
        "",
        "**SHADOW ONLY.** Descriptive output; nothing reads this file and no ceiling, controller or shaper setting "
        "was changed.",
        "",
        f"Window: {report['window']['first']} .. {report['window']['last']}; rows read: {report['rows_read']}. "
        f"Rule: highest cap in {s['cap_min']}-{s['cap_max']} Mbit with >= {s['min_wins']} of the last {s['last_n']} "
        f"paired sweeps at least {s['win_frac']:.0%} below the {s['control']} control's p99, median p99 <= "
        f"{s['p99_target_ms']:g} ms, no breach-stop, pre-sweep household <= {s['max_household_mbit']:g} Mbit. "
        f"Passive evidence: {report['passive_status']}.",
        "",
        "| Hour | Recommended | Basis | Caps (wins/paired, median p99 ms) | Adaptive runs (median p99) | Passive "
        "rttΔ p95 / non-green p50 | Reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for h in report["hours"]:
        caps = "; ".join(
            f"{c}: {i.get('wins', '-')}/{i.get('paired_sweeps', '-')}, {i.get('p99_median_ms', '-')}"
            for c, i in h["caps"].items()
        )
        ad = h["adaptive"]
        adaptive = f"{ad['runs']} ({ad['p99_median_ms']})" if ad else "-"
        pv = h["passive"]
        passive = (
            f"{pv.get('rtt_delta_max_ms_p95', '-')} / {pv.get('nongreen_frac_p50', '-')}"
            if pv
            else "-"
        )
        lines.append(
            f"| {h['hour']:02d} | {h['recommended_mbit']} | {h['basis']} | {caps or '-'} | {adaptive} | {passive} | "
            f"{' '.join(h['reasons'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    default_data = Path(
        os.environ.get("RRUL_SLOT_DATA_DIR")
        or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "wanctl-rrul"
    )
    d = Settings()
    p = argparse.ArgumentParser(
        description="Shadow per-hour cap recommendation from rrul-slot sweeps (no live change)"
    )
    p.add_argument(
        "--data-dir", type=Path, default=default_data, help="rrul-slot data dir (read-only)"
    )
    p.add_argument(
        "--out-dir", type=Path, help="where to write the recommendation (default DATA_DIR/shadow)"
    )
    p.add_argument(
        "--date", type=date.fromisoformat, help="last Central day of the window (default today)"
    )
    p.add_argument("--window-days", type=int, default=d.window_days)
    p.add_argument(
        "--last-n", type=int, default=d.last_n, help="most recent paired sweeps per cap that count"
    )
    p.add_argument("--p99-target-ms", type=float, default=d.p99_target_ms)
    p.add_argument(
        "--win-frac", type=float, default=d.win_frac, help="p99 reduction vs control that is a win"
    )
    p.add_argument("--min-wins", type=int, default=d.min_wins)
    p.add_argument("--cap-min", type=int, default=d.cap_min)
    p.add_argument("--cap-max", type=int, default=d.cap_max)
    p.add_argument("--control", type=int, default=d.control)
    p.add_argument(
        "--max-household-mbit",
        type=float,
        default=d.max_household_mbit,
        help="highest pre-sweep household rate (first run's pre_dl_mbit) of a usable sweep",
    )
    p.add_argument("--prom-cmd", default=os.environ.get("RRUL_SLOT_PROM_CMD", "prom-ro"))
    p.add_argument("--passive-days", type=int, default=28)
    p.add_argument("--no-passive", action="store_true", help="skip the Prometheus passive evidence")
    a = p.parse_args(argv)
    checks = [
        (1 <= a.window_days <= 120, "--window-days must be 1-120"),
        (1 <= a.last_n <= 50, "--last-n must be 1-50"),
        (1 <= a.min_wins <= a.last_n, "--min-wins must be 1..--last-n"),
        (0 < a.win_frac < 1, "--win-frac must be between 0 and 1"),
        (0 < a.p99_target_ms <= 10000, "--p99-target-ms must be 0-10000"),
        (
            400 <= a.cap_min <= a.cap_max <= a.control <= 900,
            "need 400 <= --cap-min <= --cap-max <= --control <= 900",
        ),
        (0 <= a.max_household_mbit <= 1000, "--max-household-mbit must be 0-1000"),
        (1 <= a.passive_days <= 90, "--passive-days must be 1-90"),
    ]
    for ok, msg in checks:
        if not ok:
            p.error(msg)
    return a


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    s = Settings(
        window_days=a.window_days,
        last_n=a.last_n,
        p99_target_ms=a.p99_target_ms,
        win_frac=a.win_frac,
        min_wins=a.min_wins,
        cap_min=a.cap_min,
        cap_max=a.cap_max,
        control=a.control,
        max_household_mbit=a.max_household_mbit,
    )
    now = datetime.now(CT)
    day = a.date or now.date()
    try:
        rows = read_rows(a.data_dir / "rrul.csv") + read_rows(a.data_dir / "rrul-v2.csv")
    except (InputError, OSError) as exc:
        print(f"rrul-shadow-analyzer: {exc}", file=sys.stderr)
        return 1

    passive: dict[int, dict] = {}
    if a.no_passive:
        passive_status = "not requested"
    elif shutil.which(a.prom_cmd) is None:
        passive_status = f"unavailable: {a.prom_cmd} not found"
    else:
        end = int(datetime.combine(day + timedelta(days=1), datetime.min.time(), CT).timestamp())
        end = min(end, int(now.timestamp())) // PASSIVE_STEP * PASSIVE_STEP
        passive, why = passive_evidence(a.prom_cmd, end, a.passive_days)
        passive_status = (
            f"{a.passive_days} d of 5-min aggregates" if why == "ok" else f"unavailable: {why}"
        )

    results = analyze(rows, s, day, passive)
    report = {
        "shadow": True,
        "note": "Descriptive only; nothing reads this file and no live setting was changed.",
        "date": day.isoformat(),
        "generated": now.isoformat(timespec="seconds"),
        "window": {
            "first": (day - timedelta(days=s.window_days - 1)).isoformat(),
            "last": day.isoformat(),
        },
        "rows_read": len(rows),
        "settings": s.__dict__,
        "passive_status": passive_status,
        "hours": [r.__dict__ for r in results],
    }
    out = a.out_dir or a.data_dir / "shadow"
    out.mkdir(parents=True, exist_ok=True)
    _write_atomic(out / f"shadow-{day.isoformat()}.json", json.dumps(report, indent=2) + "\n")
    _write_atomic(out / f"shadow-{day.isoformat()}.md", render_markdown(report))
    changed = [
        f"{r.hour:02d}:{r.recommended_mbit}" for r in results if r.recommended_mbit != s.control
    ]
    print(
        f"shadow recommendation {day}: {', '.join(changed) or f'all hours at control {s.control}'} "
        f"-> {out}/shadow-{day.isoformat()}.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

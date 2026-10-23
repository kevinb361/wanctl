"""Tests for scripts/rrul_shadow_analyzer.py: the shadow per-hour cap recommendation from rrul-slot rows.

All inputs are synthetic CSV rows written to tmp_path. Passive evidence uses a fake read-only query command in tmp_path;
no Prometheus, network or live setting is touched. The analyzer only ever writes its own shadow-<date> files.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rrul_shadow_analyzer.py"
spec = importlib.util.spec_from_file_location("rrul_shadow_analyzer", SCRIPT)
assert spec is not None and spec.loader is not None
ana = importlib.util.module_from_spec(spec)
sys.modules["rrul_shadow_analyzer"] = ana
spec.loader.exec_module(ana)

CT = ZoneInfo("America/Chicago")
DAY = date(2026, 10, 22)
V1_HEADER = ",".join(ana.V1_COLUMNS)
V2_HEADER = ",".join(ana.V2_COLUMNS)


def _row(
    *,
    day: date = DAY,
    hhmm: str = "21:05",
    cap: str = "780",
    p99: float | str = 150.0,
    status: str = "complete",
    restore: str = "ok",
    household: str = "2.0",
    pre_dl: str = "0.4",
    order: str = "1/3",
    sweep: str = "",
    mode: str = "sweep",
    offset: int = 0,
) -> str:
    local = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), CT) + timedelta(
        seconds=offset
    )
    measured = status == "complete"
    sweep = sweep or f"eve-{day.isoformat()}-{hhmm}"
    values = {
        "schema": "rrul-v2",
        "label": "auto",
        "status": status,
        "reason": "measured" if measured else "x",
        "start_utc": str(int(local.timestamp())),
        "local_date": day.isoformat(),
        "local_time": hhmm,
        "local_tz": "CDT",
        "dow": "Thu",
        "dl_mbit": "500.0" if measured else "",
        "icmp_p99_ms": str(p99) if measured else "",
        "max_dl_config_kbps": "780000",
        "run": sweep,
        "mode": mode,
        "tested_cap": cap if mode == "sweep" else "adaptive",
        "sweep_id": sweep if mode == "sweep" else "",
        "sweep_order": order if mode == "sweep" else "",
        "restore": restore if mode == "sweep" else "",
        "household_dl_mbit": household if measured else "",
        "pre_dl_mbit": pre_dl if measured else "",
    }
    return ",".join(values.get(c, "") for c in ana.V2_COLUMNS)


def _sweep(day: date, p99s: dict[str, float], hhmm: str = "21:05", **kw) -> list[str]:
    return [
        _row(day=day, hhmm=hhmm, cap=c, p99=p, offset=i * 90, order=f"{i + 1}/{len(p99s)}", **kw)
        for i, (c, p) in enumerate(p99s.items())
    ]


def _write(data: Path, rows: list[str], v1: list[str] | None = None) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / "rrul-v2.csv").write_text("\n".join([V2_HEADER, *rows]) + "\n", encoding="utf-8")
    if v1 is not None:
        (data / "rrul.csv").write_text("\n".join([V1_HEADER, *v1]) + "\n", encoding="utf-8")


def _report(tmp_path: Path, *extra: str) -> dict:
    rc = ana.main(
        ["--data-dir", str(tmp_path / "data"), "--date", DAY.isoformat(), "--no-passive", *extra]
    )
    assert rc == 0
    return json.loads((tmp_path / "data" / "shadow" / f"shadow-{DAY.isoformat()}.json").read_text())


def _hour(report: dict, hour: int) -> dict:
    return report["hours"][hour]


def test_highest_qualifying_cap_is_recommended(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 70.0, "480": 50.0})
    _write(tmp_path / "data", rows)
    report = _report(tmp_path)
    assert report["shadow"] is True and len(report["hours"]) == 24
    h = _hour(report, 21)
    assert h["recommended_mbit"] == 620 and h["basis"] == "sweep"
    assert h["caps"]["620"]["wins"] == 3 and h["caps"]["620"]["verdict"] == "qualifies"
    assert h["caps"]["480"]["verdict"] == "qualifies"
    # every other hour keeps the control, with the reason
    assert all(_hour(report, x)["recommended_mbit"] == 780 for x in range(24) if x != 21)
    assert "no sweep evidence" in _hour(report, 3)["reasons"][0]
    md = (tmp_path / "data" / "shadow" / f"shadow-{DAY.isoformat()}.md").read_text()
    assert "SHADOW ONLY" in md and "| 21 | 620 | sweep |" in md


def test_thin_evidence_keeps_the_control(tmp_path: Path) -> None:
    _write(tmp_path / "data", _sweep(DAY, {"780": 160.0, "620": 60.0}))
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780 and h["basis"] == "control"
    assert "1 of 1 paired sweeps won" in h["caps"]["620"]["verdict"]


def test_cap_over_target_does_not_qualify_but_a_lower_one_can(tmp_path: Path) -> None:
    rows = []
    for d in range(2):
        rows += _sweep(DAY - timedelta(days=d), {"780": 300.0, "620": 120.0, "480": 90.0})
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert "above target 100 ms" in h["caps"]["620"]["verdict"]
    assert h["recommended_mbit"] == 480


def test_small_improvement_is_not_a_win(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(
            DAY - timedelta(days=d), {"780": 100.0, "620": 80.0}
        )  # 20% lower, under the 30% bar
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780 and h["caps"]["620"]["wins"] == 0
    # the bar is configurable
    h = _hour(_report(tmp_path, "--win-frac", "0.15"), 21)
    assert h["recommended_mbit"] == 620


@pytest.mark.parametrize(
    ("kw", "excluded"),
    [
        ({"pre_dl": "45.0"}, "high-household"),
        ({"pre_dl": ""}, "no-household-context"),
        ({"restore": "failed:rc=8"}, "restore-not-ok"),
        ({"restore": "unverified:status-unreadable"}, "restore-not-ok"),
    ],
)
def test_unusable_rows_are_excluded_and_named(tmp_path: Path, kw: dict, excluded: str) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 60.0}, **kw)
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780
    assert h["excluded"] == {excluded: 6}
    assert any(excluded in r for r in h["reasons"])


def test_household_is_the_first_runs_pre_window_not_the_in_window_estimate(tmp_path: Path) -> None:
    # Shaped like the 2026-10-22 evening sweeps: a quiet pre-window (0.4 Mbit), an in-window household estimate inflated
    # by the test's own load (62-168 Mbit), and later runs whose pre window holds the previous held run.
    rows = []
    for d, inflated in enumerate(("62.0", "115.0", "168.0")):
        day = DAY - timedelta(days=d)
        run = {"day": day, "household": inflated}
        rows += [
            _row(**run, cap="780", p99=160.0, pre_dl="0.4", order="1/3"),
            _row(**run, cap="620", p99=60.0, pre_dl="131.0", order="2/3", offset=90),
            _row(**run, cap="480", p99=50.0, pre_dl="127.5", order="3/3", offset=180),
        ]
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["excluded"] == {}
    assert h["recommended_mbit"] == 620 and h["caps"]["620"]["wins"] == 3

    # a busy pre-window still excludes the whole sweep, and the bound stays configurable
    h = _hour(_report(tmp_path, "--max-household-mbit", "0.3"), 21)
    assert h["recommended_mbit"] == 780 and h["excluded"] == {"high-household": 9}


def test_sweep_without_its_first_run_has_no_household_context(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 60.0, "480": 50.0})[1:]
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780 and h["excluded"] == {"no-household-context": 6}


def test_first_run_context_applies_across_an_hour_boundary(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        day = DAY - timedelta(days=d)
        sweep = f"eve-{day.isoformat()}-2158"
        run = {"day": day, "sweep": sweep}
        rows += [
            _row(**run, hhmm="21:58", cap="480", p99=50.0, order="1/3"),
            _row(**run, hhmm="22:00", cap="780", p99=160.0, pre_dl="130.0", order="2/3"),
            _row(**run, hhmm="22:02", cap="620", p99=60.0, pre_dl="128.0", order="3/3"),
        ]
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 22)
    assert h["excluded"] == {} and h["recommended_mbit"] == 620


def test_breach_stop_at_a_cap_disqualifies_it(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 60.0})
    rows.append(_row(day=DAY - timedelta(days=4), cap="620", status="breach-stop", sweep="eve-b"))
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780 and "1 breach-stop" in h["caps"]["620"]["verdict"]


def test_only_the_window_and_the_last_n_paired_sweeps_count(tmp_path: Path) -> None:
    rows = []
    for d in range(20, 23):  # wins, but outside a 14-day window
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 60.0})
    _write(tmp_path / "data", rows)
    assert _hour(_report(tmp_path), 21)["recommended_mbit"] == 780
    assert _hour(_report(tmp_path, "--window-days", "30"), 21)["recommended_mbit"] == 620

    # recent losses outweigh older wins once only the last 2 paired sweeps count
    rows = []
    for d in range(2, 6):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 60.0})
    for d in range(2):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "620": 150.0})
    _write(tmp_path / "data", rows)
    assert _hour(_report(tmp_path), 21)["recommended_mbit"] == 620
    h = _hour(_report(tmp_path, "--last-n", "2"), 21)
    assert h["recommended_mbit"] == 780 and h["caps"]["620"]["paired_sweeps"] == 2


def test_caps_outside_bounds_are_ignored(tmp_path: Path) -> None:
    rows = []
    for d in range(3):
        rows += _sweep(DAY - timedelta(days=d), {"780": 160.0, "420": 30.0, "850": 20.0})
    _write(tmp_path / "data", rows)
    h = _hour(_report(tmp_path), 21)
    assert h["recommended_mbit"] == 780
    assert "ignored" in h["caps"]["420"]["verdict"] and "ignored" in h["caps"]["850"]["verdict"]


def test_v1_rows_are_read_as_adaptive_and_never_written(tmp_path: Path) -> None:
    v1 = [
        "rrul-v1,auto,complete,measured,1792629333,2026-10-21,19:35,CDT,Wed,572.0,25.0,30.1,156,0,301,0,"
        "500,780,8.0,36.0,780000,auto-20261022T003533Z",
        "rrul-v1,auto,breach-stop,sustained-breach,1792595182,2026-10-21,10:06,CDT,Wed,,,,,,,,,,,,780000,auto-x",
    ]
    _write(tmp_path / "data", [], v1=v1)
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path / "data").iterdir()
    }
    report = _report(tmp_path)
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (tmp_path / "data").iterdir()
        if p.is_file()
    }
    assert after == before
    assert report["rows_read"] == 2
    assert _hour(report, 19)["adaptive"] == {
        "runs": 1,
        "p99_median_ms": 156.0,
        "dl_median_mbit": 572.0,
    }
    assert _hour(report, 19)["recommended_mbit"] == 780


@pytest.mark.parametrize("bad", ["some,other,header\n1,2,3\n", V2_HEADER + "\nrrul-v2,short\n"])
def test_unreadable_input_fails_without_output(
    tmp_path: Path, bad: str, capsys: pytest.CaptureFixture
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "rrul-v2.csv").write_text(bad, encoding="utf-8")
    assert ana.main(["--data-dir", str(data), "--no-passive"]) == 1
    assert "rrul-shadow-analyzer:" in capsys.readouterr().err
    assert not (data / "shadow").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--min-wins", "6", "--last-n", "5"],
        ["--win-frac", "1.5"],
        ["--cap-min", "300"],
        ["--cap-max", "800"],
        ["--window-days", "0"],
    ],
)
def test_invalid_settings_are_rejected(tmp_path: Path, args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        ana.main(["--data-dir", str(tmp_path), "--no-passive", *args])
    assert exc.value.code == 2


FAKE_PROM = r"""#!/bin/sh
# range EXPR START END STEP -> one series with a point every STEP s; value depends on the query
echo "$*" >> "$(dirname "$0")/calls"
[ -n "$FAKE_PROM_FAIL" ] && exit 22
case $2 in *rtt_delta*) v=4.5 ;; *congestion*) v=0.25 ;; *) v=1.5 ;; esac
out=""; t=$3
while [ "$t" -le "$4" ]; do out="$out${out:+,}[$t,\"$v\"]"; t=$((t + $5)); done
echo "[{\"metric\":{},\"values\":[$out]}]"
"""


def test_passive_evidence_is_summarized_per_hour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prom = tmp_path / "bin" / "fake-prom"
    prom.parent.mkdir()
    prom.write_text(FAKE_PROM, encoding="utf-8")
    prom.chmod(0o755)
    _write(tmp_path / "data", [])
    monkeypatch.setenv("PATH", f"{prom.parent}:/usr/bin:/bin")
    args = ["--data-dir", str(tmp_path / "data"), "--date", DAY.isoformat(), "--passive-days", "2"]
    assert ana.main([*args, "--prom-cmd", "fake-prom"]) == 0
    report = json.loads(
        (tmp_path / "data" / "shadow" / f"shadow-{DAY.isoformat()}.json").read_text()
    )
    assert report["passive_status"].startswith("2 d")
    p = _hour(report, 21)["passive"]
    assert (
        p["rtt_delta_max_ms_p95"] == 4.5 and p["nongreen_frac_p50"] == 0.25 and p["samples"] >= 20
    )
    calls = (prom.parent / "calls").read_text().splitlines()
    assert calls and all(c.startswith("range ") for c in calls)

    monkeypatch.setenv("FAKE_PROM_FAIL", "1")
    assert ana.main([*args, "--prom-cmd", "fake-prom"]) == 0
    report = json.loads(
        (tmp_path / "data" / "shadow" / f"shadow-{DAY.isoformat()}.json").read_text()
    )
    assert (
        report["passive_status"].startswith("unavailable:") and _hour(report, 21)["passive"] == {}
    )

    assert ana.main([*args, "--prom-cmd", "no-such-prom"]) == 0
    report = json.loads(
        (tmp_path / "data" / "shadow" / f"shadow-{DAY.isoformat()}.json").read_text()
    )
    assert report["passive_status"] == "unavailable: no-such-prom not found"

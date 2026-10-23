"""Tests for scripts/wanctl_ceiling_apply.py: the phase 3 ceiling applier, shipped disabled.

Every side effect is stubbed. systemctl, silicom-bypass and logger go through FakeShaper, a runner that emulates the
controller unit, its state bridge, the sweep dead-man timer and the bypass card; the config file, state, tables, locks
and the sweep marker are synthetic files in tmp_path; the clock and sleeps are injected. No real systemctl, no network,
no live setting.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "wanctl_ceiling_apply.py"
spec = importlib.util.spec_from_file_location("wanctl_ceiling_apply", SCRIPT)
assert spec is not None and spec.loader is not None
app = importlib.util.module_from_spec(spec)
sys.modules["wanctl_ceiling_apply"] = app
spec.loader.exec_module(app)

CT = ZoneInfo("America/Chicago")
DAY = date(2026, 10, 22)
UNIT = "cake-autorate-spectrum.service"
BRIDGE = "cake-autorate-spectrum-state-bridge.service"
TIMER = "wanctl-sweep-cap-autorestore.timer"
CONFIG = (
    "#!/usr/bin/env bash\n"
    "# synthetic test config\n"
    "dl_if=test-dl\n"
    "min_dl_shaper_rate_kbps=100000\n"
    "base_dl_shaper_rate_kbps=450000\n"
    "max_dl_shaper_rate_kbps={max}\n"
    "max_ul_shaper_rate_kbps=36000\n"
)
EVENING = {19: 620, 20: 480, 21: 620}  # one window 19-21, effective cap 620


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, 30, tzinfo=CT).astimezone(UTC)


class FakeShaper:
    """Runner emulating systemctl show/restart, silicom-bypass status and logger."""

    def __init__(self) -> None:
        self.active = "active"
        self.freezer = "running"
        self.pid = 100
        self.bridge = "active"
        self.timer = "dead"
        self.timer_rc = 0
        self.bypass = "non-Bypass"
        self.disc = "non-Disconnect"
        self.bypass_rc = 0
        self.bypass_text: str | None = None
        self.restart_ok = True
        self.pid_drift = False  # MainPID changes on every read: never stable
        self.restart_hook = None  # runs when restart is called, before it takes effect
        self.after_restart_hook = None  # runs after the restart took effect, before it returns
        self.bypass_hook = None  # runs on every silicom-bypass status call
        self.cmd_cost = 0.0  # seconds every command takes on the injected clock
        self.calls: list[list[str]] = []
        self.timeouts: list[tuple[str, float]] = []
        self.clock = 0.0

    def __call__(self, argv: list[str], timeout: float) -> tuple[int | None, str]:
        assert timeout > 0
        self.calls.append(list(argv))
        if argv[0] == "logger":
            return 0, ""
        self.timeouts.append((argv[1] if argv[0] == "systemctl" else "bypass", timeout))
        self.clock += self.cmd_cost
        return self._dispatch(argv)

    def _dispatch(self, argv: list[str]) -> tuple[int | None, str]:
        if argv[:2] == ["systemctl", "show"]:
            if "--value" in argv:
                assert argv[-1] == TIMER
                return self.timer_rc, f"{self.timer}\n"
            return 0, self._props(argv[-1])
        if argv[:2] == ["systemctl", "restart"]:
            assert argv[2:] == [UNIT, BRIDGE]
            if self.restart_hook:
                self.restart_hook()
            if not self.restart_ok:
                return 1, ""
            self.active, self.freezer, self.pid = "active", "running", self.pid + 1
            if self.after_restart_hook:
                self.after_restart_hook()
            return 0, ""
        if argv[1:] == ["status", "spec-modem"]:
            if self.bypass_hook:
                self.bypass_hook()
            text = self.bypass_text
            if text is None:
                text = f"spec-modem: bypass={self.bypass} disc={self.disc} std_nic=not in Standard NIC mode\n"
            return self.bypass_rc, text
        raise AssertionError(f"unexpected command {argv}")

    def _props(self, unit: str) -> str:
        if unit == BRIDGE:
            return f"ActiveState={self.bridge}\nSubState=running\nFreezerState=running\nMainPID=7\n"
        assert unit == UNIT
        if self.pid_drift:
            self.pid += 1
        pid = self.pid if self.active == "active" else 0
        sub = "running" if self.active == "active" else "dead"
        return f"ActiveState={self.active}\nSubState={sub}\nFreezerState={self.freezer}\nMainPID={pid}\n"

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def monotonic(self) -> float:
        return self.clock

    @property
    def restarts(self) -> int:
        return sum(1 for c in self.calls if c[:2] == ["systemctl", "restart"])


class Rig:
    """One synthetic shaper: env, config, table dir, state dir, sweep files."""

    def __init__(self, root: Path, enabled: bool = True) -> None:
        self.root = root
        self.tables = root / "tables"
        self.state_dir = root / "state"
        self.config = root / "etc" / "config.spectrum.sh"
        self.off = root / "etc" / "ceiling-apply.off"
        self.marker = root / "run" / "wanctl-sweep-cap.hold"
        self.sweep_lock = root / "run" / "wanctl-sweep-cap.lock"
        self.env = root / "etc" / "ceiling-apply.env"
        for d in (self.tables, self.config.parent, self.marker.parent):
            d.mkdir(parents=True, exist_ok=True)
        self.set_config(780000)
        self.config.chmod(0o640)
        self.write_env(enabled)
        self.fake = FakeShaper()

    def write_env(self, enabled: bool) -> None:
        lines = {
            "CEILING_APPLY_ENABLED": "1" if enabled else "0",
            "CEILING_APPLY_TABLE_DIR": self.tables,
            "CEILING_APPLY_STATE_DIR": self.state_dir,
            "CEILING_APPLY_OFF_FILE": self.off,
            "CEILING_APPLY_CONFIG": self.config,
            "CEILING_APPLY_BYPASS_CMD": "/fake/silicom-bypass",
            "CEILING_APPLY_LOCK": self.root / "run" / "wanctl-ceiling-apply.lock",
            "CEILING_APPLY_SWEEP_LOCK": self.sweep_lock,
            "CEILING_APPLY_SWEEP_MARKER": self.marker,
        }
        self.env.write_text("".join(f"{k}={v}\n" for k, v in lines.items()))

    def set_config(self, kbps: int) -> None:
        self.config.write_text(CONFIG.format(max=kbps))

    def config_kbps(self) -> int:
        return int(app.MAX_DL_RE.findall(self.config.read_text())[0])

    def table(
        self,
        recs: dict[int, int] | None = None,
        day: date = DAY - timedelta(days=1),
        generated: datetime | None = None,
        status: dict | None = None,
        mutate=None,
    ) -> str:
        """Write shadow-<day>.json and a matching analyzer-status.json; returns the table sha256."""
        recs = recs if recs is not None else EVENING
        gen = generated or datetime(day.year, day.month, day.day, 23, 45, tzinfo=CT)
        t = {
            "shadow": True,
            "date": day.isoformat(),
            "generated": gen.isoformat(timespec="seconds"),
            "settings": {"control": 780},
            "hours": [{"hour": h, "recommended_mbit": recs.get(h, 780)} for h in range(24)],
        }
        if mutate:
            mutate(t)
        raw = (json.dumps(t, indent=2) + "\n").encode()
        (self.tables / f"shadow-{day.isoformat()}.json").write_bytes(raw)
        sha = hashlib.sha256(raw).hexdigest()
        s = {
            "schema": "rrul-shadow-status-v1",
            "finished": (gen + timedelta(minutes=1)).isoformat(timespec="seconds"),
            "ok": True,
            "table_date": day.isoformat(),
            "table_sha256": sha,
            "error": None,
            "passive_status": "28 d of 5-min aggregates",
            "breach_stops_24h": [],
        }
        s.update(status or {})
        self.write_status(s)
        return sha

    def write_status(self, s: dict | None) -> None:
        p = self.tables / "analyzer-status.json"
        if s is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps(s))

    def state(self) -> dict:
        return json.loads((self.state_dir / "state.json").read_text())

    def put_state(self, **kw) -> None:
        st = {
            "schema": "ceiling-apply-state-v1",
            "day": DAY.isoformat(),
            "lowerings": 0,
            "recoveries": 0,
            "applied_kbps": 780000,
            "verified": "restart",
            "verified_utc": "2026-10-22T00:00:00+00:00",
            "pending": None,
            "deferral_since": None,
            "plan": None,
        }
        st.update(kw)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "state.json").write_text(json.dumps(st))

    def run(self, *args: str, now: datetime) -> int:
        return app.main(
            ["--env-file", str(self.env), *args],
            runner=self.fake,
            now=lambda: now,
            sleep=self.fake.sleep,
            monotonic=self.fake.monotonic,
        )

    def tick(self, now: datetime) -> int:
        return self.run("tick", now=now)

    def morning(self, day: date = DAY) -> int:
        """The day's first scheduled tick (00:00:30 Central), where the plan is fixed."""
        return self.tick(at(0, day=day))

    def events(self) -> list[dict]:
        p = self.state_dir / "events.jsonl"
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def lowered(rig: Rig, kbps: int = 620000, **kw) -> None:
    """The applier's own verified lowering today."""
    rig.set_config(kbps)
    rig.put_state(applied_kbps=kbps, lowerings=1, **kw)


# --- disabled by default --------------------------------------------------------------------------------------------


def _files(root: Path) -> set[Path]:
    return {p for p in root.rglob("*")}


@pytest.mark.parametrize("env", ["missing", "zero"])
def test_disabled_tick_reads_only_env_and_changes_nothing(tmp_path: Path, env: str) -> None:
    rig = Rig(tmp_path, enabled=False)
    rig.table()
    if env == "missing":
        rig.env.unlink()
    before = _files(tmp_path)
    config = rig.config.read_bytes()
    assert rig.tick(at(19)) == 0
    assert rig.fake.calls == []
    assert _files(tmp_path) == before
    assert rig.config.read_bytes() == config


def test_env_file_example_ships_disabled() -> None:
    example = SCRIPT.parent.parent / "deploy" / "ceiling-apply" / "ceiling-apply.env.example"
    env = app.read_env(example)
    assert env is not None and env["CEILING_APPLY_ENABLED"] == "0"


def test_unknown_env_key_is_an_error_without_side_effects(rig: Rig) -> None:
    rig.env.write_text("CEILING_APPLY_ENABLED=1\nSOMETHING_ELSE=1\n")
    assert rig.tick(at(19)) == 1
    assert rig.fake.calls == []


# --- normal operation ------------------------------------------------------------------------------------------------


def test_lowering_at_window_start_then_raise_at_end(rig: Rig) -> None:
    rig.table()
    assert rig.morning() == 0
    assert rig.tick(at(18)) == 0
    assert rig.fake.restarts == 0 and rig.state()["verified"] == "baseline-assumed"
    assert rig.tick(at(19)) == 0
    assert rig.config_kbps() == 620000 and rig.fake.restarts == 1
    st = rig.state()
    assert st["applied_kbps"] == 620000 and st["verified"] == "restart" and st["lowerings"] == 1
    assert st["pending"] is None
    assert rig.tick(at(20)) == 0 and rig.tick(at(21)) == 0  # same effective cap: no restart
    assert rig.fake.restarts == 1
    assert rig.tick(at(22)) == 0
    assert rig.config_kbps() == 780000 and rig.fake.restarts == 2
    assert rig.state()["verified"] == "restart"
    assert rig.tick(at(22, 30)) == 0 and rig.fake.restarts == 2  # idempotent


def test_config_write_changes_one_line_and_keeps_mode(rig: Rig) -> None:
    rig.table()
    rig.morning()
    before = rig.config.read_text()
    assert rig.tick(at(19)) == 0
    after = rig.config.read_text()
    assert after == before.replace(
        "max_dl_shaper_rate_kbps=780000", "max_dl_shaper_rate_kbps=620000"
    )
    assert rig.config.stat().st_mode & 0o777 == 0o640
    prev = rig.config.with_name(rig.config.name + ".ceiling-apply.prev")
    assert prev.read_text() == before
    assert not [p for p in rig.config.parent.iterdir() if p.name.startswith(".")]


def test_plan_logs_original_and_effective(rig: Rig) -> None:
    rig.table()
    rig.morning()
    fixed = [e for e in rig.events() if e["event"] == "plan-fixed"][0]
    assert fixed["original"][19:22] == [620, 480, 620]
    assert fixed["effective"][19:22] == [620, 620, 620]


def test_lowering_only_on_an_hour_boundary(rig: Rig) -> None:
    rig.table()
    rig.morning()
    assert rig.tick(at(19, 30)) == 0
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000
    assert any(e["event"] == "lowering-waits" for e in rig.events())
    assert rig.tick(at(20)) == 0  # a missed first boundary: a later in-window boundary
    assert rig.config_kbps() == 620000


def test_raise_is_allowed_off_the_boundary(rig: Rig) -> None:
    rig.table()
    rig.morning()
    rig.tick(at(19))
    rig.fake.timer = "waiting"  # a sweep blocks the 22:00 raise
    assert rig.tick(at(22)) == 75
    rig.fake.timer = "dead"
    assert rig.tick(at(22, 30)) == 0
    assert rig.config_kbps() == 780000


def test_one_lowering_per_day(rig: Rig) -> None:
    rig.table()
    rig.put_state(lowerings=1)
    rig.morning()
    assert rig.tick(at(19)) == 0
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000
    assert any(e["event"] == "budget-exhausted" for e in rig.events())


def test_budget_resets_on_a_new_central_day(rig: Rig) -> None:
    rig.table(day=DAY)
    rig.put_state(lowerings=1, day=(DAY - timedelta(days=1)).isoformat())
    rig.morning(DAY + timedelta(days=1))
    assert rig.tick(at(19, day=DAY + timedelta(days=1))) == 0
    assert rig.config_kbps() == 620000


def test_table_arriving_after_the_plan_is_fixed_waits_for_tomorrow(rig: Rig) -> None:
    rig.tick(at(9))  # no table: plan not fixed, retried until noon
    rig.tick(at(12))  # noon: today stays at 780
    rig.table()
    assert rig.tick(at(19)) == 0
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000


def test_table_arriving_in_the_morning_is_used(rig: Rig) -> None:
    rig.tick(at(9))
    rig.table()
    assert rig.tick(at(11)) == 0
    assert rig.tick(at(19)) == 0
    assert rig.config_kbps() == 620000


# --- normalization ---------------------------------------------------------------------------------------------------


def _recs(low: dict[int, int]) -> list[int]:
    return [low.get(h, 780) for h in range(24)]


def test_normalize_uses_max_of_window() -> None:
    eff = app.normalize(_recs({20: 450, 21: 700}))
    assert eff[20] == eff[21] == 700
    assert eff[19] == eff[22] == 780


def test_normalize_keeps_longest_then_earliest_window() -> None:
    eff = app.normalize(_recs({8: 600, 19: 620, 20: 480, 21: 620}))
    assert eff[8] == 780 and eff[19:22] == [620, 620, 620]
    eff = app.normalize(_recs({8: 600, 20: 480}))
    assert eff[8] == 600 and eff[20] == 780


def test_normalize_hour_23_always_control() -> None:
    eff = app.normalize(_recs({22: 600, 23: 450}))
    assert eff[22] == 600 and eff[23] == 780
    assert app.normalize(_recs({})) == [780] * 24


def test_normalize_never_below_recommendation() -> None:
    recs = _recs({5: 700, 6: 450, 7: 520})
    assert all(e >= r for e, r in zip(app.normalize(recs), recs, strict=True))


# --- validity and fallback -------------------------------------------------------------------------------------------


def _bad_hours(t: dict) -> None:
    t["hours"] = t["hours"][:23]


def _dup_hour(t: dict) -> None:
    t["hours"][5]["hour"] = 4


INVALID = {
    "not-shadow": {"mutate": lambda t: t.update(shadow=False)},
    "date-mismatch": {"mutate": lambda t: t.update(date="2026-10-20")},
    "control": {"mutate": lambda t: t["settings"].update(control=900)},
    "hours": {"mutate": _bad_hours},
    "dup-hour": {"mutate": _dup_hour},
    "below-bounds": {"recs": {19: 440}},
    "above-bounds": {"recs": {19: 790}},
    "float": {"mutate": lambda t: t["hours"][19].update(recommended_mbit=620.0)},
    "stale": {"generated": datetime(2026, 10, 20, 8, 0, tzinfo=CT)},  # 40 h old at the morning tick
    "naive-time": {"mutate": lambda t: t.update(generated="2026-10-21T23:45:00")},
    "status-failed": {"status": {"ok": False, "error": "boom"}},
    "status-sha": {"status": {"table_sha256": "0" * 64}},
    "status-date": {"status": {"table_date": "2026-10-20"}},
    "status-stale": {"status": {"finished": "2026-10-20T12:00:00-05:00"}},
    "status-future": {"status": {"finished": "2026-10-23T12:00:00-05:00"}},
    "status-schema": {"status": {"schema": "other"}},
    "breach": {
        "status": {"breach_stops_24h": [{"start_utc": 1, "mode": "sweep", "tested_cap": "480"}]}
    },
    "breach-missing": {"status": {"breach_stops_24h": None}},
}


@pytest.mark.parametrize("case", sorted(INVALID))
def test_invalid_inputs_never_lower(rig: Rig, case: str) -> None:
    rig.table(**INVALID[case])
    rig.morning()
    assert rig.tick(at(19)) == 0
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000
    assert any(e["event"] == "no-plan" for e in rig.events())


def test_missing_status_never_lowers(rig: Rig) -> None:
    rig.table()
    rig.write_status(None)
    rig.morning()
    assert rig.tick(at(19)) == 0
    assert rig.config_kbps() == 780000


def test_future_dated_table_is_a_fallback(rig: Rig) -> None:
    rig.table()
    rig.table(day=DAY + timedelta(days=1), generated=datetime(2026, 10, 22, 1, 0, tzinfo=CT))
    rig.morning()
    assert rig.tick(at(19)) == 0
    assert rig.config_kbps() == 780000


def test_passive_failure_does_not_invalidate(rig: Rig) -> None:
    rig.table(status={"passive_status": "unavailable: prom-ro not found"})
    rig.morning()
    assert rig.tick(at(19)) == 0
    assert rig.config_kbps() == 620000


@pytest.mark.parametrize(
    "change",
    [
        {"ok": False, "error": "later run failed", "table_sha256": None, "table_date": None},
        {"breach_stops_24h": [{"start_utc": 1, "mode": "single", "tested_cap": "adaptive"}]},
    ],
)
def test_fallback_after_lowering_when_inputs_go_bad(rig: Rig, change: dict) -> None:
    sha = rig.table()
    rig.morning()
    rig.tick(at(19))
    assert rig.config_kbps() == 620000
    status = json.loads((rig.tables / "analyzer-status.json").read_text())
    status.update(change)
    rig.write_status(status)
    assert rig.tick(at(20, 30)) == 0  # moves to 780 need no boundary
    assert rig.config_kbps() == 780000
    rig.table(status={"table_sha256": sha})  # inputs good again: the day stays at 780
    assert rig.tick(at(21)) == 0
    assert rig.config_kbps() == 780000


def test_table_aging_past_36h_falls_back(rig: Rig) -> None:
    rig.table(generated=datetime(2026, 10, 21, 8, 0, tzinfo=CT))
    rig.morning()
    rig.tick(at(19))
    assert rig.config_kbps() == 620000
    assert rig.tick(at(20, 30)) == 0  # 36.5 h after generation
    assert rig.config_kbps() == 780000


# --- off switch and restore ------------------------------------------------------------------------------------------


def test_off_switch_restores_780(rig: Rig) -> None:
    rig.table()
    lowered(rig)
    rig.off.touch()
    assert rig.tick(at(20, 30)) == 0
    assert rig.config_kbps() == 780000 and rig.state()["verified"] == "restart"


def test_off_switch_from_baseline_claims_nothing(rig: Rig) -> None:
    rig.off.touch()
    assert rig.tick(at(19)) == 0
    assert rig.fake.restarts == 0
    note = [e for e in rig.events() if e["event"] == "no-op"][0]["note"]
    assert "not verified (baseline-assumed)" in note


def test_restore_from_baseline_restarts_and_verifies(tmp_path: Path) -> None:
    rig = Rig(tmp_path, enabled=False)
    rig.put_state(verified="baseline-assumed", verified_utc=None)
    assert rig.run("restore", now=at(10)) == 0
    assert rig.fake.restarts == 1 and rig.state()["verified"] == "restart"
    assert rig.config_kbps() == 780000


def test_restore_without_state_restarts_and_verifies(rig: Rig) -> None:
    assert rig.run("restore", now=at(10)) == 0
    assert rig.fake.restarts == 1 and rig.state()["verified"] == "restart"


def test_restore_verify_failure_never_claims_success(rig: Rig) -> None:
    rig.put_state(verified="baseline-assumed")
    rig.fake.bypass = "Bypass"
    assert rig.run("restore", now=at(10)) == 6
    assert rig.state()["verified"] is False
    assert not any(e["event"] == "applied" for e in rig.events())


def test_restore_when_verified_is_a_no_op(rig: Rig) -> None:
    rig.put_state()
    assert rig.run("restore", now=at(10)) == 0
    assert rig.fake.restarts == 0


def test_restore_lowered(rig: Rig) -> None:
    lowered(rig)
    assert rig.run("restore", now=at(20)) == 0
    assert rig.config_kbps() == 780000 and rig.state()["applied_kbps"] == 780000


# --- the sweep owns the shaper while it runs -------------------------------------------------------------------------


def _hold_marker(rig: Rig) -> None:
    rig.marker.write_text("1\n")


def _timer(rig: Rig) -> None:
    rig.fake.timer = "waiting"


def _timer_unreadable(rig: Rig) -> None:
    rig.fake.timer_rc = 1


def _frozen(rig: Rig) -> None:
    rig.fake.freezer = "frozen"


@pytest.mark.parametrize("block", [_hold_marker, _timer, _timer_unreadable, _frozen])
@pytest.mark.parametrize("action", ["lower", "fallback", "restore"])
def test_sweep_defers_every_action(rig: Rig, block, action: str) -> None:
    rig.table()
    rig.morning()
    if action == "fallback":
        lowered(rig)
        rig.off.touch()
    if action == "restore":
        lowered(rig)
    block(rig)
    before = rig.config.read_bytes()
    code = rig.run("restore", now=at(19)) if action == "restore" else rig.tick(at(19))
    assert code == 75
    assert rig.fake.restarts == 0 and rig.config.read_bytes() == before


def test_sweep_lock_busy_defers(rig: Rig) -> None:
    rig.table()
    rig.morning()
    fd = os.open(rig.sweep_lock, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert rig.tick(at(19)) == 75
    finally:
        os.close(fd)
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000


def test_long_deferral_of_a_needed_780_escalates(rig: Rig) -> None:
    lowered(rig)
    rig.off.touch()
    _hold_marker(rig)
    assert rig.tick(at(20)) == 75
    assert rig.tick(at(20, 30)) == 75
    assert rig.tick(at(21)) == 1
    assert any(e["event"] == "CRITICAL-deferred" for e in rig.events())
    rig.marker.unlink()
    assert rig.tick(at(21, 30)) == 0
    assert rig.config_kbps() == 780000 and rig.state()["deferral_since"] is None


def test_tick_before_noon_fixes_plan_after_noon_does_not(rig: Rig) -> None:
    rig.table()
    assert rig.tick(at(12)) == 0
    assert not any(e["event"] == "plan-fixed" for e in rig.events())
    assert rig.state()["plan"] is None


def test_inactive_unit_not_ours_is_refused(rig: Rig) -> None:
    rig.table()
    rig.morning()
    rig.fake.active = "inactive"
    assert rig.tick(at(19)) == 1
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000


# --- ownership -------------------------------------------------------------------------------------------------------


def test_foreign_value_without_state(rig: Rig) -> None:
    rig.set_config(600000)
    assert rig.tick(at(19)) == 1
    assert rig.fake.restarts == 0 and rig.config_kbps() == 600000
    assert not (rig.state_dir / "state.json").exists()


def test_foreign_value_with_state(rig: Rig) -> None:
    rig.table()
    rig.put_state()
    rig.set_config(700000)
    assert rig.tick(at(22)) == 1
    assert rig.fake.restarts == 0 and rig.config_kbps() == 700000


def test_deploy_reset_to_780_is_recognized(rig: Rig) -> None:
    rig.table()
    lowered(rig)
    rig.set_config(780000)  # deploy overwrote the file; the running ceiling is unknown
    assert rig.tick(at(22)) == 0
    assert rig.fake.restarts == 1 and rig.state()["applied_kbps"] == 780000


@pytest.mark.parametrize("kbps,unit", [(600000, "active"), (780000, "inactive")])
def test_corrupt_state_is_lost_ownership(rig: Rig, kbps: int, unit: str) -> None:
    rig.table()
    rig.set_config(kbps)
    rig.state_dir.mkdir()
    (rig.state_dir / "state.json").write_text("{not json")
    rig.fake.active = unit
    assert rig.tick(at(20)) == 6
    assert rig.run("restore", now=at(20)) == 6
    assert rig.fake.restarts == 0 and rig.config_kbps() == kbps
    assert rig.run("restore", "--take-ownership", now=at(20)) == 0
    assert rig.config_kbps() == 780000 and rig.fake.restarts == 1
    st = rig.state()
    assert st["verified"] == "restart" and st["lowerings"] == 1 and st["recoveries"] == 2
    kept = list(rig.state_dir.glob("state.json.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_text() == "{not json"


def test_take_ownership_still_respects_a_sweep(rig: Rig) -> None:
    rig.state_dir.mkdir()
    (rig.state_dir / "state.json").write_text("[]")
    _hold_marker(rig)
    assert rig.run("restore", "--take-ownership", now=at(20)) == 75
    assert rig.fake.restarts == 0


# --- transaction: verification, failures, interruption ---------------------------------------------------------------


def _bypass_on(rig: Rig) -> None:
    rig.fake.bypass = "Bypass"


def _disconnected(rig: Rig) -> None:
    rig.fake.disc = "Disconnect"


def _bypass_error(rig: Rig) -> None:
    rig.fake.bypass_rc = 1


def _bypass_garbage(rig: Rig) -> None:
    rig.fake.bypass_text = "spec-modem: something else\n"


def _bypass_two_lines(rig: Rig) -> None:
    rig.fake.bypass_text = "spec-modem: bypass=non-Bypass disc=non-Disconnect std_nic=x\nspec-modem: bypass=Bypass disc=x std_nic=x\n"


def _pid_drift(rig: Rig) -> None:
    rig.fake.pid_drift = True


def _bridge_down(rig: Rig) -> None:
    rig.fake.bridge = "failed"


def _restart_fails(rig: Rig) -> None:
    rig.fake.restart_ok = False


@pytest.mark.parametrize(
    "fault",
    [
        _bypass_on,
        _disconnected,
        _bypass_error,
        _bypass_garbage,
        _bypass_two_lines,
        _pid_drift,
        _bridge_down,
        _restart_fails,
    ],
)
def test_unverified_lowering_retries_780_then_exit_6(rig: Rig, fault) -> None:
    rig.table()
    rig.morning()
    fault(rig)
    assert rig.tick(at(19)) == 6
    assert rig.fake.restarts == 2  # the lowering, then one recovery to 780
    st = rig.state()
    assert st["verified"] is False and st["pending"]["to_kbps"] == 780000
    assert st["lowerings"] == 1 and st["recoveries"] == 1
    assert rig.config_kbps() == 780000


def test_unverified_lowering_recovered_in_the_same_run(rig: Rig) -> None:
    rig.table()
    rig.morning()
    fails = iter([True, False])

    def flaky() -> None:
        rig.fake.bypass = "Bypass" if next(fails) else "non-Bypass"

    rig.fake.restart_hook = flaky
    assert rig.tick(at(19)) == 0
    st = rig.state()
    assert st["applied_kbps"] == 780000 and st["verified"] == "restart" and st["recoveries"] == 1


def test_recovery_on_the_next_run_and_its_daily_bound(rig: Rig) -> None:
    rig.table()
    rig.morning()
    rig.fake.restart_ok = False
    assert rig.tick(at(19)) == 6  # lowering + recovery 1
    assert rig.tick(at(19, 30)) == 6  # recovery 2
    assert rig.state()["recoveries"] == 2
    assert rig.tick(at(20)) == 6  # bound reached: nothing started
    assert rig.fake.restarts == 3
    assert any(e["event"] == "CRITICAL-recovery-exhausted" for e in rig.events())
    rig.fake.restart_ok = True
    assert rig.run("restore", now=at(20, 5)) == 0  # a human restore is outside the bound
    assert rig.state()["verified"] == "restart"


PENDING_LOWER = {
    "kind": "lower",
    "from_kbps": 780000,
    "to_kbps": 620000,
    "started_utc": "2026-10-23T00:00:30+00:00",
}


def test_applier_owned_inactive_unit_is_recovered(rig: Rig) -> None:
    rig.set_config(620000)
    rig.put_state(applied_kbps=780000, lowerings=1, pending=PENDING_LOWER)
    rig.fake.active = "failed"
    assert rig.tick(at(19, 30)) == 0
    assert rig.config_kbps() == 780000 and rig.state()["recoveries"] == 1


class Killed(BaseException):
    """Stands in for SIGKILL / power loss at a transaction step."""


def die(*_a: object, **_k: object) -> None:
    raise Killed


def _recovered_next_run(rig: Rig, lowerings: int = 1, recoveries: int = 1) -> None:
    """The run after an interruption: recovery to 780 with a verified restart and exact counters."""
    rig.fake.restart_hook = rig.fake.after_restart_hook = rig.fake.bypass_hook = None
    assert rig.tick(at(19, 30)) == 0
    st = rig.state()
    assert rig.config_kbps() == 780000 and st["applied_kbps"] == 780000
    assert st["pending"] is None and st["verified"] == "restart"
    assert st["lowerings"] == lowerings and st["recoveries"] == recoveries


def _lowering_interrupted(rig: Rig) -> dict:
    rig.table()
    rig.morning()
    with pytest.raises(Killed):
        rig.tick(at(19))
    st = rig.state()
    assert st["pending"]["kind"] == "lower" and st["pending"]["to_kbps"] == 620000
    assert st["lowerings"] == 1 and st["recoveries"] == 0
    return st


def test_kill_right_after_intent(rig: Rig, monkeypatch) -> None:
    monkeypatch.setattr(app.Applier, "write_config", die)
    _lowering_interrupted(rig)
    assert rig.config_kbps() == 780000 and rig.fake.restarts == 0
    monkeypatch.undo()
    _recovered_next_run(rig)


def test_kill_during_restart(rig: Rig) -> None:
    rig.fake.restart_hook = die
    _lowering_interrupted(rig)
    assert rig.config_kbps() == 620000
    _recovered_next_run(rig)


def test_kill_after_restart_before_verify(rig: Rig) -> None:
    rig.fake.after_restart_hook = die
    _lowering_interrupted(rig)
    assert rig.config_kbps() == 620000 and rig.fake.pid == 101  # the restart took effect
    _recovered_next_run(rig)


def test_kill_during_verify(rig: Rig) -> None:
    rig.fake.bypass_hook = die
    _lowering_interrupted(rig)
    assert rig.config_kbps() == 620000
    _recovered_next_run(rig)


def test_kill_right_before_commit(rig: Rig, monkeypatch) -> None:
    real = app.write_atomic

    def dying(path: Path, data: bytes, like: Path | None = None) -> None:
        if path.name == "state.json" and b'"pending": null' in data and b'"restart"' in data:
            raise Killed
        real(path, data, like)

    monkeypatch.setattr(app, "write_atomic", dying)
    _lowering_interrupted(rig)
    monkeypatch.undo()
    _recovered_next_run(rig)


def test_kill_right_after_commit(rig: Rig, monkeypatch) -> None:
    real_log = app.Applier.log

    def dying_log(self, event: str, **fields: object) -> None:
        if event == "applied":
            raise Killed
        real_log(self, event, **fields)

    rig.table()
    rig.morning()
    monkeypatch.setattr(app.Applier, "log", dying_log)
    with pytest.raises(Killed):
        rig.tick(at(19))
    monkeypatch.undo()
    st = rig.state()
    assert st["pending"] is None and st["applied_kbps"] == 620000 and st["verified"] == "restart"
    assert rig.tick(at(19, 30)) == 0  # committed: nothing to recover, no restart
    st = rig.state()
    assert rig.fake.restarts == 1 and rig.config_kbps() == 620000
    assert st["lowerings"] == 1 and st["recoveries"] == 0


def test_kill_in_recovery_keeps_its_reservation(rig: Rig) -> None:
    rig.put_state(applied_kbps=780000, pending=PENDING_LOWER, lowerings=1)
    rig.set_config(620000)
    rig.fake.restart_hook = die
    with pytest.raises(Killed):
        rig.tick(at(19, 30))
    st = rig.state()
    assert st["recoveries"] == 1 and st["pending"]["kind"] == "recovery"
    assert st["pending"]["from_kbps"] == 620000 and st["lowerings"] == 1
    rig.fake.restart_hook = None
    assert rig.tick(at(20)) == 0
    st = rig.state()
    assert st["recoveries"] == 2 and st["verified"] == "restart" and rig.config_kbps() == 780000


# --- hard bounds and strict state ------------------------------------------------------------------------------------


def test_persisted_plan_cannot_grant_a_ceiling_above_780(rig: Rig) -> None:
    rig.table()
    rig.morning()
    state = rig.state()
    state["plan"]["hours"][19] = 900
    rig.put_state(**state)
    assert rig.tick(at(19)) == 6  # schema-invalid state: ownership lost
    assert rig.config_kbps() == 780000 and rig.fake.restarts == 0


@pytest.mark.parametrize(
    "change",
    [
        {"plan_original_19": 400},
        {"plan_hours_20": 480},  # not the normalized original
        {"applied_kbps": 900000},
        {"applied_kbps": 300000},
        {"pending_to": 900000},
        {"pending_kind": "other"},
        {"lowerings": -1},
        {"lowerings": True},
        {"day": "yesterday"},
        {"drop": "recoveries"},
        {"drop": "verified_utc"},
        {"extra": "x"},
    ],
)
def test_strictly_invalid_state_is_lost_ownership(rig: Rig, change: dict) -> None:
    rig.table()
    rig.morning()
    st = rig.state()
    key, value = next(iter(change.items()))
    if key == "plan_original_19":
        st["plan"]["original"][19] = value
    elif key == "plan_hours_20":
        st["plan"]["hours"][20] = value
    elif key == "pending_to":
        st["pending"] = dict(PENDING_LOWER, to_kbps=value)
    elif key == "pending_kind":
        st["pending"] = dict(PENDING_LOWER, kind=value)
    elif key == "drop":
        del st[value]
    elif key == "extra":
        st["extra"] = value
    else:
        st[key] = value
    (rig.state_dir / "state.json").write_text(json.dumps(st))
    assert rig.tick(at(19)) == 6
    assert rig.config_kbps() == 780000 and rig.fake.restarts == 0


def test_actuator_refuses_targets_outside_hard_bounds(rig: Rig) -> None:
    s = app.Settings.from_env(app.read_env(rig.env))
    applier = app.Applier(
        s, app.Shaper(s, rig.fake, rig.fake.sleep, rig.fake.monotonic), lambda: at(19)
    )
    st = app.State(day=DAY.isoformat())
    for kbps in (900000, 449000):
        with pytest.raises(app.RefusedError):
            applier.transaction(st, "lower", kbps)
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000 and st.pending is None


# --- foreign value written while waiting for the sweep lock ----------------------------------------------------------


def _foreign_write_while_waiting(rig: Rig, monkeypatch) -> None:
    original_wait = app.Applier._lock_wait

    def changed_while_waiting(self, fd: int) -> bool:
        acquired = original_wait(self, fd)
        rig.set_config(700000)
        return acquired

    monkeypatch.setattr(app.Applier, "_lock_wait", changed_while_waiting)


def test_foreign_write_during_lock_wait_is_not_overwritten_by_tick(rig: Rig, monkeypatch) -> None:
    rig.table()
    rig.morning()
    _foreign_write_while_waiting(rig, monkeypatch)
    assert rig.tick(at(19)) == 1
    assert rig.config_kbps() == 700000 and rig.fake.restarts == 0
    assert rig.state()["pending"] is None and rig.state()["lowerings"] == 0


def test_foreign_write_during_lock_wait_is_not_overwritten_by_restore(
    rig: Rig, monkeypatch
) -> None:
    lowered(rig)
    _foreign_write_while_waiting(rig, monkeypatch)
    assert rig.run("restore", now=at(20)) == 1
    assert rig.config_kbps() == 700000 and rig.fake.restarts == 0


def test_take_ownership_still_overrides_a_foreign_value(rig: Rig, monkeypatch) -> None:
    rig.state_dir.mkdir()
    (rig.state_dir / "state.json").write_text("{")
    _foreign_write_while_waiting(rig, monkeypatch)
    assert rig.run("restore", "--take-ownership", now=at(20)) == 0
    assert rig.config_kbps() == 780000


# --- verification deadline -------------------------------------------------------------------------------------------


def test_slow_checks_cannot_verify_after_the_deadline(rig: Rig) -> None:
    rig.table()
    rig.morning()
    rig.fake.cmd_cost = 3.0  # a pass = 3 commands = 9 s; passes end at 9, 20, 31 > 20
    assert rig.tick(at(19)) == 6
    assert rig.fake.restarts == 2  # the lowering and its recovery: neither verified
    assert all(t <= app.CMD_TIMEOUT for verb, t in rig.fake.timeouts if verb != "restart")


def test_command_timeouts_never_exceed_the_time_left(rig: Rig) -> None:
    s = app.Settings.from_env(app.read_env(rig.env))
    shaper = app.Shaper(s, rig.fake, rig.fake.sleep, rig.fake.monotonic)
    rig.fake.cmd_cost = 4.0
    start = rig.fake.clock
    assert shaper.verify() is False
    for _, t in rig.fake.timeouts:
        assert t <= app.CMD_TIMEOUT
    assert rig.fake.clock - start <= app.VERIFY_WINDOW + app.CMD_TIMEOUT
    left = [t for _, t in rig.fake.timeouts]
    assert min(left) < app.CMD_TIMEOUT  # the last commands got only what was left


def test_third_pass_completing_after_the_deadline_does_not_verify(rig: Rig) -> None:
    s = app.Settings.from_env(app.read_env(rig.env))
    shaper = app.Shaper(s, rig.fake, rig.fake.sleep, rig.fake.monotonic)
    rig.fake.cmd_cost = 2.0  # 6 s passes would end at 6, 14, 22: the third is past 20 s
    assert shaper.verify() is False
    assert rig.fake.clock <= app.VERIFY_WINDOW


def test_fast_checks_verify_within_the_window(rig: Rig) -> None:
    s = app.Settings.from_env(app.read_env(rig.env))
    shaper = app.Shaper(s, rig.fake, rig.fake.sleep, rig.fake.monotonic)
    rig.fake.cmd_cost = 1.0  # passes end at 3, 8, 13
    assert shaper.verify() is True


def test_kill_during_config_write_leaves_old_or_new_file(rig: Rig, monkeypatch) -> None:
    rig.table()
    rig.morning()
    real = app.write_atomic

    def dying(path: Path, data: bytes, like: Path | None = None) -> None:
        if path == rig.config:
            raise Killed
        real(path, data, like)

    monkeypatch.setattr(app, "write_atomic", dying)
    with pytest.raises(Killed):
        rig.tick(at(19))
    assert rig.config_kbps() == 780000  # never partial
    assert rig.state()["pending"]["to_kbps"] == 620000
    monkeypatch.setattr(app, "write_atomic", real)
    assert rig.tick(at(19, 30)) == 0  # recovery: restart verified at 780
    assert rig.state()["verified"] == "restart" and rig.fake.restarts == 1


def test_intent_write_failure_changes_nothing(rig: Rig, monkeypatch) -> None:
    rig.table()
    rig.morning()  # bootstrap + plan
    real = app.write_atomic

    def failing(path: Path, data: bytes, like: Path | None = None) -> None:
        if path.name == "state.json" and b'"pending": {' in data:
            raise OSError("disk full")
        real(path, data, like)

    monkeypatch.setattr(app, "write_atomic", failing)
    assert rig.tick(at(19)) == 1
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000


def test_commit_write_failure_is_recovered_next_run(rig: Rig, monkeypatch) -> None:
    rig.table()
    rig.morning()
    real = app.write_atomic

    def failing(path: Path, data: bytes, like: Path | None = None) -> None:
        if (
            path.name == "state.json"
            and b'"verified": "restart"' in data
            and b'"pending": null' in data
        ):
            raise OSError("disk full")
        real(path, data, like)

    monkeypatch.setattr(app, "write_atomic", failing)
    assert rig.tick(at(19)) == 1
    assert rig.state()["pending"]["to_kbps"] == 620000
    monkeypatch.setattr(app, "write_atomic", real)
    assert rig.tick(at(19, 30)) == 0
    assert rig.config_kbps() == 780000 and rig.state()["recoveries"] == 1


def test_equal_value_without_verification_is_not_a_no_op(rig: Rig) -> None:
    rig.put_state(verified=False)  # a failed fallback whose file already says 780000
    assert rig.tick(at(10)) == 0
    assert rig.fake.restarts == 1 and rig.state()["verified"] == "restart"


def test_base_above_new_ceiling_is_refused(rig: Rig) -> None:
    rig.table(recs={19: 450})
    rig.config.write_text(
        CONFIG.format(max=780000).replace(
            "base_dl_shaper_rate_kbps=450000", "base_dl_shaper_rate_kbps=500000"
        )
    )
    rig.morning()
    assert rig.tick(at(19)) == 1
    assert rig.fake.restarts == 0 and rig.config_kbps() == 780000


def test_duplicate_max_line_is_refused(rig: Rig) -> None:
    rig.table()
    rig.config.write_text(CONFIG.format(max=780000) + "max_dl_shaper_rate_kbps=780000\n")
    assert rig.tick(at(19)) == 1
    assert rig.fake.restarts == 0


def test_own_lock_busy(rig: Rig) -> None:
    lock = rig.root / "run" / "wanctl-ceiling-apply.lock"
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert rig.tick(at(19)) == 75
    finally:
        os.close(fd)
    assert rig.fake.calls == []


# --- time ------------------------------------------------------------------------------------------------------------


def test_fall_back_hour_twice_is_idempotent(rig: Rig) -> None:
    day = date(2026, 11, 1)  # CDT -> CST at 02:00
    rig.table(recs={1: 600}, day=day - timedelta(days=1))
    first = datetime(2026, 11, 1, 6, 0, 30, tzinfo=UTC)  # 01:00:30 CDT
    second = first + timedelta(hours=1)  # 01:00:30 CST
    assert first.astimezone(CT).hour == second.astimezone(CT).hour == 1
    assert rig.tick(first) == 0 and rig.config_kbps() == 600000
    assert rig.tick(second) == 0 and rig.fake.restarts == 1


def test_spring_forward_maps_to_central_hours(rig: Rig) -> None:
    day = date(2026, 3, 8)  # 02:00 CST -> 03:00 CDT
    rig.table(recs={3: 600}, day=day - timedelta(days=1))
    now = datetime(2026, 3, 8, 8, 0, 30, tzinfo=UTC)  # 03:00:30 CDT
    assert now.astimezone(CT).hour == 3
    assert rig.tick(now) == 0 and rig.config_kbps() == 600000


# --- read-only commands ----------------------------------------------------------------------------------------------


def test_plan_command_is_read_only(rig: Rig, capsys) -> None:
    rig.table()
    before = _files(rig.root)
    assert rig.run("plan", now=at(18)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["valid"] and out["effective"][19:22] == [620, 620, 620]
    assert _files(rig.root) == before and rig.fake.calls == []


def test_status_command_is_read_only(rig: Rig, capsys) -> None:
    rig.put_state(verified="baseline-assumed")
    before = _files(rig.root)
    assert rig.run("status", now=at(18)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"]["verified"] == "baseline-assumed"
    assert _files(rig.root) == before and rig.fake.calls == []

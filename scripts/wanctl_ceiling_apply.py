#!/usr/bin/env python3
"""Phase 3 of the adaptive evening cap: apply the shadow per-hour table to the Spectrum download ceiling.

SHIPPED DISABLED. With no env file, or CEILING_APPLY_ENABLED other than 1, `tick` returns at once: it reads only its
env file, creates no file and runs no command. Nothing in this repository installs or enables it; see
docs/CEILING_APPLY.md for the prepared enable and rollback steps and their prerequisites.

How the ceiling is set (repository configuration and one read of unpinned upstream source; the installed versions
were not inspected, so this is an assumption to check before enabling): cake-autorate reads
max_dl_shaper_rate_kbps from its config file once at startup, so a new ceiling means rewriting that one line and
restarting the controller and its state bridge. Every restart passes through the Silicom fail-open bypass briefly and
restarts the download rate from its base, so lowerings are limited to one per Central day.

Safety contract, in short (docs/CEILING_APPLY.md has the full rules):
- Hard bounds 450-780 Mbit. A table outside them, stale (> 36 h), unvouched by analyzer-status.json, from a failed
  analyzer run, or with a breach-stop in the 24 h before the analyzer finished, gives 780 for the day.
- An off switch file gives 780. `restore` gives 780 and is satisfied only by a verified restart.
- At most one window per day at one cap, the MAX of its hourly recommendations; hour 23 always 780. Lowerings only in
  the first 10 minutes of an hour; moves to 780 at any run.
- Acts only on a clean shaper: wanctl-sweep-cap's lock held, no hold marker, no pending dead-man timer, controller
  active and not frozen. Otherwise nothing is changed (exit 75).
- Edits only a value it recognizes, records intent (and budget) before any change, verifies every restart with live
  unit state plus `silicom-bypass status`, and treats an unreadable state file as lost ownership: no automatic action.

Exit codes: 0 ok, no-op or disabled; 1 error, refusal, or a needed move to 780 deferred for >= 60 min; 6 restart not
verified or manual recovery required; 75 deferred (busy, sweep active).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
CONTROL_MBIT = 780
CAP_MIN_MBIT = 450
CONTROL_KBPS = CONTROL_MBIT * 1000
MAX_AGE = timedelta(hours=36)
MAX_SKEW = timedelta(minutes=5)
LOWER_MINUTES = 10  # a lowering only in the first minutes of an hour
PLAN_UNTIL_HOUR = 12  # today's plan may still be fixed until 12:00 Central
LOWERINGS_PER_DAY = 1
RECOVERIES_PER_DAY = 2
ESCALATE_AFTER = 3600  # a needed move to 780 deferred this long fails the run
SWEEP_LOCK_WAIT = 30.0
RESTART_TIMEOUT = 60
VERIFY_PASSES = 3
VERIFY_INTERVAL = 2.0
VERIFY_WINDOW = 20.0
CMD_TIMEOUT = 10
STATE_SCHEMA = "ceiling-apply-state-v1"
STATUS_SCHEMA = "rrul-shadow-status-v1"
STATUS_FILE = "analyzer-status.json"
TABLE_RE = re.compile(r"^shadow-(\d{4}-\d{2}-\d{2})\.json$")
MAX_DL_RE = re.compile(r"^max_dl_shaper_rate_kbps=(\d+)$", re.M)
MIN_DL_RE = re.compile(r"^min_dl_shaper_rate_kbps=(\d+)$", re.M)
BASE_DL_RE = re.compile(r"^base_dl_shaper_rate_kbps=(\d+)$", re.M)
ENV_LINE_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")

EXIT_OK, EXIT_ERROR, EXIT_UNVERIFIED, EXIT_DEFERRED = 0, 1, 6, 75

DEFAULTS = {
    "CEILING_APPLY_ENABLED": "0",
    "CEILING_APPLY_TABLE_DIR": "/var/lib/wanctl/ceiling-apply/shadow",
    "CEILING_APPLY_STATE_DIR": "/var/lib/wanctl/ceiling-apply",
    "CEILING_APPLY_OFF_FILE": "/etc/wanctl/ceiling-apply.off",
    "CEILING_APPLY_CONFIG": "/etc/cake-autorate/config.spectrum.sh",
    "CEILING_APPLY_UNIT": "cake-autorate-spectrum.service",
    "CEILING_APPLY_BRIDGE": "cake-autorate-spectrum-state-bridge.service",
    "CEILING_APPLY_BYPASS_CMD": "/usr/local/sbin/silicom-bypass",
    "CEILING_APPLY_BYPASS_PAIR": "spec-modem",
    "CEILING_APPLY_LOCK": "/run/wanctl-ceiling-apply.lock",
    "CEILING_APPLY_SWEEP_LOCK": "/run/wanctl-sweep-cap.lock",
    "CEILING_APPLY_SWEEP_MARKER": "/run/wanctl-sweep-cap.hold",
    "CEILING_APPLY_SWEEP_TIMER": "wanctl-sweep-cap-autorestore.timer",
}
DEFAULT_ENV_FILE = "/etc/wanctl/ceiling-apply.env"

Runner = Callable[[list[str], float], tuple[int | None, str]]


class RefusedError(Exception):
    """A condition under which the applier changes nothing; carries the exit code."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def run_command(argv: list[str], timeout: float) -> tuple[int | None, str]:
    """Run ARGV without a shell; (None, why) when it could not run or timed out."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return proc.returncode, proc.stdout


# --- configuration -------------------------------------------------------------------------------------------------


def read_env(path: Path) -> dict[str, str] | None:
    """KEY=VALUE lines (parsed, never sourced); None when the file does not exist."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    env = dict(DEFAULTS)
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ENV_LINE_RE.match(line)
        if not m or m.group(1) not in DEFAULTS:
            raise RefusedError(EXIT_ERROR, f"{path}:{n}: not a known KEY=VALUE line")
        env[m.group(1)] = m.group(2).strip().strip('"')
    return env


@dataclass
class Settings:
    enabled: bool
    table_dir: Path
    state_dir: Path
    off_file: Path
    config: Path
    unit: str
    bridge: str
    bypass_cmd: str
    bypass_pair: str
    lock: Path
    sweep_lock: Path
    sweep_marker: Path
    sweep_timer: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> Settings:
        return cls(
            enabled=env["CEILING_APPLY_ENABLED"] == "1",
            table_dir=Path(env["CEILING_APPLY_TABLE_DIR"]),
            state_dir=Path(env["CEILING_APPLY_STATE_DIR"]),
            off_file=Path(env["CEILING_APPLY_OFF_FILE"]),
            config=Path(env["CEILING_APPLY_CONFIG"]),
            unit=env["CEILING_APPLY_UNIT"],
            bridge=env["CEILING_APPLY_BRIDGE"],
            bypass_cmd=env["CEILING_APPLY_BYPASS_CMD"],
            bypass_pair=env["CEILING_APPLY_BYPASS_PAIR"],
            lock=Path(env["CEILING_APPLY_LOCK"]),
            sweep_lock=Path(env["CEILING_APPLY_SWEEP_LOCK"]),
            sweep_marker=Path(env["CEILING_APPLY_SWEEP_MARKER"]),
            sweep_timer=env["CEILING_APPLY_SWEEP_TIMER"],
        )


# --- the table and the analyzer's health record ---------------------------------------------------------------------


@dataclass
class Plan:
    day: str
    table_date: str | None
    table_sha256: str | None
    status_sha256: str | None
    original: list[int]
    hours: list[int]  # effective ceiling per Central hour, Mbit
    failed: str | None = None  # why the day is at 780; sticky for the day


def _parse_time(value: Any, what: str) -> datetime:
    try:
        t = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{what} is not an ISO time") from exc
    if t.tzinfo is None:
        raise ValueError(f"{what} has no time zone")
    return t


def _fresh(t: datetime, now: datetime, what: str) -> None:
    if now - t > MAX_AGE:
        raise ValueError(f"{what} is older than 36 h")
    if t - now > MAX_SKEW:
        raise ValueError(f"{what} is in the future")


def pick_table(table_dir: Path, today: date) -> Path:
    """The newest shadow-DATE.json dated today or earlier; a later-dated file is a clock problem."""
    dated = []
    for p in table_dir.iterdir() if table_dir.is_dir() else []:
        m = TABLE_RE.match(p.name)
        if m:
            d = date.fromisoformat(m.group(1))
            if d > today:
                raise ValueError(f"{p.name} is dated after today")
            dated.append((d, p))
    if not dated:
        raise ValueError("no shadow table")
    return max(dated)[1]


def validate_table(raw: bytes, file_date: str, now: datetime) -> list[int]:
    """The 24 recommendations of a valid table, Mbit, or ValueError. Out-of-bounds values reject the whole table."""
    t = json.loads(raw)
    if not isinstance(t, dict) or t.get("shadow") is not True:
        raise ValueError("table is not a shadow table")
    if t.get("date") != file_date:
        raise ValueError("table date does not match its file name")
    if not isinstance(t.get("settings"), dict) or t["settings"].get("control") != CONTROL_MBIT:
        raise ValueError(f"table control is not {CONTROL_MBIT}")
    _fresh(_parse_time(t.get("generated"), "table generated"), now, "table")
    hours = t.get("hours")
    if not isinstance(hours, list) or len(hours) != 24:
        raise ValueError("table does not have 24 hours")
    recs: dict[int, int] = {}
    for h in hours:
        hour, rec = (
            (h.get("hour"), h.get("recommended_mbit")) if isinstance(h, dict) else (None, None)
        )
        if type(hour) is not int or type(rec) is not int or not 0 <= hour <= 23 or hour in recs:
            raise ValueError(
                "table hours are not 24 unique integer hours with integer recommendations"
            )
        if not CAP_MIN_MBIT <= rec <= CONTROL_MBIT:
            raise ValueError(f"breach of bounds: hour {hour} recommends {rec} Mbit")
        recs[hour] = rec
    return [recs[h] for h in range(24)]


def validate_status(raw: bytes, table_date: str, table_sha: str, now: datetime) -> None:
    """ValueError unless the analyzer's last run succeeded, wrote this very table, and saw no breach-stop."""
    s = json.loads(raw)
    if not isinstance(s, dict) or s.get("schema") != STATUS_SCHEMA:
        raise ValueError("analyzer status has an unknown schema")
    _fresh(_parse_time(s.get("finished"), "analyzer finished"), now, "analyzer status")
    if s.get("ok") is not True:
        raise ValueError(f"analyzer failed: {s.get('error')}")
    if s.get("table_date") != table_date or s.get("table_sha256") != table_sha:
        raise ValueError("analyzer status does not vouch for this table")
    breaches = s.get("breach_stops_24h")
    if breaches != []:
        n = len(breaches) if isinstance(breaches, list) else "unknown number of"
        raise ValueError(f"breach: {n} breach-stop row(s) in the 24 h before the analyzer finished")


def normalize(recs: list[int]) -> list[int]:
    """One window, one cap: the longest run of sub-780 hours among 0-22 (earliest on a tie) at the MAX of its values.

    No hour is set below its own recommendation; the higher substituted values have no evidence of their own.
    """
    runs: list[tuple[int, int]] = []
    start = None
    for h in range(24):
        low = h < 23 and recs[h] < CONTROL_MBIT
        if low and start is None:
            start = h
        if not low and start is not None:
            runs.append((start, h))
            start = None
    out = [CONTROL_MBIT] * 24
    if runs:
        a, b = max(runs, key=lambda r: (r[1] - r[0], -r[0]))
        cap = max(recs[a:b])
        out[a:b] = [cap] * (b - a)
    return out


def load_inputs(table_dir: Path, now: datetime) -> tuple[str, str, str, list[int]]:
    """(table date, table sha256, status sha256, recommendations) or ValueError with the reason."""
    today = now.astimezone(CT).date()
    path = pick_table(table_dir, today)
    file_date = TABLE_RE.match(path.name).group(1)  # type: ignore[union-attr]
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    recs = validate_table(raw, file_date, now)
    status_raw = (table_dir / STATUS_FILE).read_bytes()
    validate_status(status_raw, file_date, sha, now)
    return file_date, sha, hashlib.sha256(status_raw).hexdigest(), recs


def recheck_inputs(plan: Plan, table_dir: Path, now: datetime) -> None:
    """ValueError when the inputs today's plan was fixed from no longer hold (sticky for the rest of the day)."""
    raw = (table_dir / f"shadow-{plan.table_date}.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != plan.table_sha256:
        raise ValueError("today's table file changed")
    validate_table(raw, str(plan.table_date), now)
    validate_status(
        (table_dir / STATUS_FILE).read_bytes(), str(plan.table_date), str(plan.table_sha256), now
    )


# --- state -----------------------------------------------------------------------------------------------------------


@dataclass
class State:
    day: str
    lowerings: int = 0
    recoveries: int = 0
    applied_kbps: int = CONTROL_KBPS
    verified: str | bool = "baseline-assumed"  # "restart" | "baseline-assumed" | False
    verified_utc: str | None = None
    pending: dict | None = None
    deferral_since: float | None = None
    plan: dict | None = None
    schema: str = STATE_SCHEMA

    @classmethod
    def parse(cls, raw: bytes) -> State:
        """Strict: every field present with its exact type and range; anything else is lost ownership."""
        d = json.loads(raw)
        if not isinstance(d, dict) or d.get("schema") != STATE_SCHEMA:
            raise ValueError("unknown state schema")
        if set(d) != STATE_FIELDS:
            raise ValueError(f"state fields {sorted(set(d) ^ STATE_FIELDS)} missing or unknown")
        s = cls(**d)
        _check_date(s.day, "day")
        if not all(type(v) is int and 0 <= v <= 10 for v in (s.lowerings, s.recoveries)):
            raise ValueError("bad counters")
        if not _in_bounds_kbps(s.applied_kbps):
            raise ValueError("applied_kbps outside 450-780 Mbit")
        if s.verified not in ("restart", "baseline-assumed", False):
            raise ValueError("bad verified")
        if s.verified_utc is not None:
            _parse_time(s.verified_utc, "verified_utc")
        if s.deferral_since is not None and type(s.deferral_since) not in (int, float):
            raise ValueError("bad deferral_since")
        if s.pending is not None:
            _check_pending(s.pending)
        if s.plan is not None:
            _check_plan(s.plan)
        return s

    def roll(self, today: str) -> None:
        if self.day != today:
            self.day, self.lowerings, self.recoveries = today, 0, 0


STATE_FIELDS = set(State.__dataclass_fields__)
PENDING_KINDS = ("lower", "raise", "recovery", "restore")


def _in_bounds_kbps(v: Any) -> bool:
    return type(v) is int and CAP_MIN_MBIT * 1000 <= v <= CONTROL_KBPS


def _check_date(v: Any, what: str) -> None:
    try:
        date.fromisoformat(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bad {what}") from exc


def _check_pending(p: Any) -> None:
    if not isinstance(p, dict) or set(p) != {"kind", "from_kbps", "to_kbps", "started_utc"}:
        raise ValueError("bad pending")
    if p["kind"] not in PENDING_KINDS or type(p["from_kbps"]) is not int:
        raise ValueError("bad pending")
    if not _in_bounds_kbps(p["to_kbps"]):
        raise ValueError("pending target outside 450-780 Mbit")
    _parse_time(p["started_utc"], "pending started_utc")


def _check_plan(p: Any) -> None:
    """A persisted plan must be exactly what normalize() makes of its bounded original table."""
    if not isinstance(p, dict) or set(p) != set(Plan.__dataclass_fields__):
        raise ValueError("bad plan fields")
    _check_date(p["day"], "plan day")
    for key in ("table_date", "table_sha256", "status_sha256", "failed"):
        if p[key] is not None and not isinstance(p[key], str):
            raise ValueError(f"bad plan {key}")
    orig = p["original"]
    if not isinstance(orig, list) or len(orig) != 24:
        raise ValueError("bad plan original")
    if not all(type(v) is int and CAP_MIN_MBIT <= v <= CONTROL_MBIT for v in orig):
        raise ValueError("plan original outside 450-780 Mbit")
    if p["hours"] != normalize(orig):
        raise ValueError("plan hours are not the normalized original")


class CorruptStateError(Exception):
    """The state file exists but cannot be trusted: ownership is lost."""


def write_atomic(path: Path, data: bytes, like: Path | None = None) -> None:
    """Temp file in the same dir (mode/owner copied from LIKE), fsync, replace, fsync the dir."""
    st = like.stat() if like is not None else None
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            if st is not None:
                os.fchmod(f.fileno(), st.st_mode & 0o7777)
                os.fchown(f.fileno(), st.st_uid, st.st_gid)
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


# --- the shaper (every side effect goes through the runner) ----------------------------------------------------------


@dataclass
class Shaper:
    s: Settings
    run: Runner
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic

    def props(self, unit: str, timeout: float = CMD_TIMEOUT) -> dict[str, str] | None:
        rc, out = self.run(
            [
                "systemctl",
                "show",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "FreezerState",
                "-p",
                "MainPID",
                unit,
            ],
            timeout,
        )
        if rc != 0:
            return None
        props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        keys = ("ActiveState", "SubState", "FreezerState", "MainPID")
        return props if all(props.get(k) for k in keys) else None

    def sweep_timer_pending(self) -> bool:
        """Fail-closed: a state that cannot be read counts as pending."""
        rc, out = self.run(
            ["systemctl", "show", "-p", "SubState", "--value", self.s.sweep_timer], CMD_TIMEOUT
        )
        return rc != 0 or out.strip() == "waiting"

    def bypass_inline(self, timeout: float = CMD_TIMEOUT) -> bool:
        """`silicom-bypass status <pair>`: exit 0 and one line saying non-Bypass and non-Disconnect, nothing else."""
        rc, out = self.run([self.s.bypass_cmd, "status", self.s.bypass_pair], timeout)
        lines = out.strip().splitlines()
        if rc != 0 or len(lines) != 1:
            return False
        m = re.fullmatch(
            rf"{re.escape(self.s.bypass_pair)}: bypass=(.*?) disc=(.*?) std_nic=(.*)", lines[0]
        )
        return bool(m and "non-Bypass" in m.group(1) and "non-Disconnect" in m.group(2))

    def restart(self) -> bool:
        rc, _ = self.run(["systemctl", "restart", self.s.unit, self.s.bridge], RESTART_TIMEOUT)
        return rc == 0

    def _left(self, deadline: float) -> float:
        """Time a command may still take before DEADLINE (capped at CMD_TIMEOUT); <= 0 means none."""
        return min(CMD_TIMEOUT, deadline - self.monotonic())

    def _pass(self, deadline: float) -> str | None:
        """The controller's MainPID when every live check passes before DEADLINE, else None."""
        unit = bridge = None
        if self._left(deadline) > 0:
            unit = self.props(self.s.unit, self._left(deadline))
        if unit is not None and self._left(deadline) > 0:
            bridge = self.props(self.s.bridge, self._left(deadline))
        if unit is None or bridge is None or self._left(deadline) <= 0:
            return None
        ok = (
            unit["ActiveState"] == "active"
            and unit["SubState"] == "running"
            and unit["FreezerState"] == "running"
            and unit["MainPID"] != "0"
            and bridge["ActiveState"] == "active"
            and self.bypass_inline(self._left(deadline))
        )
        return unit["MainPID"] if ok else None

    def verify(self) -> bool:
        """Three consecutive passes VERIFY_INTERVAL apart with the same MainPID, all completed within VERIFY_WINDOW.

        Every command gets only the time left, and a pass that completes after the deadline does not count.
        """
        deadline = self.monotonic() + VERIFY_WINDOW
        pids: list[str] = []
        while True:
            pid = self._pass(deadline)
            if self.monotonic() > deadline:
                return False
            if pid is None:
                pids = []
            elif pids and pids[-1] != pid:
                pids = [pid]  # the controller restarted again: start counting over
            else:
                pids.append(pid)
            if len(pids) >= VERIFY_PASSES:
                return True
            if self.monotonic() + VERIFY_INTERVAL > deadline:
                return False
            self.sleep(VERIFY_INTERVAL)


# --- the applier -----------------------------------------------------------------------------------------------------


@dataclass
class Applier:
    s: Settings
    shaper: Shaper
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    log_lines: list[str] = field(default_factory=list)
    owner_asserted: bool = False  # `restore --take-ownership`: a human asserted ownership

    @property
    def state_file(self) -> Path:
        return self.s.state_dir / "state.json"

    # logging

    def log(self, event: str, **fields: Any) -> None:
        rec = {"utc": self.now().isoformat(timespec="seconds"), "event": event, **fields}
        line = json.dumps(rec, sort_keys=True)
        self.log_lines.append(line)
        try:
            self.s.state_dir.mkdir(parents=True, exist_ok=True)
            with (self.s.state_dir / "events.jsonl").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as exc:
            print(f"wanctl-ceiling-apply: cannot append event: {exc}", file=sys.stderr)
        self.shaper.run(["logger", "-t", "wanctl-ceiling-apply", "--", line], CMD_TIMEOUT)
        print(line)

    # state and config

    def load_state(self) -> State | None:
        try:
            raw = self.state_file.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise CorruptStateError(str(exc)) from exc
        try:
            return State.parse(raw)
        except (ValueError, TypeError) as exc:
            raise CorruptStateError(str(exc)) from exc

    def save(self, st: State) -> None:
        self.s.state_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(self.state_file, (json.dumps(asdict(st), indent=2) + "\n").encode())

    def read_config(self) -> tuple[bytes, int, int, int]:
        """(bytes, min, base, max) in kbps; each of the three lines must occur exactly once."""
        raw = self.s.config.read_bytes()
        text = raw.decode("utf-8")
        vals = []
        for rx in (MIN_DL_RE, BASE_DL_RE, MAX_DL_RE):
            found = rx.findall(text)
            if len(found) != 1:
                raise RefusedError(EXIT_ERROR, f"config: {rx.pattern} found {len(found)} times")
            vals.append(int(found[0]))
        return raw, vals[0], vals[1], vals[2]

    def write_config(self, raw: bytes, to_kbps: int) -> None:
        new = MAX_DL_RE.sub(f"max_dl_shaper_rate_kbps={to_kbps}", raw.decode("utf-8")).encode()
        if new == raw:
            return
        prev = self.s.config.with_name(self.s.config.name + ".ceiling-apply.prev")
        if not prev.exists():
            write_atomic(prev, raw, like=self.s.config)
        write_atomic(self.s.config, new, like=self.s.config)

    # plan and target

    def plan_for_today(self, st: State, now: datetime) -> Plan | None:
        local = now.astimezone(CT)
        today = local.date().isoformat()
        plan = Plan(**st.plan) if st.plan and st.plan.get("day") == today else None
        if plan is None:
            if local.hour >= PLAN_UNTIL_HOUR:
                return None
            try:
                tdate, tsha, ssha, recs = load_inputs(self.s.table_dir, now)
            except (OSError, ValueError) as exc:
                self.log("no-plan", reason=str(exc))
                return None
            plan = Plan(today, tdate, tsha, ssha, recs, normalize(recs))
            st.plan = asdict(plan)
            self.save(st)
            self.log(
                "plan-fixed",
                table_date=tdate,
                table_sha256=tsha,
                original=recs,
                effective=plan.hours,
            )
            return plan
        if plan.failed is None:
            try:
                recheck_inputs(plan, self.s.table_dir, now)
            except (OSError, ValueError) as exc:
                plan.failed = str(exc)
                st.plan = asdict(plan)
                self.save(st)
                self.log("fallback", reason=plan.failed)
        return plan

    def target(self, st: State, now: datetime) -> tuple[int, str]:
        """(target Mbit, reason) for this run."""
        if self.s.off_file.exists():
            return CONTROL_MBIT, "off-switch"
        plan = self.plan_for_today(st, now)
        if plan is None:
            return CONTROL_MBIT, "fallback: no valid plan today"
        if plan.failed:
            return CONTROL_MBIT, f"fallback: {plan.failed}"
        return plan.hours[now.astimezone(CT).hour], "plan"

    # the transaction

    def clean_shaper(self, recovery: bool) -> None:
        """RefusedError unless the shaper is clean (or, for the applier's own recovery, merely unheld)."""
        if self.s.sweep_marker.exists():
            raise RefusedError(EXIT_DEFERRED, "deferred: sweep hold marker present")
        if self.shaper.sweep_timer_pending():
            raise RefusedError(
                EXIT_DEFERRED, "deferred: sweep dead-man timer pending or unreadable"
            )
        props = self.shaper.props(self.s.unit)
        if props is None:
            raise RefusedError(EXIT_DEFERRED, "deferred: controller state unreadable")
        if props["FreezerState"] != "running":
            raise RefusedError(EXIT_DEFERRED, f"deferred: controller {props['FreezerState']}")
        if props["ActiveState"] != "active" and not recovery:
            raise RefusedError(EXIT_ERROR, f"unit-inactive-not-ours: {props['ActiveState']}")

    def transaction(self, st: State, kind: str, to_kbps: int) -> int:
        """Intent (budget reserved) -> config -> restart -> verify -> commit. Kinds: lower, raise, recovery, restore;
        only lower and recovery consume a daily budget, both at intent. A failure to anything but 780 is followed by
        one recovery to 780 in the same run while the recovery budget lasts."""
        if not _in_bounds_kbps(to_kbps):
            raise RefusedError(
                EXIT_ERROR, f"{to_kbps} kbps is outside the hard 450-780 Mbit bounds"
            )
        raw, mn, base, cur = self.read_config()
        # re-checked here, under the sweep lock: the value may have changed while this run waited for it
        if not self.owner_asserted and cur not in self.recognized(st):
            raise RefusedError(EXIT_ERROR, f"foreign-value: {cur} kbps at the change")
        if not mn <= base <= to_kbps:
            raise RefusedError(EXIT_ERROR, f"min {mn} <= base {base} <= {to_kbps} does not hold")
        st.pending = {
            "kind": kind,
            "from_kbps": cur,
            "to_kbps": to_kbps,
            "started_utc": self.now().isoformat(timespec="seconds"),
        }
        if kind == "lower":
            st.lowerings += 1
        if kind == "recovery":
            st.recoveries += 1
        try:
            self.save(st)  # intent, with the budget reserved, before anything changes
        except OSError as exc:
            raise RefusedError(EXIT_ERROR, f"cannot record intent: {exc}") from exc
        self.log("apply-start", kind=kind, from_kbps=cur, to_kbps=to_kbps)
        self.write_config(raw, to_kbps)
        if self.shaper.restart() and self.shaper.verify():
            st.applied_kbps, st.verified, st.pending, st.deferral_since = (
                to_kbps,
                "restart",
                None,
                None,
            )
            st.verified_utc = self.now().isoformat(timespec="seconds")
            try:
                self.save(st)
            except OSError as exc:
                self.log("commit-failed", error=str(exc))
                return EXIT_ERROR
            self.log("applied", kind=kind, ceiling_kbps=to_kbps, verified="restart")
            return EXIT_OK
        st.verified = False
        self.save(st)
        self.log("CRITICAL-unverified", kind=kind, to_kbps=to_kbps)
        if to_kbps != CONTROL_KBPS and st.recoveries < RECOVERIES_PER_DAY:
            return self.transaction(st, "recovery", CONTROL_KBPS)
        return EXIT_UNVERIFIED

    def guarded(self, st: State, kind: str, to_kbps: int, recovery: bool) -> int:
        """Take the sweep lock, check the shaper, run the transaction; deferrals are recorded and may escalate."""
        fd = os.open(self.s.sweep_lock, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            if not self._lock_wait(fd):
                raise RefusedError(EXIT_DEFERRED, "deferred: sweep lock busy")
            self.clean_shaper(recovery)
            return self.transaction(st, kind, to_kbps)
        except RefusedError as r:
            if r.code != EXIT_DEFERRED:
                raise
            return self._deferred(st, r.reason, to_kbps)
        finally:
            os.close(fd)

    def _lock_wait(self, fd: int) -> bool:
        deadline = self.shaper.monotonic() + SWEEP_LOCK_WAIT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if self.shaper.monotonic() >= deadline:
                    return False
                self.shaper.sleep(0.5)

    def _deferred(self, st: State, reason: str, to_kbps: int) -> int:
        now = self.now().timestamp()
        if st.deferral_since is None:
            st.deferral_since = now
            self.save(st)
        waited = now - st.deferral_since
        if to_kbps == CONTROL_KBPS and waited >= ESCALATE_AFTER:
            self.log(
                "CRITICAL-deferred",
                reason=reason,
                minutes=int(waited // 60),
                action="check `wanctl-sweep-cap status`; a stuck sweep is the operator's to recover",
            )
            return EXIT_ERROR
        self.log("deferred", reason=reason, to_kbps=to_kbps)
        return EXIT_DEFERRED

    # entry points

    def tick(self) -> int:
        now = self.now()
        today = now.astimezone(CT).date().isoformat()
        try:
            st = self.load_state()
        except CorruptStateError as exc:
            self.log("CRITICAL-state-unreadable", error=str(exc), action="manual recovery required")
            return EXIT_UNVERIFIED
        raw, _, _, cur = self.read_config()
        if st is None:
            if cur != CONTROL_KBPS:
                raise RefusedError(EXIT_ERROR, f"foreign-value: {cur} kbps with no state")
            st = State(day=today)
            self.save(st)
            self.log("bootstrap", ceiling_kbps=cur, verified="baseline-assumed")
        st.roll(today)
        if cur not in self.recognized(st):
            raise RefusedError(EXIT_ERROR, f"foreign-value: {cur} kbps (applied {st.applied_kbps})")
        if st.pending is not None or st.verified is False:
            return self._recover(st)
        mbit, reason = self.target(st, now)
        return self._move(st, cur, mbit * 1000, reason, now)

    def recognized(self, st: State) -> set[int]:
        """Config values the applier may edit from: 780000, its own last value, either end of its pending change."""
        known = {CONTROL_KBPS, st.applied_kbps}
        if st.pending is not None:
            known |= {st.pending["from_kbps"], st.pending["to_kbps"]}  # ints (State.parse)
        return known

    def _recover(self, st: State) -> int:
        if st.recoveries >= RECOVERIES_PER_DAY:
            self.log("CRITICAL-recovery-exhausted", action="manual recovery required")
            return EXIT_UNVERIFIED
        return self.guarded(st, "recovery", CONTROL_KBPS, recovery=True)

    def _move(self, st: State, cur: int, to: int, reason: str, now: datetime) -> int:
        if to < CONTROL_KBPS and st.applied_kbps < CONTROL_KBPS and to != st.applied_kbps:
            to, reason = CONTROL_KBPS, "no move between two lowered values"
        if cur == st.applied_kbps == to:
            if st.verified == "restart" or to == CONTROL_KBPS:
                if st.deferral_since is not None:
                    st.deferral_since = None
                    self.save(st)
                if to == CONTROL_KBPS and reason != "plan":
                    note = (
                        f"780 verified at {st.verified_utc}"
                        if st.verified == "restart"
                        else "780 configured; running ceiling not verified (baseline-assumed)"
                    )
                    self.log("no-op", reason=reason, note=note)
                return EXIT_OK
        if to == CONTROL_KBPS:
            return self.guarded(st, "raise", to, recovery=False)
        if now.astimezone(CT).minute >= LOWER_MINUTES:
            self.log("lowering-waits", reason="not on an hour boundary", to_kbps=to)
            return EXIT_OK
        if st.lowerings >= LOWERINGS_PER_DAY:
            self.log("budget-exhausted", to_kbps=to)
            return EXIT_OK
        return self.guarded(st, "lower", to, recovery=False)

    def restore(self, take_ownership: bool) -> int:
        """Human command: 780 with a verified restart, whether enabled or not."""
        self.owner_asserted = take_ownership  # the only exception to the foreign-value rule
        now = self.now()
        today = now.astimezone(CT).date().isoformat()
        try:
            st = self.load_state()
        except CorruptStateError as exc:
            if not take_ownership:
                self.log(
                    "CRITICAL-state-unreadable", error=str(exc), action="restore --take-ownership"
                )
                return EXIT_UNVERIFIED
            return self._take_ownership(today)
        _, _, _, cur = self.read_config()
        if st is None:
            if cur != CONTROL_KBPS and not take_ownership:
                raise RefusedError(EXIT_ERROR, f"foreign-value: {cur} kbps with no state")
            st = State(day=today)  # no ownership evidence: the same rules as a bootstrap tick
        st.roll(today)
        if (
            st.pending is None
            and st.applied_kbps == cur == CONTROL_KBPS
            and st.verified == "restart"
        ):
            self.log("no-op", reason="restore", note=f"780 verified at {st.verified_utc}")
            return EXIT_OK
        if cur not in self.recognized(st) and not take_ownership:
            raise RefusedError(EXIT_ERROR, f"foreign-value: {cur} kbps")
        owned = take_ownership or st.pending is not None or st.verified is False
        return self.guarded(st, "restore", CONTROL_KBPS, recovery=owned)

    def _take_ownership(self, today: str) -> int:
        stamp = self.now().strftime("%Y%m%dT%H%M%SZ")
        keep = self.state_file.with_name(f"state.json.corrupt-{stamp}")
        write_atomic(keep, self.state_file.read_bytes())
        st = State(
            day=today, lowerings=LOWERINGS_PER_DAY, recoveries=RECOVERIES_PER_DAY, verified=False
        )
        self.log("take-ownership", preserved=keep.name)
        return self.guarded(st, "restore", CONTROL_KBPS, recovery=True)


# --- command line ----------------------------------------------------------------------------------------------------


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply the shadow per-hour table to the Spectrum download ceiling"
    )
    p.add_argument("--env-file", type=Path, default=Path(DEFAULT_ENV_FILE))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tick", help="one scheduled decision (does nothing unless enabled)")
    sub.add_parser("plan", help="read-only: today's table, effective plan and why")
    r = sub.add_parser("restore", help="780 with a verified restart (works when disabled)")
    r.add_argument(
        "--take-ownership", action="store_true", help="after a corrupt state, asserted by a human"
    )
    sub.add_parser("status", help="read-only: state, config value, off switch")
    return p.parse_args(argv)


def show_plan(s: Settings, now: datetime) -> int:
    try:
        tdate, tsha, _, recs = load_inputs(s.table_dir, now)
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "reason": str(exc), "effective": [CONTROL_MBIT] * 24}))
        return EXIT_OK
    print(
        json.dumps(
            {
                "valid": True,
                "table_date": tdate,
                "table_sha256": tsha,
                "original": recs,
                "effective": normalize(recs),
            }
        )
    )
    return EXIT_OK


def show_status(s: Settings) -> int:
    out: dict[str, Any] = {"off_switch": s.off_file.exists()}
    try:
        out["state"] = json.loads((s.state_dir / "state.json").read_bytes())
    except FileNotFoundError:
        out["state"] = None
    except (OSError, ValueError) as exc:
        out["state"] = f"unreadable: {exc}"
    try:
        found = MAX_DL_RE.findall(s.config.read_text(encoding="utf-8"))
        out["config_max_dl_kbps"] = found
    except OSError as exc:
        out["config_max_dl_kbps"] = f"unreadable: {exc}"
    print(json.dumps(out, indent=2))
    return EXIT_OK


def main(
    argv: list[str] | None = None,
    runner: Runner = run_command,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> int:
    a = parse_args(argv)
    try:
        env = read_env(a.env_file)
    except RefusedError as r:
        print(f"wanctl-ceiling-apply: {r.reason}", file=sys.stderr)
        return r.code
    if a.cmd == "tick" and (env is None or env["CEILING_APPLY_ENABLED"] != "1"):
        return EXIT_OK  # disabled: nothing read beyond the env file, nothing written, nothing run
    s = Settings.from_env(env or dict(DEFAULTS))
    clock = now or (lambda: datetime.now(UTC))
    if a.cmd == "plan":
        return show_plan(s, clock())
    if a.cmd == "status":
        return show_status(s)
    app = Applier(s, Shaper(s, runner, sleep, monotonic), clock)
    s.lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(s.lock, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("wanctl-ceiling-apply: another run holds the lock", file=sys.stderr)
            return EXIT_DEFERRED
        return app.tick() if a.cmd == "tick" else app.restore(a.take_ownership)
    except RefusedError as r:
        app.log("refused", reason=r.reason)
        return r.code
    except (OSError, ValueError) as exc:
        app.log("error", error=str(exc))
        return EXIT_ERROR
    finally:
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())

"""Synthetic tests for the sweep mode of scripts/rrul-slot.sh: cap holds on the shaper, one restore, failure paths.

Builds on the fakes of tests/test_rrul_slot.py (flent, fping, prom-ro, pgrep; PATH holds only fakes and linked local
tools, so no real flent, ssh or Prometheus can run). The fake ssh here stands in for the shaper: it answers the
read-only max_dl_shaper_rate_kbps grep and emulates wanctl-sweep-cap r2 (hold/restore/status) with a state file, so a
test can see what the shaper would be left in. The shaper alias is a reserved .invalid name and the endpoint is
endpoint.invalid; nothing resolves or connects.

Protocol emulated (wanctl-sweep-cap r2, sha256 65f8b942..., the reviewed copy the advisor installed 2026-10-20):
  hold <mbit>  first hold arms a 600 s dead-man restore and writes the hold marker; later holds keep that deadline.
               Freezes the controller and sets the CAKE rate. Exit 0, or 2/3/4/5/6/7 on refusal or failure; 7 (rate
               check failed) leaves the controller frozen.
  restore      thaw + restart, verified; cancels the dead-man timer and removes the marker. Exit 0 ("nothing held"
               included) or 8 after three failed attempts, marker kept.
  status       "unit=.. freezer=.. rate=.. hold_since=.. dead_man_pending=yes|no", read-only.
"""

from __future__ import annotations

import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests import test_rrul_slot as base
from tests.test_rrul_slot import (
    COLUMNS,
    CONTEXT,
    CSV_NAME,
    HEADER,
    MEASURED,
    SCRIPT,
    _alive,
    _install,
    _pids,
    _set_flent_data,
    flent_data,
)

# The fake-tool fixtures of test_rrul_slot.py, made available to this module's tests.
host_tools = base.host_tools
env = base.env

SHAPER = "shaper.invalid"
ENDPOINT = "endpoint.invalid"

# State file lines: frozen (yes/no), rate (Mbit), hold_since (epoch or none), dead_man (yes/no).
# Knobs: FAKE_HOLD_FAIL="<cap>:<rc>" fails that hold (rc 7 leaves it frozen at the old rate, like r2),
# FAKE_HOLD_HANG=<cap> (hangs before acquiring), FAKE_HOLD_HANG_AFTER=any (the first hold acquires, then hangs),
# FAKE_RESTORE_RC, FAKE_RESTORE_SEC (restore duration), FAKE_STATUS_MODE: ok, garbage, garbage-held (unparsable while
# a cap is held), garbage-restored (unparsable once a restore ran), dirty (a hold already in place), stuck (still frozen
# after restore), lost (the hold is gone after the next load).
FAKE_SHAPER_SSH = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/ssh.pids"
cmd=${@: -1}
echo "$cmd" >> "$FAKE_DIR/shaper.calls"
case $cmd in
  grep*) echo 780000; exit 0 ;;
esac
st=$FAKE_DIR/shaper.state
[ -f "$st" ] || printf 'no\n700\nnone\nno\n' > "$st"
{ read -r frozen; read -r rate; read -r since; read -r dm; } < "$st"
save() { printf '%s\n%s\n%s\n%s\n' "$frozen" "$rate" "$since" "$dm" > "$st"; }
set -- $cmd
[ "$1" = /usr/local/sbin/wanctl-sweep-cap ] || { echo "unexpected remote command: $cmd" >&2; exit 127; }
case $2 in
  status)
    case ${FAKE_STATUS_MODE:-ok} in
      garbage) echo "Permission denied"; exit 0 ;;
      garbage-held) [ "$frozen" = yes ] && { echo "Permission denied"; exit 0; } ;;
      garbage-restored) [ -f "$FAKE_DIR/restored" ] && { echo "Permission denied"; exit 0; } ;;
      dirty) echo "unit=active freezer=frozen rate=500Mbit hold_since=1792600000 dead_man_pending=yes"; exit 0 ;;
      lost) [ -f "$FAKE_DIR/flent.pids" ] && [ "$frozen" = yes ] && frozen=no ;;
      stuck) [ -f "$FAKE_DIR/restored" ] && frozen=yes ;;
    esac
    f=running; [ "$frozen" = yes ] && f=frozen
    echo "unit=active freezer=$f rate=${rate}Mbit hold_since=$since dead_man_pending=$dm" ;;
  hold)
    [ "${FAKE_HOLD_HANG:-}" = "$3" ] && while :; do sleep 1; done
    if [ "$since" = none ]; then since=$(date +%s); dm=yes; fi
    frozen=yes
    case ${FAKE_HOLD_FAIL:-} in
      "$3":7) save; echo "rate check failed: wanted ${3}Mbit got ${rate}Mbit"; exit 7 ;;
      "$3":*) save; exit "${FAKE_HOLD_FAIL#*:}" ;;
    esac
    rate=$3; save
    [ -n "${FAKE_HOLD_HANG_AFTER:-}" ] && while :; do sleep 1; done
    echo "hold ${3}Mbit: freezer=frozen active=active rate=${3}Mbit" ;;
  restore)
    sleep "${FAKE_RESTORE_SEC:-0}"
    : > "$FAKE_DIR/restored"
    [ "${FAKE_RESTORE_RC:-0}" = 0 ] || { echo "RESTORE FAILED after 3 attempts"; exit "$FAKE_RESTORE_RC"; }
    frozen=no rate=700 since=none dm=no; save; echo "restore ok" ;;
  *) exit 2 ;;
esac
"""


@pytest.fixture
def senv(env: dict[str, str]) -> dict[str, str]:
    _install(Path(env["PATH"].split(":")[0]), "ssh", FAKE_SHAPER_SSH)
    return {
        **env,
        "RRUL_SLOT_HOST": ENDPOINT,
        "RRUL_SLOT_SHAPER_SSH": SHAPER,
        "RRUL_SLOT_SWEEP_GAP_SEC": "0",
        "RRUL_SLOT_SWEEP_SEED": "7",
    }


def _sweep(
    tmp_path: Path, environ: dict[str, str], *extra: str, timeout: int = 28
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--data-dir",
            str(tmp_path / "data"),
            "--mode",
            "sweep",
            *extra,
            "eve",
        ],
        env=environ,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _rows(tmp_path: Path) -> list[dict[str, str]]:
    path = tmp_path / "data" / CSV_NAME
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    assert lines[0] == HEADER
    return [dict(zip(COLUMNS, line.split(","), strict=True)) for line in lines[1:]]


def _calls(environ: dict[str, str]) -> list[str]:
    path = Path(environ["FAKE_DIR"]) / "shaper.calls"
    words = [line.split()[1:] for line in path.read_text().splitlines()] if path.exists() else []
    return [" ".join(w) for w in words if w and w[0] in ("hold", "restore", "status")]


def _state(environ: dict[str, str]) -> list[str]:
    path = Path(environ["FAKE_DIR"]) / "shaper.state"
    return path.read_text().split() if path.exists() else ["no", "700", "none", "no"]


def _result(tmp_path: Path) -> str:
    (run,) = (tmp_path / "data" / "runs").iterdir()
    return (run / "result").read_text()


def _assert_released(environ: dict[str, str]) -> None:
    """Every hold is followed by exactly one restore, after the last hold, and the shaper is left unheld."""
    calls = _calls(environ)
    holds = [i for i, c in enumerate(calls) if c.startswith("hold")]
    restores = [i for i, c in enumerate(calls) if c == "restore"]
    if holds:
        assert len(restores) == 1 and restores[0] > holds[-1], calls
    else:
        assert not restores, calls


def _no_owned_left(environ: dict[str, str]) -> None:
    assert not any(
        _alive(p) for p in _pids(environ, "flent") + _pids(environ, "fping") + _pids(environ, "ssh")
    )


def test_complete_sweep_holds_each_cap_once_and_restores_once(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    proc = _sweep(tmp_path, senv)
    assert proc.returncode == 0, proc.stderr
    assert "status=complete" in _result(tmp_path) and "restore=ok" in _result(tmp_path)

    rows = _rows(tmp_path)
    assert [r["sweep_order"] for r in rows] == ["1/3", "2/3", "3/3"]
    caps = [r["tested_cap"] for r in rows]
    assert sorted(caps, key=int) == ["480", "620", "780"]
    for r in rows:
        assert r["schema"] == "rrul-v2" and r["mode"] == "sweep" and r["status"] == "complete"
        assert (
            r["reason"] == "measured"
            and r["restore"] == "ok"
            and r["max_dl_config_kbps"] == "780000"
        )
        assert r["sweep_id"] == r["run"] and r["dl_mbit"] == "763.2" and r["household_dl_mbit"]
        assert all(r[c] for c in CONTEXT)

    calls = _calls(senv)
    holds = [c.split()[1] for c in calls if c.startswith("hold")]
    assert holds == caps
    # clean-shaper check, then per cap: hold, status after the hold, status after the load; then restore + check
    assert calls == ["status"] + [x for c in caps for x in (f"hold {c}", "status", "status")] + [
        "restore",
        "status",
    ]
    _assert_released(senv)
    assert _state(senv) == ["no", "700", "none", "no"]
    _no_owned_left(senv)

    # each held run has its own flent title and directory
    args = (Path(senv["FAKE_DIR"]) / "flent.args").read_text().splitlines()
    assert [a.split()[a.split().index("-t") + 1].rsplit("-", 1)[1] for a in args] == [
        "c1",
        "c2",
        "c3",
    ]


def _seed_order(tmp_path: Path, environ: dict[str, str], seed: str) -> tuple[str, ...]:
    """The cap order a seed gives, without a held run: the order is drawn before the clean-shaper check, and an
    unreadable status stops the sweep there with every cap already written to its row."""
    d = tmp_path / f"order{seed}"
    proc = _sweep(d, {**environ, "RRUL_SLOT_SWEEP_SEED": seed, "FAKE_STATUS_MODE": "garbage"})
    assert proc.returncode == 1, proc.stderr
    return tuple(r["tested_cap"] for r in _rows(d))


# One full sweep per test: three in one body ran close to the 30 s per-test timeout and exceeded it on a loaded runner.
@pytest.mark.parametrize("seed", ["1", "2", "3"])
def test_seeded_sweep_always_includes_the_control(
    tmp_path: Path, senv: dict[str, str], seed: str
) -> None:
    d = tmp_path / "full"
    assert _sweep(d, {**senv, "RRUL_SLOT_SWEEP_SEED": seed}).returncode == 0
    caps = tuple(r["tested_cap"] for r in _rows(d))
    assert "780" in caps and sorted(caps) == ["480", "620", "780"]
    # the full sweep runs in the order the cheap probe below reports for the same seed
    assert caps == _seed_order(tmp_path, senv, seed)


def test_order_is_random_and_always_includes_the_control(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    seen = set()
    for seed in ("1", "2", "3"):
        caps = _seed_order(tmp_path, senv, seed)
        assert "780" in caps and sorted(caps) == ["480", "620", "780"]
        seen.add(caps)
    assert len(seen) > 1, seen
    assert _calls(senv) == ["status"] * 3 and not _pids(senv, "flent")


@pytest.mark.parametrize(
    ("knobs", "reason"),
    [
        ({"FAKE_HOLD_FAIL": "SECOND:7"}, "hold-failed:SECOND:rc=7"),
        ({"FAKE_HOLD_FAIL": "SECOND:5"}, "hold-failed:SECOND:rc=5"),
        ({"FAKE_HOLD_FAIL": "SECOND:255"}, "hold-failed:SECOND:rc=255"),
    ],
)
def test_failed_hold_restores_and_keeps_earlier_rows(
    tmp_path: Path, senv: dict[str, str], knobs: dict[str, str], reason: str
) -> None:
    # learn the order of this seed first, then fail the second cap's hold
    probe = tmp_path / "probe"
    assert _sweep(probe, senv).returncode == 0
    order = [r["tested_cap"] for r in _rows(probe)]
    (Path(senv["FAKE_DIR"]) / "shaper.calls").unlink()
    (Path(senv["FAKE_DIR"]) / "shaper.state").unlink()
    knobs = {k: v.replace("SECOND", order[1]) for k, v in knobs.items()}
    reason = reason.replace("SECOND", order[1])

    proc = _sweep(tmp_path, {**senv, **knobs})
    assert proc.returncode == 1, proc.stderr
    assert reason in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    first, second, third = _rows(tmp_path)
    assert first["status"] == "complete" and first["restore"] == "ok"
    assert second["status"] == "invalid" and second["reason"] == reason
    assert third["status"] == "skipped" and third["reason"] == f"sweep-stopped:{reason}"
    assert all(second[c] == "" and third[c] == "" for c in MEASURED)
    assert not [c for c in _calls(senv) if c == f"hold {order[2]}"]
    _assert_released(senv)
    assert _state(senv)[0] == "no"
    _no_owned_left(senv)


def test_unreadable_status_before_the_first_hold_holds_nothing(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_STATUS_MODE": "garbage"})
    assert proc.returncode == 1, proc.stderr
    assert "shaper-status-unreadable" in _result(tmp_path)
    assert _calls(senv) == ["status"] and not _pids(senv, "flent")
    rows = _rows(tmp_path)
    assert [r["status"] for r in rows] == ["invalid", "skipped", "skipped"]
    assert all(r["restore"] == "none" for r in rows)


def test_lost_hold_marks_the_row_and_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_STATUS_MODE": "lost"})
    assert "hold-lost:" in _result(tmp_path), proc.stderr
    first = _rows(tmp_path)[0]
    assert first["status"] == "invalid" and first["reason"].startswith("hold-lost:")
    assert all(first[c] == "" for c in MEASURED)
    _assert_released(senv)
    _no_owned_left(senv)


def test_shaper_already_held_is_never_touched(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_STATUS_MODE": "dirty"})
    assert proc.returncode == 1, proc.stderr
    assert "shaper-not-ready:" in _result(tmp_path)
    assert _calls(senv) == ["status"]
    assert not _pids(senv, "flent")


def test_breach_during_held_load_restores_at_once(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_FPING_MODE": "loss", "FAKE_FLENT_MODE": "hang"})
    assert proc.returncode == 3, proc.stderr
    assert "status=breach-stop" in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    first, *rest = _rows(tmp_path)
    assert first["status"] == "breach-stop" and all(r["status"] == "skipped" for r in rest)
    assert len([c for c in _calls(senv) if c.startswith("hold")]) == 1
    _assert_released(senv)
    _no_owned_left(senv)


def test_flent_failure_during_held_load_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_FLENT_MODE": "fail"})
    assert proc.returncode == 1, proc.stderr
    assert "flent-rc-1" in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    _assert_released(senv)


def test_competing_load_before_a_later_cap_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    # pgrep finds nothing for the start and before-load checks, then a competing netperf before the second cap
    fake_bin = Path(senv["PATH"].split(":")[0])
    _install(
        fake_bin,
        "pgrep",
        "#!/usr/bin/env bash\n"
        'n=0; [ -f "$FAKE_DIR/pgrep.calls" ] && while read -r _; do n=$((n + 1)); done < "$FAKE_DIR/pgrep.calls"\n'
        'echo "$*" >> "$FAKE_DIR/pgrep.calls"\n'
        '[ "$n" -ge 2 ] && { echo "4242 netperf -H 198.51.100.1"; exit 0; }\nexit 1\n',
    )
    proc = _sweep(tmp_path, senv)
    assert proc.returncode == 75, proc.stderr
    assert "competing-load:before-load-2" in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    first, second, _ = _rows(tmp_path)
    assert first["status"] == "complete" and second["status"] == "skipped"
    _assert_released(senv)


@pytest.mark.parametrize(
    ("knobs", "expect"),
    [
        ({"FAKE_RESTORE_RC": "8"}, "restore=failed:rc=8"),
        ({"FAKE_STATUS_MODE": "stuck"}, "restore=unverified:unit=active/freezer=frozen"),
    ],
)
def test_unconfirmed_restore_is_an_explicit_failure(
    tmp_path: Path, senv: dict[str, str], knobs: dict[str, str], expect: str
) -> None:
    proc = _sweep(tmp_path, {**senv, **knobs})
    assert proc.returncode == 6, proc.stderr
    result = _result(tmp_path)
    assert "status=restore-failed" in result and expect in result
    assert "RESTORE NOT CONFIRMED" in proc.stderr and "restore ok:" not in proc.stderr
    # a scheduled dead-man attempt is never presented as assured recovery
    assert "recovery is NOT assured" in proc.stderr and "restores within" not in proc.stderr
    rows = _rows(tmp_path)
    assert rows and all(r["restore"].startswith(expect.removeprefix("restore=")) for r in rows)
    _assert_released(senv)


def test_restore_failure_after_a_breach_still_exits_6(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(
        tmp_path,
        {**senv, "FAKE_FPING_MODE": "loss", "FAKE_FLENT_MODE": "hang", "FAKE_RESTORE_RC": "8"},
    )
    assert proc.returncode == 6, proc.stderr
    assert "status=restore-failed" in _result(tmp_path) and "sustained-breach" in _result(tmp_path)


def _start(tmp_path: Path, environ: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        ["bash", str(SCRIPT), "--data-dir", str(tmp_path / "data"), "--mode", "sweep", "eve"],
        env=environ,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for(pred, limit: float = 10.0) -> None:
    end = time.monotonic() + limit
    while not pred() and time.monotonic() < end:
        time.sleep(0.05)
    assert pred()


def test_sigterm_during_held_load_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    run = _start(tmp_path, {**senv, "FAKE_FLENT_MODE": "hang"})
    _wait_for(lambda: bool(_pids(senv, "flent")))
    owned = _pids(senv, "flent") + _pids(senv, "fping")
    run.send_signal(signal.SIGTERM)
    assert run.wait(timeout=15) == 143, run.stderr.read()
    assert "status=aborted" in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    assert not any(_alive(p) for p in owned)
    _assert_released(senv)
    assert _state(senv)[0] == "no"


def test_sigterm_during_hold_command_still_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    # the first cap's hold hangs (e.g. waiting on the shaper's lock); the signal kills the ssh, then restore runs
    probe = tmp_path / "probe"
    assert _sweep(probe, senv).returncode == 0
    first = _rows(probe)[0]["tested_cap"]
    (Path(senv["FAKE_DIR"]) / "shaper.calls").unlink()
    run = _start(tmp_path, {**senv, "FAKE_HOLD_HANG": first})
    _wait_for(lambda: f"hold {first}" in _calls(senv))
    run.send_signal(signal.SIGTERM)
    assert run.wait(timeout=15) == 143, run.stderr.read()
    assert "restore=ok" in _result(tmp_path)
    assert _calls(senv)[-2:] == ["restore", "status"]
    _no_owned_left(senv)


def test_signal_during_restore_does_not_interrupt_it(tmp_path: Path, senv: dict[str, str]) -> None:
    run = _start(tmp_path, {**senv, "FAKE_RESTORE_SEC": "3"})
    _wait_for(lambda: "restore" in _calls(senv), limit=20)
    run.send_signal(signal.SIGTERM)
    rc = run.wait(timeout=20)
    err = run.stderr.read()
    assert "received while restoring; continuing" in err, err
    assert (Path(senv["FAKE_DIR"]) / "restored").exists() and _state(senv)[0] == "no"
    assert "restore=ok" in _result(tmp_path)
    assert rc == 1 and "signal-TERM" in _result(tmp_path)
    _assert_released(senv)


def test_dead_man_budget_stops_before_a_run_that_could_outlast_it(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    # A held run is budgeted at its worst case (about 295 s). With an assumed 330 s dead-man window and an 8 s gap,
    # the first cap fits and the second would not.
    proc = _sweep(
        tmp_path, {**senv, "RRUL_SLOT_DEAD_MAN_SEC": "330", "RRUL_SLOT_SWEEP_GAP_SEC": "8"}
    )
    assert proc.returncode == 1, proc.stderr
    assert "status=incomplete" in _result(tmp_path) and "dead-man-budget" in _result(tmp_path)
    first, *rest = _rows(tmp_path)
    assert first["status"] == "complete" and first["restore"] == "ok"
    assert [r["reason"] for r in rest] == ["dead-man-budget", "dead-man-budget"]
    assert len([c for c in _calls(senv) if c.startswith("hold")]) == 1
    _assert_released(senv)


def test_wall_too_short_for_hold_and_restore_holds_nothing(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    proc = _sweep(tmp_path, senv, "--wall-sec", "900")
    assert proc.returncode == 1, proc.stderr
    assert "deadline-before-load" in _result(tmp_path)
    assert _calls(senv) == [] and not _pids(senv, "flent")


def test_context_gaps_keep_the_measurement(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_PROM_MODE": "noctx"})
    assert proc.returncode == 0, proc.stderr
    for r in _rows(tmp_path):
        assert r["status"] == "complete" and r["dl_mbit"] == "763.2" and r["household_dl_mbit"]
        assert r["reason"].startswith("measured;context-missing:pre_dl+rtt_avg")
        assert all(r[c] == "" for c in CONTEXT[1:])


@pytest.mark.parametrize(
    ("extra", "knobs"),
    [
        ((), {"RRUL_SLOT_SHAPER_SSH": ""}),
        ((), {"RRUL_SLOT_SWEEP_CAPS": "620 400"}),
        ((), {"RRUL_SLOT_SWEEP_CAPS": "620 620"}),
        ((), {"RRUL_SLOT_SWEEP_CAPS": "780"}),
        ((), {"RRUL_SLOT_SWEEP_CAPS": ""}),
        ((), {"RRUL_SLOT_SWEEP_CAPS": "500 550 600 650"}),
        ((), {"RRUL_SLOT_SWEEP_CONTROL": "950"}),
        ((), {"RRUL_SLOT_SWEEP_CAP_CMD": "wanctl-sweep-cap; reboot"}),
        ((), {"RRUL_SLOT_SWEEP_SLOTS": "7:35"}),
        ((), {"RRUL_SLOT_DEAD_MAN_SEC": "900"}),
        (("--wall-sec", "2000"), {}),
    ],
)
def test_invalid_sweep_inputs_hold_nothing(
    tmp_path: Path, senv: dict[str, str], extra: tuple[str, ...], knobs: dict[str, str]
) -> None:
    proc = _sweep(tmp_path, {**senv, **knobs}, *extra)
    assert proc.returncode == 2, proc.stderr
    assert _calls(senv) == [] and not (tmp_path / "data").exists()


def _central_hhmm(offset_min: int = 0) -> str:
    out = subprocess.run(
        ["date", "-d", f"{offset_min} minutes", "+%H:%M"],
        env={"TZ": "America/Chicago", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    return out.stdout.strip()


@pytest.mark.parametrize(
    ("slots", "mode"),
    [
        (lambda: _central_hhmm(-1), "sweep"),
        (lambda: _central_hhmm(-20), "single"),
        (lambda: "", "single"),
    ],
    ids=["in-slot", "after-slot", "no-slots"],
)
def test_auto_mode_sweeps_only_in_a_sweep_slot(
    tmp_path: Path, senv: dict[str, str], slots, mode: str
) -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--data-dir", str(tmp_path / "data"), "eve"],
        env={**senv, "RRUL_SLOT_SWEEP_SLOTS": slots()},
        capture_output=True,
        text=True,
        timeout=28,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rows = _rows(tmp_path)
    assert {r["mode"] for r in rows} == {mode}
    assert len(rows) == (3 if mode == "sweep" else 1)
    if mode == "single":
        assert not [c for c in _calls(senv) if c != "status"]
    _assert_released(senv)


# --- held-state failure paths ----------------------------------------------------------------------------------------
# Each of these fails while a cap is already held, and must end with exactly one restore attempt, no owned process left,
# a truthful restore outcome and no measurement kept for the failing row.


def _shorten_shaper_limits(environ: dict[str, str]) -> None:
    """Put a timeout(1) wrapper first in PATH that turns the script's 120 s hold and 450 s restore limits into 2 s.

    Every other limit (flent, Prometheus, status, the ssh read) passes through unchanged, and the production constants
    in the script are not touched.
    """
    fake_bin = Path(environ["PATH"].split(":")[0])
    real = Path(environ["PATH"].split(":")[1]) / "timeout"
    _install(
        fake_bin,
        "timeout",
        "#!/usr/bin/env bash\n"
        "args=()\n"
        'for a in "$@"; do case $a in 120|450) a=2 ;; esac; args+=("$a"); done\n'
        f'exec {real} "${{args[@]}}"\n',
    )


def _assert_held_failure_cleaned_up(
    tmp_path: Path, environ: dict[str, str]
) -> list[dict[str, str]]:
    _assert_released(environ)
    _no_owned_left(environ)
    rows = _rows(tmp_path)
    assert rows and all(
        r["status"] != "complete" or r["reason"].startswith("measured") for r in rows
    )
    for r in rows:
        if r["status"] != "complete":
            assert all(r[c] == "" for c in MEASURED), r
    return rows


def test_hold_timeout_after_the_cap_was_acquired_restores(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    _shorten_shaper_limits(senv)
    proc = _sweep(tmp_path, {**senv, "FAKE_HOLD_HANG_AFTER": "any"})
    assert proc.returncode == 1, proc.stderr
    result = _result(tmp_path)
    assert "status=invalid" in result and ":rc=124" in result and "hold-failed:" in result
    assert "restore=ok" in result
    # the hold had taken effect on the shaper before the timeout; the restore cleared it
    assert _state(senv) == ["no", "700", "none", "no"]
    rows = _assert_held_failure_cleaned_up(tmp_path, senv)
    assert [r["status"] for r in rows] == ["invalid", "skipped", "skipped"]
    assert len([c for c in _calls(senv) if c.startswith("hold")]) == 1


def test_unparsable_status_after_the_hold_restores(tmp_path: Path, senv: dict[str, str]) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_STATUS_MODE": "garbage-held"})
    assert proc.returncode == 1, proc.stderr
    assert "hold-unverified:" in _result(tmp_path) and "status-unreadable" in _result(tmp_path)
    assert "restore=ok" in _result(tmp_path)
    rows = _assert_held_failure_cleaned_up(tmp_path, senv)
    assert rows[0]["status"] == "invalid" and rows[0]["restore"] == "ok"


def test_unparsable_status_after_restore_is_unverified(
    tmp_path: Path, senv: dict[str, str]
) -> None:
    proc = _sweep(tmp_path, {**senv, "FAKE_STATUS_MODE": "garbage-restored"})
    assert proc.returncode == 6, proc.stderr
    result = _result(tmp_path)
    assert "status=restore-failed" in result and "restore=unverified:status-unreadable" in result
    assert "recovery is NOT assured" in proc.stderr and "restore ok:" not in proc.stderr
    assert all(r["restore"] == "unverified:status-unreadable" for r in _rows(tmp_path))
    _assert_held_failure_cleaned_up(tmp_path, senv)


def test_restore_command_timeout_is_a_failed_restore(tmp_path: Path, senv: dict[str, str]) -> None:
    _shorten_shaper_limits(senv)
    proc = _sweep(tmp_path, {**senv, "FAKE_RESTORE_SEC": "30"})
    assert proc.returncode == 6, proc.stderr
    assert "restore=failed:rc=124" in _result(tmp_path)
    assert "recovery is NOT assured" in proc.stderr and "restore ok:" not in proc.stderr
    # truthful: the fake restore never completed, so the shaper is still held
    assert _state(senv)[0] == "yes"
    assert all(r["restore"] == "failed:rc=124" for r in _rows(tmp_path))
    _assert_held_failure_cleaned_up(tmp_path, senv)


@pytest.mark.parametrize(
    ("mode", "data", "reason"),
    [
        ("nofile", None, "flent-data-files-0"),
        ("empty", None, "flent-parse:no-result"),
        ("ok", flent_data(name="rrul_be"), "flent-parse:"),
        ("ok", flent_data(lost=frozenset(range(20, 330))), "flent-parse:"),
    ],
    ids=["no-data-file", "empty-data-file", "wrong-test", "no-replies-in-load"],
)
def test_missing_or_malformed_flent_data_while_held_restores(
    tmp_path: Path, senv: dict[str, str], mode: str, data: dict | None, reason: str
) -> None:
    if data is not None:
        _set_flent_data(Path(senv["FAKE_DIR"]), data)
    proc = _sweep(tmp_path, {**senv, "FAKE_FLENT_MODE": mode})
    assert proc.returncode == 1, proc.stderr
    assert reason in _result(tmp_path) and "restore=ok" in _result(tmp_path)
    rows = _assert_held_failure_cleaned_up(tmp_path, senv)
    assert rows[0]["status"] == "invalid" and reason in rows[0]["reason"]
    assert len([c for c in _calls(senv) if c.startswith("hold")]) == 1


@pytest.mark.parametrize(
    ("sig", "rc"), [(signal.SIGINT, 130), (signal.SIGHUP, 129)], ids=["INT", "HUP"]
)
def test_int_or_hup_during_held_load_restores(
    tmp_path: Path, senv: dict[str, str], sig: signal.Signals, rc: int
) -> None:
    run = _start(tmp_path, {**senv, "FAKE_FLENT_MODE": "hang"})
    _wait_for(lambda: bool(_pids(senv, "flent")))
    owned = _pids(senv, "flent") + _pids(senv, "fping")
    run.send_signal(sig)
    assert run.wait(timeout=15) == rc, run.stderr.read()
    result = _result(tmp_path)
    assert (
        "status=aborted" in result and f"signal-{sig.name[3:]}" in result and "restore=ok" in result
    )
    assert not any(_alive(p) for p in owned)
    _assert_held_failure_cleaned_up(tmp_path, senv)
    assert _state(senv)[0] == "no"


@pytest.mark.parametrize(
    ("sig", "rc"), [(signal.SIGINT, 130), (signal.SIGHUP, 129)], ids=["INT", "HUP"]
)
def test_signal_in_the_gap_between_held_runs_restores(
    tmp_path: Path, senv: dict[str, str], sig: signal.Signals, rc: int
) -> None:
    run = _start(tmp_path, {**senv, "RRUL_SLOT_SWEEP_GAP_SEC": "8"})

    def logged_statuses() -> int:
        logs = list((tmp_path / "data" / "runs").glob("*/rrul.log"))
        return logs[0].read_text().count("shaper status:") if logs else 0

    # clean-shaper status, status after the hold, status after the load, all logged: the first run is done and the
    # script is in the gap before the second cap (nothing else is logged until the gap ends)
    _wait_for(lambda: logged_statuses() >= 3, limit=20)
    run.send_signal(sig)
    assert run.wait(timeout=15) == rc, run.stderr.read()
    result = _result(tmp_path)
    assert "status=aborted" in result and "restore=ok" in result
    rows = _assert_held_failure_cleaned_up(tmp_path, senv)
    name = sig.name[3:]
    # the first run was measured but its telemetry is not read after a signal; the second was about to start
    assert [(r["status"], r["reason"]) for r in rows] == [
        ("aborted", f"signal-{name}:telemetry-not-read"),
        ("aborted", f"signal-{name}"),
        ("aborted", f"sweep-stopped:signal-{name}"),
    ]
    assert len([c for c in _calls(senv) if c.startswith("hold")]) == 1


def _watchdogs(script_pid: int) -> list[int]:
    """Live deadline watchdogs started by the script with this pid."""
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if (
            b"rrul-slot-deadline" in argv
            and str(script_pid).encode() in argv
            and _alive(int(proc.name))
        ):
            found.append(int(proc.name))
    return found


@pytest.mark.parametrize(
    ("sig", "rc"), [(signal.SIGINT, 130), (signal.SIGHUP, 129), (signal.SIGTERM, 143)]
)
def test_signal_reaches_the_script_and_its_watchdog_is_stopped(
    tmp_path: Path, senv: dict[str, str], sig: signal.Signals, rc: int
) -> None:
    """The signalled pid is the script itself (no timeout(1) in between), and its deadline watchdog goes with it."""
    run = _start(tmp_path, {**senv, "FAKE_FLENT_MODE": "hang"})
    _wait_for(lambda: bool(_pids(senv, "flent")) and bool(_watchdogs(run.pid)))
    assert Path(f"/proc/{run.pid}/comm").read_text().strip() == "bash"
    run.send_signal(sig)
    assert run.wait(timeout=15) == rc, run.stderr.read()
    assert (
        f"signal {sig.name[3:]} received"
        in (next((tmp_path / "data" / "runs").iterdir()) / "rrul.log").read_text()
    )
    _wait_for(lambda: not _watchdogs(run.pid), limit=5)
    _assert_released(senv)

"""Synthetic tests for scripts/capacity-sweep.sh.

The script runs against fake iperf3, fping, prom-ro and ssh executables, so no network traffic is generated. PATH holds
only the fakes and links to the real local tools in HOST_TOOLS, resolved from the runner's own PATH: the tests do not
depend on where a runner keeps jq or awk, and a real network tool can never be reached. Timing knobs are shortened
through the CAPACITY_SWEEP_*_SEC environment variables.

The tests in this module must not run concurrently with each other: the script's competing-load check sees the
fake iperf3 clients of other tests. The project's pytest config (--dist=loadfile) keeps a module on one worker.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts/capacity-sweep.sh"

ADVISOR_HEADER = (
    "label,start_utc,local_time,dow,target_mbit,achieved_mbit,retrans,rtt_median_ms,rtt_p95_ms,rtt_p99_ms,"
    "loss_pct,shaped_dl_min,shaped_dl_max,cake_dl_peak_delay_ms,max_dl_config_kbps"
)

FAKE_IPERF3 = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/iperf3.pids"
t=0; o=0
while [ $# -gt 0 ]; do
  case $1 in -t) t=$2; shift ;; -O) o=$2; shift ;; esac
  shift
done
case ${FAKE_IPERF_MODE:-ok} in
  hang) while :; do sleep 1; done ;;
  fail) echo '{"error": "unable to connect to server"}'; exit 1 ;;
  badjson) sleep "$((t + o))"; echo 'not json'; exit 0 ;;
esac
sleep "$((t + o))"
echo '{"end": {"sum_received": {"bits_per_second": 600000000.0, "bytes": 1500000000}, "sum_sent": {"retransmits": 12}}}'
"""

FAKE_FPING = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/fping.pids"
host=${@: -1}
i=0
while :; do
  ts=$(date +%s.%N)
  case ${FAKE_FPING_MODE:-ok} in
    loss) echo "[${ts:0:16}] $host : [$i], timed out (NaN avg, 100% loss)" ;;
    slow) echo "[${ts:0:16}] $host : [$i], 64 bytes, 200.0 ms (200.0 avg, 0% loss)" ;;
    garbage) echo "fping: something unexpected" ;;
    *) echo "[${ts:0:16}] $host : [$i], 64 bytes, 21.$((i % 10)) ms (21.0 avg, 0% loss)" ;;
  esac
  i=$((i + 1))
  # stall: healthy for 1 s, then alive but silent
  if [ "${FAKE_FPING_MODE:-ok}" = stall ] && [ "$i" -ge 10 ]; then while :; do sleep 1; done; fi
  sleep 0.1
done
"""

FAKE_PROM_RO = r"""#!/usr/bin/env bash
# Answers like the Prometheus API's .data.result: range queries return one point per step over [start, end].
echo "$*" >> "$FAKE_DIR/prom.calls"
mode=${FAKE_PROM_MODE:-ok}
[ "$mode" = error ] && { echo "prom-ro: curl failed" >&2; exit 22; }
now=$(date +%s)
series() { # low high: grid points from $3 to $4 every $5 s, first point low, the rest high
  local s=$3 e=$4 st=$5 t out="" v=$1
  [ "$mode" = sparse ] && e=$((s + st))
  [ "$mode" = stale-window ] && e=$((e - 60))
  for ((t = s; t <= e; t += st)); do
    out="$out${out:+, }[$t, \"$v\"]"
    [ "$mode" = dupe ] && [ "$t" = "$s" ] && out="$out, [$t, \"$v\"]"
    v=$2
  done
  [ "$mode" = nan ] && out="$out${out:+, }[$e, \"NaN\"]"
  echo "[{\"metric\": {}, \"values\": [$out]}]"
}
scalar() { echo "[{\"metric\": {}, \"value\": [$now, \"$1\"]}]"; }
case $1:$2 in
  range:*cake_tin_sent_bytes_total*)
    [ "$mode" = missing ] && { echo '[]'; exit 0; }
    [ "$mode" = busy ] && { series 0.4 55.0 "$3" "$4" "$5"; exit 0; }
    series 0.2 0.9 "$3" "$4" "$5" ;;
  range:*cake_shaped_rate_bps*)
    [ "$mode" = noshaped ] && { echo '[]'; exit 0; }
    [ "$mode" = floor ] && { series 90 450 "$3" "$4" "$5"; exit 0; }
    series 450 780 "$3" "$4" "$5" ;;
  range:*peak_delay*) series 2.5 3.1 "$3" "$4" "$5" ;;
  q:*timestamp*) [ "$mode" = stale-exporter ] && scalar 120 || scalar 3 ;;
  q:*spectrum*) scalar "${FAKE_SPEC_BYTES:-1800000000}" ;;
  q:*att*) scalar "${FAKE_ATT_BYTES:-1000}" ;;
  *) echo "unexpected prom-ro call: $*" >&2; exit 2 ;;
esac
"""

FAKE_SSH = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/ssh.pids"
case ${FAKE_SSH_MODE:-ok} in
  hang) while :; do sleep 1; done ;;
esac
echo 780000
"""


# Every external command the script and the fakes run. iperf3, fping, prom-ro and ssh are deliberately absent.
HOST_TOOLS = (
    "awk",
    "bash",
    "cat",
    "chmod",
    "date",
    "dirname",
    "flock",
    "grep",
    "head",
    "id",
    "jq",
    "mkdir",
    "mktemp",
    "mv",
    "pgrep",
    "rm",
    "sed",
    "setsid",
    "sleep",
    "stat",
    "tail",
    "tee",
    "timeout",
    "tr",
)


@pytest.fixture(scope="module")
def host_tools(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tools = tmp_path_factory.mktemp("host-tools")
    missing = []
    for name in HOST_TOOLS:
        real = shutil.which(name)
        if real is None:
            missing.append(name)
        else:
            (tools / name).symlink_to(real)
    if missing:
        pytest.fail(f"capacity-sweep tests need these tools on PATH: {' '.join(missing)}")
    # fping_stats and breach_check use asort, a GNU awk extension
    probe = subprocess.run(
        [str(tools / "awk"), 'BEGIN { split("2 1", a); asort(a); print a[1] }'],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if probe.stdout.strip() != "1":
        pytest.fail(
            f"capacity-sweep needs GNU awk; {shutil.which('awk')} failed: {probe.stderr.strip()}"
        )
    return tools


@pytest.fixture
def env(tmp_path: Path, host_tools: Path) -> dict[str, str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, body in (
        ("iperf3", FAKE_IPERF3),
        ("fping", FAKE_FPING),
        ("prom-ro", FAKE_PROM_RO),
        ("ssh", FAKE_SSH),
    ):
        path = fake_bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    fake_dir = tmp_path / "fake"
    fake_dir.mkdir()
    return {
        "PATH": f"{fake_bin}:{host_tools}",
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path),
        "LANG": "C",
        "FAKE_DIR": str(fake_dir),
        "CAPACITY_SWEEP_CONFIG": str(tmp_path / "no-config"),
        "CAPACITY_SWEEP_HOST": "192.0.2.10",
        "CAPACITY_SWEEP_LEAD_SEC": "0",
        "CAPACITY_SWEEP_OMIT_SEC": "0",
        "CAPACITY_SWEEP_POLL_SEC": "1",
        "CAPACITY_SWEEP_PROM_LAG_SEC": "0",
    }


def _args(tmp_path: Path, *extra: str, rates: str = "400 500", step: str = "2") -> list[str]:
    return [
        "bash",
        str(SCRIPT),
        "--data-dir",
        str(tmp_path / "data"),
        "--step-sec",
        step,
        *extra,
        "T1",
        rates,
    ]


def _run(
    tmp_path: Path, env: dict[str, str], *extra: str, timeout: int = 25, **kw: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        _args(tmp_path, *extra, **kw),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _pids(env: dict[str, str], name: str) -> list[int]:
    path = Path(env["FAKE_DIR"]) / f"{name}.pids"
    return [int(p) for p in path.read_text().split()] if path.exists() else []


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    return stat.exists() and stat.read_text().split()[2] != "Z"


def _result(tmp_path: Path) -> str:
    (run,) = (tmp_path / "data" / "runs").iterdir()
    return (run / "result").read_text()


def _diag(tmp_path: Path, proc: subprocess.CompletedProcess) -> str:
    """stderr plus the run's tool error files (prom.err, *.iperf.err), so a failure names the command that failed"""
    parts = [proc.stderr]
    for err in sorted(tmp_path.rglob("*.err")):
        text = err.read_text(errors="replace").strip()
        if text:
            parts.append(f"--- {err.relative_to(tmp_path)}\n{text[-2000:]}")
    return "\n".join(parts)


def _csv_rows(tmp_path: Path) -> list[str]:
    path = tmp_path / "data" / "sweeps.csv"
    return path.read_text().splitlines() if path.exists() else []


def test_path_reaches_only_the_fakes_and_listed_tools(env: dict[str, str]) -> None:
    fake_bin, tools = env["PATH"].split(":")
    for name in ("iperf3", "fping", "prom-ro", "ssh"):
        assert shutil.which(name, path=env["PATH"]) == str(Path(fake_bin) / name)
    for name in ("curl", "wget", "nc", "irtt", "flent", "netperf"):
        assert shutil.which(name, path=env["PATH"]) is None
    assert sorted(p.name for p in Path(tools).iterdir()) == sorted(HOST_TOOLS)


PROM_LINE = re.compile(
    r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[a-zA-Z_]\w*="[^"]*"(,[a-zA-Z_]\w*="[^"]*")*\})? -?[0-9.e+]+$'
)


def test_complete_sweep_appends_rows_and_textfile(tmp_path: Path, env: dict[str, str]) -> None:
    prom = tmp_path / "textfile" / "wanctl_capacity_sweep.prom"
    prom.parent.mkdir()
    # 6 s steps: the 5 s Prometheus grid then has two points per step, so min and max differ
    proc = _run(tmp_path, env, "--textfile", str(prom), step="6")
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert "status=complete" in _result(tmp_path)

    rows = _csv_rows(tmp_path)
    assert rows[0] == ADVISOR_HEADER
    assert len(rows) == 3
    for row, rate in zip(rows[1:], ("400", "500"), strict=True):
        fields = row.split(",")
        assert len(fields) == 15
        assert fields[0] == "T1" and fields[4] == rate and fields[5] == "600" and fields[6] == "12"
        assert float(fields[7]) >= 21.0 and fields[10] == "0.0"
        assert fields[11:14] == ["450", "780", "3.1"] and fields[14] == ""

    text = prom.read_text()
    for line in text.splitlines():
        assert line.startswith(("# HELP ", "# TYPE ")) or PROM_LINE.match(line), line
    assert 'wanctl_capacity_sweep_run_status{status="complete",pace="fq"} 1' in text
    assert 'wanctl_capacity_sweep_step_achieved_mbps{target_mbit="500"} 600' in text
    assert "wanctl_capacity_sweep_valid_steps 2" in text
    assert not list(prom.parent.glob(".capacity-sweep.*"))

    # a second run appends rows under the same single header
    assert _run(tmp_path, env).returncode == 0
    rows = _csv_rows(tmp_path)
    assert rows.count(ADVISOR_HEADER) == 1 and len(rows) == 5


def test_unwritable_textfile_fails_an_otherwise_good_run(
    tmp_path: Path, env: dict[str, str]
) -> None:
    missing = tmp_path / "no-such-dir" / "wanctl_capacity_sweep.prom"
    proc = _run(tmp_path, env, "--textfile", str(missing), rates="400")
    assert proc.returncode == 1, _diag(tmp_path, proc)
    result = _result(tmp_path)
    assert "status=complete" in result and "textfile-write-failed" in result
    assert len(_csv_rows(tmp_path)) == 2


@pytest.mark.parametrize(
    ("extra", "kw"),
    [
        (("--host", "192.0.2.99"), {}),
        (("--host", ""), {}),
        ((), {"rates": "500 400"}),
        ((), {"rates": "400 abc"}),
        ((), {"rates": " ".join(str(r) for r in range(100, 1400, 100))}),
        ((), {"rates": "100 200 300 400 500 600 700", "step": "60"}),
        (("--pace", "burst"), {}),
        (("--textfile", "relative.prom"), {}),
    ],
)
def test_invalid_inputs_are_rejected_before_any_load(
    tmp_path: Path, env: dict[str, str], extra: tuple[str, ...], kw: dict[str, str]
) -> None:
    proc = _run(
        tmp_path, {**env, "CAPACITY_SWEEP_UNSUITABLE_HOSTS": "192.0.2.98 192.0.2.99"}, *extra, **kw
    )
    assert proc.returncode == 2, _diag(tmp_path, proc)
    assert not _pids(env, "iperf3") and not (Path(env["FAKE_DIR"]) / "prom.calls").exists()


def _write_config(tmp_path: Path, text: str, mode: int) -> dict[str, str]:
    config = tmp_path / "sweep.env"
    config.write_text(text, encoding="utf-8")
    config.chmod(mode)
    return {"CAPACITY_SWEEP_CONFIG": str(config)}


def test_config_file_supplies_endpoint_and_data_dir(tmp_path: Path, env: dict[str, str]) -> None:
    data = tmp_path / "configured-data"
    cfg = _write_config(
        tmp_path,
        f'# site config\nCAPACITY_SWEEP_HOST="192.0.2.20"\nCAPACITY_SWEEP_DATA_DIR={data}\n',
        0o600,
    )
    base = {k: v for k, v in env.items() if k != "CAPACITY_SWEEP_HOST"}
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--step-sec", "2", "T1", "400"],
        env={**base, **cfg},
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert "host=192.0.2.20" in proc.stderr
    assert (data / "sweeps.csv").exists()


@pytest.mark.parametrize(
    ("text", "mode"),
    [
        ("CAPACITY_SWEEP_HOST=192.0.2.20\n", 0o644),
        ("CAPACITY_SWEEP_SURPRISE=1\n", 0o600),
        ("CAPACITY_SWEEP_HOST=$(id)\n", 0o600),
        ("HOST=192.0.2.20\n", 0o600),
    ],
)
def test_bad_config_is_rejected(tmp_path: Path, env: dict[str, str], text: str, mode: int) -> None:
    proc = _run(tmp_path, {**env, **_write_config(tmp_path, text, mode)})
    assert proc.returncode == 2, _diag(tmp_path, proc)
    assert not (Path(env["FAKE_DIR"]) / "prom.calls").exists()


def test_environment_overrides_config(tmp_path: Path, env: dict[str, str]) -> None:
    cfg = _write_config(tmp_path, "CAPACITY_SWEEP_HOST=192.0.2.20\n", 0o600)
    proc = _run(tmp_path, {**env, **cfg}, rates="400")
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert "host=192.0.2.10" in proc.stderr


@pytest.mark.parametrize(
    ("mode", "rc", "status"),
    [
        ("busy", 75, "skipped"),
        ("missing", 1, "invalid"),
        ("error", 1, "invalid"),
        ("sparse", 1, "invalid"),
        ("stale-window", 1, "invalid"),
        ("dupe", 1, "invalid"),
        ("nan", 1, "invalid"),
    ],
)
def test_idle_gate_blocks_load(
    tmp_path: Path, env: dict[str, str], mode: str, rc: int, status: str
) -> None:
    proc = _run(tmp_path, {**env, "FAKE_PROM_MODE": mode})
    assert proc.returncode == rc, _diag(tmp_path, proc)
    assert f"status={status}" in _result(tmp_path)
    assert not _pids(env, "iperf3") and _csv_rows(tmp_path) == []


def test_lock_held_skips(tmp_path: Path, env: dict[str, str]) -> None:
    (tmp_path / "data").mkdir()
    with open(tmp_path / "data" / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = _run(tmp_path, env)
    assert proc.returncode == 75
    assert not _pids(env, "iperf3")


def test_competing_client_load_skips_without_touching_it(
    tmp_path: Path, env: dict[str, str]
) -> None:
    other = subprocess.Popen(
        ["iperf3", "-c", "198.51.100.1", "-t", "60"],
        env={**env, "FAKE_IPERF_MODE": "hang"},
        start_new_session=True,
    )
    try:
        time.sleep(0.3)
        proc = _run(tmp_path, env)
        assert proc.returncode == 75, _diag(tmp_path, proc)
        assert "competing-load" in _result(tmp_path)
        assert other.poll() is None
    finally:
        other.kill()
        other.wait()


@pytest.mark.parametrize(
    ("env_extra", "reason"),
    [
        ({"FAKE_IPERF_MODE": "fail"}, "iperf3-rc-1"),
        ({"FAKE_IPERF_MODE": "badjson"}, "iperf3-json"),
        ({"FAKE_PROM_MODE": "noshaped"}, "telemetry-missing:shaped-rate"),
        ({"FAKE_PROM_MODE": "stale-exporter"}, "telemetry-stale:shaper-exporter"),
        ({"FAKE_SPEC_BYTES": "1000"}, "path-check:spectrum"),
        ({"FAKE_ATT_BYTES": "900000000"}, "path-check:att"),
    ],
)
def test_step_failures_are_invalid_without_rows(
    tmp_path: Path, env: dict[str, str], env_extra: dict[str, str], reason: str
) -> None:
    proc = _run(tmp_path, {**env, **env_extra})
    assert proc.returncode == 1, _diag(tmp_path, proc)
    result = _result(tmp_path)
    assert "status=invalid" in result and reason in result
    assert _csv_rows(tmp_path) == []
    assert not any(_alive(p) for p in _pids(env, "iperf3") + _pids(env, "fping"))


def test_knee_stops_after_valid_step(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_FPING_MODE": "slow"})
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert "status=knee" in _result(tmp_path)
    assert len(_csv_rows(tmp_path)) == 2
    assert len(_pids(env, "iperf3")) == 1


def test_floor_is_a_safety_stop(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_PROM_MODE": "floor"})
    assert proc.returncode == 3, _diag(tmp_path, proc)
    assert "status=floor-stop" in _result(tmp_path)


def test_sustained_breach_kills_owned_load(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_FPING_MODE": "loss", "FAKE_IPERF_MODE": "hang"}, step="8")
    assert proc.returncode == 3, _diag(tmp_path, proc)
    assert "status=breach-stop" in _result(tmp_path)
    assert _csv_rows(tmp_path) == []
    assert not any(_alive(p) for p in _pids(env, "iperf3") + _pids(env, "fping"))


@pytest.mark.parametrize("mode", ["stall", "garbage"])
def test_stalled_or_unparsable_fping_stops_owned_load(
    tmp_path: Path, env: dict[str, str], mode: str
) -> None:
    proc = _run(tmp_path, {**env, "FAKE_FPING_MODE": mode, "FAKE_IPERF_MODE": "hang"}, step="20")
    assert proc.returncode == 1, _diag(tmp_path, proc)
    assert "telemetry-stale:fping-400" in _result(tmp_path)
    assert _csv_rows(tmp_path) == []
    assert not any(_alive(p) for p in _pids(env, "iperf3") + _pids(env, "fping"))


@pytest.mark.parametrize(
    "option",
    [
        "--host",
        "--pace",
        "--step-sec",
        "--idle-ms",
        "--wall-sec",
        "--data-dir",
        "--textfile",
        "--shaper-ssh",
    ],
)
def test_option_without_value_is_a_usage_error(env: dict[str, str], option: str) -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--step-sec", "2", option],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 2, proc.stderr
    assert f"{option} needs a value" in proc.stderr


def test_configured_prometheus_command_is_used(tmp_path: Path, env: dict[str, str]) -> None:
    fake_bin = Path(env["PATH"].split(":")[0])
    (fake_bin / "prom-ro").rename(fake_bin / "site-prom")
    proc = _run(tmp_path, {**env, "CAPACITY_SWEEP_PROM_CMD": "site-prom"}, rates="400")
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert (Path(env["FAKE_DIR"]) / "prom.calls").read_text().count("\n") >= 6


def test_shaper_max_is_read_into_the_csv(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, env, "--shaper-ssh", "shaper-alias", rates="400")
    assert proc.returncode == 0, _diag(tmp_path, proc)
    assert _csv_rows(tmp_path)[1].split(",")[14] == "780000"


def test_deadline_during_run_tears_down_owned_children(tmp_path: Path, env: dict[str, str]) -> None:
    started = time.monotonic()
    proc = _run(
        tmp_path,
        {**env, "FAKE_SSH_MODE": "hang"},
        "--shaper-ssh",
        "shaper-alias",
        "--wall-sec",
        "10",
    )
    assert proc.returncode == 124, _diag(tmp_path, proc)
    assert time.monotonic() - started < 20
    assert "status=deadline" in _result(tmp_path)
    assert _pids(env, "ssh") and not any(_alive(p) for p in _pids(env, "ssh"))
    assert not _pids(env, "iperf3")


def test_deadline_refuses_a_step_that_cannot_finish(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, env, "--wall-sec", "60")
    assert proc.returncode == 1, _diag(tmp_path, proc)
    assert "deadline-before-step:400" in _result(tmp_path)
    assert not _pids(env, "iperf3")


def test_sigterm_tears_down_only_owned_processes(tmp_path: Path, env: dict[str, str]) -> None:
    decoy = subprocess.Popen(
        ["iperf3", "-s"], env={**env, "FAKE_IPERF_MODE": "hang"}, start_new_session=True
    )
    try:
        time.sleep(0.3)
        sweep = subprocess.Popen(
            _args(tmp_path, step="20"),
            env={**env, "FAKE_IPERF_MODE": "hang"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while len(_pids(env, "iperf3")) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
        owned = [p for p in _pids(env, "iperf3") if p != decoy.pid] + _pids(env, "fping")
        assert owned and all(_alive(p) for p in owned)
        sweep.send_signal(signal.SIGTERM)
        assert sweep.wait(timeout=10) == 143
        assert "status=aborted" in _result(tmp_path)
        assert not any(_alive(p) for p in owned)
        assert decoy.poll() is None
    finally:
        decoy.kill()
        decoy.wait()

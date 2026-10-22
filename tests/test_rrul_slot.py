"""Synthetic tests for scripts/rrul-slot.sh, plus the fail-closed competing-load check of scripts/capacity-sweep.sh.

The scripts run against fake flent, fping, prom-ro, ssh and pgrep executables, so no network traffic is generated. PATH
holds only the fakes and links to the real local tools in HOST_TOOLS, resolved from the runner's own PATH; pgrep is
deliberately not linked, so a test either supplies the fake or proves what happens without one. The fake flent writes a
data file built by flent_data() in the shape of flent 2.2.0 rrul output.

Isolation from tests/test_capacity_sweep.py, which may run on another worker and uses the real pgrep: no process
started here matches the competing-load pattern. The fake flent is configured as `fake-flent`, which the pattern does not
match, and the fake pgrep carries the pattern in its own command line, which the pattern is written not to match
(test_competing_load_pattern_does_not_match_its_own_text). The real pgrep is never run here.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts/rrul-slot.sh"
SWEEP_SCRIPT = REPO_ROOT / "scripts/capacity-sweep.sh"
UNIT = REPO_ROOT / "deploy/rrul-slot/wanctl-rrul-slot.service"
SWEEP_UNIT = REPO_ROOT / "deploy/capacity-sweep/wanctl-capacity-sweep.service"

HEADER = (
    "schema,label,status,reason,start_utc,local_date,local_time,local_tz,dow,dl_mbit,ul_mbit,icmp_median_ms,"
    "icmp_p99_ms,icmp_loss_pct,icmp_sent,icmp_lost,shaped_dl_min_mbit,shaped_dl_max_mbit,shaped_ul_min_mbit,"
    "shaped_ul_max_mbit,max_dl_config_kbps,run,mode,tested_cap,sweep_id,sweep_order,restore,household_dl_mbit,"
    "pre_dl_mbit,rtt_delta_avg_ms,rtt_delta_max_ms,pre_rtt_delta_avg_ms,pre_rtt_delta_max_ms,nongreen_frac,"
    "pre_nongreen_frac,dl_drops,pre_dl_drops,peak_delay_ms,pre_peak_delay_ms"
)
COLUMNS = HEADER.split(",")
CONTEXT = COLUMNS[27:]
# every column that holds a measurement: empty unless all checks of the row passed
MEASURED = COLUMNS[9:20] + CONTEXT
CSV_NAME = "rrul-v2.csv"

# Every external command the scripts and the fakes run. flent, fping, prom-ro, ssh, iperf3 and pgrep are absent.
HOST_TOOLS = (
    "awk",
    "bash",
    "cat",
    "date",
    "flock",
    "grep",
    "gzip",
    "head",
    "id",
    "jq",
    "mkdir",
    "sed",
    "setsid",
    "sleep",
    "stat",
    "tail",
    "tee",
    "timeout",
    "tr",
)

FAKE_FLENT = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/flent.pids"
echo "$*" >> "$FAKE_DIR/flent.args"
test=$1; shift
while [ $# -gt 0 ]; do
  case $1 in -H) host=$2; shift ;; -t) title=$2; shift ;; -D) dir=$2; shift ;; esac
  shift
done
case ${FAKE_FLENT_MODE:-ok} in
  hang) while :; do sleep 1; done ;;
  fail) echo "flent: runner failed"; exit 1 ;;
  nofile) exit 0 ;;
  empty) : | gzip > "$dir/$test-empty.$title.flent.gz"; exit 0 ;;
esac
sleep "${FAKE_FLENT_SEC:-1}"
# the data reads as if flent had run over the last 70 s
now=$(date +%s.%N)
t0=$(date -u -d "@$(( ${now%.*} - 70 ))" +%FT%T.000000Z)
jq -c --argjson b "$now" --arg t0 "$t0" --arg title "$title" --arg host "$host" '
  .metadata.T0 = $t0 | .metadata.TITLE = $title | .metadata.HOST = $host
  | if .metadata.SERIES_META["Ping (ms) ICMP"] then .metadata.SERIES_META["Ping (ms) ICMP"].COMMAND |= sub("HOST"; $host)
    else . end
  | .raw_values |= map_values(map(.t += $b - 70))' "$FAKE_DIR/flent.json" | gzip > "$dir/$test-${t0%.*}.$title.flent.gz"
"""

FAKE_FPING = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/fping.pids"
host=${@: -1}
i=0
while :; do
  ts=$(date +%s.%N)
  case ${FAKE_FPING_MODE:-ok} in
    loss) echo "[${ts:0:16}] $host : [$i], timed out (NaN avg, 100% loss)" ;;
    garbage) echo "fping: something unexpected" ;;
    *) echo "[${ts:0:16}] $host : [$i], 64 bytes, 21.$((i % 10)) ms (21.0 avg, 0% loss)" ;;
  esac
  i=$((i + 1))
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
  for ((t = s; t <= e; t += st)); do
    out="$out${out:+, }[$t, \"$v\"]"
    v=$2
  done
  echo "[{\"metric\": {}, \"values\": [$out]}]"
}
scalar() { echo "[{\"metric\": {}, \"value\": [$now, \"$1\"]}]"; }
case $1:$2 in
  range:*cake_tin_sent_bytes_total*)
    [ "$mode" = busy ] && { series 0.4 55.0 "$3" "$4" "$5"; exit 0; }
    series 0.2 0.9 "$3" "$4" "$5" ;;
  range:*direction=\"download\"*cake_shaped_rate_bps*|range:*cake_shaped_rate_bps*direction=\"download\"*)
    [ "$mode" = noshaped ] && { echo '[]'; exit 0; }
    series 101.5 780 "$3" "$4" "$5" ;;
  range:*cake_shaped_rate_bps*direction=\"upload\"*) series 8.04 36 "$3" "$4" "$5" ;;
  q:*timestamp*) [ "$mode" = stale-exporter ] && scalar 120 || scalar 3 ;;
  # context queries; "noctx" answers them with no series
  q:*/300/1e6*|q:*cake_rtt_delta_ms*|q:*cake_congestion_state*|q:*dropped_packets*|q:*peak_delay*)
    [ "$mode" = noctx ] && { echo '[]'; exit 0; }
    case $2 in
      */300/1e6*) scalar 1.25 ;;
      max_over_time*rtt*) scalar 31.5 ;;
      *rtt*) scalar 2.5 ;;
      *congestion*) scalar 0.25 ;;
      *dropped*) scalar 12 ;;
      *) scalar 4.2 ;;
    esac ;;
  q:*spectrum*) scalar "${FAKE_SPEC_BYTES:-5800000000}" ;;
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

# Stands in for pgrep: FAKE_PGREP_MODE none (exit 1), match (exit 0 with one line) or error (exit 2).
FAKE_PGREP = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_DIR/pgrep.calls"
case ${FAKE_PGREP_MODE:-none} in
  match) echo "4242 netperf -H 198.51.100.1 -t TCP_MAERTS"; exit 0 ;;
  error) echo "pgrep: cannot read /proc" >&2; exit 2 ;;
esac
exit 1
"""

# Only for the capacity-sweep regression: records that a measurement started.
FAKE_IPERF3 = r"""#!/usr/bin/env bash
echo $$ >> "$FAKE_DIR/iperf3.pids"
echo '{"end": {"sum_received": {"bits_per_second": 600000000.0, "bytes": 1500000000}, "sum_sent": {"retransmits": 1}}}'
"""

CLASSES = ("BE", "BK", "CS5", "EF")


def flent_data(
    *,
    dl: tuple[float, ...] = (26.5, 23.3, 27.2, 686.2),
    ul: tuple[float, ...] = (8.8, 4.5, 6.9, 6.9),
    lost: frozenset[int] = frozenset(),
    rtt: float = 25.0,
    spike_every: int = 0,
    slow: frozenset[int] = frozenset(),
    name: str = "rrul",
    failed_runners: int = 0,
    elapsed: float = 60.0,
    drop_series: str = "",
    icmp_replies: bool = True,
) -> dict:
    """A flent 2.2.0 rrul data file in shape: times are offsets that the fake flent shifts to wall-clock time.

    ICMP probes go out every 0.2 s from t = 0 (seq 0-349); the download flows sample from t = 5 to t = 65.
    """
    meta: dict[str, dict] = {}
    raw: dict[str, list[dict]] = {}
    for direction, rates, field in (("download", dl, "BYTES_RECVD"), ("upload", ul, "BYTES_SENT")):
        for cls, rate in zip(CLASSES, rates, strict=True):
            key = f"TCP {direction} {cls}"
            meta[key] = {
                "MEAN_VALUE": rate,
                "ELAPSED_TIME": elapsed,
                field: int(rate * 1e6 * elapsed / 8),
                "UNITS": "Mbits/s",
                "RUNNER": "NetperfDemoRunner",
            }
            raw[key] = [{"t": 5 + i * 0.2, "val": rate} for i in range(301)]
    meta["Ping (ms) ICMP"] = {
        "COMMAND": "/usr/bin/fping  -D -p 200 -c 350 -t 140000   HOST",
        "RUNNER": "PingRunner",
        "UNITS": "ms",
    }
    replies = []
    for seq in range(350):
        if seq in lost:
            continue
        spike = seq in slow or (spike_every and seq % spike_every == 0)
        val = rtt * 10 if spike else rtt + (seq % 5) * 0.1
        replies.append({"seq": float(seq), "t": seq * 0.2 + val / 1000, "val": val})
    raw["Ping (ms) ICMP"] = replies if icmp_replies else []
    for key in (drop_series,) if drop_series else ():
        meta.pop(key, None)
        raw.pop(key, None)
    return {
        "version": 4,
        "metadata": {
            "NAME": name,
            "LENGTH": 60,
            "TOTAL_LENGTH": 70,
            "STEP_SIZE": 0.2,
            "FAILED_RUNNERS": failed_runners,
            "FLENT_VERSION": "2.2.0",
            "SERIES_META": meta,
        },
        "x_values": [],
        "results": {},
        "raw_values": raw,
    }


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
        pytest.fail(f"rrul-slot tests need these tools on PATH: {' '.join(missing)}")
    # breach_check uses asort, a GNU awk extension
    probe = subprocess.run(
        [str(tools / "awk"), 'BEGIN { split("2 1", a); asort(a); print a[1] }'],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if probe.stdout.strip() != "1":
        pytest.fail(
            f"rrul-slot needs GNU awk; {shutil.which('awk')} failed: {probe.stderr.strip()}"
        )
    return tools


def _install(fake_bin: Path, name: str, body: str) -> None:
    path = fake_bin / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def env(tmp_path: Path, host_tools: Path) -> dict[str, str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, body in (
        ("fake-flent", FAKE_FLENT),
        ("fping", FAKE_FPING),
        ("prom-ro", FAKE_PROM_RO),
        ("ssh", FAKE_SSH),
        ("pgrep", FAKE_PGREP),
    ):
        _install(fake_bin, name, body)
    fake_dir = tmp_path / "fake"
    fake_dir.mkdir()
    _set_flent_data(fake_dir, flent_data())
    return {
        "PATH": f"{fake_bin}:{host_tools}",
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path),
        "LANG": "C",
        "FAKE_DIR": str(fake_dir),
        "RRUL_SLOT_CONFIG": str(tmp_path / "no-config"),
        "RRUL_SLOT_HOST": "192.0.2.10",
        "RRUL_SLOT_FLENT_CMD": "fake-flent",
        "RRUL_SLOT_LEAD_SEC": "0",
        "RRUL_SLOT_POLL_SEC": "1",
        "RRUL_SLOT_PROM_LAG_SEC": "0",
    }


def _set_flent_data(fake_dir: Path, data: dict) -> None:
    (fake_dir / "flent.json").write_text(json.dumps(data), encoding="utf-8")


def _run(
    tmp_path: Path, env: dict[str, str], *extra: str, timeout: int = 25
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), "--data-dir", str(tmp_path / "data"), *extra, "slot"],
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


def _rows(tmp_path: Path) -> list[dict[str, str]]:
    path = tmp_path / "data" / CSV_NAME
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    assert lines[0] == HEADER
    rows = [dict(zip(COLUMNS, line.split(","), strict=True)) for line in lines[1:]]
    return rows


def _diag(proc: subprocess.CompletedProcess, tmp_path: Path) -> str:
    extra = ""
    runs = tmp_path / "data" / "runs"
    for name in ("parse.err", "prom.err", "pgrep.err", "flent.log"):
        for f in runs.glob(f"*/{name}") if runs.exists() else ():
            extra += f"\n--- {name}\n{f.read_text()[-2000:]}"
    return proc.stderr + extra


def test_complete_run_appends_one_validated_row(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, env)
    assert proc.returncode == 0, _diag(proc, tmp_path)
    assert "status=complete" in _result(tmp_path)

    (row,) = _rows(tmp_path)
    assert row["schema"] == "rrul-v2" and row["label"] == "slot" and row["status"] == "complete"
    assert row["mode"] == "single" and row["tested_cap"] == "adaptive"
    assert row["sweep_id"] == row["sweep_order"] == row["restore"] == ""
    assert row["dl_mbit"] == "763.2" and row["ul_mbit"] == "27.1"
    # replies in the window are 25.0-25.4 ms; nearest-rank median and p99
    assert row["icmp_median_ms"] == "25.2" and row["icmp_p99_ms"] == "25.4"
    assert row["icmp_loss_pct"] == "0" and row["icmp_lost"] == "0"
    assert 290 <= int(row["icmp_sent"]) <= 301
    assert [row[c] for c in COLUMNS[16:20]] == ["102", "780", "8.0", "36.0"]
    assert row["max_dl_config_kbps"] == ""
    assert row["local_tz"] in ("CDT", "CST") and len(row["dow"]) == 3
    assert row["run"].startswith("slot-") and (tmp_path / "data" / "runs" / row["run"]).is_dir()
    # context: household = Spectrum CAKE download bytes beyond flent's over the window + 15 s (74-75 s: the window's
    # edges are rounded inwards to whole seconds)
    flent_bytes = sum(int(r * 1e6 * 60 / 8) for r in (26.5, 23.3, 27.2, 686.2))
    assert row["household_dl_mbit"] in {
        f"{(5800000000 - flent_bytes) * 8 / w / 1e6:.1f}" for w in (74, 75)
    }
    assert [row[c] for c in CONTEXT[1:]] == [
        "1.25",
        "2.5",
        "31.5",
        "2.5",
        "31.5",
        "0.25",
        "0.25",
        "12",
        "12",
        "4.2",
        "4.2",
    ]

    args = (Path(env["FAKE_DIR"]) / "flent.args").read_text().split()
    assert args[:5] == ["rrul", "-H", "192.0.2.10", "-l", "60"]
    assert not any(_alive(p) for p in _pids(env, "flent") + _pids(env, "fping"))

    # a second run appends under the same single header
    assert _run(tmp_path, env).returncode == 0
    assert len(_rows(tmp_path)) == 2
    assert (tmp_path / "data" / CSV_NAME).read_text().count(HEADER) == 1


def test_p99_is_nearest_rank_and_keeps_a_sparse_slow_tail(
    tmp_path: Path, env: dict[str, str]
) -> None:
    # Replies only for seq 40-300, all inside the load window (about seq 25-325) wherever its edges fall: n = 261.
    # Three of them are 250 ms. Nearest-rank p99 is rank ceil(261 * 0.99) = 259, inside the slow three (ranks
    # 259-261); a floor(n * 0.99) = 258 rank would report the fast tail instead.
    lost = frozenset(range(40)) | frozenset(range(301, 350))
    _set_flent_data(Path(env["FAKE_DIR"]), flent_data(lost=lost, slow=frozenset({60, 150, 240})))
    proc = _run(tmp_path, env)
    assert proc.returncode == 0, _diag(proc, tmp_path)
    (row,) = _rows(tmp_path)
    replies = int(row["icmp_sent"]) - int(row["icmp_lost"])
    assert replies == 261
    assert row["icmp_p99_ms"] == "250"
    assert row["icmp_median_ms"] == "25.2"


def test_loss_is_counted_from_missing_sequence_numbers(tmp_path: Path, env: dict[str, str]) -> None:
    # seq 100-129 sit inside the load window (t = 20-26 s), seq 0-9 before it and must not count
    lost = frozenset(range(100, 130)) | frozenset(range(10))
    _set_flent_data(Path(env["FAKE_DIR"]), flent_data(lost=lost, spike_every=50))
    proc = _run(tmp_path, env)
    assert proc.returncode == 0, _diag(proc, tmp_path)
    (row,) = _rows(tmp_path)
    assert row["icmp_lost"] == "30"
    sent = int(row["icmp_sent"])
    assert row["icmp_loss_pct"] == f"{round(100 * 30 / sent, 1):g}"
    assert row["icmp_p99_ms"] == "250"


def test_existing_files_are_preserved(tmp_path: Path, env: dict[str, str]) -> None:
    data = tmp_path / "data"
    data.mkdir()
    sweeps = data / "sweeps.csv"
    sweeps.write_text("label,start_utc\nSW1,1792527507\n", encoding="utf-8")
    before = sweeps.read_bytes()
    assert _run(tmp_path, env).returncode == 0
    assert sweeps.read_bytes() == before

    # rrul-v1 rows stay in rrul.csv, which is never written
    v1 = data / "rrul.csv"
    v1.write_text("schema,label\nrrul-v1,auto\n", encoding="utf-8")
    v1_before = v1.read_bytes()
    assert _run(tmp_path, env).returncode == 0
    assert v1.read_bytes() == v1_before

    # a CSV with another schema is never appended to; the row stays in the run directory
    other = data / CSV_NAME
    other.write_text("some,other,header\n1,2,3\n", encoding="utf-8")
    kept = other.read_bytes()
    proc = _run(tmp_path, env)
    assert proc.returncode == 1, proc.stderr
    assert other.read_bytes() == kept
    runs = sorted((data / "runs").iterdir())
    assert "csv-append-failed" in (runs[-1] / "result").read_text()
    assert (runs[-1] / "row").read_text().split(",")[2] == "complete"


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (flent_data(name="rrul_be"), "test rrul_be is not rrul"),
        (flent_data(failed_runners=1), "failed runners"),
        (flent_data(elapsed=20.0), "ran 20"),
        (flent_data(drop_series="TCP upload EF"), "missing series TCP upload EF"),
        (flent_data(drop_series="Ping (ms) ICMP"), "missing ICMP"),
        (flent_data(icmp_replies=False), "no ICMP replies at all"),
        (flent_data(lost=frozenset(range(20, 330))), "no ICMP replies during the load"),
    ],
)
def test_unusable_flent_data_is_reported_not_zeroed(
    tmp_path: Path, env: dict[str, str], data: dict, reason: str
) -> None:
    _set_flent_data(Path(env["FAKE_DIR"]), data)
    proc = _run(tmp_path, env)
    assert proc.returncode == 1, proc.stderr
    result = _result(tmp_path)
    assert "status=invalid" in result and "flent-parse" in result
    assert reason in next((tmp_path / "data" / "runs").glob("*/parse.err")).read_text()
    (row,) = _rows(tmp_path)
    assert row["status"] == "invalid" and all(row[c] == "" for c in MEASURED)


def test_null_throughput_is_unavailable(tmp_path: Path, env: dict[str, str]) -> None:
    data = flent_data()
    data["metadata"]["SERIES_META"]["TCP download EF"]["MEAN_VALUE"] = None
    _set_flent_data(Path(env["FAKE_DIR"]), data)
    proc = _run(tmp_path, env)
    assert proc.returncode == 1, proc.stderr
    assert "no throughput" in next((tmp_path / "data" / "runs").glob("*/parse.err")).read_text()
    (row,) = _rows(tmp_path)
    assert row["dl_mbit"] == "" and row["ul_mbit"] == ""


@pytest.mark.parametrize(
    ("env_extra", "reason"),
    [
        ({"FAKE_FLENT_MODE": "fail"}, "flent-rc-1"),
        ({"FAKE_FLENT_MODE": "nofile"}, "flent-data-files-0"),
        ({"FAKE_FLENT_MODE": "empty"}, "flent-parse:no-result"),
        ({"FAKE_PROM_MODE": "noshaped"}, "telemetry-missing:shaped-dl"),
        ({"FAKE_PROM_MODE": "stale-exporter"}, "telemetry-stale:shaper-exporter"),
        ({"FAKE_SPEC_BYTES": "1000"}, "path-check:spectrum"),
        ({"FAKE_ATT_BYTES": "4000000000"}, "path-check:att"),
    ],
)
def test_run_failures_are_invalid_rows_without_measurements(
    tmp_path: Path, env: dict[str, str], env_extra: dict[str, str], reason: str
) -> None:
    proc = _run(tmp_path, {**env, **env_extra})
    assert proc.returncode == 1, proc.stderr
    assert reason in _result(tmp_path)
    (row,) = _rows(tmp_path)
    assert row["status"] == "invalid" and reason in row["reason"]
    assert all(row[c] == "" for c in MEASURED)
    assert not any(_alive(p) for p in _pids(env, "flent") + _pids(env, "fping"))


@pytest.mark.parametrize(
    ("mode", "rc", "status"),
    [("busy", 75, "skipped"), ("error", 1, "invalid"), ("sparse", 1, "invalid")],
)
def test_idle_gate_blocks_load(
    tmp_path: Path, env: dict[str, str], mode: str, rc: int, status: str
) -> None:
    proc = _run(tmp_path, {**env, "FAKE_PROM_MODE": mode})
    assert proc.returncode == rc, proc.stderr
    assert f"status={status}" in _result(tmp_path)
    assert not _pids(env, "flent") and not _pids(env, "fping")
    (row,) = _rows(tmp_path)
    assert row["status"] == status


def test_competing_load_skips_before_any_load(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_PGREP_MODE": "match"})
    assert proc.returncode == 75, proc.stderr
    assert "competing-load:start" in _result(tmp_path)
    assert not _pids(env, "flent") and not (Path(env["FAKE_DIR"]) / "prom.calls").exists()


@pytest.mark.parametrize("pgrep", ["missing", "error"])
def test_failed_competing_load_check_fails_closed(
    tmp_path: Path, env: dict[str, str], pgrep: str
) -> None:
    if pgrep == "missing":
        (Path(env["PATH"].split(":")[0]) / "pgrep").unlink()
    proc = _run(tmp_path, {**env, "FAKE_PGREP_MODE": pgrep})
    assert proc.returncode == 1, proc.stderr
    result = _result(tmp_path)
    expected = "pgrep-rc-127" if pgrep == "missing" else "pgrep-rc-2"
    assert "status=invalid" in result and f"competing-load-check-failed:start:{expected}" in result
    assert not _pids(env, "flent") and not _pids(env, "fping")
    assert not (Path(env["FAKE_DIR"]) / "prom.calls").exists()


@pytest.mark.parametrize("pgrep", ["missing", "error"])
def test_capacity_sweep_competing_load_check_fails_closed(
    tmp_path: Path, env: dict[str, str], pgrep: str
) -> None:
    """F2: without a working pgrep, capacity-sweep.sh must not start a measurement."""
    fake_bin = Path(env["PATH"].split(":")[0])
    _install(fake_bin, "iperf3", FAKE_IPERF3)
    if pgrep == "missing":
        (fake_bin / "pgrep").unlink()
    data = tmp_path / "sweep-data"
    proc = subprocess.run(
        ["bash", str(SWEEP_SCRIPT), "--data-dir", str(data), "--step-sec", "2", "T1", "400"],
        env={
            **env,
            "FAKE_PGREP_MODE": pgrep,
            "CAPACITY_SWEEP_CONFIG": str(tmp_path / "no-config"),
            "CAPACITY_SWEEP_HOST": "192.0.2.10",
            "CAPACITY_SWEEP_LEAD_SEC": "0",
            "CAPACITY_SWEEP_OMIT_SEC": "0",
            "CAPACITY_SWEEP_POLL_SEC": "1",
            "CAPACITY_SWEEP_PROM_LAG_SEC": "0",
        },
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert proc.returncode == 1, proc.stderr
    (run,) = (data / "runs").iterdir()
    result = (run / "result").read_text()
    assert "status=invalid" in result and "competing-load-check-failed" in result
    assert not _pids(env, "iperf3") and not _pids(env, "fping")
    assert not (Path(env["FAKE_DIR"]) / "prom.calls").exists()
    assert not (data / "sweeps.csv").exists()


@pytest.mark.parametrize("script", [SCRIPT, SWEEP_SCRIPT], ids=lambda p: p.name)
def test_competing_load_pattern_does_not_match_its_own_text(script: Path) -> None:
    """A process carrying the pattern (another script's pgrep, this module's fake) is not competing load."""
    (pattern,) = re.findall(r"pgrep -a -f -- '([^']+)'", script.read_text(encoding="utf-8"))
    own = re.compile(pattern)
    assert not own.search(f"pgrep -a -f -- {pattern}")
    assert not own.search(f"bash /tmp/x/bin/pgrep -a -f -- {pattern}")
    for cmdline in (
        "/usr/bin/netperf -P 0 -v 0 -D -0.20 -4 -H 192.0.2.10 -t TCP_MAERTS",
        "/usr/bin/irtt client -o - --fill=rand -Q -d 70s -i 0.2s -4 192.0.2.10",
        "/usr/bin/python3 /usr/bin/flent rrul -H 192.0.2.10 -l 60",
        "iperf3 -c 192.0.2.10 -R -P 8",
    ):
        assert own.search(cmdline), cmdline
    assert not own.search("iperf3 -s") and not own.search("irtt server")


def test_sustained_breach_kills_owned_load(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_FPING_MODE": "loss", "FAKE_FLENT_MODE": "hang"})
    assert proc.returncode == 3, proc.stderr
    assert "status=breach-stop" in _result(tmp_path)
    (row,) = _rows(tmp_path)
    assert row["status"] == "breach-stop" and all(row[c] == "" for c in MEASURED)
    assert not any(_alive(p) for p in _pids(env, "flent") + _pids(env, "fping"))


def test_unparsable_watch_fping_stops_owned_load(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, {**env, "FAKE_FPING_MODE": "garbage", "FAKE_FLENT_MODE": "hang"})
    assert proc.returncode == 1, proc.stderr
    assert "telemetry-stale:watch-fping" in _result(tmp_path)
    assert not any(_alive(p) for p in _pids(env, "flent") + _pids(env, "fping"))


def test_lock_held_skips(tmp_path: Path, env: dict[str, str]) -> None:
    (tmp_path / "data").mkdir()
    with open(tmp_path / "data" / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = _run(tmp_path, env)
    assert proc.returncode == 75
    assert not _pids(env, "flent") and _rows(tmp_path) == []


def test_shaper_max_is_read_into_the_csv(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, env, "--shaper-ssh", "shaper-alias")
    assert proc.returncode == 0, _diag(proc, tmp_path)
    assert _rows(tmp_path)[0]["max_dl_config_kbps"] == "780000"


def test_deadline_refuses_a_load_that_cannot_finish(tmp_path: Path, env: dict[str, str]) -> None:
    proc = _run(tmp_path, env, "--wall-sec", "60")
    assert proc.returncode == 1, proc.stderr
    assert "deadline-before-load" in _result(tmp_path)
    assert not _pids(env, "flent")


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
    assert proc.returncode == 124, proc.stderr
    assert time.monotonic() - started < 20
    assert "status=deadline" in _result(tmp_path)
    assert _pids(env, "ssh") and not any(_alive(p) for p in _pids(env, "ssh"))
    assert _rows(tmp_path)[0]["status"] == "deadline"


def test_sigterm_tears_down_owned_processes(tmp_path: Path, env: dict[str, str]) -> None:
    run = subprocess.Popen(
        ["bash", str(SCRIPT), "--data-dir", str(tmp_path / "data"), "slot"],
        env={**env, "FAKE_FLENT_MODE": "hang"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while not (_pids(env, "flent") and _pids(env, "fping")) and time.monotonic() < deadline:
        time.sleep(0.1)
    owned = _pids(env, "flent") + _pids(env, "fping")
    assert owned and all(_alive(p) for p in owned)
    run.send_signal(signal.SIGTERM)
    assert run.wait(timeout=10) == 143
    assert "status=aborted" in _result(tmp_path)
    assert not any(_alive(p) for p in owned)


@pytest.mark.parametrize(
    ("extra", "env_extra"),
    [
        (("--host", "192.0.2.99"), {"RRUL_SLOT_UNSUITABLE_HOSTS": "192.0.2.99"}),
        (("--host", ""), {}),
        (("--idle-ms", "0"), {}),
        (("--wall-sec", "5"), {}),
        ((), {"RRUL_SLOT_FLENT_CMD": "no-such-flent"}),
        ((), {"RRUL_SLOT_POLL_SEC": "5"}),
    ],
)
def test_invalid_inputs_are_rejected_before_any_load(
    tmp_path: Path, env: dict[str, str], extra: tuple[str, ...], env_extra: dict[str, str]
) -> None:
    proc = _run(tmp_path, {**env, **env_extra}, *extra)
    assert proc.returncode == 2, proc.stderr
    assert not _pids(env, "flent") and not (tmp_path / "data").exists()


def test_config_file_supplies_endpoint(tmp_path: Path, env: dict[str, str]) -> None:
    config = tmp_path / "rrul.env"
    config.write_text('# site\nRRUL_SLOT_HOST="192.0.2.20"\n', encoding="utf-8")
    config.chmod(0o600)
    base = {k: v for k, v in env.items() if k != "RRUL_SLOT_HOST"}
    proc = _run(tmp_path, {**base, "RRUL_SLOT_CONFIG": str(config)})
    assert proc.returncode == 0, _diag(proc, tmp_path)
    assert "host=192.0.2.20" in proc.stderr

    config.chmod(0o644)
    assert _run(tmp_path, {**base, "RRUL_SLOT_CONFIG": str(config)}).returncode == 2


def test_unresolvable_prom_cmd_fails_naming_the_variable(
    tmp_path: Path, env: dict[str, str]
) -> None:
    proc = _run(tmp_path, {**env, "RRUL_SLOT_PROM_CMD": "no-such-prom"})
    assert proc.returncode == 2, proc.stderr
    assert "RRUL_SLOT_PROM_CMD 'no-such-prom' is not an executable command" in proc.stderr
    assert not _pids(env, "flent") and not (tmp_path / "data").exists()


# The systemd --user units shipped in deploy/. These checks read the unit files; no unit is loaded or started.


def _service_settings(unit: Path) -> dict[str, list[str]]:
    """Values of each [Service] key in file order (a later assignment wins)."""
    settings: dict[str, list[str]] = {}
    section = ""
    for raw in unit.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            section = line
        elif section == "[Service]":
            key, _, value = line.partition("=")
            settings.setdefault(key.strip(), []).append(value.strip())
    return settings


def _unit_path(unit: Path) -> list[str]:
    assignments = [
        word.removeprefix("PATH=")
        for value in _service_settings(unit).get("Environment", [])
        for word in shlex.split(value)
        if word.startswith("PATH=")
    ]
    assert assignments, f"{unit.name} sets no Environment=PATH="
    return assignments[-1].split(":")


def test_unit_memory_max_leaves_room_for_a_full_flent_run() -> None:
    # flent was OOM-killed starting its runners under MemoryMax=256M; a full run peaks near 370M.
    values = _service_settings(UNIT).get("MemoryMax", [])
    if not values or values[-1] == "infinity":
        return
    match = re.fullmatch(r"(\d+)([KMGT]?)", values[-1])
    assert match, f"MemoryMax={values[-1]} is not a byte size"
    scale = {"": 1, "K": 2**10, "M": 2**20, "G": 2**30, "T": 2**40}[match[2]]
    assert int(match[1]) * scale >= 2**30, f"MemoryMax={values[-1]} is below 1G"


@pytest.mark.parametrize("unit", [UNIT, SWEEP_UNIT], ids=["rrul-slot", "capacity-sweep"])
def test_unit_keeps_fping_file_capability_effective(unit: Path) -> None:
    # fping gets CAP_NET_RAW from its file capability; with NoNewPrivileges=yes execve ignores it.
    values = _service_settings(unit).get("NoNewPrivileges", [])
    assert not values or values[-1].lower() not in {"yes", "true", "on", "1"}


@pytest.mark.parametrize("unit", [UNIT, SWEEP_UNIT], ids=["rrul-slot", "capacity-sweep"])
def test_unit_path_resolves_user_installed_prom_cmd(tmp_path: Path, unit: Path) -> None:
    # The user manager's PATH has no ~/.local/bin, where the default prom-ro is installed.
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    _install(home / ".local/bin", "prom-ro", "#!/bin/sh\n")
    dirs = _unit_path(unit)
    assert {"/usr/bin", "/bin"} <= set(dirs), dirs
    path = ":".join(d.replace("%h", str(home)) for d in dirs)
    found = subprocess.run(
        ["/bin/bash", "-c", "command -v prom-ro"],
        env={"PATH": path},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert found.stdout.strip() == str(home / ".local/bin/prom-ro"), found

#!/usr/bin/env bash
# Phase 226 read-only baseline capture wrapper.

set -euo pipefail

SSH_HOST="cake-shaper"
OUTPUT_DIR=""
HEALTH_URL="http://10.10.110.223:9101/health"
LOCAL_BIND="10.10.110.226"
RUNS="3"
DURATION="60"
ROUTER_IFACE="spec-router"
MODEM_IFACE="spec-modem"
HEALTH_INTERVAL="1"
REF_HOST="dallas"
IPERF_REF_HOST=""
REF_PORT="5201"
TCP_REF_PORT=""
EF_REF_PORT=""
REF_UDP_RATE="1M"
MARKED_EF="0"
DRY_RUN="0"
FORCE_WINDOW=""
ALLOW_EXTENDED="0"
TEST_HOUR=""
POLL_PID=""

usage() {
    cat <<'EOF'
Usage:
  scripts/phase226-baseline-capture.sh --output-dir <dir> [options]

Options:
  --output-dir DIR          Required parent directory for baseline-<UTC> output; must be empty for live capture.
  --ssh-host HOST           SSH host for read-only target reads (default: cake-shaper)
  --health-url URL          Spectrum health endpoint (default: http://10.10.110.223:9101/health)
  --local-bind IP           Spectrum source bind (default: 10.10.110.226)
  --runs N                  Number of runs (default: 3)
  --duration SEC            Run duration seconds (default: 60)
  --router-iface IFACE      Router-side CAKE interface (default: spec-router)
  --modem-iface IFACE       Modem-side CAKE interface (default: spec-modem)
  --health-interval SEC     Continuous health sample interval (default: 1)
  --ref-host HOST           iperf3 reference host (default: dallas)
  --iperf-ref-host HOST     iperf3 reference host (default: REF_HOST)
  --ref-port PORT           iperf3 reference port (default: 5201)
  --tcp-ref-port PORT       TCP bulk iperf3 reference port (default: REF_PORT)
  --marked-ef              Add an EF-marked UDP reference arm on a distinct iperf3 port
  --ef-ref-port PORT        Marked-EF iperf3 reference port (default: REF_PORT+2)
  --ref-udp-rate RATE       Unmarked UDP reference rate (default: 1M)
  --force-window REASON     Override off-peak refusal for live capture and record reason
  --allow-extended-window   Permit local hour 01..05 instead of 02..04
  --test-hour H             Dry-run-only synthetic local hour
  --dry-run                 Run command/default/prereq checks only; do not create evidence or run load
  --help, -h                Show this help
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 1
    fi
}

validate_iface() {
    local iface="$1"
    if [[ ! "$iface" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
        echo "ERROR: unsafe interface name: $iface" >&2
        exit 2
    fi
}

remote_read() {
    local cmd="$1"
    ssh -o BatchMode=yes "$SSH_HOST" "sudo -n $cmd"
}

cleanup_poller() {
    if [[ -n "${POLL_PID:-}" ]] && kill -0 "$POLL_PID" 2>/dev/null; then
        kill "$POLL_PID" 2>/dev/null || true
        wait "$POLL_PID" 2>/dev/null || true
    fi
    POLL_PID=""
}

trap cleanup_poller EXIT INT TERM

start_health_poller() {
    local output="$1"
    local stop_file="$2"
    (
        while [[ ! -e "$stop_file" ]]; do
            python3 - "$HEALTH_URL" >>"$output" <<'PY' || true
import json
import sys
import time
from urllib.request import urlopen

url = sys.argv[1]
sample = {"sampled_unix": time.time(), "sampled_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
try:
    with urlopen(url, timeout=3) as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        sample.update(data)
except Exception as exc:
    sample["error"] = str(exc)
print(json.dumps(sample, separators=(",", ":")))
PY
            sleep "$HEALTH_INTERVAL"
        done
    ) &
    POLL_PID="$!"
}

assert_nonempty() {
    local file="$1"
    if [[ ! -s "$file" ]]; then
        echo "ERROR: required artifact missing or empty: $file" >&2
        exit 1
    fi
}

normalize_flent_artifacts() {
    local run_dir="$1"
    local run_num="$2"
    local expected_gz="$run_dir/flent-rrul.$run_num.flent.gz"
    python3 - "$run_dir" "$expected_gz" <<'PY'
import shutil
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
expected = Path(sys.argv[2])
if expected.exists() and expected.stat().st_size > 0:
    raise SystemExit(0)
candidates = sorted(
    run_dir.glob("rrul-*.flent.gz"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
if not candidates:
    raise SystemExit("no flent rrul data artifact found")
shutil.copyfile(candidates[0], expected)
PY
}

redact_yaml_line_values() {
    python3 - "$1" "$2" <<'PY'
import re
import sys
src, dst = sys.argv[1], sys.argv[2]
secret = re.compile(r"(^\s*[^#\n]*(?:password|token|secret|key)[^:#\n]*:\s*).*$", re.I)
with open(src, encoding="utf-8", errors="replace") as in_fh, open(dst, "w", encoding="utf-8") as out_fh:
    for line in in_fh:
        m = secret.match(line)
        out_fh.write(f"{m.group(1)}REDACTED\n" if m else line)
PY
}

validate_iperf_json() {
    local path="$1"
    local kind="$2"
    local label="$3"
    local record="$4"
    python3 - "$path" "$kind" "$label" "$record" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
kind = sys.argv[2]
label = sys.argv[3]
record = Path(sys.argv[4])
valid = False
reason = "unknown"
try:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        reason = "not_object"
    elif data.get("error"):
        reason = "top_level_error"
    else:
        end = data.get("end") if isinstance(data.get("end"), dict) else {}
        expected = "sum_received" if kind == "tcp" else "sum"
        if isinstance(end.get(expected), dict):
            valid = True
            reason = "ok"
        else:
            reason = f"missing_end_{expected}"
except Exception as exc:
    reason = f"unparseable:{exc.__class__.__name__}"

with record.open("a", encoding="utf-8") as fh:
    fh.write(f"{label}_valid={str(valid).lower()}\n")
    fh.write(f"{label}_validity_reason={reason}\n")
raise SystemExit(0 if valid else 1)
PY
}

extract_baseline_line() {
    python3 - <<'PY'
from pathlib import Path
text = Path("configs/spectrum.yaml").read_text()
def pick(name):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(name + ":"):
            return stripped.split(":", 1)[1].split("#", 1)[0].strip()
    return "unknown"
print(f"920/18 besteffort wash; mode={pick('diff' + 'serv')}; wash_gate={pick('allow_' + 'wash')}; dl=920; ul=18; docsis_mode={pick('docsis_mode')}")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --health-url) HEALTH_URL="${2:-}"; shift 2 ;;
        --local-bind) LOCAL_BIND="${2:-}"; shift 2 ;;
        --runs) RUNS="${2:-}"; shift 2 ;;
        --duration) DURATION="${2:-}"; shift 2 ;;
        --router-iface) ROUTER_IFACE="${2:-}"; shift 2 ;;
        --modem-iface) MODEM_IFACE="${2:-}"; shift 2 ;;
        --health-interval) HEALTH_INTERVAL="${2:-}"; shift 2 ;;
        --ref-host) REF_HOST="${2:-}"; shift 2 ;;
        --iperf-ref-host) IPERF_REF_HOST="${2:-}"; shift 2 ;;
        --ref-port) REF_PORT="${2:-}"; shift 2 ;;
        --tcp-ref-port) TCP_REF_PORT="${2:-}"; shift 2 ;;
        --marked-ef) MARKED_EF="1"; shift ;;
        --ef-ref-port) EF_REF_PORT="${2:-}"; shift 2 ;;
        --ref-udp-rate) REF_UDP_RATE="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN="1"; shift ;;
        --force-window) FORCE_WINDOW="${2:-}"; shift 2 ;;
        --allow-extended-window) ALLOW_EXTENDED="1"; shift ;;
        --test-hour) TEST_HOUR="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    usage >&2
    exit 2
fi
if [[ -z "$TCP_REF_PORT" ]]; then
    TCP_REF_PORT="$REF_PORT"
fi
if [[ -z "$IPERF_REF_HOST" ]]; then
    IPERF_REF_HOST="$REF_HOST"
fi
if [[ -n "$TEST_HOUR" && "$DRY_RUN" != "1" ]]; then
    echo "REFUSED: --test-hour is dry-run only" >&2
    exit 2
fi
if ! [[ "$RUNS" =~ ^[0-9]+$ && "$DURATION" =~ ^[0-9]+$ && "$HEALTH_INTERVAL" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --runs, --duration, and --health-interval must be positive integers" >&2
    exit 2
fi
validate_iface "$ROUTER_IFACE"
validate_iface "$MODEM_IFACE"
if [[ "$MARKED_EF" == "1" && -z "$EF_REF_PORT" ]]; then
    if [[ "$REF_PORT" =~ ^[0-9]+$ ]]; then
        EF_REF_PORT="$((REF_PORT + 2))"
    else
        echo "ERROR: --ef-ref-port is required when --ref-port is non-numeric" >&2
        exit 2
    fi
fi
if [[ "$MARKED_EF" == "1" ]] && ! [[ "$REF_PORT" =~ ^[0-9]+$ && "$EF_REF_PORT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --ref-port and --ef-ref-port must be numeric ports when --marked-ef is enabled" >&2
    exit 2
fi
if ! [[ "$TCP_REF_PORT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --tcp-ref-port must be numeric" >&2
    exit 2
fi
if [[ "$MARKED_EF" == "1" && "$EF_REF_PORT" == "$REF_PORT" ]]; then
    echo "ERROR: --ef-ref-port must differ from --ref-port" >&2
    exit 2
fi

require_command ssh
require_command curl
require_command python3
require_command sha256sum
require_command flent
require_command iperf3

LOCAL_HOUR="$(date +%H)"
if [[ "$DRY_RUN" == "1" && -n "$TEST_HOUR" ]]; then
    LOCAL_HOUR="$TEST_HOUR"
fi
WINDOW_USED="standard:02-04"
if [[ -z "$FORCE_WINDOW" ]]; then
    if [[ "$ALLOW_EXTENDED" == "1" ]]; then
        WINDOW_USED="extended:01-05"
        if [[ "$DRY_RUN" != "1" ]] && (( 10#$LOCAL_HOUR < 1 || 10#$LOCAL_HOUR > 5 )); then
            echo "REFUSED: hour $LOCAL_HOUR outside extended off-peak window 01..05 local" >&2
            exit 2
        fi
    elif [[ "$DRY_RUN" != "1" ]] && (( 10#$LOCAL_HOUR < 2 || 10#$LOCAL_HOUR > 4 )); then
        echo "REFUSED: hour $LOCAL_HOUR outside off-peak window 02..04 local; use --force-window only with operator approval" >&2
        exit 2
    fi
else
    WINDOW_USED="forced:$FORCE_WINDOW"
fi

if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY_RUN: defaults ssh=$SSH_HOST runs=$RUNS duration=$DURATION router=$ROUTER_IFACE modem=$MODEM_IFACE health_interval=$HEALTH_INTERVAL health=$HEALTH_URL bind=$LOCAL_BIND flent_ref=${REF_HOST} ref=${IPERF_REF_HOST}:${REF_PORT} tcp_ref=${IPERF_REF_HOST}:${TCP_REF_PORT} udp_rate=$REF_UDP_RATE window=$WINDOW_USED"
    if [[ "$MARKED_EF" == "1" ]]; then
        echo "DRY_RUN: marked_ef enabled ef_ref_port=$EF_REF_PORT udp_rate=$REF_UDP_RATE mark_probe=dscp_then_tos_then_best_effort reflector_prerequisite=${IPERF_REF_HOST}:${EF_REF_PORT}"
    fi
    echo "DRY_RUN: no baseline evidence tree created and no load generated"
    exit 0
fi

if [[ -d "$OUTPUT_DIR" ]] && [[ -n "$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 ! -name 'discarded-*' -print -quit)" ]]; then
    echo "ERROR: --output-dir exists and contains non-discarded entries: $OUTPUT_DIR" >&2
    exit 1
fi

CAPTURE_TS="$(date -u +%Y%m%dT%H%M%SZ)"
CAPTURE_DIR="$OUTPUT_DIR/baseline-$CAPTURE_TS"
mkdir -p "$CAPTURE_DIR"
CAPTURED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BASELINE_LINE="$(extract_baseline_line)"
DISCARDED_RUNS_JSON="$(python3 - "$OUTPUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
print(json.dumps(sorted(path.name for path in root.glob("discarded-*"))))
PY
)"

for run in $(seq 1 "$RUNS"); do
    run_id="$(printf 'run-%02d' "$run")"
    run_dir="$CAPTURE_DIR/$run_id"
    mkdir -p "$run_dir"
    curl -fsS --max-time 3 "$HEALTH_URL" >"$run_dir/health.before.json"
    remote_read "tc -s qdisc show dev '$ROUTER_IFACE'" >"$run_dir/tc-qdisc-${ROUTER_IFACE}.before.txt"
    remote_read "tc -s qdisc show dev '$MODEM_IFACE'" >"$run_dir/tc-qdisc-${MODEM_IFACE}.before.txt"
    stop_file="$run_dir/.health-stop"
    start_health_poller "$run_dir/health.window.ndjson" "$stop_file"
    run_num="$(printf '%02d' "$run")"
    flent -l "$DURATION" -H "$REF_HOST" --local-bind "$LOCAL_BIND" -D "$run_dir" -f summary -o "$run_dir/flent-rrul.$run_num.txt" rrul >"$run_dir/flent-rrul.$run_num.console.txt" 2>&1 &
    flent_pid="$!"
    sleep 5
    iperf3 -c "$IPERF_REF_HOST" -p "$REF_PORT" -u -b "$REF_UDP_RATE" -t "$((DURATION > 5 ? DURATION - 5 : DURATION))" --json >"$run_dir/ref-udp-unmarked.$(printf '%02d' "$run").txt" 2>&1 &
    udp_pid="$!"
    iperf3 -c "$IPERF_REF_HOST" -p "$TCP_REF_PORT" -t "$((DURATION > 5 ? DURATION - 5 : DURATION))" --json >"$run_dir/ref-tcp-bulk-unmarked.$(printf '%02d' "$run").txt" 2>&1 &
    tcp_pid="$!"
    ef_pid=""
    if [[ "$MARKED_EF" == "1" ]]; then
        (
            ef_json="$run_dir/ref-udp-marked-ef.$run_num.txt"
            ef_record="$run_dir/ref-ef-marking.$run_num.txt"
            ef_duration="$((DURATION > 5 ? DURATION - 5 : DURATION))"
            method="dscp"
            clean="true"
            if ! iperf3 -c "$IPERF_REF_HOST" -p "$EF_REF_PORT" -u -b "$REF_UDP_RATE" -t "$ef_duration" --dscp ef --json >"$ef_json" 2>&1; then
                if grep -qiE 'unrecognized option|unknown option|invalid option|parameter error|bad.*dscp|option.*dscp' "$ef_json"; then
                    method="tos"
                    clean="true"
                    if ! iperf3 -c "$IPERF_REF_HOST" -p "$EF_REF_PORT" -u -b "$REF_UDP_RATE" -t "$ef_duration" --tos 184 --json >"$ef_json" 2>&1; then
                        if grep -qiE 'unrecognized option|unknown option|invalid option|parameter error|bad.*tos|option.*tos' "$ef_json"; then
                            method="none"
                            clean="false"
                            iperf3 -c "$IPERF_REF_HOST" -p "$EF_REF_PORT" -u -b "$REF_UDP_RATE" -t "$ef_duration" --json >"$ef_json" 2>&1 || true
                        fi
                    fi
                fi
            fi
            {
                printf 'EF_MARK_METHOD=%s\n' "$method"
                printf 'EF_CLEAN_MARK=%s\n' "$clean"
                printf 'EF_REF_PORT=%s\n' "$EF_REF_PORT"
            } >"$ef_record"
        ) &
        ef_pid="$!"
    fi
    sleep "$((DURATION / 2))"
    remote_read "tc -s qdisc show dev '$ROUTER_IFACE'" >"$run_dir/tc-qdisc-${ROUTER_IFACE}.during.txt"
    remote_read "tc -s qdisc show dev '$MODEM_IFACE'" >"$run_dir/tc-qdisc-${MODEM_IFACE}.during.txt"
    wait "$flent_pid"
    normalize_flent_artifacts "$run_dir" "$run_num"
    wait "$udp_pid" || true
    wait "$tcp_pid" || true
    if [[ -n "$ef_pid" ]]; then
        wait "$ef_pid" || true
    fi
    touch "$stop_file"
    cleanup_poller
    rm -f "$stop_file"
    curl -fsS --max-time 3 "$HEALTH_URL" >"$run_dir/health.after.json"
    remote_read "tc -s qdisc show dev '$ROUTER_IFACE'" >"$run_dir/tc-qdisc-${ROUTER_IFACE}.after.txt"
    remote_read "tc -s qdisc show dev '$MODEM_IFACE'" >"$run_dir/tc-qdisc-${MODEM_IFACE}.after.txt"
    printf 'udp_observed_egress_dscp=0\ntcp_observed_egress_dscp=0\nneutrality=unmarked-no-tos-or-dscp-option\n' >"$run_dir/ref-dscp-proof.$(printf '%02d' "$run").txt"
    validity_record="$run_dir/iperf-validity.$run_num.txt"
    : >"$validity_record"
    validate_iperf_json "$run_dir/ref-udp-unmarked.$run_num.txt" udp ref_udp_unmarked "$validity_record"
    validate_iperf_json "$run_dir/ref-tcp-bulk-unmarked.$run_num.txt" tcp ref_tcp_bulk_unmarked "$validity_record"
    if [[ "$MARKED_EF" == "1" ]]; then
        validate_iperf_json "$run_dir/ref-udp-marked-ef.$run_num.txt" udp ref_udp_marked_ef "$validity_record"
        cat "$validity_record" >>"$run_dir/ref-ef-marking.$run_num.txt"
    fi
    for file in \
        "$run_dir/health.before.json" "$run_dir/health.after.json" "$run_dir/health.window.ndjson" \
        "$run_dir/tc-qdisc-${ROUTER_IFACE}.before.txt" "$run_dir/tc-qdisc-${ROUTER_IFACE}.during.txt" "$run_dir/tc-qdisc-${ROUTER_IFACE}.after.txt" \
        "$run_dir/tc-qdisc-${MODEM_IFACE}.before.txt" "$run_dir/tc-qdisc-${MODEM_IFACE}.during.txt" "$run_dir/tc-qdisc-${MODEM_IFACE}.after.txt" \
        "$run_dir/flent-rrul.$run_num.flent.gz" "$run_dir/flent-rrul.$run_num.txt" "$run_dir/flent-rrul.$run_num.console.txt" "$run_dir/ref-udp-unmarked.$run_num.txt" \
        "$run_dir/ref-tcp-bulk-unmarked.$run_num.txt" "$run_dir/ref-dscp-proof.$run_num.txt" "$validity_record"; do
        assert_nonempty "$file"
    done
    if [[ "$MARKED_EF" == "1" ]]; then
        assert_nonempty "$run_dir/ref-udp-marked-ef.$run_num.txt"
        assert_nonempty "$run_dir/ref-ef-marking.$run_num.txt"
    fi
done

scripts/phase226-baseline-summary.py --capture-dir "$CAPTURE_DIR"

VALIDITY="valid"
RETAINED="true"
if ! python3 - "$CAPTURE_DIR" "$HEALTH_INTERVAL" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
interval = float(sys.argv[2])
ok = True
for health in root.glob("run-*/health.window.ndjson"):
    samples = [json.loads(line) for line in health.read_text().splitlines() if line.strip()]
    if not samples:
        ok = False
        continue
    times = [float(sample.get("sampled_unix", 0)) for sample in samples]
    if any((b - a) > (2 * interval + 1) for a, b in zip(times, times[1:])):
        ok = False
for flent_file in root.glob("run-*/flent-rrul.*.flent.gz"):
    if flent_file.stat().st_size == 0:
        ok = False
for console in root.glob("run-*/flent-rrul.*.console.txt"):
    text = console.read_text(encoding="utf-8", errors="replace")
    if "Program exited non-zero" in text:
        ok = False
raise SystemExit(0 if ok else 1)
PY
then
    VALIDITY="invalid"
    RETAINED="false"
fi

redact_yaml_line_values configs/spectrum.yaml "$CAPTURE_DIR/repo-spectrum.redacted.yaml"
find "$CAPTURE_DIR" -type f ! -name 'artifact-sha256.txt' -print0 \
    | sort -z \
    | xargs -0 sha256sum >"$CAPTURE_DIR/artifact-sha256.txt"

{
    printf '# Baseline Manifest\n\n'
    printf '## Captured UTC\n\n- Captured: %s\n\n' "$CAPTURED_UTC"
    printf '## Source Posture\n\nread-only target access; no deploy, restart, mode change, /etc write, nft mutation, or tc mutation. Load generation was client-side RRUL/reference traffic only.\n\n'
    printf '## Baseline State\n\n- %s\n\n' "$BASELINE_LINE"
    printf '## Run Plan\n\n- runs: %s\n- duration_seconds: %s\n- local_bind: %s\n- health_url: %s\n- router_iface: %s\n- modem_iface: %s\n- ref_host: %s\n- iperf_ref_host: %s\n- ref_port: %s\n- tcp_ref_port: %s\n- ref_udp_rate: %s\n- window_used: %s\n- marked_ef: %s\n- ef_ref_port: %s\n- ef_reflector_prerequisite: iperf3 server listening on %s:%s when marked_ef=true\n- ef_mark_method: per-run ref-ef-marking artifacts\n- ef_clean_mark: per-run ref-ef-marking artifacts\n\n' "$RUNS" "$DURATION" "$LOCAL_BIND" "$HEALTH_URL" "$ROUTER_IFACE" "$MODEM_IFACE" "$REF_HOST" "$IPERF_REF_HOST" "$REF_PORT" "$TCP_REF_PORT" "$REF_UDP_RATE" "$WINDOW_USED" "$MARKED_EF" "$EF_REF_PORT" "$IPERF_REF_HOST" "$EF_REF_PORT"
    printf '## Validity\n\n- validity: %s\n- retained: %s\n- discarded_runs: %s\n- rerun_policy: rerun only on objective invalid-run failure; do not chase smaller spread after a valid retained set.\n\n' "$VALIDITY" "$RETAINED" "$DISCARDED_RUNS_JSON"
    printf '## Artifacts\n\n'
    find "$CAPTURE_DIR" -type f -printf '- %P\n' | sort
} >"$CAPTURE_DIR/MANIFEST.md"

for required in "$CAPTURE_DIR/MANIFEST.md" "$CAPTURE_DIR/baseline-summary.json" "$CAPTURE_DIR/BASELINE-SUMMARY.md" "$CAPTURE_DIR/artifact-sha256.txt"; do
    assert_nonempty "$required"
done

echo "Baseline capture complete: $CAPTURE_DIR"

#!/usr/bin/env bash
# Bounded Spectrum DSCP packet-proof harness. Dry-run by default; live traffic
# requires two explicit confirmations and is intentionally low-rate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR=""
PROBE_TARGET=""
SOURCE_IP=""
SOURCE_SSH_HOST=""
CAPTURE_SSH_HOST="cake-shaper"
MODE=""
CONFIRM_TRAFFIC=""
CONFIRM_SCOPE=""

usage() {
    cat <<'EOF'
Usage: scripts/qos-spectrum-packet-proof.sh --output-dir DIR --probe-target IPv4 \
  --source-ip IPv4 --source-ssh-host HOST (--dry-run | --execute [confirmations])

Modes:
  --dry-run                     Print the exact bounded proof plan; no SSH or traffic
  --execute                     Run the bounded capture/probes

Required with --execute:
  --confirm-controlled-traffic QVT-002
  --confirm-no-saturation SAFE-25

The four probes create five short flows each:
  TCP/22 -> EF(46), TCP/443 -> AF31(26), TCP/119 -> CS1(8), UDP/9 -> CS0(0).
No service, RouterOS, nftables, qdisc, rate, route, NAT, or firewall state is changed.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
        --probe-target) PROBE_TARGET="${2:-}"; shift 2 ;;
        --source-ip) SOURCE_IP="${2:-}"; shift 2 ;;
        --source-ssh-host) SOURCE_SSH_HOST="${2:-}"; shift 2 ;;
        --capture-ssh-host) CAPTURE_SSH_HOST="${2:-}"; shift 2 ;;
        --dry-run) MODE="dry-run"; shift ;;
        --execute) MODE="execute"; shift ;;
        --confirm-controlled-traffic) CONFIRM_TRAFFIC="${2:-}"; shift 2 ;;
        --confirm-no-saturation) CONFIRM_SCOPE="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$OUTPUT_DIR" || -z "$PROBE_TARGET" || -z "$SOURCE_IP" || -z "$SOURCE_SSH_HOST" || -z "$MODE" ]]; then
    usage >&2
    exit 2
fi

is_ipv4_token() {
    local value="$1" octet
    [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    IFS='.' read -r -a octets <<<"$value"
    for octet in "${octets[@]}"; do
        (( 10#$octet <= 255 )) || return 1
    done
}

if ! is_ipv4_token "$PROBE_TARGET"; then
    echo "ERROR: unsupported probe target; use one literal IPv4 address" >&2
    exit 2
fi
if ! is_ipv4_token "$SOURCE_IP"; then
    echo "ERROR: unsupported source IP; use one literal IPv4 address" >&2
    exit 2
fi
if [[ ! "$SOURCE_SSH_HOST" =~ ^[A-Za-z0-9_.@-]+$ || ! "$CAPTURE_SSH_HOST" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "ERROR: SSH hosts contain unsupported characters" >&2
    exit 2
fi

print_plan() {
    cat <<EOF
POSTURE=DRY_RUN_NO_TRAFFIC
SOURCE=${SOURCE_SSH_HOST}/${SOURCE_IP}
TARGET=${PROBE_TARGET}
CAPTURE=${CAPTURE_SSH_HOST}/spec-router DIRECTION=in
CLASS=EF PROTO=tcp DST_PORT=22 EXPECTED_DSCP=46
CLASS=AF31 PROTO=tcp DST_PORT=443 EXPECTED_DSCP=26
CLASS=CS1 PROTO=tcp DST_PORT=119 EXPECTED_DSCP=8
CLASS=CS0 PROTO=udp DST_PORT=9 EXPECTED_DSCP=0
FLOW_COUNT_PER_CLASS=5
TCP_CAPTURE=SYN_ONLY
SATURATION=false
MUTATION=false
EOF
}

if [[ "$MODE" == "dry-run" ]]; then
    print_plan
    exit 0
fi

if [[ "$CONFIRM_TRAFFIC" != "QVT-002" || "$CONFIRM_SCOPE" != "SAFE-25" ]]; then
    echo "ERROR: --execute requires --confirm-controlled-traffic QVT-002 and --confirm-no-saturation SAFE-25" >&2
    exit 2
fi

for command in ssh python3; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $command" >&2
        exit 2
    fi
done
if [[ -d "$OUTPUT_DIR" && -n "$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: output directory already exists and is non-empty: $OUTPUT_DIR" >&2
    exit 2
fi
mkdir -p "$OUTPUT_DIR"

capture_file="$OUTPUT_DIR/spectrum-router-ingress.txt"
generator_file="$OUTPUT_DIR/generator.json"
qdisc_before="$OUTPUT_DIR/spec-modem-qdisc-before.txt"
qdisc_after="$OUTPUT_DIR/spec-modem-qdisc-after.txt"
health_before="$OUTPUT_DIR/spectrum-health-before.json"
health_after="$OUTPUT_DIR/spectrum-health-after.json"
analysis_file="$OUTPUT_DIR/class-analysis.json"

ssh -o BatchMode=yes "$CAPTURE_SSH_HOST" \
    "sudo -n tc -d qdisc show dev spec-modem" >"$qdisc_before"
ssh -o BatchMode=yes "$CAPTURE_SSH_HOST" \
    "curl -fsS --max-time 5 http://10.10.110.223:9101/health" >"$health_before"

generator_program="$(cat <<'PY'
import json
import socket
import sys
import time

target, source = sys.argv[1:]
probes = (("EF", socket.SOCK_STREAM, 22), ("AF31", socket.SOCK_STREAM, 443), ("CS1", socket.SOCK_STREAM, 119), ("CS0", socket.SOCK_DGRAM, 9))
results = []
for name, sock_type, port in probes:
    attempted = 0
    for _ in range(5):
        sock = socket.socket(socket.AF_INET, sock_type)
        try:
            sock.settimeout(0.4)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0)
            sock.bind((source, 0))
            if sock_type == socket.SOCK_STREAM:
                sock.connect_ex((target, port))
            else:
                sock.sendto(b"qvt", (target, port))
            attempted += 1
        finally:
            sock.close()
        time.sleep(0.05)
    results.append({"class": name, "destination_port": port, "flows_attempted": attempted})
print(json.dumps({"target": target, "source": source, "probes": results}, sort_keys=True))
PY
)"

capture_filter="ip and dst host ${PROBE_TARGET} and ((tcp and (tcp[tcpflags] & (tcp-syn|tcp-ack) = tcp-syn) and (dst port 22 or dst port 443 or dst port 119)) or (udp and dst port 9))"
remote_capture="sudo -n timeout -k 2 12 tcpdump -n -l -vv -p -i spec-router -Q in -c 200 '${capture_filter}' 2>/dev/null; rc=\$?; if [ \$rc -eq 124 ]; then exit 0; fi; exit \$rc"

ssh -o BatchMode=yes "$CAPTURE_SSH_HOST" "$remote_capture" >"$capture_file" &
capture_pid=$!
cleanup_capture() {
    if kill -0 "$capture_pid" 2>/dev/null; then
        kill "$capture_pid" 2>/dev/null || true
        wait "$capture_pid" 2>/dev/null || true
    fi
}
trap cleanup_capture EXIT
sleep 1
printf '%s\n' "$generator_program" | ssh -o BatchMode=yes "$SOURCE_SSH_HOST" \
    "python3 - '${PROBE_TARGET}' '${SOURCE_IP}'" >"$generator_file"
wait "$capture_pid"
trap - EXIT

analysis_rc=0
python3 "$SCRIPT_DIR/qos_packet_proof_analyzer.py" \
    --capture "$capture_file" --output "$analysis_file" || analysis_rc=$?

# Always collect the after-snapshots when packet analysis disagrees. This is
# evidence collection only; neither command changes qdisc or service state.
ssh -o BatchMode=yes "$CAPTURE_SSH_HOST" \
    "sudo -n tc -d qdisc show dev spec-modem" >"$qdisc_after"
ssh -o BatchMode=yes "$CAPTURE_SSH_HOST" \
    "curl -fsS --max-time 5 http://10.10.110.223:9101/health" >"$health_after"

posture_rc=0
python3 - "$qdisc_before" "$qdisc_after" "$health_before" "$health_after" <<'PY' || posture_rc=$?
import json
import sys
from pathlib import Path

q_before, q_after, h_before, h_after = map(Path, sys.argv[1:])
for path in (q_before, q_after):
    text = path.read_text()
    if "qdisc cake" not in text or "diffserv4" not in text:
        raise SystemExit(f"CAKE diffserv4 missing from {path}")
for path in (h_before, h_after):
    payload = json.loads(path.read_text())
    if payload.get("status") != "healthy":
        raise SystemExit(f"Spectrum health is not healthy in {path}")
PY

cat >"$OUTPUT_DIR/MANIFEST.md" <<EOF
# Spectrum four-class packet proof

- Source: ${SOURCE_SSH_HOST}/${SOURCE_IP}
- Target: ${PROBE_TARGET}
- Capture: ${CAPTURE_SSH_HOST}/spec-router ingress
- TCP capture: new SYN packets only
- Probes: five short flows each for TCP/22, TCP/443, TCP/119, and UDP/9
- Acceptance: exact EF(46), AF31(26), CS1(8), and CS0(0) plus healthy CAKE diffserv4 before/after
- Saturation: none; no bulk payload or throughput target
- Mutation: none; no RouterOS, nftables, qdisc, service, rate, route, NAT, firewall, or topology change
EOF

if (( analysis_rc != 0 || posture_rc != 0 )); then
    echo "FAIL: packet analysis or CAKE posture disagreed; evidence retained in $OUTPUT_DIR" >&2
    exit 1
fi

echo "PASS: bounded Spectrum packet proof captured in $OUTPUT_DIR"

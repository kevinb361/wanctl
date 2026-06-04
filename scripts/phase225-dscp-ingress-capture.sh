#!/usr/bin/env bash
#
# Phase 225 DSCP ingress capture wrapper.
#
# Read-only evidence capture for Spectrum CAKE enqueue interfaces. The wrapper
# uses bounded tcpdump windows over SSH, histograms the captured DSCP byte
# offline, and records proof fields that keep unproven capture points unknown.

set -euo pipefail

SSH_HOST="cake-shaper"
OUTPUT_DIR=""
DURATION="90"
PROBE="none"
PROBE_TARGET=""
PROBE_PROTO="udp"
PROBE_PORT="5201"
MIN_PACKETS="2000"
MIN_ACTIVE_SECONDS="30"
PACKET_CAP="250000"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase225-dscp-ingress-capture.sh --output-dir <dir> [options]

Required:
  --output-dir DIR         Evidence directory to create/write

Options:
  --ssh-host HOST          SSH host for cake-shaper reads (default: cake-shaper)
  --duration SECONDS       Capture/probe window length (default: 90)
  --probe none|ul|dl|both  Optional low-rate EF probe (default: none)
  --probe-target HOST      Required when --probe is not none
  --probe-proto udp|tcp    Probe protocol descriptor (default: udp)
  --probe-port PORT        Probe port / 5-tuple field (default: 5201)
  --min-packets N          Organic window packet floor (default: 2000)
  --min-active-seconds N   Organic window active-second floor (default: 30)
  --packet-cap N           tcpdump packet cap per window (default: 250000)
  --help, -h               Show this help

Posture: read-only capture only. No gear config, queue mode, ruleset, or
persistent classifier state is changed. Probe traffic is bounded and opt-in.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

write_pcap_analyzer() {
    local path="$1"
    cat >"$path" <<'PY'
#!/usr/bin/env python3
import argparse
import collections
import os
import struct
import sys


def pcap_reader(path):
    with open(path, "rb") as fh:
        header = fh.read(24)
        if len(header) < 24:
            return
        magic = header[:4]
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            endian = "<"
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            endian = ">"
        else:
            raise SystemExit(f"unsupported capture format (expected classic pcap): {path}")
        _magic, _vmaj, _vmin, _zone, _sig, _snap, linktype = struct.unpack(endian + "IHHIIII", header)
        while True:
            rec = fh.read(16)
            if len(rec) == 0:
                break
            if len(rec) < 16:
                raise SystemExit(f"truncated pcap record header: {path}")
            ts_sec, ts_usec, incl_len, _orig_len = struct.unpack(endian + "IIII", rec)
            payload = fh.read(incl_len)
            if len(payload) < incl_len:
                raise SystemExit(f"truncated pcap packet: {path}")
            yield linktype, ts_sec, ts_usec, payload


def parse_ip_packet(linktype, frame):
    if linktype == 1:  # Ethernet
        if len(frame) < 14:
            return None
        offset = 14
        ethertype = int.from_bytes(frame[12:14], "big")
        while ethertype in (0x8100, 0x88A8, 0x9100):
            if len(frame) < offset + 4:
                return None
            ethertype = int.from_bytes(frame[offset + 2:offset + 4], "big")
            offset += 4
    elif linktype == 113:  # Linux cooked v1
        if len(frame) < 16:
            return None
        offset = 16
        ethertype = int.from_bytes(frame[14:16], "big")
    elif linktype == 276:  # Linux cooked v2
        if len(frame) < 20:
            return None
        offset = 20
        ethertype = int.from_bytes(frame[0:2], "big")
    elif linktype in (101, 228):  # raw IPv4/IPv6-ish
        offset = 0
        version = frame[0] >> 4 if frame else 0
        ethertype = 0x0800 if version == 4 else 0x86DD if version == 6 else 0
    else:
        return None

    if ethertype == 0x0800:
        if len(frame) < offset + 20:
            return None
        tos = frame[offset + 1]
        ihl = (frame[offset] & 0x0F) * 4
        if ihl < 20 or len(frame) < offset + ihl:
            return None
        total_len = int.from_bytes(frame[offset + 2:offset + 4], "big") or max(0, len(frame) - offset)
        proto = frame[offset + 9]
        src = ".".join(str(b) for b in frame[offset + 12:offset + 16])
        dst = ".".join(str(b) for b in frame[offset + 16:offset + 20])
        ports = (None, None)
        if proto in (6, 17) and len(frame) >= offset + ihl + 4:
            ports = (
                int.from_bytes(frame[offset + ihl:offset + ihl + 2], "big"),
                int.from_bytes(frame[offset + ihl + 2:offset + ihl + 4], "big"),
            )
        return {"dscp": tos >> 2, "bytes": total_len, "proto": proto, "src": src, "dst": dst, "ports": ports}

    if ethertype == 0x86DD:
        if len(frame) < offset + 40:
            return None
        first_word = int.from_bytes(frame[offset:offset + 4], "big")
        traffic_class = (first_word >> 20) & 0xFF
        payload_len = int.from_bytes(frame[offset + 4:offset + 6], "big")
        next_header = frame[offset + 6]
        src = ":".join(f"{int.from_bytes(frame[offset + 8 + i:offset + 10 + i], 'big'):x}" for i in range(0, 16, 2))
        dst = ":".join(f"{int.from_bytes(frame[offset + 24 + i:offset + 26 + i], 'big'):x}" for i in range(0, 16, 2))
        ports = (None, None)
        l4 = offset + 40
        if next_header in (6, 17) and len(frame) >= l4 + 4:
            ports = (int.from_bytes(frame[l4:l4 + 2], "big"), int.from_bytes(frame[l4 + 2:l4 + 4], "big"))
        return {"dscp": traffic_class >> 2, "bytes": payload_len + 40, "proto": next_header, "src": src, "dst": dst, "ports": ports}

    return None


def summarize(path):
    hist = collections.Counter()
    byte_hist = collections.Counter()
    active = set()
    tuples = collections.Counter()
    total = 0
    total_bytes = 0
    for linktype, ts_sec, _ts_usec, frame in pcap_reader(path):
        parsed = parse_ip_packet(linktype, frame)
        if parsed is None:
            continue
        total += 1
        total_bytes += parsed["bytes"]
        active.add(ts_sec)
        dscp = parsed["dscp"]
        hist[dscp] += 1
        byte_hist[dscp] += parsed["bytes"]
        src_port, dst_port = parsed["ports"]
        if src_port is not None and dst_port is not None:
            tuples[(parsed["proto"], parsed["src"], src_port, parsed["dst"], dst_port)] += 1
    return hist, byte_hist, total, total_bytes, len(active), tuples


def write_histogram(args):
    hist, byte_hist, total, total_bytes, active_seconds, _tuples = summarize(args.pcap)
    nonbe_packets = sum(count for dscp, count in hist.items() if dscp != 0)
    nonbe_bytes = sum(count for dscp, count in byte_hist.items() if dscp != 0)
    pkt_pct = (nonbe_packets / total * 100.0) if total else 0.0
    byte_pct = (nonbe_bytes / total_bytes * 100.0) if total_bytes else 0.0
    valid = total >= args.min_packets and active_seconds >= args.min_active_seconds
    with open(args.output, "w") as out:
        out.write(f"CHANNEL={args.channel}\n")
        out.write(f"TOTAL_IP_PACKETS={total}\n")
        out.write(f"TOTAL_IP_BYTES={total_bytes}\n")
        out.write(f"ACTIVE_SECONDS={active_seconds}\n")
        out.write(f"NONBE_PKT_PCT={pkt_pct:.3f}\n")
        out.write(f"NONBE_BYTE_PCT={byte_pct:.3f}\n")
        out.write(f"WINDOW_VALID={str(valid).lower()}\n")
        out.write("DSCP PACKETS BYTES PACKET_PCT BYTE_PCT\n")
        for dscp in sorted(hist):
            packet_pct = (hist[dscp] / total * 100.0) if total else 0.0
            bytes_pct = (byte_hist[dscp] / total_bytes * 100.0) if total_bytes else 0.0
            out.write(f"DSCP_{dscp} {hist[dscp]} {byte_hist[dscp]} {packet_pct:.3f} {bytes_pct:.3f}\n")
    return total, total_bytes, active_seconds, pkt_pct, byte_pct, valid


def probe_summary(args):
    hist, _byte_hist, total, _total_bytes, _active, tuples = summarize(args.pcap)
    src_total = 0
    src_ef = 0
    src_match = False
    source_exists = bool(args.source_pcap and os.path.exists(args.source_pcap))
    if source_exists:
        src_hist, _src_bytes, src_total, _src_total_bytes, _src_active, src_tuples = summarize(args.source_pcap)
        src_ef = src_hist.get(46, 0)
        if tuples and src_tuples:
            src_match = bool(set(tuples) & set(src_tuples))
    ef = hist.get(46, 0)
    survival_pct = (ef / total * 100.0) if total else 0.0
    src_ef_pct = (src_ef / src_total * 100.0) if src_total else 0.0
    source_proven = source_exists and src_total >= 100 and src_ef_pct >= 90.0 and src_match
    if total < 100:
        survived = "degraded"
    elif args.direction == "dl" and not source_proven:
        survived = "degraded"
    elif survival_pct >= 90.0:
        survived = "true"
    elif survival_pct < 10.0:
        survived = "false"
    else:
        survived = "degraded"
    top_tuple = "unknown"
    if tuples:
        proto, src, sport, dst, dport = tuples.most_common(1)[0][0]
        proto_name = {6: "tcp", 17: "udp"}.get(proto, str(proto))
        top_tuple = f"{proto_name} {src}:{sport}->{dst}:{dport}"
    with open(args.output, "w") as out:
        out.write(f"CHANNEL={args.direction}_ef_probe\n")
        out.write(f"PROBE_5TUPLE={top_tuple}\n")
        out.write(f"PROBE_PROTO={args.probe_proto}\n")
        out.write(f"PROBE_PORT={args.probe_port}\n")
        out.write(f"PROBE_PKTS_SENT={args.probe_packets_sent}\n")
        out.write(f"PROBE_PKTS_CAPTURED={total}\n")
        out.write(f"EF_PKTS_AT_ENQUEUE={ef}\n")
        out.write(f"EF_SURVIVAL_PCT={survival_pct:.3f}\n")
        if args.direction == "dl":
            out.write(f"SRC_PROBE_PKTS_TOTAL={src_total}\n")
            out.write(f"SRC_EF_PKTS={src_ef}\n")
            out.write(f"EF_PKTS_AT_SOURCE={src_ef}\n")
            out.write(f"SRC_EF_PCT={src_ef_pct:.3f}\n")
            out.write(f"SRC_CAPTURE_POINT={args.source_capture_point}\n")
            out.write(f"SRC_ENQUEUE_5TUPLE_MATCH={str(src_match).lower()}\n")
            out.write(f"DL_SOURCE_EF_PROVEN={str(source_proven).lower()}\n")
        out.write(f"EF_SURVIVED={survived}\n")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    hist = sub.add_parser("histogram")
    hist.add_argument("--pcap", required=True)
    hist.add_argument("--output", required=True)
    hist.add_argument("--channel", required=True)
    hist.add_argument("--min-packets", type=int, required=True)
    hist.add_argument("--min-active-seconds", type=int, required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--pcap", required=True)
    probe.add_argument("--output", required=True)
    probe.add_argument("--direction", choices=("dl", "ul"), required=True)
    probe.add_argument("--source-pcap", default="")
    probe.add_argument("--source-capture-point", default="unavailable")
    probe.add_argument("--probe-proto", required=True)
    probe.add_argument("--probe-port", required=True)
    probe.add_argument("--probe-packets-sent", default="unknown")
    args = parser.parse_args()
    if args.cmd == "histogram":
        write_histogram(args)
    elif args.cmd == "probe":
        probe_summary(args)


if __name__ == "__main__":
    main()
PY
    chmod +x "$path"
}

run_ssh_capture() {
    local iface="$1"
    local direction_flag="$2"
    local filter_expr="$3"
    local output="$4"
    local rc=0
    local remote_cmd

    remote_cmd="sudo -n timeout -k 5 ${DURATION} tcpdump -n -p -i ${iface} ${direction_flag} -c ${PACKET_CAP} -w - '${filter_expr}'"
    set +e
    ssh -o BatchMode=yes "$SSH_HOST" "$remote_cmd" >"$output"
    rc=$?
    set -e
    if [[ "$rc" -ne 0 && "$rc" -ne 124 ]]; then
        echo "ERROR: tcpdump capture failed on ${iface} (${direction_flag:-no-direction}) with exit ${rc}" >&2
        exit "$rc"
    fi
}

capture_probe_window() {
    local iface="$1"
    local direction_flag="$2"
    local output="$3"
    local probe_cmd=""
    local rc=0
    local proto_filter="$PROBE_PROTO"

    if [[ "$PROBE_PROTO" == "udp" ]]; then
        probe_cmd="if command -v iperf3 >/dev/null 2>&1; then iperf3 -u -b 1M --tos 0xb8 -c '${PROBE_TARGET}' -p '${PROBE_PORT}' -t '${DURATION}' >/dev/null 2>&1 || true; elif command -v nping >/dev/null 2>&1; then nping --udp --tos 0xb8 --rate 50 -c 200 --dest-port '${PROBE_PORT}' '${PROBE_TARGET}' >/dev/null 2>&1 || true; else ping -Q 0xb8 -c 20 '${PROBE_TARGET}' >/dev/null 2>&1 || true; fi"
    else
        probe_cmd="if command -v nping >/dev/null 2>&1; then nping --tcp --tos 0xb8 --rate 20 -c 200 --dest-port '${PROBE_PORT}' '${PROBE_TARGET}' >/dev/null 2>&1 || true; else ping -Q 0xb8 -c 20 '${PROBE_TARGET}' >/dev/null 2>&1 || true; fi"
        proto_filter="tcp"
    fi

    set +e
    ssh -o BatchMode=yes "$SSH_HOST" "sudo -n timeout -k 5 ${DURATION} tcpdump -n -p -i ${iface} ${direction_flag} -c ${PACKET_CAP} -w - '${proto_filter} and host ${PROBE_TARGET} and port ${PROBE_PORT}' & cap_pid=\$!; sleep 1; ${probe_cmd}; wait \$cap_pid; rc=\$?; if [ \$rc -eq 124 ]; then exit 0; fi; exit \$rc" >"$output"
    rc=$?
    set -e
    if [[ "$rc" -ne 0 && "$rc" -ne 124 ]]; then
        echo "ERROR: probe capture failed on ${iface} (${direction_flag:-no-direction}) with exit ${rc}" >&2
        exit "$rc"
    fi
}

derive_topology_and_proof() {
    local proof_file="$1"
    local topology_ok="false"
    local dl_pass="false"
    local ul_pass="false"
    local dl_capture_point="unknown"
    local ul_capture_point="unknown"
    local dl_wash_handle="unknown"
    local ul_wash_handle="unknown"
    local dl_hook="bridge_forward:iif=spec-modem,oif=spec-router,parent=pre-egress"
    local ul_hook="bridge_forward:iif=spec-router,oif=spec-modem,parent=pre-egress"

    if grep -Eq 'iif[[:space:]]+spec-modem[[:space:]]+oif[[:space:]]+spec-router' "$OUTPUT_DIR/topology/nft-bridge-qos.txt"; then
        topology_ok="true"
    fi
    dl_wash_handle="$(awk '/cake/ {print $3; exit}' "$OUTPUT_DIR/topology/tc-qdisc-spec-router.txt" 2>/dev/null || true)"
    ul_wash_handle="$(awk '/cake/ {print $3; exit}' "$OUTPUT_DIR/topology/tc-qdisc-spec-modem.txt" 2>/dev/null || true)"
    if [[ "$topology_ok" == "true" && -n "$dl_wash_handle" && "$dl_wash_handle" != "unknown" ]]; then
        dl_pass="true"
        dl_capture_point="pre_wash_ingress"
    fi
    if [[ -n "$ul_wash_handle" && "$ul_wash_handle" != "unknown" ]]; then
        ul_pass="true"
        ul_capture_point="pre_wash_ingress"
    fi

    {
        printf 'WASH_PROOF_METHOD=qdisc_ordering\n'
        printf 'TOPOLOGY_EVIDENCE=ip-d-link,bridge-link,nft-bridge-qos,tc-qdisc\n'
        printf 'DL_CAPTURE_INTERFACE=spec-router\n'
        printf 'DL_CAPTURE_DIRECTION_FLAG=%s\n' "$DL_DIRECTION_FLAG"
        printf 'DL_HOOK_PARENT=%s\n' "$dl_hook"
        printf 'DL_WASH_QDISC_HANDLE=%s\n' "${dl_wash_handle:-unknown}"
        printf 'DL_WASH_PROOF_PASS=%s\n' "$dl_pass"
        printf 'DL_CAPTURE_POINT=%s\n' "$dl_capture_point"
        printf 'DL_WASH_ORDERING_PROVEN=%s\n' "$dl_pass"
        printf 'UL_CAPTURE_INTERFACE=spec-modem\n'
        printf 'UL_CAPTURE_DIRECTION_FLAG=%s\n' "$UL_DIRECTION_FLAG"
        printf 'UL_HOOK_PARENT=%s\n' "$ul_hook"
        printf 'UL_WASH_QDISC_HANDLE=%s\n' "${ul_wash_handle:-unknown}"
        printf 'UL_WASH_PROOF_PASS=%s\n' "$ul_pass"
        printf 'UL_CAPTURE_POINT=%s\n' "$ul_capture_point"
        printf 'UL_WASH_ORDERING_PROVEN=%s\n' "$ul_pass"
        printf 'WASH_PROOF_PASS=%s\n' "$dl_pass"
        printf 'HOOK_PARENT=%s\n' "$dl_hook"
        printf 'WASH_QDISC_HANDLE=%s\n' "${dl_wash_handle:-unknown}"
        printf 'CAPTURE_POINT=%s\n' "$dl_capture_point"
        printf 'WASH_ORDERING_PROVEN=%s\n' "$dl_pass"
        printf 'PROOF_NOTE=Pass requires a parsed bridge-forward hook for spec-modem-to-spec-router and a parsed CAKE egress qdisc handle; otherwise capture point remains unknown.\n'
    } >"$proof_file"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --duration) DURATION="${2:-}"; shift 2 ;;
        --probe) PROBE="${2:-}"; shift 2 ;;
        --probe-target) PROBE_TARGET="${2:-}"; shift 2 ;;
        --probe-proto) PROBE_PROTO="${2:-}"; shift 2 ;;
        --probe-port) PROBE_PORT="${2:-}"; shift 2 ;;
        --min-packets) MIN_PACKETS="${2:-}"; shift 2 ;;
        --min-active-seconds) MIN_ACTIVE_SECONDS="${2:-}"; shift 2 ;;
        --packet-cap) PACKET_CAP="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    usage >&2
    exit 2
fi
case "$PROBE" in none|ul|dl|both) ;; *) echo "ERROR: --probe must be one of none, ul, dl, both" >&2; exit 2 ;; esac
case "$PROBE_PROTO" in udp|tcp) ;; *) echo "ERROR: --probe-proto must be udp or tcp" >&2; exit 2 ;; esac
if [[ "$PROBE" != "none" && -z "$PROBE_TARGET" ]]; then
    echo "ERROR: --probe-target is required whenever --probe is not none" >&2
    exit 2
fi

# Injection-safety validation gate (GAP-1 / CR-01).
# Every operator-supplied value that is interpolated into a remote SSH command
# string is allowlist/range-validated HERE — before derive_topology_and_proof,
# run_ssh_capture, or capture_probe_window build any remote command. An unsafe
# value (e.g. shell metacharacters) is rejected with exit 2 and NO SSH runs.
# This gate textually precedes the first ssh invocation in the script.
if [[ -n "$PROBE_TARGET" && ! "$PROBE_TARGET" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo "ERROR: --probe-target contains unsupported characters (allowed: A-Za-z0-9 . : _ -)" >&2
    exit 2
fi
if [[ "$PROBE" != "none" ]]; then
    if [[ ! "$PROBE_PORT" =~ ^[0-9]+$ ]] || (( PROBE_PORT < 1 || PROBE_PORT > 65535 )); then
        echo "ERROR: --probe-port must be an integer from 1 to 65535" >&2
        exit 2
    fi
fi
# SSH host token is interpolated into the ssh target and remote command context.
if [[ -z "$SSH_HOST" || ! "$SSH_HOST" =~ ^[A-Za-z0-9_.:@-]+$ ]]; then
    echo "ERROR: --ssh-host contains unsupported characters (allowed: A-Za-z0-9 . : _ @ -)" >&2
    exit 2
fi
# Numeric values interpolated into remote tcpdump command strings.
if [[ ! "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION < 1 )); then
    echo "ERROR: --duration must be a positive integer (seconds)" >&2
    exit 2
fi
if [[ ! "$PACKET_CAP" =~ ^[0-9]+$ ]] || (( PACKET_CAP < 1 )); then
    echo "ERROR: --packet-cap must be a positive integer" >&2
    exit 2
fi
if [[ ! "$MIN_PACKETS" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --min-packets must be a non-negative integer" >&2
    exit 2
fi
if [[ ! "$MIN_ACTIVE_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --min-active-seconds must be a non-negative integer" >&2
    exit 2
fi

require_command awk
require_command date
require_command grep
require_command mkdir
require_command python3
require_command sha256sum
require_command ssh

if [[ -d "$OUTPUT_DIR" && -n "$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: --output-dir already exists and is non-empty: $OUTPUT_DIR" >&2
    exit 1
fi
mkdir -p "$OUTPUT_DIR/raw" "$OUTPUT_DIR/topology"

ANALYZER="$OUTPUT_DIR/dscp_pcap_analyzer.py"
write_pcap_analyzer "$ANALYZER"
captured_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ssh -o BatchMode=yes "$SSH_HOST" "ip -d link show" >"$OUTPUT_DIR/topology/ip-d-link-show.txt"
ssh -o BatchMode=yes "$SSH_HOST" "bridge link show 2>/dev/null || true" >"$OUTPUT_DIR/topology/bridge-link-show.txt"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n nft list table bridge qos 2>/dev/null || true" >"$OUTPUT_DIR/topology/nft-bridge-qos.txt"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n tc -d qdisc show dev spec-router 2>/dev/null || true" >"$OUTPUT_DIR/topology/tc-qdisc-spec-router.txt"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n tc -d qdisc show dev spec-modem 2>/dev/null || true" >"$OUTPUT_DIR/topology/tc-qdisc-spec-modem.txt"

DL_DIRECTION_FLAG="-Q out"
UL_DIRECTION_FLAG="-Q out"
if ! grep -Eq 'iif[[:space:]]+spec-modem[[:space:]]+oif[[:space:]]+spec-router' "$OUTPUT_DIR/topology/nft-bridge-qos.txt"; then
    DL_DIRECTION_FLAG=""
fi

derive_topology_and_proof "$OUTPUT_DIR/capture-point-proof.txt"

run_ssh_capture "spec-router" "$DL_DIRECTION_FLAG" "ip or ip6" "$OUTPUT_DIR/raw/organic-dl-spec-router.pcap"
run_ssh_capture "spec-modem" "$UL_DIRECTION_FLAG" "ip or ip6" "$OUTPUT_DIR/raw/organic-ul-spec-modem.pcap"

python3 "$ANALYZER" histogram --pcap "$OUTPUT_DIR/raw/organic-dl-spec-router.pcap" --output "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt" --channel organic_dl_histogram --min-packets "$MIN_PACKETS" --min-active-seconds "$MIN_ACTIVE_SECONDS"
python3 "$ANALYZER" histogram --pcap "$OUTPUT_DIR/raw/organic-ul-spec-modem.pcap" --output "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt" --channel organic_ul_histogram --min-packets "$MIN_PACKETS" --min-active-seconds "$MIN_ACTIVE_SECONDS"

dl_total="$(awk -F= '/^TOTAL_IP_PACKETS=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
dl_bytes="$(awk -F= '/^TOTAL_IP_BYTES=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
dl_active="$(awk -F= '/^ACTIVE_SECONDS=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
dl_pkt_pct="$(awk -F= '/^NONBE_PKT_PCT=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
dl_byte_pct="$(awk -F= '/^NONBE_BYTE_PCT=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
dl_valid="$(awk -F= '/^WINDOW_VALID=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt")"
ul_total="$(awk -F= '/^TOTAL_IP_PACKETS=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"
ul_bytes="$(awk -F= '/^TOTAL_IP_BYTES=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"
ul_active="$(awk -F= '/^ACTIVE_SECONDS=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"
ul_pkt_pct="$(awk -F= '/^NONBE_PKT_PCT=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"
ul_byte_pct="$(awk -F= '/^NONBE_BYTE_PCT=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"
ul_valid="$(awk -F= '/^WINDOW_VALID=/{print $2}' "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt")"

{
    printf 'MIN_PACKETS=%s\n' "$MIN_PACKETS"
    printf 'MIN_ACTIVE_SECONDS=%s\n' "$MIN_ACTIVE_SECONDS"
    printf 'DL_TOTAL_IP_PACKETS=%s\n' "$dl_total"
    printf 'DL_TOTAL_IP_BYTES=%s\n' "$dl_bytes"
    printf 'DL_ACTIVE_SECONDS=%s\n' "$dl_active"
    printf 'DL_NONBE_PKT_PCT=%s\n' "$dl_pkt_pct"
    printf 'DL_NONBE_BYTE_PCT=%s\n' "$dl_byte_pct"
    printf 'WINDOW_VALID_DL=%s\n' "$dl_valid"
    printf 'UL_TOTAL_IP_PACKETS=%s\n' "$ul_total"
    printf 'UL_TOTAL_IP_BYTES=%s\n' "$ul_bytes"
    printf 'UL_ACTIVE_SECONDS=%s\n' "$ul_active"
    printf 'UL_NONBE_PKT_PCT=%s\n' "$ul_pkt_pct"
    printf 'UL_NONBE_BYTE_PCT=%s\n' "$ul_byte_pct"
    printf 'WINDOW_VALID_UL=%s\n' "$ul_valid"
    printf 'NONBE_PKT_PCT_DL=%s\n' "$dl_pkt_pct"
    printf 'NONBE_BYTE_PCT_DL=%s\n' "$dl_byte_pct"
    printf 'NONBE_PKT_PCT_UL=%s\n' "$ul_pkt_pct"
    printf 'NONBE_BYTE_PCT_UL=%s\n' "$ul_byte_pct"
} >"$OUTPUT_DIR/sample-quality.txt"

if [[ "$PROBE" == "ul" || "$PROBE" == "both" ]]; then
    capture_probe_window "spec-modem" "$UL_DIRECTION_FLAG" "$OUTPUT_DIR/raw/ul-ef-probe.pcap"
    python3 "$ANALYZER" probe --pcap "$OUTPUT_DIR/raw/ul-ef-probe.pcap" --output "$OUTPUT_DIR/ul-ef-probe-result.txt" --direction ul --probe-proto "$PROBE_PROTO" --probe-port "$PROBE_PORT" --probe-packets-sent unknown
else
    : >"$OUTPUT_DIR/raw/ul-ef-probe.pcap"
    {
        printf 'CHANNEL=ul_ef_probe\nPROBE_5TUPLE=not_requested\nPROBE_PROTO=%s\nPROBE_PORT=%s\n' "$PROBE_PROTO" "$PROBE_PORT"
        printf 'PROBE_PKTS_SENT=0\nPROBE_PKTS_CAPTURED=0\nEF_PKTS_AT_ENQUEUE=0\nEF_SURVIVAL_PCT=0.000\nEF_SURVIVED=degraded\n'
    } >"$OUTPUT_DIR/ul-ef-probe-result.txt"
fi

if [[ "$PROBE" == "dl" || "$PROBE" == "both" ]]; then
    capture_probe_window "spec-router" "$DL_DIRECTION_FLAG" "$OUTPUT_DIR/raw/dl-ef-probe.pcap"
    : >"$OUTPUT_DIR/raw/dl-ef-probe-source.pcap"
    python3 "$ANALYZER" probe --pcap "$OUTPUT_DIR/raw/dl-ef-probe.pcap" --output "$OUTPUT_DIR/dl-ef-probe-result.txt" --direction dl --source-pcap "$OUTPUT_DIR/raw/dl-ef-probe-source.pcap" --source-capture-point unavailable --probe-proto "$PROBE_PROTO" --probe-port "$PROBE_PORT" --probe-packets-sent unknown
else
    : >"$OUTPUT_DIR/raw/dl-ef-probe.pcap"
    : >"$OUTPUT_DIR/raw/dl-ef-probe-source.pcap"
    {
        printf 'CHANNEL=dl_ef_probe\nPROBE_5TUPLE=not_requested\nPROBE_PROTO=%s\nPROBE_PORT=%s\n' "$PROBE_PROTO" "$PROBE_PORT"
        printf 'PROBE_PKTS_SENT=0\nPROBE_PKTS_CAPTURED=0\nEF_PKTS_AT_ENQUEUE=0\nEF_SURVIVAL_PCT=0.000\n'
        printf 'SRC_PROBE_PKTS_TOTAL=0\nSRC_EF_PKTS=0\nEF_PKTS_AT_SOURCE=0\nSRC_EF_PCT=0.000\nSRC_CAPTURE_POINT=unavailable\nSRC_ENQUEUE_5TUPLE_MATCH=false\nDL_SOURCE_EF_PROVEN=false\nEF_SURVIVED=degraded\n'
    } >"$OUTPUT_DIR/dl-ef-probe-result.txt"
fi

manifest="$OUTPUT_DIR/MANIFEST.md"
{
    printf '# DSCP Ingress Capture Manifest\n\n'
    printf '## Captured\n\n'
    printf -- '- Captured: %s\n' "$captured_at"
    printf -- '- SSH host: %s\n' "$SSH_HOST"
    printf -- '- Duration: %s seconds\n' "$DURATION"
    printf -- '- Packet cap: %s packets per capture\n' "$PACKET_CAP"
    printf -- '- Probe mode: %s\n' "$PROBE"
    printf -- '- Probe target: %s\n' "${PROBE_TARGET:-not_requested}"
    printf -- '- Probe proto/port: %s/%s\n\n' "$PROBE_PROTO" "$PROBE_PORT"
    printf '## Source Posture\n\n'
    printf 'Read-only: bounded tcpdump over SSH plus optional bounded low-rate EF probe. No external gear configuration, queue mode, ruleset, or persistent classifier state was changed.\n\n'
    printf '## Capture Point\n\n'
    printf 'See capture-point-proof.txt. CAPTURE_POINT defaults to unknown unless WASH_PROOF_PASS is true.\n\n'
    printf '## Artifacts\n\n'
    printf -- '- capture-point-proof.txt\n'
    printf -- '- sample-quality.txt\n'
    printf -- '- dscp-histogram-spec-router-dl.txt\n'
    printf -- '- dscp-histogram-spec-modem-ul.txt\n'
    printf -- '- dl-ef-probe-result.txt\n'
    printf -- '- ul-ef-probe-result.txt\n'
    printf -- '- raw/organic-dl-spec-router.pcap\n'
    printf -- '- raw/organic-ul-spec-modem.pcap\n'
    printf -- '- raw/dl-ef-probe.pcap\n'
    printf -- '- raw/dl-ef-probe-source.pcap\n'
    printf -- '- raw/ul-ef-probe.pcap\n'
    printf -- '- topology/ip-d-link-show.txt\n'
    printf -- '- topology/bridge-link-show.txt\n'
    printf -- '- topology/nft-bridge-qos.txt\n'
    printf -- '- topology/tc-qdisc-spec-router.txt\n'
    printf -- '- topology/tc-qdisc-spec-modem.txt\n\n'
    printf '## SHA256\n\n'
    find "$OUTPUT_DIR" -type f ! -name 'MANIFEST.md' -print0 | sort -z | while IFS= read -r -d '' file; do
        sha256sum "$file" | sed "s# $OUTPUT_DIR/# #"
    done
} >"$manifest"

for required in \
    "$OUTPUT_DIR/capture-point-proof.txt" \
    "$OUTPUT_DIR/sample-quality.txt" \
    "$OUTPUT_DIR/dscp-histogram-spec-router-dl.txt" \
    "$OUTPUT_DIR/dscp-histogram-spec-modem-ul.txt" \
    "$OUTPUT_DIR/dl-ef-probe-result.txt" \
    "$OUTPUT_DIR/ul-ef-probe-result.txt" \
    "$OUTPUT_DIR/raw/organic-dl-spec-router.pcap" \
    "$OUTPUT_DIR/raw/organic-ul-spec-modem.pcap" \
    "$OUTPUT_DIR/raw/dl-ef-probe.pcap" \
    "$OUTPUT_DIR/raw/dl-ef-probe-source.pcap" \
    "$OUTPUT_DIR/raw/ul-ef-probe.pcap" \
    "$manifest"; do
    if [[ ! -e "$required" ]]; then
        echo "ERROR: required artifact missing: $required" >&2
        exit 1
    fi
done

echo "DSCP ingress capture evidence written: $OUTPUT_DIR"

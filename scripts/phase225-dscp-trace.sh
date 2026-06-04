#!/usr/bin/env bash
#
# Phase 225 DSCP trace capture wrapper.
#
# Captures read-only bridge / CAKE-interface evidence from cake-shaper into a
# committable output directory. The wrapper does not mutate nftables, tc, CAKE
# mode, controller source, or external network gear.

set -euo pipefail

SSH_HOST="cake-shaper"
OUTPUT_DIR=""
COUNTER_WINDOW="60"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase225-dscp-trace.sh --output-dir <dir> [options]

Options:
  --output-dir DIR       DSCP trace evidence directory to create/write (required)
  --ssh-host HOST        SSH host for read-only captures (default: cake-shaper)
  --counter-window SEC   Seconds between bridge-qos counter snapshots (default: 60)
  --help, -h             Show this help

Output:
  Read-only bridge QoS, CAKE qdisc/filter, interface topology, counter-availability,
  and MANIFEST.md artifacts under --output-dir.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

dir_has_entries() {
    local dir="$1"
    shopt -s nullglob dotglob
    local entries=("$dir"/*)
    shopt -u nullglob dotglob
    [[ ${#entries[@]} -gt 0 ]]
}

ssh_read() {
    local remote_cmd="$1"
    ssh -o BatchMode=yes "$SSH_HOST" "sudo -n $remote_cmd"
}

capture_tc_filter() {
    local dev="$1"
    local dst="$2"

    {
        printf '# tc filter show dev %s\n' "$dev"
        ssh -o BatchMode=yes "$SSH_HOST" "sudo -n tc filter show dev '$dev'" || true
        printf '\n# tc filter show dev %s root\n' "$dev"
        ssh -o BatchMode=yes "$SSH_HOST" \
            "sudo -n sh -c 'tc filter show dev \"$dev\" root 2>&1 || true'" || true
        printf '\n# tc filter show dev %s ingress\n' "$dev"
        ssh -o BatchMode=yes "$SSH_HOST" \
            "sudo -n sh -c 'tc filter show dev \"$dev\" ingress 2>&1 || true'" || true
    } >"$dst"

    python3 - "$dst" "$dev" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
dev = sys.argv[2]
text = path.read_text()
lines = text.splitlines()
out = []
section = None
seen = {"root": False, "ingress": False}
for line in lines:
    if line == f"# tc filter show dev {dev} root":
        section = "root"
        out.append(line)
        continue
    if line == f"# tc filter show dev {dev} ingress":
        if section in seen and not seen[section]:
            out.append(f"# (unavailable: tc filter {section} hook for {dev})")
        section = "ingress"
        out.append(line)
        continue
    if section in seen and line.strip():
        seen[section] = True
    out.append(line)
if section in seen and not seen[section]:
    out.append(f"# (unavailable: tc filter {section} hook for {dev})")
path.write_text("\n".join(out).rstrip() + "\n")
PY
}

write_bridge_mark_counters() {
    local before="$1"
    local after="$2"
    local dst="$3"
    python3 - "$before" "$after" "$dst" <<'PY'
import pathlib
import re
import sys

before_path, after_path, dst_path = map(pathlib.Path, sys.argv[1:4])

rule_re = re.compile(r"ip dscp set\s+(ef|af41|cs1)\b", re.I)
counter_re = re.compile(r"counter\s+packets\s+(\d+)\s+bytes\s+(\d+)", re.I)


def extract(path):
    rows = []
    if not path.exists() or path.stat().st_size == 0:
        return rows
    for line_no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        rule_match = rule_re.search(line)
        if not rule_match:
            continue
        counter_match = counter_re.search(line)
        rows.append(
            {
                "line": line_no,
                "dscp": rule_match.group(1).lower(),
                "packets": int(counter_match.group(1)) if counter_match else None,
                "bytes": int(counter_match.group(2)) if counter_match else None,
                "raw": line.strip(),
            }
        )
    return rows


before = extract(before_path)
after = extract(after_path)
countered_before = [row for row in before if row["packets"] is not None]
countered_after = [row for row in after if row["packets"] is not None]

if not countered_before:
    body = [
        "COUNTERS_AVAILABLE=false",
        "COUNTER_MODE=unavailable",
        "bridge_counter_signal=unknown",
        "",
        "No `counter packets <N> bytes <M>` clause was found on `ip dscp set ef|af41|cs1` rules in nft-bridge-qos-before.txt.",
        "Counter absence is recorded as unknown for the verdict, never negligible. No values were fabricated.",
        "",
        "## ip dscp set rules observed",
    ]
    if before:
        for row in before:
            body.append(f"- before:L{row['line']} {row['dscp']}: {row['raw']}")
    else:
        body.append("- none found")
    pathlib.Path(dst_path).write_text("\n".join(body).rstrip() + "\n")
    raise SystemExit(0)

if not countered_after:
    body = [
        "COUNTERS_AVAILABLE=true",
        "COUNTER_MODE=snapshot",
        "bridge_counter_signal=unknown",
        "",
        "Counters were present at T0 but a comparable T1 counter snapshot was unavailable; cumulative snapshot state is unknown for verdict purposes.",
        "",
        "## snapshot counters",
    ]
    for idx, row in enumerate(countered_before, 1):
        body.append(
            f"- rule_index={idx} dscp={row['dscp']} before_packets={row['packets']} before_bytes={row['bytes']} raw={row['raw']}"
        )
    pathlib.Path(dst_path).write_text("\n".join(body).rstrip() + "\n")
    raise SystemExit(0)

body = [
    "COUNTERS_AVAILABLE=true",
    "COUNTER_MODE=delta",
    "bridge_counter_signal=counter_delta_available",
    "",
    "## bounded counter delta",
]
for idx, before_row in enumerate(countered_before, 1):
    matching_after = countered_after[idx - 1] if idx - 1 < len(countered_after) else None
    if matching_after is None:
        body.append(
            f"- rule_index={idx} dscp={before_row['dscp']} before_packets={before_row['packets']} before_bytes={before_row['bytes']} after=missing delta=unknown"
        )
        continue
    pkt_delta = max(0, matching_after["packets"] - before_row["packets"])
    byte_delta = max(0, matching_after["bytes"] - before_row["bytes"])
    body.append(
        "- "
        f"rule_index={idx} dscp={before_row['dscp']} "
        f"before_packets={before_row['packets']} after_packets={matching_after['packets']} delta_packets={pkt_delta} "
        f"before_bytes={before_row['bytes']} after_bytes={matching_after['bytes']} delta_bytes={byte_delta}"
    )
pathlib.Path(dst_path).write_text("\n".join(body).rstrip() + "\n")
PY
}

write_manifest() {
    local manifest="$OUTPUT_DIR/MANIFEST.md"
    {
        printf '# DSCP Trace Manifest\n\n'
        printf '## Captured\n\n'
        printf -- '- Captured: %s\n' "$captured_ts"
        printf -- '- Source Posture: read-only; no external network gear mutation, no bridge qos reload, no CAKE mode change, no tc probe attachment.\n'
        printf -- '- SSH host: %s\n' "$SSH_HOST"
        printf -- '- Counter window: %s seconds\n\n' "$COUNTER_WINDOW"
        printf '## Artifacts\n\n'
        for artifact in \
            nft-bridge-qos-before.txt \
            nft-bridge-qos-after.txt \
            tc-qdisc-spec-router.txt \
            tc-qdisc-spec-modem.txt \
            tc-filter-spec-router.txt \
            tc-filter-spec-modem.txt \
            ip-link.txt \
            bridge-mark-counters.txt; do
            local artifact_path="$OUTPUT_DIR/$artifact"
            local digest
            digest="$(sha256sum "$artifact_path" | awk '{print $1}')"
            printf -- "- \`%s\` — sha256 \`%s\`\n" "$artifact" "$digest"
        done
    } >"$manifest"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="${2:-}"
            shift 2
            ;;
        --ssh-host)
            SSH_HOST="${2:-}"
            shift 2
            ;;
        --counter-window)
            COUNTER_WINDOW="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    usage >&2
    exit 2
fi
if [[ ! "$COUNTER_WINDOW" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --counter-window must be a non-negative integer number of seconds" >&2
    exit 2
fi

require_command ssh
require_command python3
require_command sha256sum
require_command awk

if [[ -d "$OUTPUT_DIR" ]] && dir_has_entries "$OUTPUT_DIR"; then
    echo "ERROR: --output-dir already exists and is non-empty: $OUTPUT_DIR" >&2
    exit 1
fi
mkdir -p "$OUTPUT_DIR"

captured_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ssh_read "nft list table bridge qos" >"$OUTPUT_DIR/nft-bridge-qos-before.txt"
sleep "$COUNTER_WINDOW"
ssh_read "nft list table bridge qos" >"$OUTPUT_DIR/nft-bridge-qos-after.txt"
ssh_read "tc -s qdisc show dev spec-router" >"$OUTPUT_DIR/tc-qdisc-spec-router.txt"
ssh_read "tc -s qdisc show dev spec-modem" >"$OUTPUT_DIR/tc-qdisc-spec-modem.txt"
capture_tc_filter "spec-router" "$OUTPUT_DIR/tc-filter-spec-router.txt"
capture_tc_filter "spec-modem" "$OUTPUT_DIR/tc-filter-spec-modem.txt"
ssh_read "ip -d link show" >"$OUTPUT_DIR/ip-link.txt"
write_bridge_mark_counters \
    "$OUTPUT_DIR/nft-bridge-qos-before.txt" \
    "$OUTPUT_DIR/nft-bridge-qos-after.txt" \
    "$OUTPUT_DIR/bridge-mark-counters.txt"
write_manifest

for required in \
    "$OUTPUT_DIR/nft-bridge-qos-before.txt" \
    "$OUTPUT_DIR/nft-bridge-qos-after.txt" \
    "$OUTPUT_DIR/tc-qdisc-spec-router.txt" \
    "$OUTPUT_DIR/tc-qdisc-spec-modem.txt" \
    "$OUTPUT_DIR/tc-filter-spec-router.txt" \
    "$OUTPUT_DIR/tc-filter-spec-modem.txt" \
    "$OUTPUT_DIR/ip-link.txt" \
    "$OUTPUT_DIR/bridge-mark-counters.txt" \
    "$OUTPUT_DIR/MANIFEST.md"; do
    if [[ ! -s "$required" ]]; then
        echo "ERROR: required artifact missing or empty: $required" >&2
        exit 1
    fi
done

echo "DSCP trace evidence captured: $OUTPUT_DIR"

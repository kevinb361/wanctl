#!/usr/bin/env bash
# One-packet IoT DSCP wash proof. Dry-run by default; live mode requires exact
# QVT-003 and SAFE-25 confirmation tokens.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR=""
SOURCE_SSH_HOST=""
SOURCE_IFACE=""
SOURCE_IP=""
TARGET_IP=""
INFRA_REPO="${INFRA_REPO:-$ROOT_DIR/../infra-ansible}"
MODE=""
CONFIRM_TRAFFIC=""
CONFIRM_SCOPE=""
EXPECTED_MANGLE_SHA256=""

usage() {
    cat <<'EOF'
Usage: scripts/qos-iot-wash-proof.sh --output-dir DIR --source-ssh-host HOST \
  --source-iface IFACE --source-ip IPv4 --target-ip IPv4 \
  --expected-mangle-sha256 SHA256 (--dry-run | --execute [confirmations])

Required with --execute:
  --confirm-controlled-traffic QVT-003
  --confirm-no-mutation SAFE-25

Exactly one EF-marked ICMP echo request is sent to the local VLAN gateway.
No RouterOS, host network, route, nftables, qdisc, service, or topology state is changed.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
        --source-ssh-host) SOURCE_SSH_HOST="${2:-}"; shift 2 ;;
        --source-iface) SOURCE_IFACE="${2:-}"; shift 2 ;;
        --source-ip) SOURCE_IP="${2:-}"; shift 2 ;;
        --target-ip) TARGET_IP="${2:-}"; shift 2 ;;
        --expected-mangle-sha256) EXPECTED_MANGLE_SHA256="${2:-}"; shift 2 ;;
        --infra-repo) INFRA_REPO="${2:-}"; shift 2 ;;
        --dry-run) MODE="dry-run"; shift ;;
        --execute) MODE="execute"; shift ;;
        --confirm-controlled-traffic) CONFIRM_TRAFFIC="${2:-}"; shift 2 ;;
        --confirm-no-mutation) CONFIRM_SCOPE="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$OUTPUT_DIR" || -z "$SOURCE_SSH_HOST" || -z "$SOURCE_IFACE" || -z "$SOURCE_IP" || -z "$TARGET_IP" || -z "$EXPECTED_MANGLE_SHA256" || -z "$MODE" ]]; then
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

if ! is_ipv4_token "$SOURCE_IP" || ! is_ipv4_token "$TARGET_IP"; then
    echo "ERROR: source and target must be literal IPv4 addresses" >&2
    exit 2
fi
if [[ ! "$SOURCE_SSH_HOST" =~ ^[A-Za-z0-9_.@-]+$ || ! "$SOURCE_IFACE" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo "ERROR: source host or interface contains unsupported characters" >&2
    exit 2
fi
if [[ ! "$EXPECTED_MANGLE_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ERROR: expected mangle SHA-256 must be exactly 64 lowercase hex characters" >&2
    exit 2
fi

print_plan() {
    cat <<EOF
POSTURE=DRY_RUN_NO_TRAFFIC
SOURCE=${SOURCE_SSH_HOST}/${SOURCE_IFACE}/${SOURCE_IP}
TARGET=${TARGET_IP}
PACKETS=1
PROTO=icmp
SOURCE_DSCP=46
EXPECTED_CANARY_DELTA=1
EXPECTED_MANGLE_SHA256=${EXPECTED_MANGLE_SHA256}
TRUST_EXCLUDES_IOT=true
COUNTER_SOURCE=routeros_stats_detail
SATURATION=false
MUTATION=false
EOF
}

if [[ "$MODE" == "dry-run" ]]; then
    print_plan
    exit 0
fi

if [[ "$CONFIRM_TRAFFIC" != "QVT-003" || "$CONFIRM_SCOPE" != "SAFE-25" ]]; then
    echo "ERROR: --execute requires QVT-003 and SAFE-25 confirmation tokens" >&2
    exit 2
fi
canary_playbook="$INFRA_REPO/artifacts/network-changes/20260717_routeros-qos-composite-policy/generic-rtp-canary.yml"
if [[ ! -f "$INFRA_REPO/scripts/routeros-qos-contract-audit.py" || ! -f "$canary_playbook" ]]; then
    echo "ERROR: RouterOS audit or canary status helper missing under infra repo: $INFRA_REPO" >&2
    exit 2
fi
for command in ssh python3 ansible-playbook; do
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

before_audit="$OUTPUT_DIR/routeros-audit-before.txt"
after_audit="$OUTPUT_DIR/routeros-audit-after.txt"
before_mangle="$OUTPUT_DIR/mangle-before.txt"
after_mangle="$OUTPUT_DIR/mangle-after.txt"
source_capture="$OUTPUT_DIR/source-ef-request.txt"
ping_output="$OUTPUT_DIR/ping.txt"
analysis_file="$OUTPUT_DIR/wash-analysis.json"

capture_status() {
    local label="$1" destination="$2"
    (
        cd "$INFRA_REPO"
        ansible-playbook \
            -i inventories/homelab/hosts.yml \
            "$canary_playbook" \
            --limit main-router \
            --vault-password-file .vault_pass \
            -e generic_rtp_selector=iot-dscp-wash \
            -e generic_rtp_mode=status \
            -e "generic_rtp_result_path=${destination}"
    ) >"$OUTPUT_DIR/routeros-canary-status-${label}.txt"
    python3 - "$destination" "$EXPECTED_MANGLE_SHA256" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = sys.argv[2]
assert result["selector"] == "iot-dscp-wash", result
assert result["state"] == "applied", result
assert result["changed"] is False, result
assert result["mangle_sha256"] == expected, result
PY
}

capture_mangle() {
    local audit_output="$1" destination="$2" label="$3" run_id artifact stats_log
    (cd "$INFRA_REPO" && python3 scripts/routeros-qos-contract-audit.py) | tee "$audit_output"

    run_id="qvt003_$(date +%Y%m%d_%H%M%S)_${label}_$$"
    stats_log="$OUTPUT_DIR/routeros-stats-${label}.txt"
    (
        cd "$INFRA_REPO"
        ansible-playbook \
            -i inventories/homelab/hosts.yml \
            playbooks/network/mikrotik_readonly.yml \
            --limit main-router \
            -e "{\"network_readonly_command\":\"/ip firewall mangle print stats detail\",\"network_readonly_run_id\":\"${run_id}\",\"network_readonly_output_suffix\":\"mangle-${label}\"}" \
            --vault-password-file .vault_pass
    ) >"$stats_log"
    artifact="$INFRA_REPO/artifacts/network-readonly/$run_id/main-router__mangle-${label}.txt"
    if [[ ! -f "$artifact" ]]; then
        echo "ERROR: exact RouterOS stats artifact missing: $artifact" >&2
        return 1
    fi
    cp -- "$artifact" "$destination"
}

# Exact applied policy and strict PASS are hard preconditions before the one authorized packet.
capture_status before "$OUTPUT_DIR/canary-status-before.json"
capture_mangle "$before_audit" "$before_mangle" before

capture_filter="icmp and src host ${SOURCE_IP} and dst host ${TARGET_IP}"
remote_capture="sudo -n timeout -k 1 5 tcpdump -n -l -vv -p -i '${SOURCE_IFACE}' -Q out -c 1 '${capture_filter}' 2>/dev/null; rc=\$?; if [ \$rc -eq 124 ]; then exit 0; fi; exit \$rc"
ssh -o BatchMode=yes "$SOURCE_SSH_HOST" "$remote_capture" >"$source_capture" &
capture_pid=$!
cleanup_capture() {
    if kill -0 "$capture_pid" 2>/dev/null; then
        kill "$capture_pid" 2>/dev/null || true
        wait "$capture_pid" 2>/dev/null || true
    fi
}
trap cleanup_capture EXIT
sleep 1

probe_rc=0
ssh -o BatchMode=yes "$SOURCE_SSH_HOST" \
    "ping -I '${SOURCE_IP}' -Q 0xb8 -c 1 -W 2 '${TARGET_IP}'" >"$ping_output" 2>&1 || probe_rc=$?
capture_rc=0
wait "$capture_pid" || capture_rc=$?
trap - EXIT

# Always capture authoritative after-counters, even when ping/capture disagrees.
after_audit_rc=0
capture_mangle "$after_audit" "$after_mangle" after || after_audit_rc=$?
after_status_rc=0
capture_status after "$OUTPUT_DIR/canary-status-after.json" || after_status_rc=$?
analysis_rc=0
python3 "$SCRIPT_DIR/qos_iot_wash_analyzer.py" \
    --before "$before_mangle" \
    --after "$after_mangle" \
    --source-capture "$source_capture" \
    --output "$analysis_file" || analysis_rc=$?

cat >"$OUTPUT_DIR/MANIFEST.md" <<EOF
# One-packet IoT DSCP wash proof

- Source: ${SOURCE_SSH_HOST}/${SOURCE_IFACE}/${SOURCE_IP}
- Target: ${TARGET_IP}
- Generated requests: exactly one ICMP echo with source DSCP EF(46)
- Acceptance: exact applied policy hash stable; source EF proven; source-subnet canary +1; EF/AF4x trust excludes IoT; strict audits PASS
- Saturation: none
- Mutation: none; no RouterOS, host network, route, nftables, qdisc, service, firewall, VLAN, or topology change
EOF

if (( probe_rc != 0 || capture_rc != 0 || after_audit_rc != 0 || after_status_rc != 0 || analysis_rc != 0 )); then
    echo "FAIL: probe, capture, audit, or wash acceptance disagreed; evidence retained in $OUTPUT_DIR" >&2
    exit 1
fi

echo "PASS: one-packet IoT DSCP wash proof captured in $OUTPUT_DIR"

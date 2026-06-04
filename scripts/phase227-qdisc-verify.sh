#!/usr/bin/env bash
# Phase 227 read-only CAKE qdisc mode verification gate.

set -euo pipefail

SSH_HOST="cake-shaper"
ROUTER_IFACE="spec-router"
MODEM_IFACE="spec-modem"
EXPECTED_MODE=""
OUT_FILE=""
DRY_RUN="0"
ROUTER_INPUT=""
MODEM_INPUT=""
SIMULATE_SSH_FAILED="0"

ALLOWED_MODE_RE='^(besteffort|diffserv3|diffserv4|precedence|diffserv8)$'

usage() {
    cat <<'EOF'
Usage:
  scripts/phase227-qdisc-verify.sh --expected-mode <diffserv4|besteffort> [options]

Options:
  --expected-mode MODE     Required expected CAKE mode: diffserv4 or besteffort
  --ssh-host HOST          SSH host for read-only target reads (default: cake-shaper)
  --router-iface IFACE     Router-side CAKE interface (default: spec-router)
  --modem-iface IFACE      Modem-side CAKE interface (default: spec-modem)
  --out FILE               Optional JSON proof output
  --dry-run                Print defaults/prereqs only; do not SSH
  --router-input FILE      Test-only: parse router qdisc output from FILE instead of SSH
  --modem-input FILE       Test-only: parse modem qdisc output from FILE instead of SSH
  --simulate-ssh-failed    Test-only: force both proof states to ssh_failed
  --help, -h               Show this help
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

remote_qdisc_show() {
    local iface="$1"
    ssh \
        -o BatchMode=yes \
        -o ConnectTimeout=5 \
        -o ServerAliveInterval=2 \
        -o ServerAliveCountMax=2 \
        "$SSH_HOST" \
        "timeout 8 sudo -n tc -s qdisc show dev '$iface'"
}

parse_qdisc_mode() {
    local input
    input="$(cat)"
    python3 - "$input" <<'PY'
import re
import sys

text = sys.argv[1]
if not text.strip() or "Cannot find device" in text:
    print("missing")
    raise SystemExit(0)

cake_lines = [line.strip() for line in text.splitlines() if re.match(r"^\s*qdisc\s+cake\b", line)]
if not cake_lines:
    print("no_cake")
    raise SystemExit(0)
if len(cake_lines) != 1:
    print("ambiguous")
    raise SystemExit(0)

allowed = {"besteffort", "diffserv3", "diffserv4", "precedence", "diffserv8"}
tokens = re.findall(r"[A-Za-z0-9_+-]+", cake_lines[0])
matches = [token for token in tokens if token in allowed]
if len(matches) != 1:
    print("ambiguous")
else:
    print(matches[0])
PY
}

json_escape() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

write_proof_json() {
    local checked_utc="$1"
    local router_got="$2"
    local modem_got="$3"
    local match="$4"

    if [[ -z "$OUT_FILE" ]]; then
        return 0
    fi
    python3 - "$OUT_FILE" "$checked_utc" "$SSH_HOST" "$EXPECTED_MODE" "$router_got" "$modem_got" "$match" <<'PY'
import json
import sys
from pathlib import Path

out, checked_utc, ssh_host, expected, router_got, modem_got, match = sys.argv[1:]
payload = {
    "checked_utc": checked_utc,
    "ssh_host": ssh_host,
    "expected_mode": expected,
    "router_got": router_got,
    "modem_got": modem_got,
    "match": match == "true",
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

check_iface() {
    local label="$1"
    local iface="$2"
    local input_file="${3:-}"
    local output

    if [[ "$SIMULATE_SSH_FAILED" == "1" ]]; then
        printf '%s\n' "ssh_failed"
        return 0
    fi
    if [[ -n "$input_file" ]]; then
        if [[ ! -r "$input_file" ]]; then
            printf '%s\n' "missing"
            return 0
        fi
        parse_qdisc_mode <"$input_file"
        return 0
    fi
    if ! output="$(remote_qdisc_show "$iface" 2>&1)"; then
        printf '%s\n' "ssh_failed"
        return 0
    fi
    printf '%s' "$output" | parse_qdisc_mode
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --expected-mode) EXPECTED_MODE="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --router-iface) ROUTER_IFACE="${2:-}"; shift 2 ;;
        --modem-iface) MODEM_IFACE="${2:-}"; shift 2 ;;
        --out) OUT_FILE="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN="1"; shift ;;
        --router-input) ROUTER_INPUT="${2:-}"; shift 2 ;;
        --modem-input) MODEM_INPUT="${2:-}"; shift 2 ;;
        --simulate-ssh-failed) SIMULATE_SSH_FAILED="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$EXPECTED_MODE" ]]; then
    echo "ERROR: --expected-mode is required" >&2
    usage >&2
    exit 2
fi
if [[ ! "$EXPECTED_MODE" =~ $ALLOWED_MODE_RE || "$EXPECTED_MODE" == "diffserv3" || "$EXPECTED_MODE" == "precedence" || "$EXPECTED_MODE" == "diffserv8" ]]; then
    echo "ERROR: --expected-mode must be diffserv4 or besteffort" >&2
    exit 2
fi
validate_iface "$ROUTER_IFACE"
validate_iface "$MODEM_IFACE"

require_command python3
require_command ssh

if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY_RUN: expected_mode=$EXPECTED_MODE ssh=$SSH_HOST router=$ROUTER_IFACE modem=$MODEM_IFACE"
    echo "DRY_RUN: read command uses ssh BatchMode with ConnectTimeout=5 and remote timeout 8 sudo -n tc -s qdisc show dev <iface>"
    echo "DRY_RUN: no SSH performed and no qdisc state mutated"
    exit 0
fi

if [[ -n "$ROUTER_INPUT$MODEM_INPUT" && ( -z "$ROUTER_INPUT" || -z "$MODEM_INPUT" ) ]]; then
    echo "ERROR: --router-input and --modem-input must be provided together" >&2
    exit 2
fi

CHECKED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ROUTER_GOT="$(check_iface router "$ROUTER_IFACE" "$ROUTER_INPUT")"
MODEM_GOT="$(check_iface modem "$MODEM_IFACE" "$MODEM_INPUT")"

MATCH="false"
EXIT_CODE=1
if [[ "$ROUTER_GOT" == "$EXPECTED_MODE" && "$MODEM_GOT" == "$EXPECTED_MODE" ]]; then
    MATCH="true"
    EXIT_CODE=0
fi

write_proof_json "$CHECKED_UTC" "$ROUTER_GOT" "$MODEM_GOT" "$MATCH"

if [[ "$EXIT_CODE" -eq 0 ]]; then
    echo "QDISC MODE OK: expected $EXPECTED_MODE got router=$ROUTER_GOT modem=$MODEM_GOT"
else
    if [[ "$ROUTER_GOT" != "$EXPECTED_MODE" ]]; then
        echo "MODE MISMATCH on $ROUTER_IFACE: expected $EXPECTED_MODE got $ROUTER_GOT" >&2
    fi
    if [[ "$MODEM_GOT" != "$EXPECTED_MODE" ]]; then
        echo "MODE MISMATCH on $MODEM_IFACE: expected $EXPECTED_MODE got $MODEM_GOT" >&2
    fi
fi

exit "$EXIT_CODE"

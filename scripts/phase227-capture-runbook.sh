#!/usr/bin/env bash
# Phase 227 operator-gated capture sequence driver.
#
# This script orchestrates the D-07 order without silently performing the
# production flip.  The flip subcommand prints the exact operator commands;
# deploy/restart remains checkpoint-gated by the human operator.

set -euo pipefail

HEALTH_URL="http://10.10.110.223:9101/health"
SSH_HOST="cake-shaper"
EVIDENCE_DIR=".planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/evidence"
RAW_DIR=""
DRY_RUN="0"
FORCE_WINDOW=""
TCP_REF_PORT="5202"
EF_REF_PORT="5203"
REF_HOST="vultr-chicago"
IPERF_REF_HOST="dallas"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase227-capture-runbook.sh [options] <precheck|baseline|flip|verify|candidate|abort|plan>

Options:
  --evidence-dir DIR   Phase 227 evidence directory (default: phase evidence/)
  --raw-dir DIR        Operator-private Snapshot A raw-dir for abort/rollback
  --ssh-host HOST      SSH host for read-only checks / rollback target (default: cake-shaper)
  --health-url URL     Spectrum health endpoint (default: http://10.10.110.223:9101/health)
  --force-window TEXT  Pass operator-approved forced-window reason to capture harness
  --tcp-ref-port PORT  TCP bulk iperf3 reference port passed to capture harness (default: 5202)
  --ef-ref-port PORT   Marked-EF iperf3 reference port passed to capture harness (default: 5203)
  --ref-host HOST      Flent/netperf reference host passed to capture harness (default: vultr-chicago)
  --iperf-ref-host HOST iperf3 reference host passed to capture harness (default: dallas)
  --dry-run            Print the ordered plan and commands; mutate nothing and run no load
  --help, -h           Show this help

Subcommands:
  precheck    Verify besteffort qdisc on both Spectrum NICs and healthy /health.
  baseline    Capture fresh besteffort+EF evidence before the flip.
  flip        Print the exact one-line edit, deploy, and restart commands; does not mutate.
  verify      Verify diffserv4 qdisc on both NICs plus health/crashloop guards.
  candidate   Capture diffserv4+EF evidence and leave diffserv4 live.
  abort       Delegate to scripts/phase227-rollback.sh (requires --raw-dir for real rollback).
  plan        Print the full D-07 ordered sequence.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 1
    fi
}

health_check() {
    python3 - "$HEALTH_URL" <<'PY'
import json
import sys
from urllib.request import urlopen

url = sys.argv[1]
try:
    with urlopen(url, timeout=3) as fh:
        payload = json.load(fh)
except Exception as exc:
    raise SystemExit(f"HEALTH FAIL: {url}: {exc}")

status = payload.get("status") if isinstance(payload, dict) else None
if status != "healthy":
    raise SystemExit(f"HEALTH FAIL: status={status!r} expected 'healthy'")
print(f"HEALTH OK: {url} status=healthy")
PY
}

nrestarts() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" \
        "systemctl show -p NRestarts --value wanctl@spectrum.service"
}

crashloop_check() {
    local before after active
    active="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "systemctl is-active wanctl@spectrum.service")"
    if [[ "$active" != "active" ]]; then
        echo "CRASHLOOP TRIGGER: wanctl@spectrum.service is-active=$active" >&2
        return 1
    fi
    before="$(nrestarts)"
    sleep 10
    after="$(nrestarts)"
    if [[ "$before" != "$after" ]]; then
        echo "CRASHLOOP TRIGGER: NRestarts increased $before -> $after" >&2
        return 1
    fi
    echo "SERVICE OK: active; NRestarts stable at $after"
}

abort_instruction() {
    cat <<EOF >&2
ABORT INSTRUCTION (D-09): run the genuine rollback, not phase226-restore.sh:
  scripts/phase227-rollback.sh --raw-dir <operator-private-snapshot-A-raw-dir> --confirm --out ${EVIDENCE_DIR}/rollback-proof.json
EOF
}

print_plan() {
    cat <<EOF
Phase 227 D-07 ordered sequence (no production mutation in --dry-run):
  1. precheck: scripts/phase227-qdisc-verify.sh --expected-mode besteffort + health ${HEALTH_URL}
  2. baseline: scripts/phase226-baseline-capture.sh --output-dir <temp> --marked-ef, then store ${EVIDENCE_DIR}/baseline-<UTC>
  3. flip: edit configs/spectrum.yaml exactly: diffserv: besteffort -> diffserv: diffserv4
           scripts/deploy.sh spectrum ${SSH_HOST}
           ssh ${SSH_HOST} 'sudo systemctl restart wanctl@spectrum.service'
  4. verify: scripts/phase227-qdisc-verify.sh --expected-mode diffserv4 --out ${EVIDENCE_DIR}/qdisc-verify-candidate.json
             health ${HEALTH_URL}; systemctl active; NRestarts stable across two polls
  5. candidate: scripts/phase226-baseline-capture.sh --output-dir <temp> --marked-ef, then store ${EVIDENCE_DIR}/candidate-<UTC>
  6. leave live: diffserv4 remains deployed for Phase 228 verdict (no capture-then-restore)

Armed abort for qdisc mismatch, unhealthy /health, or daemon crashloop:
  scripts/phase227-rollback.sh --raw-dir <operator-private-snapshot-A-raw-dir> --confirm --out ${EVIDENCE_DIR}/rollback-proof.json
EOF
}

run_capture() {
    local label="$1"
    local tmp_dir capture_dir final_dir
    tmp_dir="${EVIDENCE_DIR}/.${label}-capture-tmp-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$EVIDENCE_DIR"
    if [[ "$DRY_RUN" == "1" ]]; then
        echo "DRY_RUN: would run scripts/phase226-baseline-capture.sh --output-dir $tmp_dir --marked-ef --ref-host $REF_HOST --iperf-ref-host $IPERF_REF_HOST --tcp-ref-port $TCP_REF_PORT --ef-ref-port $EF_REF_PORT"
        echo "DRY_RUN: would move generated baseline-<UTC> tree to ${EVIDENCE_DIR}/${label}-<UTC>"
        return 0
    fi
    local args=(--output-dir "$tmp_dir" --marked-ef --ref-host "$REF_HOST" --iperf-ref-host "$IPERF_REF_HOST" --tcp-ref-port "$TCP_REF_PORT" --ef-ref-port "$EF_REF_PORT" --health-url "$HEALTH_URL" --ssh-host "$SSH_HOST")
    if [[ -n "$FORCE_WINDOW" ]]; then
        args+=(--force-window "$FORCE_WINDOW")
    fi
    scripts/phase226-baseline-capture.sh "${args[@]}"
    capture_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d -name 'baseline-*' -print -quit)"
    if [[ -z "$capture_dir" ]]; then
        echo "ERROR: capture harness did not create baseline-<UTC> under $tmp_dir" >&2
        exit 1
    fi
    final_dir="${EVIDENCE_DIR}/${label}-${capture_dir##*-}"
    mv "$capture_dir" "$final_dir"
    rmdir "$tmp_dir"
    echo "${label^} capture complete: $final_dir"
}

precheck() {
    scripts/phase227-qdisc-verify.sh --expected-mode besteffort --ssh-host "$SSH_HOST" --out "${EVIDENCE_DIR}/qdisc-verify-besteffort.json"
    health_check
}

flip() {
    cat <<EOF
OPERATOR FLIP COMMANDS (not executed by this script):
  Edit configs/spectrum.yaml exactly one line:
    diffserv: besteffort  ->  diffserv: diffserv4
    leave allow_wash: true, DL 920, UL 18, docsis_mode: true unchanged
  scripts/deploy.sh spectrum ${SSH_HOST}
  ssh ${SSH_HOST} 'sudo systemctl restart wanctl@spectrum.service'
EOF
}

verify_candidate() {
    mkdir -p "$EVIDENCE_DIR"
    if ! scripts/phase227-qdisc-verify.sh --expected-mode diffserv4 --ssh-host "$SSH_HOST" --out "${EVIDENCE_DIR}/qdisc-verify-candidate.json"; then
        abort_instruction
        return 1
    fi
    if ! health_check; then
        abort_instruction
        return 1
    fi
    if ! crashloop_check; then
        abort_instruction
        return 1
    fi
}

abort_run() {
    if [[ -z "$RAW_DIR" ]]; then
        echo "ERROR: abort requires --raw-dir <operator-private-snapshot-A-raw-dir>" >&2
        abort_instruction
        exit 2
    fi
    scripts/phase227-rollback.sh --raw-dir "$RAW_DIR" --ssh-host "$SSH_HOST" --health-url "$HEALTH_URL" --out "${EVIDENCE_DIR}/rollback-proof.json" --confirm
}

SUBCOMMAND=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
        --raw-dir) RAW_DIR="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --health-url) HEALTH_URL="${2:-}"; shift 2 ;;
        --force-window) FORCE_WINDOW="${2:-}"; shift 2 ;;
        --tcp-ref-port) TCP_REF_PORT="${2:-}"; shift 2 ;;
        --ef-ref-port) EF_REF_PORT="${2:-}"; shift 2 ;;
        --ref-host) REF_HOST="${2:-}"; shift 2 ;;
        --iperf-ref-host) IPERF_REF_HOST="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        precheck|baseline|flip|verify|candidate|abort|plan) SUBCOMMAND="$1"; shift ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$SUBCOMMAND" ]]; then
    if [[ "$DRY_RUN" == "1" ]]; then
        SUBCOMMAND="plan"
    else
        usage >&2
        exit 2
    fi
fi

if [[ "$DRY_RUN" == "1" ]]; then
    print_plan
    case "$SUBCOMMAND" in
        plan) exit 0 ;;
        baseline) run_capture baseline; exit 0 ;;
        candidate) run_capture candidate; exit 0 ;;
        flip) flip; exit 0 ;;
        abort) echo "DRY_RUN: would delegate to scripts/phase227-rollback.sh --raw-dir <raw-dir> --confirm"; exit 0 ;;
        precheck|verify) echo "DRY_RUN: would run $SUBCOMMAND checks against $HEALTH_URL and $SSH_HOST"; exit 0 ;;
    esac
fi

require_command python3
require_command ssh
require_command find

case "$SUBCOMMAND" in
    plan) print_plan ;;
    precheck) mkdir -p "$EVIDENCE_DIR"; precheck ;;
    baseline) run_capture baseline ;;
    flip) flip ;;
    verify) verify_candidate ;;
    candidate) run_capture candidate ;;
    abort) abort_run ;;
esac

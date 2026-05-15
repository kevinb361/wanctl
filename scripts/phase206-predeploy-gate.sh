#!/usr/bin/env bash
# Phase 206 predeploy gate (TOPO-05).
# Three rollback triggers (any one BLOCKs deploy):
#   1. RRUL p99 latency regression > 5%
#   2. Spectrum daemon restart-rate > 10% increase per hour
#   3. Pressure-state transition-rate > 10% increase per hour
#
# Exit codes (matches scripts/phase201-predeploy-gate.sh contract):
#   0  PASS  — all thresholds clear
#   1  BLOCK — at least one threshold breached
#   2  ABORT — missing input, malformed env, SSH failure
#
# SSH/NRestarts sampling lives in this wrapper (M7); the Python helper
# phase206-gate-check.py is SSH-free and operates on JSON/NDJSON only.

set -euo pipefail

EXIT_PASS=0
EXIT_BLOCK=1
EXIT_ABORT=2

log_info()  { printf '[phase206-predeploy-gate INFO]  %s\n' "$*" >&2; }
log_block() { printf '[phase206-predeploy-gate BLOCK] %s\n' "$*" >&2; printf '%s\n' "$*"; }
log_abort() { printf '[phase206-predeploy-gate ABORT] %s\n' "$*" >&2; }

# require_value OPT VALUE — abort with rc=2 if VALUE is empty or starts with `--`.
# Call BEFORE any `shift 2` so a missing operator-input value classifies as ABORT,
# not BLOCK (which is reserved for threshold breaches under valid input).
require_value() {
    local opt="$1"
    local val="${2-}"
    if [[ -z "${val}" ]]; then
        log_abort "missing value for ${opt}"
        exit $EXIT_ABORT
    fi
    if [[ "${val}" == --* ]]; then
        log_abort "missing value for ${opt} (next token is option-like: ${val})"
        exit $EXIT_ABORT
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="${VENV_PY:-$REPO_ROOT/.venv/bin/python3}"

usage() {
    cat <<'EOF'
Usage: phase206-predeploy-gate.sh --baseline PATH --candidate PATH [options]

Options:
  --baseline PATH                 v1.43 baseline / A/B summary JSON (required)
  --candidate PATH                candidate A/B summary JSON (required)
  --soak-ndjson PATH              post-deploy soak capture for transition-rate gate
  --mode predeploy|post-soak      predeploy allows partial dry-runs; post-soak requires all gates
  --ssh-target HOST               sample NRestarts from HOST via SSH when end counter absent
  --window-start-iso8601 VALUE    deploy-complete-plus-grace timestamp
  --window-end-iso8601 VALUE      end-of-soak timestamp
  --window-hours FLOAT            explicit soak window hours
  --restart-counter-start INT     start NRestarts counter
  --restart-counter-end INT       end NRestarts counter
  --journal-since VALUE           informational audit timestamp passed to Python core
  -h, --help                      show this help
EOF
}

BASELINE=""
CANDIDATE=""
SOAK=""
MODE="predeploy"
SSH_TARGET=""
WIN_START=""
WIN_END=""
WIN_HOURS=""
RC_START=""
RC_END=""
JOURNAL_SINCE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline)
            require_value "--baseline" "${2-}"; BASELINE="$2"; shift 2 ;;
        --candidate)
            require_value "--candidate" "${2-}"; CANDIDATE="$2"; shift 2 ;;
        --soak-ndjson)
            require_value "--soak-ndjson" "${2-}"; SOAK="$2"; shift 2 ;;
        --mode)
            require_value "--mode" "${2-}"; MODE="$2"; shift 2 ;;
        --ssh-target)
            require_value "--ssh-target" "${2-}"; SSH_TARGET="$2"; shift 2 ;;
        --window-start-iso8601)
            require_value "--window-start-iso8601" "${2-}"; WIN_START="$2"; shift 2 ;;
        --window-end-iso8601)
            require_value "--window-end-iso8601" "${2-}"; WIN_END="$2"; shift 2 ;;
        --window-hours)
            require_value "--window-hours" "${2-}"; WIN_HOURS="$2"; shift 2 ;;
        --restart-counter-start)
            require_value "--restart-counter-start" "${2-}"; RC_START="$2"; shift 2 ;;
        --restart-counter-end)
            require_value "--restart-counter-end" "${2-}"; RC_END="$2"; shift 2 ;;
        --journal-since)
            require_value "--journal-since" "${2-}"; JOURNAL_SINCE="$2"; shift 2 ;;
        -h|--help)
            usage; exit $EXIT_PASS ;;
        *)
            log_abort "unknown argument: $1"
            usage
            exit $EXIT_ABORT ;;
    esac
done

if [[ "$MODE" != "predeploy" && "$MODE" != "post-soak" ]]; then
    log_abort "invalid --mode: ${MODE} (must be predeploy or post-soak)"
    exit $EXIT_ABORT
fi

if [[ -z "$BASELINE" ]]; then
    log_abort "missing --baseline"
    exit $EXIT_ABORT
fi
if [[ ! -r "$BASELINE" ]]; then
    log_abort "baseline not readable: $BASELINE"
    exit $EXIT_ABORT
fi
if [[ -z "$CANDIDATE" ]]; then
    log_abort "missing --candidate"
    exit $EXIT_ABORT
fi
if [[ ! -r "$CANDIDATE" ]]; then
    log_abort "candidate not readable: $CANDIDATE"
    exit $EXIT_ABORT
fi
if [[ -n "$SOAK" && ! -r "$SOAK" ]]; then
    log_abort "soak NDJSON not readable: $SOAK"
    exit $EXIT_ABORT
fi

if [[ -n "$SSH_TARGET" ]]; then
    if [[ ! "$SSH_TARGET" =~ ^[A-Za-z0-9._-]+$ ]]; then
        log_abort "invalid --ssh-target: $SSH_TARGET"
        exit $EXIT_ABORT
    fi
fi

if [[ -n "$SSH_TARGET" && -z "$RC_END" ]]; then
    if [[ -z "$WIN_START" || -z "$WIN_END" ]]; then
        log_abort "--ssh-target requires --window-start-iso8601 and --window-end-iso8601 when --restart-counter-end is absent"
        exit $EXIT_ABORT
    fi
    log_info "sampling NRestarts via SSH: $SSH_TARGET"
    SSH_OUT=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" \
        "systemctl show -p NRestarts wanctl@spectrum.service" 2>&1) || {
        log_abort "ssh failed: $SSH_OUT"
        exit $EXIT_ABORT
    }
    RC_END="${SSH_OUT##*NRestarts=}"
    RC_END="${RC_END%%[^0-9]*}"
    if [[ -z "$RC_END" ]]; then
        log_abort "could not parse NRestarts from: $SSH_OUT"
        exit $EXIT_ABORT
    fi
    log_info "RC_END=$RC_END (sampled via SSH at gate-invocation time)"
fi

if [[ -n "$WIN_START" && -n "$WIN_END" && -z "$WIN_HOURS" ]]; then
    START_S=$(date -d "$WIN_START" +%s) || { log_abort "invalid --window-start-iso8601"; exit $EXIT_ABORT; }
    END_S=$(date -d "$WIN_END" +%s) || { log_abort "invalid --window-end-iso8601"; exit $EXIT_ABORT; }
    WIN_HOURS=$(python3 -c 'import sys; s=float(sys.argv[1]); e=float(sys.argv[2]); print(f"{(e-s)/3600.0:.6f}")' "$START_S" "$END_S")
    log_info "computed --window-hours=$WIN_HOURS from ISO8601 window"
fi

PY_ARGS=("--baseline" "$BASELINE" "--candidate" "$CANDIDATE" "--mode" "$MODE")
[[ -n "$SOAK" ]] && PY_ARGS+=("--soak-ndjson" "$SOAK")
[[ -n "$RC_START" ]] && PY_ARGS+=("--restart-counter-start" "$RC_START")
[[ -n "$RC_END" ]] && PY_ARGS+=("--restart-counter-end" "$RC_END")
[[ -n "$WIN_HOURS" ]] && PY_ARGS+=("--window-hours" "$WIN_HOURS")
[[ -n "$JOURNAL_SINCE" ]] && PY_ARGS+=("--journal-since" "$JOURNAL_SINCE")

if [[ ! -x "$VENV_PY" && ! -f "$VENV_PY" ]]; then
    log_abort "Python interpreter not found: $VENV_PY"
    exit $EXIT_ABORT
fi

log_info "invoking gate-check helper (mode=$MODE)"
exec "$VENV_PY" "$SCRIPT_DIR/phase206-gate-check.py" "${PY_ARGS[@]}"

#!/bin/bash
# compact-metrics-dbs.sh - Explicit offline compaction for active per-WAN metrics DBs
#
# Usage:
#   ./scripts/compact-metrics-dbs.sh [--ssh user@host] [--wan spectrum|att|all] [--aggregate-hours 24] [--dry-run]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SSH_TARGET=""
DRY_RUN=false
WAN_FILTER="all"
AGGREGATE_HOURS=24

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1" >&2
}

usage() {
    cat <<EOF
wanctl per-WAN metrics DB compaction

Usage:
  ./scripts/compact-metrics-dbs.sh [--ssh user@host] [--wan spectrum|att|all] [--aggregate-hours 24] [--dry-run]

Options:
  --ssh TARGET   Execute remotely over SSH
  --wan NAME     Compact only one WAN DB (default: all)
  --aggregate-hours N
                 Prune 5m/1h aggregates older than N hours before VACUUM (default: 24)
  --dry-run      Show the actions without mutating the target
  --help, -h     Show this help
EOF
}

human_size() {
    local bytes="${1:-0}"
    if command -v numfmt >/dev/null 2>&1; then
        numfmt --to=iec --suffix=B "$bytes"
    else
        echo "${bytes} bytes"
    fi
}

run_cmd() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        print_info "DRY RUN: $*"
        return 0
    fi
    "$@"
}

run_sql() {
    local db_path="$1"
    local sql="$2"
    if [[ "${DRY_RUN}" == "true" ]]; then
        print_info "DRY RUN: sudo sqlite3 \"$db_path\" \"$sql\""
        return 0
    fi
    sudo sqlite3 "$db_path" "$sql"
}

compact_one_db() {
    local wan_name="$1"
    local db_path="$2"
    local service_unit="wanctl@${wan_name}.service"
    local before_size after_size saved_bytes cutoff deleted_rows

    if ! sudo test -f "${db_path}"; then
        print_warn "${wan_name}: ${db_path} not found, skipping"
        return 0
    fi

    before_size=$(sudo stat -c%s "${db_path}" 2>/dev/null || echo 0)
    print_info "${wan_name}: stopping ${service_unit}"
    run_cmd sudo systemctl stop "${service_unit}"

    cutoff=$(date -d "${AGGREGATE_HOURS} hours ago" +%s)
    print_info "${wan_name}: pruning 5m/1h aggregates older than ${AGGREGATE_HOURS}h"
    deleted_rows=$(run_sql "${db_path}" "DELETE FROM metrics WHERE granularity IN ('5m','1h') AND timestamp < ${cutoff}; SELECT changes();" | tail -n 1 | tr -d '\r')
    print_info "${wan_name}: pruned ${deleted_rows:-0} aggregate rows"

    print_info "${wan_name}: checkpointing and vacuuming ${db_path}"
    run_sql "${db_path}" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;" >/dev/null

    after_size=$(sudo stat -c%s "${db_path}" 2>/dev/null || echo "${before_size}")
    if (( before_size >= after_size )); then
        saved_bytes=$((before_size - after_size))
    else
        saved_bytes=0
    fi

    print_info "${wan_name}: starting ${service_unit}"
    run_cmd sudo systemctl start "${service_unit}"

    print_pass "${wan_name}: $(human_size "${before_size}") -> $(human_size "${after_size}") (saved $(human_size "${saved_bytes}"))"
}

run_compaction() {
    local state_dir="/var/lib/wanctl"

    if [[ "${DRY_RUN}" != "true" ]] && ! command -v sqlite3 >/dev/null 2>&1; then
        print_fail "sqlite3 not found on target host"
        return 1
    fi

    case "${WAN_FILTER}" in
        spectrum)
            compact_one_db "spectrum" "${state_dir}/metrics-spectrum.db"
            ;;
        att)
            compact_one_db "att" "${state_dir}/metrics-att.db"
            ;;
        all)
            compact_one_db "spectrum" "${state_dir}/metrics-spectrum.db"
            compact_one_db "att" "${state_dir}/metrics-att.db"
            ;;
        *)
            print_fail "Unknown --wan value: ${WAN_FILTER}"
            return 1
            ;;
    esac

    echo
    echo "Next step:"
    echo "  ./scripts/canary-check.sh --ssh ${SSH_TARGET:-<host>} --expect-version 1.35.0 --json"
}

run_remote() {
    ssh "$SSH_TARGET" "DRY_RUN=${DRY_RUN} WAN_FILTER=${WAN_FILTER} AGGREGATE_HOURS=${AGGREGATE_HOURS} bash -s --" <<REMOTE_SCRIPT
set -euo pipefail
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
DRY_RUN="${DRY_RUN:-false}"
WAN_FILTER="${WAN_FILTER:-all}"
$(declare -f print_info)
$(declare -f print_pass)
$(declare -f print_warn)
$(declare -f print_fail)
$(declare -f human_size)
$(declare -f run_cmd)
$(declare -f run_sql)
$(declare -f compact_one_db)
$(declare -f run_compaction)
run_compaction
REMOTE_SCRIPT
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssh)
            SSH_TARGET="${2:-}"
            shift 2
            ;;
        --wan)
            WAN_FILTER="${2:-}"
            shift 2
            ;;
        --aggregate-hours)
            AGGREGATE_HOURS="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            print_fail "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ -n "${SSH_TARGET}" ]]; then
    run_remote
else
    run_compaction
fi

#!/bin/bash
# wanctl One-Shot Storage Migration
#
# Archives the legacy shared metrics DB after retention purge + VACUUM.
#
# Usage:
#   ./scripts/migrate-storage.sh [--ssh user@host] [--dry-run]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SSH_TARGET=""
DRY_RUN=false

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
wanctl One-Shot Storage Migration

Usage:
  ./scripts/migrate-storage.sh [--ssh user@host] [--dry-run]

Options:
  --ssh TARGET   Execute migration remotely over SSH
  --dry-run      Show what would happen without making changes
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
        echo "0"
        return 0
    fi
    sudo sqlite3 "$db_path" "$sql"
}

run_migration() {
    local state_dir="/var/lib/wanctl"
    local legacy_db="${state_dir}/metrics.db"
    local archive_name="${state_dir}/metrics.db.pre-v135-archive"
    local spectrum_db="${state_dir}/metrics-spectrum.db"
    local att_db="${state_dir}/metrics-att.db"
    local legacy_size cutoff metrics_deleted downsampled_deleted pre_size post_size saved_bytes saved_mb

    if [[ ! -f "${legacy_db}" ]]; then
        print_warn "Legacy DB not found, nothing to migrate"
        return 0
    fi

    if [[ -f "${archive_name}" ]]; then
        print_warn "Archive already exists, migration already completed"
        return 0
    fi

    if [[ "${DRY_RUN}" != "true" ]] && ! command -v sqlite3 >/dev/null 2>&1; then
        print_fail "sqlite3 not found on target host"
        return 1
    fi

    legacy_size=$(sudo stat -c%s "${legacy_db}" 2>/dev/null || echo 0)
    print_info "Legacy DB: $(human_size "${legacy_size}")"

    print_info "Stopping wanctl services..."
    run_cmd sudo systemctl stop wanctl@spectrum.service wanctl@att.service 2>/dev/null || true
    if [[ "${DRY_RUN}" == "true" ]]; then
        print_info "DRY RUN: sleep 2"
    else
        sleep 2
    fi

    print_info "Purging data older than 24h from legacy DB..."
    cutoff=$(date -d '24 hours ago' +%s)
    metrics_deleted=$(run_sql "${legacy_db}" "DELETE FROM metrics WHERE timestamp < ${cutoff}; SELECT changes();")
    downsampled_deleted=$(run_sql "${legacy_db}" "DELETE FROM downsampled_metrics WHERE timestamp < ${cutoff}; SELECT changes();")
    print_info "Deleted rows from metrics: ${metrics_deleted}"
    print_info "Deleted rows from downsampled_metrics: ${downsampled_deleted}"

    print_info "Running VACUUM on legacy DB (this may take a moment)..."
    pre_size=$(sudo stat -c%s "${legacy_db}" 2>/dev/null || echo 0)
    run_sql "${legacy_db}" "VACUUM;" >/dev/null
    post_size=$(sudo stat -c%s "${legacy_db}" 2>/dev/null || echo 0)
    if (( pre_size >= post_size )); then
        saved_bytes=$((pre_size - post_size))
    else
        saved_bytes=0
    fi
    saved_mb=$((saved_bytes / 1024 / 1024))
    print_pass "VACUUM complete: ${pre_size} -> ${post_size} bytes (saved ${saved_mb} MB)"

    print_info "Archiving legacy DB..."
    run_cmd sudo mv "${legacy_db}" "${archive_name}"
    if [[ -f "${legacy_db}-wal" ]]; then
        run_cmd sudo mv "${legacy_db}-wal" "${archive_name}-wal"
    fi
    if [[ -f "${legacy_db}-shm" ]]; then
        run_cmd sudo mv "${legacy_db}-shm" "${archive_name}-shm"
    fi
    print_pass "Archived to: ${archive_name}"

    echo
    echo "=== Post-Migration Verification ==="
    if [[ -f "${legacy_db}" ]]; then
        echo "Legacy DB: STILL EXISTS (ERROR)"
    else
        echo "Legacy DB: Archived (OK)"
    fi

    if [[ -f "${archive_name}" ]]; then
        echo "Archive: $(human_size "$(sudo stat -c%s "${archive_name}" 2>/dev/null || echo 0)") (OK)"
    elif [[ "${DRY_RUN}" == "true" ]]; then
        echo "Archive: Dry-run only (would be created)"
    else
        echo "Archive: Missing (ERROR)"
    fi

    if [[ -f "${spectrum_db}" ]]; then
        echo "Spectrum DB: $(human_size "$(sudo stat -c%s "${spectrum_db}" 2>/dev/null || echo 0)")"
    else
        echo "Spectrum DB: Not yet created (will be created on service start)"
    fi

    if [[ -f "${att_db}" ]]; then
        echo "ATT DB: $(human_size "$(sudo stat -c%s "${att_db}" 2>/dev/null || echo 0)")"
    else
        echo "ATT DB: Not yet created (will be created on service start)"
    fi

    echo
    echo "Next steps:"
    echo "  1. Start services: sudo systemctl start wanctl@spectrum wanctl@att"
    echo "  2. Wait 30s for initial data, then run: ./scripts/canary-check.sh --ssh user@host"
    echo "  3. Verify storage.status is 'ok' in canary output"
}

run_remote() {
    ssh "$SSH_TARGET" "DRY_RUN=${DRY_RUN} bash -s --" <<REMOTE_SCRIPT
set -euo pipefail
$(declare -f print_info)
$(declare -f print_pass)
$(declare -f print_warn)
$(declare -f print_fail)
$(declare -f human_size)
$(declare -f run_cmd)
$(declare -f run_sql)
$(declare -f run_migration)
run_migration
REMOTE_SCRIPT
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssh)
            SSH_TARGET="${2:-}"
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
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "${SSH_TARGET}" ]]; then
    run_migration
else
    run_remote
fi

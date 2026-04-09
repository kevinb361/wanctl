#!/bin/bash
# burst-soak-check.sh — 24h soak monitor for burst detection (Phase 153, VAL-03)
#
# Usage:
#   burst-soak-check.sh --start    Record soak baseline
#   burst-soak-check.sh --check    Check current state vs baseline
set -euo pipefail

# Configuration
VM_HOST="kevin@10.10.110.223"
HEALTH_URL="http://10.10.110.223:9101/health"
SOAK_STATE_FILE="/tmp/burst-soak-baseline.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

print_pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; }
print_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
print_info() { echo -e "  ${BLUE}[INFO]${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

query_health() {
    local health_json
    health_json=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$VM_HOST" \
        "curl -s ${HEALTH_URL}" 2>/dev/null) || {
        echo -e "${RED}ERROR: Could not reach health endpoint via SSH${NC}" >&2
        exit 1
    }
    if [[ -z "$health_json" ]]; then
        echo -e "${RED}ERROR: Empty response from health endpoint${NC}" >&2
        exit 1
    fi
    echo "$health_json"
}

extract_field() {
    local json="$1" path="$2"
    echo "$json" | jq -r "$path // empty" 2>/dev/null
}

extract_burst_field() {
    local json="$1" field="$2"
    # Navigate into wans array to find burst_detection
    echo "$json" | jq -r "
        (.wans // .wan_controllers // [{}])[0].burst_detection.${field} // empty
    " 2>/dev/null
}

mode="${1:---check}"

case "$mode" in
    --start)
        echo -e "${BOLD}========================================${NC}"
        echo -e "${BOLD}  Burst Soak: Recording Baseline${NC}"
        echo -e "${BOLD}========================================${NC}"
        echo ""

        health_json=$(query_health)

        version=$(extract_field "$health_json" '.version')
        uptime=$(extract_field "$health_json" '.uptime_seconds')
        status=$(extract_field "$health_json" '.status')
        total_bursts=$(extract_burst_field "$health_json" 'total_bursts')
        total_responses=$(extract_burst_field "$health_json" 'burst_responses_total')
        bd_enabled=$(extract_burst_field "$health_json" 'enabled')
        br_enabled=$(extract_burst_field "$health_json" 'burst_response_enabled')

        print_info "Version: ${version:-unknown}"
        print_info "Uptime: ${uptime:-0}s"
        print_info "Status: ${status:-unknown}"
        print_info "Burst detection enabled: ${bd_enabled:-false}"
        print_info "Burst response enabled: ${br_enabled:-false}"
        print_info "Current total_bursts: ${total_bursts:-0}"
        print_info "Current burst_responses_total: ${total_responses:-0}"
        echo ""

        if [[ "$bd_enabled" != "true" ]] || [[ "$br_enabled" != "true" ]]; then
            print_fail "Burst detection or response not enabled. Cannot start soak."
            exit 1
        fi

        # Save baseline
        cat > "$SOAK_STATE_FILE" <<EOJSON
{
    "start_time": "$(date -Iseconds)",
    "start_uptime": ${uptime:-0},
    "start_bursts": ${total_bursts:-0},
    "start_responses": ${total_responses:-0},
    "version": "${version:-unknown}"
}
EOJSON

        print_pass "Soak baseline recorded to ${SOAK_STATE_FILE}"
        echo ""
        echo -e "Run ${BOLD}burst-soak-check.sh --check${NC} after 24h."
        ;;

    --check)
        echo -e "${BOLD}========================================${NC}"
        echo -e "${BOLD}  Burst Soak: Status Check${NC}"
        echo -e "${BOLD}========================================${NC}"
        echo ""

        if [[ ! -f "$SOAK_STATE_FILE" ]]; then
            print_fail "No soak baseline found. Run --start first."
            exit 1
        fi

        # Load baseline
        start_time=$(jq -r '.start_time' "$SOAK_STATE_FILE")
        start_uptime=$(jq -r '.start_uptime' "$SOAK_STATE_FILE")
        start_bursts=$(jq -r '.start_bursts' "$SOAK_STATE_FILE")
        start_responses=$(jq -r '.start_responses' "$SOAK_STATE_FILE")
        start_version=$(jq -r '.version' "$SOAK_STATE_FILE")

        # Query current state
        health_json=$(query_health)

        version=$(extract_field "$health_json" '.version')
        uptime=$(extract_field "$health_json" '.uptime_seconds')
        status=$(extract_field "$health_json" '.status')
        total_bursts=$(extract_burst_field "$health_json" 'total_bursts')
        total_responses=$(extract_burst_field "$health_json" 'burst_responses_total')

        # Compute deltas
        soak_hours=$(awk "BEGIN {printf \"%.1f\", (${uptime:-0} - ${start_uptime:-0}) / 3600}")
        new_bursts=$((${total_bursts:-0} - ${start_bursts:-0}))
        new_responses=$((${total_responses:-0} - ${start_responses:-0}))

        # Check for restart
        restarted="no"
        if awk "BEGIN {exit (${uptime:-0} < ${start_uptime:-0}) ? 0 : 1}"; then
            restarted="yes"
        fi

        # Report
        echo -e "  Soak Started:      ${start_time}"
        echo -e "  Soak Duration:     ${soak_hours}h"
        echo -e "  Version:           ${version:-unknown}"
        echo -e "  Service Status:    ${status:-unknown}"
        echo -e "  New Burst Triggers:   ${new_bursts}"
        echo -e "  New Burst Responses:  ${new_responses}"
        echo -e "  Service Restarts:  ${restarted} (uptime: ${uptime:-0}s)"
        echo ""

        # Warnings
        if [[ "$version" != "$start_version" ]]; then
            print_warn "Version changed: ${start_version} -> ${version}"
        fi
        if [[ "$restarted" == "yes" ]]; then
            print_warn "Service restarted during soak (counters may have reset)"
        fi

        # Verdict
        echo -e "${BOLD}  Verdict:${NC}"
        if (( new_bursts == 0 )) && [[ "$status" == "healthy" ]]; then
            if awk "BEGIN {exit (${soak_hours} >= 24) ? 0 : 1}"; then
                print_pass "VAL-03: PASSED — 24h soak, zero false triggers, service healthy"
                exit 0
            else
                print_warn "VAL-03: PENDING — soak not yet 24h (${soak_hours}h elapsed)"
                exit 0
            fi
        elif (( new_bursts > 0 )); then
            print_fail "VAL-03: FAILED — ${new_bursts} burst trigger(s) during soak"
            exit 1
        else
            print_fail "VAL-03: FAILED — service status: ${status}"
            exit 1
        fi
        ;;

    *)
        echo "Usage: burst-soak-check.sh [--start|--check]"
        exit 1
        ;;
esac

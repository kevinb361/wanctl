#!/bin/bash
# soak-monitor.sh - Simple soak period monitoring for wanctl rc7
# Usage: ./soak-monitor.sh [--watch] [--json]
#
# Run once for status check, or with --watch for continuous monitoring

set -euo pipefail

# Configuration
CONTAINERS=("cake-spectrum" "cake-att")
HEALTH_PORT=9101
CHECK_INTERVAL=60  # seconds for --watch mode

# Colors (use -e with echo)
RED='\e[0;31m'
GREEN='\e[0;32m'
YELLOW='\e[0;33m'
BLUE='\e[0;34m'
BOLD='\e[1m'
NC='\e[0m'

# Parse arguments
WATCH_MODE=false
JSON_MODE=false
for arg in "$@"; do
    case $arg in
        --watch) WATCH_MODE=true ;;
        --json) JSON_MODE=true ;;
        --help|-h)
            echo "Usage: $0 [--watch] [--json]"
            echo "  --watch  Continuous monitoring (every ${CHECK_INTERVAL}s)"
            echo "  --json   Output raw JSON instead of formatted"
            exit 0
            ;;
    esac
done

# Check if jq is available
HAS_JQ=false
if command -v jq &>/dev/null; then
    HAS_JQ=true
fi

# Check single container health
check_container() {
    local container=$1
    local health_json

    # Fetch health data
    if ! health_json=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$container" "curl -s http://127.0.0.1:${HEALTH_PORT}/health" 2>/dev/null); then
        echo "UNREACHABLE|?|?|?|?/?"
        return 1
    fi

    if [[ -z "$health_json" || "$health_json" == "null" ]]; then
        echo "NO_RESPONSE|?|?|?|?/?"
        return 1
    fi

    if $JSON_MODE; then
        echo "$health_json"
        return 0
    fi

    local status version uptime failures dl_state ul_state

    if $HAS_JQ; then
        # Use jq for reliable parsing
        status=$(echo "$health_json" | jq -r '.status // "unknown"')
        version=$(echo "$health_json" | jq -r '.version // "?"')
        uptime=$(echo "$health_json" | jq -r '.uptime_seconds // 0')
        failures=$(echo "$health_json" | jq -r '.consecutive_failures // 0')
        dl_state=$(echo "$health_json" | jq -r '.wans[0].download.state // "?"')
        ul_state=$(echo "$health_json" | jq -r '.wans[0].upload.state // "?"')
    else
        # Fallback to grep/sed parsing
        status=$(echo "$health_json" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
        version=$(echo "$health_json" | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
        uptime=$(echo "$health_json" | sed -n 's/.*"uptime_seconds"[[:space:]]*:[[:space:]]*\([0-9.]*\).*/\1/p' | head -1)
        failures=$(echo "$health_json" | sed -n 's/.*"consecutive_failures"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' | head -1)
        # Simplified state extraction - just get first occurrence
        dl_state=$(echo "$health_json" | sed -n 's/.*"download"[^}]*"state"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
        ul_state=$(echo "$health_json" | sed -n 's/.*"upload"[^}]*"state"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
    fi

    # Format uptime
    local uptime_fmt="?"
    if [[ -n "$uptime" && "$uptime" != "0" ]]; then
        local hours mins
        hours=$(echo "$uptime / 3600" | bc 2>/dev/null || echo "?")
        mins=$(echo "($uptime % 3600) / 60" | bc 2>/dev/null || echo "?")
        if [[ "$hours" != "?" ]]; then
            uptime_fmt="${hours}h ${mins}m"
        fi
    fi

    echo "${status:-?}|${version:-?}|${uptime_fmt}|${failures:-0}|${dl_state:-?}/${ul_state:-?}"
}

# Check for recent errors in journal
check_errors() {
    local container=$1
    local count
    count=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$container" \
        "journalctl -u wanctl@wan1 --since '1 hour ago' -p err --no-pager 2>/dev/null | grep -v '^-- No entries --$' | grep -c '.' || true" 2>/dev/null)
    echo "${count:-0}" | tr -d '\n'
}

# Check rate limiter activity
check_rate_limits() {
    local container=$1
    local count
    count=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$container" \
        "journalctl -u wanctl@wan1 --since '1 hour ago' --no-pager 2>/dev/null | grep -ci 'rate.limit' 2>/dev/null || true" 2>/dev/null)
    echo "${count:-0}" | tr -d '\n'
}

# Colorize value based on condition
colorize() {
    local value=$1
    local good_pattern=$2
    local bad_pattern=${3:-}

    if [[ -n "$bad_pattern" && "$value" =~ $bad_pattern ]]; then
        echo -e "${RED}${value}${NC}"
    elif [[ "$value" =~ $good_pattern ]]; then
        echo -e "${GREEN}${value}${NC}"
    else
        echo -e "${YELLOW}${value}${NC}"
    fi
}

# Print header
print_header() {
    if $JSON_MODE; then
        return
    fi
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  wanctl Soak Monitor - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}CONTAINER        HEALTH     VERSION      UPTIME     FAILS  STATE        ERR  RL${NC}"
    echo "───────────────────────────────────────────────────────────────────────────────"
}

# Main check function
run_check() {
    print_header

    local all_healthy=true
    local json_output="["

    for i in "${!CONTAINERS[@]}"; do
        local container="${CONTAINERS[$i]}"
        local health_data errors rate_limits

        health_data=$(check_container "$container")

        if $JSON_MODE; then
            errors=$(check_errors "$container")
            rate_limits=$(check_rate_limits "$container")
            [[ $i -gt 0 ]] && json_output+=","
            json_output+="{\"container\":\"$container\",\"health\":$health_data,\"errors_1h\":$errors,\"rate_limits_1h\":$rate_limits}"
            continue
        fi

        # Parse health data
        IFS='|' read -r status version uptime failures state <<< "$health_data"

        errors=$(check_errors "$container")
        rate_limits=$(check_rate_limits "$container")

        # Colorize values
        local c_status c_fails c_state c_errors

        case "$status" in
            healthy) c_status="${GREEN}healthy${NC}" ;;
            degraded) c_status="${YELLOW}degraded${NC}" ;;
            *) c_status="${RED}${status}${NC}"; all_healthy=false ;;
        esac

        if [[ "$failures" == "0" ]]; then
            c_fails="${GREEN}${failures}${NC}"
        else
            c_fails="${RED}${failures}${NC}"
            all_healthy=false
        fi

        case "$state" in
            GREEN/GREEN) c_state="${GREEN}${state}${NC}" ;;
            *RED*) c_state="${RED}${state}${NC}" ;;
            *YELLOW*) c_state="${YELLOW}${state}${NC}" ;;
            *) c_state="$state" ;;
        esac

        if [[ "$errors" == "0" ]]; then
            c_errors="${GREEN}${errors}${NC}"
        elif [[ "$errors" =~ ^[0-9]+$ && "$errors" -gt 0 ]]; then
            c_errors="${RED}${errors}${NC}"
        else
            c_errors="$errors"
        fi

        # Print row
        printf "%-16s " "$container"
        echo -en "$c_status"
        printf "%*s" $((11 - ${#status})) ""
        printf "%-12s %-10s " "$version" "$uptime"
        echo -en "$c_fails"
        printf "%*s" $((6 - ${#failures})) ""
        echo -en "$c_state"
        printf "%*s" $((13 - ${#state})) ""
        echo -en "$c_errors"
        printf "%*s" $((5 - ${#errors})) ""
        echo "$rate_limits"
    done

    if $JSON_MODE; then
        echo "${json_output}]"
        return
    fi

    # Summary
    echo ""
    if $all_healthy; then
        echo -e "${GREEN}${BOLD}✓ All containers healthy${NC}"
    else
        echo -e "${RED}${BOLD}✗ Issues detected - investigate with: journalctl -u wanctl@wan1 -n 50${NC}"
    fi
    echo ""
}

# Main
if $WATCH_MODE; then
    echo "Starting continuous monitoring (Ctrl+C to stop)..."
    sleep 1
    while true; do
        clear
        run_check
        echo -e "${BLUE}Refreshing in ${CHECK_INTERVAL}s... (Ctrl+C to stop)${NC}"
        sleep $CHECK_INTERVAL
    done
else
    run_check
fi

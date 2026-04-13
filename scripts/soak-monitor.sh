#!/bin/bash
# soak-monitor.sh - Soak period monitoring for wanctl
# Usage: ./soak-monitor.sh [--watch] [--json]
#
# Run once for status check, or with --watch for continuous monitoring

set -euo pipefail

# Configuration - cake-shaper VM with WAN-specific health IPs
TARGETS=(
    "kevin@10.10.110.223|spectrum|10.10.110.223"
    "kevin@10.10.110.223|att|10.10.110.227"
)
SERVICE_UNITS=(
    "wanctl@spectrum.service"
    "wanctl@att.service"
    "steering.service"
)
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

# Check single target health
check_target() {
    local ssh_target=$1
    local wan_name=$2
    local health_ip=$3
    local health_json

    # Fetch health data
    if ! health_json=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" "curl -s http://${health_ip}:${HEALTH_PORT}/health" 2>/dev/null); then
        echo "UNREACHABLE|?|?|?|?/?|?|?|?"
        return 1
    fi

    if [[ -z "$health_json" || "$health_json" == "null" ]]; then
        echo "NO_RESPONSE|?|?|?|?/?|?|?|?"
        return 1
    fi

    if $JSON_MODE; then
        echo "$health_json"
        return 0
    fi

    local status version uptime failures dl_state ul_state drop_rate backlog peak_delay

    if $HAS_JQ; then
        status=$(echo "$health_json" | jq -r '.status // "unknown"')
        version=$(echo "$health_json" | jq -r '.version // "?"')
        uptime=$(echo "$health_json" | jq -r '.uptime_seconds // 0')
        failures=$(echo "$health_json" | jq -r '.consecutive_failures // 0')
        dl_state=$(echo "$health_json" | jq -r '.wans[0].download.state // "?"')
        ul_state=$(echo "$health_json" | jq -r '.wans[0].upload.state // "?"')
        # CAKE signal data
        drop_rate=$(echo "$health_json" | jq -r '.wans[0].cake_signal.download.drop_rate // "-"')
        backlog=$(echo "$health_json" | jq -r '.wans[0].cake_signal.download.backlog_bytes // "-"')
        peak_delay=$(echo "$health_json" | jq -r '.wans[0].cake_signal.download.peak_delay_us // "-"')
    else
        # Fallback to python parsing (more reliable than sed for nested JSON)
        eval "$(echo "$health_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
w = d.get('wans', [{}])[0]
cs = w.get('cake_signal', {}).get('download', {})
print(f'status=\"{d.get(\"status\", \"?\")}\"')
print(f'version=\"{d.get(\"version\", \"?\")}\"')
print(f'uptime=\"{d.get(\"uptime_seconds\", 0)}\"')
print(f'failures=\"{d.get(\"consecutive_failures\", 0)}\"')
print(f'dl_state=\"{w.get(\"download\", {}).get(\"state\", \"?\")}\"')
print(f'ul_state=\"{w.get(\"upload\", {}).get(\"state\", \"?\")}\"')
print(f'drop_rate=\"{cs.get(\"drop_rate\", \"-\")}\"')
print(f'backlog=\"{cs.get(\"backlog_bytes\", \"-\")}\"')
print(f'peak_delay=\"{cs.get(\"peak_delay_us\", \"-\")}\"')
" 2>/dev/null)" || true
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

    # Format CAKE signal values
    local cake_str="-"
    if [[ "$drop_rate" != "-" && "$drop_rate" != "null" ]]; then
        local dr_fmt bl_fmt pd_fmt
        dr_fmt=$(printf "%.0f" "$drop_rate" 2>/dev/null || echo "$drop_rate")
        bl_fmt=$(echo "$backlog" | awk '{if($1>1048576)printf "%.1fM",$1/1048576; else if($1>1024)printf "%.0fK",$1/1024; else printf "%d",$1}' 2>/dev/null || echo "$backlog")
        pd_fmt=$(printf "%.1f" "$(echo "$peak_delay / 1000" | bc -l 2>/dev/null || echo 0)" 2>/dev/null || echo "$peak_delay")
        cake_str="${dr_fmt}d/s ${bl_fmt} ${pd_fmt}ms"
    fi

    echo "${status:-?}|${version:-?}|${uptime_fmt}|${failures:-0}|${dl_state:-?}/${ul_state:-?}|${cake_str}"
}

# Check for recent errors in journal
check_errors() {
    local ssh_target=$1
    shift
    local unit_args=()
    local unit
    local count

    for unit in "$@"; do
        unit_args+=(-u "$unit")
    done

    count=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" \
        "journalctl ${unit_args[*]} --since '1 hour ago' -p err --no-pager 2>/dev/null | grep -v '^-- No entries --$' | grep -c '.' || true" 2>/dev/null)
    echo "${count:-0}" | tr -d '\n'
}

# Print header
print_header() {
    if $JSON_MODE; then
        return
    fi
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  wanctl Soak Monitor - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}WAN        HEALTH     VERSION   UPTIME     FAILS  STATE        CAKE SIGNAL           ERR${NC}"
    echo "───────────────────────────────────────────────────────────────────────────────────────────"
}

# Main check function
run_check() {
    print_header

    local all_healthy=true
    local json_output="["

    for i in "${!TARGETS[@]}"; do
        IFS='|' read -r ssh_target wan_name health_ip <<< "${TARGETS[$i]}"
        local health_data errors

        health_data=$(check_target "$ssh_target" "$wan_name" "$health_ip")

        if $JSON_MODE; then
            errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
            [[ $i -gt 0 ]] && json_output+=","
            json_output+="{\"wan\":\"$wan_name\",\"health\":$health_data,\"errors_1h\":$errors}"
            continue
        fi

        # Parse health data
        IFS='|' read -r status version uptime failures state cake_str <<< "$health_data"

        errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")

        # Colorize values
        local c_status c_fails c_state c_errors c_cake

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

        # Colorize CAKE signal
        if [[ "$cake_str" == "-" ]]; then
            c_cake="${BLUE}disabled${NC}"
        else
            c_cake="$cake_str"
        fi

        # Print row
        printf "%-10s " "$wan_name"
        echo -en "$c_status"
        printf "%*s" $((11 - ${#status})) ""
        printf "%-9s %-10s " "$version" "$uptime"
        echo -en "$c_fails"
        printf "%*s" $((6 - ${#failures})) ""
        echo -en "$c_state"
        printf "%*s" $((13 - ${#state})) ""
        echo -en "$c_cake"
        printf "%*s" $((22 - ${#cake_str})) ""
        echo -e "$c_errors"
    done

    if $JSON_MODE; then
        local service_errors
        service_errors=$(check_errors "kevin@10.10.110.223" "${SERVICE_UNITS[@]}")
        if [[ "$json_output" != "[" ]]; then
            json_output+=","
        fi
        json_output+="{\"service_group\":\"all-claimed-services\",\"units\":[\"wanctl@spectrum.service\",\"wanctl@att.service\",\"steering.service\"],\"errors_1h\":$service_errors}"
        echo "${json_output}]"
        return
    fi

    # Summary
    echo ""
    local service_errors
    service_errors=$(check_errors "kevin@10.10.110.223" "${SERVICE_UNITS[@]}")
    echo "Service error scan (1h): wanctl@spectrum.service, wanctl@att.service, steering.service => ${service_errors}"
    if $all_healthy; then
        echo -e "${GREEN}${BOLD}✓ All WANs healthy${NC}"
    else
        echo -e "${RED}${BOLD}✗ Issues detected - investigate with: ssh kevin@10.10.110.223 'journalctl -u wanctl@spectrum.service -u wanctl@att.service -u steering.service -n 50'${NC}"
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

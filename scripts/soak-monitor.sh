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

# Fetch Spectrum state from the temporary cake-autorate trial bridge when
# wanctl@spectrum.service is intentionally inactive and its /health endpoint is
# unavailable. This keeps soak-monitor useful during cake-autorate A/B trials
# without pretending the normal wanctl controller is running.
check_spectrum_cake_autorate_state() {
    local ssh_target=$1

    ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" 'sudo -n python3 - <<'"'"'PY'"'"'
import json
import subprocess
import time
from pathlib import Path

STATE = Path("/var/lib/wanctl/spectrum_state.json")
MAX_STATE_AGE_SECONDS = 15

def run(*args):
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).stdout.strip()
    except Exception:
        return ""

def service_active(unit):
    return run("systemctl", "is-active", unit) == "active"

def link_lower_up(dev):
    out = run("ip", "-br", "link", "show", "dev", dev)
    return "LOWER_UP" in out

def qdisc_bandwidth(dev):
    out = run("tc", "qdisc", "show", "dev", dev)
    if " qdisc cake " not in f" {out} ":
        return None
    parts = out.split()
    try:
        i = parts.index("bandwidth")
        return parts[i + 1]
    except Exception:
        return "cake"

now = time.time()
issues = []
state = {}
age = None
if not STATE.exists():
    issues.append("missing_state_file")
else:
    try:
        age = now - STATE.stat().st_mtime
        state = json.loads(STATE.read_text())
    except Exception as exc:
        issues.append(f"state_parse_error:{type(exc).__name__}")
    if age is not None and age > MAX_STATE_AGE_SECONDS:
        issues.append(f"stale_state:{age:.1f}s")

if not service_active("cake-autorate-spectrum.service"):
    issues.append("cake_autorate_inactive")
if service_active("wanctl@spectrum.service"):
    issues.append("wanctl_spectrum_active_during_cake_trial")
if not service_active("cake-autorate-spectrum-state-bridge.service"):
    issues.append("state_bridge_inactive")
for dev in ("spec-router", "spec-modem"):
    if not link_lower_up(dev):
        issues.append(f"{dev}_no_carrier")

dl_qdisc = qdisc_bandwidth("spec-router")
ul_qdisc = qdisc_bandwidth("spec-modem")
if dl_qdisc is None:
    issues.append("spec-router_no_cake")
if ul_qdisc is None:
    issues.append("spec-modem_no_cake")

last = state.get("last_applied") or {}
dl_rate = last.get("dl_rate") or state.get("download", {}).get("current_rate")
ul_rate = last.get("ul_rate") or state.get("upload", {}).get("current_rate")
cong = state.get("congestion") or {}
dl_state = cong.get("dl_state") or state.get("download", {}).get("state") or "?"
ul_state = cong.get("ul_state") or state.get("upload", {}).get("state") or "?"

status = "healthy" if not issues and dl_state == "GREEN" and ul_state == "GREEN" else "degraded"

def mbps(v):
    try:
        return round(float(v) / 1_000_000, 3)
    except Exception:
        return None

health = {
    "status": status,
    "version": "cake-autorate-trial",
    "uptime_seconds": None,
    "consecutive_failures": 0 if status == "healthy" else len(issues),
    "source": "cake-autorate-state-bridge",
    "state_age_seconds": None if age is None else round(age, 1),
    "issues": issues,
    "wan_count": 1,
    "wans": [
        {
            "name": "spectrum",
            "download": {
                "current_rate_mbps": mbps(dl_rate),
                "state": dl_state,
                "state_reason": "cake_autorate_state_bridge",
                "qdisc_bandwidth": dl_qdisc,
            },
            "upload": {
                "current_rate_mbps": mbps(ul_rate),
                "state": ul_state,
                "state_reason": "cake_autorate_state_bridge",
                "qdisc_bandwidth": ul_qdisc,
            },
            "cake_autorate": {
                "service_active": service_active("cake-autorate-spectrum.service"),
                "state_bridge_active": service_active("cake-autorate-spectrum-state-bridge.service"),
                "wanctl_service_active": service_active("wanctl@spectrum.service"),
                "spec_router_lower_up": link_lower_up("spec-router"),
                "spec_modem_lower_up": link_lower_up("spec-modem"),
            },
        }
    ],
}
print(json.dumps(health, separators=(",", ":")))
PY'
}

# Check single target health
check_target() {
    local ssh_target=$1
    local wan_name=$2
    local health_ip=$3
    local health_json

    # Fetch health data. During the Spectrum cake-autorate trial the normal
    # wanctl /health endpoint is intentionally down, so fall back to the bridge
    # state instead of marking the WAN unreachable.
    if ! health_json=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" "curl -fsS --max-time 3 http://${health_ip}:${HEALTH_PORT}/health" 2>/dev/null); then
        if [[ "$wan_name" == "spectrum" ]]; then
            health_json=$(check_spectrum_cake_autorate_state "$ssh_target" 2>/dev/null || true)
        fi
    fi

    if [[ -z "$health_json" || "$health_json" == "null" ]]; then
        echo "UNREACHABLE|?|?|?|?/?|-"
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
        if [[ "$drop_rate" == "-" && "$(echo "$health_json" | jq -r '.source // ""')" == "cake-autorate-state-bridge" ]]; then
            drop_rate="rates"
            backlog=$(echo "$health_json" | jq -r '(.wans[0].download.qdisc_bandwidth // "?") + "/" + (.wans[0].upload.qdisc_bandwidth // "?")')
            peak_delay="0"
        fi
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
    if [[ "$drop_rate" == "rates" ]]; then
        cake_str="rates ${backlog}"
    elif [[ "$drop_rate" != "-" && "$drop_rate" != "null" ]]; then
        local dr_fmt bl_fmt pd_fmt
        dr_fmt=$(printf "%.0f" "$drop_rate" 2>/dev/null || echo "$drop_rate")
        bl_fmt=$(echo "$backlog" | awk '{if($1>1048576)printf "%.1fM",$1/1048576; else if($1>1024)printf "%.0fK",$1/1024; else printf "%d",$1}' 2>/dev/null || echo "$backlog")
        pd_fmt=$(printf "%.1f" "$(echo "$peak_delay / 1000" | bc -l 2>/dev/null || echo 0)" 2>/dev/null || echo "$peak_delay")
        cake_str="${dr_fmt}d/s ${bl_fmt} ${pd_fmt}ms"
    fi

    echo "${status:-?}|${version:-?}|${uptime_fmt}|${failures:-0}|${dl_state:-?}/${ul_state:-?}|${cake_str}"
}

# Check whether a WAN is currently in external cake-autorate mode rather than
# normal wanctl@ control. WAN names come from the in-repo TARGETS literals.
is_external_cake_mode() {
    local ssh_target=$1 wan=$2
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" \
        "test \"\$(systemctl is-active cake-autorate-${wan}.service 2>/dev/null)\" = active \
         && test \"\$(systemctl is-active wanctl@${wan}.service 2>/dev/null)\" != active" \
        >/dev/null 2>&1
}

# Units owned by the external cake-autorate controller for a WAN.
external_units_for() {
    case "$1" in
        att) echo "cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service" ;;
        *) echo "cake-autorate-$1.service cake-autorate-$1-state-bridge.service" ;;
    esac
}

aggregate_ssh_target() {
    local ssh_target _wan_name _health_ip
    IFS='|' read -r ssh_target _wan_name _health_ip <<< "${TARGETS[0]}"
    echo "$ssh_target"
}

aggregate_units_for() {
    local aggregate_ssh=$1
    local target ssh_target wan_name health_ip
    local -a wan_units

    for target in "${TARGETS[@]}"; do
        IFS='|' read -r ssh_target wan_name health_ip <<< "$target"
        if is_external_cake_mode "$ssh_target" "$wan_name"; then
            read -r -a wan_units <<< "$(external_units_for "$wan_name")"
            printf '%s\n' "${wan_units[@]}"
        else
            printf 'wanctl@%s.service\n' "$wan_name"
        fi
    done
    printf '%s\n' "steering.service"

    # The aggregate scan is intentionally single-target because current TARGETS
    # share the cake-shaper ssh host; keep the target derived from TARGETS.
    : "$aggregate_ssh"
}

json_array_for_units() {
    local unit json="[" separator=""
    for unit in "$@"; do
        json+="${separator}\"${unit}\""
        separator=","
    done
    json+="]"
    echo "$json"
}

join_units_for_label() {
    local unit label="" separator=""
    for unit in "$@"; do
        label+="${separator}${unit}"
        separator=", "
    done
    echo "$label"
}

journalctl_hint_for_units() {
    local unit hint="journalctl"
    for unit in "$@"; do
        hint+=" -u ${unit}"
    done
    echo "$hint -n 50"
}

# Check whether Spectrum is currently in the cake-autorate trial mode rather
# than normal wanctl@spectrum control.
is_spectrum_cake_trial_active() {
    local ssh_target=$1
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" \
        'test "$(systemctl is-active cake-autorate-spectrum.service 2>/dev/null)" = active && test "$(systemctl is-active wanctl@spectrum.service 2>/dev/null)" != active' \
        >/dev/null 2>&1
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
            if is_external_cake_mode "$ssh_target" "$wan_name"; then
                # If both external and native units are active, fall back to native-unit scanning.
                local -a wan_units
                read -r -a wan_units <<< "$(external_units_for "$wan_name")"
                errors=$(check_errors "$ssh_target" "${wan_units[@]}")
            else
                errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
            fi
            [[ $i -gt 0 ]] && json_output+=","
            json_output+="{\"wan\":\"$wan_name\",\"health\":$health_data,\"errors_1h\":$errors}"
            continue
        fi

        # Parse health data
        IFS='|' read -r status version uptime failures state cake_str <<< "$health_data"

        if is_external_cake_mode "$ssh_target" "$wan_name"; then
            # If both external and native units are active, fall back to native-unit scanning.
            local -a wan_units
            read -r -a wan_units <<< "$(external_units_for "$wan_name")"
            errors=$(check_errors "$ssh_target" "${wan_units[@]}")
        else
            errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
        fi

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
        local service_errors service_units_json service_ssh_target
        local -a service_units
        service_ssh_target=$(aggregate_ssh_target)
        mapfile -t service_units < <(aggregate_units_for "$service_ssh_target")
        service_errors=$(check_errors "$service_ssh_target" "${service_units[@]}")
        service_units_json=$(json_array_for_units "${service_units[@]}")
        if [[ "$json_output" != "[" ]]; then
            json_output+=","
        fi
        json_output+="{\"service_group\":\"all-claimed-services\",\"units\":${service_units_json},\"errors_1h\":$service_errors}"
        echo "${json_output}]"
        return
    fi

    # Summary
    echo ""
    local service_errors service_label service_ssh_target journal_hint
    local -a service_units
    service_ssh_target=$(aggregate_ssh_target)
    mapfile -t service_units < <(aggregate_units_for "$service_ssh_target")
    service_errors=$(check_errors "$service_ssh_target" "${service_units[@]}")
    service_label=$(join_units_for_label "${service_units[@]}")
    journal_hint=$(journalctl_hint_for_units "${service_units[@]}")
    echo "Service error scan (1h): ${service_label} => ${service_errors}"
    if [[ "$service_errors" =~ ^[0-9]+$ && "$service_errors" -gt 0 ]]; then
        echo -e "${YELLOW}${BOLD}⚠ WAN state is healthy, but recent service errors exist in the 1h journal window${NC}"
    elif $all_healthy; then
        echo -e "${GREEN}${BOLD}✓ All WANs healthy${NC}"
    else
        echo -e "${RED}${BOLD}✗ Issues detected - investigate with: ssh ${service_ssh_target} '${journal_hint}'${NC}"
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

#!/bin/bash
# Simple CAKE Status Dashboard

ATT_HOST="10.10.110.247"
SPECTRUM_HOST="10.10.110.246"
SSH_USER="kevin"
STATE_DIR="/home/kevin/wanctl"

clear
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║           CAKE Auto-Tuning System Status                                  ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Function to get WAN status
get_wan_status() {
    local HOST=$1
    local NAME=$2
    local STATE_FILE=$3

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " $NAME ($HOST)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Get state file
    local STATE=$(ssh ${SSH_USER}@${HOST} "cat ${STATE_FILE} 2>/dev/null")

    if [ -z "$STATE" ]; then
        echo "  ERROR: Could not read state file"
        echo ""
        return
    fi

    # Parse state JSON
    local EWMA_DOWN=$(echo "$STATE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data.get('ewma_down', 0):.1f}\")")
    local EWMA_UP=$(echo "$STATE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data.get('ewma_up', 0):.1f}\")")
    local LAST_DOWN_CAP=$(echo "$STATE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('last_down_cap', 0))")
    local LAST_UP_CAP=$(echo "$STATE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('last_up_cap', 0))")

    # Get last log entry
    local LAST_LOG=$(ssh ${SSH_USER}@${HOST} "tail -100 /home/kevin/wanctl/logs/cake_auto.log 2>/dev/null | grep 'Test complete' | tail -1")

    if [ -n "$LAST_LOG" ]; then
        # Extract timestamp
        local TIMESTAMP=$(echo "$LAST_LOG" | awk '{print $1, $2}')

        # Extract measurements
        local DOWN_MBPS=$(echo "$LAST_LOG" | grep -oP 'DOWN=\K[0-9.]+')
        local UP_MBPS=$(echo "$LAST_LOG" | grep -oP 'UP=\K[0-9.]+')
        local DOWN_BLOAT=$(echo "$LAST_LOG" | grep -oP '\(bloat=\K[0-9.]+' | head -1)
        local UP_BLOAT=$(echo "$LAST_LOG" | grep -oP '\(bloat=\K[0-9.]+' | tail -1)

        echo "  Last Test: $TIMESTAMP"
        echo ""
        echo "  Measured:"
        echo "    Download: ${DOWN_MBPS} Mbps (bloat: ${DOWN_BLOAT}ms)"
        echo "    Upload:   ${UP_MBPS} Mbps (bloat: ${UP_BLOAT}ms)"
    else
        echo "  No test data available"
    fi

    echo ""
    echo "  Current CAKE Limits:"
    printf "    Download: %d Mbps\n" $((LAST_DOWN_CAP / 1000000))
    printf "    Upload:   %d Mbps\n" $((LAST_UP_CAP / 1000000))

    echo ""
    echo "  EWMA Smoothed:"
    echo "    Download: ${EWMA_DOWN} Mbps"
    echo "    Upload:   ${EWMA_UP} Mbps"

    echo ""
}

# Get status for both WANs
get_wan_status "$ATT_HOST" "ATT" "${STATE_DIR}/att_state.json"
get_wan_status "$SPECTRUM_HOST" "Spectrum" "${STATE_DIR}/spectrum_state.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Bloat Guide: <5ms = Good | 5-15ms = Moderate | >15ms = High"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Refresh: $0"
echo "Watch logs: ssh kevin@$ATT_HOST 'tail -f /home/kevin/wanctl/logs/cake_auto.log'"
echo ""

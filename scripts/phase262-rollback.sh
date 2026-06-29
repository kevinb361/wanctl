#!/usr/bin/env bash
# phase262-rollback.sh — Manual one-command rollback from wanctl to Netwatch ownership.
#
# Usage:
#   scripts/phase262-rollback.sh [cake-shaper]
#
# Changes steering.yaml mode from "active" to "dry_run" and sends SIGUSR1 to the
# steering daemon, which triggers the revert sequence (re-enable Netwatch routes,
# disable wanctl routes, reset circuit breaker).
#
# If the target host argument is provided, the script SSHs to that host and runs
# the rollback remotely. Otherwise, it runs locally (for direct host execution).

set -euo pipefail

TARGET_HOST="${1:-}"
STEERING_YAML="/etc/wanctl/steering.yaml"
HEALTH_URL="http://127.0.0.1:9102/health"

rollback() {
    echo "=== Phase 262 Manual Rollback ==="

    # Step 1: Verify current mode is "active"
    current_mode=$(grep -A1 'route_management:' "$STEERING_YAML" | grep 'mode:' | head -1 | sed 's/.*mode: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d ' ')
    if [ "$current_mode" != "active" ]; then
        echo "ERROR: route_management.mode is '$current_mode', not 'active'. No rollback needed."
        exit 1
    fi

    echo "Current mode: active — proceeding with rollback"

    # Step 2: Change mode to dry_run
    sed -i 's/^  mode: "active"/  mode: "dry_run"/' "$STEERING_YAML"
    echo "Updated steering.yaml mode: active -> dry_run"

    # Step 3: Send SIGUSR1 to steering daemon to trigger config reload + revert
    # The daemon calls _handle_mode_change() which triggers abort_to_netwatch()
    steering_pid=$(pgrep -f "python.*steering.*daemon" || pgrep -f "steering.service" || true)
    if [ -n "$steering_pid" ]; then
        echo "Sending SIGUSR1 to steering daemon (PID: $steering_pid)"
        kill -USR1 "$steering_pid"
    else
        # Fallback: restart steering.service
        echo "Steering daemon not found via pgrep — restarting steering.service"
        systemctl restart steering.service
    fi

    # Step 4: Wait for daemon to process the reload
    echo "Waiting for steering daemon to process rollback..."
    sleep 3

    # Step 5: Verify via health endpoint
    echo "Verifying rollback via health endpoint..."
    health=$(curl -s "$HEALTH_URL" || echo '{}')
    mode=$(echo "$health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('route_management',{}).get('mode','unknown'))" 2>/dev/null || echo "unknown")
    owner=$(echo "$health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('route_management',{}).get('active_owner','unknown'))" 2>/dev/null || echo "unknown")
    abort=$(echo "$health" | python3 -c "import sys,json; a=json.load(sys.stdin).get('route_management',{}).get('last_abort'); print('YES' if a else 'NO')" 2>/dev/null || echo "NO")

    echo "Post-rollback status:"
    echo "  mode: $mode"
    echo "  active_owner: $owner"
    echo "  last_abort: $abort"

    if [ "$mode" = "dry_run" ] && [ "$abort" = "YES" ]; then
        echo "=== ROLLBACK COMPLETE ==="
        exit 0
    else
        echo "WARNING: Rollback may not have completed fully."
        echo "  Expected mode=dry_run, got mode=$mode"
        echo "  Expected last_abort=YES, got last_abort=$abort"
        exit 1
    fi
}

if [ -n "$TARGET_HOST" ]; then
    echo "Running rollback on host: $TARGET_HOST"
    ssh "$TARGET_HOST" "sudo bash -s" <<'ROLLBACK_EOF'
ROLLBACK_EOF
    # Execute rollback remotely
    ssh "$TARGET_HOST" "sudo bash -c '$(declare -f rollback); rollback'"
else
    sudo rollback
fi

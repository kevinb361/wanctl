# shellcheck shell=bash
# Operator-invoked chaos scenario: long bypass period to verify wanctl recovery
# after extended time without the host in the data path.
# Sourced by silicom-test (not executed) so restore handlers remain in scope.

PAIR="${1:-spec-modem}"
DURATION="${2:-60}"
validate_pair "$PAIR"

"$SILICOM_BYPASS" mark "long-bypass-recovery: PRE duration=${DURATION}s"
capture_state pre
warn_if_degraded_pre_state
start_health_poller

# Enter bypass mode for extended period
run_bypass on "$PAIR" --yes
"$SILICOM_BYPASS" mark "long-bypass-recovery: BYPASS-ENTERED"
capture_state bypass-start

# Stay in bypass for DURATION seconds, capturing periodic snapshots
INTERVAL=15
ELAPSED=0
while [ "$ELAPSED" -lt "$DURATION" ]; do
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
    capture_state "bypass-${ELAPSED}s"
done

"$SILICOM_BYPASS" mark "long-bypass-recovery: BYPASS-EXITING elapsed=${ELAPSED}s"

# Restore to NIC mode and observe recovery
"$SILICOM_BYPASS" off "$PAIR"
"$SILICOM_BYPASS" mark "long-bypass-recovery: NIC-RESTORED"
capture_state post-recovery

# Wait for wanctl to re-stabilize
sleep 20
capture_state post-stable

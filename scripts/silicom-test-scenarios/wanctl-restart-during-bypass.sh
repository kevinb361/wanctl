# shellcheck shell=bash
# Operator-invoked chaos scenario: restart wanctl daemon while bypass is active.
# Sourced by silicom-test (not executed) so restore handlers remain in scope.
# Tests that wanctl recovery works when the WAN path has been manually manipulated.

# Default to Spectrum for safety (ATT is canary in many other workstreams)
PAIR="${1:-spec-modem}"
validate_pair "$PAIR"

"$SILICOM_BYPASS" mark "wanctl-restart-bypass: PRE"
capture_state pre
warn_if_degraded_pre_state

# Put the pair into bypass mode
run_bypass on "$PAIR" --yes
"$SILICOM_BYPASS" mark "wanctl-restart-bypass: BYPASS-ACTIVE"
capture_state bypass-active

# Restart the wanctl service for this WAN
WAN_NAME=$(echo "$PAIR" | sed 's/-modem$//')
journal -t silicom-test "Restarting wanctl@$WAN_NAME during bypass on $PAIR"
systemctl restart "wanctl@$WAN_NAME" 2>&1 | tee -a "$RAW_OUTPUT_REL" || true
"$SILICOM_BYPASS" mark "wanctl-restart-bypass: RESTARTED"

# Wait for wanctl to recover
sleep 15
capture_state post-restart

# Restore to NIC mode
"$SILICOM_BYPASS" off "$PAIR"
"$SILICOM_BYPASS" mark "wanctl-restart-bypass: RESTORED"
capture_state post

# shellcheck shell=bash
# Operator-invoked chaos scenario: pull both WAN pairs simultaneously.
# Sourced by silicom-test (not executed) so restore handlers remain in scope.
# WARNING: requires --both-wan-confirm silicom-bypass guard. Use with caution.

PAIR="spec-modem" # default for health poller; actual ops touch both pairs below

"$SILICOM_BYPASS" mark "dual-wan-loss: PRE"
capture_state pre
warn_if_degraded_pre_state
start_health_poller

# Pull Spectrum first, then ATT — observe which WAN the steering daemon prefers
run_bypass disc spec-modem --yes
"$SILICOM_BYPASS" mark "dual-wan-loss: SPECTRUM-PULLED"
capture_state spectrum-down
sleep 2

run_bypass disc att-modem --yes --both-wan-confirm
"$SILICOM_BYPASS" mark "dual-wan-loss: BOTH-PULLED"
capture_state both-down
sleep "$RECOVERY_WINDOW"

# Restore in reverse order: ATT first, then Spectrum
"$SILICOM_BYPASS" conn att-modem
"$SILICOM_BYPASS" mark "dual-wan-loss: ATT-RESTORED"
capture_state att-up
sleep 2

"$SILICOM_BYPASS" conn spec-modem
"$SILICOM_BYPASS" mark "dual-wan-loss: BOTH-RESTORED"
capture_state post

# shellcheck shell=bash
# Operator-invoked chaos scenario; no schedule registration.
# Sourced by silicom-test (not executed) so restore handlers remain in scope.
# Deployed copies live in the root-owned scenario dir as 0644 files; operators do not edit live copies in place.

cmd_ab_cake att-modem

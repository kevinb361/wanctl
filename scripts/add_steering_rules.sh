#!/usr/bin/env bash
# Deprecated: the original helper created a broad QoS-coupled adaptive route.
# That design can steer recursive DNS toward the wrong WAN and is unsafe.
set -euo pipefail

cat >&2 <<'EOF'
ERROR: scripts/add_steering_rules.sh is retired.

Do not recreate `ADAPTIVE: Steer latency-sensitive to ATT`.
Use the approval-gated migration package in infra-ansible:
  artifacts/network-changes/20260717_routeros-qos-composite-policy/

The supported controller target is the explicit new-connection producer:
  ADAPTIVE: Work VPN eligible for ATT
EOF
exit 2

#!/bin/bash
# Add ADAPTIVE rule in correct position (after CLASSIFY rules)

ROUTER="admin@10.10.99.1"
SSH_KEY="/home/kevin/.ssh/mikrotik_cake"

# Find the rule number for CLASSIFY: QOS_MEDIUM
QOS_MEDIUM_NUM=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" \
  '/ip firewall mangle print terse where comment~"CLASSIFY: QOS_MEDIUM"' | \
  grep -oP '^\s*\K\d+' | head -1)

echo "QOS_MEDIUM CLASSIFY rule is at position: $QOS_MEDIUM_NUM"
echo "Adding ADAPTIVE rule after position $QOS_MEDIUM_NUM..."

# Add the ADAPTIVE rule right after the last CLASSIFY rule
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" \
  "/ip firewall mangle add place-after=$QOS_MEDIUM_NUM chain=prerouting action=mark-routing new-routing-mark=to_ATT passthrough=no connection-state=new connection-mark=LATENCY_SENSITIVE dst-address=!10.10.0.0/16 disabled=yes comment=\"ADAPTIVE: Steer latency-sensitive to ATT\""

echo "Done! Verifying placement..."

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" \
  '/ip firewall mangle export' | grep -B2 -A2 "ADAPTIVE"

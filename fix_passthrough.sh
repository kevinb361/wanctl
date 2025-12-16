#!/bin/bash
# Fix passthrough on upstream QOS marking rules

set -e

ROUTER="admin@10.10.99.1"
SSH_KEY="/home/kevin/.ssh/mikrotik_cake"

run_ros() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" "$1"
}

echo "=================================================="
echo "Fix QOS Marking Rules Passthrough"
echo "=================================================="
echo

echo "Step 1: Finding rules that need passthrough=yes"
echo "------------------------------------------------"
echo "Rules marking as QOS_HIGH:"
run_ros '/ip firewall mangle print terse where new-connection-mark="QOS_HIGH"' | grep -c "passthrough=no" || echo "0"

echo "Rules marking as GAMES:"
run_ros '/ip firewall mangle print terse where new-connection-mark="GAMES"' | grep -c "passthrough=no" || echo "0"

echo "Rules marking as QOS_MEDIUM:"
run_ros '/ip firewall mangle print terse where new-connection-mark="QOS_MEDIUM"' | grep -c "passthrough=no" || echo "0"

echo
echo "Step 2: Setting passthrough=yes on all upstream QOS rules"
echo "----------------------------------------------------------"

echo "Fixing QOS_HIGH rules..."
run_ros '/ip firewall mangle set [find new-connection-mark="QOS_HIGH" and passthrough=no] passthrough=yes'
echo "✓ QOS_HIGH rules fixed"

echo "Fixing GAMES rules..."
run_ros '/ip firewall mangle set [find new-connection-mark="GAMES" and passthrough=no] passthrough=yes'
echo "✓ GAMES rules fixed"

echo "Fixing QOS_MEDIUM rules..."
run_ros '/ip firewall mangle set [find new-connection-mark="QOS_MEDIUM" and passthrough=no] passthrough=yes'
echo "✓ QOS_MEDIUM rules fixed"

echo
echo "Step 3: Verifying CLASSIFY rules have passthrough=no"
echo "-----------------------------------------------------"
run_ros '/ip firewall mangle print detail where comment~"CLASSIFY"' | grep passthrough

echo
echo "Step 4: Summary"
echo "---------------"
echo "✓ All upstream QOS marking rules now have passthrough=yes"
echo "✓ Packets will continue to CLASSIFY rules"
echo "✓ CLASSIFY rules will translate to LATENCY_SENSITIVE (passthrough=no)"
echo "✓ ADAPTIVE rule will route LATENCY_SENSITIVE to ATT"
echo
echo "=================================================="
echo "Done! Test by reconnecting to Mumble or Discord"
echo "=================================================="

#!/bin/bash
# Verify traffic steering is working

set -e

ROUTER="admin@10.10.99.1"
SSH_KEY="/home/kevin/.ssh/mikrotik_cake"

echo "=================================="
echo "Traffic Steering Verification Test"
echo "=================================="
echo

# Function to run RouterOS commands
run_ros() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" "$1"
}

echo "Step 1: Check current ADAPTIVE rule status"
echo "-------------------------------------------"
run_ros '/ip firewall mangle print where comment~"ADAPTIVE"'
echo

echo "Step 2: Enable ADAPTIVE rule for testing"
echo "-----------------------------------------"
run_ros '/ip firewall mangle enable [find comment~"ADAPTIVE"]'
echo "Rule enabled"
echo

echo "Step 3: Verify rule is enabled"
echo "-------------------------------"
run_ros '/ip firewall mangle print where comment~"ADAPTIVE"' | grep -v "X " || echo "ERROR: Rule still disabled!"
echo

echo "Step 4: Check existing LATENCY_SENSITIVE connections"
echo "-----------------------------------------------------"
echo "Connections with LATENCY_SENSITIVE mark:"
run_ros '/ip firewall connection print where connection-mark="LATENCY_SENSITIVE"' | head -20
echo

echo "Step 5: Check routing marks on connections"
echo "-------------------------------------------"
echo "Connections with to_ATT routing mark:"
run_ros '/ip firewall connection print where routing-mark="to_ATT"' | head -20
echo

echo "Step 6: Generate test traffic and check routing"
echo "------------------------------------------------"
echo "Testing with ping (should be marked as latency-sensitive)..."
echo "Running ping to 1.1.1.1 in background..."
ping -c 5 1.1.1.1 > /dev/null 2>&1 &
PING_PID=$!

sleep 2

echo
echo "Checking for ICMP connections with LATENCY_SENSITIVE mark:"
run_ros '/ip firewall connection print where protocol="icmp" and connection-mark="LATENCY_SENSITIVE"' || echo "No ICMP LATENCY_SENSITIVE connections found"
echo

echo "Checking for ICMP connections with to_ATT routing mark:"
run_ros '/ip firewall connection print where protocol="icmp" and routing-mark="to_ATT"' || echo "No ICMP to_ATT connections found"
echo

wait $PING_PID 2>/dev/null || true

echo "Step 7: Check routing table hits"
echo "---------------------------------"
echo "ATT routing table (to_ATT):"
run_ros '/routing table print stats where name="to_ATT"' || run_ros '/ip route print where routing-table="to_ATT"'
echo

echo "Step 8: Connection stats summary"
echo "---------------------------------"
echo "Total LATENCY_SENSITIVE connections:"
run_ros '/ip firewall connection print count-only where connection-mark="LATENCY_SENSITIVE"'
echo

echo "Total to_ATT routing mark connections:"
run_ros '/ip firewall connection print count-only where routing-mark="to_ATT"'
echo

echo "Step 9: Check mangle rule counters"
echo "-----------------------------------"
echo "ADAPTIVE rule hit counter:"
run_ros '/ip firewall mangle print stats where comment~"ADAPTIVE"' | grep -A1 "ADAPTIVE"
echo

echo
echo "=================================="
echo "Test Complete!"
echo "=================================="
echo
echo "To disable steering rule again:"
echo "  ssh -i $SSH_KEY $ROUTER '/ip firewall mangle disable [find comment~\"ADAPTIVE\"]'"

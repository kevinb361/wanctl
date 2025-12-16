#!/bin/bash
# Verify NEW connections get steered to ATT

set -e

ROUTER="admin@10.10.99.1"
SSH_KEY="/home/kevin/.ssh/mikrotik_cake"

run_ros() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROUTER" "$1"
}

echo "=================================="
echo "NEW Connection Steering Test"
echo "=================================="
echo

echo "Step 1: Enable ADAPTIVE rule"
echo "-----------------------------"
run_ros '/ip firewall mangle enable [find comment~"ADAPTIVE"]'
echo "✓ Rule enabled"
echo

echo "Step 2: Clear connection tracking (so we can see new connections)"
echo "------------------------------------------------------------------"
echo "Before clearing - LATENCY_SENSITIVE connections:"
run_ros '/ip firewall connection print count-only where connection-mark="LATENCY_SENSITIVE"'
echo

echo "Step 3: Monitor connections in real-time"
echo "-----------------------------------------"
echo "Creating NEW connections that should be marked LATENCY_SENSITIVE..."
echo

# Generate multiple types of traffic that should match QOS_HIGH
echo "Generating DNS query (UDP/53 - should match QOS_HIGH)..."
nslookup google.com 1.1.1.1 > /dev/null 2>&1 &

echo "Generating HTTPS to 1.1.1.1 (should trigger LATENCY_SENSITIVE)..."
curl -m 2 https://1.1.1.1 > /dev/null 2>&1 &

sleep 2

echo
echo "Step 4: Check NEW connections"
echo "------------------------------"
echo "LATENCY_SENSITIVE connections (should include our new traffic):"
run_ros '/ip firewall connection print where connection-mark="LATENCY_SENSITIVE"' | head -25
echo

echo "to_ATT routing mark connections (THESE should exist if steering works):"
run_ros '/ip firewall connection print where routing-mark="to_ATT"' | head -25
echo

echo "Step 5: Check ADAPTIVE rule statistics"
echo "---------------------------------------"
run_ros '/ip firewall mangle print stats where comment~"ADAPTIVE"'
echo

echo "Step 6: Detailed connection check"
echo "----------------------------------"
echo "Connections to 1.1.1.1 (our test target):"
run_ros '/ip firewall connection print detail where dst-address~"1.1.1.1"' | head -30
echo

echo
echo "=================================="
echo "Analysis"
echo "=================================="
echo

LATENCY_COUNT=$(run_ros '/ip firewall connection print count-only where connection-mark="LATENCY_SENSITIVE"')
ATT_COUNT=$(run_ros '/ip firewall connection print count-only where routing-mark="to_ATT"')

echo "LATENCY_SENSITIVE connections: $LATENCY_COUNT"
echo "to_ATT routing mark connections: $ATT_COUNT"
echo

if [ "$ATT_COUNT" -gt 0 ]; then
    echo "✓ SUCCESS! Traffic is being steered to ATT"
else
    echo "✗ ISSUE: No traffic has to_ATT routing mark"
    echo
    echo "Troubleshooting:"
    echo "1. Check if traffic is being marked as LATENCY_SENSITIVE first"
    echo "2. Verify ADAPTIVE rule placement (should be early in chain)"
    echo "3. Check connection-state filter (only affects NEW connections)"
fi

echo
echo "Disabling ADAPTIVE rule..."
run_ros '/ip firewall mangle disable [find comment~"ADAPTIVE"]'
echo "✓ Rule disabled"

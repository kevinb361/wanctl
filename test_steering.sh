#!/bin/bash
#
# Test Script for WAN Steering
# Run this ON THE CAKE-SPECTRUM CONTAINER after stopping autorate_continuous timer
#
set -e

echo "=========================================="
echo " WAN Steering Test"
echo "=========================================="
echo ""
echo "PREREQUISITE: You must stop autorate_continuous first!"
echo "Run: sudo systemctl stop cake-spectrum-continuous.timer"
echo ""
read -p "Press Enter when autorate is stopped, or Ctrl-C to abort..."
echo ""

# Verify we're on the right container
if [ ! -f /home/kevin/wanctl/wan_steering_daemon.py ]; then
    echo "ERROR: This script must run on cake-spectrum container (10.10.110.246)"
    echo "Run: ssh kevin@10.10.110.246"
    echo "Then: bash /home/kevin/CAKE/test_steering.sh"
    exit 1
fi

# Verify we can access RouterOS
echo "[1/5] Testing RouterOS access..."
ssh -i /home/kevin/.ssh/mikrotik_cake -o StrictHostKeyChecking=no admin@10.10.99.1 '/system resource print' | grep -q "version" && echo "✓ RouterOS accessible"
echo ""

# Show current state
echo "[2/5] Current steering state:"
if [ -f /home/kevin/adaptive_cake_steering/steering_state.json ]; then
    cat /home/kevin/adaptive_cake_steering/steering_state.json | grep -E "(current_state|bad_count|good_count|baseline_rtt)" | head -4
else
    echo "State file not found (daemon hasn't run yet?)"
fi
echo ""

# Throttle Spectrum
echo "[3/5] Throttling Spectrum to 3 Mbps..."
ssh -i /home/kevin/.ssh/mikrotik_cake -o StrictHostKeyChecking=no admin@10.10.99.1 \
  '/queue tree set WAN-Download-Spectrum limit-at=3M max-limit=3M'

# Verify throttle
CURRENT=$(ssh -i /home/kevin/.ssh/mikrotik_cake -o StrictHostKeyChecking=no admin@10.10.99.1 \
  '/queue tree print where name=WAN-Download-Spectrum' | grep -o 'max-limit=[^ ]*')
echo "✓ Spectrum throttled: $CURRENT"
echo ""

# Start download in background
echo "[4/5] Starting download to saturate link..."
wget -q -O /dev/null http://speedtest.tele2.net/100MB.zip &
WGET_PID=$!
echo "✓ Download started (PID: $WGET_PID)"
echo ""

# Watch for state transition
echo "[5/5] Watching for state transition (40 seconds)..."
echo "Looking for bad_count to reach 8/8 and transition to DEGRADED..."
echo ""

for i in {1..20}; do
    sleep 2
    LOGLINE=$(tail -1 /home/kevin/wanctl/logs/steering.log)

    # Extract key metrics
    if echo "$LOGLINE" | grep -q "RTT="; then
        RTT=$(echo "$LOGLINE" | grep -o 'RTT=[0-9.]*ms' | cut -d= -f2)
        DELTA=$(echo "$LOGLINE" | grep -o 'delta=[0-9.]*ms' | cut -d= -f2)
        BAD=$(echo "$LOGLINE" | grep -o 'bad_count=[0-9]*/[0-9]*' | cut -d= -f2)
        STATE=$(echo "$LOGLINE" | grep -o '\[SPECTRUM_[A-Z]*\]')

        printf "[%2ds] %s RTT=%s delta=%s bad_count=%s\n" "$((i*2))" "$STATE" "$RTT" "$DELTA" "$BAD"

        # Check for transition
        if echo "$LOGLINE" | grep -q "DEGRADED"; then
            if [ "$i" -eq 1 ]; then
                echo "Already degraded!"
            else
                echo ""
                echo "=========================================="
                echo " ✓ STATE TRANSITION DETECTED!"
                echo "=========================================="
                break
            fi
        fi
    fi
done

# Kill download
kill $WGET_PID 2>/dev/null || true
echo ""

# Check RouterOS rule status
echo "Checking RouterOS ADAPTIVE rule..."
RULE_STATUS=$(ssh -i /home/kevin/.ssh/mikrotik_cake -o StrictHostKeyChecking=no admin@10.10.99.1 \
  '/ip firewall mangle print where comment~"ADAPTIVE"')

if echo "$RULE_STATUS" | grep -q "^[^X]"; then
    echo "✓ ADAPTIVE rule is ENABLED - steering active!"
else
    echo "✗ ADAPTIVE rule still DISABLED - no state change yet"
fi
echo ""

# Show final state
echo "Final steering state:"
cat /home/kevin/adaptive_cake_steering/steering_state.json | grep -E "(current_state|bad_count|baseline_rtt)" | head -3
echo ""

# Restore
echo "=========================================="
echo " Cleanup"
echo "=========================================="
read -p "Restore Spectrum to normal? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restoring Spectrum to 870 Mbps..."
    ssh -i /home/kevin/.ssh/mikrotik_cake -o StrictHostKeyChecking=no admin@10.10.99.1 \
      '/queue tree set WAN-Download-Spectrum limit-at=0 max-limit=870M'
    echo "✓ Restored"
    echo ""
    echo "Remember to restart autorate:"
    echo "  sudo systemctl start cake-spectrum-continuous.timer"
fi
echo ""
echo "Test complete!"

#!/bin/bash
# ============================================================================
# RB5009 Performance Testing Script
# ============================================================================
# Tests throughput and latency before/after optimization
# Run this BEFORE applying optimization, then again AFTER
# ============================================================================

set -euo pipefail

ROUTER="10.10.99.1"
ROUTER_USER="admin"
SSH_KEY="/home/kevin/.ssh/mikrotik_cake"
TEST_DURATION=30
IPERF_SERVER="104.200.21.31"  # Your netperf server

echo "============================================================================"
echo "RB5009 Performance Benchmark"
echo "============================================================================"
echo "Date: $(date)"
echo ""

# ============================================================================
# 1. Check Current Settings
# ============================================================================
echo "==> Checking current optimization status..."
echo ""

echo "Bridge fast-forward:"
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/interface bridge print detail where name=bridge1' | grep fast-forward

echo ""
echo "IP fast-path:"
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/ip settings print' | grep allow-fast-path

echo ""
echo "FastTrack rules:"
FASTTRACK_COUNT=$(ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/ip firewall filter print count-only where action=fasttrack-connection')
echo "FastTrack rules active: $FASTTRACK_COUNT"

echo ""
echo "WAN packet marking status:"
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/ip firewall mangle print where new-packet-mark~"wan-"' | grep -E "(disabled|wan-in-|wan-out-)" || echo "No WAN marking rules found!"

# ============================================================================
# 2. System Resource Baseline
# ============================================================================
echo ""
echo "==> System resources BEFORE test..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/system resource print' | grep -E "(cpu-load|free-memory)"

# ============================================================================
# 3. Connection Tracking Stats
# ============================================================================
echo ""
echo "==> Connection tracking stats..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/ip firewall connection print count-only'

# ============================================================================
# 4. Run Throughput Tests
# ============================================================================
echo ""
echo "============================================================================"
echo "Running throughput tests (${TEST_DURATION}s each)..."
echo "============================================================================"

# Test download (if iperf3 available)
if command -v iperf3 &> /dev/null; then
    echo ""
    echo "==> TCP Download Test (${TEST_DURATION}s)..."
    iperf3 -c "$IPERF_SERVER" -t "$TEST_DURATION" -P 4 -R 2>&1 | tee /tmp/perf_download.txt | grep -E "(sender|receiver|Mbits)"

    echo ""
    echo "==> TCP Upload Test (${TEST_DURATION}s)..."
    iperf3 -c "$IPERF_SERVER" -t "$TEST_DURATION" -P 4 2>&1 | tee /tmp/perf_upload.txt | grep -E "(sender|receiver|Mbits)"
else
    echo "iperf3 not found, skipping bandwidth tests"
    echo "Install with: sudo apt install iperf3"
fi

# ============================================================================
# 5. Latency Tests
# ============================================================================
echo ""
echo "============================================================================"
echo "Running latency tests..."
echo "============================================================================"

echo ""
echo "==> Baseline latency (idle)..."
ping -c 20 -i 0.2 8.8.8.8 | tail -1

echo ""
echo "==> Latency under load (during upload)..."
if command -v iperf3 &> /dev/null; then
    # Start background upload
    iperf3 -c "$IPERF_SERVER" -t 20 -P 4 > /dev/null 2>&1 &
    IPERF_PID=$!
    sleep 2  # Let upload stabilize

    # Measure latency during upload
    ping -c 15 -i 0.5 8.8.8.8 | tail -1

    # Kill background upload
    kill $IPERF_PID 2>/dev/null || true
    wait $IPERF_PID 2>/dev/null || true
fi

# ============================================================================
# 6. System Resource After Test
# ============================================================================
echo ""
echo "==> System resources AFTER test..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/system resource print' | grep -E "(cpu-load|free-memory)"

# ============================================================================
# 7. CPU Per-Core Stats
# ============================================================================
echo ""
echo "==> CPU per-core utilization..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/system resource cpu print'

# ============================================================================
# 8. Interface Statistics
# ============================================================================
echo ""
echo "============================================================================"
echo "Interface statistics (errors/drops)..."
echo "============================================================================"

echo ""
echo "==> WAN interfaces..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/interface ethernet print stats where name~"WAN"' | grep -E "(name|rx-drop|tx-drop|rx-error|tx-error)"

echo ""
echo "==> 10G Trunk..."
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/interface ethernet monitor sfp-10gSwitch once' | grep -E "(status|rate|sfp)"

# ============================================================================
# 9. Queue Statistics
# ============================================================================
echo ""
echo "============================================================================"
echo "CAKE queue statistics..."
echo "============================================================================"
ssh -i "$SSH_KEY" "$ROUTER_USER@$ROUTER" '/queue tree print stats' | grep -E "(name|rate|bytes)"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "============================================================================"
echo "Test complete - $(date)"
echo "============================================================================"
echo ""
echo "Save these results and compare before/after optimization!"
echo ""

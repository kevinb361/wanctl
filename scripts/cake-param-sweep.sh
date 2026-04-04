#!/bin/bash
#
# CAKE Parameter Sweep — Automated Late-Night Testing
#
# Runs a matrix of CAKE parameter combinations with RRUL flent tests.
# Designed to run at 3 AM when DOCSIS node load is lowest.
#
# Usage:
#   ./scripts/cake-param-sweep.sh              # Run full sweep
#   ./scripts/cake-param-sweep.sh --dry-run    # Show what would be tested without running
#
# Output: logs/cake-sweep-YYYY-MM-DD.log (machine-readable results)
#
# Safety:
#   - Restores original CAKE config after every test and at exit (trap)
#   - Validates SSH connectivity before starting
#   - Logs every config change for auditability

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

CAKE_SHAPER="kevin@10.10.110.223"
FLENT_HOST="104.200.21.31"
FLENT_DURATION=60
RUNS_PER_CONFIG=10

# tc binary path — /sbin/tc not in non-interactive SSH PATH
TC="/sbin/tc"

# Interfaces on cake-shaper VM
UL_IFACE="ens16"
DL_IFACE="ens17"

# Current production values (restored after sweep)
PROD_UL_BW="32Mbit"
PROD_DL_BW="940Mbit"
PROD_RTT="40ms"
PROD_OVERHEAD="38"
PROD_MPU=""  # empty = not set

# Base CAKE params that don't change during sweep
UL_BASE="diffserv4 triple-isolate nonat nowash ack-filter split-gso noatm memlimit 32Mb"
DL_BASE="diffserv4 triple-isolate nonat nowash ingress no-ack-filter split-gso noatm memlimit 32Mb"

# Output
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cake-sweep-$(date '+%Y-%m-%d').log"
RESULTS_FILE="$PROJECT_ROOT/.planning/cake-sweep-results-$(date '+%Y-%m-%d').md"

# ============================================================================
# Parameter Matrix
# ============================================================================
# Format: "label:rtt:overhead:mpu"
# Each combo tested with $RUNS_PER_CONFIG flent runs

CONFIGS=(
    # RTT sweep (overhead=38, no mpu — current baseline for comparison)
    "rtt25-oh38:25ms:38:"
    "rtt30-oh38:30ms:38:"
    "rtt35-oh38:35ms:38:"
    "rtt40-oh38:40ms:38:"

    # Overhead sweep at rtt=25ms (MikroTik's tuned rtt)
    "rtt25-oh18-mpu64:25ms:18:64"
    "rtt25-oh22-mpu64:25ms:22:64"
    "rtt25-oh38-mpu64:25ms:38:64"

    # Overhead sweep at rtt=40ms (v1.26 validated rtt)
    "rtt40-oh18-mpu64:40ms:18:64"
    "rtt40-oh22-mpu64:40ms:22:64"

    # DL ceiling sweep (with best rtt/overhead from above — tested last)
    # These are added manually after initial results, or uncomment:
    # "rtt25-oh18-mpu64-dlceil900:25ms:18:64:900"
    # "rtt25-oh18-mpu64-dlceil850:25ms:18:64:850"
)

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# ============================================================================
# Functions
# ============================================================================

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

log_result() {
    # Machine-readable result line
    echo "$1" >> "$LOG_FILE"
}

set_cake() {
    local iface="$1"
    local bw="$2"
    local rtt="$3"
    local overhead="$4"
    local mpu="$5"
    local base="$6"

    local cmd="sudo $TC qdisc change dev $iface root cake bandwidth $bw $base rtt $rtt overhead $overhead"
    if [[ -n "$mpu" ]]; then
        cmd="$cmd mpu $mpu"
    fi

    ssh "$CAKE_SHAPER" "$cmd" 2>&1
}

restore_production() {
    log "RESTORING production CAKE config..."
    local mpu_arg=""
    if [[ -n "$PROD_MPU" ]]; then
        mpu_arg="mpu $PROD_MPU"
    fi
    set_cake "$UL_IFACE" "$PROD_UL_BW" "$PROD_RTT" "$PROD_OVERHEAD" "$PROD_MPU" "$UL_BASE"
    set_cake "$DL_IFACE" "$PROD_DL_BW" "$PROD_RTT" "$PROD_OVERHEAD" "$PROD_MPU" "$DL_BASE"
    log "Production config restored: rtt=$PROD_RTT overhead=$PROD_OVERHEAD"
}

verify_connectivity() {
    log "Verifying connectivity..."

    if ! ssh -o ConnectTimeout=5 "$CAKE_SHAPER" "echo OK" &>/dev/null; then
        log "FATAL: Cannot SSH to $CAKE_SHAPER"
        exit 1
    fi

    if ! flent rrul -H "$FLENT_HOST" -l 5 -t "connectivity-check" &>/dev/null; then
        log "FATAL: flent cannot reach $FLENT_HOST"
        exit 1
    fi

    # Verify CAKE is running
    local ul_qdisc
    ul_qdisc=$(ssh "$CAKE_SHAPER" "$TC qdisc show dev $UL_IFACE | head -1" 2>&1)
    if ! echo "$ul_qdisc" | grep -q "cake"; then
        log "FATAL: CAKE not running on $UL_IFACE: $ul_qdisc"
        exit 1
    fi

    log "Connectivity OK: SSH, flent, CAKE all verified"
}

run_flent() {
    local label="$1"
    local run_num="$2"

    local output
    output=$(flent rrul -H "$FLENT_HOST" -l "$FLENT_DURATION" -t "${label}-run${run_num}" 2>&1)

    local icmp_median icmp_p99 dl_sum ul_sum
    icmp_median=$(echo "$output" | grep "Ping (ms) ICMP" | awk '{print $6}')
    icmp_p99=$(echo "$output" | grep "Ping (ms) ICMP" | awk '{print $7}')
    dl_sum=$(echo "$output" | grep "TCP download sum" | awk '{print $5}')
    ul_sum=$(echo "$output" | grep "TCP upload sum" | awk '{print $5}')

    log_result "RESULT|$label|$run_num|$icmp_median|$icmp_p99|$dl_sum|$ul_sum|$(date '+%H:%M:%S')"
    echo "$icmp_median"  # return for averaging
}

# ============================================================================
# Main
# ============================================================================

# Trap: always restore production config on exit
trap restore_production EXIT

log "=========================================="
log "CAKE Parameter Sweep Starting"
log "=========================================="
log "Host: $(hostname)"
log "Configs: ${#CONFIGS[@]}"
log "Runs per config: $RUNS_PER_CONFIG"
log "Duration per run: ${FLENT_DURATION}s"
log "Total estimated time: $(( ${#CONFIGS[@]} * RUNS_PER_CONFIG * (FLENT_DURATION + 10) / 60 )) minutes"
log "Log: $LOG_FILE"
log ""

if $DRY_RUN; then
    log "DRY RUN — showing test matrix without executing"
    echo ""
    echo "Test Matrix:"
    echo "| # | Label | RTT | Overhead | MPU | Runs |"
    echo "|---|-------|-----|----------|-----|------|"
    for i in "${!CONFIGS[@]}"; do
        IFS=':' read -r label rtt overhead mpu <<< "${CONFIGS[$i]}"
        echo "| $((i+1)) | $label | $rtt | $overhead | ${mpu:-default} | $RUNS_PER_CONFIG |"
    done
    echo ""
    echo "Total: ${#CONFIGS[@]} configs × $RUNS_PER_CONFIG runs = $(( ${#CONFIGS[@]} * RUNS_PER_CONFIG )) flent runs"
    echo "Estimated time: $(( ${#CONFIGS[@]} * RUNS_PER_CONFIG * (FLENT_DURATION + 10) / 60 )) minutes"
    exit 0
fi

verify_connectivity

# Write results header
cat > "$RESULTS_FILE" << 'HEADER'
# CAKE Parameter Sweep Results

**Date:** SWEEP_DATE
**Methodology:** flent rrul -H 104.200.21.31 -l 60, RUNS_PER runs per config
**Host:** dev machine → cake-shaper VM 206 → Dallas

## Raw Results

| Config | Run | ICMP Median (ms) | ICMP p99 (ms) | DL Sum (Mbps) | UL Sum (Mbps) | Time |
|--------|-----|-------------------|---------------|---------------|---------------|------|
HEADER
sed -i "s/SWEEP_DATE/$(date '+%Y-%m-%d')/" "$RESULTS_FILE"
sed -i "s/RUNS_PER/$RUNS_PER_CONFIG/" "$RESULTS_FILE"

# Run each config
for config_idx in "${!CONFIGS[@]}"; do
    IFS=':' read -r label rtt overhead mpu <<< "${CONFIGS[$config_idx]}"

    log ""
    log "--- Config $((config_idx+1))/${#CONFIGS[@]}: $label (rtt=$rtt, overhead=$overhead, mpu=${mpu:-default}) ---"

    # Apply CAKE params to both interfaces
    set_cake "$UL_IFACE" "$PROD_UL_BW" "$rtt" "$overhead" "$mpu" "$UL_BASE"
    set_cake "$DL_IFACE" "$PROD_DL_BW" "$rtt" "$overhead" "$mpu" "$DL_BASE"

    # Verify applied
    local actual
    actual=$(ssh "$CAKE_SHAPER" "$TC qdisc show dev $UL_IFACE | head -1" 2>&1)
    log "Applied UL: $actual"

    # Wait for CAKE to settle
    sleep 5

    # Run N flent tests
    local median_sum=0
    for run in $(seq 1 $RUNS_PER_CONFIG); do
        log "  Run $run/$RUNS_PER_CONFIG..."
        local median
        median=$(run_flent "$label" "$run")

        # Append to results file
        local last_line
        last_line=$(tail -1 "$LOG_FILE")
        if echo "$last_line" | grep -q "^RESULT|"; then
            IFS='|' read -r _ _ _ med p99 dl ul time <<< "$last_line"
            echo "| $label | $run | $med | $p99 | $dl | $ul | $time |" >> "$RESULTS_FILE"
        fi

        # Brief pause between runs
        sleep 5
    done

    log "  Config $label complete"
done

# Restore production (also handled by trap, but be explicit)
restore_production

# Add summary section to results
cat >> "$RESULTS_FILE" << 'FOOTER'

## Summary (compute averages from raw data above)

TODO: Analyze after sweep completes. Compare each config's median-of-medians.

## Config Applied After Sweep

Production restored: rtt=PROD_RTT, overhead=PROD_OH, ceiling UL=32Mbit DL=940Mbit

---
*Sweep completed: SWEEP_TIMESTAMP*
FOOTER
sed -i "s/PROD_RTT/$PROD_RTT/" "$RESULTS_FILE"
sed -i "s/PROD_OH/$PROD_OVERHEAD/" "$RESULTS_FILE"
sed -i "s/SWEEP_TIMESTAMP/$(date '+%Y-%m-%d %H:%M:%S')/" "$RESULTS_FILE"

log ""
log "=========================================="
log "CAKE Parameter Sweep Complete"
log "=========================================="
log "Results: $RESULTS_FILE"
log "Log: $LOG_FILE"
log "Production config restored"

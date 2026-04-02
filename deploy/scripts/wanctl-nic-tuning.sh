#!/bin/bash
# wanctl NIC tuning -- ring buffers, rx-udp-gro-forwarding, IRQ affinity
#
# Deployed to: /usr/local/bin/wanctl-nic-tuning.sh
# Called by:   wanctl-nic-tuning.service (systemd oneshot, runs before wanctl)
#
# Idempotent: safe to re-run at any time. Already-applied settings are
# re-applied without error. Missing NICs are warned and skipped.
#
# Exit code: ALWAYS 0. Failures log warnings but never block the boot chain.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TAG="wanctl-nic-tuning"

# Spectrum bridge pair (Intel i210)
SPECTRUM_NICS=(ens16 ens17)
# ATT bridge pair (Intel i350)
ATT_NICS=(ens27 ens28)
# Combined list
ALL_NICS=("${SPECTRUM_NICS[@]}" "${ATT_NICS[@]}")

# IRQ affinity targets
SPECTRUM_CPU=0
ATT_CPU=1

# Ring buffer sizes (max for both i210 and i350)
RING_RX=4096
RING_TX=4096

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

tune_nic() {
    local nic="$1"

    # Check NIC exists
    if ! ip link show "$nic" &>/dev/null; then
        logger -t "$TAG" "WARNING: $nic not found, skipping"
        return 0
    fi

    # Ring buffers
    if ! ethtool -G "$nic" rx "$RING_RX" tx "$RING_TX" 2>&1; then
        logger -t "$TAG" "WARNING: ring buffer set failed for $nic (may already be at max)"
    fi

    # rx-udp-gro-forwarding
    if ! ethtool -K "$nic" rx-udp-gro-forwarding on 2>&1; then
        logger -t "$TAG" "WARNING: rx-udp-gro-forwarding failed for $nic"
    fi

    logger -t "$TAG" "$nic: ring buffers rx=$RING_RX tx=$RING_TX, rx-udp-gro-forwarding=on"
    return 0
}

set_irq_affinity() {
    local nic="$1"
    local cpu="$2"

    # Find IRQs for this NIC
    local irqs
    irqs=$(grep "$nic" /proc/interrupts 2>/dev/null | awk '{print $1}' | tr -d ':') || true

    if [[ -z "$irqs" ]]; then
        logger -t "$TAG" "WARNING: no IRQs found for $nic, skipping affinity"
        return 0
    fi

    local irq
    for irq in $irqs; do
        if ! echo "$cpu" > "/proc/irq/$irq/smp_affinity_list" 2>/dev/null; then
            logger -t "$TAG" "WARNING: IRQ $irq affinity failed for $nic"
        fi
    done

    logger -t "$TAG" "$nic: IRQ affinity pinned to CPU $cpu"
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

logger -t "$TAG" "Starting NIC tuning..."

errors=0

# Apply ring buffers and GRO forwarding to all NICs
for nic in "${ALL_NICS[@]}"; do
    if ! tune_nic "$nic"; then
        errors=$((errors + 1))
    fi
done

# Pin IRQ affinity -- Spectrum NICs to CPU 0
for nic in "${SPECTRUM_NICS[@]}"; do
    if ! set_irq_affinity "$nic" "$SPECTRUM_CPU"; then
        errors=$((errors + 1))
    fi
done

# Pin IRQ affinity -- ATT NICs to CPU 1
for nic in "${ATT_NICS[@]}"; do
    if ! set_irq_affinity "$nic" "$ATT_CPU"; then
        errors=$((errors + 1))
    fi
done

logger -t "$TAG" "NIC tuning complete (${#ALL_NICS[@]} NICs configured, $errors errors)"

# Always exit 0 -- warn but never block boot chain (D-01)
exit 0

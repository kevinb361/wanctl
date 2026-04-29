#!/bin/bash
# wanctl NIC tuning -- ring buffers, offloads, IRQ affinity, sysctl
#
# Deployed to: /usr/local/bin/wanctl-nic-tuning.sh
# Called by:   wanctl-nic-tuning.service (systemd oneshot, runs before wanctl)
#
# IRQ affinity distribution (3-core):
#   CPU0: spec-router (Spectrum DL) -- heaviest single-NIC IRQ load
#   CPU1: att-modem+att-router (ATT bridge pair) -- light traffic
#   CPU2: spec-modem (Spectrum UL) -- balances Spectrum load
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

# Spectrum Silicom bridge pair (Intel i350)
SPECTRUM_NICS=(spec-router spec-modem)
# ATT Silicom bridge pair (Intel i350)
ATT_NICS=(att-modem att-router)
# Combined list
ALL_NICS=("${SPECTRUM_NICS[@]}" "${ATT_NICS[@]}")

# IRQ affinity targets (3-core distribution per D-01)
# Spectrum DL NIC -- heaviest single-NIC IRQ load
SPECTRUM_DL_CPU=0
# Spectrum UL NIC -- moved away from CPU0 to balance Spectrum load
SPECTRUM_UL_CPU=2
# ATT bridge pair -- light traffic, single core sufficient
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

    if [[ " ${SPECTRUM_NICS[*]} " == *" $nic "* ]]; then
        # Software shaping on the Silicom Spectrum pair loses packets when GRO/GSO/TSO
        # and hardware TC offload are enabled. Keep frames visible to qdisc at MTU size.
        if ! ethtool -K "$nic" gro off gso off tso off hw-tc-offload off 2>&1; then
            logger -t "$TAG" "WARNING: offload disable failed for $nic"
        fi
        logger -t "$TAG" "$nic: ring buffers rx=$RING_RX tx=$RING_TX, gro/gso/tso/hw-tc-offload=off"
    else
        # rx-udp-gro-forwarding remains useful on non-Spectrum paths.
        if ! ethtool -K "$nic" rx-udp-gro-forwarding on 2>&1; then
            logger -t "$TAG" "WARNING: rx-udp-gro-forwarding failed for $nic"
        fi
        logger -t "$TAG" "$nic: ring buffers rx=$RING_RX tx=$RING_TX, rx-udp-gro-forwarding=on"
    fi
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

# Apply ring buffers and per-link offload policy to all NICs
for nic in "${ALL_NICS[@]}"; do
    if ! tune_nic "$nic"; then
        errors=$((errors + 1))
    fi
done

# Pin IRQ affinity -- Spectrum DL to CPU 0
if ! set_irq_affinity "spec-router" "$SPECTRUM_DL_CPU"; then
    errors=$((errors + 1))
fi

# Pin IRQ affinity -- Spectrum UL to CPU 2
if ! set_irq_affinity "spec-modem" "$SPECTRUM_UL_CPU"; then
    errors=$((errors + 1))
fi

# Pin IRQ affinity -- ATT NICs to CPU 1
for nic in "${ATT_NICS[@]}"; do
    if ! set_irq_affinity "$nic" "$ATT_CPU"; then
        errors=$((errors + 1))
    fi
done

# ---------------------------------------------------------------------------
# Kernel network stack tuning (per D-04, D-05, D-06)
# These complement the sysctl.d drop-in for immediate effect on service restart
# ---------------------------------------------------------------------------

apply_sysctl() {
    local key="$1"
    local value="$2"
    if sysctl -w "${key}=${value}" &>/dev/null; then
        logger -t "$TAG" "sysctl: ${key}=${value}"
    else
        logger -t "$TAG" "WARNING: sysctl ${key}=${value} failed"
    fi
}

apply_sysctl net.core.netdev_budget 600
apply_sysctl net.core.netdev_budget_usecs 8000   # kernel min=8000, keep explicit
apply_sysctl net.core.netdev_max_backlog 10000

logger -t "$TAG" "NIC tuning complete (${#ALL_NICS[@]} NICs configured, $errors errors)"

# Always exit 0 -- warn but never block boot chain (D-01)
exit 0

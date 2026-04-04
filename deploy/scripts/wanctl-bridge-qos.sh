#!/bin/bash
# wanctl Bridge QoS loader -- nftables DSCP classification for CAKE tins
#
# Loads the nf_conntrack_bridge kernel module and applies nftables bridge
# forward rules that classify download traffic into CAKE diffserv4 tins.
#
# Deployed to: /usr/local/bin/wanctl-bridge-qos.sh
# Called by:   wanctl-bridge-qos.service (systemd oneshot, runs before wanctl)
# Rules file:  /etc/wanctl/bridge-qos.nft
#
# Idempotent: safe to re-run at any time. Module is loaded if not already
# present, and nftables rules are flushed and reloaded.
#
# Exit code: ALWAYS 0. Failures log warnings but never block the boot chain.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TAG="wanctl-bridge-qos"
NFT_RULES="/etc/wanctl/bridge-qos.nft"

# Bridge NIC pairs (modem-side, router-side)
SPECTRUM_NICS=(ens16 ens17)
ATT_NICS=(ens27 ens28)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

check_nics() {
    local missing=0
    local all_nics=("${SPECTRUM_NICS[@]}" "${ATT_NICS[@]}")

    for nic in "${all_nics[@]}"; do
        if ! ip link show "$nic" &>/dev/null; then
            logger -t "$TAG" "WARNING: NIC $nic not found -- bridge QoS rules may not match traffic"
            missing=$((missing + 1))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        logger -t "$TAG" "WARNING: $missing NIC(s) missing -- loading rules anyway (they will match when NICs appear)"
    fi

    return 0
}

load_conntrack_bridge() {
    if lsmod | grep -q nf_conntrack_bridge; then
        logger -t "$TAG" "nf_conntrack_bridge already loaded"
    else
        if modprobe nf_conntrack_bridge 2>&1; then
            logger -t "$TAG" "nf_conntrack_bridge loaded successfully"
        else
            logger -t "$TAG" "ERROR: failed to load nf_conntrack_bridge -- conntrack-based rules will not work"
            return 1
        fi
    fi
    return 0
}

load_nftables_rules() {
    if [[ ! -f "$NFT_RULES" ]]; then
        logger -t "$TAG" "ERROR: nftables rules not found: $NFT_RULES"
        return 1
    fi

    if nft -f "$NFT_RULES" 2>&1; then
        logger -t "$TAG" "nftables rules loaded from $NFT_RULES"
    else
        logger -t "$TAG" "ERROR: failed to load nftables rules from $NFT_RULES"
        return 1
    fi

    return 0
}

verify_rules() {
    if nft list table bridge qos &>/dev/null; then
        local rule_count
        rule_count=$(nft list table bridge qos | grep -c "ip dscp set" || true)
        logger -t "$TAG" "Verified: bridge qos table active ($rule_count DSCP classification rules)"
    else
        logger -t "$TAG" "ERROR: bridge qos table not found after loading"
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

logger -t "$TAG" "Starting bridge QoS setup..."

errors=0

# Check NICs exist (warn only)
check_nics

# Load conntrack bridge module (required for ct state/ct mark/ct bytes)
if ! load_conntrack_bridge; then
    errors=$((errors + 1))
fi

# Load nftables classification rules
if ! load_nftables_rules; then
    errors=$((errors + 1))
fi

# Verify rules are active
if ! verify_rules; then
    errors=$((errors + 1))
fi

if [[ $errors -eq 0 ]]; then
    logger -t "$TAG" "Bridge QoS setup complete -- download DSCP classification active"
else
    logger -t "$TAG" "Bridge QoS setup completed with $errors error(s)"
fi

# Always exit 0 -- warn but never block boot chain
exit 0

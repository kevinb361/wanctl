# ============================================================================
# RB5009 Performance Optimization Script
# ============================================================================
# WARNING: This will modify firewall, bridge, and routing settings
# BACKUP YOUR CONFIG FIRST: /export file=backup-before-optimization
#
# Trade-offs:
# - FastTrack bypasses CAKE queues (only for bulk TCP, not real-time traffic)
# - FastPath improves routing performance significantly
# - Fast-forward improves bridge/VLAN performance
#
# Created: 2025-12-11
# ============================================================================

# ============================================================================
# STEP 1: Enable Critical WAN Packet Marking (REQUIRED FOR CAKE!)
# ============================================================================
# Your CAKE queues are expecting these packet marks but they're disabled!

/ip firewall mangle

# Enable Spectrum inbound marking
set [find comment~"WAN: Mark Spectrum inbound"] disabled=no

# Enable ATT inbound marking
set [find comment~"WAN: Mark ATT inbound"] disabled=no

# Enable Spectrum outbound marking
set [find comment~"WAN: Mark Spectrum outbound"] disabled=no

# Enable ATT outbound marking
set [find comment~"WAN: Mark ATT outbound"] disabled=no

:log info "WAN packet marking enabled for CAKE queues"

# ============================================================================
# STEP 2: Add FastTrack Rules (MASSIVE Performance Gain)
# ============================================================================
# FastTrack only bulk TCP connections, preserve CAKE for:
# - UDP (real-time traffic, gaming, VoIP)
# - Small/interactive connections
# - Traffic that needs QoS

/ip firewall filter

# Add FastTrack BEFORE established/related rule
# Find the position of "FW: Accept established,related" rule
:local fwdPos [/ip firewall filter find where chain=forward comment="FW: Accept established,related"]

# Add FastTrack rule right before it
/ip firewall filter add place-before=$fwdPos \
    chain=forward \
    action=fasttrack-connection \
    connection-state=established,related \
    connection-mark=!QOS_HIGH \
    connection-bytes=1000000-4294967295 \
    protocol=tcp \
    comment="PERF: FastTrack bulk TCP (>1MB, not QoS-HIGH)"

:log info "FastTrack rule added for bulk TCP connections"

# ============================================================================
# STEP 3: Enable IP Fast-Path (Hardware Routing Offload)
# ============================================================================

/ip settings
set allow-fast-path=yes

:log info "IP fast-path enabled for hardware routing offload"

# ============================================================================
# STEP 4: Enable Bridge Fast-Forward (Bridge Performance)
# ============================================================================
# NOTE: This works with VLAN filtering on modern RouterOS 7.x

/interface bridge
set bridge1 fast-forward=yes

:log info "Bridge fast-forward enabled"

# ============================================================================
# STEP 5: Optimize Connection Tracking
# ============================================================================

/ip firewall connection tracking
set \
    tcp-established-timeout=1d \
    tcp-close-timeout=10s \
    tcp-close-wait-timeout=10s \
    udp-timeout=30s \
    udp-stream-timeout=3m \
    icmp-timeout=10s \
    generic-timeout=10m

:log info "Connection tracking timeouts optimized"

# ============================================================================
# STEP 6: Optimize Interface Settings
# ============================================================================

# Enable flow control on 10G uplink (helps with buffer management)
/interface ethernet
set sfp-10gSwitch rx-flow-control=on tx-flow-control=on

:log info "Flow control enabled on 10G uplink"

# ============================================================================
# STEP 7: Clean Up Disabled Mangle Rules (Optional - Improves Rule Processing)
# ============================================================================
# Disabled rules still consume processing time during rule evaluation
# You have ~100+ disabled mangle rules

# UNCOMMENT TO REMOVE ALL DISABLED MANGLE RULES (review first!)
# /ip firewall mangle remove [find disabled=yes]
# :log warning "All disabled mangle rules removed"

:log info "Performance optimization complete - review changes"

# ============================================================================
# VERIFICATION COMMANDS (run these manually after applying)
# ============================================================================
# /interface bridge print detail
# /ip settings print
# /ip firewall filter print where action=fasttrack-connection
# /ip firewall mangle print where new-packet-mark~"wan-"
# /system resource cpu print
# ============================================================================

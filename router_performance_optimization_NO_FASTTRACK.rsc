# ============================================================================
# RB5009 Performance Optimization (CAKE-Safe, NO FASTTRACK)
# ============================================================================
# This optimization preserves CAKE queuing for ALL traffic
# Focus: Reduce CPU overhead without bypassing queues
#
# BACKUP YOUR CONFIG FIRST: /export file=backup-before-optimization
# ============================================================================

# ============================================================================
# STEP 1: CRITICAL FIX - Enable WAN Packet Marking (REQUIRED FOR CAKE!)
# ============================================================================
# Your CAKE queues expect these packet marks but they're DISABLED!
# This is why your bufferbloat control may not be working!

/ip firewall mangle

# Enable Spectrum inbound marking
set [find comment~"WAN: Mark Spectrum inbound"] disabled=no

# Enable ATT inbound marking
set [find comment~"WAN: Mark ATT inbound"] disabled=no

# Enable Spectrum outbound marking
set [find comment~"WAN: Mark Spectrum outbound"] disabled=no

# Enable ATT outbound marking
set [find comment~"WAN: Mark ATT outbound"] disabled=no

:log warning "CRITICAL FIX: WAN packet marking enabled - CAKE should now work!"

# ============================================================================
# STEP 2: Enable Bridge Fast-Forward (Safe for Queued Traffic)
# ============================================================================
# Fast-forward only affects bridged traffic between ports on same bridge
# Traffic going through queues (WAN) is NOT affected
# This speeds up VLAN-to-VLAN traffic that doesn't hit WAN

/interface bridge
set bridge1 fast-forward=yes

:log info "Bridge fast-forward enabled (does not affect CAKE)"

# ============================================================================
# STEP 3: Optimize Connection Tracking (Reduce Memory/CPU)
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
# STEP 4: Enable Flow Control on 10G Uplink
# ============================================================================
# Prevents packet loss during bursts, improves throughput stability

/interface ethernet
set sfp-10gSwitch rx-flow-control=on tx-flow-control=on

:log info "Flow control enabled on 10G uplink"

# ============================================================================
# STEP 5: Disable Unused Ports (Reduce Processing Overhead)
# ============================================================================
# Unused ports still consume CPU cycles for link monitoring, etc.

/interface ethernet
set ether3,ether4,ether5,ether6,ether7 disabled=yes comment="Disabled - unused"

:log info "Unused ports disabled"

# ============================================================================
# STEP 6: Remove Bridge Membership for Disabled Ports
# ============================================================================
# Further reduces bridge processing overhead

/interface bridge port
:foreach port in=[find interface~"ether[3-7]"] do={
    :if ([get $port interface] != "ether8-MGMT Port") do={
        remove $port
        :log info ("Removed " . [get $port interface] . " from bridge")
    }
}

# ============================================================================
# NOTE: IP Fast-Path NOT Enabled
# ============================================================================
# Keeping allow-fast-path=no because:
# 1. You need firewall processing on all traffic
# 2. You need mangle rules for CAKE packet marking
# 3. Fast-path would bypass both
#
# If you want to test it: /ip settings set allow-fast-path=yes
# But monitor that CAKE continues working: /queue tree print stats

:log warning "IP fast-path remains DISABLED to preserve CAKE functionality"

# ============================================================================
# VERIFICATION
# ============================================================================

:log info "Performance optimization complete (CAKE-safe)"
:log info "Verify WAN marking: /ip firewall mangle print where new-packet-mark~\"wan-\""
:log info "Verify CAKE working: /queue tree print stats"
:log info "Monitor CPU: /system resource cpu print"


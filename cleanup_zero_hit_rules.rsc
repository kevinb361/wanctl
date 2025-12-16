# ============================================================================
# Zero-Hit Firewall Rule Cleanup
# ============================================================================
# This script disables (not removes) zero-hit rules for testing
# If nothing breaks after 1 week, you can remove them permanently
#
# BACKUP FIRST: /export file=backup-before-cleanup
# ============================================================================

:log warning "Starting zero-hit rule cleanup analysis..."

# ============================================================================
# PHASE 1: Disable zero-hit rules (TEST MODE)
# ============================================================================
# These rules have NEVER matched any traffic based on your stats

/ip firewall filter

# WireGuard rules (0 hits, appears unused)
set [find comment="IN: Allow WireGuard to router"] disabled=yes
set [find comment="IN: Allow WireGuard WAN ports"] disabled=yes
set [find comment="FW: Allow WireGuard forwarding"] disabled=yes

# WINBOX rule (0 hits, but might be working - be careful!)
# Commented out - test this separately
# set [find comment="IN: Allow WINBOX"] disabled=yes

# Monitoring rule (0 hits)
set [find comment="FW: Monitoring host -> mgmt"] disabled=yes

# NDI blocking (0 hits)
set [find comment="FW: Block NDI from mgmt"] disabled=yes

# DSTNAT jump (0 hits, empty chain?)
set [find comment="FW: internet -> local (DSTNAT)"] disabled=yes

# Block rules with 0 hits (working or misplaced?)
set [find comment="Block direct NTP to WAN"] disabled=yes
set [find comment~"Drop QUIC to WAN"] disabled=yes
set [find comment~"Block IoT STUN/TURN"] disabled=yes
set [find comment~"Block IoT tracking domains"] disabled=yes

# Plex GDM (0 hits)
set [find comment="IN: Silent drop Plex GDM"] disabled=yes

:log warning "Phase 1 complete: Zero-hit rules disabled"
:log info "Monitor for 1 week. If no issues, run Phase 2 to remove permanently"

# ============================================================================
# PHASE 2: Remove permanently (RUN AFTER 1 WEEK OF TESTING)
# ============================================================================
# Uncomment these after verifying nothing broke

# /ip firewall filter
# remove [find comment="IN: Allow WireGuard to router"]
# remove [find comment="IN: Allow WireGuard WAN ports"]
# remove [find comment="FW: Allow WireGuard forwarding"]
# remove [find comment="FW: Monitoring host -> mgmt"]
# remove [find comment="FW: Block NDI from mgmt"]
# remove [find comment="FW: internet -> local (DSTNAT)"]
# remove [find comment="Block direct NTP to WAN"]
# remove [find comment~"Drop QUIC to WAN"]
# remove [find comment~"Block IoT STUN/TURN"]
# remove [find comment~"Block IoT tracking domains"]
# remove [find comment="IN: Silent drop Plex GDM"]

# :log warning "Phase 2 complete: Zero-hit rules removed permanently"

# ============================================================================
# PHASE 3: Investigate anomalies
# ============================================================================

:log info "INVESTIGATE: ZeroTier forward rule has 0 hits but input rule is active"
:log info "  Rule 'FW: LAN -> ZeroTier' might be in wrong position"

:log info "INVESTIGATE: WiFi Calling ESP has 0 hits"
:log info "  Do you actually use WiFi calling? If not, remove the rule"

:log info "INVESTIGATE: 'FW: MGMT -> ALL' has 0 hits"
:log info "  Is management VLAN actually being used from 10.10.99.0/24?"

:log info "Review complete. Monitor logs and connectivity for 1 week before Phase 2"


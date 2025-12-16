#!/bin/bash
#
# RouterOS Mangle Rules for Adaptive WAN Steering
# Run these commands on the RouterOS router to add steering infrastructure
#
# IMPORTANT: Review the plan before running!
# Location: /home/kevin/.claude/plans/optimized-mapping-ullman.md
#

echo "=========================================="
echo " RouterOS Steering Rules Setup"
echo "=========================================="
echo ""
echo "This script will add the following to your RouterOS mangle table:"
echo ""
echo "1. Three LATENCY_SENSITIVE translation rules:"
echo "   - QOS_HIGH → LATENCY_SENSITIVE"
echo "   - GAMES → LATENCY_SENSITIVE"
echo "   - QOS_MEDIUM → LATENCY_SENSITIVE"
echo ""
echo "2. One ADAPTIVE steering rule (initially DISABLED):"
echo "   - Routes LATENCY_SENSITIVE traffic to ATT when enabled"
echo ""
echo "=========================================="
echo ""
read -p "Press Enter to see the commands, or Ctrl-C to abort..."
echo ""

cat << 'EOF'
# Connect to RouterOS
ssh admin@10.10.99.1

# =============================================================================
# CURRENT MANGLE TABLE STRUCTURE (for reference)
# =============================================================================
# Rules 0-6:   Routing, WAN packet marking, DSCP wash
# Rules 7-49:  Connection marking (QOS_HIGH, GAMES, QOS_MEDIUM, QOS_LOW, etc.)
#              Rule 49 = last rule (default QOS_NORMAL for unclassified)
# Rules 50-65: Postrouting (different chain - upload WAN marking, DSCP setting)

# =============================================================================
# STEP 1: Add LATENCY_SENSITIVE Translation Rules
# =============================================================================
# PLACEMENT: These will be added AFTER rule 49 (end of prerouting chain)
# PURPOSE: Translate existing QoS connection-marks → LATENCY_SENSITIVE mark
# CRITICAL: passthrough=yes preserves original marks for DSCP tagging (rules 56-61)
#
# Traffic flow:
#   1. Rules 7-49 mark connection as QOS_HIGH/GAMES/QOS_MEDIUM
#   2. These new rules ALSO mark as LATENCY_SENSITIVE (passthrough=yes allows both)
#   3. ADAPTIVE rule (rule #1) uses LATENCY_SENSITIVE for routing decisions
#   4. Rules 56-61 still see original QOS_HIGH/GAMES/etc. for DSCP tagging

/ip firewall mangle add \
  chain=prerouting \
  action=mark-connection \
  new-connection-mark=LATENCY_SENSITIVE \
  passthrough=yes \
  connection-state=new \
  connection-mark=QOS_HIGH \
  comment="CLASSIFY: QOS_HIGH -> LATENCY_SENSITIVE"

/ip firewall mangle add \
  chain=prerouting \
  action=mark-connection \
  new-connection-mark=LATENCY_SENSITIVE \
  passthrough=yes \
  connection-state=new \
  connection-mark=GAMES \
  comment="CLASSIFY: GAMES -> LATENCY_SENSITIVE"

/ip firewall mangle add \
  chain=prerouting \
  action=mark-connection \
  new-connection-mark=LATENCY_SENSITIVE \
  passthrough=yes \
  connection-state=new \
  connection-mark=QOS_MEDIUM \
  comment="CLASSIFY: QOS_MEDIUM -> LATENCY_SENSITIVE"

# =============================================================================
# STEP 2: Add ADAPTIVE Steering Rule (initially disabled)
# =============================================================================
# PLACEMENT: place-before=1 inserts this RIGHT AFTER rule #0 (FORCE_OUT_ATT)
# This ensures priority order:
#   Rule 0: FORCE_OUT_ATT (static overrides - always active)
#   Rule 1: ADAPTIVE steering (new rule - toggleable by daemon)
#   Rule 2+: Rest of mangle rules
#
# PURPOSE: Route LATENCY_SENSITIVE traffic to ATT when enabled by daemon
# INITIAL STATE: disabled=yes (starts in SPECTRUM_GOOD state)
# DAEMON CONTROL: Daemon enables/disables this rule based on Spectrum RTT
#
# Why place-before=1 instead of place-before=0?
#   - Rule 0 is FORCE_OUT_ATT (manual overrides for specific hosts)
#   - Those should ALWAYS have highest priority (never interfered with)
#   - This rule goes right after, so ADAPTIVE steering is 2nd priority

/ip firewall mangle add \
  place-before=1 \
  chain=prerouting \
  action=mark-routing \
  new-routing-mark=to_ATT \
  passthrough=no \
  connection-state=new \
  connection-mark=LATENCY_SENSITIVE \
  dst-address=!10.10.0.0/16 \
  disabled=yes \
  comment="ADAPTIVE: Steer latency-sensitive to ATT"

# =============================================================================
# STEP 3: Verify Rules
# =============================================================================

# Check LATENCY_SENSITIVE translation rules (should be at end of prerouting)
/ip firewall mangle print where comment~"CLASSIFY.*LATENCY"

# Check ADAPTIVE steering rule (should show "disabled=yes" or "X" flag)
/ip firewall mangle print where comment~"ADAPTIVE"

# Verify complete prerouting chain order
/ip firewall mangle print chain=prerouting

# Expected order after adding rules:
#   0: FORCE_OUT_ATT (static routing)
#   1: ADAPTIVE: Steer latency-sensitive to ATT (NEW - disabled initially)
#   2: DSCP WASH
#   3-7: WAN packet marking, MSS clamp
#   8-50: Connection marking (QOS_HIGH, GAMES, QOS_MEDIUM, etc.)
#   51: CLASSIFY: QOS_HIGH -> LATENCY_SENSITIVE (NEW)
#   52: CLASSIFY: GAMES -> LATENCY_SENSITIVE (NEW)
#   53: CLASSIFY: QOS_MEDIUM -> LATENCY_SENSITIVE (NEW)

# Count total prerouting rules (should be 54 after adding 4 new rules)
/ip firewall mangle print count-only chain=prerouting

# =============================================================================
# STEP 4: Test Enable/Disable (optional)
# =============================================================================

# Test enabling the rule (steering daemon will do this automatically)
/ip firewall mangle enable [find comment~"ADAPTIVE: Steer"]

# Verify it's enabled
/ip firewall mangle print where comment~"ADAPTIVE"

# Test disabling the rule (return to default)
/ip firewall mangle disable [find comment~"ADAPTIVE: Steer"]

# Verify it's disabled
/ip firewall mangle print where comment~"ADAPTIVE"

EOF

echo ""
echo "=========================================="
echo " Notes on Rule Placement"
echo "=========================================="
echo ""
echo "ADAPTIVE Steering Rule (routing decision):"
echo "  - Added with place-before=1 → becomes rule #1"
echo "  - Positioned RIGHT AFTER rule #0 (FORCE_OUT_ATT)"
echo "  - Starts DISABLED (disabled=yes)"
echo "  - Daemon toggles this rule based on Spectrum RTT"
echo ""
echo "LATENCY_SENSITIVE Translation Rules (classification):"
echo "  - Added at END of prerouting chain (after rule 49)"
echo "  - Become rules 51-53 (after all existing connection marking)"
echo "  - Use passthrough=yes to preserve original marks"
echo "  - Run AFTER original QoS classification completes"
echo ""
echo "Why This Order Matters:"
echo "  1. Routing decisions (rule #1) happen early"
echo "  2. Connection classification (rules 7-50) sets QOS marks"
echo "  3. Translation to LATENCY_SENSITIVE (rules 51-53) happens after"
echo "  4. DSCP tagging (postrouting) still sees original QOS marks"
echo ""
echo "Key Details:"
echo "  - connection-state=new ensures existing connections never move"
echo "  - dst-address=!10.10.0.0/16 excludes local network traffic"
echo "  - passthrough=yes allows multiple connection marks simultaneously"
echo ""
echo "=========================================="
echo " After Adding Rules"
echo "=========================================="
echo ""
echo "1. Deploy the steering daemon:"
echo "   cd /home/kevin/CAKE"
echo "   ./deploy_steering.sh"
echo ""
echo "2. Follow the manual steps to install systemd units"
echo ""
echo "3. Monitor operation:"
echo "   ssh kevin@10.10.110.246 'journalctl -u wan-steering.service -f'"
echo ""

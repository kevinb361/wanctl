#!/bin/bash
# Production container cleanup script
# Renames fusion_cake → wanctl and removes cruft

set -e

CONTAINER=$1

if [[ -z "$CONTAINER" ]]; then
    echo "Usage: $0 <cake-spectrum|cake-att>"
    exit 1
fi

echo "=== Cleaning up $CONTAINER ==="
echo ""

# Step 1: Stop all services
echo "1. Stopping all CAKE services..."
ssh $CONTAINER 'sudo systemctl stop cake-*-continuous.service cake-*.service wan-steering.service 2>/dev/null || true'
echo "   ✓ Services stopped"
echo ""

# Step 2: Rename fusion_cake → wanctl
echo "2. Renaming fusion_cake → wanctl..."
ssh $CONTAINER 'if [ -d /home/kevin/fusion_cake ]; then mv /home/kevin/fusion_cake /home/kevin/wanctl; echo "   ✓ Renamed"; else echo "   Already renamed or doesn'\''t exist"; fi'
echo ""

# Step 3: Clean up inside wanctl/
echo "3. Cleaning up /home/kevin/wanctl/ (removing backup files)..."
ssh $CONTAINER 'cd /home/kevin/wanctl && rm -rf __pycache__ *.backup.* *_backup_*.py && ls -la'
echo "   ✓ Backup files deleted"
echo ""

# Step 4: Delete obsolete directories in /home/kevin/
echo "4. Deleting obsolete directories and files..."
ssh $CONTAINER 'cd /home/kevin && rm -rf .obsolete_* adaptive_cake_* adaptive_state.json att_state.json systemd/ *.timer test_steering.sh README.NFO get-pip.py 2>/dev/null && echo "   ✓ Cruft deleted"'
echo ""

# Step 5: Update systemd units (fusion_cake → wanctl)
echo "5. Updating systemd unit files..."
ssh $CONTAINER "sudo sed -i 's|/home/kevin/fusion_cake|/home/kevin/wanctl|g' /etc/systemd/system/cake-*.service /etc/systemd/system/wan-steering.service 2>/dev/null && echo '   ✓ Systemd units updated'"
echo ""

# Step 6: Reload systemd
echo "6. Reloading systemd daemon..."
ssh $CONTAINER 'sudo systemctl daemon-reload'
echo "   ✓ Daemon reloaded"
echo ""

# Step 7: Restart services
echo "7. Restarting services..."
if [[ "$CONTAINER" == "cake-spectrum" ]]; then
    ssh $CONTAINER 'sudo systemctl start cake-spectrum-continuous.service wan-steering.service'
    echo "   ✓ Started cake-spectrum-continuous and wan-steering"
elif [[ "$CONTAINER" == "cake-att" ]]; then
    ssh $CONTAINER 'sudo systemctl start cake-att-continuous.service'
    echo "   ✓ Started cake-att-continuous"
fi
echo ""

# Step 8: Verify services
echo "8. Verifying services..."
sleep 3
ssh $CONTAINER 'systemctl status cake-*-continuous.service --no-pager | grep -E "(Loaded|Active)"'
if [[ "$CONTAINER" == "cake-spectrum" ]]; then
    ssh $CONTAINER 'systemctl status wan-steering.service --no-pager | grep -E "(Loaded|Active)"'
fi
echo ""

# Step 9: Check logs
echo "9. Checking recent logs..."
ssh $CONTAINER 'tail -3 /home/kevin/wanctl/logs/cake_auto.log'
echo ""

echo "=== Cleanup complete for $CONTAINER ✓ ==="
echo ""

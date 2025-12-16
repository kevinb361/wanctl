#!/bin/bash
# Run this script ON the ATT container (as root or with sudo)
# Usage: sudo ./container_install_att.sh

echo "=========================================="
echo "Installing CAKE services - ATT"
echo "=========================================="
echo ""

# Check if files exist in /tmp
echo "Checking for unit files..."
if [ ! -f /tmp/cake-att.service ]; then
    echo "ERROR: Unit files not found in /tmp"
    echo "Make sure deployment script has run first"
    exit 1
fi

ls -l /tmp/cake-att*.{service,timer} 2>/dev/null
echo ""

# Move files
echo "Moving unit files to /etc/systemd/system/..."
mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start timers
echo "Enabling and starting timers..."
systemctl enable cake-att.timer cake-att-reset.timer
systemctl start cake-att.timer cake-att-reset.timer

# Show status
echo ""
echo "Timer status:"
systemctl list-timers cake-att* --no-pager
echo ""

echo "Installation complete!"
echo ""
echo "View logs:"
echo "  journalctl -u cake-att.service -f"
echo "  tail -f /home/kevin/fusion_cake/logs/cake_auto.log"
echo ""

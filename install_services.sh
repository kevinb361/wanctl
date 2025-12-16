#!/bin/bash
# Install new CAKE systemd services and timers

echo "=========================================="
echo "Installing CAKE systemd services"
echo "=========================================="
echo ""

# Function to install on a container
install_container() {
    local HOST=$1
    local NAME=$2
    local PREFIX=$3

    echo "Installing on $NAME ($HOST)..."

    # Check if files exist in /tmp
    echo "Checking for unit files in /tmp..."
    ssh root@${HOST} "ls -l /tmp/${PREFIX}*.{service,timer} 2>/dev/null || echo 'WARNING: No unit files found in /tmp'"
    echo ""

    # Move files
    echo "Moving unit files to /etc/systemd/system/..."
    ssh root@${HOST} "mv /tmp/${PREFIX}*.service /tmp/${PREFIX}*.timer /etc/systemd/system/ 2>/dev/null || echo 'ERROR: Failed to move files'"

    # Reload systemd
    echo "Reloading systemd..."
    ssh root@${HOST} 'systemctl daemon-reload'

    # Enable and start timers
    echo "Enabling and starting timers..."
    ssh root@${HOST} "systemctl enable --now ${PREFIX}.timer ${PREFIX}-reset.timer"

    # Show status
    echo ""
    echo "$NAME timer status:"
    ssh root@${HOST} "systemctl list-timers ${PREFIX}* --no-pager"
    echo ""

    echo "Installation complete for $NAME"
    echo ""
}

# Install on both containers
install_container "10.10.110.247" "ATT" "cake-att"
install_container "10.10.110.246" "Spectrum" "cake-spectrum"

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Verify timers are running:"
echo "  ssh root@10.10.110.247 'systemctl list-timers cake-*'"
echo "  ssh root@10.10.110.246 'systemctl list-timers cake-*'"
echo ""
echo "Watch logs:"
echo "  ssh kevin@10.10.110.247 'tail -f /home/kevin/fusion_cake/logs/cake_auto.log'"
echo "  ssh kevin@10.10.110.246 'tail -f /home/kevin/fusion_cake/logs/cake_auto.log'"
echo ""
echo "View journal:"
echo "  ssh root@10.10.110.247 'journalctl -u cake-att.service -f'"
echo "  ssh root@10.10.110.246 'journalctl -u cake-spectrum.service -f'"
echo ""

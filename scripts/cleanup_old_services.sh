#!/bin/bash
# Cleanup old CAKE services and timers

echo "=========================================="
echo "Cleaning up old CAKE services/timers"
echo "=========================================="
echo ""

# Function to cleanup on a container
cleanup_container() {
    local HOST=$1
    local NAME=$2

    echo "Checking $NAME ($HOST)..."

    # List what's currently installed
    echo "Current CAKE services/timers:"
    ssh root@${HOST} 'systemctl list-unit-files | grep -i cake || echo "  None found"'
    echo ""

    # Stop and disable any running timers
    echo "Stopping timers..."
    ssh root@${HOST} 'systemctl stop cake-*.timer 2>/dev/null || true'
    ssh root@${HOST} 'systemctl disable cake-*.timer 2>/dev/null || true'

    echo "Stopping services..."
    ssh root@${HOST} 'systemctl stop cake-*.service 2>/dev/null || true'
    ssh root@${HOST} 'systemctl disable cake-*.service 2>/dev/null || true'

    # Remove unit files
    echo "Removing old unit files..."
    ssh root@${HOST} 'rm -f /etc/systemd/system/cake-*.service /etc/systemd/system/cake-*.timer'

    # Reload systemd
    echo "Reloading systemd..."
    ssh root@${HOST} 'systemctl daemon-reload'
    ssh root@${HOST} 'systemctl reset-failed 2>/dev/null || true'

    echo "Cleanup complete for $NAME"
    echo ""
}

# Cleanup both containers
cleanup_container "10.10.110.247" "ATT"
cleanup_container "10.10.110.246" "Spectrum"

echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
echo ""
echo "Now you can install new services with:"
echo ""
echo "On ATT container:"
echo "  ssh root@10.10.110.247"
echo "  mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-att.timer cake-att-reset.timer"
echo ""
echo "On Spectrum container:"
echo "  ssh root@10.10.110.246"
echo "  mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-spectrum.timer cake-spectrum-reset.timer"
echo ""

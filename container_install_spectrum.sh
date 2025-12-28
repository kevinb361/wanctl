#!/bin/bash
# Run this script ON the Spectrum container (as root or with sudo)
# Usage: sudo ./container_install_spectrum.sh

echo "=========================================="
echo "Installing CAKE services - Spectrum"
echo "=========================================="
echo ""

# Install dependencies first
echo "Installing Python dependencies..."
if ! python3 -c "import yaml; import pexpect" 2>/dev/null; then
    echo "Installing python3-pexpect and python3-yaml..."
    apt update && apt install -y python3-pexpect python3-yaml
    echo "Dependencies installed"
else
    echo "Dependencies already installed"
fi
echo ""

# Check if files exist in /tmp
echo "Checking for unit files..."
if [ ! -f /tmp/cake-spectrum.service ]; then
    echo "ERROR: Unit files not found in /tmp"
    echo "Make sure deployment script has run first"
    exit 1
fi

ls -l /tmp/cake-spectrum*.{service,timer} 2>/dev/null
echo ""

# Move files
echo "Moving unit files to /etc/systemd/system/..."
mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start timers
echo "Enabling and starting timers..."
systemctl enable cake-spectrum.timer cake-spectrum-reset.timer
systemctl start cake-spectrum.timer cake-spectrum-reset.timer

# Show status
echo ""
echo "Timer status:"
systemctl list-timers cake-spectrum* --no-pager
echo ""

echo "Installation complete!"
echo ""
echo "View logs:"
echo "  journalctl -u cake-spectrum.service -f"
echo "  tail -f /home/kevin/wanctl/logs/cake_auto.log"
echo ""

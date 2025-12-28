#!/bin/bash
# Run this script ON each container (as root or with sudo)
# Usage: sudo ./container_cleanup.sh

echo "=========================================="
echo "Cleaning up old CAKE services/timers"
echo "=========================================="
echo ""

# Check what's installed
echo "Current CAKE services/timers:"
systemctl list-unit-files | grep -i cake || echo "  None found"
echo ""

# Stop and disable any running timers
echo "Stopping timers..."
systemctl stop cake-*.timer 2>/dev/null || true
systemctl disable cake-*.timer 2>/dev/null || true

echo "Stopping services..."
systemctl stop cake-*.service 2>/dev/null || true
systemctl disable cake-*.service 2>/dev/null || true

# Remove unit files
echo "Removing old unit files..."
rm -f /etc/systemd/system/cake-*.service /etc/systemd/system/cake-*.timer

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo ""
echo "Cleanup complete!"
echo ""
echo "Remaining CAKE units:"
systemctl list-unit-files | grep -i cake || echo "  None - all cleaned up"
echo ""

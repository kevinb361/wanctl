#!/bin/bash
# Setup logrotate and clean up old logs on both CAKE containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGROTATE_CONFIG="${SCRIPT_DIR}/configs/logrotate-cake"

echo "=== CAKE Log Rotation Setup ==="
echo ""

# Deploy to cake-spectrum
echo "Deploying logrotate config to cake-spectrum..."
ssh cake-spectrum "sudo cp /dev/stdin /etc/logrotate.d/cake" < "${LOGROTATE_CONFIG}"
ssh cake-spectrum "sudo chmod 0644 /etc/logrotate.d/cake"
echo "✓ Logrotate config deployed to cake-spectrum"

# Deploy to cake-att
echo "Deploying logrotate config to cake-att..."
ssh cake-att "sudo cp /dev/stdin /etc/logrotate.d/cake" < "${LOGROTATE_CONFIG}"
ssh cake-att "sudo chmod 0644 /etc/logrotate.d/cake"
echo "✓ Logrotate config deployed to cake-att"

echo ""
echo "=== Cleaning Up Old Logs ==="
echo ""

# Clean up cake-spectrum logs
echo "Cleaning logs on cake-spectrum..."
ssh cake-spectrum 'cd /home/kevin/wanctl/logs && rm -f *.log && echo "✓ Logs deleted"'

# Clean up cake-att logs
echo "Cleaning logs on cake-att..."
ssh cake-att 'cd /home/kevin/wanctl/logs && rm -f *.log && echo "✓ Logs deleted"'

echo ""
echo "=== Testing Logrotate Configuration ==="
echo ""

# Test on cake-spectrum
echo "Testing logrotate on cake-spectrum..."
ssh cake-spectrum "sudo logrotate -d /etc/logrotate.d/cake 2>&1 | head -20"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Logrotate will run daily and:"
echo "  - Rotate logs in /home/kevin/wanctl/logs/"
echo "  - Keep 7 days of rotated logs"
echo "  - Compress old logs (delayed by 1 day)"
echo ""
echo "To manually test rotation:"
echo "  ssh cake-spectrum 'sudo logrotate -f /etc/logrotate.d/cake'"
echo "  ssh cake-att 'sudo logrotate -f /etc/logrotate.d/cake'"
echo ""

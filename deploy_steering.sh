#!/bin/bash
#
# Deploy WAN Steering Daemon to cake-spectrum container
# Colocated with autorate_continuous for local state file access
#
set -e

CONTAINER_IP="10.10.110.246"  # cake-spectrum (colocated)
CONTAINER_USER="kevin"
CONTAINER_PASS="d00kie"

echo "=========================================="
echo " WAN Steering Daemon Deployment"
echo "=========================================="
echo " Target: cake-spectrum ($CONTAINER_IP)"
echo " Colocated with: autorate_continuous"
echo "=========================================="
echo ""

# Check dependencies
command -v sshpass >/dev/null 2>&1 || { echo "ERROR: sshpass not installed"; exit 1; }
command -v ssh >/dev/null 2>&1 || { echo "ERROR: ssh not installed"; exit 1; }

# Create remote directory structure
echo "[1/6] Creating remote directories..."
sshpass -p "$CONTAINER_PASS" ssh ${CONTAINER_USER}@${CONTAINER_IP} \
  "mkdir -p /home/kevin/fusion_cake/configs /home/kevin/fusion_cake/logs /home/kevin/adaptive_cake_steering"

# Copy daemon script
echo "[2/6] Copying wan_steering_daemon.py..."
sshpass -p "$CONTAINER_PASS" scp wan_steering_daemon.py ${CONTAINER_USER}@${CONTAINER_IP}:/home/kevin/fusion_cake/

# Copy config
echo "[3/6] Copying steering_config.yaml..."
sshpass -p "$CONTAINER_PASS" scp configs/steering_config.yaml ${CONTAINER_USER}@${CONTAINER_IP}:/home/kevin/fusion_cake/configs/

# Verify requirements.txt is already present (should be from autorate deployment)
echo "[4/6] Verifying requirements.txt..."
sshpass -p "$CONTAINER_PASS" ssh ${CONTAINER_USER}@${CONTAINER_IP} \
  "test -f /home/kevin/fusion_cake/requirements.txt && echo 'requirements.txt exists' || echo 'WARNING: requirements.txt not found'"

# Copy systemd units to /tmp for manual installation
echo "[5/6] Copying systemd units..."
sshpass -p "$CONTAINER_PASS" scp systemd/wan-steering.service ${CONTAINER_USER}@${CONTAINER_IP}:/tmp/
sshpass -p "$CONTAINER_PASS" scp systemd/wan-steering.timer ${CONTAINER_USER}@${CONTAINER_IP}:/tmp/

# Make script executable
echo "[6/6] Making daemon executable..."
sshpass -p "$CONTAINER_PASS" ssh ${CONTAINER_USER}@${CONTAINER_IP} \
  "chmod +x /home/kevin/fusion_cake/wan_steering_daemon.py"

echo ""
echo "=========================================="
echo " Deployment Complete!"
echo "=========================================="
echo ""
echo "NEXT STEPS (manual, as root on container):"
echo ""
echo "1. SSH to container:"
echo "   ssh root@${CONTAINER_IP}"
echo ""
echo "2. Install systemd units:"
echo "   mv /tmp/wan-steering.service /etc/systemd/system/"
echo "   mv /tmp/wan-steering.timer /etc/systemd/system/"
echo "   systemctl daemon-reload"
echo ""
echo "3. Enable and start timer:"
echo "   systemctl enable wan-steering.timer"
echo "   systemctl start wan-steering.timer"
echo ""
echo "4. Verify operation:"
echo "   systemctl status wan-steering.timer"
echo "   journalctl -u wan-steering.service -f"
echo ""
echo "=========================================="
echo " Monitoring Commands"
echo "=========================================="
echo ""
echo "# Live logs:"
echo "ssh kevin@${CONTAINER_IP} 'journalctl -u wan-steering.service -f'"
echo ""
echo "# State file:"
echo "ssh kevin@${CONTAINER_IP} 'cat /home/kevin/adaptive_cake_steering/steering_state.json'"
echo ""
echo "# Log file:"
echo "ssh kevin@${CONTAINER_IP} 'tail -f /home/kevin/fusion_cake/logs/steering.log'"
echo ""
echo "# RouterOS rule status:"
echo "ssh admin@10.10.99.1 '/ip firewall mangle print where comment~\"ADAPTIVE\"'"
echo ""

#!/bin/bash
set -e

echo "=== Adaptive CAKE Deployment Script ==="
echo ""

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo "ERROR: sshpass not found. Install it with: sudo apt install sshpass"
    exit 1
fi

ATT_HOST="10.10.110.247"
SPECTRUM_HOST="10.10.110.246"
SSH_USER="kevin"
SSH_PASS="d00kie"

echo "=== Deploying to ATT container ($ATT_HOST) ==="
echo "Copying systemd units..."
sshpass -p "$SSH_PASS" scp cake-att.service cake-att.timer cake-att-reset.service cake-att-reset.timer \
    ${SSH_USER}@${ATT_HOST}:/tmp/

echo "Installing units..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${ATT_HOST} << 'EOF'
sudo mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cake-att.timer
sudo systemctl enable cake-att-reset.timer
sudo systemctl start cake-att.timer
sudo systemctl start cake-att-reset.timer
echo "ATT timers enabled and started"
systemctl status cake-att.timer --no-pager
EOF

echo ""
echo "=== Deploying to Spectrum container ($SPECTRUM_HOST) ==="
echo "Copying systemd units..."
sshpass -p "$SSH_PASS" scp cake-spectrum.service cake-spectrum.timer cake-spectrum-reset.service cake-spectrum-reset.timer \
    ${SSH_USER}@${SPECTRUM_HOST}:/tmp/

echo "Installing units..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${SPECTRUM_HOST} << 'EOF'
sudo mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cake-spectrum.timer
sudo systemctl enable cake-spectrum-reset.timer
sudo systemctl start cake-spectrum.timer
sudo systemctl start cake-spectrum-reset.timer
echo "Spectrum timers enabled and started"
systemctl status cake-spectrum.timer --no-pager
EOF

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Verify with:"
echo "  ssh ${SSH_USER}@${ATT_HOST} 'systemctl list-timers cake-*'"
echo "  ssh ${SSH_USER}@${SPECTRUM_HOST} 'systemctl list-timers cake-*'"
echo ""
echo "View logs with:"
echo "  ssh ${SSH_USER}@${ATT_HOST} 'journalctl -u cake-att.service -f'"
echo "  ssh ${SSH_USER}@${SPECTRUM_HOST} 'journalctl -u cake-spectrum.service -f'"

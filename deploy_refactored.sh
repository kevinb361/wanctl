#!/bin/bash
set -e

echo "=========================================="
echo "Adaptive CAKE - Refactored Deployment"
echo "=========================================="
echo ""

# Configuration
ATT_HOST="10.10.110.247"
SPECTRUM_HOST="10.10.110.246"
SSH_USER="kevin"
SSH_PASS="d00kie"
INSTALL_DIR="/home/kevin/wanctl"

# Check dependencies
if ! command -v sshpass &> /dev/null; then
    echo "ERROR: sshpass not found. Install with: sudo apt install sshpass"
    exit 1
fi

echo "Checking Python dependencies on local machine..."
python3 -c "import yaml" 2>/dev/null || {
    echo "Installing PyYAML locally..."
    pip3 install --user PyYAML
}

# =============================================================================
# Deploy to ATT Container
# =============================================================================
echo ""
echo "=========================================="
echo "Deploying to ATT ($ATT_HOST)"
echo "=========================================="

echo "Creating directory structure..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${ATT_HOST} "mkdir -p ${INSTALL_DIR}/configs ${INSTALL_DIR}/logs"

echo "Copying files..."
sshpass -p "$SSH_PASS" scp adaptive_cake.py ${SSH_USER}@${ATT_HOST}:${INSTALL_DIR}/
sshpass -p "$SSH_PASS" scp requirements.txt ${SSH_USER}@${ATT_HOST}:${INSTALL_DIR}/
sshpass -p "$SSH_PASS" scp configs/att_config.yaml ${SSH_USER}@${ATT_HOST}:${INSTALL_DIR}/configs/
sshpass -p "$SSH_PASS" scp systemd/cake-att*.service systemd/cake-att*.timer ${SSH_USER}@${ATT_HOST}:/tmp/

echo "Checking Python dependencies..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${ATT_HOST} << 'EOF'
# Check if dependencies are already installed
python3 -c "import yaml; import pexpect" 2>/dev/null && {
    echo "Dependencies already installed"
    exit 0
}

# Try user install if pip3 available
if command -v pip3 &> /dev/null; then
    echo "Installing via pip3..."
    pip3 install --user pexpect PyYAML
else
    echo "WARNING: pip3 not found and dependencies missing"
    echo "Please manually install: python3-pexpect python3-yaml"
fi
EOF

echo "Making script executable..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${ATT_HOST} "chmod +x ${INSTALL_DIR}/adaptive_cake.py"

echo "Installing systemd units..."
echo "NOTE: Unprivileged container - systemd units need manual installation"
echo ""
echo "On ATT container, run as root:"
echo "  mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-att.timer cake-att-reset.timer"

# =============================================================================
# Deploy to Spectrum Container
# =============================================================================
echo ""
echo "=========================================="
echo "Deploying to Spectrum ($SPECTRUM_HOST)"
echo "=========================================="

echo "Creating directory structure..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${SPECTRUM_HOST} "mkdir -p ${INSTALL_DIR}/configs ${INSTALL_DIR}/logs"

echo "Copying files..."
sshpass -p "$SSH_PASS" scp adaptive_cake.py ${SSH_USER}@${SPECTRUM_HOST}:${INSTALL_DIR}/
sshpass -p "$SSH_PASS" scp requirements.txt ${SSH_USER}@${SPECTRUM_HOST}:${INSTALL_DIR}/
sshpass -p "$SSH_PASS" scp configs/spectrum_config.yaml ${SSH_USER}@${SPECTRUM_HOST}:${INSTALL_DIR}/configs/
sshpass -p "$SSH_PASS" scp systemd/cake-spectrum*.service systemd/cake-spectrum*.timer ${SSH_USER}@${SPECTRUM_HOST}:/tmp/

echo "Checking Python dependencies..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${SPECTRUM_HOST} << 'EOF'
# Check if dependencies are already installed
python3 -c "import yaml; import pexpect" 2>/dev/null && {
    echo "Dependencies already installed"
    exit 0
}

# Try user install if pip3 available
if command -v pip3 &> /dev/null; then
    echo "Installing via pip3..."
    pip3 install --user pexpect PyYAML
else
    echo "WARNING: pip3 not found and dependencies missing"
    echo "Please manually install: python3-pexpect python3-yaml"
fi
EOF

echo "Making script executable..."
sshpass -p "$SSH_PASS" ssh ${SSH_USER}@${SPECTRUM_HOST} "chmod +x ${INSTALL_DIR}/adaptive_cake.py"

echo "Installing systemd units..."
echo "NOTE: Unprivileged container - systemd units need manual installation"
echo ""
echo "On Spectrum container, run as root:"
echo "  mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-spectrum.timer cake-spectrum-reset.timer"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "IMPORTANT: Systemd units require manual installation (unprivileged containers)"
echo ""
echo "On ATT container (ssh root@10.10.110.247):"
echo "  mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-att.timer cake-att-reset.timer"
echo "  systemctl list-timers cake-*"
echo ""
echo "On Spectrum container (ssh root@10.10.110.246):"
echo "  mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now cake-spectrum.timer cake-spectrum-reset.timer"
echo "  systemctl list-timers cake-*"
echo ""
echo "Manual test runs (as user kevin):"
echo "  ssh ${SSH_USER}@${ATT_HOST} 'cd ${INSTALL_DIR} && python3 adaptive_cake.py --config configs/att_config.yaml --debug'"
echo "  ssh ${SSH_USER}@${SPECTRUM_HOST} 'cd ${INSTALL_DIR} && python3 adaptive_cake.py --config configs/spectrum_config.yaml --debug'"
echo ""
echo "View logs (after timers are running):"
echo "  ssh ${SSH_USER}@${ATT_HOST} 'journalctl -u cake-att.service -f'"
echo "  ssh ${SSH_USER}@${ATT_HOST} 'tail -f ${INSTALL_DIR}/logs/cake_auto.log'"
echo ""

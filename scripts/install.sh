#!/bin/bash
#
# wanctl Installation Script
# Sets up FHS-compliant directory structure and service user
#
# Run this script ON the target host (LXC container, VM, or bare metal)
# Requires root privileges
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# FHS Directory Structure
CODE_DIR="/opt/wanctl"
CONFIG_DIR="/etc/wanctl"
STATE_DIR="/var/lib/wanctl"
LOG_DIR="/var/log/wanctl"
RUN_DIR="/run/wanctl"

# Service user
SERVICE_USER="wanctl"
SERVICE_GROUP="wanctl"

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_step() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[x]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[+]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Create service user
create_user() {
    print_step "Creating service user '$SERVICE_USER'..."

    if id "$SERVICE_USER" &>/dev/null; then
        print_warning "User '$SERVICE_USER' already exists"
    else
        useradd -r -s /usr/sbin/nologin -d "$STATE_DIR" -c "wanctl service user" "$SERVICE_USER"
        print_success "Created user '$SERVICE_USER'"
    fi
}

# Create FHS directory structure
create_directories() {
    print_step "Creating directory structure..."

    # Code directory (root:root, world-readable)
    mkdir -p "$CODE_DIR"
    chown root:root "$CODE_DIR"
    chmod 755 "$CODE_DIR"
    print_success "$CODE_DIR (code)"

    # Configuration directory (root:wanctl, group-readable)
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CONFIG_DIR/ssh"
    chown -R root:"$SERVICE_GROUP" "$CONFIG_DIR"
    chmod 750 "$CONFIG_DIR"
    chmod 750 "$CONFIG_DIR/ssh"
    print_success "$CONFIG_DIR (configs)"
    print_success "$CONFIG_DIR/ssh (SSH keys)"

    # Secrets file (root:wanctl, group-readable, restricted)
    if [[ ! -f "$CONFIG_DIR/secrets" ]]; then
        cat > "$CONFIG_DIR/secrets" << 'EOF'
# wanctl secrets file
# This file contains sensitive credentials - DO NOT commit to version control
# Format: KEY=value (no spaces around =)
#
# Example:
# ROUTER_PASSWORD=your_router_password_here
#
# Reference in configs using: ${ROUTER_PASSWORD}
EOF
        chown root:"$SERVICE_GROUP" "$CONFIG_DIR/secrets"
        chmod 640 "$CONFIG_DIR/secrets"
        print_success "$CONFIG_DIR/secrets (credentials - EDIT THIS)"
    else
        print_warning "$CONFIG_DIR/secrets already exists (not overwriting)"
    fi

    # State directory (wanctl:wanctl)
    mkdir -p "$STATE_DIR"
    chown "$SERVICE_USER":"$SERVICE_GROUP" "$STATE_DIR"
    chmod 750 "$STATE_DIR"
    print_success "$STATE_DIR (state files)"

    # SSH known_hosts directory for wanctl user (required for host key validation)
    mkdir -p "$STATE_DIR/.ssh"
    chown "$SERVICE_USER":"$SERVICE_GROUP" "$STATE_DIR/.ssh"
    chmod 700 "$STATE_DIR/.ssh"
    # Create empty known_hosts if it doesn't exist
    if [[ ! -f "$STATE_DIR/.ssh/known_hosts" ]]; then
        touch "$STATE_DIR/.ssh/known_hosts"
        chown "$SERVICE_USER":"$SERVICE_GROUP" "$STATE_DIR/.ssh/known_hosts"
        chmod 600 "$STATE_DIR/.ssh/known_hosts"
    fi
    print_success "$STATE_DIR/.ssh (SSH known_hosts)"

    # Log directory (wanctl:wanctl)
    mkdir -p "$LOG_DIR"
    chown "$SERVICE_USER":"$SERVICE_GROUP" "$LOG_DIR"
    chmod 750 "$LOG_DIR"
    print_success "$LOG_DIR (logs)"

    # Runtime directory (wanctl:wanctl)
    mkdir -p "$RUN_DIR"
    chown "$SERVICE_USER":"$SERVICE_GROUP" "$RUN_DIR"
    chmod 755 "$RUN_DIR"
    print_success "$RUN_DIR (runtime/locks)"
}

# Create tmpfiles.d for /run/wanctl (survives reboots)
create_tmpfiles() {
    print_step "Creating tmpfiles.d configuration..."

    cat > /etc/tmpfiles.d/wanctl.conf << EOF
# wanctl runtime directory
d /run/wanctl 0755 $SERVICE_USER $SERVICE_GROUP -
EOF

    print_success "/etc/tmpfiles.d/wanctl.conf"
}

# Install Python dependencies
install_dependencies() {
    print_step "Checking Python dependencies..."

    if ! command -v python3 &>/dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check for required packages
    local missing=()

    python3 -c "import yaml" 2>/dev/null || missing+=("pyyaml")
    python3 -c "import pexpect" 2>/dev/null || missing+=("pexpect")

    if [[ ${#missing[@]} -gt 0 ]]; then
        print_warning "Missing packages: ${missing[*]}"

        if command -v apt-get &>/dev/null; then
            print_step "Installing via apt..."
            apt-get update -qq
            apt-get install -y python3-yaml python3-pexpect
        elif command -v pip3 &>/dev/null; then
            print_step "Installing via pip..."
            pip3 install pyyaml pexpect
        else
            print_error "Please install: ${missing[*]}"
            exit 1
        fi
    fi

    print_success "Python dependencies satisfied"
}

# Configure logrotate
setup_logrotate() {
    print_step "Configuring log rotation..."

    cat > /etc/logrotate.d/wanctl << 'EOF'
/var/log/wanctl/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 wanctl wanctl
}
EOF

    print_success "/etc/logrotate.d/wanctl"
}

# Print summary and next steps
print_summary() {
    print_header "Installation Complete"

    echo ""
    echo "Directory structure:"
    echo "  $CODE_DIR          - Code files"
    echo "  $CONFIG_DIR        - Configuration files"
    echo "  $CONFIG_DIR/ssh    - SSH keys for router access"
    echo "  $CONFIG_DIR/secrets - Credentials (mode 640)"
    echo "  $STATE_DIR         - State files (JSON)"
    echo "  $LOG_DIR           - Log files"
    echo "  $RUN_DIR           - Runtime/lock files"
    echo ""
    echo "Service user: $SERVICE_USER"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Copy your WAN config to $CONFIG_DIR/wan1.yaml"
    echo ""
    echo "  2. For SSH transport:"
    echo "     a) Copy router SSH key:"
    echo "        sudo cp ~/.ssh/router_key $CONFIG_DIR/ssh/router.key"
    echo "        sudo chmod 600 $CONFIG_DIR/ssh/router.key"
    echo "        sudo chown $SERVICE_USER:$SERVICE_GROUP $CONFIG_DIR/ssh/router.key"
    echo ""
    echo "     b) Add router host key to known_hosts (REQUIRED for security):"
    echo "        sudo -u $SERVICE_USER ssh-keyscan -H <router_ip> >> $STATE_DIR/.ssh/known_hosts"
    echo ""
    echo "  3. For REST API transport (recommended):"
    echo "     Edit $CONFIG_DIR/secrets and add:"
    echo "       ROUTER_PASSWORD=your_router_password"
    echo "     Set transport: \"rest\" in your config file"
    echo ""
    echo "  4. Enable the service:"
    echo "     systemctl enable --now wanctl@wan1.service"
    echo ""
}

# Uninstall function
uninstall() {
    print_header "Uninstalling wanctl"

    print_step "Stopping services..."
    systemctl stop 'wanctl@*.timer' 2>/dev/null || true
    systemctl disable 'wanctl@*.timer' 2>/dev/null || true

    print_step "Removing systemd units..."
    rm -f /etc/systemd/system/wanctl@.service
    rm -f /etc/systemd/system/wanctl@.timer
    rm -f /etc/systemd/system/steering.service
    rm -f /etc/systemd/system/steering.timer
    systemctl daemon-reload

    print_step "Removing directories..."
    rm -rf "$CODE_DIR"
    # Note: CONFIG_DIR contains secrets - prompt before removal
    if [[ -f "$CONFIG_DIR/secrets" ]]; then
        print_warning "$CONFIG_DIR/secrets contains credentials"
        read -p "Remove $CONFIG_DIR? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
        else
            print_warning "Keeping $CONFIG_DIR"
        fi
    else
        rm -rf "$CONFIG_DIR"
    fi
    rm -rf "$STATE_DIR"
    rm -rf "$LOG_DIR"
    rm -rf "$RUN_DIR"

    print_step "Removing configuration files..."
    rm -f /etc/tmpfiles.d/wanctl.conf
    rm -f /etc/logrotate.d/wanctl

    print_step "Removing service user..."
    userdel "$SERVICE_USER" 2>/dev/null || true

    print_success "wanctl has been uninstalled"
}

# Show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Install wanctl with FHS-compliant directory structure"
    echo ""
    echo "Options:"
    echo "  --uninstall    Remove wanctl completely"
    echo "  --help         Show this help message"
    echo ""
    echo "This script must be run as root on the target host."
}

# Main execution
main() {
    check_root

    print_header "wanctl Installation"
    echo ""
    echo "This will set up:"
    echo "  - Service user 'wanctl'"
    echo "  - FHS-compliant directories"
    echo "  - Log rotation"
    echo ""

    create_user
    create_directories
    create_tmpfiles
    install_dependencies
    setup_logrotate

    print_summary
}

# Parse arguments
case "${1:-}" in
    --uninstall)
        check_root
        uninstall
        ;;
    --help|-h)
        usage
        ;;
    *)
        main
        ;;
esac

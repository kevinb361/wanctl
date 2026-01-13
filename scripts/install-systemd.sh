#!/bin/bash
#
# wanctl Systemd Installation Helper
#
# Run this ON the target host to enable wanctl services
# Assumes install.sh and deploy.sh have already been run
#
# Usage:
#   ./install-systemd.sh wan1              # Enable wan1 timer
#   ./install-systemd.sh wan1 wan2         # Enable multiple WANs
#   ./install-systemd.sh wan1 --steering   # Enable with steering
#
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}[+]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[x]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Parse arguments
WANS=()
ENABLE_STEERING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --steering)
            ENABLE_STEERING=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 <wan_name> [wan_name...] [--steering]"
            echo ""
            echo "Enable wanctl timers for specified WANs"
            echo ""
            echo "Options:"
            echo "  --steering    Also enable steering timer"
            exit 0
            ;;
        *)
            WANS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#WANS[@]} -eq 0 ]]; then
    print_error "At least one WAN name required"
    echo "Usage: $0 <wan_name> [--steering]"
    exit 1
fi

# Check prerequisites
if [[ ! -f /etc/systemd/system/wanctl@.service ]]; then
    print_error "wanctl@.service not found - run deploy.sh first"
    exit 1
fi

# Enable WAN timers
for wan in "${WANS[@]}"; do
    if [[ ! -f "/etc/wanctl/${wan}.yaml" ]]; then
        print_warning "Config not found: /etc/wanctl/${wan}.yaml"
        print_warning "Create config before enabling timer"
        continue
    fi

    echo "Enabling wanctl@${wan}..."
    systemctl enable "wanctl@${wan}.timer"
    systemctl start "wanctl@${wan}.timer"
    print_success "wanctl@${wan}.timer enabled and started"
done

# Enable steering if requested
if [[ "$ENABLE_STEERING" == "true" ]]; then
    if [[ ! -f /etc/systemd/system/steering.service ]]; then
        print_error "steering.service not found - deploy with --with-steering"
    elif [[ ! -f "/etc/wanctl/steering.yaml" ]]; then
        print_warning "Steering config not found: /etc/wanctl/steering.yaml"
        print_warning "Create steering config before enabling"
    else
        echo "Enabling steering..."

        # Disable old timer-based deployment if exists (upgrade path)
        if systemctl is-enabled steering.timer &>/dev/null; then
            echo "Disabling old steering.timer (migrating to daemon mode)..."
            systemctl stop steering.timer 2>/dev/null || true
            systemctl disable steering.timer 2>/dev/null || true
        fi

        # Enable daemon service
        systemctl enable steering.service
        systemctl start steering.service
        print_success "steering.service enabled and started (daemon mode)"
    fi
fi

# Show status
echo ""
echo "Active services:"
systemctl list-units 'wanctl@*' 'steering.service' --no-pager 2>/dev/null || true

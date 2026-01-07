#!/bin/bash
#
# Unified Deployment Script for Adaptive CAKE System
# Deploys autorate + steering to both containers using SSH keys
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ATT_HOST="cake-att"
SPECTRUM_HOST="cake-spectrum"
INSTALL_DIR="/home/kevin/wanctl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Files to deploy
COMMON_FILES=(
    "src/cake/autorate_continuous.py"
    "requirements.txt"
)

ATT_CONFIGS=(
    "configs/att_config.yaml"
)

SPECTRUM_FILES=(
    "src/cake/wan_steering_daemon.py"
    "src/cake/cake_stats.py"
    "src/cake/congestion_assessment.py"
    "src/cake/steering_confidence.py"
)

SPECTRUM_CONFIGS=(
    "configs/spectrum_config.yaml"
    "configs/steering_config_v2.yaml"
)

# Systemd units
ATT_SYSTEMD=(
    "systemd/cake-att-continuous.service"
    "systemd/cake-att-continuous.timer"
)

SPECTRUM_SYSTEMD=(
    "systemd/cake-spectrum-continuous.service"
    "systemd/cake-spectrum-continuous.timer"
    "systemd/wan-steering.service"
    "systemd/wan-steering.timer"
)

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_step() {
    echo -e "${GREEN}[$1/$2]${NC} $3"
}

print_warning() {
    echo -e "${YELLOW}⚠ WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}✗ ERROR:${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if we're in the project root
    if [[ ! -f "$PROJECT_ROOT/src/cake/autorate_continuous.py" ]]; then
        print_error "Must be run from wanctl project directory"
        exit 1
    fi

    # Check SSH connectivity
    echo "Testing SSH connectivity..."
    if ! ssh -o ConnectTimeout=5 "$ATT_HOST" 'echo "ATT reachable"' &>/dev/null; then
        print_error "Cannot connect to $ATT_HOST"
        exit 1
    fi
    print_success "ATT container reachable"

    if ! ssh -o ConnectTimeout=5 "$SPECTRUM_HOST" 'echo "Spectrum reachable"' &>/dev/null; then
        print_error "Cannot connect to $SPECTRUM_HOST"
        exit 1
    fi
    print_success "Spectrum container reachable"

    echo ""
}

deploy_to_att() {
    print_header "Deploying to ATT Container ($ATT_HOST)"

    local total_steps=5
    local step=1

    # Create directory structure
    print_step "$step" "$total_steps" "Creating directory structure..."
    ssh "$ATT_HOST" "mkdir -p $INSTALL_DIR/configs $INSTALL_DIR/logs"
    ((step++))

    # Deploy common files
    print_step "$step" "$total_steps" "Deploying autorate script..."
    cd "$PROJECT_ROOT"
    for file in "${COMMON_FILES[@]}"; do
        scp "$file" "$ATT_HOST:$INSTALL_DIR/$(basename "$file")"
    done
    ((step++))

    # Deploy ATT config
    print_step "$step" "$total_steps" "Deploying ATT configuration..."
    for config in "${ATT_CONFIGS[@]}"; do
        scp "$config" "$ATT_HOST:$INSTALL_DIR/configs/$(basename "$config")"
    done
    ((step++))

    # Set permissions
    print_step "$step" "$total_steps" "Setting permissions..."
    ssh "$ATT_HOST" "chmod +x $INSTALL_DIR/autorate_continuous.py"
    ((step++))

    # Copy systemd units to /tmp
    print_step "$step" "$total_steps" "Copying systemd units..."
    for unit in "${ATT_SYSTEMD[@]}"; do
        scp "$unit" "$ATT_HOST:/tmp/$(basename "$unit")"
    done

    print_success "ATT deployment complete"
    echo ""
}

deploy_to_spectrum() {
    print_header "Deploying to Spectrum Container ($SPECTRUM_HOST)"

    local total_steps=6
    local step=1

    # Create directory structure
    print_step "$step" "$total_steps" "Creating directory structure..."
    ssh "$SPECTRUM_HOST" "mkdir -p $INSTALL_DIR/configs $INSTALL_DIR/logs"
    ((step++))

    # Deploy common files
    print_step "$step" "$total_steps" "Deploying autorate script..."
    cd "$PROJECT_ROOT"
    for file in "${COMMON_FILES[@]}"; do
        scp "$file" "$SPECTRUM_HOST:$INSTALL_DIR/$(basename "$file")"
    done
    ((step++))

    # Deploy spectrum-specific files
    print_step "$step" "$total_steps" "Deploying steering daemon and dependencies..."
    for file in "${SPECTRUM_FILES[@]}"; do
        scp "$file" "$SPECTRUM_HOST:$INSTALL_DIR/$(basename "$file")"
    done
    ((step++))

    # Deploy spectrum configs
    print_step "$step" "$total_steps" "Deploying Spectrum configurations..."
    for config in "${SPECTRUM_CONFIGS[@]}"; do
        scp "$config" "$SPECTRUM_HOST:$INSTALL_DIR/configs/$(basename "$config")"
    done
    ((step++))

    # Set permissions
    print_step "$step" "$total_steps" "Setting permissions..."
    ssh "$SPECTRUM_HOST" "chmod +x $INSTALL_DIR/autorate_continuous.py $INSTALL_DIR/wan_steering_daemon.py"
    ((step++))

    # Copy systemd units to /tmp
    print_step "$step" "$total_steps" "Copying systemd units..."
    for unit in "${SPECTRUM_SYSTEMD[@]}"; do
        scp "$unit" "$SPECTRUM_HOST:/tmp/$(basename "$unit")"
    done

    print_success "Spectrum deployment complete"
    echo ""
}

verify_deployment() {
    print_header "Verifying Deployment"

    echo "ATT Container:"
    if ssh "$ATT_HOST" "test -f $INSTALL_DIR/autorate_continuous.py"; then
        print_success "autorate_continuous.py"
    else
        print_error "autorate_continuous.py missing"
    fi

    if ssh "$ATT_HOST" "test -f $INSTALL_DIR/configs/att_config.yaml"; then
        print_success "att_config.yaml"
    else
        print_error "att_config.yaml missing"
    fi

    echo ""
    echo "Spectrum Container:"
    if ssh "$SPECTRUM_HOST" "test -f $INSTALL_DIR/autorate_continuous.py"; then
        print_success "autorate_continuous.py"
    else
        print_error "autorate_continuous.py missing"
    fi

    if ssh "$SPECTRUM_HOST" "test -f $INSTALL_DIR/wan_steering_daemon.py"; then
        print_success "wan_steering_daemon.py"
    else
        print_error "wan_steering_daemon.py missing"
    fi

    if ssh "$SPECTRUM_HOST" "test -f $INSTALL_DIR/configs/spectrum_config.yaml"; then
        print_success "spectrum_config.yaml"
    else
        print_error "spectrum_config.yaml missing"
    fi

    if ssh "$SPECTRUM_HOST" "test -f $INSTALL_DIR/configs/steering_config_v2.yaml"; then
        print_success "steering_config_v2.yaml"
    else
        print_error "steering_config_v2.yaml missing"
    fi

    echo ""
}

print_manual_steps() {
    print_header "Manual Steps Required"

    echo -e "${YELLOW}Systemd units need manual installation (unprivileged containers)${NC}"
    echo ""

    echo -e "${BLUE}On ATT container:${NC}"
    echo "  ssh root@$ATT_HOST"
    echo "  mv /tmp/cake-att-continuous.{service,timer} /etc/systemd/system/"
    echo "  systemctl daemon-reload"
    echo "  systemctl restart cake-att-continuous.timer"
    echo "  systemctl status cake-att-continuous.timer"
    echo ""

    echo -e "${BLUE}On Spectrum container:${NC}"
    echo "  ssh root@$SPECTRUM_HOST"
    echo "  mv /tmp/cake-spectrum-continuous.{service,timer} /tmp/wan-steering.{service,timer} /etc/systemd/system/"
    echo "  systemctl daemon-reload"
    echo "  systemctl restart cake-spectrum-continuous.timer wan-steering.timer"
    echo "  systemctl status cake-spectrum-continuous.timer wan-steering.timer"
    echo ""

    echo -e "${BLUE}Monitoring:${NC}"
    echo "  # ATT logs"
    echo "  ssh $ATT_HOST 'tail -f $INSTALL_DIR/logs/cake_auto.log'"
    echo ""
    echo "  # Spectrum logs"
    echo "  ssh $SPECTRUM_HOST 'tail -f $INSTALL_DIR/logs/cake_auto.log'"
    echo "  ssh $SPECTRUM_HOST 'tail -f $INSTALL_DIR/logs/steering.log'"
    echo ""
}

# Main execution
main() {
    cd "$PROJECT_ROOT"

    print_header "Adaptive CAKE - Unified Deployment"
    echo ""
    echo "This script will deploy:"
    echo "  • Autorate continuous monitoring (both containers)"
    echo "  • WAN steering daemon (Spectrum only)"
    echo "  • Configurations (container-specific)"
    echo ""

    # Check prerequisites
    check_prerequisites

    # Deploy to both containers
    deploy_to_att
    deploy_to_spectrum

    # Verify
    verify_deployment

    # Print manual steps
    print_manual_steps

    print_success "Deployment complete!"
}

# Run main
main

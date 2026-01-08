#!/bin/bash
#
# wanctl Installation Script
# Sets up FHS-compliant directory structure and service user
#
# Run this script ON the target host (LXC container, VM, or bare metal)
# Requires root privileges
#
# Usage:
#   ./install.sh              # Install with interactive wizard (default)
#   ./install.sh --no-wizard  # Install without wizard (for automation)
#   ./install.sh --reconfigure # Re-run wizard on existing install
#   ./install.sh --docker     # Force Docker mode
#   ./install.sh --uninstall  # Remove wanctl
#   ./install.sh --help       # Show help
#
set -e

# Version
VERSION="1.0.0-rc4"

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

# Runtime flags (set by argument parsing)
RUN_WIZARD=true
FORCE_DOCKER=false
RECONFIGURE=false
ENV_TYPE=""  # Detected environment: docker, lxc, systemd, minimal

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

# Check prerequisites before installation
check_prerequisites() {
    print_header "Checking Prerequisites"

    local errors=0
    local warnings=0

    # Python 3.11+ required
    if ! command -v python3 &>/dev/null; then
        print_error "Python 3 is required but not installed"
        errors=$((errors + 1))
    else
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local py_major py_minor
        py_major=$(echo "$py_version" | cut -d. -f1)
        py_minor=$(echo "$py_version" | cut -d. -f2)
        if [[ "$py_major" -lt 3 ]] || [[ "$py_major" -eq 3 && "$py_minor" -lt 11 ]]; then
            print_error "Python 3.11+ required, found $py_version"
            errors=$((errors + 1))
        else
            print_success "Python $py_version"
        fi
    fi

    # curl required for REST API
    if ! command -v curl &>/dev/null; then
        print_warning "curl not found - REST API transport won't work"
        warnings=$((warnings + 1))
    else
        print_success "curl available"
    fi

    # ssh-keygen for SSH key generation
    if ! command -v ssh-keygen &>/dev/null; then
        print_warning "ssh-keygen not found - SSH key generation won't work"
        warnings=$((warnings + 1))
    else
        print_success "ssh-keygen available"
    fi

    # Network connectivity (can we reach common DNS?)
    if ! ping -c 1 -W 2 1.1.1.1 &>/dev/null 2>&1; then
        print_error "No internet connectivity (cannot ping 1.1.1.1)"
        errors=$((errors + 1))
    else
        print_success "Internet connectivity OK"
    fi

    echo ""
    if [[ $errors -gt 0 ]]; then
        print_error "Prerequisites not met ($errors error(s)). Please fix the above issues and try again."
        exit 1
    elif [[ $warnings -gt 0 ]]; then
        print_warning "$warnings warning(s) - some features may not work"
    else
        print_success "All prerequisites met!"
    fi
    echo ""
}

# Detect runtime environment
detect_environment() {
    if [[ "$FORCE_DOCKER" == "true" ]]; then
        ENV_TYPE="docker"
    elif [[ -f /.dockerenv ]]; then
        ENV_TYPE="docker"
    elif [[ -f /run/systemd/container ]]; then
        ENV_TYPE=$(cat /run/systemd/container)  # "lxc", "docker", etc.
    elif systemctl is-system-running &>/dev/null 2>&1; then
        ENV_TYPE="systemd"  # VM or bare metal with systemd
    else
        ENV_TYPE="minimal"  # No systemd
    fi

    print_step "Detected environment: $ENV_TYPE"
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

# Create example configuration files
create_example_configs() {
    print_step "Creating example configurations..."

    # Cable (DOCSIS) example
    if [[ ! -f "$CONFIG_DIR/cable.yaml.example" ]]; then
        cat > "$CONFIG_DIR/cable.yaml.example" << 'CABLEEOF'
# wanctl Configuration - DOCSIS Cable Connection
#
# Template for cable modem (DOCSIS 3.0/3.1) connections.
# Cable has variable latency due to shared spectrum and DOCSIS timing.
#
# Characteristics:
# - Moderate baseline RTT (15-30ms typical)
# - Variable latency (CMTS contention, DOCSIS MAP cycles)
# - Asymmetric speeds (fast download, slower upload)
# - May require median-of-three pings for accuracy

wan_name: "cable"

router:
  transport: "rest"                    # "rest" (recommended) or "ssh"
  host: "192.168.1.1"                  # Your router IP
  user: "admin"
  password: "${ROUTER_PASSWORD}"       # From /etc/wanctl/secrets
  port: 443
  verify_ssl: false
  ssh_key: "/etc/wanctl/ssh/router.key"  # For SSH transport

queues:
  download: "WAN-Download-Cable"       # Your download queue name
  upload: "WAN-Upload-Cable"           # Your upload queue name

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 24             # DOCSIS typical baseline (ms)

  download:
    floor_green_mbps: 550
    floor_yellow_mbps: 350
    floor_soft_red_mbps: 275
    floor_red_mbps: 200
    ceiling_mbps: 940                  # Your plan speed
    step_up_mbps: 10
    factor_down: 0.85

  upload:
    floor_mbps: 8
    ceiling_mbps: 38                   # Your plan upload speed
    step_up_mbps: 1
    factor_down: 0.90

  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    hard_red_bloat_ms: 80
    alpha_baseline: 0.02
    alpha_load: 0.20

  ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
  use_median_of_three: true

logging:
  main_log: "/var/log/wanctl/cable.log"
  debug_log: "/var/log/wanctl/cable_debug.log"

lock_file: "/run/wanctl/cable.lock"
lock_timeout: 300
state_file: "/var/lib/wanctl/cable_state.json"
CABLEEOF
        chown root:"$SERVICE_GROUP" "$CONFIG_DIR/cable.yaml.example"
        chmod 640 "$CONFIG_DIR/cable.yaml.example"
        print_success "cable.yaml.example"
    else
        print_warning "cable.yaml.example already exists"
    fi

    # DSL/VDSL example
    if [[ ! -f "$CONFIG_DIR/dsl.yaml.example" ]]; then
        cat > "$CONFIG_DIR/dsl.yaml.example" << 'DSLEOF'
# wanctl Configuration - DSL/VDSL Connection
#
# Template for DSL (ADSL, VDSL, VDSL2) connections.
# DSL has consistent latency but lower bandwidth and noise sensitivity.
#
# Characteristics:
# - Higher baseline RTT (25-50ms depending on distance)
# - Very asymmetric (upload much slower than download)
# - Sensitive to line noise and interference
# - Requires conservative tuning, especially upload

wan_name: "dsl"

router:
  transport: "rest"                    # "rest" (recommended) or "ssh"
  host: "192.168.1.1"                  # Your router IP
  user: "admin"
  password: "${ROUTER_PASSWORD}"       # From /etc/wanctl/secrets
  port: 443
  verify_ssl: false
  ssh_key: "/etc/wanctl/ssh/router.key"  # For SSH transport

queues:
  download: "WAN-Download-DSL"         # Your download queue name
  upload: "WAN-Upload-DSL"             # Your upload queue name

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 31             # DSL typical baseline (ms)

  download:
    floor_mbps: 25
    ceiling_mbps: 95                   # Your plan speed
    step_up_mbps: 2
    factor_down: 0.90

  upload:
    floor_mbps: 6
    ceiling_mbps: 18                   # Your plan upload speed
    step_up_mbps: 0.5
    factor_down: 0.95

  thresholds:
    target_bloat_ms: 3
    warn_bloat_ms: 10
    alpha_baseline: 0.015
    alpha_load: 0.20

  ping_hosts: ["1.1.1.1"]
  use_median_of_three: false

logging:
  main_log: "/var/log/wanctl/dsl.log"
  debug_log: "/var/log/wanctl/dsl_debug.log"

lock_file: "/run/wanctl/dsl.lock"
lock_timeout: 300
state_file: "/var/lib/wanctl/dsl_state.json"
DSLEOF
        chown root:"$SERVICE_GROUP" "$CONFIG_DIR/dsl.yaml.example"
        chmod 640 "$CONFIG_DIR/dsl.yaml.example"
        print_success "dsl.yaml.example"
    else
        print_warning "dsl.yaml.example already exists"
    fi

    # Fiber example
    if [[ ! -f "$CONFIG_DIR/fiber.yaml.example" ]]; then
        cat > "$CONFIG_DIR/fiber.yaml.example" << 'FIBEREOF'
# wanctl Configuration - Fiber Connection (GPON/XGS-PON)
#
# Template for high-speed, low-latency fiber connections.
# Fiber is typically very stable with consistent low latency.
#
# Characteristics:
# - Low baseline RTT (5-15ms typical)
# - High bandwidth (100M-10G)
# - Very stable, minimal jitter
# - Less aggressive tuning needed

wan_name: "fiber"

router:
  transport: "rest"                    # "rest" (recommended) or "ssh"
  host: "192.168.1.1"                  # Your router IP
  user: "admin"
  password: "${ROUTER_PASSWORD}"       # From /etc/wanctl/secrets
  port: 443
  verify_ssl: false
  ssh_key: "/etc/wanctl/ssh/router.key"  # For SSH transport

queues:
  download: "WAN-Download-Fiber"       # Your download queue name
  upload: "WAN-Upload-Fiber"           # Your upload queue name

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 8              # Fiber typical baseline (ms)

  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 400
    floor_red_mbps: 200
    ceiling_mbps: 950                  # Your plan speed
    step_up_mbps: 20
    factor_down: 0.90

  upload:
    floor_mbps: 100
    ceiling_mbps: 950                  # Your plan upload speed
    step_up_mbps: 10
    factor_down: 0.90

  thresholds:
    target_bloat_ms: 5
    warn_bloat_ms: 15
    hard_red_bloat_ms: 30
    alpha_baseline: 0.01
    alpha_load: 0.15

  ping_hosts: ["1.1.1.1"]
  use_median_of_three: false

logging:
  main_log: "/var/log/wanctl/fiber.log"
  debug_log: "/var/log/wanctl/fiber_debug.log"

lock_file: "/run/wanctl/fiber.lock"
lock_timeout: 300
state_file: "/var/lib/wanctl/fiber_state.json"
FIBEREOF
        chown root:"$SERVICE_GROUP" "$CONFIG_DIR/fiber.yaml.example"
        chmod 640 "$CONFIG_DIR/fiber.yaml.example"
        print_success "fiber.yaml.example"
    else
        print_warning "fiber.yaml.example already exists"
    fi
}

# Print summary and next steps
print_summary() {
    if [[ "$ENV_TYPE" == "docker" ]]; then
        print_header "Installation Complete (Docker)"
    else
        print_header "Installation Complete"
    fi

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

    if [[ "$ENV_TYPE" != "docker" ]]; then
        echo "Service user: $SERVICE_USER"
        echo ""
    fi

    echo "Example configs created:"
    echo "  $CONFIG_DIR/cable.yaml.example  - DOCSIS cable"
    echo "  $CONFIG_DIR/dsl.yaml.example    - DSL/VDSL"
    echo "  $CONFIG_DIR/fiber.yaml.example  - Fiber (GPON)"
    echo ""

    echo -e "${YELLOW}Next steps:${NC}"
    echo ""
    echo "  1. Create your config from an example:"
    echo "     cd $CONFIG_DIR"
    echo "     sudo cp cable.yaml.example wan1.yaml   # or dsl/fiber"
    echo "     sudo nano wan1.yaml"
    echo ""
    echo "  2. Set router credentials (choose one):"
    echo ""
    echo "     Option A - REST API (recommended):"
    echo "       sudo nano $CONFIG_DIR/secrets"
    echo "       Add: ROUTER_PASSWORD=your_password"
    echo ""
    echo "     Option B - SSH key:"
    echo "       sudo cp ~/.ssh/router_key $CONFIG_DIR/ssh/router.key"
    echo "       sudo chown $SERVICE_USER:$SERVICE_GROUP $CONFIG_DIR/ssh/router.key"
    echo "       sudo chmod 600 $CONFIG_DIR/ssh/router.key"
    echo ""

    if [[ "$ENV_TYPE" == "docker" ]]; then
        echo "  3. Run wanctl:"
        echo "     python3 -m wanctl.autorate_continuous --config $CONFIG_DIR/wan1.yaml"
        echo ""
        echo "     For Docker Compose:"
        echo "       command: python3 -m wanctl.autorate_continuous --config $CONFIG_DIR/wan1.yaml"
    else
        echo "  3. Enable the service:"
        echo "     sudo systemctl enable --now wanctl@wan1.service"
        echo ""
        echo "  4. Monitor:"
        echo "     sudo journalctl -u wanctl@wan1 -f"
    fi
    echo ""

    echo -e "${BLUE}Need help?${NC}"
    echo "  Documentation: https://github.com/kevinb361/wanctl/docs"
    echo "  Issues/Support: https://github.com/kevinb361/wanctl/issues"
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
    echo "Install wanctl with FHS-compliant directory structure and optional"
    echo "interactive setup wizard."
    echo ""
    echo "Options:"
    echo "  (default)       Run installation with interactive wizard"
    echo "  --no-wizard     Install without wizard (creates example configs only)"
    echo "  --reconfigure   Re-run wizard on existing installation"
    echo "  --docker        Force Docker mode (skip systemd, stdout logging)"
    echo "  --uninstall     Remove wanctl completely"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo $0                    # Interactive install with wizard"
    echo "  sudo $0 --no-wizard        # Non-interactive install (for automation)"
    echo "  sudo $0 --reconfigure      # Modify existing configuration"
    echo ""
    echo "This script must be run as root on the target host."
    echo ""
    echo "Documentation: https://github.com/kevinb361/wanctl/docs"
    echo "Issues/Support: https://github.com/kevinb361/wanctl/issues"
}

# Main execution
main() {
    check_root

    # Check prerequisites first
    check_prerequisites

    # Detect environment
    detect_environment

    # Handle reconfigure mode (skip base install)
    if [[ "$RECONFIGURE" == "true" ]]; then
        if [[ ! -d "$CONFIG_DIR" ]]; then
            print_error "wanctl is not installed. Run without --reconfigure first."
            exit 1
        fi
        print_header "wanctl Reconfiguration"
        echo ""
        echo "Re-running setup wizard on existing installation..."
        echo ""
        # TODO: run_wizard will be called here in Phase 3
        print_warning "Wizard not yet implemented - coming in Phase 3"
        exit 0
    fi

    print_header "wanctl Installation v$VERSION"
    echo ""
    echo "This will set up:"
    echo "  - Service user 'wanctl'"
    echo "  - FHS-compliant directories"
    echo "  - Log rotation"
    if [[ "$ENV_TYPE" == "docker" ]]; then
        echo ""
        print_warning "Docker mode: skipping systemd and user creation"
    fi
    echo ""

    # Skip user creation in Docker (typically running as root)
    if [[ "$ENV_TYPE" != "docker" ]]; then
        create_user
    else
        print_step "Skipping user creation (Docker mode)"
    fi

    create_directories

    # Skip tmpfiles.d in Docker
    if [[ "$ENV_TYPE" != "docker" ]]; then
        create_tmpfiles
    else
        print_step "Skipping tmpfiles.d (Docker mode)"
    fi

    install_dependencies
    setup_logrotate
    create_example_configs

    # Write version file
    echo "$VERSION" > "$CODE_DIR/.version"
    echo "Installed: $(date -Iseconds)" >> "$CODE_DIR/.version"
    print_success "Installed wanctl version $VERSION"

    # TODO: In Phase 3, run_wizard will be called here if RUN_WIZARD=true

    if [[ "$RUN_WIZARD" == "true" ]]; then
        echo ""
        print_warning "Wizard not yet implemented - coming in Phase 3"
        echo ""
    fi

    print_summary
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-wizard)
            RUN_WIZARD=false
            shift
            ;;
        --reconfigure)
            RECONFIGURE=true
            shift
            ;;
        --docker)
            FORCE_DOCKER=true
            shift
            ;;
        --uninstall)
            check_root
            uninstall
            exit 0
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main
main

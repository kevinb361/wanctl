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
VERSION="1.4.0"

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

    # bc required for floor calculations in wizard (will be auto-installed)
    if ! command -v bc &>/dev/null; then
        print_step "bc not found - will be installed"
    else
        print_success "bc available"
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

# Install dependencies (Python packages and system tools)
install_dependencies() {
    print_step "Checking dependencies..."

    if ! command -v python3 &>/dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check for required Python packages
    local missing_py=()
    python3 -c "import yaml" 2>/dev/null || missing_py+=("python3-yaml")
    python3 -c "import pexpect" 2>/dev/null || missing_py+=("python3-pexpect")

    # Check for required system tools
    local missing_sys=()
    command -v rsync &>/dev/null || missing_sys+=("rsync")
    command -v bc &>/dev/null || missing_sys+=("bc")

    # Install missing packages
    if [[ ${#missing_py[@]} -gt 0 ]] || [[ ${#missing_sys[@]} -gt 0 ]]; then
        local all_missing=("${missing_py[@]}" "${missing_sys[@]}")
        print_warning "Missing packages: ${all_missing[*]}"

        if command -v apt-get &>/dev/null; then
            print_step "Installing via apt..."
            apt-get update -qq
            apt-get install -y "${all_missing[@]}"
        else
            # Try pip for Python packages only
            if [[ ${#missing_py[@]} -gt 0 ]] && command -v pip3 &>/dev/null; then
                print_step "Installing Python packages via pip..."
                pip3 install pyyaml pexpect
            fi
            # Warn about missing system tools
            if [[ ${#missing_sys[@]} -gt 0 ]]; then
                print_warning "Please install system packages manually: ${missing_sys[*]}"
            fi
        fi
    fi

    print_success "Dependencies satisfied"
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

# ============================================================================
# WIZARD FUNCTIONS
# ============================================================================

# Prompt for a selection from numbered options
# Usage: prompt_selection "Question" "option1" "option2" ...
# Returns: selected option number (1-based) in REPLY
prompt_selection() {
    local question="$1"
    shift
    local options=("$@")
    local num_options=${#options[@]}

    echo ""
    echo -e "${BLUE}$question${NC}"
    for i in "${!options[@]}"; do
        echo "  $((i+1))) ${options[$i]}"
    done

    while true; do
        read -p "Choice [1-$num_options]: " REPLY
        if [[ "$REPLY" =~ ^[0-9]+$ ]] && [[ "$REPLY" -ge 1 ]] && [[ "$REPLY" -le "$num_options" ]]; then
            return 0
        fi
        echo "Please enter a number between 1 and $num_options"
    done
}

# Prompt for text input with default value
# Usage: prompt_input "Question" "default"
# Returns: user input (or default) in REPLY
prompt_input() {
    local question="$1"
    local default="$2"

    echo ""
    if [[ -n "$default" ]]; then
        read -p "$question [$default]: " REPLY
        REPLY="${REPLY:-$default}"
    else
        read -p "$question: " REPLY
    fi
}

# Prompt for password (hidden input)
# Usage: prompt_password "Question"
# Returns: password in REPLY
prompt_password() {
    local question="$1"

    echo ""
    read -s -p "$question: " REPLY
    echo ""  # New line after hidden input
}

# Prompt for yes/no with default
# Usage: prompt_yesno "Question" "y" (default yes) or "n" (default no)
# Returns: 0 for yes, 1 for no
prompt_yesno() {
    local question="$1"
    local default="${2:-n}"

    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="$question [Y/n]: "
    else
        prompt="$question [y/N]: "
    fi

    echo ""
    read -p "$prompt" REPLY
    REPLY="${REPLY:-$default}"

    if [[ "$REPLY" =~ ^[Yy] ]]; then
        return 0
    else
        return 1
    fi
}

# Test router connection
# Usage: test_router_connection "transport" "router_ip" ["password"]
# Returns: 0 on success, 1 on failure
test_router_connection() {
    local transport="$1"
    local router_ip="$2"
    local password="$3"  # Only used for REST

    print_step "Testing connection to $router_ip..."

    if [[ "$transport" == "rest" ]]; then
        # Test REST API - try to get system resource info
        if [[ -z "$password" ]]; then
            print_error "No password provided for REST API test"
            return 1
        fi

        local response
        local http_code

        # Use curl with timeout, suppress progress, get HTTP code
        http_code=$(curl -s -k -o /dev/null -w "%{http_code}" \
            -u "admin:$password" \
            --connect-timeout 5 \
            --max-time 10 \
            "https://${router_ip}/rest/system/resource" 2>/dev/null)

        case "$http_code" in
            200)
                print_success "REST API connection successful"
                return 0
                ;;
            401)
                print_error "Authentication failed (HTTP 401) - check password"
                return 1
                ;;
            000)
                print_error "Connection failed - check IP address and network"
                return 1
                ;;
            *)
                print_error "Unexpected response (HTTP $http_code)"
                return 1
                ;;
        esac

    elif [[ "$transport" == "ssh" ]]; then
        # Test SSH connection
        local ssh_key="$CONFIG_DIR/ssh/router.key"

        if [[ ! -f "$ssh_key" ]]; then
            print_error "SSH key not found at $ssh_key"
            return 1
        fi

        # Test SSH with timeout, run simple command
        local ssh_output
        if ssh_output=$(ssh -i "$ssh_key" \
            -o ConnectTimeout=5 \
            -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes \
            "admin@${router_ip}" \
            '/system resource print' 2>&1); then
            print_success "SSH connection successful"
            return 0
        else
            # Check for common errors
            if echo "$ssh_output" | grep -qi "permission denied"; then
                print_error "SSH authentication failed - check key is authorized on router"
            elif echo "$ssh_output" | grep -qi "connection refused"; then
                print_error "SSH connection refused - check SSH is enabled on router"
            elif echo "$ssh_output" | grep -qi "no route\|network is unreachable"; then
                print_error "Network unreachable - check IP address"
            elif echo "$ssh_output" | grep -qi "timed out"; then
                print_error "Connection timed out - check IP address and firewall"
            else
                print_error "SSH connection failed: $ssh_output"
            fi
            return 1
        fi
    else
        print_error "Unknown transport: $transport"
        return 1
    fi
}

# Discover queue tree names from router
# Usage: discover_queues "transport" "router_ip" ["password"]
# Outputs queue names to stdout (one per line)
# Returns: 0 if queues found, 1 if none or error
discover_queues() {
    local transport="$1"
    local router_ip="$2"
    local password="$3"

    local queues=""

    if [[ "$transport" == "rest" ]]; then
        if [[ -z "$password" ]]; then
            return 1
        fi

        # Query REST API for queue tree
        local response
        response=$(curl -s -k \
            -u "admin:$password" \
            --connect-timeout 5 \
            --max-time 10 \
            "https://${router_ip}/rest/queue/tree" 2>/dev/null)

        if [[ -z "$response" ]]; then
            return 1
        fi

        # Parse JSON response - extract "name" fields
        # RouterOS REST returns array of objects with "name" field
        queues=$(echo "$response" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | sort -u)

    elif [[ "$transport" == "ssh" ]]; then
        local ssh_key="$CONFIG_DIR/ssh/router.key"

        if [[ ! -f "$ssh_key" ]]; then
            return 1
        fi

        # Query via SSH
        local response
        response=$(ssh -i "$ssh_key" \
            -o ConnectTimeout=5 \
            -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes \
            "admin@${router_ip}" \
            '/queue tree print terse' 2>/dev/null)

        if [[ -z "$response" ]]; then
            return 1
        fi

        # Parse terse output - extract name= values
        queues=$(echo "$response" | grep -o 'name=[^ ]*' | cut -d= -f2 | sort -u)
    else
        return 1
    fi

    # Output queues if any found
    if [[ -n "$queues" ]]; then
        echo "$queues"
        return 0
    else
        return 1
    fi
}

# Select a queue from discovered list or enter manually
# Usage: select_queue "prompt" "default" "queue_list"
# Returns selected queue in REPLY
select_queue() {
    local prompt="$1"
    local default="$2"
    local queue_list="$3"

    if [[ -z "$queue_list" ]]; then
        # No queues discovered - manual entry
        prompt_input "$prompt" "$default"
        return
    fi

    # Convert newline-separated list to array
    local -a queues
    while IFS= read -r line; do
        [[ -n "$line" ]] && queues+=("$line")
    done <<< "$queue_list"

    local num_queues=${#queues[@]}

    if [[ $num_queues -eq 0 ]]; then
        prompt_input "$prompt" "$default"
        return
    fi

    # Show selection menu
    echo ""
    echo -e "${BLUE}$prompt${NC}"
    echo "  Discovered queues:"
    local i
    for i in "${!queues[@]}"; do
        echo "    $((i+1))) ${queues[$i]}"
    done
    echo "    $((num_queues+1))) Enter manually"

    while true; do
        read -p "Choice [1-$((num_queues+1))]: " REPLY
        if [[ "$REPLY" =~ ^[0-9]+$ ]]; then
            if [[ "$REPLY" -ge 1 ]] && [[ "$REPLY" -le "$num_queues" ]]; then
                REPLY="${queues[$((REPLY-1))]}"
                return
            elif [[ "$REPLY" -eq $((num_queues+1)) ]]; then
                prompt_input "Enter queue name" "$default"
                return
            fi
        fi
        echo "Please enter a number between 1 and $((num_queues+1))"
    done
}

# Generate a config file from wizard inputs
generate_config() {
    local wan_name="$1"
    local conn_type="$2"
    local router_ip="$3"
    local transport="$4"
    local queue_down="$5"
    local queue_up="$6"
    local speed_down="$7"
    local speed_up="$8"

    local config_file="$CONFIG_DIR/${wan_name}.yaml"

    # Set connection-type-specific defaults
    local baseline_rtt floor_green floor_yellow floor_soft_red floor_red
    local floor_up step_up_down step_up_up factor_down_down factor_down_up
    local target_bloat warn_bloat hard_red_bloat alpha_baseline alpha_load
    local use_median ping_hosts

    case "$conn_type" in
        cable)
            baseline_rtt=24
            floor_green=550; floor_yellow=350; floor_soft_red=275; floor_red=200
            floor_up=8
            step_up_down=10; step_up_up=1
            factor_down_down=0.85; factor_down_up=0.90
            target_bloat=15; warn_bloat=45; hard_red_bloat=80
            alpha_baseline=0.02; alpha_load=0.20
            use_median=true
            ping_hosts='["1.1.1.1", "8.8.8.8", "9.9.9.9"]'
            ;;
        dsl)
            baseline_rtt=31
            floor_green=25; floor_yellow=0; floor_soft_red=0; floor_red=0  # DSL uses simple floor
            floor_up=6
            step_up_down=2; step_up_up=0.5
            factor_down_down=0.90; factor_down_up=0.95
            target_bloat=3; warn_bloat=10; hard_red_bloat=0  # No SOFT_RED for DSL
            alpha_baseline=0.015; alpha_load=0.20
            use_median=false
            ping_hosts='["1.1.1.1"]'
            ;;
        fiber)
            baseline_rtt=8
            floor_green=800; floor_yellow=600; floor_soft_red=400; floor_red=200
            floor_up=100
            step_up_down=20; step_up_up=10
            factor_down_down=0.90; factor_down_up=0.90
            target_bloat=5; warn_bloat=15; hard_red_bloat=30
            alpha_baseline=0.01; alpha_load=0.15
            use_median=false
            ping_hosts='["1.1.1.1"]'
            ;;
    esac

    # Scale floors based on actual speed (rough approximation)
    if [[ "$conn_type" == "cable" || "$conn_type" == "fiber" ]]; then
        if command -v bc &>/dev/null; then
            # Scale floors proportionally to speed
            local scale=$(echo "scale=2; $speed_down / 1000" | bc)
            floor_green=$(echo "scale=0; $floor_green * $scale" | bc | cut -d. -f1)
            floor_yellow=$(echo "scale=0; $floor_yellow * $scale" | bc | cut -d. -f1)
            floor_soft_red=$(echo "scale=0; $floor_soft_red * $scale" | bc | cut -d. -f1)
            floor_red=$(echo "scale=0; $floor_red * $scale" | bc | cut -d. -f1)
            # Ensure minimums
            [[ "$floor_green" -lt 50 ]] && floor_green=50
            [[ "$floor_yellow" -lt 30 ]] && floor_yellow=30
            [[ "$floor_soft_red" -lt 20 ]] && floor_soft_red=20
            [[ "$floor_red" -lt 10 ]] && floor_red=10
        else
            # bc not available - use simple percentage-based defaults
            # Set floors as percentages of speed: green=55%, yellow=35%, soft_red=25%, red=20%
            floor_green=$((speed_down * 55 / 100))
            floor_yellow=$((speed_down * 35 / 100))
            floor_soft_red=$((speed_down * 25 / 100))
            floor_red=$((speed_down * 20 / 100))
            # Ensure minimums
            [[ "$floor_green" -lt 50 ]] && floor_green=50
            [[ "$floor_yellow" -lt 30 ]] && floor_yellow=30
            [[ "$floor_soft_red" -lt 20 ]] && floor_soft_red=20
            [[ "$floor_red" -lt 10 ]] && floor_red=10
        fi
    fi

    # Backup existing config if present
    if [[ -f "$config_file" ]]; then
        local backup="${config_file}.bak.$(date +%Y%m%d_%H%M%S)"
        cp "$config_file" "$backup"
        print_warning "Existing config backed up to: $backup"
    fi

    # Generate the config
    cat > "$config_file" << CONFIGEOF
# wanctl Configuration - Generated by wizard
# Connection type: $conn_type
# Generated: $(date -Iseconds)

wan_name: "$wan_name"

router:
  transport: "$transport"
  host: "$router_ip"
  user: "admin"
  password: "\${ROUTER_PASSWORD}"
  port: 443
  verify_ssl: false
  ssh_key: "$CONFIG_DIR/ssh/router.key"

queues:
  download: "$queue_down"
  upload: "$queue_up"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: $baseline_rtt

CONFIGEOF

    # Add download config based on connection type
    if [[ "$conn_type" == "dsl" ]]; then
        # DSL uses simple 3-state
        cat >> "$config_file" << CONFIGEOF
  download:
    floor_mbps: $floor_green
    ceiling_mbps: $speed_down
    step_up_mbps: $step_up_down
    factor_down: $factor_down_down

CONFIGEOF
    else
        # Cable/Fiber use 4-state
        cat >> "$config_file" << CONFIGEOF
  download:
    floor_green_mbps: $floor_green
    floor_yellow_mbps: $floor_yellow
    floor_soft_red_mbps: $floor_soft_red
    floor_red_mbps: $floor_red
    ceiling_mbps: $speed_down
    step_up_mbps: $step_up_down
    factor_down: $factor_down_down

CONFIGEOF
    fi

    # Add upload and thresholds
    cat >> "$config_file" << CONFIGEOF
  upload:
    floor_mbps: $floor_up
    ceiling_mbps: $speed_up
    step_up_mbps: $step_up_up
    factor_down: $factor_down_up

  thresholds:
    target_bloat_ms: $target_bloat
    warn_bloat_ms: $warn_bloat
CONFIGEOF

    # Add hard_red_bloat only for 4-state
    if [[ "$hard_red_bloat" -gt 0 ]]; then
        echo "    hard_red_bloat_ms: $hard_red_bloat" >> "$config_file"
    fi

    cat >> "$config_file" << CONFIGEOF
    alpha_baseline: $alpha_baseline
    alpha_load: $alpha_load

  ping_hosts: $ping_hosts
  use_median_of_three: $use_median

logging:
  main_log: "$LOG_DIR/${wan_name}.log"
  debug_log: "$LOG_DIR/${wan_name}_debug.log"

lock_file: "$RUN_DIR/${wan_name}.lock"
lock_timeout: 300
state_file: "$STATE_DIR/${wan_name}_state.json"
CONFIGEOF

    chown root:"$SERVICE_GROUP" "$config_file"
    chmod 640 "$config_file"

    print_success "Created $config_file"
}

# Main wizard function
run_wizard() {
    print_header "wanctl Setup Wizard"

    echo ""
    echo "This wizard will help you configure wanctl for your network."
    echo "Press Ctrl+C at any time to exit."
    echo ""

    # -------------------------------------------------------------------------
    # Step 1: Router Setup
    # -------------------------------------------------------------------------
    echo -e "${BLUE}--- Router Setup ---${NC}"

    prompt_input "Router IP address" "192.168.1.1"
    local router_ip="$REPLY"

    prompt_selection "Select transport method:" \
        "REST API (recommended - faster)" \
        "SSH"
    local transport_choice="$REPLY"

    local transport
    local router_password=""  # Save for connection testing

    if [[ "$transport_choice" == "1" ]]; then
        transport="rest"

        # REST password setup
        echo ""
        print_step "Setting up REST API credentials..."
        echo ""
        echo "Password will be stored in $CONFIG_DIR/secrets (mode 640, readable only by root and wanctl)."
        echo "Input is hidden."
        prompt_password "Router password for admin@$router_ip (or Enter to skip)"

        if [[ -n "$REPLY" ]]; then
            router_password="$REPLY"  # Save for connection test
            # Save to secrets file (delete existing, then append)
            # Using grep -v and printf to safely handle special characters
            if [[ -f "$CONFIG_DIR/secrets" ]]; then
                grep -v "^ROUTER_PASSWORD=" "$CONFIG_DIR/secrets" > "$CONFIG_DIR/secrets.tmp" || true
                mv "$CONFIG_DIR/secrets.tmp" "$CONFIG_DIR/secrets"
            fi
            printf 'ROUTER_PASSWORD=%s\n' "$REPLY" >> "$CONFIG_DIR/secrets"
            chown root:"$SERVICE_GROUP" "$CONFIG_DIR/secrets"
            chmod 640 "$CONFIG_DIR/secrets"
            print_success "Password saved to $CONFIG_DIR/secrets"
        else
            print_warning "Skipped - set ROUTER_PASSWORD in $CONFIG_DIR/secrets manually"
        fi
    else
        transport="ssh"

        # SSH key setup
        echo ""
        print_step "Setting up SSH authentication..."

        if [[ -f "$CONFIG_DIR/ssh/router.key" ]]; then
            print_success "SSH key already exists at $CONFIG_DIR/ssh/router.key"
        else
            prompt_selection "SSH key setup:" \
                "Generate a new SSH key (recommended)" \
                "Copy an existing key from ~/.ssh/" \
                "Skip - I'll set it up manually"

            case "$REPLY" in
                1)
                    # Generate new key
                    ssh-keygen -t ed25519 -f "$CONFIG_DIR/ssh/router.key" -N "" -C "wanctl@$(hostname)"
                    chown "$SERVICE_USER":"$SERVICE_GROUP" "$CONFIG_DIR/ssh/router.key"
                    chmod 600 "$CONFIG_DIR/ssh/router.key"
                    print_success "Created $CONFIG_DIR/ssh/router.key"
                    echo ""
                    echo -e "${YELLOW}IMPORTANT: Add this public key to your router:${NC}"
                    echo ""
                    cat "$CONFIG_DIR/ssh/router.key.pub"
                    echo ""
                    echo "In RouterOS, run:"
                    echo "  /user ssh-keys import public-key-file=wanctl.pub user=admin"
                    echo ""
                    read -p "Press Enter when done..."
                    ;;
                2)
                    # Copy existing key - use SUDO_USER's home if available
                    local user_home
                    if [[ -n "$SUDO_USER" ]]; then
                        user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
                    else
                        user_home="$HOME"
                    fi
                    local ssh_dir="$user_home/.ssh"

                    echo ""
                    if [[ -d "$ssh_dir" ]]; then
                        echo "Available keys in $ssh_dir/:"
                        ls -1 "$ssh_dir"/*.pub 2>/dev/null | while read f; do basename "${f%.pub}"; done
                    else
                        echo "No .ssh directory found at $ssh_dir"
                    fi
                    prompt_input "Key name to copy (or full path)" "id_ed25519"
                    local keyname="$REPLY"

                    # Handle both relative and absolute paths
                    local keypath
                    if [[ "$keyname" == /* ]]; then
                        keypath="$keyname"
                    else
                        keypath="$ssh_dir/$keyname"
                    fi

                    if [[ -f "$keypath" ]]; then
                        cp "$keypath" "$CONFIG_DIR/ssh/router.key"
                        chown "$SERVICE_USER":"$SERVICE_GROUP" "$CONFIG_DIR/ssh/router.key"
                        chmod 600 "$CONFIG_DIR/ssh/router.key"
                        print_success "Copied to $CONFIG_DIR/ssh/router.key"
                    else
                        print_error "Key not found: $keypath"
                        print_warning "Set up SSH key manually"
                    fi
                    ;;
                3)
                    print_warning "Skipped - set up SSH key manually at $CONFIG_DIR/ssh/router.key"
                    ;;
            esac
        fi
    fi

    # -------------------------------------------------------------------------
    # Connection Test
    # -------------------------------------------------------------------------
    local can_test=false
    if [[ "$transport" == "rest" && -n "$router_password" ]]; then
        can_test=true
    elif [[ "$transport" == "ssh" && -f "$CONFIG_DIR/ssh/router.key" ]]; then
        can_test=true
    fi

    if [[ "$can_test" == "true" ]]; then
        echo ""
        echo -e "${BLUE}--- Testing Router Connection ---${NC}"

        local test_attempts=0
        local max_attempts=3

        while [[ $test_attempts -lt $max_attempts ]]; do
            test_attempts=$((test_attempts + 1))

            if test_router_connection "$transport" "$router_ip" "$router_password"; then
                # Success - continue with wizard
                break
            else
                # Failure - offer retry or skip
                echo ""
                if [[ $test_attempts -lt $max_attempts ]]; then
                    prompt_selection "Connection failed. What would you like to do?" \
                        "Retry connection test" \
                        "Re-enter credentials" \
                        "Skip test and continue anyway"

                    case "$REPLY" in
                        1)
                            # Retry - loop continues
                            ;;
                        2)
                            # Re-enter credentials
                            if [[ "$transport" == "rest" ]]; then
                                echo "(stored securely in $CONFIG_DIR/secrets)"
                                prompt_password "Router password for admin@$router_ip"
                                if [[ -n "$REPLY" ]]; then
                                    router_password="$REPLY"
                                    if [[ -f "$CONFIG_DIR/secrets" ]]; then
                                        grep -v "^ROUTER_PASSWORD=" "$CONFIG_DIR/secrets" > "$CONFIG_DIR/secrets.tmp" || true
                                        mv "$CONFIG_DIR/secrets.tmp" "$CONFIG_DIR/secrets"
                                    fi
                                    printf 'ROUTER_PASSWORD=%s\n' "$REPLY" >> "$CONFIG_DIR/secrets"
                                    chmod 640 "$CONFIG_DIR/secrets"
                                fi
                            else
                                print_warning "For SSH, manually update key at: $CONFIG_DIR/ssh/router.key"
                                read -p "Press Enter when ready to retry..."
                            fi
                            ;;
                        3)
                            # Skip
                            print_warning "Skipping connection test - verify manually later"
                            break
                            ;;
                    esac
                else
                    # Max attempts reached
                    if prompt_yesno "Max attempts reached. Continue anyway?" "n"; then
                        print_warning "Continuing without verified connection"
                    else
                        print_error "Wizard aborted. Fix connection issues and run: $0 --reconfigure"
                        exit 1
                    fi
                fi
            fi
        done
    else
        echo ""
        print_warning "Skipping connection test (no credentials provided)"
        print_warning "Test manually after completing setup"
    fi

    # -------------------------------------------------------------------------
    # Step 2: WAN Count
    # -------------------------------------------------------------------------
    echo ""
    echo -e "${BLUE}--- WAN Configuration ---${NC}"

    prompt_selection "How many WAN connections do you have?" \
        "Single WAN" \
        "Dual WAN (e.g., cable + DSL)" \
        "Three or more WANs"
    local wan_count="$REPLY"

    local is_multi_wan=false
    local is_primary_host=false

    if [[ "$wan_count" != "1" ]]; then
        is_multi_wan=true

        # Show multi-WAN architecture explanation
        echo ""
        echo -e "${YELLOW}========================================"
        echo -e "IMPORTANT: Multi-WAN Architecture"
        echo -e "========================================${NC}"
        echo ""
        echo "For accurate RTT monitoring, each WAN requires its own wanctl"
        echo "instance running on a host that routes through that WAN."
        echo ""
        echo "Deployment options:"
        echo "  A) Separate hosts (recommended for accuracy):"
        echo "     - Host 1 (routes via Cable) → wanctl for Cable + steering"
        echo "     - Host 2 (routes via DSL)   → wanctl for DSL"
        echo ""
        echo "  B) Single controller host (simpler, if routing allows):"
        echo "     - One host with policy routing to test each WAN separately"
        echo ""
        echo "This wizard will configure ONE WAN for THIS host."
        echo ""
        read -p "Press Enter to continue..."
    fi

    # -------------------------------------------------------------------------
    # Step 3: Configure THIS Host's WAN
    # -------------------------------------------------------------------------
    echo ""
    echo -e "${BLUE}--- Configure THIS Host's WAN ---${NC}"

    prompt_input "WAN name" "wan1"
    local wan_name="$REPLY"

    prompt_selection "Connection type:" \
        "Cable (DOCSIS) - variable latency, asymmetric speeds" \
        "DSL/VDSL - higher baseline RTT, sensitive upload" \
        "Fiber - low latency, stable"
    local conn_type_choice="$REPLY"

    local conn_type
    case "$conn_type_choice" in
        1) conn_type="cable" ;;
        2) conn_type="dsl" ;;
        3) conn_type="fiber" ;;
    esac

    # Queue discovery from router
    local default_queue_down="WAN-Download-${wan_name^}"
    local default_queue_up="WAN-Upload-${wan_name^}"
    local discovered_queues=""

    # Try to discover existing queues
    print_step "Discovering queues from router..."
    if discovered_queues=$(discover_queues "$transport" "$router_ip" "$router_password" 2>/dev/null); then
        local queue_count
        queue_count=$(echo "$discovered_queues" | wc -l)
        print_success "Found $queue_count queue(s)"
    else
        print_warning "Could not discover queues - will use manual entry"
        discovered_queues=""
    fi

    # Select download queue
    select_queue "Select DOWNLOAD queue:" "$default_queue_down" "$discovered_queues"
    local queue_down="$REPLY"

    # Select upload queue
    select_queue "Select UPLOAD queue:" "$default_queue_up" "$discovered_queues"
    local queue_up="$REPLY"

    # Bandwidth settings with connection-type defaults
    local default_down default_up
    case "$conn_type" in
        cable) default_down=500; default_up=50 ;;
        dsl)   default_down=100; default_up=20 ;;
        fiber) default_down=1000; default_up=1000 ;;
    esac

    prompt_input "Download speed (Mbps)" "$default_down"
    local speed_down="$REPLY"

    prompt_input "Upload speed (Mbps)" "$default_up"
    local speed_up="$REPLY"

    # Generate the config
    echo ""
    generate_config "$wan_name" "$conn_type" "$router_ip" "$transport" \
        "$queue_down" "$queue_up" "$speed_down" "$speed_up"

    # -------------------------------------------------------------------------
    # Step 4: Steering Setup (multi-WAN only)
    # -------------------------------------------------------------------------
    if [[ "$is_multi_wan" == "true" ]]; then
        echo ""
        echo -e "${BLUE}--- Steering Configuration ---${NC}"

        prompt_selection "Is this the PRIMARY WAN host? (Steering daemon runs here)" \
            "Yes - this host monitors the primary/default WAN" \
            "No - this host monitors a secondary WAN"

        if [[ "$REPLY" == "1" ]]; then
            is_primary_host=true

            if prompt_yesno "Enable WAN steering? (Routes latency-sensitive traffic during congestion)" "y"; then
                echo ""
                echo -e "${YELLOW}========================================"
                echo -e "IMPORTANT: RouterOS Setup Required"
                echo -e "========================================${NC}"
                echo ""
                echo "WAN steering requires additional RouterOS configuration:"
                echo "  - Mangle rules for traffic marking"
                echo "  - Routing rules for WAN selection"
                echo "  - Connection tracking marks"
                echo ""
                echo "See: docs/STEERING_ROUTEROS_SETUP.md"
                echo ""

                if prompt_yesno "Continue with steering setup?" "y"; then
                    # Create basic steering config
                    local steering_file="$CONFIG_DIR/steering.yaml"

                    if [[ -f "$steering_file" ]]; then
                        local backup="${steering_file}.bak.$(date +%Y%m%d_%H%M%S)"
                        cp "$steering_file" "$backup"
                        print_warning "Existing steering config backed up to: $backup"
                    fi

                    cat > "$steering_file" << STEEREOF
# wanctl Steering Configuration
# Generated by wizard: $(date -Iseconds)
#
# IMPORTANT: This requires RouterOS mangle rules to be configured.
# See docs/STEERING_ROUTEROS_SETUP.md for setup instructions.

primary_wan: "$wan_name"

router:
  transport: "$transport"
  host: "$router_ip"
  user: "admin"
  password: "\${ROUTER_PASSWORD}"
  port: 443
  verify_ssl: false

steering:
  enabled: true
  check_interval: 2
  enable_threshold: 3
  disable_threshold: 15

logging:
  main_log: "$LOG_DIR/steering.log"
STEEREOF

                    chown root:"$SERVICE_GROUP" "$steering_file"
                    chmod 640 "$steering_file"
                    print_success "Created $steering_file"
                else
                    print_warning "Steering skipped - enable later with --reconfigure"
                fi
            fi
        fi
    fi

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    echo ""
    print_header "Setup Complete!"

    echo ""
    echo "Configuration created:"
    echo "  $CONFIG_DIR/${wan_name}.yaml"
    if [[ "$is_multi_wan" == "true" && "$is_primary_host" == "true" ]] && [[ -f "$CONFIG_DIR/steering.yaml" ]]; then
        echo "  $CONFIG_DIR/steering.yaml"
    fi
    echo ""
    echo "Credentials: $CONFIG_DIR/secrets"
    echo ""

    if [[ "$ENV_TYPE" == "docker" ]]; then
        echo "To run wanctl:"
        echo "  python3 -m wanctl.autorate_continuous --config $CONFIG_DIR/${wan_name}.yaml"
    else
        echo "To start wanctl on THIS host:"
        echo "  sudo systemctl enable --now wanctl@${wan_name}.service"

        if [[ "$is_multi_wan" == "true" && "$is_primary_host" == "true" ]] && [[ -f "$CONFIG_DIR/steering.yaml" ]]; then
            echo "  sudo systemctl enable --now steering.timer"
        fi

        if [[ "$is_multi_wan" == "true" && "$is_primary_host" == "true" ]]; then
            echo ""
            echo -e "${YELLOW}NEXT: Run this wizard on your secondary WAN host(s)${NC}"
        fi
    fi
    echo ""
    echo "To monitor:"
    if [[ "$ENV_TYPE" == "docker" ]]; then
        echo "  (logs go to stdout in Docker)"
    else
        echo "  sudo journalctl -u wanctl@${wan_name} -f"
    fi
    echo ""
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
        run_wizard
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

    # Run interactive wizard if requested
    if [[ "$RUN_WIZARD" == "true" ]]; then
        run_wizard
    else
        print_summary
    fi
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

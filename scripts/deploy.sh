#!/bin/bash
#
# wanctl Unified Deployment Script
#
# Deploys wanctl to a target host (LXC container, VM, or bare metal)
# Uses generic WAN naming and FHS-compliant paths
#
# Usage:
#   ./deploy.sh wan1 target-host              # Deploy wan1 config
#   ./deploy.sh wan1 target-host --with-steering  # Include steering daemon
#   ./deploy.sh wan1 192.168.1.100            # Deploy to IP address
#   ./deploy.sh --install-only target-host    # Only run install.sh on target
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Target paths (FHS compliant)
TARGET_CODE_DIR="/opt/wanctl"
TARGET_CONFIG_DIR="/etc/wanctl"
TARGET_SYSTEMD_DIR="/etc/systemd/system"

# Core files to deploy (always needed)
# Updated for v1.1: removed consolidated modules (lockfile, ping_utils, rate_limiter)
# Added new v1.1 modules (signal_utils, systemd_utils, wan_controller_state)
CORE_FILES=(
    "src/wanctl/__init__.py"
    "src/wanctl/autorate_continuous.py"
    "src/wanctl/calibrate.py"
    "src/wanctl/config_base.py"
    "src/wanctl/config_validation_utils.py"
    "src/wanctl/error_handling.py"
    "src/wanctl/health_check.py"
    "src/wanctl/lock_utils.py"
    "src/wanctl/logging_utils.py"
    "src/wanctl/metrics.py"
    "src/wanctl/path_utils.py"
    "src/wanctl/perf_profiler.py"
    "src/wanctl/rate_utils.py"
    "src/wanctl/retry_utils.py"
    "src/wanctl/router_client.py"
    "src/wanctl/router_command_utils.py"
    "src/wanctl/routeros_ssh.py"
    "src/wanctl/routeros_rest.py"
    "src/wanctl/rtt_measurement.py"
    "src/wanctl/signal_utils.py"
    "src/wanctl/state_manager.py"
    "src/wanctl/state_utils.py"
    "src/wanctl/steering_logger.py"
    "src/wanctl/systemd_utils.py"
    "src/wanctl/timeouts.py"
    "src/wanctl/baseline_rtt_manager.py"
    "src/wanctl/wan_controller_state.py"
)

# Backend files (router abstraction)
BACKEND_FILES=(
    "src/wanctl/backends/__init__.py"
    "src/wanctl/backends/base.py"
    "src/wanctl/backends/routeros.py"
)

# Steering module files (optional - for multi-WAN setups)
STEERING_MODULE_FILES=(
    "src/wanctl/steering/__init__.py"
    "src/wanctl/steering/daemon.py"
    "src/wanctl/steering/cake_stats.py"
    "src/wanctl/steering/congestion_assessment.py"
    "src/wanctl/steering/steering_confidence.py"
)

# Legacy steering files removed in v1.1 (consolidated into steering/ module)
STEERING_FILES=()

# Profiling and analysis scripts (optional, for data collection and analysis)
PROFILING_SCRIPTS=(
    "scripts/profiling_collector.py"
    "scripts/analyze_profiling.py"
)

# Documentation files (optional, for reference)
DOCS_FILES=(
    "docs/PROFILING.md"
)

# Systemd units (daemon mode - no timer needed)
SYSTEMD_FILES=(
    "systemd/wanctl@.service"
)

STEERING_SYSTEMD=(
    "systemd/steering.service"
    "systemd/steering.timer"
)

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

usage() {
    echo "Usage: $0 <wan_name> <target_host> [OPTIONS]"
    echo ""
    echo "Arguments:"
    echo "  wan_name       WAN identifier (e.g., wan1, wan2, fiber, cable)"
    echo "  target_host    SSH target (hostname or IP)"
    echo ""
    echo "Options:"
    echo "  --with-steering    Deploy steering daemon (for multi-WAN setups)"
    echo "  --install-only     Only run install.sh on target (no file deployment)"
    echo "  --dry-run          Show what would be deployed without doing it"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 wan1 cake-wan1                  # Deploy wan1 to host cake-wan1"
    echo "  $0 wan2 192.168.1.100 --with-steering  # Deploy with steering"
    echo "  $0 --install-only cake-wan1       # Just run installation on target"
}

check_prerequisites() {
    print_step "Checking prerequisites..."

    # Check we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/src/wanctl/autorate_continuous.py" ]]; then
        print_error "Must be run from wanctl project directory"
        exit 1
    fi

    # Check SSH connectivity
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$TARGET_HOST" 'echo ok' &>/dev/null; then
        print_error "Cannot connect to $TARGET_HOST via SSH"
        print_warning "Ensure SSH key authentication is configured"
        exit 1
    fi

    print_success "Prerequisites OK"
}

run_remote_install() {
    print_step "Running install.sh on $TARGET_HOST..."

    # Copy install.sh to target
    scp "$PROJECT_ROOT/scripts/install.sh" "$TARGET_HOST:/tmp/wanctl_install.sh"

    # Run install.sh as root
    ssh "$TARGET_HOST" "sudo bash /tmp/wanctl_install.sh"

    print_success "Remote installation complete"
}

deploy_core_files() {
    print_step "Deploying core files to $TARGET_HOST..."

    cd "$PROJECT_ROOT"

    # Deploy main Python files
    for file in "${CORE_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            ssh "$TARGET_HOST" "sudo mkdir -p $TARGET_CODE_DIR"
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_CODE_DIR/$basename && sudo chown root:root $TARGET_CODE_DIR/$basename && sudo chmod 644 $TARGET_CODE_DIR/$basename"
            echo "  -> $basename"
        else
            print_warning "File not found: $file"
        fi
    done

    # Deploy backends module
    print_step "Deploying backends module..."
    ssh "$TARGET_HOST" "sudo mkdir -p $TARGET_CODE_DIR/backends"
    for file in "${BACKEND_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_CODE_DIR/backends/$basename && sudo chown root:root $TARGET_CODE_DIR/backends/$basename && sudo chmod 644 $TARGET_CODE_DIR/backends/$basename"
            echo "  -> backends/$basename"
        else
            print_warning "File not found: $file"
        fi
    done

    print_success "Core files deployed"
}

deploy_steering_files() {
    print_step "Deploying steering module..."

    cd "$PROJECT_ROOT"

    # Create steering module directory
    ssh "$TARGET_HOST" "sudo mkdir -p $TARGET_CODE_DIR/steering"

    # Deploy new modular steering files
    for file in "${STEERING_MODULE_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_CODE_DIR/steering/$basename && sudo chown root:root $TARGET_CODE_DIR/steering/$basename"
            echo "  -> steering/$basename"
        else
            print_warning "File not found: $file"
        fi
    done

    # Also deploy legacy steering files for backward compatibility
    print_step "Deploying legacy steering files (backward compat)..."
    for file in "${STEERING_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_CODE_DIR/$basename && sudo chown root:root $TARGET_CODE_DIR/$basename"
            echo "  -> $basename"
        fi
    done

    print_success "Steering module deployed"
}

deploy_config() {
    local wan_name="$1"

    print_step "Deploying configuration for $wan_name..."

    # Check for config file
    local config_src=""
    if [[ -f "$PROJECT_ROOT/configs/${wan_name}.yaml" ]]; then
        config_src="$PROJECT_ROOT/configs/${wan_name}.yaml"
    elif [[ -f "$PROJECT_ROOT/configs/${wan_name}_config.yaml" ]]; then
        config_src="$PROJECT_ROOT/configs/${wan_name}_config.yaml"
    elif [[ -f "$PROJECT_ROOT/configs/examples/${wan_name}.yaml.example" ]]; then
        config_src="$PROJECT_ROOT/configs/examples/${wan_name}.yaml.example"
        print_warning "Using example config - customize $TARGET_CONFIG_DIR/${wan_name}.yaml after deployment"
    fi

    if [[ -n "$config_src" ]]; then
        scp "$config_src" "$TARGET_HOST:/tmp/${wan_name}.yaml"
        ssh "$TARGET_HOST" "sudo mv /tmp/${wan_name}.yaml $TARGET_CONFIG_DIR/${wan_name}.yaml && sudo chown root:wanctl $TARGET_CONFIG_DIR/${wan_name}.yaml && sudo chmod 640 $TARGET_CONFIG_DIR/${wan_name}.yaml"
        print_success "Config deployed: $TARGET_CONFIG_DIR/${wan_name}.yaml"
    else
        print_warning "No config found for $wan_name"
        print_warning "Create $TARGET_CONFIG_DIR/${wan_name}.yaml manually from examples"
    fi
}

deploy_profiling_scripts() {
    print_step "Deploying profiling scripts..."

    cd "$PROJECT_ROOT"

    # Create scripts directory if needed
    ssh "$TARGET_HOST" "sudo mkdir -p /opt/scripts"

    for file in "${PROFILING_SCRIPTS[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename /opt/scripts/$basename && sudo chown root:root /opt/scripts/$basename && sudo chmod 755 /opt/scripts/$basename"
            echo "  -> scripts/$basename"
        else
            print_warning "File not found: $file"
        fi
    done

    print_success "Profiling scripts deployed"
}

deploy_docs() {
    print_step "Deploying documentation..."

    cd "$PROJECT_ROOT"

    # Create docs directory if needed
    ssh "$TARGET_HOST" "sudo mkdir -p /opt/docs"

    for file in "${DOCS_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename /opt/docs/$basename && sudo chown root:root /opt/docs/$basename && sudo chmod 644 /opt/docs/$basename"
            echo "  -> docs/$basename"
        else
            print_warning "File not found: $file"
        fi
    done

    print_success "Documentation deployed"
}

deploy_systemd() {
    print_step "Deploying systemd units..."

    cd "$PROJECT_ROOT"

    for file in "${SYSTEMD_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_SYSTEMD_DIR/$basename && sudo chown root:root $TARGET_SYSTEMD_DIR/$basename"
            echo "  -> $basename"
        fi
    done

    ssh "$TARGET_HOST" "sudo systemctl daemon-reload"

    print_success "Systemd units deployed"
}

deploy_steering_systemd() {
    print_step "Deploying steering systemd units..."

    cd "$PROJECT_ROOT"

    for file in "${STEERING_SYSTEMD[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_SYSTEMD_DIR/$basename && sudo chown root:root $TARGET_SYSTEMD_DIR/$basename"
            echo "  -> $basename"
        fi
    done

    # Deploy steering config - REQUIRED for --with-steering
    if [[ -f "$PROJECT_ROOT/configs/steering.yaml" ]]; then
        scp "$PROJECT_ROOT/configs/steering.yaml" "$TARGET_HOST:/tmp/steering.yaml"
        ssh "$TARGET_HOST" "sudo mv /tmp/steering.yaml $TARGET_CONFIG_DIR/steering.yaml && sudo chown root:wanctl $TARGET_CONFIG_DIR/steering.yaml && sudo chmod 640 $TARGET_CONFIG_DIR/steering.yaml"
        print_success "Steering config deployed"
    else
        print_error "Production steering config not found: configs/steering.yaml"
        print_error "Create configs/steering.yaml before deploying with --with-steering"
        print_error "See configs/examples/steering.yaml.example for template"
        exit 1
    fi

    ssh "$TARGET_HOST" "sudo systemctl daemon-reload"

    print_success "Steering systemd units deployed"
}

verify_deployment() {
    local wan_name="$1"

    print_step "Verifying deployment..."

    local errors=0

    # Check core files
    if ssh "$TARGET_HOST" "test -f $TARGET_CODE_DIR/autorate_continuous.py"; then
        print_success "Core script present"
    else
        print_error "Core script missing"
        ((errors++))
    fi

    # Check config
    if ssh "$TARGET_HOST" "test -f $TARGET_CONFIG_DIR/${wan_name}.yaml"; then
        print_success "Config present: ${wan_name}.yaml"
    else
        print_warning "Config not found: ${wan_name}.yaml"
    fi

    # Check systemd
    if ssh "$TARGET_HOST" "test -f $TARGET_SYSTEMD_DIR/wanctl@.service"; then
        print_success "Systemd template present"
    else
        print_error "Systemd template missing"
        ((errors++))
    fi

    if [[ $errors -gt 0 ]]; then
        print_error "Verification failed with $errors errors"
        return 1
    fi

    print_success "Verification passed"
}

print_next_steps() {
    local wan_name="$1"

    print_header "Next Steps"

    echo -e "${BLUE}1. Configure your WAN:${NC}"
    echo "   Edit $TARGET_CONFIG_DIR/${wan_name}.yaml on $TARGET_HOST"
    echo "   - Set router host, user"
    echo "   - Set queue names to match your RouterOS config"
    echo "   - Adjust bandwidth floors and ceilings"
    echo ""

    echo -e "${BLUE}2. Set up router credentials:${NC}"
    echo ""
    echo "   Option A - REST API (recommended for faster response):"
    echo "     ssh $TARGET_HOST 'sudo nano $TARGET_CONFIG_DIR/secrets'"
    echo "     Add: ROUTER_PASSWORD=your_router_password"
    echo "     Set transport: \"rest\" in your config file"
    echo ""
    echo "   Option B - SSH key authentication:"
    echo "     Copy your router SSH key to $TARGET_CONFIG_DIR/ssh/router.key"
    echo "     sudo chown wanctl:wanctl $TARGET_CONFIG_DIR/ssh/router.key"
    echo "     sudo chmod 600 $TARGET_CONFIG_DIR/ssh/router.key"
    echo "     Set transport: \"ssh\" in your config file"
    echo ""

    echo -e "${BLUE}3. Enable the service:${NC}"
    echo "   ssh $TARGET_HOST 'sudo systemctl enable --now wanctl@${wan_name}.service'"
    echo ""

    echo -e "${BLUE}4. Monitor:${NC}"
    echo "   ssh $TARGET_HOST 'sudo journalctl -u wanctl@${wan_name} -f'"
    echo "   ssh $TARGET_HOST 'sudo tail -f /var/log/wanctl/${wan_name}.log'"
    echo "   ssh $TARGET_HOST 'sudo systemctl status wanctl@${wan_name}.service'"
    echo ""

    if [[ "$WITH_STEERING" == "true" ]]; then
        echo -e "${BLUE}5. Enable steering (optional):${NC}"
        echo "   Edit $TARGET_CONFIG_DIR/steering.yaml"
        echo "   ssh $TARGET_HOST 'sudo systemctl enable --now steering.timer'"
        echo ""
    fi

    echo -e "${BLUE}6. Collect profiling data (Phase 1):${NC}"
    echo "   After deployment, let the daemon run for 7-14 days"
    echo "   Then extract profiling statistics:"
    echo "   ssh $TARGET_HOST 'python3 /opt/scripts/profiling_collector.py /var/log/wanctl/${wan_name}.log --all'"
    echo ""
    echo "   Generate analysis report:"
    echo "   ssh $TARGET_HOST 'python3 /opt/scripts/analyze_profiling.py --log-file /var/log/wanctl/${wan_name}.log'"
    echo ""
    echo "   See /opt/docs/PROFILING.md for detailed procedure"
    echo ""
}

# Parse arguments
WAN_NAME=""
TARGET_HOST=""
WITH_STEERING=false
INSTALL_ONLY=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-steering)
            WITH_STEERING=true
            shift
            ;;
        --install-only)
            INSTALL_ONLY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$WAN_NAME" ]]; then
                WAN_NAME="$1"
            elif [[ -z "$TARGET_HOST" ]]; then
                TARGET_HOST="$1"
            else
                print_error "Unexpected argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Handle --install-only mode
if [[ "$INSTALL_ONLY" == "true" ]]; then
    TARGET_HOST="$WAN_NAME"  # First arg is actually the host
    if [[ -z "$TARGET_HOST" ]]; then
        print_error "Target host required for --install-only"
        usage
        exit 1
    fi

    print_header "wanctl Remote Installation"
    check_prerequisites
    run_remote_install
    exit 0
fi

# Validate arguments
if [[ -z "$WAN_NAME" ]] || [[ -z "$TARGET_HOST" ]]; then
    print_error "WAN name and target host are required"
    usage
    exit 1
fi

# Main deployment
print_header "wanctl Deployment"
echo ""
echo "WAN Name:    $WAN_NAME"
echo "Target:      $TARGET_HOST"
echo "Steering:    $([[ "$WITH_STEERING" == "true" ]] && echo "Yes" || echo "No")"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    print_warning "DRY RUN - no changes will be made"
    echo ""
    echo "Would deploy:"
    echo "  - Core files to $TARGET_CODE_DIR/"
    echo "  - Config to $TARGET_CONFIG_DIR/${WAN_NAME}.yaml"
    echo "  - Systemd templates to $TARGET_SYSTEMD_DIR/"
    [[ "$WITH_STEERING" == "true" ]] && echo "  - Steering daemon and config"
    exit 0
fi

check_prerequisites

# Check if install.sh has been run
if ! ssh "$TARGET_HOST" "id wanctl" &>/dev/null; then
    print_warning "wanctl user not found on target - running install.sh first"
    run_remote_install
fi

deploy_core_files
deploy_config "$WAN_NAME"
deploy_profiling_scripts
deploy_docs
deploy_systemd

if [[ "$WITH_STEERING" == "true" ]]; then
    deploy_steering_files
    deploy_steering_systemd
fi

verify_deployment "$WAN_NAME"

print_next_steps "$WAN_NAME"

print_success "Deployment complete!"

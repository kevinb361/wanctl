#!/bin/bash
#
# wanctl Docker Entrypoint
#
# Modes:
#   continuous  - Run continuous RTT monitoring (default)
#   calibrate   - Run calibration wizard
#   steering    - Run steering daemon
#   oneshot     - Run single measurement cycle
#   shell       - Start interactive shell
#
set -e

# Configuration
CONFIG="${WANCTL_CONFIG:-/etc/wanctl/wan.yaml}"
MODE="${1:-continuous}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[wanctl]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[wanctl]${NC} $1"
}

log_error() {
    echo -e "${RED}[wanctl]${NC} $1"
}

# Validate configuration
validate_config() {
    if [[ ! -f "$CONFIG" ]]; then
        log_error "Configuration file not found: $CONFIG"
        log_error "Mount your config: -v /path/to/wan.yaml:/etc/wanctl/wan.yaml"
        exit 1
    fi

    # Basic YAML validation
    if ! python3 -c "import yaml; yaml.safe_load(open('$CONFIG'))" 2>/dev/null; then
        log_error "Invalid YAML in configuration file: $CONFIG"
        exit 1
    fi

    log_info "Configuration validated: $CONFIG"
}

# Check SSH key if specified in config
check_ssh_key() {
    local ssh_key
    ssh_key=$(python3 -c "
import yaml
config = yaml.safe_load(open('$CONFIG'))
router = config.get('router', {})
print(router.get('ssh_key', ''))
" 2>/dev/null || echo "")

    if [[ -n "$ssh_key" ]] && [[ ! -f "$ssh_key" ]]; then
        log_warn "SSH key not found: $ssh_key"
        log_warn "Mount your SSH key: -v /path/to/key:/etc/wanctl/ssh/router.key"
    elif [[ -n "$ssh_key" ]]; then
        # Check permissions
        local perms
        perms=$(stat -c %a "$ssh_key" 2>/dev/null || echo "000")
        if [[ "$perms" != "600" ]] && [[ "$perms" != "400" ]]; then
            log_warn "SSH key permissions should be 600 or 400 (currently $perms)"
        fi
    fi
}

# Run continuous monitoring mode
run_continuous() {
    log_info "Starting continuous RTT monitoring..."
    log_info "Config: $CONFIG"

    exec python3 -m autorate_continuous --config "$CONFIG" "${@:2}"
}

# Run calibration mode
run_calibrate() {
    log_info "Starting calibration mode..."

    # Get WAN name from config
    local wan_name
    wan_name=$(python3 -c "
import yaml
config = yaml.safe_load(open('$CONFIG'))
print(config.get('wan_name', 'wan1'))
" 2>/dev/null || echo "wan1")

    # Get router from config
    local router_host
    router_host=$(python3 -c "
import yaml
config = yaml.safe_load(open('$CONFIG'))
router = config.get('router', {})
print(router.get('host', ''))
" 2>/dev/null || echo "")

    if [[ -z "$router_host" ]]; then
        log_error "Router host not specified in config"
        exit 1
    fi

    exec python3 -m calibrate \
        --wan-name "$wan_name" \
        --router "$router_host" \
        "${@:2}"
}

# Run steering daemon
run_steering() {
    log_info "Starting steering daemon..."

    # Steering uses its own config format
    local steering_config="${WANCTL_STEERING_CONFIG:-/etc/wanctl/steering.yaml}"

    if [[ ! -f "$steering_config" ]]; then
        log_error "Steering config not found: $steering_config"
        exit 1
    fi

    exec python3 -m steering.daemon --config "$steering_config" "${@:2}"
}

# Run single measurement cycle
run_oneshot() {
    log_info "Running single measurement cycle..."

    exec python3 -m autorate_continuous --config "$CONFIG" --once "${@:2}"
}

# Show help
show_help() {
    cat << EOF
wanctl Docker Container

Usage: docker run [options] wanctl [MODE] [ARGS]

Modes:
  continuous    Run continuous RTT monitoring (default)
  calibrate     Run calibration wizard
  steering      Run steering daemon
  oneshot       Run single measurement cycle
  shell         Start interactive shell
  help          Show this help message

Environment Variables:
  WANCTL_CONFIG           Path to main config file (default: /etc/wanctl/wan.yaml)
  WANCTL_STEERING_CONFIG  Path to steering config (default: /etc/wanctl/steering.yaml)
  WANCTL_MODE             Default mode if not specified

Volume Mounts:
  /etc/wanctl/wan.yaml        Main configuration file
  /etc/wanctl/steering.yaml   Steering configuration (optional)
  /etc/wanctl/ssh/            SSH keys directory
  /var/lib/wanctl/            State files (persistent)
  /var/log/wanctl/            Log files (optional)

Examples:
  # Run continuous monitoring
  docker run -v ./wan1.yaml:/etc/wanctl/wan.yaml \\
             -v ./ssh/router.key:/etc/wanctl/ssh/router.key \\
             wanctl

  # Run calibration
  docker run -it -v ./wan1.yaml:/etc/wanctl/wan.yaml \\
             wanctl calibrate

  # Run with persistent state
  docker run -v ./wan1.yaml:/etc/wanctl/wan.yaml \\
             -v ./state:/var/lib/wanctl \\
             wanctl

EOF
}

# Main
case "$MODE" in
    continuous)
        validate_config
        check_ssh_key
        run_continuous "$@"
        ;;
    calibrate)
        validate_config
        check_ssh_key
        run_calibrate "$@"
        ;;
    steering)
        check_ssh_key
        run_steering "$@"
        ;;
    oneshot)
        validate_config
        check_ssh_key
        run_oneshot "$@"
        ;;
    shell|bash|sh)
        exec /bin/bash
        ;;
    help|--help|-h)
        show_help
        exit 0
        ;;
    *)
        log_error "Unknown mode: $MODE"
        show_help
        exit 1
        ;;
esac

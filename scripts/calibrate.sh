#!/bin/bash
#
# wanctl Calibration Wizard
#
# Interactive script to discover optimal CAKE settings for your connection.
# Uses the Flent/LibreQoS methodology: find maximum throughput with acceptable latency.
#
# Usage:
#   ./calibrate.sh                    # Interactive mode
#   ./calibrate.sh --wan-name wan1    # With pre-set WAN name
#   ./calibrate.sh --help             # Show all options
#
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
WAN_NAME=""
ROUTER_HOST=""
ROUTER_USER="admin"
SSH_KEY=""
NETPERF_HOST="netperf.bufferbloat.net"
PING_HOST="1.1.1.1"
TARGET_BLOAT="10"
OUTPUT_DIR="/etc/wanctl"
SKIP_BINARY_SEARCH=false
INTERACTIVE=true

# Helper functions
print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}========================================${NC}"
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${BOLD}${BLUE}========================================${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
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

prompt() {
    local prompt_text="$1"
    local default_value="$2"
    local result

    if [[ -n "$default_value" ]]; then
        echo -en "${CYAN}$prompt_text${NC} [$default_value]: "
        read -r result
        echo "${result:-$default_value}"
    else
        echo -en "${CYAN}$prompt_text${NC}: "
        read -r result
        echo "$result"
    fi
}

confirm() {
    local prompt_text="$1"
    local default="$2"

    if [[ "$default" == "y" ]]; then
        echo -en "${CYAN}$prompt_text${NC} [Y/n]: "
    else
        echo -en "${CYAN}$prompt_text${NC} [y/N]: "
    fi

    read -r response
    response="${response:-$default}"

    [[ "$response" =~ ^[Yy]$ ]]
}

usage() {
    cat << EOF
wanctl Calibration Wizard

Discovers optimal CAKE bandwidth settings for your connection using
the Flent/LibreQoS methodology: find maximum throughput with acceptable latency.

Usage:
    $0 [OPTIONS]

Options:
    --wan-name NAME         WAN identifier (e.g., wan1, cable, fiber)
    --router HOST           Router IP or hostname
    --user USER             SSH username for router (default: admin)
    --ssh-key PATH          Path to SSH private key
    --netperf-host HOST     Netperf server (default: netperf.bufferbloat.net)
    --ping-host HOST        RTT measurement host (default: 1.1.1.1)
    --target-bloat MS       Target bloat in ms (default: 10)
    --output-dir DIR        Config output directory (default: /etc/wanctl)
    --skip-binary-search    Skip binary search, measure raw only
    --non-interactive       Skip interactive prompts
    --help                  Show this help message

Examples:
    $0                                          # Interactive wizard
    $0 --wan-name wan1 --router 192.168.1.1    # With preset values
    $0 --wan-name fiber --skip-binary-search   # Quick calibration

EOF
}

check_prerequisites() {
    print_step "Checking prerequisites..."

    local missing=0

    # Check Python
    if ! command -v python3 &>/dev/null; then
        print_error "Python 3 not found"
        ((missing++))
    fi

    # Check netperf
    if ! command -v netperf &>/dev/null; then
        print_warning "netperf not installed - throughput tests will be skipped"
        print_info "Install with: sudo apt install netperf"
    fi

    # Check ping
    if ! command -v ping &>/dev/null; then
        print_error "ping not found"
        ((missing++))
    fi

    # Check SSH
    if ! command -v ssh &>/dev/null; then
        print_error "ssh not found"
        ((missing++))
    fi

    # Check for calibrate.py
    if [[ ! -f "$PROJECT_ROOT/src/wanctl/calibrate.py" ]]; then
        print_error "calibrate.py not found at $PROJECT_ROOT/src/wanctl/"
        ((missing++))
    fi

    if [[ $missing -gt 0 ]]; then
        print_error "Missing prerequisites. Please install required tools."
        return 1
    fi

    print_success "Prerequisites OK"
    return 0
}

interactive_wizard() {
    print_header "wanctl Calibration Wizard"

    echo "This wizard will help you discover optimal CAKE settings for your connection."
    echo "It will:"
    echo "  1. Test connectivity to your router"
    echo "  2. Measure your baseline RTT (idle latency)"
    echo "  3. Measure raw throughput (may cause latency spikes)"
    echo "  4. Binary search for optimal shaped rates"
    echo "  5. Generate a configuration file"
    echo ""
    echo -e "${YELLOW}Note: The binary search will temporarily modify your CAKE queue limits.${NC}"
    echo ""

    if ! confirm "Ready to begin?" "y"; then
        echo "Calibration cancelled."
        exit 0
    fi

    # WAN Name
    print_header "WAN Configuration"
    if [[ -z "$WAN_NAME" ]]; then
        WAN_NAME=$(prompt "Enter a name for this WAN (e.g., wan1, cable, fiber)" "wan1")
    fi
    print_info "WAN name: $WAN_NAME"

    # Router connection
    if [[ -z "$ROUTER_HOST" ]]; then
        ROUTER_HOST=$(prompt "Enter router IP or hostname")
    fi
    print_info "Router: $ROUTER_HOST"

    ROUTER_USER=$(prompt "Enter SSH username for router" "$ROUTER_USER")
    print_info "SSH user: $ROUTER_USER"

    if [[ -z "$SSH_KEY" ]]; then
        echo ""
        print_info "SSH key authentication is recommended."
        if confirm "Do you want to specify an SSH key?" "n"; then
            SSH_KEY=$(prompt "Enter path to SSH private key" "$HOME/.ssh/id_rsa")
        fi
    fi

    # Test connectivity
    print_header "Testing Connectivity"
    print_step "Testing SSH connection to $ROUTER_USER@$ROUTER_HOST..."

    local ssh_cmd="ssh -o ConnectTimeout=5 -o BatchMode=yes"
    if [[ -n "$SSH_KEY" ]]; then
        ssh_cmd="$ssh_cmd -i $SSH_KEY"
    fi

    if ! $ssh_cmd "$ROUTER_USER@$ROUTER_HOST" 'echo ok' &>/dev/null; then
        print_error "SSH connection failed!"
        print_info "Please check:"
        print_info "  - Router IP/hostname is correct"
        print_info "  - SSH is enabled on router"
        print_info "  - SSH key is configured (if using key auth)"
        exit 1
    fi
    print_success "SSH connection successful"

    # Netperf server
    print_header "Test Server Configuration"
    print_info "A netperf server is needed for throughput measurements."
    print_info "Public servers: netperf.bufferbloat.net, flent-fremont.bufferbloat.net"
    NETPERF_HOST=$(prompt "Enter netperf server hostname" "$NETPERF_HOST")

    # Binary search option
    print_header "Calibration Options"
    echo "Binary search will find the optimal rate that maintains low latency."
    echo "This takes longer but gives more accurate results."
    echo ""
    if ! confirm "Perform binary search for optimal rates?" "y"; then
        SKIP_BINARY_SEARCH=true
        print_info "Binary search disabled - will measure raw throughput only"
    fi

    # Target bloat
    if [[ "$SKIP_BINARY_SEARCH" == "false" ]]; then
        echo ""
        print_info "Target bloat is the maximum acceptable latency increase under load."
        print_info "Recommended: 10ms for gaming/VoIP, 15-20ms for general use"
        TARGET_BLOAT=$(prompt "Enter target bloat (ms)" "$TARGET_BLOAT")
    fi

    # Output directory
    print_header "Output Configuration"
    OUTPUT_DIR=$(prompt "Enter config output directory" "$OUTPUT_DIR")

    # Summary
    print_header "Configuration Summary"
    echo -e "  WAN name:        ${CYAN}$WAN_NAME${NC}"
    echo -e "  Router:          ${CYAN}$ROUTER_HOST${NC}"
    echo -e "  SSH user:        ${CYAN}$ROUTER_USER${NC}"
    echo -e "  SSH key:         ${CYAN}${SSH_KEY:-none}${NC}"
    echo -e "  Netperf server:  ${CYAN}$NETPERF_HOST${NC}"
    echo -e "  Target bloat:    ${CYAN}${TARGET_BLOAT}ms${NC}"
    echo -e "  Binary search:   ${CYAN}$([[ "$SKIP_BINARY_SEARCH" == "true" ]] && echo "disabled" || echo "enabled")${NC}"
    echo -e "  Output dir:      ${CYAN}$OUTPUT_DIR${NC}"
    echo ""

    if ! confirm "Proceed with calibration?" "y"; then
        echo "Calibration cancelled."
        exit 0
    fi
}

run_calibration() {
    print_header "Running Calibration"

    local python_cmd="python3 -m wanctl.calibrate"
    local args=(
        "--wan-name" "$WAN_NAME"
        "--router" "$ROUTER_HOST"
        "--user" "$ROUTER_USER"
        "--netperf-host" "$NETPERF_HOST"
        "--ping-host" "$PING_HOST"
        "--target-bloat" "$TARGET_BLOAT"
        "--output-dir" "$OUTPUT_DIR"
    )

    if [[ -n "$SSH_KEY" ]]; then
        args+=("--ssh-key" "$SSH_KEY")
    fi

    if [[ "$SKIP_BINARY_SEARCH" == "true" ]]; then
        args+=("--skip-binary-search")
    fi

    # Run from project root so Python can find the module
    cd "$PROJECT_ROOT"

    # Set PYTHONPATH to include src directory
    export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

    print_info "Running: $python_cmd ${args[*]}"
    echo ""

    # Execute calibration
    python3 -m wanctl.calibrate "${args[@]}"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan-name)
            WAN_NAME="$2"
            shift 2
            ;;
        --router)
            ROUTER_HOST="$2"
            shift 2
            ;;
        --user)
            ROUTER_USER="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="$2"
            shift 2
            ;;
        --netperf-host)
            NETPERF_HOST="$2"
            shift 2
            ;;
        --ping-host)
            PING_HOST="$2"
            shift 2
            ;;
        --target-bloat)
            TARGET_BLOAT="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --skip-binary-search)
            SKIP_BINARY_SEARCH=true
            shift
            ;;
        --non-interactive)
            INTERACTIVE=false
            shift
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

# Main execution
print_header "wanctl Calibration Tool"

if ! check_prerequisites; then
    exit 1
fi

# Run interactive wizard if needed
if [[ "$INTERACTIVE" == "true" ]]; then
    if [[ -z "$WAN_NAME" ]] || [[ -z "$ROUTER_HOST" ]]; then
        interactive_wizard
    fi
fi

# Validate required arguments
if [[ -z "$WAN_NAME" ]]; then
    print_error "WAN name is required (--wan-name)"
    exit 1
fi

if [[ -z "$ROUTER_HOST" ]]; then
    print_error "Router host is required (--router)"
    exit 1
fi

# Run calibration
run_calibration

print_success "Calibration complete!"

#!/bin/bash
#
# wanctl Pre-Startup Validation Script
#
# Validates deployment readiness before daemon start.
# Checks config files, router reachability, and state paths.
#
# Usage:
#   validate-deployment.sh [wan-config.yaml]              # Basic validation
#   validate-deployment.sh [wan-config.yaml] --steering   # Include steering checks
#   validate-deployment.sh --help                         # Show help
#
# Exit codes:
#   0 = All checks passed
#   1 = Blocking errors (must fix before starting daemon)
#   2 = Warnings only (daemon may work but review recommended)
#
set -e

# Version
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default paths (FHS compliant)
CONFIG_DIR="/etc/wanctl"
STATE_DIR="/var/lib/wanctl"

# Counters
ERRORS=0
WARNINGS=0

# Output functions
print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ERRORS=$((ERRORS + 1))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Extract a value from YAML using Python (handles complex paths)
# Usage: extract_yaml_value "path.to.key" "config_file"
extract_yaml_value() {
    local key_path="$1"
    local config_file="$2"

    python3 -c "
import yaml
import sys

with open('$config_file', 'r') as f:
    data = yaml.safe_load(f)

keys = '$key_path'.split('.')
value = data
try:
    for key in keys:
        value = value[key]
    print(value if value is not None else '')
except (KeyError, TypeError):
    print('')
" 2>/dev/null
}

# Validate config file exists and is valid YAML
validate_config() {
    local config_file="$1"

    print_info "Validating config: $config_file"

    # Check file exists
    if [[ ! -f "$config_file" ]]; then
        print_fail "Config file not found: $config_file"
        return 1
    fi

    # Check readable
    if [[ ! -r "$config_file" ]]; then
        print_fail "Config file not readable: $config_file"
        return 1
    fi

    # Validate YAML syntax
    if ! python3 -c "import yaml; yaml.safe_load(open('$config_file'))" 2>/dev/null; then
        print_fail "Invalid YAML syntax in: $config_file"
        return 1
    fi

    print_pass "Config valid: $config_file"
    return 0
}

# Test router reachability (adapted from install.sh)
# Usage: test_router_reachable "transport" "router_ip" ["password"]
test_router_reachable() {
    local transport="$1"
    local router_ip="$2"
    local password="$3"

    print_info "Testing router connection: $router_ip ($transport)"

    if [[ "$transport" == "rest" ]]; then
        # Test REST API
        if [[ -z "$password" ]]; then
            print_warn "No password provided for REST API test (from secrets file)"
            return 2
        fi

        local http_code
        http_code=$(curl -s -k -o /dev/null -w "%{http_code}" \
            -u "admin:$password" \
            --connect-timeout 5 \
            --max-time 10 \
            "https://${router_ip}/rest/system/resource" 2>/dev/null || echo "000")

        case "$http_code" in
            200)
                print_pass "Router reachable: $router_ip (REST)"
                return 0
                ;;
            401)
                print_fail "Authentication failed (HTTP 401) - check password in secrets"
                return 1
                ;;
            000)
                print_fail "Router unreachable: $router_ip - check IP and network"
                return 1
                ;;
            *)
                print_fail "Unexpected response from router (HTTP $http_code)"
                return 1
                ;;
        esac

    elif [[ "$transport" == "ssh" ]]; then
        # Test SSH connection
        local ssh_key="$CONFIG_DIR/ssh/router.key"

        if [[ ! -f "$ssh_key" ]]; then
            print_fail "SSH key not found: $ssh_key"
            return 1
        fi

        # Quick SSH test with timeout
        if ssh -i "$ssh_key" \
            -o ConnectTimeout=5 \
            -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes \
            "admin@${router_ip}" \
            '/system resource print' &>/dev/null; then
            print_pass "Router reachable: $router_ip (SSH)"
            return 0
        else
            print_fail "SSH connection failed to $router_ip"
            return 1
        fi
    else
        print_warn "Unknown transport: $transport (skipping router test)"
        return 2
    fi
}

# Check state file path is writable
check_state_path() {
    local state_file="$1"

    print_info "Checking state path: $state_file"

    if [[ -z "$state_file" ]]; then
        print_warn "No state_file configured (using default)"
        return 0
    fi

    # Get parent directory
    local state_dir
    state_dir=$(dirname "$state_file")

    # Check directory exists
    if [[ ! -d "$state_dir" ]]; then
        print_fail "State directory does not exist: $state_dir"
        return 1
    fi

    # Check directory is writable (by current user or wanctl)
    if [[ ! -w "$state_dir" ]]; then
        # Check if wanctl user can write (running as root checking for wanctl)
        if id wanctl &>/dev/null && [[ -O "$state_dir" || -G "$state_dir" ]]; then
            print_pass "State directory writable by wanctl: $state_dir"
            return 0
        fi
        print_warn "State directory may not be writable: $state_dir"
        return 2
    fi

    # If state file exists, check it's valid JSON
    if [[ -f "$state_file" ]]; then
        if python3 -c "import json; json.load(open('$state_file'))" 2>/dev/null; then
            print_pass "State file exists and valid: $state_file"
        else
            print_warn "State file exists but may be corrupt: $state_file"
            return 2
        fi
    else
        print_warn "State file not found (will be created on first run): $state_file"
        return 2
    fi

    return 0
}

# Check steering-specific dependencies
check_steering_deps() {
    local steering_config="$1"

    print_info "Checking steering dependencies"

    # Check primary WAN state file exists
    local primary_state
    primary_state=$(extract_yaml_value "cake_state_sources.primary" "$steering_config")

    if [[ -n "$primary_state" ]]; then
        if [[ -f "$primary_state" ]]; then
            print_pass "Primary WAN state file exists: $primary_state"
        else
            print_warn "Primary WAN state file not found: $primary_state"
            print_warn "  Ensure primary WAN autorate daemon is running"
        fi
    else
        print_warn "No cake_state_sources.primary configured"
    fi

    # Check mangle rule comment is configured
    local mangle_comment
    mangle_comment=$(extract_yaml_value "mangle_rule.comment" "$steering_config")

    if [[ -n "$mangle_comment" ]]; then
        print_pass "Mangle rule comment configured: $mangle_comment"
    else
        print_warn "No mangle_rule.comment configured (may use default)"
    fi

    return 0
}

# Load password from secrets file
load_password() {
    local secrets_file="$CONFIG_DIR/secrets"

    if [[ -f "$secrets_file" && -r "$secrets_file" ]]; then
        local password
        password=$(grep "^ROUTER_PASSWORD=" "$secrets_file" 2>/dev/null | cut -d'=' -f2-)
        echo "$password"
    fi
}

# Display usage
usage() {
    echo "wanctl Pre-Startup Validation Script v$VERSION"
    echo ""
    echo "Usage: $0 [config-file] [OPTIONS]"
    echo ""
    echo "Arguments:"
    echo "  config-file    Path to WAN config YAML (e.g., /etc/wanctl/spectrum.yaml)"
    echo ""
    echo "Options:"
    echo "  --steering     Also validate steering config (/etc/wanctl/steering.yaml)"
    echo "  --config-dir   Config directory (default: /etc/wanctl)"
    echo "  --help, -h     Show this help message"
    echo ""
    echo "Exit codes:"
    echo "  0 = All checks passed"
    echo "  1 = Blocking errors found (must fix)"
    echo "  2 = Warnings only (review recommended)"
    echo ""
    echo "Examples:"
    echo "  $0 /etc/wanctl/spectrum.yaml"
    echo "  $0 /etc/wanctl/spectrum.yaml --steering"
    echo "  $0 configs/spectrum.yaml --config-dir configs"
}

# Parse arguments
CONFIG_FILE=""
CHECK_STEERING=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --steering)
            CHECK_STEERING=true
            shift
            ;;
        --config-dir)
            CONFIG_DIR="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$CONFIG_FILE" ]]; then
                CONFIG_FILE="$1"
            else
                echo "Unexpected argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate we have a config file
if [[ -z "$CONFIG_FILE" ]]; then
    echo "Error: Config file required"
    echo ""
    usage
    exit 1
fi

# Main validation
echo ""
echo "========================================="
echo " wanctl Deployment Validation"
echo "========================================="
echo ""

# Step 1: Validate config file
if ! validate_config "$CONFIG_FILE"; then
    echo ""
    echo -e "${RED}CRITICAL:${NC} Config validation failed. Fix errors above."
    exit 1
fi

# Step 2: Extract router settings from config
ROUTER_HOST=$(extract_yaml_value "router.host" "$CONFIG_FILE")
ROUTER_TRANSPORT=$(extract_yaml_value "router.transport" "$CONFIG_FILE")
STATE_FILE=$(extract_yaml_value "state_file" "$CONFIG_FILE")

# Get password from secrets
ROUTER_PASSWORD=$(load_password)

echo ""

# Step 3: Test router reachability
if [[ -n "$ROUTER_HOST" ]]; then
    test_router_reachable "$ROUTER_TRANSPORT" "$ROUTER_HOST" "$ROUTER_PASSWORD" || true
else
    print_fail "No router.host configured in $CONFIG_FILE"
fi

echo ""

# Step 4: Check state file path
check_state_path "$STATE_FILE" || true

# Step 5: Steering validation (if requested)
if [[ "$CHECK_STEERING" == "true" ]]; then
    echo ""
    STEERING_CONFIG="$CONFIG_DIR/steering.yaml"

    if validate_config "$STEERING_CONFIG"; then
        echo ""

        # Extract steering router settings (may be different from WAN config)
        STEERING_ROUTER_HOST=$(extract_yaml_value "router.host" "$STEERING_CONFIG")
        STEERING_ROUTER_TRANSPORT=$(extract_yaml_value "router.transport" "$STEERING_CONFIG")

        if [[ -n "$STEERING_ROUTER_HOST" ]]; then
            test_router_reachable "$STEERING_ROUTER_TRANSPORT" "$STEERING_ROUTER_HOST" "$ROUTER_PASSWORD" || true
        fi

        echo ""
        check_steering_deps "$STEERING_CONFIG"
    fi
fi

# Summary
echo ""
echo "========================================="
echo " Validation Summary"
echo "========================================="
echo ""

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}ERRORS: $ERRORS${NC} (must fix before starting daemon)"
    echo -e "${YELLOW}WARNINGS: $WARNINGS${NC}"
    echo ""
    echo "Fix the errors above before starting wanctl."
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "${GREEN}ERRORS: 0${NC}"
    echo -e "${YELLOW}WARNINGS: $WARNINGS${NC} (review recommended)"
    echo ""
    echo "All critical checks passed. Review warnings if daemon fails to start."
    exit 2
else
    echo -e "${GREEN}All checks passed!${NC}"
    echo ""
    echo "Deployment is ready. Start daemon with:"
    echo "  sudo systemctl start wanctl@<wan_name>.service"
    exit 0
fi

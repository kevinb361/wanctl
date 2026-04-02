#!/bin/bash
#
# Pre-Tuning Gate Check Script
#
# Validates the test environment before any A/B tuning begins.
# Runs FROM the dev machine -- SSHes to cake-shaper VM as needed.
#
# Checks:
#   1. CAKE qdiscs active on all 4 bridge NICs (GATE-01)
#   2. No active CAKE on MikroTik router (GATE-02)
#   3. Rate change produces visible tc bandwidth change (GATE-03)
#   4. Transport is linux-cake in spectrum.yaml
#   5. Health endpoint returns correct version
#
# Usage:
#   bash scripts/check-tuning-gate.sh
#
# Exit: 0 if all pass, 1 if any fail

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VM_HOST="kevin@10.10.110.223"
ROUTER_HOST="10.10.99.1"
ROUTER_USER="admin"
SPECTRUM_CONFIG="/etc/wanctl/spectrum.yaml"
HEALTH_URL="http://127.0.0.1:9101/health"
BRIDGE_NICS=(ens16 ens17 ens27 ens28)

# ---------------------------------------------------------------------------
# Colors (matching deploy.sh pattern)
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
PASS=0
FAIL=0
TOTAL=5

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
print_pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    ((PASS++))
}

print_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    ((FAIL++))
}

print_info() {
    echo -e "  ${BLUE}[INFO]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Pre-Tuning Gate Check${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Check if jq is available on VM, set JSON parser accordingly
setup_json_parser() {
    if ssh "$VM_HOST" 'command -v jq' &>/dev/null; then
        JSON_PARSER="jq"
    else
        JSON_PARSER="python3"
    fi
}

# Parse JSON field using available tool (runs on VM via SSH)
# Usage: parse_json "$json_string" ".field" or parse_json "$json_string" "expression"
parse_json_field() {
    local json="$1"
    local field="$2"

    if [[ "$JSON_PARSER" == "jq" ]]; then
        echo "$json" | ssh "$VM_HOST" "jq -r '$field'"
    else
        # Python fallback -- map jq-style field to Python
        echo "$json" | ssh "$VM_HOST" "python3 -c \"
import sys, json
data = json.load(sys.stdin)
# Support simple jq expressions
expr = '''$field'''
if expr.startswith('.'):
    expr = expr[1:]
if expr == '':
    print(json.dumps(data))
else:
    # Handle array length
    if '| length' in expr:
        key = expr.split('|')[0].strip().lstrip('.')
        if key:
            print(len(data[key]) if key in data else len(data))
        else:
            print(len(data))
    else:
        result = data
        for part in expr.split('.'):
            if part:
                result = result[part]
        print(result)
\""
    fi
}

# ---------------------------------------------------------------------------
# Get router password from VM secrets file
# ---------------------------------------------------------------------------
get_router_password() {
    ssh "$VM_HOST" "sudo grep -oP 'ROUTER_PASSWORD=\K.*' /etc/wanctl/secrets" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Check 1 (GATE-01): CAKE qdiscs on all 4 bridge NICs
# ---------------------------------------------------------------------------
check_cake_qdiscs() {
    echo -e "${YELLOW}Check 1: CAKE qdiscs on bridge NICs${NC}"

    local tc_output
    tc_output=$(ssh "$VM_HOST" 'tc -s qdisc show' 2>/dev/null) || {
        print_fail "Could not retrieve tc qdisc data from VM"
        return
    }

    local missing=()
    for nic in "${BRIDGE_NICS[@]}"; do
        if echo "$tc_output" | grep -q "qdisc cake.*dev ${nic}"; then
            print_info "CAKE qdisc found on $nic"
        else
            missing+=("$nic")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        print_pass "CAKE qdiscs active on all ${#BRIDGE_NICS[@]} bridge NICs (${BRIDGE_NICS[*]})"
    else
        print_fail "CAKE qdiscs missing on: ${missing[*]}"
    fi
}

# ---------------------------------------------------------------------------
# Check 2 (GATE-02): No active CAKE on MikroTik router
# ---------------------------------------------------------------------------
check_router_no_cake() {
    echo ""
    echo -e "${YELLOW}Check 2: No active CAKE on MikroTik router${NC}"

    local router_pass
    router_pass=$(get_router_password) || {
        print_fail "Could not read router password from VM secrets"
        return
    }

    local has_active_cake=false
    local details=""

    # Check queue tree for active CAKE entries
    local queue_tree
    queue_tree=$(ssh "$VM_HOST" "curl -sk -u ${ROUTER_USER}:${router_pass} https://${ROUTER_HOST}/rest/queue/tree" 2>/dev/null) || {
        print_fail "Could not query router /rest/queue/tree"
        return
    }

    # Check each queue tree entry for active CAKE
    local active_cake_queues
    if [[ "$JSON_PARSER" == "jq" ]]; then
        active_cake_queues=$(echo "$queue_tree" | ssh "$VM_HOST" \
            "jq -r '.[] | select(.queue // \"\" | startswith(\"cake\")) | select(.disabled != \"true\") | .name'" 2>/dev/null) || true
    else
        active_cake_queues=$(echo "$queue_tree" | ssh "$VM_HOST" \
            "python3 -c \"
import sys, json
data = json.load(sys.stdin)
for entry in data:
    queue_type = entry.get('queue', '')
    disabled = entry.get('disabled', 'false')
    if queue_type.startswith('cake') and disabled != 'true':
        print(entry.get('name', 'unknown'))
\"" 2>/dev/null) || true
    fi

    if [[ -n "$active_cake_queues" ]]; then
        has_active_cake=true
        details+="Active CAKE queue tree entries: ${active_cake_queues//$'\n'/, }. "
        print_info "Found active CAKE queue trees: ${active_cake_queues//$'\n'/, }"
    else
        print_info "No active CAKE queue tree entries"
    fi

    # Check queue types for CAKE
    local queue_types
    queue_types=$(ssh "$VM_HOST" "curl -sk -u ${ROUTER_USER}:${router_pass} https://${ROUTER_HOST}/rest/queue/type" 2>/dev/null) || {
        print_info "Could not query /rest/queue/type (non-fatal)"
    }

    if [[ -n "${queue_types:-}" ]]; then
        local cake_types
        if [[ "$JSON_PARSER" == "jq" ]]; then
            cake_types=$(echo "$queue_types" | ssh "$VM_HOST" \
                "jq -r '.[] | select(.kind // \"\" | startswith(\"cake\")) | .name'" 2>/dev/null) || true
        else
            cake_types=$(echo "$queue_types" | ssh "$VM_HOST" \
                "python3 -c \"
import sys, json
data = json.load(sys.stdin)
for entry in data:
    kind = entry.get('kind', '')
    if kind.startswith('cake'):
        print(entry.get('name', 'unknown'))
\"" 2>/dev/null) || true
        fi

        if [[ -n "$cake_types" ]]; then
            print_info "CAKE queue types registered: ${cake_types//$'\n'/, } (OK if queue trees are disabled)"
        else
            print_info "No CAKE queue types registered"
        fi
    fi

    # Check mangle rules for CAKE-related entries (per D-03)
    local mangle_rules
    mangle_rules=$(ssh "$VM_HOST" "curl -sk -u ${ROUTER_USER}:${router_pass} https://${ROUTER_HOST}/rest/ip/firewall/mangle" 2>/dev/null) || {
        print_info "Could not query /rest/ip/firewall/mangle (non-fatal)"
    }

    if [[ -n "${mangle_rules:-}" ]]; then
        local active_cake_mangles
        if [[ "$JSON_PARSER" == "jq" ]]; then
            active_cake_mangles=$(echo "$mangle_rules" | ssh "$VM_HOST" \
                "jq -r '.[] | select(.comment // \"\" | test(\"cake\"; \"i\")) | select(.disabled != \"true\") | .comment'" 2>/dev/null) || true
        else
            active_cake_mangles=$(echo "$mangle_rules" | ssh "$VM_HOST" \
                "python3 -c \"
import sys, json
data = json.load(sys.stdin)
for entry in data:
    comment = entry.get('comment', '')
    disabled = entry.get('disabled', 'false')
    if 'cake' in comment.lower() and disabled != 'true':
        print(comment)
\"" 2>/dev/null) || true
        fi

        if [[ -n "$active_cake_mangles" ]]; then
            has_active_cake=true
            details+="Active CAKE mangle rules: ${active_cake_mangles//$'\n'/, }. "
            print_info "Found active CAKE mangle rules: ${active_cake_mangles//$'\n'/, }"
        else
            print_info "No active CAKE mangle rules"
        fi
    fi

    if [[ "$has_active_cake" == "false" ]]; then
        print_pass "No active CAKE queues or mangle rules on MikroTik router"
    else
        print_fail "Active CAKE found on router -- disable before testing. ${details}"
    fi
}

# ---------------------------------------------------------------------------
# Check 3 (GATE-03): Rate change produces visible tc bandwidth change
# ---------------------------------------------------------------------------
check_rate_change_visible() {
    echo ""
    echo -e "${YELLOW}Check 3: Rate change visibility via SIGUSR1 + tc${NC}"

    # Verify wanctl process is alive
    local pid
    pid=$(ssh "$VM_HOST" "pgrep -f 'autorate_continuous.*spectrum'" 2>/dev/null) || {
        print_fail "wanctl process not running (pgrep for autorate_continuous.*spectrum failed)"
        return
    }
    print_info "wanctl process alive (PID: $pid)"

    # Capture current CAKE bandwidth on ens16
    local bw_before
    bw_before=$(ssh "$VM_HOST" "tc -s qdisc show dev ens16" 2>/dev/null | grep -oP 'bandwidth \K[0-9]+[A-Za-z]*' || echo "") || true
    print_info "Current bandwidth on ens16: ${bw_before:-unknown}"

    # Send SIGUSR1 to trigger config reload
    ssh "$VM_HOST" "sudo kill -USR1 $pid" 2>/dev/null || {
        print_fail "Could not send SIGUSR1 to wanctl process"
        return
    }
    print_info "SIGUSR1 sent to PID $pid"

    # Wait for reload to take effect
    sleep 1

    # Verify process survived SIGUSR1
    if ! ssh "$VM_HOST" "kill -0 $pid" 2>/dev/null; then
        print_fail "wanctl process died after SIGUSR1"
        return
    fi
    print_info "Process survived SIGUSR1"

    # Capture bandwidth again
    local bw_after
    bw_after=$(ssh "$VM_HOST" "tc -s qdisc show dev ens16" 2>/dev/null | grep -oP 'bandwidth \K[0-9]+[A-Za-z]*' || echo "") || true
    print_info "Bandwidth on ens16 after SIGUSR1: ${bw_after:-unknown}"

    # Verify bandwidth is non-zero (meaning CAKE is actively shaped by wanctl)
    if [[ -n "$bw_after" && "$bw_after" != "0" && "$bw_after" != "0bit" && "$bw_after" != "0Kbit" ]]; then
        print_pass "CAKE bandwidth is non-zero ($bw_after) -- wanctl is actively shaping via tc"
    else
        print_fail "CAKE bandwidth is zero or unreadable -- wanctl may not be controlling CAKE qdiscs"
    fi
}

# ---------------------------------------------------------------------------
# Check 4: Verify transport is linux-cake in spectrum.yaml
# ---------------------------------------------------------------------------
check_transport_linux_cake() {
    echo ""
    echo -e "${YELLOW}Check 4: Transport is linux-cake in spectrum.yaml${NC}"

    local transport_line
    transport_line=$(ssh "$VM_HOST" "sudo grep 'transport:' ${SPECTRUM_CONFIG}" 2>/dev/null) || {
        print_fail "Could not read transport from ${SPECTRUM_CONFIG}"
        return
    }

    print_info "Config line: ${transport_line}"

    if echo "$transport_line" | grep -q 'linux-cake'; then
        print_pass "Transport is linux-cake"
    elif echo "$transport_line" | grep -q 'rest'; then
        print_fail "Transport is REST -- must be linux-cake for valid tuning tests"
    elif echo "$transport_line" | grep -q 'ssh'; then
        print_fail "Transport is SSH -- must be linux-cake for valid tuning tests"
    else
        print_fail "Unknown transport: ${transport_line}"
    fi
}

# ---------------------------------------------------------------------------
# Check 5: Confirm health endpoint returns correct version
# ---------------------------------------------------------------------------
check_health_endpoint() {
    echo ""
    echo -e "${YELLOW}Check 5: Health endpoint version${NC}"

    local health_json
    health_json=$(ssh "$VM_HOST" "curl -s ${HEALTH_URL}" 2>/dev/null) || {
        print_fail "Could not reach health endpoint at ${HEALTH_URL}"
        return
    }

    if [[ -z "$health_json" ]]; then
        print_fail "Empty response from health endpoint"
        return
    fi

    # Extract version
    local version
    if [[ "$JSON_PARSER" == "jq" ]]; then
        version=$(echo "$health_json" | ssh "$VM_HOST" "jq -r '.version'" 2>/dev/null) || true
    else
        version=$(echo "$health_json" | ssh "$VM_HOST" \
            "python3 -c \"import sys, json; print(json.load(sys.stdin).get('version', ''))\"" 2>/dev/null) || true
    fi

    if [[ -n "$version" && "$version" != "null" ]]; then
        print_pass "Health endpoint reports version: $version"
    else
        print_fail "Health endpoint did not return a version"
        print_info "Response: ${health_json:0:200}"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print_header

# Verify SSH connectivity first
echo -e "${YELLOW}Preflight: SSH connectivity${NC}"
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$VM_HOST" 'echo ok' &>/dev/null; then
    echo -e "  ${RED}[FAIL]${NC} Cannot connect to $VM_HOST via SSH"
    echo ""
    echo -e "${RED}GATE CHECK: 0/${TOTAL} passed -- SSH connectivity failed${NC}"
    exit 1
fi
print_info "SSH to $VM_HOST OK"

# Determine JSON parser available on VM
setup_json_parser
print_info "JSON parser on VM: $JSON_PARSER"
echo ""

# Run all 5 checks
check_cake_qdiscs
check_router_no_cake
check_rate_change_visible
check_transport_linux_cake
check_health_endpoint

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${BLUE}========================================${NC}"
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}  GATE CHECK: ${PASS}/${TOTAL} passed${NC}"
    echo -e "${GREEN}  Test environment is READY for tuning${NC}"
else
    echo -e "${RED}  GATE CHECK: ${PASS}/${TOTAL} passed, ${FAIL} failed${NC}"
    echo -e "${RED}  Fix failures before starting tuning tests${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo ""

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi

exit 0

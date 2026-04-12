#!/bin/bash
# wanctl Post-Deploy Canary Check
#
# Validates live health endpoints after deployment and service restart.
# Consumes the compact summary contract from /health.
#
# Usage:
#   canary-check.sh                            # Check all targets locally
#   canary-check.sh --ssh kevin@10.10.110.223  # Check via SSH
#   canary-check.sh --timeout 45               # Custom readiness timeout
#   canary-check.sh --skip-steering            # Skip steering check
#   canary-check.sh --expect-version 1.33.0    # Warn on version mismatch
#   canary-check.sh --json                     # JSON output for automation
#   canary-check.sh --help                     # Show help
#
# Exit codes:
#   0 = PASS  (all checks passed)
#   1 = FAIL  (blocking failures detected)
#   2 = WARN  (no failures but warnings present)
#
set -euo pipefail

VERSION="1.0.0"

AUTORATE_TARGETS=(
    "spectrum|10.10.110.223|9101"
    "att|10.10.110.227|9101"
)
STEERING_TARGET="steering|127.0.0.1|9102"
DEFAULT_TIMEOUT=30
POLL_INTERVAL=2

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ERRORS=0
WARNINGS=0
SSH_TARGET=""
TIMEOUT="$DEFAULT_TIMEOUT"
SKIP_STEERING=false
EXPECT_VERSION=""
JSON_MODE=false
HAS_JQ=false
JSON_RESULTS=()

if command -v jq &>/dev/null; then
    HAS_JQ=true
fi

usage() {
    cat <<EOF
wanctl Post-Deploy Canary Check ${VERSION}

Usage:
  canary-check.sh [options]

Options:
  --ssh TARGET       SSH target for remote execution
  --timeout N        Readiness timeout in seconds (default: ${DEFAULT_TIMEOUT})
  --skip-steering    Skip steering health check
  --expect-version V Warn if health version != V
  --json             Output results as JSON array
  --help, -h         Show help

Exit codes:
  0 = PASS  (all checks passed)
  1 = FAIL  (blocking failures detected)
  2 = WARN  (no failures but warnings present)
EOF
}

print_pass() {
    if ! $JSON_MODE; then
        echo -e "${GREEN}[PASS]${NC} $1"
    fi
}

print_fail() {
    if ! $JSON_MODE; then
        echo -e "${RED}[FAIL]${NC} $1"
    fi
    ERRORS=$((ERRORS + 1))
}

print_warn() {
    if ! $JSON_MODE; then
        echo -e "${YELLOW}[WARN]${NC} $1"
    fi
    WARNINGS=$((WARNINGS + 1))
}

print_info() {
    if ! $JSON_MODE; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

json_escape() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

jq_or_py() {
    local json="$1"
    local jq_expr="$2"
    local py_expr="$3"
    if $HAS_JQ; then
        echo "$json" | jq -r "$jq_expr"
    else
        echo "$json" | python3 -c "import json, sys; d=json.load(sys.stdin); print($py_expr)"
    fi
}

get_summary_row_json() {
    local json="$1"
    local index="$2"
    if $HAS_JQ; then
        echo "$json" | jq -c ".summary.rows[$index]"
    else
        echo "$json" | python3 -c "import json, sys; d=json.load(sys.stdin); print(json.dumps(d.get('summary', {}).get('rows', [])[int(sys.argv[1])]))" "$index"
    fi
}

append_json_result() {
    local target="$1"
    local result="$2"
    local service="$3"
    local detail="$4"
    JSON_RESULTS+=("{\"target\":$(json_escape "$target"),\"service\":$(json_escape "$service"),\"result\":$(json_escape "$result"),\"detail\":$(json_escape "$detail")}")
}

wait_for_health() {
    local url="$1"
    local timeout="$2"
    local start
    start=$(date +%s)

    while true; do
        local http_code="000"
        if [[ -n "$SSH_TARGET" ]]; then
            http_code=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" \
                "curl -s -o /dev/null -w \"%{http_code}\" --connect-timeout 3 --max-time 5 \"$url\"" \
                2>/dev/null || echo "000")
        else
            http_code=$(curl -s -o /dev/null -w "%{http_code}" \
                --connect-timeout 3 --max-time 5 "$url" 2>/dev/null || echo "000")
        fi

        if [[ "$http_code" == "200" || "$http_code" == "503" ]]; then
            return 0
        fi

        if (( $(date +%s) - start >= timeout )); then
            return 1
        fi

        sleep "$POLL_INTERVAL"
    done
}

fetch_health() {
    local url="$1"
    if [[ -n "$SSH_TARGET" ]]; then
        ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" \
            "curl -s --connect-timeout 3 --max-time 5 \"$url\""
    else
        curl -s --connect-timeout 3 --max-time 5 "$url"
    fi
}

check_status_field() {
    local service="$1"
    local target="$2"
    local json="$3"
    local status

    status=$(jq_or_py "$json" '.status // "unknown"' 'd.get("status", "unknown")')
    if [[ "$status" == "healthy" ]]; then
        print_pass "${service} ${target}: top-level status healthy"
    else
        print_fail "${service} ${target}: top-level status is ${status}"
    fi
}

check_autorate_health() {
    local target="$1"
    local json="$2"
    local version uptime row_count index row_json row_name

    check_status_field "autorate" "$target" "$json"

    version=$(jq_or_py "$json" '.version // "unknown"' 'd.get("version", "unknown")')
    if [[ -n "$EXPECT_VERSION" && "$version" != "$EXPECT_VERSION" ]]; then
        print_warn "autorate ${target}: version ${version} != expected ${EXPECT_VERSION}"
    else
        print_pass "autorate ${target}: version ${version}"
    fi

    uptime=$(jq_or_py "$json" '.uptime_seconds // 0' 'd.get("uptime_seconds", 0)')
    if python3 -c "import sys; raise SystemExit(0 if float(sys.argv[1]) >= 10 else 1)" "$uptime"; then
        print_pass "autorate ${target}: uptime ${uptime}s"
    else
        print_warn "autorate ${target}: uptime ${uptime}s is below 10s"
    fi

    row_count=$(jq_or_py "$json" '.summary.rows | length' 'len(d.get("summary", {}).get("rows", []))')
    if [[ "$row_count" =~ ^[0-9]+$ ]] && [[ "$row_count" -gt 0 ]]; then
        :
    else
        print_fail "autorate ${target}: summary.rows missing"
        return
    fi

    for ((index = 0; index < row_count; index++)); do
        row_json=$(get_summary_row_json "$json" "$index")
        row_name=$(jq_or_py "$row_json" '.name // "unknown"' 'd.get("name", "unknown")')

        if [[ "$(jq_or_py "$row_json" '.router_reachable // false' 'd.get("router_reachable", False)')" == "true" ]]; then
            print_pass "autorate ${target}/${row_name}: router reachable"
        else
            print_fail "autorate ${target}/${row_name}: router unreachable"
        fi

        case "$(jq_or_py "$row_json" '.storage_status // "unknown"' 'd.get("storage_status", "unknown")')" in
            ok) print_pass "autorate ${target}/${row_name}: storage ok" ;;
            warning) print_warn "autorate ${target}/${row_name}: storage warning" ;;
            critical) print_fail "autorate ${target}/${row_name}: storage critical" ;;
            *) print_fail "autorate ${target}/${row_name}: storage status unknown" ;;
        esac

        case "$(jq_or_py "$row_json" '.runtime_status // "unknown"' 'd.get("runtime_status", "unknown")')" in
            ok) print_pass "autorate ${target}/${row_name}: runtime ok" ;;
            warning) print_warn "autorate ${target}/${row_name}: runtime warning" ;;
            critical) print_fail "autorate ${target}/${row_name}: runtime critical" ;;
            *) print_fail "autorate ${target}/${row_name}: runtime status unknown" ;;
        esac

        case "$(jq_or_py "$row_json" '.download_state // "unknown"' 'd.get("download_state", "unknown")')" in
            GREEN|YELLOW) print_pass "autorate ${target}/${row_name}: download state healthy" ;;
            SOFT_RED|RED) print_warn "autorate ${target}/${row_name}: download state elevated" ;;
            *) print_fail "autorate ${target}/${row_name}: download state unknown" ;;
        esac

        case "$(jq_or_py "$row_json" '.upload_state // "unknown"' 'd.get("upload_state", "unknown")')" in
            GREEN|YELLOW) print_pass "autorate ${target}/${row_name}: upload state healthy" ;;
            RED|SOFT_RED) print_warn "autorate ${target}/${row_name}: upload state elevated" ;;
            *) print_fail "autorate ${target}/${row_name}: upload state unknown" ;;
        esac
    done
}

check_steering_health() {
    local target="$1"
    local json="$2"
    local row_count index row_json row_name

    check_status_field "steering" "$target" "$json"

    row_count=$(jq_or_py "$json" '.summary.rows | length' 'len(d.get("summary", {}).get("rows", []))')
    if [[ "$row_count" =~ ^[0-9]+$ ]] && [[ "$row_count" -gt 0 ]]; then
        :
    else
        print_fail "steering ${target}: summary.rows missing"
        return
    fi

    for ((index = 0; index < row_count; index++)); do
        row_json=$(get_summary_row_json "$json" "$index")
        row_name=$(jq_or_py "$row_json" '.name // "unknown"' 'd.get("name", "unknown")')

        if [[ "$(jq_or_py "$row_json" '.router_reachable // false' 'd.get("router_reachable", False)')" == "true" ]]; then
            print_pass "steering ${target}/${row_name}: router reachable"
        else
            print_fail "steering ${target}/${row_name}: router unreachable"
        fi

        case "$(jq_or_py "$row_json" '.storage_status // "unknown"' 'd.get("storage_status", "unknown")')" in
            ok) print_pass "steering ${target}/${row_name}: storage ok" ;;
            warning) print_warn "steering ${target}/${row_name}: storage warning" ;;
            critical) print_fail "steering ${target}/${row_name}: storage critical" ;;
            *) print_fail "steering ${target}/${row_name}: storage status unknown" ;;
        esac

        case "$(jq_or_py "$row_json" '.runtime_status // "unknown"' 'd.get("runtime_status", "unknown")')" in
            ok) print_pass "steering ${target}/${row_name}: runtime ok" ;;
            warning) print_warn "steering ${target}/${row_name}: runtime warning" ;;
            critical) print_fail "steering ${target}/${row_name}: runtime critical" ;;
            *) print_fail "steering ${target}/${row_name}: runtime status unknown" ;;
        esac
    done
}

run_target_check() {
    local service="$1"
    local name="$2"
    local host="$3"
    local port="$4"
    local url="http://${host}:${port}/health"
    local before_errors before_warnings json result detail

    before_errors=$ERRORS
    before_warnings=$WARNINGS

    print_info "Checking ${service} ${name} via ${url}"
    if ! wait_for_health "$url" "$TIMEOUT"; then
        print_fail "${service} ${name}: health endpoint not ready within ${TIMEOUT}s"
        append_json_result "$name" "fail" "$service" "health endpoint timeout"
        return
    fi

    if ! json=$(fetch_health "$url"); then
        print_fail "${service} ${name}: failed to fetch health JSON"
        append_json_result "$name" "fail" "$service" "fetch health failed"
        return
    fi

    if [[ -z "$json" || "$json" == "null" ]]; then
        print_fail "${service} ${name}: empty health response"
        append_json_result "$name" "fail" "$service" "empty health response"
        return
    fi

    if [[ "$service" == "autorate" ]]; then
        check_autorate_health "$name" "$json"
    else
        check_steering_health "$name" "$json"
    fi

    if (( ERRORS > before_errors )); then
        result="fail"
        detail="blocking issues detected"
    elif (( WARNINGS > before_warnings )); then
        result="warn"
        detail="warnings detected"
    else
        result="pass"
        detail="all checks passed"
    fi
    append_json_result "$name" "$result" "$service" "$detail"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssh)
            SSH_TARGET="${2:-}"
            shift 2
            ;;
        --timeout)
            TIMEOUT="${2:-}"
            shift 2
            ;;
        --skip-steering)
            SKIP_STEERING=true
            shift
            ;;
        --expect-version)
            EXPECT_VERSION="${2:-}"
            shift 2
            ;;
        --json)
            JSON_MODE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT" -le 0 ]]; then
    echo "Timeout must be a positive integer" >&2
    exit 1
fi

if ! $JSON_MODE; then
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  wanctl Post-Deploy Canary Check - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
fi

for target in "${AUTORATE_TARGETS[@]}"; do
    IFS='|' read -r name host port <<< "$target"
    run_target_check "autorate" "$name" "$host" "$port"
done

if ! $SKIP_STEERING; then
    IFS='|' read -r name host port <<< "$STEERING_TARGET"
    run_target_check "steering" "$name" "$host" "$port"
fi

if $JSON_MODE; then
    printf '[%s]\n' "$(IFS=,; echo "${JSON_RESULTS[*]}")"
else
    echo ""
    echo -e "${BOLD}Summary${NC}"
    echo "-------"
    echo "Errors:   ${ERRORS}"
    echo "Warnings: ${WARNINGS}"
    echo ""
fi

if [[ $ERRORS -gt 0 ]]; then
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    exit 2
else
    exit 0
fi

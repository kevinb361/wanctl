#!/bin/bash
#
# Burst Detection Validation — Flent Regression Suite
#
# Runs tcp_12down, rrul, and rrul_be flent tests to validate:
#   VAL-01: tcp_12down p99 < 500ms (burst detection eliminates bufferbloat spikes)
#   VAL-02: rrul and rrul_be p99 within 10% of pre-burst baselines (no regression)
#
# Runs FROM the dev machine. Flent is invoked locally against the dallas netperf server.
# Pre-flight gate verifies CAKE qdiscs, transport, and burst detection before any tests.
#
# Usage:
#   bash scripts/burst-validation.sh                              # Run all 3 test types (5 runs each, 60s)
#   bash scripts/burst-validation.sh --test tcp_12down            # Run tcp_12down only
#   bash scripts/burst-validation.sh --test rrul --runs 10        # 10 runs of rrul
#   bash scripts/burst-validation.sh --test all --duration 30     # Shorter runs
#
# Output: Structured results table with PASS/FAIL verdicts per test type.

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

FLENT_HOST="104.200.21.31"       # Dallas netperf server
VM_HOST="kevin@10.10.110.223"    # cake-shaper VM
HEALTH_URL="http://127.0.0.1:9101/health"

DEFAULT_RUNS=5
DEFAULT_DURATION=60

# Pre-burst baselines (from formal testing, 153-RESEARCH)
BASELINE_TCP12_P99=3302          # ms — tcp_12down p99 before burst detection
BASELINE_RRUL_P99=200            # ms — rrul p99 before burst detection
BASELINE_RRUL_BE_P99=152         # ms — rrul_be p99 before burst detection

# Thresholds
TCP12_P99_THRESHOLD=500          # VAL-01: tcp_12down p99 must be below this
REGRESSION_TOLERANCE=10          # VAL-02: percent — rrul/rrul_be must be within this of baseline

# ============================================================================
# Colors (matching check-tuning-gate.sh pattern)
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# Argument Parsing
# ============================================================================

TEST_TYPE="all"
RUNS="$DEFAULT_RUNS"
DURATION="$DEFAULT_DURATION"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            TEST_TYPE="$2"
            shift 2
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--test tcp_12down|rrul|rrul_be|all] [--runs N] [--duration N]"
            echo ""
            echo "Options:"
            echo "  --test TYPE     Test type: tcp_12down, rrul, rrul_be, or all (default: all)"
            echo "  --runs N        Number of runs per test type (default: $DEFAULT_RUNS)"
            echo "  --duration N    Flent test duration in seconds (default: $DEFAULT_DURATION)"
            echo ""
            echo "Thresholds:"
            echo "  VAL-01: tcp_12down p99 < ${TCP12_P99_THRESHOLD}ms"
            echo "  VAL-02: rrul/rrul_be p99 within ${REGRESSION_TOLERANCE}% of baseline"
            echo ""
            echo "Baselines: tcp_12down=${BASELINE_TCP12_P99}ms, rrul=${BASELINE_RRUL_P99}ms, rrul_be=${BASELINE_RRUL_BE_P99}ms"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Use --help for usage."
            exit 1
            ;;
    esac
done

# Validate test type
case "$TEST_TYPE" in
    tcp_12down|rrul|rrul_be|all) ;;
    *)
        echo -e "${RED}ERROR: Invalid test type '$TEST_TYPE'. Must be tcp_12down, rrul, rrul_be, or all.${NC}"
        exit 1
        ;;
esac

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

print_pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
}

print_info() {
    echo -e "  ${BLUE}[INFO]${NC} $1"
}

# ============================================================================
# Pre-flight Gate (mandatory)
# ============================================================================

run_preflight_gate() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Pre-flight Gate Check${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Run the standard tuning gate check
    log "Running check-tuning-gate.sh..."
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if ! bash "${script_dir}/check-tuning-gate.sh"; then
        echo ""
        echo -e "${RED}ABORT: Pre-flight gate check failed. Fix issues before running validation.${NC}"
        exit 1
    fi

    # Verify burst detection is enabled via health endpoint
    echo ""
    echo -e "${YELLOW}Burst Detection Verification${NC}"

    local health_json
    health_json=$(ssh "$VM_HOST" "curl -s ${HEALTH_URL}" 2>/dev/null) || {
        echo -e "${RED}ABORT: Could not reach health endpoint at ${HEALTH_URL}${NC}"
        exit 1
    }

    if [[ -z "$health_json" ]]; then
        echo -e "${RED}ABORT: Empty response from health endpoint${NC}"
        exit 1
    fi

    # Determine JSON parser available on VM
    local json_parser="python3"
    if ssh "$VM_HOST" 'command -v jq' &>/dev/null; then
        json_parser="jq"
    fi

    # Check burst_detection.enabled
    local burst_enabled
    if [[ "$json_parser" == "jq" ]]; then
        burst_enabled=$(echo "$health_json" | ssh "$VM_HOST" "jq -r '.wans[0].burst_detection.enabled'" 2>/dev/null) || true
    else
        burst_enabled=$(echo "$health_json" | ssh "$VM_HOST" "python3 -c \"
import sys, json
data = json.load(sys.stdin)
print(data.get('wans', [{}])[0].get('burst_detection', {}).get('enabled', False))
\"" 2>/dev/null) || true
    fi

    if [[ "$burst_enabled" != "true" && "$burst_enabled" != "True" ]]; then
        print_fail "burst_detection.enabled is '$burst_enabled' (expected true)"
        echo -e "${RED}ABORT: Burst detection must be enabled for validation.${NC}"
        exit 1
    fi
    print_pass "burst_detection.enabled = true"

    # Check burst_response_enabled
    local response_enabled
    if [[ "$json_parser" == "jq" ]]; then
        response_enabled=$(echo "$health_json" | ssh "$VM_HOST" "jq -r '.wans[0].burst_detection.burst_response_enabled'" 2>/dev/null) || true
    else
        response_enabled=$(echo "$health_json" | ssh "$VM_HOST" "python3 -c \"
import sys, json
data = json.load(sys.stdin)
print(data.get('wans', [{}])[0].get('burst_detection', {}).get('burst_response_enabled', False))
\"" 2>/dev/null) || true
    fi

    if [[ "$response_enabled" != "true" && "$response_enabled" != "True" ]]; then
        print_fail "burst_detection.burst_response_enabled is '$response_enabled' (expected true)"
        echo -e "${RED}ABORT: Burst response must be enabled for validation.${NC}"
        exit 1
    fi
    print_pass "burst_detection.burst_response_enabled = true"

    # Record version for results output
    if [[ "$json_parser" == "jq" ]]; then
        WANCTL_VERSION=$(echo "$health_json" | ssh "$VM_HOST" "jq -r '.version'" 2>/dev/null) || WANCTL_VERSION="unknown"
    else
        WANCTL_VERSION=$(echo "$health_json" | ssh "$VM_HOST" "python3 -c \"
import sys, json
print(json.load(sys.stdin).get('version', 'unknown'))
\"" 2>/dev/null) || WANCTL_VERSION="unknown"
    fi
    print_info "wanctl version: $WANCTL_VERSION"

    echo ""
    echo -e "${GREEN}Pre-flight gate: ALL CHECKS PASSED${NC}"
    echo ""
}

# ============================================================================
# Flent Test Execution
# ============================================================================

# Run a single flent test and return pipe-delimited results: median|p99|dl_sum
# Arguments: test_name label run_num
run_flent_test() {
    local test_name="$1"
    local label="$2"
    local run_num="$3"

    local output
    output=$(flent "$test_name" -H "$FLENT_HOST" -l "$DURATION" -t "${label}-run${run_num}" 2>&1)

    local icmp_median icmp_p99 dl_sum
    icmp_median=$(echo "$output" | grep "Ping (ms) ICMP" | awk '{print $6}')
    icmp_p99=$(echo "$output" | grep "Ping (ms) ICMP" | awk '{print $7}')
    dl_sum=$(echo "$output" | grep "TCP download sum" | awk '{print $5}')

    echo "${icmp_median}|${icmp_p99}|${dl_sum}"
}

# ============================================================================
# Test Suite Runner
# ============================================================================

# Run a complete test suite for a given test type.
# Arguments: test_type
# Sets global VERDICT_<test_type>=PASS|FAIL
run_test_suite() {
    local test_type="$1"
    local baseline threshold_desc

    case "$test_type" in
        tcp_12down)
            baseline="$BASELINE_TCP12_P99"
            threshold_desc="p99 < ${TCP12_P99_THRESHOLD}ms (VAL-01)"
            ;;
        rrul)
            baseline="$BASELINE_RRUL_P99"
            local max_allowed
            max_allowed=$(awk "BEGIN {printf \"%.0f\", $baseline * (1 + $REGRESSION_TOLERANCE / 100.0)}")
            threshold_desc="p99 <= ${max_allowed}ms (within ${REGRESSION_TOLERANCE}% of baseline ${baseline}ms) (VAL-02)"
            ;;
        rrul_be)
            baseline="$BASELINE_RRUL_BE_P99"
            local max_allowed
            max_allowed=$(awk "BEGIN {printf \"%.0f\", $baseline * (1 + $REGRESSION_TOLERANCE / 100.0)}")
            threshold_desc="p99 <= ${max_allowed}ms (within ${REGRESSION_TOLERANCE}% of baseline ${baseline}ms) (VAL-02)"
            ;;
    esac

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Test: ${test_type} (${RUNS} runs x ${DURATION}s)${NC}"
    echo -e "${BLUE}  Threshold: ${threshold_desc}${NC}"
    echo -e "${BLUE}  Baseline p99: ${baseline}ms${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Collect per-run results
    local p99_values=()
    local median_values=()
    local dl_values=()

    echo "| Run | Median (ms) | p99 (ms) | DL Sum (Mbps) |"
    echo "|-----|-------------|----------|---------------|"

    for run in $(seq 1 "$RUNS"); do
        log "  Running ${test_type} run ${run}/${RUNS}..."
        local result
        result=$(run_flent_test "$test_type" "${test_type}" "$run")

        local median p99 dl_sum
        IFS='|' read -r median p99 dl_sum <<< "$result"

        # Handle empty values gracefully
        median="${median:-N/A}"
        p99="${p99:-N/A}"
        dl_sum="${dl_sum:-N/A}"

        echo "| ${run} | ${median} | ${p99} | ${dl_sum} |"

        # Collect numeric p99 for averaging (skip N/A)
        if [[ "$p99" != "N/A" && "$p99" =~ ^[0-9.]+$ ]]; then
            p99_values+=("$p99")
        fi
        if [[ "$median" != "N/A" && "$median" =~ ^[0-9.]+$ ]]; then
            median_values+=("$median")
        fi

        # Brief pause between runs to let CAKE/controller settle
        if [[ "$run" -lt "$RUNS" ]]; then
            sleep 3
        fi
    done

    echo ""

    # Compute average p99
    if [[ ${#p99_values[@]} -eq 0 ]]; then
        echo -e "${RED}ERROR: No valid p99 values collected for ${test_type}${NC}"
        eval "VERDICT_${test_type}=FAIL"
        return
    fi

    local avg_p99
    avg_p99=$(printf '%s\n' "${p99_values[@]}" | awk '{sum+=$1} END {printf "%.1f", sum/NR}')

    local avg_median="N/A"
    if [[ ${#median_values[@]} -gt 0 ]]; then
        avg_median=$(printf '%s\n' "${median_values[@]}" | awk '{sum+=$1} END {printf "%.1f", sum/NR}')
    fi

    local min_p99 max_p99
    min_p99=$(printf '%s\n' "${p99_values[@]}" | sort -n | head -1)
    max_p99=$(printf '%s\n' "${p99_values[@]}" | sort -n | tail -1)

    echo -e "${BOLD}Results Summary:${NC}"
    echo "  Runs completed: ${#p99_values[@]}/${RUNS}"
    echo "  Average median: ${avg_median}ms"
    echo "  Average p99:    ${avg_p99}ms"
    echo "  p99 range:      ${min_p99}ms - ${max_p99}ms"
    echo "  Baseline p99:   ${baseline}ms"
    echo ""

    # Verdict
    local verdict="FAIL"
    case "$test_type" in
        tcp_12down)
            # VAL-01: avg p99 must be below threshold
            local passes
            passes=$(awk "BEGIN {print ($avg_p99 < $TCP12_P99_THRESHOLD) ? 1 : 0}")
            if [[ "$passes" -eq 1 ]]; then
                verdict="PASS"
                local improvement
                improvement=$(awk "BEGIN {printf \"%.0f\", (1 - $avg_p99 / $baseline) * 100}")
                print_pass "tcp_12down avg p99 = ${avg_p99}ms < ${TCP12_P99_THRESHOLD}ms threshold (${improvement}% improvement from ${baseline}ms baseline)"
            else
                print_fail "tcp_12down avg p99 = ${avg_p99}ms >= ${TCP12_P99_THRESHOLD}ms threshold"
            fi
            ;;
        rrul|rrul_be)
            # VAL-02: avg p99 must be within REGRESSION_TOLERANCE% of baseline
            local max_allowed delta_pct
            max_allowed=$(awk "BEGIN {printf \"%.1f\", $baseline * (1 + $REGRESSION_TOLERANCE / 100.0)}")
            delta_pct=$(awk "BEGIN {printf \"%.1f\", (($avg_p99 - $baseline) / $baseline) * 100}")
            local passes
            passes=$(awk "BEGIN {print ($avg_p99 <= $max_allowed) ? 1 : 0}")
            if [[ "$passes" -eq 1 ]]; then
                verdict="PASS"
                print_pass "${test_type} avg p99 = ${avg_p99}ms <= ${max_allowed}ms (delta: ${delta_pct}% from ${baseline}ms baseline)"
            else
                print_fail "${test_type} avg p99 = ${avg_p99}ms > ${max_allowed}ms (delta: ${delta_pct}% exceeds ${REGRESSION_TOLERANCE}% tolerance)"
            fi
            ;;
    esac

    eval "VERDICT_${test_type}=${verdict}"
}

# ============================================================================
# Main
# ============================================================================

WANCTL_VERSION="unknown"

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Burst Detection Validation Suite${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "  Date:     $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  Host:     $(hostname)"
echo "  Target:   ${FLENT_HOST} (dallas netperf)"
echo "  VM:       ${VM_HOST}"
echo "  Test:     ${TEST_TYPE}"
echo "  Runs:     ${RUNS} per test type"
echo "  Duration: ${DURATION}s per run"
echo ""

# Run pre-flight gate
run_preflight_gate

# Estimated time
TESTS_TO_RUN=()
case "$TEST_TYPE" in
    all)        TESTS_TO_RUN=(tcp_12down rrul rrul_be) ;;
    tcp_12down) TESTS_TO_RUN=(tcp_12down) ;;
    rrul)       TESTS_TO_RUN=(rrul) ;;
    rrul_be)    TESTS_TO_RUN=(rrul_be) ;;
esac

total_runs=$(( ${#TESTS_TO_RUN[@]} * RUNS ))
est_minutes=$(( total_runs * (DURATION + 10) / 60 ))
log "Starting ${#TESTS_TO_RUN[@]} test suites, ${total_runs} total runs (~${est_minutes} minutes)"

# Initialize verdict variables
VERDICT_tcp_12down="SKIP"
VERDICT_rrul="SKIP"
VERDICT_rrul_be="SKIP"

# Run each selected test suite
for test in "${TESTS_TO_RUN[@]}"; do
    run_test_suite "$test"
done

# ============================================================================
# Final Summary
# ============================================================================

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Validation Summary${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "  wanctl version: ${WANCTL_VERSION}"
echo "  Date:           $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  Runs per test:  ${RUNS} x ${DURATION}s"
echo ""
echo "| Test        | Verdict | Requirement | Threshold                           |"
echo "|-------------|---------|-------------|-------------------------------------|"

ALL_PASS=true

for test in tcp_12down rrul rrul_be; do
    local_verdict="SKIP"
    eval "local_verdict=\${VERDICT_${test}}"

    case "$test" in
        tcp_12down)
            req="VAL-01"
            thresh="p99 < ${TCP12_P99_THRESHOLD}ms"
            ;;
        rrul)
            req="VAL-02"
            thresh="p99 within ${REGRESSION_TOLERANCE}% of ${BASELINE_RRUL_P99}ms"
            ;;
        rrul_be)
            req="VAL-02"
            thresh="p99 within ${REGRESSION_TOLERANCE}% of ${BASELINE_RRUL_BE_P99}ms"
            ;;
    esac

    if [[ "$local_verdict" == "PASS" ]]; then
        color="$GREEN"
    elif [[ "$local_verdict" == "FAIL" ]]; then
        color="$RED"
        ALL_PASS=false
    else
        color="$YELLOW"
    fi

    echo -e "| ${test} | ${color}${local_verdict}${NC} | ${req} | ${thresh} |"
done

echo ""

if $ALL_PASS; then
    echo -e "${GREEN}OVERALL: ALL VALIDATION TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}OVERALL: ONE OR MORE VALIDATION TESTS FAILED${NC}"
    exit 1
fi

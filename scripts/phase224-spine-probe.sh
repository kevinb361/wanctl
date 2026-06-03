#!/usr/bin/env bash
#
# Phase 224 read-only steering spine probe.
#
# Emits a single JSON record for the live canary gate evaluator. The probe reads
# raw steering /health over SSH, reads the RouterOS selector shape when operator
# credentials are available, and fingerprints the deployed steering daemon code.
# It deliberately does not inspect /var/lib/wanctl/spectrum_state.json presence:
# production steering reads that file as autorate baseline input by design.

set -euo pipefail

SSH_HOST="cake-shaper"
HEALTH_URL="http://10.10.110.223:9101/health"
STEERING_HEALTH_URL="http://127.0.0.1:9102/health"
DAEMON_SOURCE_PATH="/opt/wanctl/steering/daemon.py"
BASELINE_FINGERPRINT=""
OUTPUT=""

MANGLE_COMMENT="ADAPTIVE: Steer latency-sensitive to ATT"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase224-spine-probe.sh [options]

Options:
  --ssh-host HOST              Target host for SSH reads (default: cake-shaper)
  --health-url URL             Autorate health URL recorded for context (default: http://10.10.110.223:9101/health)
  --steering-health-url URL    Steering health URL fetched over SSH (default: http://127.0.0.1:9102/health)
  --daemon-source-path PATH    Deployed daemon source path to sha256sum (default: /opt/wanctl/steering/daemon.py)
  --baseline-fingerprint SHA   REQUIRED Phase 223-validated daemon.py SHA-256 baseline
  --output PATH                Optional output JSON path; stdout when omitted
  --help, -h                   Show this help

RouterOS read-only selector probe:
  Preferred REST env: PHASE224_ROUTER_REST_URL, PHASE224_ROUTER_USER, PHASE224_ROUTER_PASSWORD
  Fallback SSH env:   PHASE224_ROUTER_SSH_HOST

The script never consumes canary-check summary-mode payloads and never uses
spectrum_state.json file presence as an invariant signal.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssh-host)
            SSH_HOST="${2:-}"
            shift 2
            ;;
        --health-url)
            HEALTH_URL="${2:-}"
            shift 2
            ;;
        --steering-health-url)
            STEERING_HEALTH_URL="${2:-}"
            shift 2
            ;;
        --daemon-source-path)
            DAEMON_SOURCE_PATH="${2:-}"
            shift 2
            ;;
        --baseline-fingerprint)
            BASELINE_FINGERPRINT="${2:-}"
            shift 2
            ;;
        --output)
            OUTPUT="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$BASELINE_FINGERPRINT" ]]; then
    echo "ERROR: --baseline-fingerprint is required for code-fingerprint invariant" >&2
    exit 2
fi

require_command ssh
require_command curl
require_command jq
require_command date

captured_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

if [[ -n "$OUTPUT" ]]; then
    mkdir -p "$(dirname "$OUTPUT")"
    RAW_HEALTH_PATH="${OUTPUT}.raw-steering-health.json"
else
    RAW_HEALTH_PATH="$(mktemp -t phase224-raw-steering-health.XXXXXX.json)"
fi

# First action after setup: fetch raw steering /health over SSH. This is the
# source payload consumed by the gate evaluator, not the canary-check summary mode.
ssh -o BatchMode=yes "$SSH_HOST" \
    "curl -s --connect-timeout 3 --max-time 5 \"$STEERING_HEALTH_URL\"" \
    >"$RAW_HEALTH_PATH"

health_json="$(cat "$RAW_HEALTH_PATH")"

fetch_rule_rest() {
    local rest_url="${PHASE224_ROUTER_REST_URL:-}"
    local user="${PHASE224_ROUTER_USER:-}"
    local password="${PHASE224_ROUTER_PASSWORD:-}"
    if [[ -z "$rest_url" || -z "$user" || -z "$password" ]]; then
        return 1
    fi
    curl -sk --connect-timeout 3 --max-time 8 \
        -u "${user}:${password}" \
        "${rest_url%/}/rest/ip/firewall/mangle"
}

fetch_rule_ssh() {
    local router_ssh="${PHASE224_ROUTER_SSH_HOST:-}"
    if [[ -z "$router_ssh" ]]; then
        return 1
    fi
    ssh -o BatchMode=yes "$router_ssh" \
        '/ip/firewall/mangle/print detail where comment="ADAPTIVE: Steer latency-sensitive to ATT"'
}

rule_payload=""
rule_read_error=""
if rule_payload="$(fetch_rule_rest 2>/dev/null)"; then
    router_method="rest"
elif rule_payload="$(fetch_rule_ssh 2>/dev/null)"; then
    router_method="ssh"
else
    router_method="unreadable"
    rule_read_error="router rule read unavailable; set PHASE224_ROUTER_REST_URL/USER/PASSWORD or PHASE224_ROUTER_SSH_HOST"
fi

selector_json="{}"
selector_match="null"
rule_present="null"
binary_read_error="$rule_read_error"
selector_read_error="$rule_read_error"

if [[ -n "$rule_payload" ]]; then
    if jq -e 'type == "array"' >/dev/null 2>&1 <<<"$rule_payload"; then
        selector_json="$(jq -c --arg comment "$MANGLE_COMMENT" '[.[] | select(.comment == $comment)][0] // {}' <<<"$rule_payload")"
        if [[ "$selector_json" != "{}" ]]; then
            rule_present="$(jq -r 'if (.disabled // "false") == "true" then "false" else "true" end' <<<"$selector_json")"
            selector_match="$(jq -r '
                (.chain == "prerouting") and
                (.action == "mark-routing") and
                ((."connection-state" // .connection_state // "") | contains("new")) and
                ((."connection-mark" // .connection_mark // "") | test("QOS_HIGH|QOS_MEDIUM|GAMES"))
            ' <<<"$selector_json")"
            binary_read_error=""
            selector_read_error=""
        else
            rule_present="false"
            selector_match="false"
            binary_read_error=""
            selector_read_error="mangle rule with expected comment not found"
        fi
    else
        # SSH detail output fallback: record text fields without trying to mutate.
        selector_json="$(jq -n --arg raw "$rule_payload" '{raw: $raw}')"
        if grep -q "$MANGLE_COMMENT" <<<"$rule_payload"; then
            rule_present="true"
            if grep -Eq 'connection-state=new|connection-state=.*new' <<<"$rule_payload" \
                && grep -Eq 'QOS_HIGH|QOS_MEDIUM|GAMES' <<<"$rule_payload"; then
                selector_match="true"
            else
                selector_match="false"
            fi
            binary_read_error=""
            selector_read_error=""
        else
            rule_present="false"
            selector_match="false"
            binary_read_error=""
            selector_read_error="mangle rule with expected comment not found"
        fi
    fi
fi

enabled="$(jq -r '.steering.enabled // null' <<<"$health_json")"
binary_match="null"
if [[ "$enabled" == "true" || "$enabled" == "false" ]] && [[ "$rule_present" == "true" || "$rule_present" == "false" ]]; then
    if [[ "$enabled" == "$rule_present" ]]; then
        binary_match="true"
    else
        binary_match="false"
    fi
fi

fingerprint_out=""
fingerprint_error=""
deployed_sha256=""
fingerprint_match="null"
if fingerprint_out="$(ssh -o BatchMode=yes "$SSH_HOST" "sudo -n sha256sum \"$DAEMON_SOURCE_PATH\"" 2>&1)"; then
    deployed_sha256="${fingerprint_out%% *}"
    if [[ "$deployed_sha256" == "$BASELINE_FINGERPRINT" ]]; then
        fingerprint_match="true"
    else
        fingerprint_match="false"
    fi
else
    fingerprint_error="$fingerprint_out"
fi

expected_selector="$(jq -n --arg comment "$MANGLE_COMMENT" '{comment: $comment, chain: "prerouting", action: "mark-routing", connection_state: "new", connection_mark_any_of: ["QOS_HIGH", "QOS_MEDIUM", "GAMES"]}')"

result="$(jq -n \
    --arg captured_at "$captured_at" \
    --arg target_host "$SSH_HOST" \
    --arg raw_health_path "$RAW_HEALTH_PATH" \
    --arg health_url "$HEALTH_URL" \
    --arg router_method "$router_method" \
    --argjson health "$health_json" \
    --argjson enabled "$enabled" \
    --argjson rule_present "$rule_present" \
    --argjson binary_match "$binary_match" \
    --arg binary_read_error "$binary_read_error" \
    --argjson live_selector "$selector_json" \
    --argjson expected_selector "$expected_selector" \
    --argjson selector_match "$selector_match" \
    --arg selector_read_error "$selector_read_error" \
    --arg daemon_source_path "$DAEMON_SOURCE_PATH" \
    --arg deployed_sha256 "$deployed_sha256" \
    --arg baseline_sha256 "$BASELINE_FINGERPRINT" \
    --argjson fingerprint_match "$fingerprint_match" \
    --arg fingerprint_error "$fingerprint_error" \
    '{
      captured_at: $captured_at,
      target_host: $target_host,
      raw_health_path: $raw_health_path,
      autorate_health_url: $health_url,
      router_probe_method: $router_method,
      health: {
        version: ($health.version // null),
        status: ($health.status // null),
        uptime_seconds: ($health.uptime_seconds // null),
        router_reachable: ($health.router_reachable // null),
        decision: {
          last_transition_time: ($health.decision.last_transition_time // null),
          time_in_state_seconds: ($health.decision.time_in_state_seconds // null)
        },
        rtt_source: {
          current: ($health.rtt_source.current // null),
          last_successful: ($health.rtt_source.last_successful // null),
          last_measurement_age_sec: ($health.rtt_source.last_measurement_age_sec // null)
        }
      },
      spine: {
        binary_on_off: {
          enabled: $enabled,
          rule_present: $rule_present,
          match: $binary_match,
          read_error: (if $binary_read_error == "" then null else $binary_read_error end)
        },
        only_new_connections: {
          live_selector: $live_selector,
          expected_selector: $expected_selector,
          match: $selector_match,
          read_error: (if $selector_read_error == "" then null else $selector_read_error end)
        },
        spectrum_state_not_written_by_daemon: {
          method: "code-fingerprint",
          daemon_source_path: $daemon_source_path,
          deployed_sha256: $deployed_sha256,
          baseline_sha256: $baseline_sha256,
          match: $fingerprint_match,
          read_error: (if $fingerprint_error == "" then null else $fingerprint_error end)
        }
      }
    }')"

if [[ -n "$OUTPUT" ]]; then
    printf '%s\n' "$result" >"$OUTPUT"
else
    printf '%s\n' "$result"
fi

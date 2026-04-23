#!/usr/bin/env bash
#
# Phase 192 soak capture helper.
#
# Operator-run only. This script captures the three D-08 soak categories plus
# protocol-deprioritization log volume into one JSON object per WAN. It does
# not deploy, restart services, or modify router/controller state.
#
# Requirements:
# - `jq`, `curl`, and `ssh` available on the machine running the script
# - environment variables sourced from `scripts/phase192-soak-capture.env.example`
#
# Timing:
# - run `pre` before the merge/deploy that ships Phase 192
# - run `post` 24h after deploy in a comparable load window when possible
#
# Usage:
#   WANS="wan_a wan_b" \
#   WANCTL_WAN_A_HEALTH_URL="http://host-a:9101/health" \
#   WANCTL_WAN_A_SSH_HOST="operator@host-a" \
#   WANCTL_WAN_B_HEALTH_URL="http://host-b:9101/health" \
#   WANCTL_WAN_B_SSH_HOST="operator@host-b" \
#     ./scripts/phase192-soak-capture.sh pre

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/phase192-soak-capture.sh {pre|post}

Environment:
  WANS                     Space-separated WAN names
  WANCTL_<WAN>_HEALTH_URL  Per-WAN /health URL
  WANCTL_<WAN>_SSH_HOST    Per-WAN SSH host for journalctl reads
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

require_var() {
    local var_name="$1"
    local description="$2"
    if [[ -z "${!var_name:-}" ]]; then
        echo "ERROR: $var_name is required ($description)" >&2
        exit 2
    fi
}

normalize_wan_token() {
    local wan="$1"
    printf '%s' "$wan" | tr '[:lower:]-' '[:upper:]_'
}

phase_window="${1:-}"
case "$phase_window" in
    pre|post) ;;
    "")
        usage >&2
        exit 2
        ;;
    *)
        echo "ERROR: first argument must be 'pre' or 'post', got: $phase_window" >&2
        usage >&2
        exit 2
        ;;
esac

require_command curl
require_command jq
require_command ssh

require_var WANS "space-separated WAN names, e.g. 'wan_a wan_b'"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
out_dir="$repo_root/.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/soak/$phase_window"
mkdir -p "$out_dir"

captured_at_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
file_ts="$(date -u +%Y%m%dT%H%M%SZ)"

capture_wan() {
    local wan="$1"
    local wan_upper
    local health_var
    local ssh_var
    local health_url
    local ssh_host
    local raw_dir
    local raw_health
    local raw_journal
    local raw_fusion
    local parsed_file
    local dwell_bypassed_count
    local burst_trigger_count_dl
    local burst_trigger_count_ul
    local fusion_transition_count_24h
    local protocol_deprio_count_24h

    wan_upper="$(normalize_wan_token "$wan")"
    health_var="WANCTL_${wan_upper}_HEALTH_URL"
    ssh_var="WANCTL_${wan_upper}_SSH_HOST"

    require_var "$health_var" "health endpoint URL for WAN '$wan'"
    require_var "$ssh_var" "SSH target for WAN '$wan' journalctl reads"

    health_url="${!health_var}"
    ssh_host="${!ssh_var}"

    raw_dir="$out_dir/${wan}-raw"
    mkdir -p "$raw_dir"
    raw_health="$raw_dir/health-${file_ts}.json"
    raw_journal="$raw_dir/journal-${file_ts}.log"
    raw_fusion="$raw_dir/fusion-transitions-${file_ts}.log"
    parsed_file="$out_dir/${wan}.json"

    curl --fail --silent --show-error --max-time 5 "$health_url" >"$raw_health"

    dwell_bypassed_count="$(jq -er '.download.hysteresis.dwell_bypassed_count // 0 | floor' "$raw_health")"
    burst_trigger_count_dl="$(jq -er '.download.burst.trigger_count // 0 | floor' "$raw_health")"
    burst_trigger_count_ul="$(jq -er '.upload.burst.trigger_count // 0 | floor' "$raw_health")"

    ssh -o BatchMode=yes "$ssh_host" \
        "sudo journalctl -u 'wanctl@${wan}' --since '-24h' --no-pager" \
        >"$raw_journal"

    grep -E 'Fusion healer.*->' "$raw_journal" >"$raw_fusion" || true
    fusion_transition_count_24h="$(wc -l <"$raw_fusion" | tr -d ' ')"
    protocol_deprio_count_24h="$(grep -c 'Protocol deprioritization detected' "$raw_journal" || true)"

    jq -n \
        --arg captured_at_iso "$captured_at_iso" \
        --argjson dwell_bypassed_count "$dwell_bypassed_count" \
        --argjson burst_trigger_count_dl "$burst_trigger_count_dl" \
        --argjson burst_trigger_count_ul "$burst_trigger_count_ul" \
        --argjson fusion_transition_count_24h "$fusion_transition_count_24h" \
        --argjson protocol_deprio_count_24h "$protocol_deprio_count_24h" \
        '{
          captured_at_iso: $captured_at_iso,
          dwell_bypassed_count: $dwell_bypassed_count,
          burst_trigger_count_dl: $burst_trigger_count_dl,
          burst_trigger_count_ul: $burst_trigger_count_ul,
          fusion_transition_count_24h: $fusion_transition_count_24h,
          protocol_deprio_count_24h: $protocol_deprio_count_24h
        }' >"$parsed_file"
}

for wan in $WANS; do
    capture_wan "$wan"
done

echo "Phase 192 soak capture ($phase_window) complete: $out_dir"

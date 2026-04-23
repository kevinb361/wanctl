#!/usr/bin/env bash
# Phase 192 soak capture - D-08 three-category evidence.
#
# Operator-run helper only. No timer, deploy, restart, or flent behavior lives here.
# Requires jq, curl, and ssh access to the journal source host(s).
# All deployment-specific values (IPs, hostnames, WAN names) come from env.
# See scripts/phase192-soak-capture.env.example for the required variables.
# Capture "pre" before the merge/deploy that ships Plans 01+02.
# Capture "post" 24h after merge/deploy during a comparable load window if possible.
# This script does not invoke flent; pre-merge flent work is Task 3.

set -euo pipefail

usage() {
    echo "usage: $0 {pre|post}" >&2
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

require_env() {
    local name="$1"
    local description="$2"
    if [[ -z "${!name:-}" ]]; then
        echo "ERROR: ${name} is required (${description})" >&2
        exit 2
    fi
}

count_matches() {
    local pattern="$1"
    local file="$2"
    local count

    count=$(grep -E -c "$pattern" "$file" || true)
    echo "${count:-0}"
}

phase_window="${1:-}"
case "$phase_window" in
    pre|post) ;;
    *)
        usage
        exit 2
        ;;
esac

require_command jq
require_command curl
require_command ssh

require_env WANS "space-separated WAN names, e.g. 'wan_a wan_b'"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
out_dir="$repo_root/.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/soak/$phase_window"
mkdir -p "$out_dir"

capture_at_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
capture_file_stamp="$(date -u +%Y%m%dT%H%M%SZ)"

capture_wan() {
    local wan="$1"
    local upper
    local health_url_var
    local ssh_host_var
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

    upper=$(echo "$wan" | tr '[:lower:]' '[:upper:]')
    health_url_var="WANCTL_${upper}_HEALTH_URL"
    ssh_host_var="WANCTL_${upper}_SSH_HOST"

    require_env "$health_url_var" "health endpoint URL for WAN '$wan'"
    require_env "$ssh_host_var" "SSH target for WAN '$wan' journalctl reads"

    health_url="${!health_url_var}"
    ssh_host="${!ssh_host_var}"

    raw_dir="$out_dir/${wan}-raw"
    mkdir -p "$raw_dir"
    raw_health="$raw_dir/health-${capture_file_stamp}.json"
    raw_journal="$raw_dir/journal-${capture_file_stamp}.log"
    raw_fusion="$raw_dir/fusion-transitions-${capture_file_stamp}.log"
    parsed_file="$out_dir/${wan}.json"

    curl --fail --silent --show-error --max-time 10 "$health_url" >"$raw_health"

    dwell_bypassed_count=$(jq -e -r '.download.hysteresis.dwell_bypassed_count // 0' "$raw_health")
    burst_trigger_count_dl=$(jq -e -r '.download.burst.trigger_count // 0' "$raw_health")
    burst_trigger_count_ul=$(jq -e -r '.upload.burst.trigger_count // 0' "$raw_health")

    ssh "$ssh_host" \
        "sudo journalctl -u wanctl@${wan} --since '-24h' --no-pager" \
        >"$raw_journal"

    grep -E 'Fusion healer.*->' "$raw_journal" >"$raw_fusion" || true
    fusion_transition_count_24h=$(count_matches 'Fusion healer.*->' "$raw_journal")
    protocol_deprio_count_24h=$(count_matches 'Protocol deprioritization detected' "$raw_journal")

    jq -n \
        --arg captured_at_iso "$capture_at_iso" \
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

echo "Phase 192 soak capture (${phase_window}) complete: ${out_dir}"

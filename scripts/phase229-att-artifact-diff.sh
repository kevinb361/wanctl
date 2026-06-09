#!/usr/bin/env bash
#
# Phase 229 DEPLOY-02 ATT artifact diff.
#
# Read-only audit: compares the repo-owned ATT cake-autorate artifacts with
# the live hand-deployed copies on cake-shaper. The remote side is read via
# BatchMode SSH and sudo -n cat only; drift is reported as evidence, not fixed.

set -euo pipefail

SSH_HOST="${SSH_HOST:-cake-shaper}"
if [[ $# -gt 0 ]]; then
    SSH_HOST="$1"
fi

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    fi
}

artifact_sha256() {
    sha256sum "$1" | cut -d' ' -f1
}

live_sha256() {
    local live_path="$1"
    ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat ${live_path}" | sha256sum | cut -d' ' -f1
}

require_command cut
require_command git
require_command sha256sum
require_command ssh

REPO_ROOT="$(git rev-parse --show-toplevel)"

ARTIFACTS=(
    "configs/cake-autorate/config.att.sh|/etc/cake-autorate/config.att.sh"
    "deploy/scripts/cake-autorate-att-qdisc-init|/usr/local/sbin/cake-autorate-att-qdisc-init"
    "deploy/scripts/cake-autorate-att-state-bridge|/usr/local/sbin/cake-autorate-att-state-bridge"
    "deploy/systemd/cake-autorate-att.service|/etc/systemd/system/cake-autorate-att.service"
    "deploy/systemd/cake-autorate-att-state-bridge.service|/etc/systemd/system/cake-autorate-att-state-bridge.service"
    "deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service|/etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service"
)

printf 'artifact\trepo_sha\tlive_sha\tverdict\n'

drift_artifacts=()
unavailable_artifacts=()

for artifact in "${ARTIFACTS[@]}"; do
    repo_path="${artifact%%|*}"
    live_path="${artifact#*|}"
    repo_abs="$REPO_ROOT/$repo_path"

    if [[ ! -f "$repo_abs" ]]; then
        printf '%s\t%s\t%s\t%s\n' "$repo_path" "missing" "-" "unavailable"
        unavailable_artifacts+=("$repo_path")
        continue
    fi

    repo_sha="$(artifact_sha256 "$repo_abs")"
    if live_sha="$(live_sha256 "$live_path" 2>/dev/null)"; then
        if [[ "$live_sha" == "$repo_sha" ]]; then
            verdict="equal"
        else
            verdict="drift"
            drift_artifacts+=("$repo_path")
        fi
    else
        live_sha="unavailable"
        verdict="unavailable"
        unavailable_artifacts+=("$repo_path")
    fi

    printf '%s\t%s\t%s\t%s\n' "$repo_path" "$repo_sha" "$live_sha" "$verdict"
done

if [[ ${#unavailable_artifacts[@]} -gt 0 ]]; then
    printf 'UNAVAILABLE: read-only access to %s is required for: %s\n' \
        "$SSH_HOST" "${unavailable_artifacts[*]}"
    exit 2
fi

if [[ ${#drift_artifacts[@]} -gt 0 ]]; then
    printf 'DRIFT FOUND: %s\n' "${drift_artifacts[*]}"
    exit 3
fi

printf 'ALL EQUAL\n'
exit 0

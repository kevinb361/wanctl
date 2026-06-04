#!/usr/bin/env bash
#
# Phase 226 Spectrum CAKE restore proof wrapper.
#
# This Phase 226 wrapper is dry-run only. It proves config-artifact equality
# and command identity for the Snapshot A restore source without changing git,
# target host state, qdisc state, services, or deployed files.

set -euo pipefail

SNAPSHOT_DIR=""
RAW_DIR=""
SSH_HOST="cake-shaper"
DRY_RUN=false
RESTORE_PROOF_DIR=".planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/restore-proof"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase226-restore.sh --snapshot <dir> --raw-dir <operator-private-dir> --dry-run [options]

Options:
  --snapshot DIR    Snapshot A evidence directory containing MANIFEST.md (required)
  --raw-dir DIR     Operator-private raw artifact directory from phase226-snapshot-a.sh (required)
  --ssh-host HOST   SSH host for read-only deployed-config comparison (default: cake-shaper)
  --dry-run         Required. Print/assert restore proof only; no mutation is available in Phase 226
  --help, -h        Show this help

This proof is intentionally bounded to config-artifact equality and command identity.
It does not claim runtime qdisc restoration, sudo/install permission validity at rollback time,
service-reload behavior, or live qdisc reapplication.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

artifact_sha256() {
    sha256sum "$1" | cut -d' ' -f1
}

manifest_apply_command() {
    local manifest="$1"
    python3 - "$manifest" <<'PY'
import re
import sys

manifest = sys.argv[1]
pattern = re.compile(r"`(ssh [^`]+sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/spectrum\.yaml < <raw-dir>/deployed-spectrum\.yaml)`")
with open(manifest, encoding="utf-8") as fh:
    for line in fh:
        match = pattern.search(line)
        if match:
            print(match.group(1))
            raise SystemExit(0)
raise SystemExit(1)
PY
}

json_escape() {
    python3 - "$1" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1]))
PY
}

write_equivalence_json() {
    local path="$1"
    local raw_source="$2"
    local raw_sha="$3"
    local repo_sha="$4"
    local deployed_sha="$5"
    local verdict="$6"
    local printed_command="$7"
    local manifest_command="$8"
    local command_match="$9"
    local checked_at="${10}"

    {
        printf '{\n'
        printf '  "checked_at": %s,\n' "$(json_escape "$checked_at")"
        printf '  "proof_scope": "config-artifact-equality + command-identity only; no runtime qdisc restoration, sudo/install permission validity, service reload, or live qdisc reapplication claim",\n'
        printf '  "raw_restore_source": %s,\n' "$(json_escape "$raw_source")"
        printf '  "raw_source_sha256": %s,\n' "$(json_escape "$raw_sha")"
        printf '  "repo_spectrum_yaml_sha256": %s,\n' "$(json_escape "$repo_sha")"
        printf '  "deployed_spectrum_yaml_sha256": %s,\n' "$(json_escape "$deployed_sha")"
        printf '  "restore_equivalence": %s,\n' "$(json_escape "$verdict")"
        printf '  "printed_apply_command": %s,\n' "$(json_escape "$printed_command")"
        printf '  "manifest_apply_command": %s,\n' "$(json_escape "$manifest_command")"
        printf '  "apply_command_matches_manifest": %s\n' "$command_match"
        printf '}\n'
    } >"$path"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --snapshot)
            SNAPSHOT_DIR="${2:-}"
            shift 2
            ;;
        --raw-dir)
            RAW_DIR="${2:-}"
            shift 2
            ;;
        --ssh-host)
            SSH_HOST="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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

if [[ -z "$SNAPSHOT_DIR" || -z "$RAW_DIR" ]]; then
    usage >&2
    exit 2
fi

if ! $DRY_RUN; then
    echo "ERROR: Phase 226 restore proof is dry-run only; mutation-capable restore behavior is deferred to Phase 228." >&2
    exit 2
fi

require_command git
require_command python3
require_command sha256sum
require_command ssh

MANIFEST="$SNAPSHOT_DIR/MANIFEST.md"
RAW_CONFIG="$RAW_DIR/deployed-spectrum.yaml"

if [[ ! -d "$SNAPSHOT_DIR" || ! -s "$MANIFEST" ]]; then
    echo "ERROR: --snapshot must contain MANIFEST.md: $SNAPSHOT_DIR" >&2
    exit 1
fi
if [[ ! -s "$RAW_CONFIG" ]]; then
    echo "ERROR: --raw-dir must contain operator-private deployed-spectrum.yaml: $RAW_CONFIG" >&2
    exit 1
fi
if [[ ! -s "configs/spectrum.yaml" ]]; then
    echo "ERROR: missing repo config: configs/spectrum.yaml" >&2
    exit 1
fi

mkdir -p "$RESTORE_PROOF_DIR"

checked_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
raw_sha="$(artifact_sha256 "$RAW_CONFIG")"
repo_sha="$(artifact_sha256 "configs/spectrum.yaml")"
deployed_sha="$(ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/wanctl/spectrum.yaml" | sha256sum | cut -d' ' -f1)"

restore_equivalence="diff"
if [[ "$raw_sha" == "$repo_sha" && "$raw_sha" == "$deployed_sha" ]]; then
    restore_equivalence="equal"
fi

printed_apply_command="ssh $SSH_HOST sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/spectrum.yaml < <raw-dir>/deployed-spectrum.yaml"
manifest_command="$(manifest_apply_command "$MANIFEST")"
command_match=false
if [[ "$printed_apply_command" == "$manifest_command" ]]; then
    command_match=true
fi

transcript="$RESTORE_PROOF_DIR/restore-dry-run.txt"
equivalence_json="$RESTORE_PROOF_DIR/restore-equivalence.json"

{
    printf 'Phase 226 Snapshot A restore dry-run proof\n'
    printf 'Checked UTC: %s\n\n' "$checked_at"
    printf 'Scope: config-artifact-equality + command-identity only.\n'
    printf 'Not claimed: runtime qdisc restoration, sudo/install permission validity at rollback time, service-reload behavior, or live qdisc reapplication.\n\n'
    printf 'Inputs:\n'
    printf -- '- snapshot: %s\n' "$SNAPSHOT_DIR"
    printf -- '- raw_restore_source: %s\n' "$RAW_CONFIG"
    printf -- '- ssh_host: %s\n\n' "$SSH_HOST"
    printf 'SHA256 comparison:\n'
    printf -- '- raw_source_sha256: %s\n' "$raw_sha"
    printf -- '- repo_spectrum_yaml_sha256: %s\n' "$repo_sha"
    printf -- '- deployed_spectrum_yaml_sha256: %s\n' "$deployed_sha"
    printf 'RESTORE_EQUIVALENCE=%s\n\n' "$restore_equivalence"
    printf 'Numbered restore plan (proof text only; not executed):\n'
    printf '1. Confirm the Snapshot A manifest and operator-private raw source are present.\n'
    printf '2. Apply-command text for Phase 228 rollback path: %s\n' "$printed_apply_command"
    printf '3. Verify restored bytes during Phase 228 with a read-only remote sha256 comparison.\n\n'
    printf 'Manifest command identity:\n'
    printf -- '- printed_apply_command: %s\n' "$printed_apply_command"
    printf -- '- manifest_apply_command: %s\n' "$manifest_command"
    printf 'APPLY_COMMAND_MATCHES_MANIFEST=%s\n' "$command_match"
} | tee "$transcript"

write_equivalence_json \
    "$equivalence_json" \
    "$RAW_CONFIG" \
    "$raw_sha" \
    "$repo_sha" \
    "$deployed_sha" \
    "$restore_equivalence" \
    "$printed_apply_command" \
    "$manifest_command" \
    "$command_match" \
    "$checked_at"

if [[ "$restore_equivalence" != "equal" ]]; then
    echo "ERROR: restore source, repo config, and deployed config are not byte-identical" >&2
    exit 1
fi
if [[ "$command_match" != "true" ]]; then
    echo "ERROR: printed apply-command does not match Snapshot A MANIFEST command" >&2
    exit 1
fi

#!/usr/bin/env bash
#
# Phase 226 Spectrum CAKE Snapshot A capture wrapper.
#
# Captures redacted, committable evidence under --output-dir and unredacted
# restore artifacts under an operator-private --raw-dir outside this git tree.
# Snapshot capture is read-only on the target host: sudo -n cat, tc show,
# nft list, and /health only.

set -euo pipefail

SSH_HOST="cake-shaper"
OUTPUT_DIR=""
RAW_DIR=""
HEALTH_URL="http://10.10.110.223:9101/health"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase226-snapshot-a.sh --output-dir <dir> --raw-dir <operator-private-dir> [options]

Options:
  --output-dir DIR   Snapshot A evidence directory to create/write (required)
  --raw-dir DIR      Operator-private raw restore artifact directory (required; outside git tree)
  --ssh-host HOST    SSH host for Spectrum CAKE reads (default: cake-shaper)
  --health-url URL   Spectrum /health URL (default: http://10.10.110.223:9101/health)
  --help, -h         Show this help

Snapshot output:
  Redacted evidence files and MANIFEST.md are written under --output-dir.
  Unredacted restore sources are written mode 0600 under --raw-dir and MUST NOT be committed.

This wrapper captures Spectrum CAKE/qdisc state, configs/spectrum.yaml, bridge qos nft rules,
and Spectrum /health. It does not deploy, restart, change CAKE mode, or mutate target state.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

json_field() {
    local file="$1"
    local field="$2"
    python3 - "$file" "$field" <<'PY'
import json
import sys

path, field = sys.argv[1], sys.argv[2]
try:
    with open(path) as fh:
        data = json.load(fh)
except Exception:
    print("unknown")
    raise SystemExit(0)

value = data
for part in field.split("."):
    if isinstance(value, dict):
        value = value.get(part, "unknown")
    else:
        value = "unknown"
        break
print(value if value is not None else "unknown")
PY
}

redact_yaml() {
    local src="$1"
    local dst="$2"
    python3 - "$src" "$dst" <<'PY'
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
secret_key = re.compile(r"(^\s*[^#\n]*(?:password|token|secret|api[_-]?key)[^:#\n]*:\s*)(.*)$", re.I)
with open(src) as in_fh, open(dst, "w") as out_fh:
    for line in in_fh:
        match = secret_key.match(line)
        if match:
            suffix = ""
            value = match.group(2).rstrip("\n")
            if " #" in value:
                suffix = " #" + value.split(" #", 1)[1]
            out_fh.write(f"{match.group(1)}REDACTED{suffix}\n")
        else:
            out_fh.write(line)
PY
}

real_path() {
    local path="$1"
    python3 - "$path" <<'PY'
import os
import sys

print(os.path.realpath(sys.argv[1]))
PY
}

repo_contains_path() {
    local candidate="$1"
    local repo_root="$2"
    python3 - "$candidate" "$repo_root" <<'PY'
import os
import sys

candidate = os.path.realpath(sys.argv[1])
repo = os.path.realpath(sys.argv[2])
try:
    inside = os.path.commonpath([candidate, repo]) == repo
except ValueError:
    inside = False
raise SystemExit(0 if inside else 1)
PY
}

artifact_sha256() {
    sha256sum "$1" | cut -d' ' -f1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="${2:-}"
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
        --health-url)
            HEALTH_URL="${2:-}"
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

if [[ -z "$OUTPUT_DIR" || -z "$RAW_DIR" ]]; then
    usage >&2
    exit 2
fi

require_command curl
require_command git
require_command python3
require_command sha256sum
require_command ssh

REPO_ROOT="$(real_path "$(git rev-parse --show-toplevel)")"
RAW_DIR_REAL="$(real_path "$RAW_DIR")"
OUTPUT_DIR_REAL="$(real_path "$OUTPUT_DIR")"
if repo_contains_path "$RAW_DIR_REAL" "$REPO_ROOT"; then
    echo "ERROR: --raw-dir must be outside the git working tree: $RAW_DIR_REAL" >&2
    exit 1
fi

if [[ -d "$OUTPUT_DIR_REAL" ]] && [[ -n "$(find "$OUTPUT_DIR_REAL" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: --output-dir already exists and is non-empty: $OUTPUT_DIR_REAL" >&2
    exit 1
fi
if [[ -d "$RAW_DIR_REAL" ]] && [[ -n "$(find "$RAW_DIR_REAL" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: --raw-dir already exists and is non-empty: $RAW_DIR_REAL" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR_REAL" "$RAW_DIR_REAL"
chmod 700 "$RAW_DIR_REAL"

captured_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

raw_config="$RAW_DIR_REAL/deployed-spectrum.yaml"
raw_config_source="$RAW_DIR_REAL/deployed-spectrum.source-path.txt"

ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/wanctl/spectrum.yaml" >"$raw_config"
chmod 600 "$raw_config"
printf '%s\n' '/etc/wanctl/spectrum.yaml' >"$raw_config_source"
chmod 600 "$raw_config_source"

deployed_redacted="$OUTPUT_DIR_REAL/deployed-spectrum.redacted.yaml"
repo_redacted="$OUTPUT_DIR_REAL/repo-spectrum.redacted.yaml"
redact_yaml "$raw_config" "$deployed_redacted"
redact_yaml "configs/spectrum.yaml" "$repo_redacted"

ssh -o BatchMode=yes "$SSH_HOST" "sudo -n tc -s qdisc show dev spec-router" >"$OUTPUT_DIR_REAL/tc-qdisc-spec-router.txt"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n tc -s qdisc show dev spec-modem" >"$OUTPUT_DIR_REAL/tc-qdisc-spec-modem.txt"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n nft list table bridge qos" >"$OUTPUT_DIR_REAL/bridge-qos.live.txt"
cp deploy/nftables/bridge-qos.nft "$OUTPUT_DIR_REAL/repo-bridge-qos.nft"

commit_sha="$(git rev-parse HEAD)"
spectrum_blob_sha="$(git rev-parse HEAD:configs/spectrum.yaml)"
configs_tree_sha="$(git rev-parse HEAD:configs)"
{
    printf 'commit_sha=%s\n' "$commit_sha"
    printf 'tree_sha_configs=%s\n' "$configs_tree_sha"
    printf 'blob_sha_configs_spectrum_yaml=%s\n' "$spectrum_blob_sha"
} >"$OUTPUT_DIR_REAL/pre-deploy-git-ref.txt"

curl -fsS --connect-timeout 3 --max-time 5 "$HEALTH_URL" >"$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json"

repo_init_version="$(python3 - <<'PY'
import re
with open('src/wanctl/__init__.py') as fh:
    text = fh.read()
match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", text)
print(match.group(1) if match else 'unknown')
PY
)"
repo_pyproject_version="$(python3 - <<'PY'
import re
with open('pyproject.toml') as fh:
    for line in fh:
        match = re.match(r"version\s*=\s*['\"]([^'\"]+)['\"]", line)
        if match:
            print(match.group(1))
            raise SystemExit(0)
print('unknown')
PY
)"
{
    printf '__version__=%s\n' "$repo_init_version"
    printf 'pyproject_version=%s\n' "$repo_pyproject_version"
} >"$OUTPUT_DIR_REAL/repo-version.txt"

bound_version="$(json_field "$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json" version)"
bound_status="$(json_field "$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json" status)"
bound_uptime="$(json_field "$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json" uptime_seconds)"
deployed_sha="$(artifact_sha256 "$deployed_redacted")"
repo_sha="$(artifact_sha256 "$repo_redacted")"
raw_config_sha="$(artifact_sha256 "$raw_config")"
config_equality="diff"
if [[ "$deployed_sha" == "$repo_sha" ]]; then
    config_equality="equal"
fi

sha_file="$OUTPUT_DIR_REAL/artifact-sha256.txt"
{
    sha256sum \
        "$deployed_redacted" \
        "$repo_redacted" \
        "$OUTPUT_DIR_REAL/tc-qdisc-spec-router.txt" \
        "$OUTPUT_DIR_REAL/tc-qdisc-spec-modem.txt" \
        "$OUTPUT_DIR_REAL/bridge-qos.live.txt" \
        "$OUTPUT_DIR_REAL/repo-bridge-qos.nft" \
        "$OUTPUT_DIR_REAL/pre-deploy-git-ref.txt" \
        "$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json" \
        "$OUTPUT_DIR_REAL/repo-version.txt"
    printf '%s  %s\n' "$raw_config_sha" "$raw_config"
    sha256sum "$raw_config_source"
} >"$sha_file"

manifest="$OUTPUT_DIR_REAL/MANIFEST.md"
{
    printf '# Snapshot A Manifest\n\n'
    printf '## Captured UTC\n\n'
    printf -- '- Captured: %s\n\n' "$captured_ts"
    printf '## Source Posture\n\n'
    printf 'read-only; no deploy, restart, CAKE-mode change, traffic generation, nft mutation, tc mutation, /etc/wanctl write, or production write was performed.\n\n'
    printf '## Health Source URL\n\n'
    printf -- '- Spectrum health URL: %s\n\n' "$HEALTH_URL"
    printf '## Deployed Version\n\n'
    printf -- '- Spectrum /health version: %s\n' "$bound_version"
    printf -- '- Spectrum /health status: %s\n' "$bound_status"
    printf -- '- Health uptime_seconds: %s\n\n' "$bound_uptime"
    printf '## Repo Version\n\n'
    printf -- '- __version__: %s\n' "$repo_init_version"
    printf -- '- pyproject.toml version: %s\n\n' "$repo_pyproject_version"
    printf '## Pre-Deploy Git Ref\n\n'
    printf -- '- commit_sha: %s\n' "$commit_sha"
    printf -- '- tree_sha_configs: %s\n' "$configs_tree_sha"
    printf -- '- blob_sha_configs_spectrum_yaml: %s\n\n' "$spectrum_blob_sha"
    printf '## Deployed Config Equality\n\n'
    printf -- '- deployed_redacted_sha256: %s\n' "$deployed_sha"
    printf -- '- repo_redacted_sha256: %s\n' "$repo_sha"
    printf -- '- raw_deployed_spectrum_sha256: %s\n' "$raw_config_sha"
    printf -- '- verdict: %s\n\n' "$config_equality"
    printf '## Raw Artifact Restore Path\n\n'
    printf -- '- raw_dir: %s\n' "$RAW_DIR_REAL"
    printf -- '- raw_restore_source: %s/deployed-spectrum.yaml\n' "$RAW_DIR_REAL"
    printf -- '- restore_destination: /etc/wanctl/spectrum.yaml\n'
    printf -- '- operator_private: true\n'
    printf -- '- committed: false\n\n'
    printf '## Artifacts\n\n'
    printf -- '- repo-spectrum.redacted.yaml — redacted repo configs/spectrum.yaml.\n'
    printf -- '- deployed-spectrum.redacted.yaml — redacted deployed /etc/wanctl/spectrum.yaml.\n'
    printf -- '- tc-qdisc-spec-router.txt — read-only sudo tc -s qdisc show dev spec-router.\n'
    printf -- '- tc-qdisc-spec-modem.txt — read-only sudo tc -s qdisc show dev spec-modem.\n'
    printf -- '- bridge-qos.live.txt — read-only sudo nft list table bridge qos.\n'
    printf -- '- repo-bridge-qos.nft — repo deploy/nftables/bridge-qos.nft copy.\n'
    printf -- '- pre-deploy-git-ref.txt — commit, configs tree, and configs/spectrum.yaml blob SHA.\n'
    printf -- '- snapshot-a-health.bound.redacted.json — Spectrum /health baseline.\n'
    printf -- '- repo-version.txt — repo version fields.\n'
    printf -- '- artifact-sha256.txt — sha256 inventory for redacted evidence and operator-private raw restore sources.\n'
    printf -- '- %s/deployed-spectrum.yaml — unredacted raw restore source, operator-private.\n' "$RAW_DIR_REAL"
    printf -- '- %s/deployed-spectrum.source-path.txt — restore destination marker, operator-private.\n\n' "$RAW_DIR_REAL"
    printf '## Artifact SHA256\n\n'
    while IFS= read -r line; do
        printf -- '- %s\n' "$line"
    done <"$sha_file"
    printf '\n## Targeted Revert Sequence\n\n'
    printf 'Scope note: this manifest proves config-artifact equality and command identity only. It does not claim runtime qdisc restoration, sudo/install permission validity at rollback time, or service-reload behavior; those require a live drill out of scope for Phase 226.\n\n'
    printf "1. Confirm local checkout is at the intended rollback context: \`git checkout %s\`.\n" "$commit_sha"
    printf "2. Restore \`<raw-dir>/deployed-spectrum.yaml\` to \`/etc/wanctl/spectrum.yaml\`: \`ssh %s sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/spectrum.yaml < <raw-dir>/deployed-spectrum.yaml\`.\n" "$SSH_HOST"
    printf '3. Verify restored config bytes during Phase 228 rollback proof with a read-only remote sha256 comparison.\n'
} >"$manifest"

for required in \
    "$deployed_redacted" \
    "$repo_redacted" \
    "$OUTPUT_DIR_REAL/tc-qdisc-spec-router.txt" \
    "$OUTPUT_DIR_REAL/tc-qdisc-spec-modem.txt" \
    "$OUTPUT_DIR_REAL/bridge-qos.live.txt" \
    "$OUTPUT_DIR_REAL/repo-bridge-qos.nft" \
    "$OUTPUT_DIR_REAL/pre-deploy-git-ref.txt" \
    "$OUTPUT_DIR_REAL/snapshot-a-health.bound.redacted.json" \
    "$OUTPUT_DIR_REAL/repo-version.txt" \
    "$sha_file" \
    "$manifest" \
    "$raw_config" \
    "$raw_config_source"; do
    if [[ ! -s "$required" ]]; then
        echo "ERROR: required artifact missing or empty: $required" >&2
        exit 1
    fi
done

echo "Snapshot A captured: $OUTPUT_DIR_REAL"
echo "Raw restore artifacts captured outside git tree: $RAW_DIR_REAL"

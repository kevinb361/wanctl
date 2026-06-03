#!/usr/bin/env bash
#
# Phase 224 Snapshot A capture wrapper.
#
# Captures redacted, committable evidence under --output-dir and unredacted
# restore artifacts under an operator-private --raw-dir outside this git tree.
# Snapshot capture is read-only on the target host: sudo -n cat and /health only.

set -euo pipefail

SSH_HOST="cake-shaper"
OUTPUT_DIR=""
RAW_DIR=""
HEALTH_URL="http://10.10.110.223:9101/health"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase224-snapshot-a.sh --output-dir <dir> --raw-dir <operator-private-dir> [options]

Options:
  --output-dir DIR   Snapshot A evidence directory to create/write (required)
  --raw-dir DIR      Operator-private raw restore artifact directory (required; outside git tree)
  --ssh-host HOST    SSH host for steering daemon reads (default: cake-shaper)
  --health-url URL   Bound autorate /health URL (default: http://10.10.110.223:9101/health)
  --help, -h         Show this help

Snapshot output:
  Redacted evidence files and MANIFEST.md are written under --output-dir.
  Unredacted restore sources are written mode 0600 under --raw-dir and MUST NOT be committed.

This wrapper delegates steering /health + redacted state capture to
scripts/phase213-steering-snapshot.sh and does not deploy, restart, or mutate target state.
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
secret_key = re.compile(r"(^\s*[^#\n]*(?:password|token|secret)[^:#\n]*:\s*)(.*)$", re.I)
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

read_state_file_from_yaml() {
    local yaml_file="$1"
    python3 - "$yaml_file" <<'PY'
import re
import sys

path = sys.argv[1]
in_state = False
state_indent = None
with open(path) as fh:
    for raw in fh:
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if re.match(r"^\s*state\s*:\s*(?:#.*)?$", line):
            in_state = True
            state_indent = indent
            continue
        if in_state and indent <= (state_indent or 0):
            in_state = False
        if in_state:
            match = re.match(r"^\s*file\s*:\s*['\"]?([^'\"#]+?)['\"]?\s*(?:#.*)?$", line)
            if match:
                print(match.group(1).strip())
                raise SystemExit(0)
print("/var/lib/wanctl/steering_state.json")
PY
}

repo_contains_path() {
    local candidate="$1"
    local repo_root="$2"
    python3 - "$candidate" "$repo_root" <<'PY'
import os
import sys

candidate = os.path.abspath(sys.argv[1])
repo = os.path.abspath(sys.argv[2])
try:
    inside = os.path.commonpath([candidate, repo]) == repo
except ValueError:
    inside = False
raise SystemExit(0 if inside else 1)
PY
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

REPO_ROOT="$(git rev-parse --show-toplevel)"
if repo_contains_path "$RAW_DIR" "$REPO_ROOT"; then
    echo "ERROR: --raw-dir must be outside the git working tree: $RAW_DIR" >&2
    exit 1
fi

if [[ -d "$OUTPUT_DIR" ]] && [[ -n "$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: --output-dir already exists and is non-empty: $OUTPUT_DIR" >&2
    exit 1
fi
if [[ -d "$RAW_DIR" ]] && [[ -n "$(find "$RAW_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: --raw-dir already exists and is non-empty: $RAW_DIR" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR" "$RAW_DIR"
chmod 700 "$RAW_DIR"

captured_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

scripts/phase213-steering-snapshot.sh --output "$OUTPUT_DIR/steering" --ssh-host "$SSH_HOST"

raw_config="$RAW_DIR/deployed-steering.yaml"
raw_state="$RAW_DIR/deployed-steering-state.json"
state_source="$RAW_DIR/deployed-steering-state.source-path.txt"

ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/wanctl/steering.yaml" >"$raw_config"
chmod 600 "$raw_config"

state_file="$(read_state_file_from_yaml "$raw_config")"
printf '%s\n' "$state_file" >"$state_source"
chmod 600 "$state_source"

ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat '$state_file'" >"$raw_state"
chmod 600 "$raw_state"

deployed_redacted="$OUTPUT_DIR/deployed-steering.redacted.yaml"
repo_redacted="$OUTPUT_DIR/repo-steering.redacted.yaml"
redact_yaml "$raw_config" "$deployed_redacted"
redact_yaml "configs/steering.yaml" "$repo_redacted"

commit_sha="$(git rev-parse HEAD)"
tree_sha="$(git rev-parse HEAD:src/wanctl)"
{
    printf 'commit_sha=%s\n' "$commit_sha"
    printf 'tree_sha_src_wanctl=%s\n' "$tree_sha"
} >"$OUTPUT_DIR/pre-deploy-git-ref.txt"

curl -fsS --connect-timeout 3 --max-time 5 "$HEALTH_URL" >"$OUTPUT_DIR/snapshot-a-health.bound.redacted.json"
ssh -o BatchMode=yes "$SSH_HOST" "curl -fsS --max-time 3 http://127.0.0.1:9102/health" \
    >"$OUTPUT_DIR/snapshot-a-health.steering.redacted.json"

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
} >"$OUTPUT_DIR/repo-version.txt"

bound_version="$(json_field "$OUTPUT_DIR/snapshot-a-health.bound.redacted.json" version)"
steering_version="$(json_field "$OUTPUT_DIR/snapshot-a-health.steering.redacted.json" version)"
bound_uptime="$(json_field "$OUTPUT_DIR/snapshot-a-health.bound.redacted.json" uptime_seconds)"
deployed_sha="$(sha256sum "$deployed_redacted" | cut -d' ' -f1)"
repo_sha="$(sha256sum "$repo_redacted" | cut -d' ' -f1)"
state_sha="$(sha256sum "$raw_state" | cut -d' ' -f1)"
config_equality="diff"
if [[ "$deployed_sha" == "$repo_sha" ]]; then
    config_equality="equal"
fi

manifest="$OUTPUT_DIR/MANIFEST.md"
{
    printf '# Snapshot A Manifest\n\n'
    printf '## Captured\n\n'
    printf -- '- Captured: %s\n' "$captured_ts"
    printf -- '- Source posture: read-only; no deploy, restart, mutation, traffic generation, or production write was performed.\n\n'
    printf '## Source Posture\n\n'
    printf 'Read-only; no deploy, restart, mutation, traffic generation, or production write was performed.\n\n'
    printf '## Health Source URL\n\n'
    printf -- '- Bound health URL: %s\n' "$HEALTH_URL"
    printf -- '- Steering loopback URL via SSH: http://127.0.0.1:9102/health\n\n'
    printf '## Deployed Version\n\n'
    printf -- '- Bound /health version: %s\n' "$bound_version"
    printf -- '- Steering /health version: %s\n' "$steering_version"
    printf -- '- Health uptime_seconds: %s\n\n' "$bound_uptime"
    printf '## Repo Version\n\n'
    printf -- '- __version__: %s\n' "$repo_init_version"
    printf -- '- pyproject.toml version: %s\n\n' "$repo_pyproject_version"
    printf '## Pre-Deploy Git Ref\n\n'
    printf -- '- commit_sha: %s\n' "$commit_sha"
    printf -- '- tree_sha_src_wanctl: %s\n\n' "$tree_sha"
    printf '## Deployed Config Equality\n\n'
    printf -- '- deployed_redacted_sha256: %s\n' "$deployed_sha"
    printf -- '- repo_redacted_sha256: %s\n' "$repo_sha"
    printf -- '- verdict: %s\n\n' "$config_equality"
    printf '## Persisted State Summary\n\n'
    printf -- '- state.file: %s\n' "$state_file"
    printf -- '- state_sha256: %s\n\n' "$state_sha"
    printf '## Raw Artifact Restore Path\n\n'
    printf -- '- raw_dir: %s\n' "$RAW_DIR"
    printf -- '- operator_private: true\n'
    printf -- '- committed: false\n\n'
    printf '## Steering State Source Path\n\n'
    printf -- '- %s\n\n' "$state_file"
    printf '## Artifacts\n\n'
    printf -- '- steering-health.json — delegated steering /health capture from phase213-steering-snapshot.sh.\n'
    printf -- '- steering-state.redacted.json — delegated redacted steering state evidence from phase213-steering-snapshot.sh.\n'
    printf -- '- deployed-steering.redacted.yaml — redacted deployed /etc/wanctl/steering.yaml.\n'
    printf -- '- repo-steering.redacted.yaml — redacted repo configs/steering.yaml.\n'
    printf -- '- pre-deploy-git-ref.txt — commit and src/wanctl tree SHA.\n'
    printf -- '- snapshot-a-health.bound.redacted.json — bound /health baseline.\n'
    printf -- '- snapshot-a-health.steering.redacted.json — steering loopback /health baseline.\n'
    printf -- '- repo-version.txt — repo version fields.\n'
    printf -- '- %s/deployed-steering.yaml — unredacted raw restore source, operator-private.\n' "$RAW_DIR"
    printf -- '- %s/deployed-steering-state.json — unredacted state restore source, operator-private.\n' "$RAW_DIR"
    printf -- '- %s/deployed-steering-state.source-path.txt — captured state.file restore destination, operator-private.\n\n' "$RAW_DIR"
    printf '## Targeted Revert Sequence\n\n'
    printf "1. \`git checkout %s\` locally.\n" "$commit_sha"
    printf "2. Run \`scripts/deploy.sh <wan_name> %s --with-steering\` against the checked-out pre-deploy ref.\n" "$SSH_HOST"
    printf "3. Restore \`<raw-dir>/deployed-steering.yaml\` to \`/etc/wanctl/steering.yaml\`: \`ssh %s sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/steering.yaml < <raw-dir>/deployed-steering.yaml\`.\n" "$SSH_HOST"
    printf "4. Restore \`<raw-dir>/deployed-steering-state.json\` to the exact captured \`state.file\` path from \`<raw-dir>/deployed-steering-state.source-path.txt\` (\`%s\`): \`ssh %s sudo -n install -m 0640 -o wanctl -g wanctl /dev/stdin %s < <raw-dir>/deployed-steering-state.json\`.\n" "$state_file" "$SSH_HOST" "$state_file"
    printf '5. `ssh %s '\''sudo systemctl restart steering.service'\''`.\n' "$SSH_HOST"
    printf "6. Run \`scripts/canary-check.sh --ssh kevin@%s --expect-version %s --json\` and \`ssh kevin@%s curl -s http://127.0.0.1:9102/health\` for post-revert /health proof.\n" "$SSH_HOST" "$bound_version" "$SSH_HOST"
} >"$manifest"

for required in \
    "$OUTPUT_DIR/steering-health.json" \
    "$OUTPUT_DIR/steering-state.redacted.json" \
    "$deployed_redacted" \
    "$repo_redacted" \
    "$OUTPUT_DIR/pre-deploy-git-ref.txt" \
    "$OUTPUT_DIR/snapshot-a-health.bound.redacted.json" \
    "$OUTPUT_DIR/snapshot-a-health.steering.redacted.json" \
    "$OUTPUT_DIR/repo-version.txt" \
    "$manifest" \
    "$raw_config" \
    "$raw_state" \
    "$state_source"; do
    if [[ ! -s "$required" ]]; then
        echo "ERROR: required artifact missing or empty: $required" >&2
        exit 1
    fi
done

echo "Snapshot A captured: $OUTPUT_DIR"
echo "Raw restore artifacts captured outside git tree: $RAW_DIR"

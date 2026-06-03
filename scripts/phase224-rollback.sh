#!/usr/bin/env bash
#
# Phase 224 targeted rollback wrapper for Snapshot A artifacts.
#
# Consumes redacted Snapshot A evidence plus unredacted operator-private raw
# restore artifacts. By default this script mutates the local git checkout and
# target host; use --dry-run to print the numbered plan without mutation.

set -euo pipefail

SNAPSHOT_DIR=""
RAW_DIR=""
SSH_HOST="cake-shaper"
TARGET_WAN="spectrum"
HEALTH_URL=""
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage:
  scripts/phase224-rollback.sh --snapshot <dir> --raw-dir <operator-private-dir> [options]

Options:
  --snapshot DIR    Snapshot A evidence directory containing MANIFEST.md (required)
  --raw-dir DIR     Operator-private raw artifact directory from phase224-snapshot-a.sh (required)
  --ssh-host HOST   SSH host to restore/restart (default: cake-shaper)
  --target-wan WAN  WAN name passed to deploy.sh (default: spectrum)
  --health-url URL  Bound health URL for post-revert context (default: manifest Bound health URL)
  --dry-run         Print numbered rollback sequence but do not mutate git or target host
  --help, -h        Show this help

WARNING:
  Non-dry-run rollback mutates the local git checkout with `git checkout <pre-deploy-sha>`
  before invoking scripts/deploy.sh. Start from a clean worktree.

The rollback requires unredacted raw artifacts; redacted Snapshot A YAML is evidence only
and is never used as a restore source.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

manifest_value() {
    local label="$1"
    local manifest="$2"
    python3 - "$label" "$manifest" <<'PY'
import re
import sys

label, path = sys.argv[1], sys.argv[2]
patterns = [
    re.compile(rf"^\s*-\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.I),
    re.compile(rf"^\s*{re.escape(label)}\s*=\s*(.+?)\s*$", re.I),
]
with open(path) as fh:
    for raw in fh:
        line = raw.rstrip("\n")
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                print(match.group(1).strip().strip('`'))
                raise SystemExit(0)
raise SystemExit(1)
PY
}

artifact_sha256() {
    sha256sum "$1" | cut -d' ' -f1
}

remote_sha256() {
    local path="$1"
    ssh -o BatchMode=yes "$SSH_HOST" "sudo -n sha256sum '$path'" | cut -d' ' -f1
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
        --target-wan)
            TARGET_WAN="${2:-}"
            shift 2
            ;;
        --health-url)
            HEALTH_URL="${2:-}"
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

require_command git
require_command python3
require_command sha256sum
require_command ssh
require_command jq

MANIFEST="$SNAPSHOT_DIR/MANIFEST.md"
if [[ ! -d "$SNAPSHOT_DIR" || ! -s "$MANIFEST" ]]; then
    echo "ERROR: --snapshot must contain MANIFEST.md: $SNAPSHOT_DIR" >&2
    exit 1
fi

RAW_CONFIG="$RAW_DIR/deployed-steering.yaml"
RAW_STATE="$RAW_DIR/deployed-steering-state.json"
RAW_STATE_SOURCE="$RAW_DIR/deployed-steering-state.source-path.txt"

if [[ ! -s "$RAW_CONFIG" ]]; then
    echo "ERROR: rollback requires unredacted raw artifacts; --raw-dir must point to the operator-private path used by phase224-snapshot-a.sh --raw-dir at capture time." >&2
    exit 1
fi
if [[ ! -s "$RAW_STATE" ]]; then
    echo "ERROR: missing required raw artifact: $RAW_STATE" >&2
    exit 1
fi
if [[ ! -s "$RAW_STATE_SOURCE" ]]; then
    echo "ERROR: missing required raw artifact: $RAW_STATE_SOURCE" >&2
    exit 1
fi

STATE_DEST="$(<"$RAW_STATE_SOURCE")"
if ! [[ "$STATE_DEST" =~ ^/var/lib/wanctl/[A-Za-z0-9_.-]+\.json$ ]]; then
    echo "ERROR: invalid steering state destination path from source-path file: $STATE_DEST" >&2
    exit 1
fi

PRE_DEPLOY_COMMIT="$(manifest_value commit_sha "$MANIFEST")"
PRE_DEPLOY_VERSION="$(manifest_value "__version__" "$MANIFEST")"
DEPLOYED_VERSION="$(manifest_value "Bound /health version" "$MANIFEST")"
if [[ -z "$PRE_DEPLOY_COMMIT" || -z "$PRE_DEPLOY_VERSION" || -z "$DEPLOYED_VERSION" ]]; then
    echo "ERROR: MANIFEST.md missing Pre-Deploy Git Ref, Repo Version, or Deployed Version fields" >&2
    exit 1
fi
if [[ -z "$HEALTH_URL" ]]; then
    HEALTH_URL="$(manifest_value "Bound health URL" "$MANIFEST" || true)"
fi
if [[ -z "$HEALTH_URL" ]]; then
    HEALTH_URL="http://10.10.110.223:9101/health"
fi

CONFIG_SHA="$(artifact_sha256 "$RAW_CONFIG")"
STATE_SHA="$(artifact_sha256 "$RAW_STATE")"

print_plan() {
    {
        echo "Rollback plan:"
        echo "1. git checkout $PRE_DEPLOY_COMMIT"
        echo "2. scripts/deploy.sh $TARGET_WAN $SSH_HOST --with-steering"
        echo "3. restore $RAW_CONFIG to /etc/wanctl/steering.yaml and verify sha256=$CONFIG_SHA"
        echo "4. restore $RAW_STATE to $STATE_DEST and verify sha256=$STATE_SHA"
        echo "5. ssh $SSH_HOST 'sudo systemctl restart steering.service'"
        echo "6. scripts/canary-check.sh --ssh kevin@$SSH_HOST --expect-version $PRE_DEPLOY_VERSION --json"
        echo "7. capture steering loopback /health to $SNAPSHOT_DIR/post-revert-health.steering.json"
        echo "Context: manifest deployed_version=$DEPLOYED_VERSION health_url=$HEALTH_URL"
    } >&2
}

print_plan
if $DRY_RUN; then
    exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR: worktree must be clean before rollback mutates local git ref" >&2
    exit 1
fi

SECONDS=0
git checkout "$PRE_DEPLOY_COMMIT"
scripts/deploy.sh "$TARGET_WAN" "$SSH_HOST" --with-steering

ssh -o BatchMode=yes "$SSH_HOST" \
    "sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/steering.yaml" \
    <"$RAW_CONFIG"
remote_config_sha="$(remote_sha256 /etc/wanctl/steering.yaml)"
if [[ "$remote_config_sha" != "$CONFIG_SHA" ]]; then
    echo "ERROR: restored steering.yaml sha256 mismatch: remote=$remote_config_sha source=$CONFIG_SHA" >&2
    exit 1
fi

ssh -o BatchMode=yes "$SSH_HOST" \
    "sudo -n install -m 0640 -o wanctl -g wanctl /dev/stdin '$STATE_DEST'" \
    <"$RAW_STATE"
remote_state_sha="$(remote_sha256 "$STATE_DEST")"
if [[ "$remote_state_sha" != "$STATE_SHA" ]]; then
    echo "ERROR: restored steering state sha256 mismatch: remote=$remote_state_sha source=$STATE_SHA" >&2
    echo "Refusing to restart steering.service after state restore mismatch" >&2
    exit 1
fi

ssh -o BatchMode=yes "$SSH_HOST" 'sudo systemctl restart steering.service'

restart_start="$SECONDS"
while true; do
    status="$(ssh -o BatchMode=yes "$SSH_HOST" "curl -s --max-time 3 http://127.0.0.1:9102/health | jq -r '.status // \"unknown\"'" || true)"
    if [[ "$status" == "healthy" ]]; then
        break
    fi
    if (( SECONDS - restart_start >= 30 )); then
        echo "ERROR: steering.service did not report healthy within 30 seconds (last status=$status)" >&2
        exit 1
    fi
    sleep 1
done

scripts/canary-check.sh --ssh "kevin@$SSH_HOST" --expect-version "$PRE_DEPLOY_VERSION" --json
ssh -o BatchMode=yes "kevin@$SSH_HOST" "curl -s http://127.0.0.1:9102/health" \
    >"$SNAPSHOT_DIR/post-revert-health.steering.json"

echo "ROLLBACK_DURATION_SECONDS=$SECONDS"

#!/usr/bin/env bash
#
# Phase 213 steering snapshot helper.
#
# Evidence-only D-08/D-09/D-10 helper for pre/post steering capture. It reads
# steering /health over loopback on cake-shaper and reads persisted state via
# sudo -n cat, then writes only the redacted state artifact under evidence.
# HIGH-2 design: raw state lives only in a /tmp mktemp file for this process
# lifetime; the EXIT trap removes it on success, failure, or signal. D-14:
# threshold field names from v1.39 are captured verbatim by JSON, not compared.

set -euo pipefail

OUTPUT=""
SSH_HOST="cake-shaper"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase213-steering-snapshot.sh --output <prefix> [--ssh-host cake-shaper]

Output:
  <prefix>-health.json
  <prefix>-state.redacted.json

No raw state artifact is written under the output directory.
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
        --output)
            OUTPUT="${2:-}"
            shift 2
            ;;
        --ssh-host)
            SSH_HOST="${2:-}"
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

if [[ -z "$OUTPUT" ]]; then
    usage >&2
    exit 2
fi

require_command ssh
require_command python3

ts_utc="$(date -u -Iseconds)"
mkdir -p "$(dirname "$OUTPUT")"
RAW_TMP="$(mktemp -t phase213-steering-raw.XXXXXX)"
trap 'rm -f "$RAW_TMP"' EXIT INT TERM

ssh -o BatchMode=yes "$SSH_HOST" \
    "curl -fsS --max-time 3 http://127.0.0.1:9102/health" \
    >"${OUTPUT}-health.json"

ssh -o BatchMode=yes "$SSH_HOST" \
    "sudo -n cat /var/lib/wanctl/steering_state.json" \
    >"$RAW_TMP"

python3 - "$RAW_TMP" "${OUTPUT}-state.redacted.json" <<'PY'
import json
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
PAT = re.compile(r"(password|secret|token|credential|auth|key|private)", re.I)


def redact(value):
    if isinstance(value, dict):
        return {key: ("<REDACTED>" if PAT.search(key) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


with open(src) as f:
    data = json.load(f)

with open(dst, "w") as f:
    json.dump(redact(data), f, indent=2, sort_keys=True)
    f.write("\n")
PY

# /health and state.json are sequential reads, not atomic. The expected ~100ms
# gap is acceptable for pre/post bracketing at test-duration granularity.
echo "${ts_utc} ${OUTPUT}-health.json ${OUTPUT}-state.redacted.json" >>"${OUTPUT%/*}/.snapshot-log"

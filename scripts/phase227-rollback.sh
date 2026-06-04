#!/usr/bin/env bash
# Phase 227 D-09 genuine mutation-capable rollback to Snapshot A besteffort.

set -euo pipefail

RAW_DIR=""
SSH_HOST="cake-shaper"
HEALTH_URL="http://10.10.110.223:9101/health"
OUT_FILE=".planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/evidence/rollback-proof.json"
DRY_RUN="0"
CONFIRM="0"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase227-rollback.sh --raw-dir <operator-private-dir> [options]

Options:
  --raw-dir DIR     Required; contains Snapshot A deployed-spectrum.yaml besteffort bytes
  --ssh-host HOST   Deployment/restart target (default: cake-shaper)
  --health-url URL  Spectrum health endpoint (default: http://10.10.110.223:9101/health)
  --out FILE        Rollback proof JSON path
  --dry-run         Print ordered rollback plan and commands; mutate nothing
  --confirm         Required for real mutation
  --help, -h        Show this help
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 1
    fi
}

json_string() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

sha256_file() {
    sha256sum "$1" | cut -d' ' -f1
}

print_plan() {
    cat <<EOF
Phase 227 D-09 rollback plan (genuine mutation only with --confirm):
  1. Assert ${RAW_DIR:-<raw-dir>}/deployed-spectrum.yaml exists and contains diffserv: besteffort.
  2. Copy Snapshot A besteffort bytes to configs/spectrum.yaml.
  3. Run standard deploy path: scripts/deploy.sh spectrum ${SSH_HOST}
  4. Restart: ssh ${SSH_HOST} 'sudo systemctl restart wanctl@spectrum.service'
  5. Verify besteffort on both NICs: scripts/phase227-qdisc-verify.sh --expected-mode besteffort
  6. Check health: ${HEALTH_URL} status == healthy
  7. Record rollback proof JSON: ${OUT_FILE}

Rollback is implemented directly here; no dry-run proof wrapper is delegated.
EOF
}

health_check() {
    python3 - "$HEALTH_URL" <<'PY'
import json
import sys
from urllib.request import urlopen

url = sys.argv[1]
try:
    with urlopen(url, timeout=3) as fh:
        payload = json.load(fh)
except Exception as exc:
    raise SystemExit(f"HEALTH FAIL: {url}: {exc}")
status = payload.get("status") if isinstance(payload, dict) else None
if status != "healthy":
    raise SystemExit(f"HEALTH FAIL: status={status!r} expected 'healthy'")
print("healthy")
PY
}

nrestarts() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" \
        "systemctl show -p NRestarts --value wanctl@spectrum.service"
}

service_active() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "systemctl is-active wanctl@spectrum.service"
}

journal_excerpt_json() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" \
        "journalctl -u wanctl@spectrum.service -n 20 --no-pager 2>/dev/null" \
        | python3 -c 'import json, sys; print(json.dumps(sys.stdin.read()))'
}

write_proof() {
    local rolled_back_utc="$1"
    local raw_sha="$2"
    local deployed_sha="$3"
    local qdisc_json="$4"
    local active="$5"
    local before="$6"
    local after="$7"
    local journal_json="$8"
    mkdir -p "$(dirname "$OUT_FILE")"
    python3 - "$OUT_FILE" "$rolled_back_utc" "$RAW_DIR" "$raw_sha" "$deployed_sha" "$qdisc_json" "$active" "$before" "$after" "$journal_json" <<'PY'
import json
import sys
from pathlib import Path

out, rolled_back_utc, raw_dir, raw_sha, deployed_sha, qdisc_path, active, before, after, journal_json = sys.argv[1:]
qdisc_verify = None
try:
    qdisc_verify = json.loads(Path(qdisc_path).read_text(encoding="utf-8"))
except Exception as exc:
    qdisc_verify = {"error": f"unreadable qdisc proof: {exc}"}
payload = {
    "rolled_back_utc": rolled_back_utc,
    "raw_dir": raw_dir,
    "raw_dir_sha256": raw_sha,
    "deployed_config_sha256": deployed_sha,
    "qdisc_verify": qdisc_verify,
    "systemctl_is_active": active,
    "nrestarts_before": before,
    "nrestarts_after": after,
    "journal_excerpt": json.loads(journal_json),
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --raw-dir) RAW_DIR="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --health-url) HEALTH_URL="${2:-}"; shift 2 ;;
        --out) OUT_FILE="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN="1"; shift ;;
        --confirm) CONFIRM="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$RAW_DIR" ]]; then
    usage >&2
    exit 2
fi

if [[ "$DRY_RUN" == "1" ]]; then
    print_plan
    exit 0
fi

if [[ "$CONFIRM" != "1" ]]; then
    echo "REFUSED: rollback mutates production/repo config; rerun with --confirm after operator approval." >&2
    print_plan >&2
    exit 2
fi

require_command python3
require_command sha256sum
require_command ssh

RAW_CONFIG="$RAW_DIR/deployed-spectrum.yaml"
if [[ ! -s "$RAW_CONFIG" ]]; then
    echo "ERROR: --raw-dir must contain deployed-spectrum.yaml: $RAW_CONFIG" >&2
    exit 1
fi
if ! grep -Eq '^([[:space:]]*)diffserv:[[:space:]]+besteffort([[:space:]#]|$)' "$RAW_CONFIG"; then
    echo "ERROR: Snapshot A raw config does not contain diffserv: besteffort" >&2
    exit 1
fi

before="$(nrestarts)"
raw_sha="$(sha256_file "$RAW_CONFIG")"
cp "$RAW_CONFIG" configs/spectrum.yaml
deployed_sha="$(sha256_file configs/spectrum.yaml)"
if [[ "$raw_sha" != "$deployed_sha" ]]; then
    echo "ERROR: copied config hash mismatch: raw=$raw_sha repo=$deployed_sha" >&2
    exit 1
fi

scripts/deploy.sh spectrum "$SSH_HOST"
ssh "$SSH_HOST" 'sudo systemctl restart wanctl@spectrum.service'

qdisc_tmp="$(mktemp)"
if ! scripts/phase227-qdisc-verify.sh --expected-mode besteffort --ssh-host "$SSH_HOST" --out "$qdisc_tmp"; then
    echo "ROLLBACK VERIFY FAILED: qdisc did not return to besteffort on both NICs" >&2
    exit 1
fi
health_check >/dev/null
active="$(service_active)"
if [[ "$active" != "active" ]]; then
    echo "ROLLBACK VERIFY FAILED: service is-active=$active" >&2
    exit 1
fi
after="$(nrestarts)"
journal_json="$(journal_excerpt_json)"
rolled_back_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
write_proof "$rolled_back_utc" "$raw_sha" "$deployed_sha" "$qdisc_tmp" "$active" "$before" "$after" "$journal_json"
rm -f "$qdisc_tmp"
echo "Rollback proof recorded: $OUT_FILE"

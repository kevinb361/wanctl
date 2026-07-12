#!/usr/bin/env bash
# deploy-dry-run-gate.sh — CI-safe manual deployment proof.
#
# This script intentionally performs no live mutation. It renders the standard
# deploy.sh --dry-run plan and the rollback --dry-run plan, then fails closed if
# either path cannot prove it is dry-run/manual-only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WAN="spectrum"
TARGET_HOST="cake-shaper"
DEPLOY_MODE="base"
ROLLBACK_SCRIPT="scripts/phase231-rollback.sh"

usage() {
    cat <<'EOF'
Usage: scripts/deploy-dry-run-gate.sh [options]

Options:
  --wan spectrum|att
      WAN selector for deploy and rollback plans (default: spectrum)
  --target-host HOST
      Target hostname rendered into the dry-run deploy plan (default: cake-shaper)
  --deploy-mode base|steering|spectrum-cake-autorate|att-cake-autorate
      Deployment shape to render. Cake-autorate modes must match --wan.
  --rollback-script PATH
      Rollback script to render with --dry-run (default: scripts/phase231-rollback.sh)
  --help, -h
      Show this help.

Safety:
  This gate never runs deploy.sh without --dry-run and never runs rollback without --dry-run.
  It is suitable for workflow_dispatch CI because it does not require SSH keys, router creds,
  sudo, or live network access.
EOF
}

fail() {
    echo "ERROR: $*" >&2
    exit 2
}

require_file() {
    local path="$1"
    [[ -f "$path" ]] || fail "required file missing: $path"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan) WAN="${2:-}"; shift 2 ;;
        --target-host) TARGET_HOST="${2:-}"; shift 2 ;;
        --deploy-mode) DEPLOY_MODE="${2:-}"; shift 2 ;;
        --rollback-script) ROLLBACK_SCRIPT="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) fail "unknown argument: $1" ;;
    esac
done

case "$WAN" in
    spectrum|att) ;;
    *) fail "--wan must be spectrum or att" ;;
esac

case "$DEPLOY_MODE" in
    base) DEPLOY_ARGS=() ;;
    steering) DEPLOY_ARGS=(--with-steering) ;;
    spectrum-cake-autorate)
        [[ "$WAN" == "spectrum" ]] || fail "spectrum-cake-autorate requires --wan spectrum"
        DEPLOY_ARGS=(--with-spectrum-cake-autorate)
        ;;
    att-cake-autorate)
        [[ "$WAN" == "att" ]] || fail "att-cake-autorate requires --wan att"
        DEPLOY_ARGS=(--with-att-cake-autorate)
        ;;
    *) fail "unknown --deploy-mode: $DEPLOY_MODE" ;;
esac

cd "$PROJECT_ROOT"
require_file "scripts/deploy.sh"
require_file "$ROLLBACK_SCRIPT"

printf '=== wanctl manual dry-run deploy gate ===\n'
printf 'WAN: %s\n' "$WAN"
printf 'target_host: %s\n' "$TARGET_HOST"
printf 'deploy_mode: %s\n' "$DEPLOY_MODE"
printf 'rollback_script: %s\n\n' "$ROLLBACK_SCRIPT"

DEPLOY_LOG="$(mktemp)"
ROLLBACK_LOG="$(mktemp)"
trap 'rm -f "$DEPLOY_LOG" "$ROLLBACK_LOG"' EXIT

printf '%s\n' '--- deploy dry-run ---'
bash scripts/deploy.sh "$WAN" "$TARGET_HOST" "${DEPLOY_ARGS[@]}" --dry-run | tee "$DEPLOY_LOG"

grep -q "DRY RUN - no changes will be made" "$DEPLOY_LOG" \
    || fail "deploy dry-run proof marker missing"
grep -q -- "rsync src/wanctl/ to ${TARGET_HOST}:/opt/wanctl/" "$DEPLOY_LOG" \
    || fail "deploy dry-run did not render expected target/code path"

printf '\n%s\n' '--- rollback dry-run ---'
bash "$ROLLBACK_SCRIPT" --wan "$WAN" --ssh-host "$TARGET_HOST" --dry-run | tee "$ROLLBACK_LOG"

grep -q "mutation only with --confirm" "$ROLLBACK_LOG" \
    || fail "rollback dry-run does not prove confirm-gated mutation"
grep -q "Rollback sequence:" "$ROLLBACK_LOG" \
    || fail "rollback dry-run sequence missing"
grep -q "Return-to-cake sequence" "$ROLLBACK_LOG" \
    || fail "return-to-cake sequence missing"

printf '\nOK: manual deploy dry-run gate rendered deploy and rollback plans without live mutation.\n'

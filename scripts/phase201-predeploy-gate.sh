#!/usr/bin/env bash
# Phase 201 predeploy gate (D-15).
#
# Inspects $REMOTE_SSH_TARGET:$REMOTE_YAML_PATH (default
# /etc/wanctl/spectrum.yaml) for v1.41-only rejected-hypothesis keys.
#
# Exit 0  PASS  — YAML is clean (or aligned with Phase 201 design).
# Exit 1  BLOCK — rejected v1.41 keys present, OR docsis_mode: true
#                 without setpoint_mbps. Operator-actionable message.
# Exit 2  ABORT — missing deps / SSH fail / parse error / malformed env.
#
# Reconciliation rules (RESEARCH.md §5):
#   - target_bloat_ms      in continuous_monitoring.upload  -> BLOCK (rejected v1.41)
#   - warn_bloat_ms        in continuous_monitoring.upload  -> BLOCK (rejected v1.41)
#   - factor_down_yellow   in continuous_monitoring.upload  -> ALLOW (R5 retained)
#   - consecutive_yellow_decay_clamp -> ALLOW (R3 retained)
#   - docsis_mode: true requires setpoint_mbps -> BLOCK if missing.
#
# Fail-closed (RESEARCH §9 Option B). Auto-strip is intentionally NOT
# implemented — operator must decide.
#
# Test escape hatch: set PHASE201_LOCAL_YAML_OVERRIDE=<path> to bypass SSH
# and read a local YAML file directly. Used by tests/test_phase201_predeploy_gate.py.

set -euo pipefail

EXIT_PASS=0
EXIT_BLOCK=1
EXIT_ABORT=2

log_info()  { printf '[predeploy-gate INFO]  %s\n' "$*" >&2; }
log_block() { printf '[predeploy-gate BLOCK] %s\n' "$*" >&2; printf '%s\n' "$*"; }
log_abort() { printf '[predeploy-gate ABORT] %s\n' "$*" >&2; }

# --- Path validation (Phase 200 Plan 11 mirror) ---
validate_remote_yaml_path() {
    local p="$1"
    [[ "$p" =~ ^/[A-Za-z0-9._/-]+$ ]]
}

# --- Read YAML (local override OR SSH+sudo+cat) ---
read_yaml() {
    if [[ -n "${PHASE201_LOCAL_YAML_OVERRIDE:-}" ]]; then
        if [[ ! -f "$PHASE201_LOCAL_YAML_OVERRIDE" ]]; then
            log_abort "PHASE201_LOCAL_YAML_OVERRIDE=${PHASE201_LOCAL_YAML_OVERRIDE} does not exist"
            return $EXIT_ABORT
        fi
        cat -- "$PHASE201_LOCAL_YAML_OVERRIDE"
        return 0
    fi

    : "${REMOTE_YAML_PATH:=/etc/wanctl/spectrum.yaml}"
    if [[ -z "${REMOTE_SSH_TARGET:-}" ]]; then
        log_abort "REMOTE_SSH_TARGET must be set (or use PHASE201_LOCAL_YAML_OVERRIDE)"
        return $EXIT_ABORT
    fi
    if ! validate_remote_yaml_path "$REMOTE_YAML_PATH"; then
        log_abort "REMOTE_YAML_PATH failed safe-path validation: ${REMOTE_YAML_PATH}"
        return $EXIT_ABORT
    fi
    if ! command -v ssh >/dev/null 2>&1; then
        log_abort "ssh not found on PATH"
        return $EXIT_ABORT
    fi
    # Pre-check remote python+yaml (closes WR-02 from Phase 200 RETRO).
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_SSH_TARGET" \
        'python3 -c "import yaml" 2>/dev/null'; then
        log_abort "Remote python3+pyyaml unavailable on ${REMOTE_SSH_TARGET}"
        return $EXIT_ABORT
    fi
    ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
        "sudo cat -- '${REMOTE_YAML_PATH}'" 2>/dev/null
}

# --- Run python YAML probe ---
yaml_probe() {
    if ! command -v python3 >/dev/null 2>&1; then
        log_abort "python3 not found on PATH"
        return $EXIT_ABORT
    fi
    python3 -c '
import sys, json, yaml
try:
    d = yaml.safe_load(sys.stdin)
    if not isinstance(d, dict):
        print(json.dumps({"error": "yaml root not a mapping"}))
        sys.exit(2)
    cm = d.get("continuous_monitoring") or {}
    ul = cm.get("upload") or {}
    if not isinstance(ul, dict):
        print(json.dumps({"error": "continuous_monitoring.upload not a mapping"}))
        sys.exit(2)
    print(json.dumps({
        "has_target_bloat_ms": "target_bloat_ms" in ul,
        "has_warn_bloat_ms": "warn_bloat_ms" in ul,
        "docsis_mode": ul.get("docsis_mode", False),
        "setpoint_mbps": ul.get("setpoint_mbps"),
        "has_factor_down_yellow": "factor_down_yellow" in ul,
        "has_consecutive_yellow_decay_clamp": "consecutive_yellow_decay_clamp" in ul,
    }))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    sys.exit(2)
'
}

json_get() {
    local key="$1"
    python3 -c 'import sys,json; data=json.loads(sys.stdin.read()); v=data.get(sys.argv[1]); print("" if v is None else v)' "$key"
}

# --- Main ---
main() {
    local yaml_text
    yaml_text="$(read_yaml)" || exit $?
    if [[ -z "$yaml_text" ]]; then
        log_abort "Empty YAML returned from read_yaml"
        exit $EXIT_ABORT
    fi

    local probe
    probe="$(printf '%s' "$yaml_text" | yaml_probe)" || exit $?

    local err
    err="$(printf '%s' "$probe" | json_get error)"
    if [[ -n "$err" ]]; then
        log_abort "YAML parse error: ${err}"
        exit $EXIT_ABORT
    fi

    local has_target has_warn docsis_mode setpoint
    has_target="$(printf '%s' "$probe" | json_get has_target_bloat_ms)"
    has_warn="$(printf '%s' "$probe" | json_get has_warn_bloat_ms)"
    docsis_mode="$(printf '%s' "$probe" | json_get docsis_mode)"
    setpoint="$(printf '%s' "$probe" | json_get setpoint_mbps)"

    local blocked=false
    if [[ "$has_target" == "True" ]]; then
        log_block "BLOCK: target_bloat_ms present in continuous_monitoring.upload (rejected v1.41 hypothesis key). Reconcile manually: ssh to deploy target, edit ${REMOTE_YAML_PATH:-/etc/wanctl/spectrum.yaml}, remove the target_bloat_ms key under continuous_monitoring.upload, then re-run deploy. Auto-strip is intentionally not implemented."
        blocked=true
    fi
    if [[ "$has_warn" == "True" ]]; then
        log_block "BLOCK: warn_bloat_ms present in continuous_monitoring.upload (rejected v1.41 hypothesis key). Reconcile manually: ssh to deploy target, edit ${REMOTE_YAML_PATH:-/etc/wanctl/spectrum.yaml}, remove the warn_bloat_ms key under continuous_monitoring.upload, then re-run deploy. Auto-strip is intentionally not implemented."
        blocked=true
    fi
    if [[ "$docsis_mode" == "True" && -z "$setpoint" ]]; then
        log_block "BLOCK: docsis_mode: true present but setpoint_mbps missing. Phase 201 D-06 fail-closed: setpoint_mbps is REQUIRED when docsis_mode is enabled. Add setpoint_mbps to continuous_monitoring.upload in ${REMOTE_YAML_PATH:-/etc/wanctl/spectrum.yaml}."
        blocked=true
    fi
    if [[ "$blocked" == "true" ]]; then
        exit $EXIT_BLOCK
    fi

    log_info "PASS: continuous_monitoring.upload is clean (no v1.41 rejected keys; if docsis_mode is enabled, setpoint_mbps is set)."
    exit $EXIT_PASS
}

main "$@"

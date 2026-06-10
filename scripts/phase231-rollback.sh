#!/usr/bin/env bash
# phase231-rollback.sh - SOAK-02 rollback procedure renderer/preflight/executor.
# Usage: scripts/phase231-rollback.sh --wan spectrum|att [--preflight|--dry-run|--confirm --i-have-operator-approval]

set -euo pipefail

WAN=""
SSH_HOST="kevin@10.10.110.223"
OUT_FILE=".planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight.json"
PREFLIGHT="0"
DRY_RUN="0"
CONFIRM="0"
OPERATOR_APPROVAL="0"
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)

usage() {
    cat <<'EOF'
Usage: scripts/phase231-rollback.sh --wan spectrum|att [options]

SOAK-02 rollback verification for the cake-autorate migration.

Modes:
  --preflight                    Read-only live precondition proof; writes JSON to --out
  --dry-run                      Print ordered rollback + return-to-cake plans; mutate nothing
                                 Default mode when neither --preflight nor --confirm is provided
  --confirm                      Execute production rollback; requires --i-have-operator-approval

Options:
  --wan spectrum|att             Required WAN selector
  --ssh-host HOST                SSH target (default: kevin@10.10.110.223)
  --out FILE                     Proof JSON output path
  --i-have-operator-approval     Required with --confirm; belt-and-suspenders mutation gate
  --help, -h                     Show this help

Safety:
  Preflight and dry-run are read-only. Any production mutation requires BOTH --confirm and
  --i-have-operator-approval, and should only be run after the operator checkpoint approves
  a live exercise on one named WAN.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 2
    fi
}

json_string() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

validate_wan() {
    case "$WAN" in
        spectrum|att) ;;
        "") echo "ERROR: --wan is required" >&2; usage >&2; exit 2 ;;
        *) echo "ERROR: --wan must be spectrum or att" >&2; exit 2 ;;
    esac
}

health_url_for_wan() {
    case "$1" in
        spectrum) printf '%s\n' "http://10.10.110.223:9101/health" ;;
        att) printf '%s\n' "http://10.10.110.227:9101/health" ;;
    esac
}

rollback_commands_for_wan() {
    case "$1" in
        att)
            cat <<'EOF'
sudo systemctl disable --now cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service
sudo systemctl enable --now wanctl@att.service silicom-bypass-watchdog@att.service
sleep 8
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem set_disc off
sudo ./bpctl_util att-modem set_bypass off
sudo ./bpctl_util att-modem reset_bypass_wd >/dev/null || true
sudo tc qdisc replace dev att-router root cake bandwidth 95Mbit diffserv4 triple-isolate ingress nonat nowash no-ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb
sudo tc qdisc replace dev att-modem root cake bandwidth 18Mbit diffserv4 triple-isolate egress nonat nowash ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb
EOF
            ;;
        spectrum)
            cat <<'EOF'
sudo systemctl disable --now cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service
sudo systemctl enable --now wanctl@spectrum.service
sleep 8
sudo tc qdisc replace dev spec-router root cake bandwidth 550Mbit diffserv4 triple-isolate nonat wash no-ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb
sudo tc qdisc replace dev spec-modem root cake bandwidth 18Mbit diffserv4 triple-isolate nonat wash ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb
EOF
            ;;
    esac
}

return_commands_for_wan() {
    case "$1" in
        att)
            cat <<'EOF'
sudo systemctl disable --now wanctl@att.service silicom-bypass-watchdog@att.service
sudo systemctl enable --now cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service
# qdisc re-init is handled by /usr/local/sbin/cake-autorate-att-qdisc-init via ExecStartPre
EOF
            ;;
        spectrum)
            cat <<'EOF'
sudo systemctl disable --now wanctl@spectrum.service
sudo systemctl enable --now cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service
# silicom-bypass-watchdog@spectrum.service stays active in both modes; do not stop/disable it here.
# qdisc re-init is handled by /usr/local/sbin/cake-autorate-spectrum-qdisc-init via ExecStartPre
EOF
            ;;
    esac
}

print_plan() {
    cat <<EOF
Phase 231 SOAK-02 rollback plan for ${WAN} (mutation only with --confirm --i-have-operator-approval)

Expected watchdog states:
  - spectrum: silicom-bypass-watchdog@spectrum.service active in external mode and native rollback mode; rollback leaves it untouched.
  - att: silicom-bypass-watchdog-cake-autorate-att.service active in external mode; silicom-bypass-watchdog@att.service inactive until native rollback.

Rollback sequence:
EOF
    rollback_commands_for_wan "$WAN" | sed 's/^/  /'
    cat <<'EOF'

Return-to-cake sequence (production steady state after any live exercise):
EOF
    return_commands_for_wan "$WAN" | sed 's/^/  /'
}

remote_capture() {
    local remote_cmd="$1" stdout_file="$2" stderr_file="$3"
    ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "$remote_cmd" >"$stdout_file" 2>"$stderr_file"
}

append_check() {
    local checks_file="$1" name="$2" command_text="$3" expected="$4" stdout_file="$5" stderr_file="$6" rc="$7" pass="$8"
    python3 - "$checks_file" "$name" "$command_text" "$expected" "$stdout_file" "$stderr_file" "$rc" "$pass" <<'PY'
import json
import sys
from pathlib import Path

checks_file, name, command_text, expected, stdout_path, stderr_path, rc, passed = sys.argv[1:]
row = {
    "name": name,
    "command": command_text,
    "expected": expected,
    "pass": passed == "true",
    "exit_code": int(rc),
    "raw_stdout": Path(stdout_path).read_text(encoding="utf-8", errors="replace"),
    "raw_stderr": Path(stderr_path).read_text(encoding="utf-8", errors="replace"),
}
with Path(checks_file).open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, sort_keys=True) + "\n")
PY
}

run_check() {
    local checks_file="$1" name="$2" command_text="$3" expected="$4" predicate="$5" tmpdir="$6"
    local stdout_file stderr_file rc pass="false" raw_stdout
    stdout_file="${tmpdir}/${name//[^A-Za-z0-9_.-]/_}.stdout"
    stderr_file="${tmpdir}/${name//[^A-Za-z0-9_.-]/_}.stderr"
    set +e
    remote_capture "$command_text" "$stdout_file" "$stderr_file"
    rc="$?"
    set -e
    raw_stdout="$(<"$stdout_file")"
    case "$predicate" in
        rc0) [[ "$rc" -eq 0 ]] && pass="true" ;;
        stdout-disabled) [[ "$raw_stdout" == "disabled" ]] && pass="true" ;;
        stdout-inactive) [[ "$raw_stdout" == "inactive" ]] && pass="true" ;;
        stdout-active) [[ "$rc" -eq 0 && "$raw_stdout" == "active" ]] && pass="true" ;;
        contains-conflicts) [[ "$rc" -eq 0 && "$raw_stdout" == *"Conflicts=wanctl@${WAN}.service"* ]] && pass="true" ;;
        *) echo "ERROR: unknown predicate: $predicate" >&2; exit 2 ;;
    esac
    append_check "$checks_file" "$name" "$command_text" "$expected" "$stdout_file" "$stderr_file" "$rc" "$pass"
}

write_preflight_json() {
    local checks_file="$1" captured_utc="$2" rollback_file="$3" return_file="$4"
    mkdir -p "$(dirname "$OUT_FILE")"
    python3 - "$OUT_FILE" "$WAN" "$SSH_HOST" "$captured_utc" "$checks_file" "$rollback_file" "$return_file" <<'PY'
import json
import sys
from pathlib import Path

out, wan, ssh_host, captured_utc, checks_path, rollback_path, return_path = sys.argv[1:]
checks = [json.loads(line) for line in Path(checks_path).read_text(encoding="utf-8").splitlines() if line.strip()]
payload = {
    "proof_type": "phase231-rollback-preflight",
    "captured_utc": captured_utc,
    "wan": wan,
    "ssh_host": ssh_host,
    "read_only": True,
    "overall_pass": all(row.get("pass") is True for row in checks),
    "checks": checks,
    "rollback_sequence": Path(rollback_path).read_text(encoding="utf-8"),
    "return_to_cake_sequence": Path(return_path).read_text(encoding="utf-8"),
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Preflight proof recorded: {out}")
raise SystemExit(0 if payload["overall_pass"] else 1)
PY
}

run_preflight() {
    local tmpdir checks_file rollback_file return_file captured
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' RETURN
    checks_file="${tmpdir}/checks.ndjson"
    rollback_file="${tmpdir}/rollback.txt"
    return_file="${tmpdir}/return.txt"
    : >"$checks_file"
    rollback_commands_for_wan "$WAN" >"$rollback_file"
    return_commands_for_wan "$WAN" >"$return_file"
    captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    run_check "$checks_file" "native_unit_template" "systemctl cat wanctl@.service" "wanctl template exists" rc0 "$tmpdir"
    run_check "$checks_file" "native_instance_disabled" "systemctl is-enabled wanctl@${WAN}.service" "stdout exactly disabled" stdout-disabled "$tmpdir"
    run_check "$checks_file" "native_instance_inactive" "systemctl is-active wanctl@${WAN}.service" "stdout exactly inactive" stdout-inactive "$tmpdir"
    run_check "$checks_file" "native_config_present" "sudo -n test -f /etc/wanctl/${WAN}.yaml" "native config present" rc0 "$tmpdir"
    run_check "$checks_file" "native_code_present" "test -f /opt/wanctl/autorate_continuous.py" "native controller code present" rc0 "$tmpdir"
    run_check "$checks_file" "cake_conflicts_guard" "systemctl cat cake-autorate-${WAN}.service" "contains Conflicts=wanctl@${WAN}.service" contains-conflicts "$tmpdir"
    run_check "$checks_file" "external_cake_active" "systemctl is-active cake-autorate-${WAN}.service" "stdout exactly active" stdout-active "$tmpdir"
    run_check "$checks_file" "external_bridge_active" "systemctl is-active cake-autorate-${WAN}-state-bridge.service" "stdout exactly active" stdout-active "$tmpdir"

    if [[ "$WAN" == "spectrum" ]]; then
        run_check "$checks_file" "spectrum_watchdog_active" "systemctl is-active silicom-bypass-watchdog@spectrum.service" "stdout exactly active" stdout-active "$tmpdir"
    else
        run_check "$checks_file" "att_cake_watchdog_active" "systemctl is-active silicom-bypass-watchdog-cake-autorate-att.service" "stdout exactly active" stdout-active "$tmpdir"
        run_check "$checks_file" "att_native_watchdog_inactive" "systemctl is-active silicom-bypass-watchdog@att.service" "stdout exactly inactive" stdout-inactive "$tmpdir"
        run_check "$checks_file" "att_bpctl_executable" "test -x /opt/bpctl-silicom/bpctl_util" "bpctl_util is executable" rc0 "$tmpdir"
        run_check "$checks_file" "att_watchdog_template" "systemctl cat silicom-bypass-watchdog@.service" "native watchdog template exists" rc0 "$tmpdir"
        run_check "$checks_file" "att_watchdog_env_present" "sudo -n test -f /etc/wanctl/bpctl-watchdog/att.env" "native watchdog EnvironmentFile present" rc0 "$tmpdir"
    fi

    write_preflight_json "$checks_file" "$captured" "$rollback_file" "$return_file"
}

health_check() {
    local url="$1"
    python3 - "$url" <<'PY'
import json
import sys
import time
from urllib.request import urlopen

url = sys.argv[1]
deadline = time.time() + 45
last = None
while time.time() < deadline:
    try:
        with urlopen(url, timeout=5) as fh:
            payload = json.load(fh)
        if isinstance(payload, dict) and payload.get("status") == "healthy":
            print("healthy")
            raise SystemExit(0)
        last = payload
    except Exception as exc:  # pragma: no cover - confirm mode only
        last = str(exc)
    time.sleep(3)
raise SystemExit(f"HEALTH FAIL: {url}: {last!r}")
PY
}

run_confirm() {
    local tmpdir remote_script active health_url proof_time
    if [[ "$OPERATOR_APPROVAL" != "1" ]]; then
        echo "REFUSED: --confirm requires --i-have-operator-approval before any remote call." >&2
        exit 2
    fi
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' RETURN
    remote_script="${tmpdir}/rollback-remote.sh"
    rollback_commands_for_wan "$WAN" >"$remote_script"
    ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "bash -s" <"$remote_script"
    active="$(ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "systemctl is-active wanctl@${WAN}.service")"
    if [[ "$active" != "active" ]]; then
        echo "ROLLBACK VERIFY FAILED: wanctl@${WAN}.service is-active=${active}" >&2
        exit 1
    fi
    health_url="$(health_url_for_wan "$WAN")"
    health_check "$health_url" >/dev/null
    proof_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    mkdir -p "$(dirname "$OUT_FILE")"
    python3 - "$OUT_FILE" "$WAN" "$SSH_HOST" "$proof_time" "$active" "$health_url" <<'PY'
import json
import sys
from pathlib import Path

out, wan, ssh_host, proof_time, active, health_url = sys.argv[1:]
Path(out).write_text(json.dumps({
    "proof_type": "phase231-rollback-confirm",
    "wan": wan,
    "ssh_host": ssh_host,
    "rolled_back_utc": proof_time,
    "wanctl_active": active,
    "health_url": health_url,
    "health_status": "healthy",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Rollback exercise proof recorded: {out}")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan) WAN="${2:-}"; shift 2 ;;
        --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
        --out) OUT_FILE="${2:-}"; shift 2 ;;
        --preflight) PREFLIGHT="1"; shift ;;
        --dry-run) DRY_RUN="1"; shift ;;
        --confirm) CONFIRM="1"; shift ;;
        --i-have-operator-approval) OPERATOR_APPROVAL="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

validate_wan
require_command python3
require_command ssh
require_command sed

mode_count=$((PREFLIGHT + DRY_RUN + CONFIRM))
if [[ "$mode_count" -gt 1 ]]; then
    echo "ERROR: choose only one of --preflight, --dry-run, or --confirm" >&2
    exit 2
fi
if [[ "$mode_count" -eq 0 ]]; then
    DRY_RUN="1"
fi

if [[ "$DRY_RUN" == "1" ]]; then
    print_plan
elif [[ "$PREFLIGHT" == "1" ]]; then
    run_preflight
elif [[ "$CONFIRM" == "1" ]]; then
    run_confirm
fi

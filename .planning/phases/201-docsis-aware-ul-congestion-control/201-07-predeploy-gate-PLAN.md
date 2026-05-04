---
phase: 201-docsis-aware-ul-congestion-control
plan: 07
type: execute
wave: 4
depends_on: [02, 06]
files_modified:
  - scripts/phase201-predeploy-gate.sh
  - scripts/deploy.sh
  - tests/test_phase201_predeploy_gate.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-4, predeploy, d-15, fail-closed, security-gate]

must_haves:
  truths:
    - "scripts/phase201-predeploy-gate.sh exists, is executable, and uses set -euo pipefail"
    - "Gate inspects target /etc/wanctl/spectrum.yaml via SSH+sudo+yaml.safe_load (mirroring Phase 200 43838f4 pattern); offers PHASE201_LOCAL_YAML_OVERRIDE for tests"
    - "Gate exits 0 (PASS) when YAML is clean: no target_bloat_ms / warn_bloat_ms in continuous_monitoring.upload, AND if docsis_mode: true then setpoint_mbps present"
    - "Gate exits 1 (BLOCK) with operator-actionable message when rejected v1.41 keys present, OR docsis_mode: true without setpoint_mbps"
    - "Gate exits 2 (ABORT) on missing remote python3+pyyaml, missing SSH access, malformed env, or unreadable YAML (closes WR-02)"
    - "scripts/deploy.sh invokes the gate BEFORE rsync of /opt/wanctl artifacts; deploy aborts on non-zero gate exit"
    - "REMOTE_YAML_PATH validated with absolute-path regex (^/[A-Za-z0-9._/-]+$) before SSH command construction (Phase 200 Plan 11 pattern)"
    - "Predeploy gate test suite (tests/test_phase201_predeploy_gate.py from Plan 201-02) passes end-to-end"
  artifacts:
    - path: scripts/phase201-predeploy-gate.sh
      provides: "D-15 fail-closed predeploy gate; SSH+sudo+yaml.safe_load+jq pattern; three-way exit (0/1/2)"
      contains: "phase201-predeploy-gate"
    - path: scripts/deploy.sh
      provides: "Pre-rsync gate invocation; deploy aborts on gate fail"
      contains: "phase201-predeploy-gate.sh"
    - path: tests/test_phase201_predeploy_gate.py
      provides: "Full TestPredeployGate test class — 6 cases all passing"
      contains: "TestPredeployGate"
  key_links:
    - from: "scripts/deploy.sh"
      to: "scripts/phase201-predeploy-gate.sh"
      via: "sourcing or exec invocation before rsync step"
      pattern: "phase201-predeploy-gate.sh"
    - from: "scripts/phase201-predeploy-gate.sh"
      to: "production /etc/wanctl/spectrum.yaml"
      via: "ssh sudo cat | python3 yaml.safe_load"
      pattern: "yaml.safe_load"
---

<objective>
Wave 4 deploy-machinery gate. Implements D-15 fail-closed predeploy reconciliation per RESEARCH §9 Option B (operator-manual reconcile, NOT auto-strip). The gate inspects production `/etc/wanctl/spectrum.yaml` on the deploy target and aborts with an operator-actionable message if v1.41-only rejected-hypothesis keys (`target_bloat_ms`, `warn_bloat_ms` in `continuous_monitoring.upload`) remain in place.

Per RESEARCH §9 reasoning: auto-strip is irreversible and the operator MUST decide what to keep (R5+R3) vs strip (R0). Fail-closed mirrors Phase 200's gate philosophy and CLAUDE.md priority order.

After this plan lands, any future Spectrum deploy/restart under v1.42 is gated: production YAML must be reconciled to Phase 201's design before the binary moves.

Plan 201-02 wrote test stubs in `tests/test_phase201_predeploy_gate.py` with `pytest.skip()` guards. This plan removes those skips by implementing the gate script with `PHASE201_LOCAL_YAML_OVERRIDE` test escape hatch.

Output: One new shell script (executable); deploy.sh extension; full predeploy-gate test class GREEN.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@scripts/phase200-saturation-canary.sh
@scripts/deploy.sh
</context>

<interfaces>
<!-- Existing patterns to mirror VERBATIM. -->

Existing SSH+sudo+yaml.safe_load pattern (scripts/phase200-saturation-canary.sh:314-362):
```
YAML_PROBE="$(ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
    "sudo cat -- '${REMOTE_YAML_PATH}'" 2>/dev/null \
    | python3 -c '
import sys, json, yaml
try:
    d = yaml.safe_load(sys.stdin)
    ul = d["continuous_monitoring"]["upload"]
    print(json.dumps({"floor": ul["floor_mbps"], ...}))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
' 2>/dev/null)"
```

Existing path-validation helper (Phase 200 Plan 11): `validate_remote_yaml_path` accepts `^/[A-Za-z0-9._/-]+$`. Source it from canary script via `source scripts/phase200-saturation-canary.sh --self-test-export-helpers` if it exposes that, OR copy the helper inline (preferred — keeps gate script self-contained).

Test escape hatch (test contract from Plan 201-02):
  PHASE201_LOCAL_YAML_OVERRIDE=<path>  -> read local YAML directly, bypassing SSH

Three-way exit:
  0 = PASS (clean or aligned with Phase 201 design)
  1 = BLOCK (rejected keys present; operator-actionable message)
  2 = ABORT (env malformed, SSH fail, missing deps, parse error)
</interfaces>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Author scripts/phase201-predeploy-gate.sh with three-way fail-closed exit</name>
  <files>scripts/phase201-predeploy-gate.sh</files>
  <read_first>
    - scripts/phase200-saturation-canary.sh:1-100 (header, helpers, log_info/log_abort patterns to copy)
    - scripts/phase200-saturation-canary.sh:300-400 (SSH+yaml probe pattern)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §9 (action shape Option B)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "scripts/phase201-predeploy-gate.sh (NEW)"
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-13-PLAN.md if present, OR docker hardening lessons (REMOTE_YAML_PATH validation regex)
    - tests/test_phase201_predeploy_gate.py (the contract — six TestPredeployGate cases)
  </read_first>
  <action>
Create `scripts/phase201-predeploy-gate.sh` (chmod +x). Use this exact skeleton (adjust helper names to match existing canary script):

```bash
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
    if [[ -z "${REMOTE_SSH_TARGET:-}" || -z "${REMOTE_YAML_PATH:-}" ]]; then
        log_abort "REMOTE_SSH_TARGET and REMOTE_YAML_PATH must be set (or use PHASE201_LOCAL_YAML_OVERRIDE)"
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
        sys.exit(0)
    cm = d.get("continuous_monitoring") or {}
    ul = cm.get("upload") or {}
    print(json.dumps({
        "has_target_bloat_ms": "target_bloat_ms" in ul,
        "has_warn_bloat_ms":   "warn_bloat_ms" in ul,
        "docsis_mode":         ul.get("docsis_mode", False),
        "setpoint_mbps":       ul.get("setpoint_mbps"),
        "has_factor_down_yellow": "factor_down_yellow" in ul,
        "has_consecutive_yellow_decay_clamp": "consecutive_yellow_decay_clamp" in ul,
    }))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
'
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
    err="$(printf '%s' "$probe" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read()).get("error",""))')"
    if [[ -n "$err" ]]; then
        log_abort "YAML parse error: ${err}"
        exit $EXIT_ABORT
    fi

    local has_target has_warn docsis_mode setpoint
    has_target="$(printf '%s' "$probe" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["has_target_bloat_ms"])')"
    has_warn="$(printf '%s' "$probe"   | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["has_warn_bloat_ms"])')"
    docsis_mode="$(printf '%s' "$probe" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["docsis_mode"])')"
    setpoint="$(printf '%s' "$probe"    | python3 -c 'import sys,json; v=json.loads(sys.stdin.read())["setpoint_mbps"]; print("" if v is None else v)')"

    local blocked=false
    if [[ "$has_target" == "True" ]]; then
        log_block "BLOCK: target_bloat_ms present in continuous_monitoring.upload (rejected v1.41 hypothesis key). Remove it from /etc/wanctl/spectrum.yaml or run scripts/phase201-reconcile-yaml.sh --strip-rejected (operator-manual)."
        blocked=true
    fi
    if [[ "$has_warn" == "True" ]]; then
        log_block "BLOCK: warn_bloat_ms present in continuous_monitoring.upload (rejected v1.41 hypothesis key). Remove it from /etc/wanctl/spectrum.yaml or run scripts/phase201-reconcile-yaml.sh --strip-rejected (operator-manual)."
        blocked=true
    fi
    if [[ "$docsis_mode" == "True" && -z "$setpoint" ]]; then
        log_block "BLOCK: docsis_mode: true present but setpoint_mbps missing. Phase 201 D-06 fail-closed: setpoint_mbps is REQUIRED when docsis_mode is enabled. Add setpoint_mbps to continuous_monitoring.upload in /etc/wanctl/spectrum.yaml."
        blocked=true
    fi
    if [[ "$blocked" == "true" ]]; then
        exit $EXIT_BLOCK
    fi
    log_info "PASS: continuous_monitoring.upload is clean (no v1.41 rejected keys; if docsis_mode is enabled, setpoint_mbps is set)."
    exit $EXIT_PASS
}

main "$@"
```

After writing, `chmod +x scripts/phase201-predeploy-gate.sh`.

Verify the test contract:
```
.venv/bin/pytest -o addopts='' tests/test_phase201_predeploy_gate.py -v
```
All six cases must pass.
  </action>
  <acceptance_criteria>
    - `test -x scripts/phase201-predeploy-gate.sh` succeeds.
    - `grep -c '^set -euo pipefail' scripts/phase201-predeploy-gate.sh` returns 1.
    - `grep -c 'EXIT_BLOCK=1' scripts/phase201-predeploy-gate.sh` returns 1.
    - `grep -c 'EXIT_ABORT=2' scripts/phase201-predeploy-gate.sh` returns 1.
    - `grep -c 'PHASE201_LOCAL_YAML_OVERRIDE' scripts/phase201-predeploy-gate.sh` returns >= 2.
    - `grep -c 'validate_remote_yaml_path' scripts/phase201-predeploy-gate.sh` returns >= 2.
    - `grep -c 'target_bloat_ms' scripts/phase201-predeploy-gate.sh` returns >= 2.
    - `grep -c 'docsis_mode' scripts/phase201-predeploy-gate.sh` returns >= 2.
    - `grep -c 'yaml.safe_load' scripts/phase201-predeploy-gate.sh` returns 1.
    - `grep -c 'python3 -c "import yaml"' scripts/phase201-predeploy-gate.sh` returns 1 (closes WR-02 remote-deps precheck).
    - All TestPredeployGate cases pass: `.venv/bin/pytest -o addopts='' tests/test_phase201_predeploy_gate.py -v` returns 0.
    - bash -n syntax check: `bash -n scripts/phase201-predeploy-gate.sh` returns 0.
    - shellcheck (if available): `command -v shellcheck && shellcheck scripts/phase201-predeploy-gate.sh` returns 0; if shellcheck not on PATH, this gate is skipped and bash -n is sufficient.
  </acceptance_criteria>
  <verify>
    <automated>bash -n scripts/phase201-predeploy-gate.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_phase201_predeploy_gate.py -v</automated>
  </verify>
  <done>Gate script exists, executable, syntax-clean, passes all six test contracts; remote-deps precheck closes WR-02; absolute-path validation prevents shell injection.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Wire scripts/deploy.sh to invoke the predeploy gate before rsync</name>
  <files>scripts/deploy.sh</files>
  <read_first>
    - scripts/deploy.sh (full file — locate via grep where rsync of /opt/wanctl is invoked, and where any preflight-style checks already run)
    - scripts/install.sh (locate via grep — does it call deploy.sh, or vice versa?)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §9 ("Option α (new script) + invocation from scripts/deploy.sh")
  </read_first>
  <action>
First, read `scripts/deploy.sh` end-to-end. Find:
- Where `rsync` to `/opt/wanctl` is executed (this is the gate-before-this point)
- Whether deploy.sh accepts the WAN name (e.g. `spectrum`) as an argument
- Existing preflight pattern (any `command -v ssh` or similar)

Insert a new gate-invocation block IMMEDIATELY BEFORE the rsync command. The block must:

1. Only run for Spectrum deploys (the gate's scope is Spectrum YAML; ATT and other YAMLs do not carry the v1.41 keys per D-17). If deploy.sh is WAN-aware, gate by WAN name; if it's ALL-WANs, run the gate once and let it short-circuit on non-Spectrum if the YAML doesn't have the rejected keys (which it shouldn't).

2. Source environment for `REMOTE_SSH_TARGET` and `REMOTE_YAML_PATH`. Reuse the existing canary `.env` if deploy.sh already loads it; otherwise add an inline doc note that operator must export these before invoking deploy.sh.

3. Invoke the gate; capture exit code; on non-zero, print operator-actionable line and exit deploy.sh with the gate's exit code.

Suggested insert (adapt to deploy.sh structure):

```bash
# ----------------------------------------------------------------------
# Phase 201 predeploy gate (D-15) — fail-closed against rejected v1.41
# hypothesis keys in /etc/wanctl/spectrum.yaml on the deploy target.
# Runs BEFORE rsync of /opt/wanctl artifacts.
# ----------------------------------------------------------------------
PREDEPLOY_GATE="$(dirname "$0")/phase201-predeploy-gate.sh"
if [[ -x "$PREDEPLOY_GATE" ]]; then
    echo "[deploy] running Phase 201 predeploy gate"
    if ! "$PREDEPLOY_GATE"; then
        gate_rc=$?
        echo "[deploy] ABORTING: predeploy gate exit=${gate_rc}. Reconcile /etc/wanctl/spectrum.yaml on the deploy target before retrying."
        exit "$gate_rc"
    fi
    echo "[deploy] predeploy gate PASS"
else
    echo "[deploy] WARNING: $PREDEPLOY_GATE not found or not executable; skipping Phase 201 gate. This is unsafe for Spectrum deploys under v1.42+."
fi
```

If deploy.sh has a separate preflight section or a dispatcher pattern (multi-WAN), choose the integration point that ensures the gate runs ONCE before any /opt/wanctl write. Do NOT duplicate the gate invocation across loop iterations.

If the script uses `set -euo pipefail` and the gate exit-1 would auto-abort, the explicit `if ! ... ; then exit $?; fi` is still preferred for the operator-actionable echo line.

Do NOT modify any existing rsync flags or the unit-restart commands; the only change is the new gate block immediately before rsync.
  </action>
  <acceptance_criteria>
    - `grep -c 'phase201-predeploy-gate.sh' scripts/deploy.sh` returns >= 1.
    - `grep -c 'predeploy gate' scripts/deploy.sh` returns >= 1 (operator-visible log line).
    - `grep -c 'D-15' scripts/deploy.sh` returns >= 1 (decision-traceability comment).
    - `bash -n scripts/deploy.sh` returns 0.
    - The gate invocation is BEFORE the rsync command (verify by line-number ordering): `awk '/phase201-predeploy-gate/{p=NR} /rsync.*\\/opt\\/wanctl/{r=NR} END {exit (p>0 \&\& p < r)?0:1}' scripts/deploy.sh` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>bash -n scripts/deploy.sh &amp;&amp; grep -q 'phase201-predeploy-gate.sh' scripts/deploy.sh</automated>
  </verify>
  <done>deploy.sh invokes the predeploy gate before rsync; non-zero gate exit aborts deploy with operator-actionable message; D-15 traceability comment present.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator workstation -> deploy target via SSH | sudo-required to read /etc/wanctl/spectrum.yaml; operator's existing SSH key + sudo allow-list (Phase 200 reuse). |
| gate script -> python3 yaml.safe_load | yaml.safe_load is the safe loader (no arbitrary object construction); same shape as Phase 200 canary. |
| REMOTE_YAML_PATH env -> ssh argv | Validated by `^/[A-Za-z0-9._/-]+$` regex (Phase 200 Plan 11 pattern); rejects shell metacharacters. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-29 | Tampering | Operator passes `REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml; rm -rf /` | mitigate | `validate_remote_yaml_path` regex `^/[A-Za-z0-9._/-]+$` rejects shell metacharacters; gate aborts with EXIT_ABORT before SSH invocation. |
| T-201-30 | Spoofing | Auto-strip silently removes operator-curated keys without audit trail | mitigate | RESEARCH §9 Option B chosen (fail-closed, NOT auto-strip). Operator action required. |
| T-201-31 | Repudiation | Gate logs nothing on PASS, so operators don't know it ran | mitigate | log_info "PASS" line; deploy.sh prints "[deploy] predeploy gate PASS". |
| T-201-32 | Information Disclosure | Gate output reveals YAML contents in CI logs | accept | YAML contains operator config, not secrets; output is bool flags + operator-actionable messages, not raw YAML. |
| T-201-33 | Tampering | Gate skipped via missing executable bit -> deploy proceeds with v1.41 keys live under v1.42 | mitigate | deploy.sh prints WARNING when gate not executable; operator-visible. Acceptance gate: `test -x scripts/phase201-predeploy-gate.sh` enforced in Task 1. |
| T-201-34 | DoS | Remote python3+pyyaml missing -> gate hangs | mitigate | SSH ConnectTimeout=5 + BatchMode=yes ensures fast-fail; abort with operator-actionable message (closes WR-02). |
| T-201-35 | Tampering | Gate deletes or modifies the target YAML | accept | Gate uses `sudo cat`, not edit; no write paths in the script (verified by grep `sudo (rm|tee|sed|cp|mv)` returning 0). |
</threat_model>

<verification>
- Gate script exists, executable, syntax-clean.
- All TestPredeployGate cases green.
- deploy.sh invokes gate before rsync.
- WR-02 closed (remote-deps precheck).
- Path-validation regex blocks shell injection.
- Auto-strip path is intentionally absent (Option B).
</verification>

<success_criteria>
- D-15 fail-closed predeploy gate operational.
- Operator-actionable BLOCK messages cite specific keys and remediation paths.
- Three-way exit (PASS/BLOCK/ABORT) discriminates between bad-YAML (recoverable by operator) and bad-environment (recoverable by ops setup).
- WR-02 closed.
- Test contract from Plan 201-02 fully satisfied.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-07-SUMMARY.md` listing: gate script line count, the three exit conditions and their messages, deploy.sh integration point line number, test pass count, and a one-line confirmation that auto-strip is NOT implemented.
</output>

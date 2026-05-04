---
phase: 201-docsis-aware-ul-congestion-control
plan: 08
type: execute
wave: 5
depends_on: [02, 06]
files_modified:
  - scripts/phase200-saturation-canary.sh
  - scripts/phase200-saturation-canary.env.example
  - tests/test_phase200_canary_script.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-5, canary, d-12, fail-closed, env-yaml-cross-check, health-probe]

must_haves:
  truths:
    - "Canary preflight cross-checks env vars PHASE201_DOCSIS_MODE and PHASE201_SETPOINT_MBPS against deployed YAML; ABORTs on mismatch with named verdict reasons (REVIEWS HIGH-6: missing env vars ABORT for Phase 201 runs unless explicit PHASE201_LEGACY_MODE=true is set; PHASE201_LEGACY_MODE=true mutually-exclusive with PHASE201_DOCSIS_MODE=true — both set ABORTs)"
    - "Canary preflight asserts /health.wans[0].upload.docsis_mode_active is present-and-true with three-branch logic (absent / false / true / invalid)"
    - "Canary preflight prechecks remote python3+pyyaml availability (closes WR-02)"
    - "Canary capture loop records cake_signal.upload.max_delay_delta_us at the existing 1 Hz cadence (closes 201-01-CORPUS-AUDIT.md gap for v1.43+ replay corpus)"
    - "env-template gains PHASE201_DOCSIS_MODE and PHASE201_SETPOINT_MBPS commented examples"
    - "All TestPhase201Preflight cases pass (six cases from Plan 201-02 Wave 0 stubs)"
    - "Pre-existing canary self-tests still pass (no regression to Phase 200 hardening)"
  artifacts:
    - path: scripts/phase200-saturation-canary.sh
      provides: "D-12 preflight extension: env-vs-YAML cross-check for new keys; /health DOCSIS-mode probe; remote-deps precheck; max_delay_delta_us capture"
      contains: "PHASE201_DOCSIS_MODE"
    - path: scripts/phase200-saturation-canary.env.example
      provides: "Operator-facing env template additions"
      contains: "PHASE201_DOCSIS_MODE"
    - path: tests/test_phase200_canary_script.py
      provides: "TestPhase201Preflight class — six green cases"
      contains: "TestPhase201Preflight"
  key_links:
    - from: "scripts/phase200-saturation-canary.sh:328-362"
      to: "/etc/wanctl/spectrum.yaml on deploy target"
      via: "ssh sudo cat | python3 yaml.safe_load"
      pattern: "PHASE201_DOCSIS_MODE"
    - from: "scripts/phase200-saturation-canary.sh capture loop"
      to: "/health.wans[0].cake_signal.upload.max_delay_delta_us"
      via: "jq filter add for the new field at 1 Hz"
      pattern: "max_delay_delta_us"
---

<objective>
Wave 4 canary preflight extension. Implements D-12 by extending the Phase 200 saturation canary script with: (a) env-vs-YAML cross-check for PHASE201_DOCSIS_MODE and PHASE201_SETPOINT_MBPS; (b) `/health` DOCSIS-mode probe with three-branch validation (absent / false / true / invalid); (c) remote python3+pyyaml availability precheck (closes WR-02); (d) `max_delay_delta_us` capture in the loaded-window NDJSON (per 201-01-CORPUS-AUDIT.md gap finding).

Per D-11 reuse mandate: extend, do NOT fork. The Phase 200 script's bug-fix history (logger silent-drop, `/health` field assumption, env-var false-PASS regression `dd67493 -> 43838f4`) is preserved.

Plan 201-02 wrote test stubs in tests/test_phase200_canary_script.py with `pytest.skip()` guards. This plan removes those skips by implementing the preflight extensions and self-test dispatch.

Output: Extended canary script; updated env template; six new self-test cases green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md
@scripts/phase200-saturation-canary.sh
@scripts/phase200-saturation-canary.env.example
</context>

<interfaces>
<!-- Existing patterns to mirror VERBATIM. -->

YAML probe pattern (lines 328-338): SSH+sudo+python3 yaml.safe_load with json.dumps output captured via jq.

Mismatch ABORT pattern (lines 352-361): `[[ "$YAML_FLOOR" != "$PHASE200_UL_FLOOR_MBPS" ]] -> log_abort + write_abort_verdict + exit $EXIT_ABORT`.

Self-test dispatch (Phase 200 Plan 11): script accepts `--self-test <subcommand>` for pytest invocation; subcommands include preflight-yaml, env-validation, etc.

/health three-branch (RESEARCH Pitfall 7):
  absent (key missing) -> ABORT verdict "health_docsis_key_absent"  (deploy didn't happen)
  false  (key present, false) -> ABORT verdict "health_docsis_false"  (wrong WAN or stale binary)
  true   -> log_info "Preflight: /health confirms docsis_mode_active=true" + proceed
  other  -> ABORT verdict "health_docsis_invalid"

Capture-loop addition: `jq` filter currently extracts a fixed shape from /health; extend it to also include `cake_signal.upload.max_delay_delta_us` (PATTERNS.md confirms field is populated by CakeSignalSnapshot).
</interfaces>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend YAML probe + add /health DOCSIS-mode probe + remote-deps precheck</name>
  <files>scripts/phase200-saturation-canary.sh, scripts/phase200-saturation-canary.env.example</files>
  <read_first>
    - scripts/phase200-saturation-canary.sh (full read; locate via grep first: `grep -n "fetch_health_sample\|YAML_PROBE\|YAML_FLOOR\|YAML_CEIL\|capture_health_ndjson\|--self-test\|write_abort_verdict\|EXIT_ABORT" scripts/phase200-saturation-canary.sh`)
    - scripts/phase200-saturation-canary.env.example (full file)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "scripts/phase200-saturation-canary.sh (extend lines 314-362)" + "scripts/phase200-saturation-canary.env.example (extend)"
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md Pitfall 7 (three-branch health probe), §11 / WR-02 (remote-deps precheck)
    - tests/test_phase200_canary_script.py — TestPhase201Preflight (the contract this task satisfies)
  </read_first>
  <action>
PRECHECK FIRST — read the script and identify:
- Line ranges of YAML_PROBE python heredoc (~328-338)
- Line ranges of mismatch-ABORT block (~352-361)
- Where `fetch_health_sample` is defined (used for `/health` probe)
- Where `--self-test` dispatcher branch lives (Phase 200 Plan 11 added it)
- Whether a remote python3+pyyaml precheck already exists

Apply these edits:

1. **YAML probe extension** (around line 328-338): inside the python heredoc, extend the `print(json.dumps({...}))` shape to include the two new keys:

```bash
YAML_PROBE="$(ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
    "sudo cat -- '${REMOTE_YAML_PATH}'" 2>/dev/null \
    | python3 -c '
import sys, json, yaml
try:
    d = yaml.safe_load(sys.stdin)
    ul = d["continuous_monitoring"]["upload"]
    print(json.dumps({
        "floor": ul["floor_mbps"],
        "ceiling": ul["ceiling_mbps"],
        "docsis_mode": ul.get("docsis_mode", False),
        "setpoint_mbps": ul.get("setpoint_mbps"),
    }))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
' 2>/dev/null)"
```

2. **Mismatch ABORT block** (after the existing floor/ceiling mismatch checks, around line 361): append two new mismatch checks:

```bash
YAML_DOCSIS="$(printf '%s' "$YAML_PROBE" | jq -r '.docsis_mode')"
YAML_SETPOINT="$(printf '%s' "$YAML_PROBE" | jq -r '.setpoint_mbps // ""')"
if [[ -n "${PHASE201_DOCSIS_MODE:-}" ]]; then
    # Normalize boolean comparison: YAML emits 'true'/'false', env may emit 'True'/'true'/'1'.
    expected="$(printf '%s' "$PHASE201_DOCSIS_MODE" | tr '[:upper:]' '[:lower:]')"
    if [[ "$YAML_DOCSIS" != "$expected" ]]; then
        log_abort "PHASE201_DOCSIS_MODE=${PHASE201_DOCSIS_MODE} does not match deployed YAML docsis_mode=${YAML_DOCSIS} at ${PHASE200_REMOTE_YAML_SSH}"
        write_abort_verdict "env_yaml_docsis_mode_mismatch"
        exit "$EXIT_ABORT"
    fi
fi
if [[ -n "${PHASE201_SETPOINT_MBPS:-}" ]]; then
    if [[ "$YAML_SETPOINT" != "$PHASE201_SETPOINT_MBPS" ]]; then
        log_abort "PHASE201_SETPOINT_MBPS=${PHASE201_SETPOINT_MBPS} does not match deployed YAML setpoint_mbps=${YAML_SETPOINT} at ${PHASE200_REMOTE_YAML_SSH}"
        write_abort_verdict "env_yaml_setpoint_mismatch"
        exit "$EXIT_ABORT"
    fi
fi
```

**REVIEWS HIGH-6 (2026-05-04) — fail-closed env enforcement.** The new env vars are OPTIONAL ONLY when the operator explicitly opts into legacy-mode comparison via `PHASE201_LEGACY_MODE=true` (e.g., A/B against v1.40 binary). For Phase 201 deploys, missing `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` MUST abort. Without this, the canary silently no-ops the DOCSIS-mode probe AND mismatch checks while still claiming PASS.

Add this block at the TOP of the canary preflight section (BEFORE any YAML probe or /health probe runs):

```bash
# REVIEWS HIGH-6 (2026-05-04): fail-closed env enforcement for Phase 201.
# A Phase 201 canary run that forgets to declare DOCSIS-mode + setpoint
# would silently no-op the new probes and falsely PASS — the same fail-OPEN
# pattern Codex caught in Phase 200 (dd67493 -> 43838f4). Mutual exclusion
# of PHASE201_LEGACY_MODE and PHASE201_DOCSIS_MODE prevents accidental
# both-set drift.
if [[ "${PHASE201_LEGACY_MODE:-}" == "true" && "${PHASE201_DOCSIS_MODE:-}" == "true" ]]; then
    log_abort "PHASE201_LEGACY_MODE=true and PHASE201_DOCSIS_MODE=true are mutually exclusive; pick one"
    write_abort_verdict "phase201_env_legacy_and_docsis_both_set"
    exit "$EXIT_ABORT"
fi
if [[ "${PHASE201_LEGACY_MODE:-}" != "true" ]]; then
    if [[ -z "${PHASE201_DOCSIS_MODE:-}" ]]; then
        log_abort "PHASE201_DOCSIS_MODE must be set for Phase 201 canary runs (set PHASE201_LEGACY_MODE=true to opt into legacy A/B comparison instead)"
        write_abort_verdict "phase201_env_docsis_mode_missing"
        exit "$EXIT_ABORT"
    fi
    if [[ -z "${PHASE201_SETPOINT_MBPS:-}" ]]; then
        log_abort "PHASE201_SETPOINT_MBPS must be set for Phase 201 canary runs (set PHASE201_LEGACY_MODE=true to opt into legacy A/B comparison instead)"
        write_abort_verdict "phase201_env_setpoint_missing"
        exit "$EXIT_ABORT"
    fi
fi
```

When the canary is invoked from Plan 11 in Phase 201 mode, both `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12` MUST be exported in the env file (Plan 11 Task 2 step 1 already does this — verify the env file template before launch).

3. **/health DOCSIS-mode three-branch probe** (insert AFTER the existing /health shape check around line 312, BEFORE the YAML_PROBE block; or place it just BEFORE the loaded-window capture begins — wherever fetch_health_sample is callable):

```bash
log_info "Preflight: /health DOCSIS-mode probe (three-branch)"
HEALTH_DOCSIS="$(fetch_health_sample | jq -r '.wans[0].upload.docsis_mode_active // "absent"')"
case "$HEALTH_DOCSIS" in
    absent)
        log_abort "/health.wans[0].upload.docsis_mode_active key absent — deploy did not happen or v1.42 binary not running"
        write_abort_verdict "health_docsis_key_absent"
        exit "$EXIT_ABORT"
        ;;
    false)
        log_abort "/health.wans[0].upload.docsis_mode_active=false — wrong WAN or stale binary (Spectrum should be true under v1.42)"
        write_abort_verdict "health_docsis_false"
        exit "$EXIT_ABORT"
        ;;
    true)
        log_info "Preflight: /health confirms docsis_mode_active=true"
        ;;
    *)
        log_abort "/health.wans[0].upload.docsis_mode_active=${HEALTH_DOCSIS} (expected true|false|absent)"
        write_abort_verdict "health_docsis_invalid"
        exit "$EXIT_ABORT"
        ;;
esac
```

NOTE: this probe should be GATED on `PHASE201_DOCSIS_MODE` being set to `true` so the canary remains usable for legacy v1.41 verification too. Wrap the case block in `if [[ "${PHASE201_DOCSIS_MODE:-}" == "true" ]]; then ... fi`.

4. **Remote python3+pyyaml precheck** (closes WR-02). Insert IMMEDIATELY BEFORE the YAML_PROBE block:

```bash
log_info "Preflight: checking remote python3+pyyaml availability on ${REMOTE_SSH_TARGET}"
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_SSH_TARGET" \
        'python3 -c "import yaml" 2>/dev/null'; then
    log_abort "Remote python3+pyyaml not available on ${REMOTE_SSH_TARGET}; YAML probe cannot proceed"
    write_abort_verdict "remote_python_yaml_missing"
    exit "$EXIT_ABORT"
fi
```

5. **Self-test dispatch additions** (Phase 200 Plan 11 pattern): add new sub-commands so test_phase200_canary_script.py can exercise the new preflight branches. Locate the existing `--self-test` dispatcher and add cases:
   - `--self-test phase201-preflight-docsis-mode-match` (simulate env+yaml match -> exit 0)
   - `--self-test phase201-preflight-docsis-mode-mismatch` (simulate mismatch -> exit non-zero with verdict reason)
   - `--self-test phase201-preflight-setpoint-mismatch`
   - `--self-test phase201-preflight-health-absent`
   - `--self-test phase201-preflight-health-false`
   - `--self-test phase201-preflight-remote-python-missing`

Each self-test sub-command should NOT exec real ssh/iperf3; instead, set up env vars to simulate the failure, then exit with the same verdict the live path would produce. Mirror the Phase 200 self-test pattern verbatim.

6. **env.example additions**:

```bash
# Phase 201 D-12 additions (env-declared expectation; canary preflight
# cross-checks against deployed YAML and ABORTs on mismatch).
# Also gates the /health DOCSIS-mode three-branch probe.
# Optional: leave empty for legacy (non-DOCSIS) canary runs.
# Example (Spectrum after Phase 201 deploy):
#   PHASE201_DOCSIS_MODE=true
#   PHASE201_SETPOINT_MBPS=12
PHASE201_DOCSIS_MODE=""
PHASE201_SETPOINT_MBPS=""
```

CRITICAL: do NOT change any existing behavior when PHASE201_* env vars are empty. Phase 200 canary semantics must be preserved for legacy A/B comparisons against v1.40/v1.41 binaries.
  </action>
  <acceptance_criteria>
    - `grep -c 'PHASE201_DOCSIS_MODE' scripts/phase200-saturation-canary.sh` returns >= 3 (env extraction + comparison + self-test).
    - `grep -c 'PHASE201_SETPOINT_MBPS' scripts/phase200-saturation-canary.sh` returns >= 3.
    - `grep -c 'env_yaml_docsis_mode_mismatch' scripts/phase200-saturation-canary.sh` returns 1.
    - `grep -c 'env_yaml_setpoint_mismatch' scripts/phase200-saturation-canary.sh` returns 1.
    - `grep -c 'health_docsis_key_absent' scripts/phase200-saturation-canary.sh` returns 1.
    - `grep -c 'health_docsis_false' scripts/phase200-saturation-canary.sh` returns 1.
    - `grep -c 'health_docsis_invalid' scripts/phase200-saturation-canary.sh` returns 1.
    - `grep -c 'remote_python_yaml_missing' scripts/phase200-saturation-canary.sh` returns 1.
    - **REVIEWS HIGH-6:** `grep -c 'phase201_env_docsis_mode_missing' scripts/phase200-saturation-canary.sh` returns 1.
    - **REVIEWS HIGH-6:** `grep -c 'phase201_env_setpoint_missing' scripts/phase200-saturation-canary.sh` returns 1.
    - **REVIEWS HIGH-6:** `grep -c 'phase201_env_legacy_and_docsis_both_set' scripts/phase200-saturation-canary.sh` returns 1.
    - **REVIEWS HIGH-6:** `grep -c 'PHASE201_LEGACY_MODE' scripts/phase200-saturation-canary.sh` returns >= 2 (legacy opt-in flag honored, mutually-exclusive check). `grep -c 'PHASE201_LEGACY_MODE' scripts/phase200-saturation-canary.env.example` returns >= 1 (operator-facing doc).
    - `grep -c 'PHASE201_DOCSIS_MODE' scripts/phase200-saturation-canary.env.example` returns >= 1.
    - `grep -c 'PHASE201_SETPOINT_MBPS' scripts/phase200-saturation-canary.env.example` returns >= 1.
    - `bash -n scripts/phase200-saturation-canary.sh` returns 0.
    - `bash -n scripts/phase200-saturation-canary.env.example` returns 0 (or `python3 -c "with open(...): pass"` — env file is sourced).
    - All TestPhase201Preflight cases pass: `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q -k TestPhase201Preflight` returns 0.
    - Pre-existing canary tests still green: `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>bash -n scripts/phase200-saturation-canary.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q</automated>
  </verify>
  <done>D-12 preflight extension live; six new self-test cases green; pre-existing canary tests unchanged; WR-02 closed; env template documented.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Extend canary capture loop to record cake_signal.upload.max_delay_delta_us at 1 Hz</name>
  <files>scripts/phase200-saturation-canary.sh</files>
  <read_first>
    - scripts/phase200-saturation-canary.sh — locate via grep: `grep -n "capture_health_ndjson\|fetch_health_sample\|jq -c\|loaded_capture\|HEALTH_POLL_HZ" scripts/phase200-saturation-canary.sh`
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md (the gap finding: max_delay_delta_us absent in current capture)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §8 ("Recommended Phase 201 replay setup" item 3)
  </read_first>
  <action>
Locate the capture-loop function. Likely shape:

```bash
capture_health_ndjson() {
    local out="$1"
    local duration_sec="$2"
    local interval_sec=$(awk "BEGIN { print 1 / $HEALTH_POLL_HZ }")
    local end=$((SECONDS + duration_sec))
    while [[ $SECONDS -lt $end ]]; do
        fetch_health_sample >> "$out"
        sleep "$interval_sec"
    done
}
```

If `fetch_health_sample` invokes `curl <health_url> | jq -c '.'` directly, the max_delay_delta_us field is already passed through (it's part of /health.wans[0].cake_signal.upload — confirmed during Plan 201-01 audit). NO change needed if the capture is "raw `/health` snapshot saved verbatim".

If the capture pipes through a jq filter that explicitly selects fields, locate the filter and ensure it includes `cake_signal` deeply. The simplest expansion:

```bash
fetch_health_sample() {
    curl -sS --max-time "$HEALTH_FETCH_TIMEOUT_SEC" "$PHASE200_SPECTRUM_HEALTH_URL" \
        | jq -c '.'   # full snapshot — preserve all keys including cake_signal.upload.max_delay_delta_us
}
```

If the existing fetch already does `jq -c '.'`, this task is a no-op verification that the captured field is present. Verify by spot-checking:

```bash
# Run a one-shot capture in self-test mode (or via a test fixture); assert the field is present
bash scripts/phase200-saturation-canary.sh --self-test capture-shape | jq -e '.wans[0].cake_signal.upload.max_delay_delta_us != null'
```

If the field is NOT present at fetch time, this means production /health doesn't expose it (it's an internal CakeSignalSnapshot field). In that case, Plan 201-05 needs to add it as part of the additive /health fields — coordinate via a follow-up task in this plan or fold into the SUMMARY for Plan 201-05.

**REVIEWS MED-6 (2026-05-04) — disposition: scripts-only stays.**

The replanner verified that `max_delay_delta_us` is ALREADY serialized in `/health.wans[].cake_signal.upload.max_delay_delta_us`:

- `src/wanctl/cake_signal.py:123` defines `max_delay_delta_us: int = 0` as a `CakeSignalSnapshot` dataclass field.
- `src/wanctl/wan_controller.py:4511` serializes the snapshot wholesale (`"upload": self._ul_cake_snapshot`) — every dataclass field flows through.
- `src/wanctl/wan_controller.py:4553` already references `self._dl_cake_snapshot.max_delay_delta_us` for the DL arbitration field, confirming the dataclass->JSON path works.

Therefore, this task is **scripts-only verification + documentation**:

1. Confirm the field is in `/health` output. From the deploy target during Plan 11:
   ```
   ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" | jq '.wans[0].cake_signal.upload.max_delay_delta_us'
   ```
   Expect a non-null integer.

2. Confirm capture loop preserves the field. The canary's `fetch_health_sample` uses `jq -c '.'` (full snapshot, no field-selection filter), so the field flows through unchanged. Verify by reading the existing `fetch_health_sample` body.

3. Update 201-08-SUMMARY.md to record: "max_delay_delta_us already serialized via cake_signal.upload (CakeSignalSnapshot dataclass); no wan_controller.py modification needed; v1.43+ replay corpus picks it up automatically from existing canary captures."

`files_modified` for THIS task is therefore the canary script ONLY (no wan_controller.py modification needed). If during execution the assumption proves wrong (field absent in /health output despite the dataclass + serialization audit), STOP and re-route via gap closure rather than expanding files_modified mid-flight — the dataclass audit was deterministic, so a discrepancy would indicate a deeper drift.
  </action>
  <acceptance_criteria>
    - Production `/health` payload contains `wans[].cake_signal.upload.max_delay_delta_us` (verify by reading src/wanctl/wan_controller.py and confirming the field is serialized; OR add it as part of this task if absent).
    - If a code change was needed in wan_controller.py to expose max_delay_delta_us, SAFE-05 baseline updated and `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v` returns 0.
    - Self-test capture exposes the field: `bash scripts/phase200-saturation-canary.sh --self-test capture-shape 2>&1 | grep -q max_delay_delta_us` (if the self-test sub-command is implemented; otherwise verify via direct unit test in tests/test_wan_controller.py).
    - **REVIEWS MED-6:** 201-08-SUMMARY.md documents the disposition: max_delay_delta_us already serialized via `cake_signal.upload` (CakeSignalSnapshot dataclass at cake_signal.py:123 + serialization at wan_controller.py:4511); files_modified for this task remains scripts-only. Verify with: `grep -c 'CakeSignalSnapshot dataclass' .planning/phases/201-docsis-aware-ul-congestion-control/201-08-SUMMARY.md` returns >= 1.
  </acceptance_criteria>
  <verify>
    <automated>grep -q 'max_delay_delta_us' src/wanctl/wan_controller.py &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v</automated>
  </verify>
  <done>cake_signal.upload.max_delay_delta_us present in /health output and therefore in canary capture NDJSON; SAFE-05 baseline absorbed any new occurrence; 201-08-SUMMARY documents the disposition.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator env file -> canary script | Env vars carry expected YAML state; script cross-checks against actual deploy. Same trust boundary Phase 200 hardened. |
| canary script -> /health endpoint | Read-only HTTP fetch; no auth. Same as Phase 200. |
| canary script -> deploy-target SSH | sudo cat /etc/wanctl/spectrum.yaml; existing operator SSH key + sudo allow-list. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-36 | Tampering | Operator forgets to set PHASE201_DOCSIS_MODE -> canary proceeds against legacy v1.41 binary thinking it's v1.42 | mitigate | /health DOCSIS-mode probe is gated on `PHASE201_DOCSIS_MODE=true`; if env unset, no probe runs (legacy compat). When set, three-branch probe asserts docsis_mode_active=true. Operator-actionable verdict on mismatch. |
| T-201-37 | Tampering | Env false-PASS regression (Phase 200 dd67493 family) | mitigate | New env vars use the SAME pattern as PHASE200_UL_FLOOR_MBPS / PHASE200_UL_CEILING_MBPS — env-declared expectation + SSH probe + jq comparison + abort. Self-test cases cover mismatch paths. |
| T-201-38 | Tampering | YAML probe shell-injection via REMOTE_YAML_PATH | mitigate | Inherits Phase 200 Plan 11 `validate_remote_yaml_path` regex check (already in canary script before line 322). |
| T-201-39 | Repudiation | Verdict reasons drift from documented set | mitigate | Acceptance grep enforces all six new verdict reason strings present. Phase 200 verdict.json schema preserved. |
| T-201-40 | DoS | Remote python3+pyyaml missing -> canary hangs | mitigate | Task 1 adds remote-deps precheck (closes WR-02); ConnectTimeout=5 + BatchMode=yes ensures fast-fail. |
</threat_model>

<verification>
- TestPhase201Preflight green (six cases).
- Pre-existing canary tests still green.
- Six new verdict reasons grep-asserted present.
- bash -n syntax-clean.
- env.example documents new optional vars.
- Capture loop records max_delay_delta_us (either pre-existing or added in this plan).
</verification>

<success_criteria>
- D-12 preflight extension lands cleanly.
- D-11 reuse mandate honored (no fork).
- WR-02 closed.
- Three-branch /health probe per RESEARCH Pitfall 7.
- Operator can opt out by leaving PHASE201_* empty (legacy compat).
- v1.43+ replay corpus has max_delay_delta_us baked in.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-08-SUMMARY.md` with: lines added in canary script + env template; the six new verdict reason strings; bash -n status; full canary self-test pass count; max_delay_delta_us disposition (pre-existing vs added).
</output>

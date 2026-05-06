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
    - "REVIEWS HIGH-5 closure: canary script's verdict-decision is gated on floor_hit_cycles_total_delta_loaded_window == 0 AND-coupled with ul_floor_hits_during_load == 0 (snapshot). Disagreement between the two produces FAIL with a diagnostic verdict reason, NOT PASS. verdict.json publishes start/end/delta of the counter and a `primary_gate` field naming counter-delta as authoritative. The legacy single-gate `[[ snapshot == 0 ]] && write_pass_verdict` pattern is removed entirely."
    - "env-template gains PHASE201_DOCSIS_MODE and PHASE201_SETPOINT_MBPS commented examples"
    - "All TestPhase201Preflight cases pass (six cases from Plan 201-02 Wave 0 stubs)"
    - "All TestPhase201CounterDeltaVerdict cases pass (six cases — pass / primary_fail / secondary_disagreement / both_fail / field_missing / negative_delta)"
    - "Pre-existing canary self-tests still pass (no regression to Phase 200 hardening)"
  artifacts:
    - path: scripts/phase200-saturation-canary.sh
      provides: "D-12 preflight extension: env-vs-YAML cross-check for new keys; /health DOCSIS-mode probe; remote-deps precheck; max_delay_delta_us capture; REVIEWS HIGH-5 counter-delta verdict-decision wiring"
      contains: "floor_hit_cycles_total_delta_loaded_window"
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
# Phase 201 runs are fail-closed: these must be set to true/12.
# Legacy A/B runs must explicitly set PHASE201_LEGACY_MODE=true instead.
# Example (Spectrum after Phase 201 deploy):
#   PHASE201_DOCSIS_MODE=true
#   PHASE201_SETPOINT_MBPS=12
PHASE201_DOCSIS_MODE=""
PHASE201_SETPOINT_MBPS=""
PHASE201_LEGACY_MODE=""
```

CRITICAL (Codex HIGH #5): Phase 201 canary runs fail closed when `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` is empty. Preserve legacy A/B behavior only behind explicit `PHASE201_LEGACY_MODE=true`; do not treat empty Phase 201 vars as an implicit legacy run.
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

<task type="auto" tdd="true">
  <name>Task 3: Wire floor_hit_cycles_total counter-delta into the verdict-decision logic (REVIEWS HIGH-5 closure — primary gate must actually GATE, not just be labeled "primary")</name>
  <files>scripts/phase200-saturation-canary.sh, tests/test_phase200_canary_script.py</files>
  <read_first>
    - scripts/phase200-saturation-canary.sh (full read; locate via grep first: `grep -n "write_pass_verdict\|write_fail_verdict\|write_abort_verdict\|verdict\.json\|ul_floor_hits_during_load\|verdict_pass\|verdict_fail" scripts/phase200-saturation-canary.sh`)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md "Top HIGH Concerns #5" (verdict-script vs verdict-interpreter separation)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-04-controller-core-PLAN.md (counter increment sites — confirms self.upload.floor_hit_cycles is monotonic per-process)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-05-wan-controller-and-health-PLAN.md (confirms `/health.wans[0].upload.floor_hit_cycles_total` is an additive runtime field that mirrors self.upload.floor_hit_cycles)
    - tests/test_phase200_canary_script.py (existing test file Plan 02 stubbed; locate the new TestPhase201CounterDeltaVerdict test class added by Plan 02-T2)
  </read_first>
  <action>
**Purpose (REVIEWS HIGH-5 closure):** The HIGH-5 fix added a `floor_hit_cycles_total` counter and labeled it the "PRIMARY VALN-06 gate" in Plan 11. But the canary script — the actual agent that writes `verdict.json` and decides `verdict: pass/fail` — was not amended to gate on the counter delta. This task closes the loop: the script's verdict-decision uses counter_delta as the gate, AND-coupled with the legacy 1 Hz snapshot count. Disagreement between the two is itself a FAIL with a diagnostic verdict reason.

**Step 1 — Snapshot the counter at loaded-window boundaries.**

The canary script already brackets the loaded window with start/end timestamps (`LOADED_START_TS`, `LOADED_END_TS` — search the script for these). Add two new captures:

```bash
# Around the existing LOADED_START_TS capture in the canary script:
LOADED_START_FLOOR_HIT_CYCLES_TOTAL=$(fetch_health_sample | jq -r '.wans[0].upload.floor_hit_cycles_total // "missing"')
if [[ "$LOADED_START_FLOOR_HIT_CYCLES_TOTAL" == "missing" ]]; then
    write_abort_verdict "phase201_floor_hit_counter_field_missing"
    exit $EXIT_ABORT
fi

# Around the existing LOADED_END_TS capture:
LOADED_END_FLOOR_HIT_CYCLES_TOTAL=$(fetch_health_sample | jq -r '.wans[0].upload.floor_hit_cycles_total // "missing"')
if [[ "$LOADED_END_FLOOR_HIT_CYCLES_TOTAL" == "missing" ]]; then
    write_abort_verdict "phase201_floor_hit_counter_field_missing"
    exit $EXIT_ABORT
fi

FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW=$(( LOADED_END_FLOOR_HIT_CYCLES_TOTAL - LOADED_START_FLOOR_HIT_CYCLES_TOTAL ))
if (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW < 0 )); then
    # Counter went BACKWARDS — process restart mid-window or counter reset bug.
    # Treat as ABORT (cannot trust the gate).
    write_abort_verdict "phase201_floor_hit_counter_delta_negative"
    exit $EXIT_ABORT
fi
```

The "missing" branch closes the case where Plan 05's /health field somehow didn't ship (e.g., a partial deploy). The negative-delta branch closes the case where the controller process restarted mid-canary (counter would reset to 0). Both ABORT, not FAIL — they're environment problems, not control-model failures.

**Step 2 — Gate verdict-decision on counter delta AND-coupled with the legacy snapshot count.**

Locate the existing verdict-decision block (likely a function `decide_loaded_window_verdict` or inline near `write_pass_verdict` / `write_fail_verdict` calls — grep `ul_floor_hits_during_load` to find the existing site). Replace its single-condition gate with the AND-coupled gate:

```bash
# Existing pattern (Phase 200): verdict: pass iff ul_floor_hits_during_load == 0
# REVIEWS HIGH-5 amended pattern: verdict: pass iff BOTH gates green AND no disagreement.

if [[ "$UL_FLOOR_HITS_DURING_LOAD" == "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW == 0 )); then
    write_pass_verdict
elif [[ "$UL_FLOOR_HITS_DURING_LOAD" == "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW > 0 )); then
    # 1 Hz snapshot missed sub-second floor touches the cycle-fidelity counter caught.
    # This is the EXACT scenario REVIEWS HIGH-5 was designed to catch — the legacy
    # snapshot would have written verdict: pass and silently failed VALN-06.
    # FAIL with a diagnostic reason so operators see the gap.
    write_fail_verdict "primary_gate_floor_hit_cycles_delta_${FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW}_snapshot_zero_disagreement"
elif [[ "$UL_FLOOR_HITS_DURING_LOAD" != "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW == 0 )); then
    # Snapshot saw floor at a 1 Hz tick but counter delta is 0 — impossible unless
    # /health.upload.floor_hit_cycles_total mirroring lags or there's a serialization
    # bug. Treat as FAIL with a diagnostic so the bug surfaces.
    write_fail_verdict "secondary_gate_disagreement_snapshot_${UL_FLOOR_HITS_DURING_LOAD}_counter_delta_zero"
else
    # Both gates report floor hits — clean FAIL.
    write_fail_verdict "ul_floor_hits_during_load_${UL_FLOOR_HITS_DURING_LOAD}_counter_delta_${FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW}"
fi
```

Both single-gate-zero-disagreement cases FAIL (not pass), making counter delta a true gate. The legacy `ul_floor_hits_during_load == 0` path alone NEVER produces `verdict: pass` — only the AND-coupled green case does.

**Step 3 — Extend the verdict.json schema.**

Update `write_pass_verdict` and `write_fail_verdict` (or whatever the existing helpers are named — grep for them) to also emit:

```json
{
  "verdict": "pass" | "fail" | "abort",
  "reason": "...",
  "ul_floor_hits_during_load": <int>,                          // legacy 1 Hz snapshot count (SECONDARY)
  "floor_hit_cycles_total_loaded_window_start": <int>,         // NEW (HIGH-5)
  "floor_hit_cycles_total_loaded_window_end": <int>,           // NEW (HIGH-5)
  "floor_hit_cycles_total_delta_loaded_window": <int>,         // NEW (HIGH-5) — PRIMARY gate metric
  "primary_gate": "floor_hit_cycles_total_delta_loaded_window",// NEW — names the authoritative gate
  "primary_gate_value": <int>,                                 // NEW — copy of delta for convenience
  ...
}
```

The `primary_gate` string field is operator-readable proof that the script considers counter-delta authoritative; the value field makes operator dashboards trivial.

**Step 4 — Add self-tests via the existing `--self-test` dispatcher** (mirror the Phase 200 self-test pattern):

- `--self-test phase201-counter-delta-pass` — synthesizes start=100, end=100, snapshot=0; expect `verdict: pass`.
- `--self-test phase201-counter-delta-primary-fail` — synthesizes start=100, end=104 (4 hits, matching Phase 200 Attempt 3), snapshot=0; expect `verdict: fail` with reason `primary_gate_floor_hit_cycles_delta_4_snapshot_zero_disagreement`.
- `--self-test phase201-counter-delta-secondary-disagreement` — synthesizes start=100, end=100 (counter delta 0), snapshot=2; expect `verdict: fail` with reason starting `secondary_gate_disagreement`.
- `--self-test phase201-counter-delta-both-fail` — synthesizes start=100, end=104, snapshot=4; expect `verdict: fail` with reason `ul_floor_hits_during_load_4_counter_delta_4`.
- `--self-test phase201-counter-delta-field-missing` — synthesizes /health response with no `floor_hit_cycles_total` field; expect `verdict: abort` with reason `phase201_floor_hit_counter_field_missing`.
- `--self-test phase201-counter-delta-negative` — synthesizes start=100, end=80 (process restart mid-window); expect `verdict: abort` with reason `phase201_floor_hit_counter_delta_negative`.

Each self-test sub-command sets up env vars / mock /health responses and asserts the verdict.json output without invoking real ssh/iperf3.

**Step 5 — Pytest stubs** (Plan 02-T2 should have created `TestPhase201CounterDeltaVerdict` — extend it here):

Add 6 cases that drive the canary script's `--self-test` dispatcher and assert the verdict reasons. Pattern mirrors existing Phase 200 self-test pytest cases.

**Step 6 — env-template addition.**

Add to `scripts/phase200-saturation-canary.env.example`:
```
# Phase 201 (REVIEWS HIGH-5): cycle-fidelity floor-hit counter delta is the
# PRIMARY VALN-06 gate. The canary script reads /health.wans[0].upload.floor_hit_cycles_total
# at loaded-window start and end, and FAILS the canary if delta != 0
# regardless of the 1 Hz snapshot rate compare. No env var needed — the
# script reads /health directly.
```
  </action>
  <acceptance_criteria>
    - `grep -c 'floor_hit_cycles_total_delta_loaded_window' scripts/phase200-saturation-canary.sh` returns >= 4 (capture x2, gate x1, verdict.json field x1).
    - `grep -c 'phase201_floor_hit_counter_field_missing' scripts/phase200-saturation-canary.sh` returns >= 1 (ABORT path).
    - `grep -c 'phase201_floor_hit_counter_delta_negative' scripts/phase200-saturation-canary.sh` returns >= 1 (ABORT path).
    - `grep -c 'primary_gate_floor_hit_cycles_delta' scripts/phase200-saturation-canary.sh` returns >= 1 (FAIL reason for snapshot-zero counter-nonzero — the exact scenario HIGH-5 prevents).
    - `grep -c 'secondary_gate_disagreement' scripts/phase200-saturation-canary.sh` returns >= 1 (FAIL reason for snapshot-nonzero counter-zero diagnostic).
    - `grep -Ec '"primary_gate"\s*:\s*"floor_hit_cycles_total_delta_loaded_window"' scripts/phase200-saturation-canary.sh` returns >= 1 (verdict.json schema field that operators can grep on).
    - **No remaining single-gate verdict.** `grep -Ec 'write_pass_verdict\(\)' scripts/phase200-saturation-canary.sh` returns >= 1, but every call site is preceded within 5 lines by both `UL_FLOOR_HITS_DURING_LOAD` and `FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW` checks (verify via `awk` or manual inspection during code review). The legacy single-gate `[[ "$UL_FLOOR_HITS_DURING_LOAD" == "0" ]] && write_pass_verdict` pattern MUST NOT remain anywhere: `grep -Ec 'UL_FLOOR_HITS_DURING_LOAD.*==.*0.*&&.*write_pass_verdict' scripts/phase200-saturation-canary.sh` returns 0.
    - `bash -n scripts/phase200-saturation-canary.sh` returns 0.
    - All six new self-tests dispatch correctly and produce expected verdicts: `bash scripts/phase200-saturation-canary.sh --self-test phase201-counter-delta-pass | jq -e '.verdict == "pass"'`, `--self-test phase201-counter-delta-primary-fail | jq -e '.verdict == "fail" and (.reason | startswith("primary_gate_floor_hit_cycles_delta"))'`, etc.
    - Pytest: `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py::TestPhase201CounterDeltaVerdict -v` returns 0 (six cases green).
    - SAFE-05 baseline test still passes: `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v`.
  </acceptance_criteria>
  <verify>
    <automated>bash -n scripts/phase200-saturation-canary.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py::TestPhase201CounterDeltaVerdict -v &amp;&amp; ! grep -Ec 'UL_FLOOR_HITS_DURING_LOAD.*==.*0.*&amp;&amp;.*write_pass_verdict' scripts/phase200-saturation-canary.sh</automated>
  </verify>
  <done>The canary script's verdict-decision logic gates on `floor_hit_cycles_total_delta_loaded_window == 0` AND `ul_floor_hits_during_load == 0` (AND-coupled, with disagreement producing FAIL not PASS). verdict.json publishes the delta + start/end + primary_gate name. The "PRIMARY/SECONDARY" labeling in Plan 11 is now backed by actual gate logic in the verdict-writing code, not just operator-interpretation prose. REVIEWS HIGH-5 is now closed at the gate-deciding agent, not just at the gate-interpreting agent.</done>
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
| T-201-36 | Tampering | Operator forgets to set PHASE201_DOCSIS_MODE -> canary proceeds against legacy v1.41 binary thinking it's v1.42 | mitigate | Phase 201 mode aborts if `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` is unset. Legacy compatibility requires explicit `PHASE201_LEGACY_MODE=true`; when docsis mode is set, the three-branch /health probe asserts docsis_mode_active=true. Operator-actionable verdict on mismatch. |
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
- Operator can opt out only by setting PHASE201_LEGACY_MODE=true (legacy compat); empty PHASE201_* vars abort Phase 201 runs.
- v1.43+ replay corpus has max_delay_delta_us baked in.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-08-SUMMARY.md` with: lines added in canary script + env template; the six new verdict reason strings; bash -n status; full canary self-test pass count; max_delay_delta_us disposition (pre-existing vs added).
</output>

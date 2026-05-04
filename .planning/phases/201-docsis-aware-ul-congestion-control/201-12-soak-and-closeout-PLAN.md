---
phase: 201-docsis-aware-ul-congestion-control
plan: 12
type: execute
wave: 8
depends_on: [11]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
autonomous: false
requirements: [VALN-06]
tags: [phase-201, wave-8, soak, valn-06-watchdog, closeout, verification]

must_haves:
  truths:
    - "24h Spectrum UL regression soak completed against the v1.42.0 binary that passed Plan 201-11 canary"
    - "UL hysteresis suppression rate over the soak window is < 5/60s mean (D-14 watchdog threshold; no relaxation, no tightening)"
    - "soak-summary.json captures suppression rate, floor-hit count (must be 0), CAKE backlog distribution, and DOCSIS-state transitions"
    - "REVIEWS HIGH-5 (2026-05-04): soak verdict primary gate is `floor_hit_cycles_total` delta across the 24h window (end_value - start_value). Delta == 0 is required for VALN-06 watchdog PASS. The legacy `ul_hysteresis_suppression_rate_per_60s.mean < 5.0` gate is RETAINED as a SECONDARY watchdog signal."
    - "REVIEWS round-5 (2026-05-04): the PRIMARY gate is COLLECTIBLE — Step 1.5 (capture floor_hit_cycles_total at soak T+0, anchored to Plan 201-11 verdict.json `.floor_hit_cycles_total_loaded_window_end` with live `/health` fallback) is REQUIRED before the 24h wait begins. /health exposes only the current counter value; past values cannot be reconstructed at soak end. Skipping Step 1.5 makes the PRIMARY gate uncollectible, which is itself a fail-OPEN — Step 4 detects the missing T+0 baseline and authors `verdict: fail` with reason `soak_primary_gate_uncollectible_t0_baseline_missing`. Daemon restart mid-soak (negative delta) similarly invalidates the gate and produces `soak_primary_gate_uncollectible_negative_delta_<N>`."
    - "201-VERIFICATION.md records the closure verdict (passed/failed/blocked) with per-criterion evidence pointers"
    - "REQUIREMENTS.md flips VALN-06 to satisfied (or records the failure) with traceability to 201-VERIFICATION.md"
    - "STATE.md updated with phase closure (reflecting milestone v1.42 status)"
    - "201-VALIDATION.md `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
      provides: "Standardized soak metrics: suppression rate, floor hits, distribution stats"
      contains: "suppressions_per_60s_mean"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
      provides: "Phase 201 closure verdict + per-criterion evidence pointers"
      contains: "VALN-06"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
      provides: "Operator-readable soak outcome + closeout decisions"
      contains: "Soak verdict"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md"
      to: ".planning/REQUIREMENTS.md VALN-06 row"
      via: "VALN-06 satisfied / failed status references this VERIFICATION.md"
      pattern: "VALN-06"
---

<objective>
Wave 7 24h soak watchdog + phase closeout. The soak is the regression watchdog (NOT the verdict — Plan 201-11 canary is the verdict per VALN-06 closure shape). The soak validates that the new control mode behaves stably over 24h without spurious oscillation, with UL hysteresis suppression rate < 5/60s mean (D-14 unchanged from Phase 200 closure shape).

Per RESEARCH and CONTEXT: tightening to <2/60s is deferred to v1.43+; relaxing is forbidden. Same fail-closed shape: if soak fails, that's a regression signal — escalate to gap-closure planning.

After the soak passes, this plan finalizes phase closure: writes 201-VERIFICATION.md, flips REQUIREMENTS.md VALN-06 to satisfied, updates STATE.md, marks VALIDATION.md as nyquist-compliant.

Output: Soak capture + verdict; 201-VERIFICATION.md (canonical phase closure); REQUIREMENTS.md + STATE.md updated; VALIDATION.md frontmatter flipped to compliant.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Run 24h Spectrum UL regression soak; capture suppression-rate distribution</name>
  <what-built>
    Plan 201-11 canary passed: zero floor hits at setpoint=12. v1.42.0 is live in production. 24h watchdog window now begins.
  </what-built>
  <how-to-verify>
    Operator MUST execute:

    1. **Mark soak start time** (UTC ISO):
       ```
       echo "soak_start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /tmp/phase201-soak.env
       ```

    1.5. **CAPTURE PRIMARY-GATE BASELINE** (REVIEWS HIGH-5: this MUST happen at soak T+0 — `/health.upload.floor_hit_cycles_total` is a live in-process counter; past values cannot be reconstructed at soak end. Skipping this step makes the PRIMARY soak gate uncollectible, which itself is a fail-OPEN.):

       **Required invariants for `/tmp/phase201-soak.env`:** the file MUST contain ONLY `key=value` assignments after this step (no warnings, no commentary, no narration), so that Step 4's `source /tmp/phase201-soak.env` is a clean, deterministic load. All informational output goes to stderr. All values are validated as digit-only integers before being written. The provenance label is set from the code path that actually produced the value, NOT from a leftover variable.

       ```bash
       set -euo pipefail

       PHASE_DIR=.planning/phases/201-docsis-aware-ul-congestion-control
       ENV_FILE=/tmp/phase201-soak.env

       # Find the most recent canary verdict.json. `|| true` prevents set-e abort
       # on no-match; `2>/dev/null` suppresses ls's "no such file" stderr noise.
       CANARY_VERDICT=$(ls -1t "$PHASE_DIR"/canary/*/verdict.json 2>/dev/null | head -1 || true)

       FLOOR_HIT_T0=""
       SOURCE=""

       # Try anchor 1: Plan 201-11 verdict.json `.floor_hit_cycles_total_loaded_window_end`.
       # This is the canonical anchor — by construction, the canary's last counter
       # value is identical to soak T+0 (no cycles between canary loaded-window end
       # and soak start, modulo bounded deploy/restart time).
       if [[ -n "$CANARY_VERDICT" && -s "$CANARY_VERDICT" ]]; then
           candidate=$(jq -r '.floor_hit_cycles_total_loaded_window_end // empty' "$CANARY_VERDICT" 2>/dev/null || true)
           if [[ "$candidate" =~ ^[0-9]+$ ]]; then
               FLOOR_HIT_T0="$candidate"
               SOURCE="verdict.json:$CANARY_VERDICT"
           fi
       fi

       # Try anchor 2 (fallback): live /health sample. Only used when verdict.json
       # is missing OR predates Plan 08-T3 (field absent). Operator should be aware
       # this introduces deploy-latency drift between canary end and soak start.
       if [[ -z "$FLOOR_HIT_T0" ]]; then
           candidate=$(ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" 2>/dev/null \
               | jq -r '.wans[0].upload.floor_hit_cycles_total // empty' 2>/dev/null || true)
           if [[ "$candidate" =~ ^[0-9]+$ ]]; then
               FLOOR_HIT_T0="$candidate"
               SOURCE="live_health"
           fi
       fi

       # Hard-fail if neither anchor produced a valid integer. PRIMARY soak gate
       # is uncollectible; better to FAIL the procedure NOW than 24 hours from now.
       if [[ -z "$FLOOR_HIT_T0" ]]; then
           echo "ABORT: floor_hit_cycles_total_start unavailable from both verdict.json (${CANARY_VERDICT:-not found}) and live /health." >&2
           echo "ABORT: PRIMARY soak gate is uncollectible. Restore /health.upload.floor_hit_cycles_total (Plan 05) and/or fix verdict.json (Plan 08-T3), then re-run Step 1.5." >&2
           exit 2
       fi

       # Atomic append: only key=value lines go into the sourceable env file.
       # Commentary goes to stderr, NOT into $ENV_FILE.
       {
           echo "floor_hit_cycles_total_start=$FLOOR_HIT_T0"
           echo "floor_hit_cycles_total_start_source=\"$SOURCE\""
       } >> "$ENV_FILE"

       # Verify the env file is clean-sourceable before declaring Step 1.5 complete.
       # If the file has any non-key=value lines (e.g., from a prior buggy run),
       # this catches it now.
       if ! bash -n <(grep -v '^[[:space:]]*$\|^[[:space:]]*#' "$ENV_FILE"); then
           echo "ABORT: $ENV_FILE has non-sourceable lines. Inspect and clean before continuing." >&2
           exit 2
       fi

       # Operator-visible confirmation (stderr, not $ENV_FILE):
       echo "Step 1.5 complete: floor_hit_cycles_total_start=$FLOOR_HIT_T0 (source: $SOURCE) recorded in $ENV_FILE" >&2
       ```

       **Why this is structured this way (lessons from rounds 1-6):**
       - `set -euo pipefail` so any unbound var or pipeline failure aborts; no silent partial writes.
       - `|| true` only on `ls` no-match (legitimate empty case), not on `jq`/`ssh` failures (those should propagate).
       - The `SOURCE` variable is set inside each successful branch, never inferred post-hoc from leftover state, so the provenance label always matches the code path that actually produced the value.
       - Strict regex validation (`^[0-9]+$`) — empty string, `null`, `"-1"`, `"1.0"` all rejected.
       - The env file gets ONLY `key=value` lines, double-quoted where the value could contain a colon or path-separator. `bash -n` on a stripped copy verifies sourceability before exit.
       - Commentary, warnings, success messages all go to **stderr**. The env file is data only; channel separation is enforced.

       **Failure modes Step 1.5 closes:**
       - Step 1.5 skipped entirely → Step 4 detects missing `floor_hit_cycles_total_start` and authors `verdict: fail` with reason `soak_primary_gate_uncollectible_t0_baseline_missing`.
       - Step 1.5 ran but neither anchor available → `exit 2` with operator-actionable abort message; env file untouched (or only has the prior `soak_start_utc` line).
       - Step 1.5 ran and succeeded → env file has clean `key=value` pairs; Step 4 sources cleanly.
       - Step 1.5 ran with verdict.json predating Plan 08-T3 → fallback to `live_health`; provenance label honestly records the source so post-mortem can compare.

    2. **Schedule soak finish capture** (24h + 30 min for summarization):
       ```
       systemd-run --user --on-active=24h30m --unit=phase201-soak-finish \
           bash -c 'bash scripts/phase201-soak-finish.sh > /tmp/phase201-soak-finish.log 2>&1'
       ```
       (If `scripts/phase201-soak-finish.sh` does not exist, the soak finish is run manually at the 24h mark; the script is optional automation.)

    3. **Live monitoring (optional, NOT a gate)** — operator can periodically check:
       ```
       ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" \
           | jq '.wans[0].upload | {state, hysteresis: .hysteresis | {suppressions_per_min, transitions_suppressed, alert_threshold_per_min}, headroom_state, rtt_integral_ms_s, cake_aligned}'
       ```

    4. **At soak end (~24h after start)**, capture the soak summary. The summary MUST include:
       - `soak_start_utc`, `soak_end_utc`, `soak_duration_s` (>= 86_400)
       - `floor_hit_cycles_total_start`, `floor_hit_cycles_total_end`, `floor_hit_cycles_total_delta` (PRIMARY gate — must be 0; cycle-fidelity 50ms counter, REVIEWS HIGH-5)
       - `floor_hits_during_soak_1hz_secondary` (1 Hz snapshot count — must also be 0; cross-check)
       - `ul_hysteresis_suppression_rate_per_60s_p50`, `_p95`, `_mean` (D-14 SECONDARY gate — `_mean` must be < 5.0)
       - `headroom_state_distribution` (counts of AVAILABLE/EXHAUSTED across the soak)
       - `cake_aligned_distribution` (counts of true/false across the soak)
       - `rtt_integral_ms_s` quartiles + max
       - Daemon restart count during soak (INFRASTRUCTURE gate — must be 0)
       - Any non-INFO log lines (errors/warnings) flagged

       Example synthesis (REQUIRED steps, not optional — operator can adapt to local tooling but the PRIMARY-gate capture commands are not skippable):
       ```
       # Read T+0 baseline captured at Step 1.5 (REVIEWS HIGH-5). This is REQUIRED;
       # if /tmp/phase201-soak.env doesn't have floor_hit_cycles_total_start, the
       # PRIMARY soak gate is uncollectible — author verdict: fail with reason
       # `soak_primary_gate_uncollectible_t0_baseline_missing`.
       source /tmp/phase201-soak.env
       if [[ -z "${floor_hit_cycles_total_start:-}" ]]; then
           echo "FAIL: PRIMARY soak gate uncollectible — Step 1.5 was not executed at soak start. Authoring verdict: fail." >&2
           # Continue to write soak-summary.json with verdict: fail and the
           # uncollectible reason, then exit non-zero.
       fi

       # Capture T+24h counter live, compute delta:
       FLOOR_HIT_T24=$(ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" \
           | jq -r '.wans[0].upload.floor_hit_cycles_total')
       FLOOR_HIT_DELTA=$(( FLOOR_HIT_T24 - floor_hit_cycles_total_start ))
       if (( FLOOR_HIT_DELTA < 0 )); then
           # Counter went backwards — daemon restarted mid-soak. INFRASTRUCTURE
           # gate violated; PRIMARY gate is invalidated by the restart (counter
           # reset to 0). Author verdict: fail with both reasons.
           echo "FAIL: floor_hit_cycles_total_delta=$FLOOR_HIT_DELTA (negative) — daemon restart mid-soak invalidates PRIMARY gate." >&2
       fi

       OUT=.planning/phases/201-docsis-aware-ul-congestion-control/soak/$(date -u -d "$soak_start_utc" +%Y%m%dT%H%M%SZ)
       mkdir -p "$OUT"
       ssh cake-shaper "journalctl -u wanctl@spectrum.service --since '$soak_start_utc' --output=cat" > "$OUT/wanctl-spectrum.log"
       # ... use existing soak-monitor.sh + jq pipeline for the suppression-rate stats
       # ... write soak-summary.json including:
       #   floor_hit_cycles_total_start: $floor_hit_cycles_total_start
       #   floor_hit_cycles_total_end:   $FLOOR_HIT_T24
       #   floor_hit_cycles_total_delta: $FLOOR_HIT_DELTA
       #   floor_hit_cycles_total_start_source: $floor_hit_cycles_total_start_source
       ```

    5. **Capture verdict** in `.planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json`:
       ```
       {
         "phase": "201",
         "version": "1.42.0",
         "soak_start_utc": "...",
         "soak_end_utc": "...",
         "soak_duration_s": ...,
         "floor_hit_cycles_total_start": ...,
         "floor_hit_cycles_total_end": ...,
         "floor_hit_cycles_total_delta": 0,
         "floor_hits_during_soak_1hz_secondary": 0,
         "ul_hysteresis_suppression_rate_per_60s": {
           "mean": ...,
           "p50": ...,
           "p95": ...,
           "max": ...
         },
         "headroom_state_distribution": {"AVAILABLE": ..., "EXHAUSTED": ...},
         "cake_aligned_distribution": {"true": ..., "false": ...},
         "rtt_integral_ms_s_p50": ...,
         "rtt_integral_ms_s_p95": ...,
         "rtt_integral_ms_s_max": ...,
         "daemon_restart_count": 0,
         "verdict": "pass"
       }
       ```

       **VALN-06 24h soak watchdog decision matrix (authoritative — operator MUST evaluate every row before authoring `verdict` in soak-summary.json. ALL `pass` conditions must hold conjunctively. ANY single FAIL row makes the verdict `fail`. Ambiguity = FAIL by default; this is a fail-closed contract):**

       | Gate | Condition | Verdict effect if violated | Notes |
       |---|---|---|---|
       | **PRIMARY** (REVIEWS HIGH-5) | `floor_hit_cycles_total_delta == 0` over the 24h window | **FAIL** with reason `soak_primary_gate_floor_hit_cycles_delta_<N>` | Cycle-fidelity 50ms counter; this is the authoritative signal. |
       | **PRIMARY-COLLECTIBILITY** (REVIEWS round-5) | `floor_hit_cycles_total_start` was captured at Step 1.5 AND `/tmp/phase201-soak.env` carries it through to Step 4 AND `floor_hit_cycles_total_delta >= 0` (no daemon restart mid-soak) | **FAIL** with reason `soak_primary_gate_uncollectible_t0_baseline_missing` (Step 1.5 skipped) OR `soak_primary_gate_uncollectible_negative_delta_<N>` (daemon restart mid-soak invalidates the gate) | The PRIMARY gate is only meaningful if the T+0 anchor was actually captured. Operator skipping Step 1.5 OR a mid-soak daemon restart invalidates the entire 24h evidence — fail-closed; do NOT author `verdict: pass` on the assumption that "the counter probably didn't increment." Re-run the soak after capturing T+0 at the start. |
       | **SECONDARY** (D-14, NO RELAXATION) | `ul_hysteresis_suppression_rate_per_60s.mean < 5.0` | **FAIL** with reason `soak_secondary_gate_suppression_rate_<value>` | Inherited Phase 200 closure-shape watchdog. |
       | **INFRASTRUCTURE** | `daemon_restart_count == 0` | **FAIL** with reason `soak_infrastructure_daemon_restart_count_<N>` | A daemon restart mid-soak invalidates the counter delta (would reset to 0); restart-count > 0 is itself a regression signal. |
       | **PRIMARY/CROSS-CHECK COHERENCE** | `floor_hit_cycles_total_delta == 0` IFF `floor_hits_during_soak_1hz_secondary == 0` (i.e., they agree) | **FAIL** with reason `soak_primary_secondary_disagreement_counter_<N>_snapshot_<M>` | Disagreement indicates /health-vs-counter drift bug or a counter-increment defect; treated as FAIL not "investigate" — fail-closed. |
       | **DURATION** | `soak_duration_s >= 86_400` (24h minimum) | **FAIL** with reason `soak_duration_short_<N>s` | A short soak has not produced enough evidence to satisfy D-14. |

       **PASS authoring rule:** write `"verdict": "pass"` in soak-summary.json ONLY when every row above is in its non-violated state. If any row violates, write `"verdict": "fail"` with the listed reason string (concatenate multiple reasons with `;` if multiple gates fail). The operator does NOT have discretion to interpret a partial-pass — there is no "PRIMARY pass + SECONDARY fail = soft pass" path. ALL gates must hold.

       **Anti-pattern reminder:** the original Phase 200 closure-shape soak watchdog evaluated only `ul_hysteresis_suppression_rate_per_60s.mean < 5.0`. The cycle-fidelity counter was added by REVIEWS HIGH-5 to close the 1 Hz vs 50ms resolution gap. Demoting the counter to "advisory" by writing `verdict: pass` despite `floor_hit_cycles_total_delta > 0` because suppression rate is fine would re-create the exact fail-OPEN HIGH-5 was designed to prevent. Don't.

    6. **Capture operator-readable summary** in 201-12-SOAK-VERDICT.md mirroring the 201-11 shape (Soak start/end, key stats, decision PASS/FAIL, rollback protocol if FAIL).

    7. **On FAIL**: execute D-10 rollback (same archive Plan 201-11 captured); record rollback in 201-12-SOAK-VERDICT.md; type "soak-fail" + the watchdog metric that failed. Phase 201 closes as `gaps_found` and a follow-up phase is required (mirror Phase 200 closure shape).
  </how-to-verify>
  <resume-signal>
    PASS: type "soak-pass" with the soak-summary.json `floor_hit_cycles_total_delta` (must be 0) AND `ul_hysteresis_suppression_rate_per_60s.mean` (must be < 5.0) to proceed to Task 2 (closeout artifacts). Both numbers are required — operator restating them is an attestation that the AND-gate held.
    FAIL: type "soak-fail" + ALL violated gates from the decision matrix (PRIMARY / SECONDARY / INFRASTRUCTURE / COHERENCE / DURATION — list every one that violated, do NOT pick "the worst"; multiple-gate FAIL is common and operator must surface all of them) + operator's chosen remediation path. If verdict.json contains `;`-separated reasons (multi-gate FAIL), the resume signal must include all of them verbatim.
  </resume-signal>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write 201-VERIFICATION.md, update REQUIREMENTS.md, STATE.md, VALIDATION.md, commit closeout</name>
  <files>
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md,
    .planning/REQUIREMENTS.md,
    .planning/STATE.md,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  </files>
  <read_first>
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md (closure shape mirror — both pass and gaps_found shapes documented there)
    - .planning/REQUIREMENTS.md (VALN-06 row to flip)
    - .planning/STATE.md (current state to update)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md (frontmatter to flip)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md
  </read_first>
  <action>
1. **Author `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md`** mirroring Phase 200's structure but reflecting Phase 201's outcome. Required sections:

   ```
   ---
   phase: 201
   slug: docsis-aware-ul-congestion-control
   status: passed | gaps_found | blocked
   closure: <e.g. "valn-06-satisfied">
   inherited_blocking_closed: VALN-06
   nyquist_compliant: true
   wave_0_complete: true
   verified_at: YYYY-MM-DD
   ---

   # Phase 201 — Verification

   ## Inherited blocking closure
   - **VALN-06** (inherited from Phase 200): satisfied via Plan 201-11 canary verdict `pass` with PRIMARY gate `floor_hit_cycles_total_delta_loaded_window == 0` (cycle-fidelity 50ms counter, REVIEWS HIGH-5) AND-coupled with SECONDARY gate `ul_floor_hits_during_load == 0` (1 Hz snapshot, retained for cross-check) — both zero with no disagreement, enforced by the canary script's verdict-decision logic in Plan 08-T3. AND Plan 201-12 24h soak watchdog `pass` with PRIMARY gate `floor_hit_cycles_total_delta == 0` over the 24h window AND SECONDARY gate `ul_hysteresis_suppression_rate_per_60s.mean=<value>` (< 5.0). See `canary/<TS>/verdict.json` and `soak/<TS>/soak-summary.json`.

   ## Per-criterion evidence
   1. Schema accepts new keys + presence flags + ordering: TestPhase201Schema + TestSafe06Phase201KeysKnown + TestDocsisModeValidation green. Plan 201-03.
   2. Canary PRIMARY `floor_hit_cycles_total_delta_loaded_window == 0` AND SECONDARY `ul_floor_hits_during_load == 0`: canary/<TS>/verdict.json (Plan 201-11), with the AND-coupled gate enforced by the canary script in Plan 08-T3. Direct evidence improved upon: Phase 200 canary 20260504T133207Z `ul_floor_hits_during_load: 4` (cycle-fidelity counter not present in v1.41).
   3. 24h soak PRIMARY `floor_hit_cycles_total_delta == 0` AND SECONDARY suppression rate `<5/60s` mean: soak/<TS>/soak-summary.json (Plan 201-12).
   4. Predeploy gate inspects deploy target and aborts on rejected v1.41 keys: scripts/phase201-predeploy-gate.sh; tests/test_phase201_predeploy_gate.py green; live exercise in Plan 201-11.
   5. CHANGELOG + CONFIGURATION.md migration note: greps in Plan 201-06.
   6. Cross-AI review (D-18): 201-09-CODEX-PRE-REVIEW.md + 201-10-CODEX-STOP-TIME-REVIEW.md.

   ## Out of scope (deferred per CONTEXT/RESEARCH; not assessed here)
   - Modem SNMP / DOCSIS HCS counter (D-05; v1.43+).
   - Tighter soak watchdog `<2/60s` (D-14 alternative; v1.43+).
   - DOCSIS-mode auto-tuning of setpoint_mbps.
   - Multi-window integral.
   - ATT cake-primary canary (VALN-05b; cross-milestone).

   ## Closure decision
   <verdict statement matching frontmatter status>
   ```

   For FAIL or BLOCKED outcomes, mirror Phase 200's `closure: deferred-to-phase-XXX` shape and explicitly leave VALN-06 unsatisfied with a follow-up phase recommendation.

2. **Update `.planning/REQUIREMENTS.md`**:
   - Flip VALN-06 checkbox from `[ ]` to `[x]` if PASS.
   - Update the VALN-06 row text from "Blocked in Phase 200 gap closure ... Operator-escalated 2026-05-04: deferred to Phase 201" to "Satisfied in Phase 201 (`docsis-aware-ul-congestion-control`) — canary `pass` with PRIMARY `floor_hit_cycles_total_delta_loaded_window == 0` (cycle-fidelity 50ms counter, REVIEWS HIGH-5) AND SECONDARY `ul_floor_hits_during_load == 0`; 24h soak watchdog `<5/60s` mean (also AND-coupled with counter-delta == 0). See `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md`."
   - On FAIL: leave checkbox `[ ]` and append Phase 201 closure note (gap or block).

3. **Update `.planning/STATE.md`** frontmatter and body:
   - `milestone: v1.42` (or whatever the operator declared at `/gsd-new-milestone` time).
   - `status: Phase 201 closed (passed | gaps_found); VALN-06 <satisfied|deferred>; v1.42 milestone <state>; production on v1.42.0 binary post-canary-pass.`
   - Append to Decisions: `[Phase 201]: Single-phase milestone; D-09 setpoint=12 verified by canary; AUGMENT-not-replace integrating with existing 3-state classifier preserved D-17 byte-identity.`

4. **Update `.planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md`** frontmatter:
   - `status: passed` (or `gaps_found`).
   - `nyquist_compliant: true` (was `false`).
   - `wave_0_complete: true` (was `false`).

5. **Commit closeout**:
   ```
   git add .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/201-12-SOAK-VERDICT.md \
           .planning/phases/201-docsis-aware-ul-congestion-control/soak/ \
           .planning/REQUIREMENTS.md \
           .planning/STATE.md
   git commit -m "docs(201): close VALN-06 via Phase 201 canary+soak pass"
   ```

   On FAIL/BLOCKED: commit with message `docs(201): close Phase 201 as gaps_found; VALN-06 deferred to <next-phase>` and avoid touching REQUIREMENTS.md to falsely indicate satisfaction.
  </action>
  <acceptance_criteria>
    - `test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` succeeds.
    - `grep -c "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 3.
    - `grep -c "ul_floor_hits_during_load" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 1.
    - `grep -c "nyquist_compliant: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md` returns 1.
    - `grep -c "wave_0_complete: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md` returns 1.
    - On PASS: `grep -c '\\- \\[x\\] \\*\\*VALN-06\\*\\*' .planning/REQUIREMENTS.md` returns 1.
    - On PASS: `grep -c "Satisfied in Phase 201" .planning/REQUIREMENTS.md` returns >= 1.
    - On FAIL: `grep -c "deferred-to-phase-" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` returns >= 1 (mirror Phase 200 shape).
    - STATE.md last_updated reflects today; status string mentions Phase 201 outcome.
    - No staged but uncommitted changes after the commit step (`git status --porcelain | wc -l` returns 0).
  </acceptance_criteria>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md &amp;&amp; grep -q "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md &amp;&amp; grep -q "nyquist_compliant: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md &amp;&amp; grep -q "wave_0_complete: true" .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md</automated>
  </verify>
  <done>Phase 201 closure artifacts written; VALN-06 status (satisfied or deferred) reflected in REQUIREMENTS.md; STATE.md updated; VALIDATION.md frontmatter flipped; closeout committed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 24h production soak -> wanctl daemon | Live production traffic; soak observes but does not alter. Same trust shape as Phase 198 / Phase 200 soaks. |
| operator-authored verdict -> repository git history | Verdict is captured in committed files; integrity via git. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-53 | Tampering | Soak metric numbers fabricated to clear watchdog | accept | Soak summary cites journalctl + /health captures; reproducible from raw evidence in soak/<TS>/. |
| T-201-54 | Repudiation | VALN-06 closed silently in REQUIREMENTS.md without closure artifact | mitigate | Acceptance gate: 201-VERIFICATION.md must reference verdict.json + soak-summary.json; REQUIREMENTS.md flip cites 201-VERIFICATION.md. |
| T-201-55 | DoS | Soak window itself causes regression (e.g., daemon crash) | accept | Soak is observational; daemon restart count is part of the watchdog metric and gates closure. |
| T-201-56 | Tampering | Frontmatter flipped (nyquist_compliant: true) without actual Wave 0 completion | mitigate | All Wave 0 stubs (Plan 201-02) must have implementation in Plans 03-08 turning them GREEN; flipping the flag without those plans complete is a documentation tampering, caught by reading the test results. |
</threat_model>

<verification>
- Soak summary committed; suppression rate < 5/60s mean; floor hits during soak == 0; daemon restart count == 0.
- 201-VERIFICATION.md authored with full per-criterion evidence pointers.
- REQUIREMENTS.md VALN-06 row updated.
- STATE.md updated.
- VALIDATION.md frontmatter flipped.
- Closeout commit landed.
</verification>

<success_criteria>
- D-14 watchdog satisfied (no relaxation).
- Phase 201 closes with VALN-06 satisfied (or `gaps_found` with explicit deferral if soak fails).
- Closure artifacts mirror Phase 200's verification doc shape.
- Validation strategy formally Nyquist-compliant.
- Cross-AI review trail (Plans 09 + 10) preserved as audit-quality evidence.
</success_criteria>

<output>
The artifact set IS the SUMMARY: 201-VERIFICATION.md + 201-VALIDATION.md (flipped frontmatter) + 201-12-SOAK-VERDICT.md + REQUIREMENTS.md + STATE.md + soak/<TS>/. After commit, Phase 201 (and v1.42 milestone if single-phase) is closed.
</output>

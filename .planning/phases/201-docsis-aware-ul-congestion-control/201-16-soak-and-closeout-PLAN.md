---
phase: 201-docsis-aware-ul-congestion-control
plan: 16
type: execute
wave: 12
depends_on: [15]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
autonomous: false
gap_closure: true
supersedes: [12]
revision: 2  # Iteration 2 — incorporates Codex LOW/MEDIUM-CODEX-5 + on-host capture + monotonic timestamps from 201-REVIEWS.md
requirements: [VALN-06]
tags: [phase-201, gap-closure, soak, valn-06-watchdog, closeout, verification, supersedes-201-12, codex-revised]

must_haves:
  truths:
    - "24h Spectrum UL regression soak runs against the v1.42.1 binary that PASSED Plan 201-15 re-canary (NOT the failed 201-11 binary; this plan supersedes 201-12)"
    - "PRIMARY GATE: floor_hit_cycles_total counter delta from soak-T+0 to soak-T+24h == 0. T+0 baseline taken from Plan 201-15 verdict.json (.floor_hit_cycles_total_loaded_window_end), with live /health fallback at soak start. Skipping the T+0 capture is itself a fail-OPEN — verdict is `fail` with reason `soak_primary_gate_uncollectible_t0_baseline_missing`. **THE PRIMARY GATE TIGHTENING (zero floor hits over 24h vs the original Phase 200/201 success criterion of suppression `<5/60s` only) IS RECORDED AS AN OPERATOR-APPROVED CHANGE in 201-16-SOAK-VERDICT.md and 201-CONTEXT.md per codex LOW-CODEX-5; not a silent escalation. Rationale: with the rev-3 control-model amendment in place, zero floor hits is the cycle-fidelity proof of the fix; the soak transitions from secondary watchdog to primary closure gate.**"
    - "SECONDARY GATE: ul_hysteresis_suppression_rate_per_60s.mean < 5.0 across the soak window (D-14 watchdog threshold; preserved verbatim — this is the ORIGINAL VALN-06 success criterion, not relaxed)"
    - "Daemon restart mid-soak invalidates the primary gate (negative delta possible) and produces verdict=fail with reason `soak_primary_gate_uncollectible_negative_delta_<N>` — same fail-OPEN-detection pattern as Plan 201-12"
    - "**Capture loop runs ON cake-shaper itself** (codex suggestion / WARNING 7): tmux/screen session on the production node minimizes network-dependency-induced sample loss. Operator-workstation capture is permitted only when cake-shaper-host capture is infeasible; either way, MONOTONIC timestamps are used so sample coverage can be computed deterministically."
    - "**Suppression windows computed from MONOTONIC TIMESTAMPS** (codex suggestion): the secondary gate is `mean(suppressions_per_min)` over 60s sliding windows, where windows are aligned by recorded timestamp deltas, NOT by raw line count. This handles capture gaps correctly: a 90s gap between samples produces ONE 60s window (the next observation) plus a 30s remainder, not '60 implicit samples assumed.'"
    - "soak-summary.json captures: T+0 / T+24h floor_hit_cycles_total, suppressions_per_60s_mean + p95 (timestamp-windowed), RTT distribution, CAKE backlog distribution, headroom_state transitions, anti-windup trigger count, sample-coverage ratio (samples_observed / samples_expected_at_1Hz)"
    - "On PASS: Phase 201 closes with VALN-06 satisfied; 201-VERIFICATION.md status flips to verified; REQUIREMENTS.md VALN-06 row updated; STATE.md records phase closure; A5 fallback explicitly recorded as Deferred Idea (superseded); GATE TIGHTENING recorded as operator-approved closure decision"
    - "On FAIL: 201-VERIFICATION.md remains gaps_found with new gap entries; STATE.md records soak failure"
    - "201-VALIDATION.md `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
      provides: "Standardized soak metrics; timestamp-windowed suppression rate; sample-coverage ratio"
      contains: "floor_hit_cycles_total_delta_soak_window"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
      provides: "Operator-readable soak outcome + closure decisions + operator-approved gate tightening rationale"
      contains: "VALN-06"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
      provides: "Phase 201 closure verdict + per-criterion evidence pointers (re-verification mode)"
      contains: "verified"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md"
      to: "soak T+0 baseline"
      via: "verdict.json .floor_hit_cycles_total_loaded_window_end"
      pattern: "T\\+0"
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md"
      to: ".planning/REQUIREMENTS.md VALN-06 row"
      via: "VALN-06 satisfied / failed status references VERIFICATION"
      pattern: "VALN-06"
---

<objective>
**Gap-closure Plan 4 of 4. PHASE CLOSEOUT. Revision 2 — incorporates codex LOW/MEDIUM-CODEX-5 (operator-approved gate tightening), on-host supervised capture, and monotonic-timestamp suppression windows.**

Re-staged 24h soak watchdog + Phase 201 verification update. Supersedes Plan 201-12 (failed-canary path).

This plan executes ONLY if Plan 201-15 returned PASS. The soak validates that the control-model amendment (Plans 201-13 + 201-14 rev 3) is stable over 24h continuous operation, with both the primary cycle-fidelity gate (floor-hit counter delta = 0) and the legacy secondary watchdog (UL hysteresis suppression rate < 5/60s mean) green.

**Codex LOW-CODEX-5 closure — gate tightening recorded as operator-approved:**

The original Phase 200/201 success criterion (CONTEXT.md D-14) was suppression `<5/60s` mean over the 24h soak. This plan adds a STRICTER PRIMARY gate: zero floor hits over the 24h soak window (counter delta == 0). Codex correctly flagged this as a tightening that should be explicitly approved, not silently escalated. The rationale, recorded in 201-16-SOAK-VERDICT.md and appended to 201-CONTEXT.md `## Decisions`:

> **D-19 (operator-approved gate tightening, 2026-05-XX):** With the rev-3 control-model amendment (bounded-absolute decay + cap-and-clamp anti-windup), zero floor hits over a 24h DOCSIS soak is achievable as a cycle-fidelity proof of fix. The original `<5/60s` suppression-rate watchdog stays as the SECONDARY gate (legacy compatibility, also a more permissive surface). Tightening the primary gate aligns the soak with the canary's primary gate (`floor_hit_cycles_total_delta_loaded_window == 0`), so PASS at canary-time and PASS at soak-time use the same metric. Operator-approved as the closure shape for Phase 201 gap-closure path (b).

**Codex on-host supervised capture (suggestion):**

Revision 1's capture loop ran from the operator workstation, polling /health on cake-shaper. Codex correctly noted that this introduces network dependency between the operator's machine and cake-shaper, which can produce sample gaps that look like controller behavior. Revision 2 PREFERS running the capture loop on cake-shaper itself (`ssh cake-shaper "tmux new -d -s soak '...'"`). Operator-workstation capture is still permitted as a fallback (e.g., if cake-shaper has tight disk-quota constraints), but the choice is documented in 201-16-SOAK-VERDICT.md.

**Codex monotonic timestamps (suggestion):**

Revision 1 computed the secondary gate via `add / length` over the captured stream. If the capture had gaps (e.g., a 90s network blip), the per-minute suppression rate would be misweighted because each captured row was assumed to represent exactly 1s of wall-clock. Revision 2 records `t_monotonic` (a `time.monotonic()` value or `now` epoch) in every captured row, and the secondary gate computation uses 60s sliding windows aligned by timestamp deltas. A 90s gap produces one observation gap, NOT 60 implicit-but-missing samples. Same approach for sample-coverage ratio.

**Honors operator-confirmed closure direction:** path (b) — control-model amendment. A5 fallback at setpoint=10 is now formally superseded.

**autonomous: false** because: (1) 24h soak is operator-initiated and operator-monitored; (2) closure decisions update REQUIREMENTS.md / STATE.md and require operator approval per CLAUDE.md change policy.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
</context>

<interfaces>
<!-- Soak protocol mirrors Plan 201-12 verbatim except for the three rev-2 changes:
     1. Capture loop runs on cake-shaper preferred (codex suggestion)
     2. Monotonic timestamps in every captured row (codex suggestion)
     3. Gate-tightening rationale recorded as D-19 (codex LOW-CODEX-5) -->

T+0 baseline source (Plan 201-12 step 1.5 pattern preserved):
1. Primary: `jq -r '.floor_hit_cycles_total_loaded_window_end' <201-15-canary-verdict.json>`
2. Fallback: live `curl -s http://10.10.110.223:9101/health | jq '.wans[0].upload.floor_hit_cycles_total'` at soak start.

T+24h reading: live /health at soak end. Counter is monotonic-since-daemon-restart; if `systemctl status wanctl@spectrum` shows a restart between T+0 and T+24h, the delta is INVALID and verdict is `fail` with reason `soak_primary_gate_uncollectible_negative_delta_<N>`.

**Capture loop placement (codex suggestion):**

Preferred: on cake-shaper inside a tmux session. The capture loop appends each /health snapshot to `$SOAK_DIR/soak-capture.ndjson` (a path that resolves on cake-shaper; the operator copies it back at T+24h).

Fallback: operator workstation, polling cake-shaper's /health endpoint over the LAN.

Either way, every captured row includes:
- `t_wall`: wall-clock UTC ISO timestamp (`date -u -Iseconds`)
- `t_monotonic`: monotonic seconds since arbitrary epoch (jq cannot produce this directly; embed via `$(date +%s.%N)` substitution OR use a shell loop variable that records `t0_seconds` once and emits `t_monotonic = current_seconds - t0_seconds`)

Secondary metric (D-14, unchanged): `ul_hysteresis_suppression_rate_per_60s.mean`. Source = the existing wanctl health-pulse metrics emitter. Sample at 1Hz from /health for the full 24h window. Compute mean over 60s sliding windows aligned by `t_monotonic` deltas.

Diagnostic capture (Plan 201-13 fields): max_delay_delta_us, red_streak, zone_trace, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers at 1Hz. Stored in soak-summary.json under `.diagnostic_distribution`.

Anti-windup trigger count: read directly from `.wans[0].upload.anti_windup_triggers` at T+0 and T+24h; the delta IS the trigger count over the soak window. Cross-check against `journalctl -u wanctl@spectrum --since` for the rate-limited INFO logs (Plan 201-14 rev 3 emits at most one log per anti_windup_cycles interval).

REQUIREMENTS.md update pattern: VALN-06 row currently `Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement)`. On PASS: append `→ Satisfied via Phase 201 (canary <201-15-TS> + 24h soak <SOAK_TS>; primary gate floor_hit_cycles_total_delta_soak_window == 0 per operator-approved D-19)`. On FAIL: append `→ Phase 201 gap-closure soak FAIL`.
</interfaces>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Operator-run 24h soak ON cake-shaper (preferred); capture T+0 baseline; capture suppression-rate distribution at 1Hz with monotonic timestamps</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 1 — original operator-soak playbook)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (T+0 baseline source)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (codex on-host capture + monotonic-timestamp suggestions)
  </read_first>
  <what-built>
    Plans 201-13 + 201-14 rev 3 + 201-15 all complete; v1.42.1 binary deployed and running on cake-shaper; Plan 201-15 returned PASS with primary_gate_value=0 and ul_floor_hits_during_load=0; active control knob assertion confirmed all rev-3 knobs live.
  </what-built>
  <how-to-verify>
    1. **Verify prerequisites**:
       ```
       jq -e '.verdict == "pass"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
       curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1" and .wans[0].upload.docsis_mode_active == true and .wans[0].upload.anti_windup_cycles == 60'
       ```
       All three must succeed before starting the soak.

    2. **Capture T+0 baseline** (REVIEWS round-5 collectibility — REQUIRED before the 24h wait):
       ```
       export SOAK_TS=$(date -u +%Y%m%dT%H%M%SZ)
       mkdir -p .planning/phases/201-docsis-aware-ul-congestion-control/soak/${SOAK_TS}
       SOAK_DIR=.planning/phases/201-docsis-aware-ul-congestion-control/soak/${SOAK_TS}

       # Primary source: 201-15 canary verdict
       T0_FROM_VERDICT=$(jq -r '.floor_hit_cycles_total_loaded_window_end' \
         $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1))
       # Fallback source: live /health
       T0_LIVE=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.floor_hit_cycles_total')
       T0_AW_TRIGGERS=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.anti_windup_triggers')
       echo "{\"t0_from_verdict\": $T0_FROM_VERDICT, \"t0_live\": $T0_LIVE, \"t0_chosen\": $T0_LIVE, \"t0_anti_windup_triggers\": $T0_AW_TRIGGERS, \"t0_captured_at_utc\": \"$(date -u -Iseconds)\"}" \
         > $SOAK_DIR/t0-baseline.json
       cat $SOAK_DIR/t0-baseline.json
       ```

    3. **Choose capture host** (codex suggestion):
       - **PREFERRED — on cake-shaper**: Open a tmux session on cake-shaper, run the capture loop there, write to a path on cake-shaper's filesystem.
       - **FALLBACK — operator workstation**: poll over the LAN. Document the choice in `$SOAK_DIR/capture-host.txt`:
         ```
         echo "capture_host: cake-shaper (on-host, preferred per codex suggestion)" > $SOAK_DIR/capture-host.txt
         # OR:
         echo "capture_host: operator-workstation (fallback; reason: <e.g. cake-shaper disk quota>)" > $SOAK_DIR/capture-host.txt
         ```

    4. **Start 1Hz soak capture loop with MONOTONIC TIMESTAMPS** (codex suggestion). On-host variant (preferred):
       ```bash
       # Run on cake-shaper inside tmux:
       ssh cake-shaper bash <<'REMOTE_EOF'
         set -euo pipefail
         SOAK_DURATION_SEC=86400  # 24h
         CAPTURE_DIR=/var/tmp/wanctl-soak-${SOAK_TS}
         mkdir -p "$CAPTURE_DIR"
         T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
         SOAK_END=$(($(date +%s) + $SOAK_DURATION_SEC))
         while [ $(date +%s) -lt $SOAK_END ]; do
           T_MONO=$(awk '{print $1; exit}' /proc/uptime)
           T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')
           curl -s http://127.0.0.1:9101/health \
             | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
                 t_wall: $twall,
                 t_monotonic: $tmono,
                 version: .version,
                 status: .status,
                 floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
                 suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
                 max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
                 red_streak: .wans[0].upload.red_streak,
                 zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
                 headroom_state: .wans[0].upload.headroom_state,
                 headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
                 anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
                 rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
                 docsis_mode_active: .wans[0].upload.docsis_mode_active
               }' >> "$CAPTURE_DIR/soak-capture.ndjson"
           sleep 1
         done
       REMOTE_EOF
       ```
       (Wrap the inner loop in `tmux new -d -s soak '<above>'` so the operator can detach.)

       At T+24h, copy `soak-capture.ndjson` back to operator workstation:
       ```
       scp cake-shaper:/var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson $SOAK_DIR/soak-capture.ndjson
       ```

       Operator-workstation fallback variant: same loop running locally, polling `http://10.10.110.223:9101/health` over LAN, writing directly to `$SOAK_DIR/soak-capture.ndjson`. Same monotonic-timestamp logic.

    5. **Detect daemon restart mid-soak**: at any point, check `ssh cake-shaper "sudo systemctl is-active wanctl@spectrum"` returns `active`; if it ever shows inactive/failed, record the restart timestamp in `$SOAK_DIR/restart-events.log`. The gate verdict in Task 2 will then be fail-OPEN.

    6. **At T+24h, capture end values**:
       ```
       T24_LIVE=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.floor_hit_cycles_total')
       T24_AW_TRIGGERS=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.anti_windup_triggers')
       echo "{\"t24_live\": $T24_LIVE, \"t24_anti_windup_triggers\": $T24_AW_TRIGGERS, \"t24_captured_at_utc\": \"$(date -u -Iseconds)\"}" \
         > $SOAK_DIR/t24-baseline.json
       ```

    7. **Hand off to Task 2** with the soak directory path.
  </how-to-verify>
  <resume-signal>Type "soak complete: <SOAK_DIR>" with the directory path, OR "soak aborted: <reason>" if the soak couldn't run to completion.</resume-signal>
  <acceptance_criteria>
    - $SOAK_DIR/t0-baseline.json exists with t0_anti_windup_triggers field
    - $SOAK_DIR/t24-baseline.json exists with t24_anti_windup_triggers field
    - $SOAK_DIR/capture-host.txt exists documenting cake-shaper vs operator-workstation choice
    - $SOAK_DIR/soak-capture.ndjson exists, non-empty, every row has both `t_wall` and `t_monotonic` fields (codex monotonic-timestamps requirement). Validate by `head -1 $SOAK_DIR/soak-capture.ndjson | jq -e '.t_wall and (.t_monotonic | type == "number")'`.
    - Sample count >= 86000 (1% loss budget on 24h × 1Hz capture; expected = 86400)
    - $SOAK_DIR/restart-events.log either does not exist or is empty
    - Operator typed the resume signal with directory path
  </acceptance_criteria>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Compute soak verdict via timestamp-windowed suppression rate; write soak-summary.json + 201-16-SOAK-VERDICT.md; record D-19 operator-approved gate tightening; update VERIFICATION/REQUIREMENTS/STATE/CONTEXT</name>
  <read_first>
    - $SOAK_DIR/t0-baseline.json, $SOAK_DIR/t24-baseline.json, $SOAK_DIR/soak-capture.ndjson, $SOAK_DIR/restart-events.log (if exists), $SOAK_DIR/capture-host.txt
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 2 — original closeout playbook format)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (current gaps_found state)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (Decisions section — D-19 will be appended)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (LOW-CODEX-5 — gate tightening must be operator-approved)
    - .planning/REQUIREMENTS.md (VALN-06 row)
    - .planning/STATE.md
  </read_first>
  <files>
    .planning/phases/201-docsis-aware-ul-congestion-control/soak/<SOAK_TS>/soak-summary.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md,
    .planning/REQUIREMENTS.md,
    .planning/STATE.md
  </files>
  <action>
    1. **Compute primary gate** (floor_hit_cycles_total delta over 24h):
       ```
       T0=$(jq -r '.t0_chosen' $SOAK_DIR/t0-baseline.json)
       T24=$(jq -r '.t24_live' $SOAK_DIR/t24-baseline.json)
       PRIMARY_DELTA=$((T24 - T0))
       ```
       - If $PRIMARY_DELTA < 0: verdict=fail, reason=`soak_primary_gate_uncollectible_negative_delta_${PRIMARY_DELTA}`
       - If $SOAK_DIR/restart-events.log exists and is non-empty: verdict=fail, reason=`soak_primary_gate_uncollectible_daemon_restart_observed`
       - If $PRIMARY_DELTA == 0 AND no restart events: primary gate PASS
       - If $PRIMARY_DELTA > 0: verdict=fail, reason=`soak_primary_gate_floor_hit_delta_${PRIMARY_DELTA}` (D-19 zero-tolerance)

    2. **Compute secondary gate via TIMESTAMP-WINDOWED 60s mean** (codex suggestion). The naive `add/length` approach assumes one sample per second of wall-clock — wrong if there are gaps. Compute proper 60s windows:
       ```
       jq -s '
         # Sort by t_monotonic to handle any out-of-order rows.
         sort_by(.t_monotonic)
         | (.[0].t_monotonic) as $t_start
         | (.[-1].t_monotonic) as $t_end
         | (($t_end - $t_start) / 60.0 | floor) as $window_count
         | reduce range(0; $window_count) as $w (
             {windows: [], samples_total: length, t_start: $t_start, t_end: $t_end};
             .windows += [
               (
                 [.[] | select(.t_monotonic >= ($t_start + ($w * 60)))
                       | select(.t_monotonic <  ($t_start + (($w + 1) * 60)))
                       | .suppressions_per_min // 0]
                 | if length > 0 then (add / length) else null end
               )
             ]
           )
         | .windows |= map(select(. != null))
         | {
             samples_total: .samples_total,
             t_start: .t_start,
             t_end: .t_end,
             window_count: (.windows | length),
             suppressions_per_min_mean: (
               if (.windows | length) > 0
               then (.windows | add / length)
               else null
               end
             ),
             suppressions_per_min_p95: (
               if (.windows | length) > 0
               then (.windows | sort | .[((.windows | length) * 95 / 100) | floor])
               else null
               end
             ),
             suppressions_per_min_max: (.windows | max),
             expected_samples_at_1hz: ((.t_end - .t_start) | floor),
             sample_coverage_ratio: (.samples_total / ((.t_end - .t_start)))
           }
       ' $SOAK_DIR/soak-capture.ndjson > $SOAK_DIR/suppression-stats.json
       SUPP_MEAN=$(jq -r '.suppressions_per_min_mean' $SOAK_DIR/suppression-stats.json)
       COVERAGE=$(jq -r '.sample_coverage_ratio' $SOAK_DIR/suppression-stats.json)
       ```
       - If $SUPP_MEAN < 5.0: secondary gate PASS
       - Else: verdict=fail, reason=`soak_secondary_gate_suppressions_per_min_${SUPP_MEAN}`
       - If $COVERAGE < 0.95: append warning to verdict (capture loss high; gate values may be approximate)
       - Disagreement (one PASS one FAIL): verdict=fail, reason=`soak_gates_disagreement_primary_${PRIMARY_GATE}_secondary_${SECONDARY_GATE}`

    3. **Compute diagnostic distributions**:
       ```
       jq -s '
         {
           rtt_integral_ms_s: { mean: ([.[].rtt_integral_ms_s] | add/length), max: ([.[].rtt_integral_ms_s] | max) },
           max_delay_delta_us: { mean: ([.[].max_delay_delta_us] | add/length), max: ([.[].max_delay_delta_us] | max) },
           red_streak: { mean: ([.[].red_streak] | add/length), max: ([.[].red_streak] | max) },
           headroom_exhausted_samples: ([.[] | select(.headroom_state == "EXHAUSTED")] | length),
           total_samples: length
         }
       ' $SOAK_DIR/soak-capture.ndjson > $SOAK_DIR/diagnostic-distribution.json
       ```

    4. **Anti-windup trigger count** (delta from /health counter):
       ```
       T0_AW=$(jq -r '.t0_anti_windup_triggers' $SOAK_DIR/t0-baseline.json)
       T24_AW=$(jq -r '.t24_anti_windup_triggers' $SOAK_DIR/t24-baseline.json)
       ANTI_WINDUP_DELTA=$((T24_AW - T0_AW))
       # Cross-check via journalctl (rate-limited INFO logs from Plan 201-14 rev 3):
       ANTI_WINDUP_LOGS=$(ssh cake-shaper "sudo journalctl -u wanctl@spectrum.service --since '24 hours ago' | grep -c 'ANTI-WINDUP'" 2>/dev/null || echo 0)
       ```

    5. **Write soak-summary.json**:
       ```json
       {
         "phase": 201,
         "plan": 16,
         "soak_ts": "<SOAK_TS>",
         "supersedes": "201-12 (failed-canary path)",
         "v_binary": "1.42.1",
         "duration_sec": 86400,
         "capture_host": "<from $SOAK_DIR/capture-host.txt>",
         "sample_coverage_ratio": <COVERAGE>,
         "primary_gate": {
           "name": "floor_hit_cycles_total_delta_soak_window",
           "threshold": "== 0 (operator-approved D-19 tightening)",
           "t0": <T0>, "t24": <T24>, "delta": <PRIMARY_DELTA>,
           "verdict": "<pass|fail>",
           "reason": "<reason or null>"
         },
         "secondary_gate": {
           "name": "ul_hysteresis_suppression_rate_per_60s_mean",
           "computation": "timestamp-windowed 60s sliding mean (codex monotonic-timestamps)",
           "value": <SUPP_MEAN>, "threshold": 5.0,
           "verdict": "<pass|fail>"
         },
         "diagnostic_distribution": <contents of diagnostic-distribution.json>,
         "anti_windup_triggers_delta": <ANTI_WINDUP_DELTA>,
         "anti_windup_log_count": <ANTI_WINDUP_LOGS>,
         "verdict": "<pass|fail>",
         "reason": "<combined reason>"
       }
       ```

    6. **Write 201-16-SOAK-VERDICT.md** mirroring 201-11-CANARY-VERDICT.md format. Required sections: Soak Run Metadata (incl. capture host, sample coverage), Primary Gate (incl. D-19 tightening rationale block — see step 7), Secondary Gate (timestamp-windowed computation), Diagnostic Distribution, Anti-Windup Triggers (counter delta + log count), Decision (PASS/FAIL/aborted), Closure Action.

    7. **Record D-19 (operator-approved gate tightening) in 201-CONTEXT.md** (codex LOW-CODEX-5):
       Append to the `## Decisions` section, in the appropriate sub-section (likely between D-18 and the existing Claude's Discretion section):
       ```markdown
       ### Soak Closure Gate (gap-closure path b, 2026-05-XX)

       - **D-19 (operator-approved gate tightening, post-201-15-PASS):** Phase 201 closure adds a STRICTER PRIMARY soak gate beyond the original D-14 secondary watchdog. With the rev-3 control-model amendment in place (bounded-absolute decay + cap-and-clamp anti-windup, Plans 201-13/201-14 rev 3), zero floor hits over a 24h DOCSIS soak (`floor_hit_cycles_total_delta_soak_window == 0`) is achievable as a cycle-fidelity proof of fix. The original D-14 `<5/60s` suppression-rate threshold STAYS as the SECONDARY gate (legacy compatibility, more permissive). Tightening the primary gate aligns the soak's primary metric with the canary's primary metric, so PASS at canary-time and PASS at soak-time use the same cycle-fidelity surface. Operator-approved 2026-05-XX as the closure shape for Phase 201 gap-closure path (b). Codex 201-REVIEWS LOW-CODEX-5: this tightening is recorded explicitly per cross-AI review feedback, not silently escalated.
       ```

    8. **On PASS**: update artifacts:
       - **201-VERIFICATION.md**: change `status: gaps_found` → `status: verified` in frontmatter; flip truth-1 (floor_hit_cycles_total) to VERIFIED with evidence pointer; flip truth-2 (24h soak) to VERIFIED; flip truth-3 (A5 fallback) to SUPERSEDED; convert `## Gaps Summary` to `## Closure Summary`.
       - **REQUIREMENTS.md**: VALN-06 row → `Satisfied via Phase 201 (re-canary <201-15-TS> + 24h soak <SOAK_TS>; D-19 primary gate met)`.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 closure (PASS via gap-closure path b)`.
       - **201-VALIDATION.md**: set `nyquist_compliant: true`, `wave_0_complete: true`.
       - **201-CONTEXT.md**: append D-19 (per step 7) AND under `## Deferred Ideas` `### Not in Scope for Phase 201` add the A5-superseded note from revision 1.

    9. **On FAIL**: update artifacts:
       - **201-VERIFICATION.md**: stays `gaps_found`; append new gap entries.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 soak FAIL (gap-closure path)`.
       - **REQUIREMENTS.md**: VALN-06 stays Deferred; append `→ Phase 201 gap-closure soak FAIL (<SOAK_TS>); next action <A5|v1.43+>`.
       - 201-CONTEXT.md still gets D-19 appended (the gate-tightening decision was taken; soak failed against it — that's an honest record).
       - Do NOT mark 201-VALIDATION.md complete.

    10. **Commit**: `feat(201-16): close Phase 201 — VALN-06 satisfied via gap-closure path (b); record D-19 gate tightening` on PASS, or `docs(201-16): record soak FAIL; route to <A5|v1.43+>` on FAIL.
  </action>
  <verify>
    <automated>jq -e '.verdict | IN("pass", "fail")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
    <automated>grep -q "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -q "supersedes" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -q "D-19" .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md</automated>
    <automated>grep -q "operator-approved" .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md</automated>
    <automated>grep -E "Phase 201 closure|Phase 201 soak FAIL" .planning/STATE.md | head -1</automated>
    <automated>jq -e '.secondary_gate.computation | contains("timestamp-windowed")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
  </verify>
  <acceptance_criteria>
    - soak-summary.json exists with verdict ∈ {"pass", "fail"}, sample_coverage_ratio recorded, secondary_gate.computation explicitly notes "timestamp-windowed"
    - 201-16-SOAK-VERDICT.md exists with all required sections including D-19 rationale block
    - 201-CONTEXT.md contains D-19 with "operator-approved" language (codex LOW-CODEX-5)
    - On PASS: 201-VERIFICATION.md `status: verified`; REQUIREMENTS.md VALN-06 row updated with D-19 reference; STATE.md records closure; 201-VALIDATION.md `nyquist_compliant: true`; A5 superseded note in 201-CONTEXT.md
    - On FAIL: 201-VERIFICATION.md retains `gaps_found` with new gaps; STATE.md records failure; D-19 still appended to 201-CONTEXT.md (decision was taken regardless of outcome)
    - Commit recorded
  </acceptance_criteria>
  <done>
    Phase 201 closure posture is final. PASS = VALN-06 satisfied with operator-approved D-19 primary gate; FAIL = next gap-closure cycle scoped.
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 2 verdict:

- **PASS**: 201-VERIFICATION.md `status: verified`; REQUIREMENTS.md VALN-06 says "Satisfied"; STATE.md records phase closure; A5 superseded; D-19 recorded as operator-approved gate tightening. Phase 201 is closed.
- **FAIL**: 201-VERIFICATION.md retains `gaps_found`; STATE.md records failure + next-action choice; D-19 still recorded (decision-taking is independent of outcome).
</verification>

<success_criteria>
- 24h soak runs to completion against the v1.42.1 binary that PASSED Plan 201-15 re-canary
- Capture host choice documented (cake-shaper preferred per codex on-host suggestion)
- Every captured row has monotonic timestamp; secondary gate uses timestamp-windowed 60s mean (codex suggestion)
- soak-summary.json captures both gates with cycle-fidelity primary metric
- D-19 (gate tightening) recorded as operator-approved in 201-CONTEXT.md (codex LOW-CODEX-5)
- Closure verdict recorded across all four planning artifacts (VERIFICATION, REQUIREMENTS, STATE, VALIDATION)
- A5 fallback explicitly recorded as superseded (PASS) or as next-action option (FAIL)
- Sample coverage ratio recorded; daemon-restart fail-OPEN-detection honored
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SUMMARY.md` per the standard template. Include: soak timestamp, capture host (on-host vs operator-workstation), sample coverage ratio, primary gate verdict + delta, secondary gate verdict + value (with note that computation is timestamp-windowed), diagnostic distribution highlights, anti-windup triggers delta + log count, closure verdict, downstream artifacts updated, codex review findings closed (LOW-CODEX-5 + on-host capture + monotonic timestamps).
</output>

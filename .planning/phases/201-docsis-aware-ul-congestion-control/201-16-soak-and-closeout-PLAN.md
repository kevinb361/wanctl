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
requirements: [VALN-06]
tags: [phase-201, gap-closure, soak, valn-06-watchdog, closeout, verification, supersedes-201-12]

must_haves:
  truths:
    - "24h Spectrum UL regression soak runs against the v1.42 binary that PASSED Plan 201-15 re-canary (NOT the failed 201-11 binary; this plan supersedes 201-12 because 201-12 was authored against the failed path)"
    - "PRIMARY GATE: floor_hit_cycles_total counter delta from soak-T+0 to soak-T+24h == 0. T+0 baseline taken from Plan 201-15 verdict.json (.floor_hit_cycles_total_loaded_window_end), with live /health fallback at soak start. Skipping the T+0 capture is itself a fail-OPEN — verdict is `fail` with reason `soak_primary_gate_uncollectible_t0_baseline_missing`."
    - "SECONDARY GATE: ul_hysteresis_suppression_rate_per_60s.mean < 5.0 across the soak window (D-14 watchdog threshold; no relaxation, no tightening per CONTEXT.md)"
    - "Daemon restart mid-soak invalidates the primary gate (negative delta possible) and produces verdict=fail with reason `soak_primary_gate_uncollectible_negative_delta_<N>` — same fail-OPEN-detection pattern as Plan 201-12"
    - "soak-summary.json captures: T+0 / T+24h floor_hit_cycles_total, suppressions_per_60s_mean + p95, RTT distribution, CAKE backlog distribution, headroom_state transitions, anti-windup trigger count"
    - "On PASS: Phase 201 closes with VALN-06 satisfied; 201-VERIFICATION.md status flips to verified; REQUIREMENTS.md VALN-06 row updated; STATE.md records phase closure; A5 fallback explicitly recorded as Deferred Idea (superseded)"
    - "On FAIL: 201-VERIFICATION.md remains gaps_found with new gap entries; STATE.md records soak failure; operator chooses A5 fallback re-canary OR v1.43+ re-roadmap"
    - "201-VALIDATION.md `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
      provides: "Standardized soak metrics capturing both gates + diagnostic distributions"
      contains: "floor_hit_cycles_total_delta_soak_window"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
      provides: "Operator-readable soak outcome + closure decisions"
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
**Gap-closure Plan 4 of 4. PHASE CLOSEOUT.** Re-staged 24h soak watchdog + Phase 201 verification update. Supersedes Plan 201-12 (which was authored against the 201-11 canary path that FAILED; the gap-closure path requires a fresh soak plan against the 201-15 PASS).

This plan executes ONLY if Plan 201-15 returned PASS. The soak validates that the control-model amendment (Plans 201-13 + 201-14) is stable over 24h continuous operation, with both the primary cycle-fidelity gate (floor-hit counter delta = 0) and the legacy secondary watchdog (UL hysteresis suppression rate < 5/60s mean) green.

**Closure shape:** PASS → Phase 201 closes with VALN-06 satisfied; 201-VERIFICATION.md re-verified; A5 fallback (setpoint=10) explicitly recorded as superseded Deferred Idea. FAIL → 201-VERIFICATION.md gains new gap entries; operator chooses next path (A5 fallback OR v1.43+ re-roadmap).

**Re-uses 201-12 spec extensively** because the soak protocol itself is unchanged — only the inputs differ (v1.42 post-201-14 binary vs v1.42 post-201-11 binary; T+0 baseline from 201-15 verdict.json vs 201-11 verdict.json). REVIEWS round-5 fail-OPEN-detection patterns from 201-12 (T+0 baseline collectibility, negative-delta detection) carry through verbatim.

**Honors operator-confirmed closure direction:** path (b) — control-model amendment. A5 fallback at setpoint=10 is now formally superseded because path (b) closed VALN-06 (assuming PASS). Recorded in CONTEXT.md `## Deferred Ideas` per the planning-context guidance.

**autonomous: false** because: (1) 24h soak is operator-initiated and operator-monitored (cannot be automated end-to-end on a control system Claude doesn't own); (2) closure decisions update REQUIREMENTS.md / STATE.md and require operator approval per CLAUDE.md change policy.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
</context>

<interfaces>
<!-- Soak protocol mirrors Plan 201-12 verbatim. The contract is: 24h continuous wanctl@spectrum operation, secondary-gate metric collection at 1Hz, primary-gate counter delta computed from /health reads at T+0 and T+24h. -->

T+0 baseline source (REVIEWS round-5 / 201-12 step 1.5):
1. Primary: `jq -r '.floor_hit_cycles_total_loaded_window_end' <201-15-canary-verdict.json>`
2. Fallback: live `curl -s http://10.10.110.223:9101/health | jq '.wans[0].upload.floor_hit_cycles_total'` at soak start.

T+24h reading: live /health at soak end. Counter is monotonic-since-daemon-restart; if `systemctl status wanctl@spectrum` shows a restart between T+0 and T+24h, the delta is INVALID and verdict is `fail` with reason `soak_primary_gate_uncollectible_negative_delta_<N>`.

Secondary metric (D-14): `ul_hysteresis_suppression_rate_per_60s.mean`. Source = the existing wanctl health-pulse metrics emitter (already wired pre-Phase-201; no new instrumentation). Sample at 1Hz from /health for the full 24h window, compute mean over 60s sliding windows.

Diagnostic capture (Plan 201-13 fields, valuable for post-soak inspection even on PASS): sample max_delay_delta_us, red_streak, zone_trace at 1Hz alongside the suppression rate. Stored in soak-summary.json under `.diagnostic_distribution`.

Anti-windup trigger count: count occurrences of `[ANTI-WINDUP] upload integral halved` in `journalctl -u wanctl@spectrum --since` over the soak window. Expected to be 0 on a healthy DOCSIS link with the control-model fix; non-zero is informational (indicates the anti-windup safety net engaged).

REQUIREMENTS.md update pattern: the VALN-06 row currently reads `Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement)`. On PASS, append `→ Satisfied via Phase 201 (canary 20260504T... + 24h soak <TS>)`. On FAIL, append `→ Phase 201 gaps_found, deferred to v1.43+`.
</interfaces>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Operator-run 24h soak; capture T+0 baseline; capture suppression-rate distribution at 1Hz; capture diagnostic distributions</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 1, the existing operator-soak playbook — re-use verbatim with the 201-15 verdict swapped in for 201-11)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (T+0 baseline source)
  </read_first>
  <what-built>
    Plans 201-13 + 201-14 + 201-15 all complete; v1.42 binary deployed and running on cake-shaper; Plan 201-15 returned PASS with primary_gate_value=0 and ul_floor_hits_during_load=0. Plan 201-15-CANARY-VERDICT.md records the soak T+0 baseline value.
  </what-built>
  <how-to-verify>
    1. **Verify prerequisites**:
       ```
       jq -e '.verdict == "pass"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
       curl -s http://10.10.110.223:9101/health | jq -e '.wans[0].upload.docsis_mode_active == true'
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
       echo "{\"t0_from_verdict\": $T0_FROM_VERDICT, \"t0_live\": $T0_LIVE, \"t0_chosen\": $T0_LIVE, \"t0_captured_at_utc\": \"$(date -u -Iseconds)\"}" \
         > $SOAK_DIR/t0-baseline.json
       cat $SOAK_DIR/t0-baseline.json
       ```
       The chosen T+0 is the LIVE /health value at soak start (most accurate for a delta against T+24h live read). The verdict-derived value is recorded for cross-reference.

    3. **Start 1Hz soak capture loop** (operator-run, can be a screen/tmux session). WARNING 7 operational note: PREFER running this loop on `cake-shaper` itself (`ssh cake-shaper "screen -dmS soak ..."`) when feasible — it eliminates network-dependency-induced sample loss that an operator-workstation loop would experience. If running from a remote workstation is required, monitor for sample gaps and document any extended (>5s) gaps in $SOAK_DIR/restart-events.log so Task 2 can distinguish capture-loss from controller behavior.
       ```
       SOAK_DURATION_SEC=86400  # 24h
       SOAK_END=$(($(date +%s) + $SOAK_DURATION_SEC))
       while [ $(date +%s) -lt $SOAK_END ]; do
         curl -s http://10.10.110.223:9101/health \
           | jq -c '{
               t: now,
               version: .version,
               status: .status,
               floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
               suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
               max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
               red_streak: .wans[0].upload.red_streak,
               zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
               headroom_state: .wans[0].upload.headroom_state,
               rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
               docsis_mode_active: .wans[0].upload.docsis_mode_active
             }' >> $SOAK_DIR/soak-capture.ndjson
         sleep 1
       done
       ```
       At any point during the soak, the operator may sample journalctl for anti-windup triggers:
       ```
       ssh cake-shaper "sudo journalctl -u wanctl@spectrum.service --since '24 hours ago' | grep -c 'ANTI-WINDUP' || echo 0"
       ```

    4. **Detect daemon restart mid-soak** (REVIEWS round-5 negative-delta detection): periodically check `systemctl is-active`; if it ever shows inactive/failed during the 24h window, the primary gate is uncollectible. Record the restart timestamp in `$SOAK_DIR/restart-events.log`. The gate verdict in Task 2 will then be `fail` with reason `soak_primary_gate_uncollectible_negative_delta_<N>`.

    5. **At T+24h, capture end values**:
       ```
       T24_LIVE=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.floor_hit_cycles_total')
       echo "{\"t24_live\": $T24_LIVE, \"t24_captured_at_utc\": \"$(date -u -Iseconds)\"}" \
         > $SOAK_DIR/t24-baseline.json
       ```

    6. **Hand off to Task 2** with the soak directory path.
  </how-to-verify>
  <resume-signal>Type "soak complete: <SOAK_DIR>" with the directory path, OR "soak aborted: <reason>" if the soak couldn't run to completion.</resume-signal>
  <acceptance_criteria>
    - $SOAK_DIR/t0-baseline.json exists and is valid JSON
    - $SOAK_DIR/t24-baseline.json exists and is valid JSON
    - $SOAK_DIR/soak-capture.ndjson exists and is non-empty (>= 86000 lines — 1% loss budget on 24h × 1Hz capture; expected = 86400 lines). WARNING 7 fix: tightened from 80000 to 86000. Operator playbook: when feasible the capture loop SHOULD run on cake-shaper itself (no network dependency between operator workstation and the /health endpoint) to minimize loss. If running from a remote workstation, document any network gaps in restart-events.log.
    - $SOAK_DIR/restart-events.log either does not exist or is empty (no daemon restarts) — non-empty triggers fail-OPEN-detection in Task 2
    - Operator typed the resume signal with directory path
  </acceptance_criteria>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Compute soak verdict; write soak-summary.json + 201-16-SOAK-VERDICT.md; update VERIFICATION/REQUIREMENTS/STATE/CONTEXT</name>
  <read_first>
    - $SOAK_DIR/t0-baseline.json, $SOAK_DIR/t24-baseline.json, $SOAK_DIR/soak-capture.ndjson, $SOAK_DIR/restart-events.log (if exists)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 2, the existing closeout playbook — mirror format)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (current gaps_found state)
    - .planning/REQUIREMENTS.md (VALN-06 row)
    - .planning/STATE.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (Deferred Ideas section)
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
       - If $PRIMARY_DELTA > 0: verdict=fail, reason=`soak_primary_gate_floor_hit_delta_${PRIMARY_DELTA}`

    2. **Compute secondary gate** (suppression rate < 5/60s mean):
       ```
       jq -s '
         [.[].suppressions_per_min] | map(. // 0)
         | {
             samples: length,
             suppressions_per_min_mean: (add / length),
             suppressions_per_min_p95: (sort | .[length * 95 / 100 | floor]),
             suppressions_per_min_max: max
           }
       ' $SOAK_DIR/soak-capture.ndjson > $SOAK_DIR/suppression-stats.json
       SUPP_MEAN=$(jq -r '.suppressions_per_min_mean' $SOAK_DIR/suppression-stats.json)
       ```
       - If $SUPP_MEAN < 5.0: secondary gate PASS
       - Else: verdict=fail, reason=`soak_secondary_gate_suppressions_per_min_${SUPP_MEAN}`
       - Disagreement (one PASS one FAIL): verdict=fail, reason=`soak_gates_disagreement_primary_${PRIMARY_GATE}_secondary_${SECONDARY_GATE}`

    3. **Compute diagnostic distributions** (Plan 201-13 fields, informational on PASS, root-cause on FAIL):
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

    4. **Anti-windup trigger count**:
       ```
       ANTI_WINDUP_COUNT=$(ssh cake-shaper "sudo journalctl -u wanctl@spectrum.service --since '24 hours ago' | grep -c 'ANTI-WINDUP'" 2>/dev/null || echo 0)
       ```

    5. **Write soak-summary.json** with the canonical schema:
       ```json
       {
         "phase": 201,
         "plan": 16,
         "soak_ts": "<SOAK_TS>",
         "supersedes": "201-12 (failed-canary path)",
         "v_binary": "1.42.0",
         "duration_sec": 86400,
         "primary_gate": {
           "name": "floor_hit_cycles_total_delta_soak_window",
           "t0": <T0>, "t24": <T24>, "delta": <PRIMARY_DELTA>,
           "verdict": "<pass|fail>",
           "reason": "<reason or null>"
         },
         "secondary_gate": {
           "name": "ul_hysteresis_suppression_rate_per_60s_mean",
           "value": <SUPP_MEAN>, "threshold": 5.0,
           "verdict": "<pass|fail>"
         },
         "diagnostic_distribution": <contents of diagnostic-distribution.json>,
         "anti_windup_triggers": <ANTI_WINDUP_COUNT>,
         "verdict": "<pass|fail>",
         "reason": "<combined reason>"
       }
       ```

    6. **Write 201-16-SOAK-VERDICT.md** mirroring 201-11-CANARY-VERDICT.md format. Sections: Soak Run Metadata, Primary Gate, Secondary Gate, Diagnostic Distribution, Anti-Windup Triggers, Decision (PASS/FAIL/aborted), Closure Action.

    7. **On PASS**: update artifacts:
       - **201-VERIFICATION.md**: change `status: gaps_found` to `status: verified` in frontmatter; flip truth-1 (floor_hit_cycles_total) to VERIFIED with evidence pointer to soak-summary.json; flip truth-2 (24h soak) to VERIFIED; flip truth-3 (A5 fallback) to SUPERSEDED with note "path (b) closure successful; A5 not required"; update `## Gaps Summary` to a `## Closure Summary` reflecting the resolution.
       - **REQUIREMENTS.md**: update VALN-06 row from `Deferred -> Phase 201 (inherited blocking requirement)` to `Satisfied via Phase 201 (re-canary <201-15-TS> + 24h soak <SOAK_TS>)`.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 closure (PASS via gap-closure)` section recording the milestone status update.
       - **201-VALIDATION.md**: set `nyquist_compliant: true` and `wave_0_complete: true` in frontmatter.
       - **201-CONTEXT.md**: under `## Deferred Ideas` `### Not in Scope for Phase 201`, append:
         ```
         - **A5 fallback (re-canary at setpoint_mbps=10)** — explicitly SUPERSEDED by gap-closure path (b) (control-model amendment in Plans 201-13/201-14). The 1453-floor-cycle margin from canary 20260504T231334Z was closed by the floor-anchored RED decay + integral anti-windup, not by setpoint reduction. A5 is recorded here for historical reference; do not re-attempt unless a future canary fails AND the control-model amendment is shown to be the failing component.
         ```

    8. **On FAIL**: update artifacts:
       - **201-VERIFICATION.md**: stays `status: gaps_found`; append new gap entries for the failing gate(s) with evidence pointers.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 soak FAIL (gap-closure path)` section. Include the operator's choice for next action (A5 fallback re-canary planning OR v1.43+ re-roadmap).
       - **REQUIREMENTS.md**: VALN-06 row stays in Deferred state; append `→ Phase 201 gap-closure soak FAIL (<SOAK_TS>); next action <A5|v1.43+>`.
       - Do NOT mark 201-VALIDATION.md complete on FAIL.

    9. **Commit**: `feat(201-16): close Phase 201 — VALN-06 satisfied via gap-closure path (b)` on PASS, or `docs(201-16): record soak FAIL; route to <A5|v1.43+>` on FAIL.
  </action>
  <verify>
    <automated>jq -e '.verdict | IN("pass", "fail")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
    <automated>grep -q "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -q "supersedes" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -E "Phase 201 closure|Phase 201 soak FAIL" .planning/STATE.md | head -1</automated>
  </verify>
  <acceptance_criteria>
    - soak-summary.json exists with canonical schema and a verdict value of "pass" or "fail"
    - 201-16-SOAK-VERDICT.md exists with all required sections
    - On PASS: 201-VERIFICATION.md frontmatter `status: verified`; REQUIREMENTS.md VALN-06 row updated; STATE.md records closure; 201-VALIDATION.md `nyquist_compliant: true`; 201-CONTEXT.md records A5 as superseded
    - On FAIL: 201-VERIFICATION.md retains `status: gaps_found` with new gap entries; STATE.md records soak failure + next-action choice; REQUIREMENTS.md row reflects deferred state
    - Commit recorded
  </acceptance_criteria>
  <done>
    Phase 201 closure posture is final. PASS = VALN-06 satisfied; FAIL = next gap-closure cycle scoped (A5 fallback OR v1.43+).
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 2 verdict:

- **PASS**: 201-VERIFICATION.md `status: verified`; REQUIREMENTS.md VALN-06 row says "Satisfied"; STATE.md records phase closure; A5 deferred (superseded). Phase 201 is closed.
- **FAIL**: 201-VERIFICATION.md retains `status: gaps_found` with new gap entries; STATE.md records failure + operator's next-action choice; Phase 201 stays open or closes-as-failed pending operator re-roadmap.
</verification>

<success_criteria>
- 24h soak runs to completion against the v1.42 binary that PASSED Plan 201-15 re-canary
- soak-summary.json captures both primary + secondary gates with cycle-fidelity primary metric
- Closure verdict (PASS or FAIL) is recorded across all four planning artifacts (VERIFICATION, REQUIREMENTS, STATE, VALIDATION)
- A5 fallback explicitly recorded as superseded (PASS) or as the next-action option (FAIL)
- The fail-OPEN-detection patterns from 201-12 (T+0 collectibility, daemon-restart invalidation) are honored
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SUMMARY.md` per the standard template. Include: soak timestamp, primary_gate verdict + delta, secondary_gate verdict + value, diagnostic distribution highlights, anti-windup trigger count, closure verdict, downstream artifacts updated.
</output>

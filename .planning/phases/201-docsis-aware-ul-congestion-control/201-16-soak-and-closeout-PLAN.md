---
phase: 201-docsis-aware-ul-congestion-control
plan: 16
type: execute
wave: 12
depends_on: [15]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-capture.sh
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
autonomous: false
gap_closure: true
supersedes: [12]
revision: 3  # Round-3 revision — closes codex 201-REVIEWS.md round-2 NEW-HIGH-2 (SOAK_TS not exported to remote shell — fix via uploaded script + positional arg) + NEW-HIGH-3 (jq reduce iterates accumulator — fix via $rows binding) + LOW-CODEX-5 PARTIALLY-CLOSED (distinct operator-approval checkpoint task BEFORE soak begins).
revision_driver: "201-REVIEWS.md round 2 — closes NEW-HIGH-2 (replace single-quoted heredoc + ${SOAK_TS} interpolation with explicit scp + ssh-with-positional-arg pattern; verbatim tmux invocation), NEW-HIGH-3 (rewrite jq pipeline to bind sorted rows as $rows and iterate $rows[] inside reduce, eliminating .[] iteration over accumulator), and LOW-CODEX-5 (add a distinct BLOCKING checkpoint task for D-19 operator approval BEFORE 24h soak starts; capture in 201-16-OPERATOR-APPROVAL-D19.md)."
requirements: [VALN-06]
tags: [phase-201, gap-closure, soak, valn-06-watchdog, closeout, verification, supersedes-201-12, codex-revised, codex-round-3]

must_haves:
  truths:
    - "24h Spectrum UL regression soak runs against the v1.42.1 binary that PASSED Plan 201-15 rev 3 re-canary (NOT the failed 201-11 binary; this plan supersedes 201-12)"
    - "**REV 3 (codex LOW-CODEX-5 closure):** A DISTINCT BLOCKING checkpoint task (Task 1) emits an operator-approval prompt for D-19 (the stricter primary gate: zero floor hits over 24h vs the original `<5/60s` watchdog only). The checkpoint captures operator confirmation in `201-16-OPERATOR-APPROVAL-D19.md` with a UTC timestamp + free-text justification field. The 24h soak (Task 2) is gated on this artifact's existence. autonomous: false on Task 1. The gate tightening cannot be silently entered into a verdict file later; it must be captured BEFORE the soak begins."
    - "PRIMARY GATE: floor_hit_cycles_total counter delta from soak-T+0 to soak-T+24h == 0. T+0 baseline taken from Plan 201-15 verdict.json. Skipping the T+0 capture is itself a fail-OPEN. Operator-approved per D-19 captured in Task 1."
    - "SECONDARY GATE: ul_hysteresis_suppression_rate_per_60s.mean < 5.0 across the soak window (D-14 watchdog threshold; preserved verbatim — this is the ORIGINAL VALN-06 success criterion, not relaxed)"
    - "Daemon restart mid-soak invalidates the primary gate (negative delta possible) and produces verdict=fail with reason `soak_primary_gate_uncollectible_negative_delta_<N>` — same fail-OPEN-detection pattern as Plan 201-12"
    - "**REV 3 (codex NEW-HIGH-2 closure):** Capture loop runs ON cake-shaper inside tmux, but the script is **uploaded via scp and invoked with a positional arg**, NOT embedded in a single-quoted heredoc. Specifically: (1) write the capture script locally to a temp file with no `${SOAK_TS}` interpolation needed (script reads `$1`); (2) `scp` it to `/tmp/soak-capture.sh` on cake-shaper; (3) `ssh cake-shaper 'tmux new-session -d -s wanctl-soak \"bash /tmp/soak-capture.sh <SOAK_TS> 2>&1 | tee /tmp/soak-capture.log\"'`. The local `$SOAK_TS` is interpolated by the local shell at the time of the ssh invocation, becoming a literal positional arg on the remote side. `set -u` on the remote shell sees `$1` (always defined) instead of `${SOAK_TS}` (was unbound). The verbatim tmux invocation (above) replaces rev-2's prose 'wrap in tmux'."
    - "**REV 3 (codex NEW-HIGH-3 closure):** The 60s sliding-window suppression-rate jq pipeline is rewritten to bind sorted rows as `$rows` and iterate `$rows[]` inside `reduce`. The previous rev-2 pipeline used `[.[] | select(...)]` inside `reduce`, which iterated the accumulator (a number after the first iteration), not the original rows. The fix: `jq -s 'sort_by(.t_monotonic) as $rows | reduce $rows[] as $sample (...; <use $rows for window selection>)'`. Computation is otherwise unchanged: 60s windows aligned by timestamp deltas, mean and p95 of suppressions_per_min."
    - "soak-summary.json captures: T+0 / T+24h floor_hit_cycles_total, suppressions_per_60s_mean + p95 (timestamp-windowed via `$rows` per NEW-HIGH-3 fix), RTT distribution, CAKE backlog distribution, headroom_state transitions, anti-windup trigger count, sample-coverage ratio (samples_observed / samples_expected_at_1Hz)"
    - "On PASS: Phase 201 closes with VALN-06 satisfied; 201-VERIFICATION.md status flips to verified; REQUIREMENTS.md VALN-06 row updated; STATE.md records phase closure; A5 fallback explicitly recorded as Deferred Idea (superseded); D-19 GATE TIGHTENING already captured pre-soak in operator-approval artifact"
    - "On FAIL: 201-VERIFICATION.md remains gaps_found with new gap entries; STATE.md records soak failure"
    - "201-VALIDATION.md `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md
      provides: "Operator-signed approval for the D-19 stricter primary soak gate (codex LOW-CODEX-5); captured BEFORE soak begins; gates Task 2"
      contains: "D-19"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-summary.json
      provides: "Standardized soak metrics; timestamp-windowed suppression rate computed via $rows-iterating jq (codex NEW-HIGH-3); sample-coverage ratio"
      contains: "floor_hit_cycles_total_delta_soak_window"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/soak/<TIMESTAMP>/soak-capture.sh
      provides: "Uploaded capture script (codex NEW-HIGH-2) — invoked with positional SOAK_TS arg, no heredoc interpolation needed"
      contains: "SOAK_TS=\"$1\""
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
      provides: "Operator-readable soak outcome + closure decisions + reference to D-19 operator-approval artifact"
      contains: "VALN-06"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
      provides: "Phase 201 closure verdict + per-criterion evidence pointers (re-verification mode)"
      contains: "verified"
  key_links:
    - from: "201-16-OPERATOR-APPROVAL-D19.md (Task 1 output)"
      to: "Task 2 gate (soak start blocked until artifact exists)"
      via: "Task 2 first action: `test -f 201-16-OPERATOR-APPROVAL-D19.md` else exit 2"
      pattern: "OPERATOR-APPROVAL-D19"
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
**Gap-closure Plan 4 of 4. PHASE CLOSEOUT. Revision 3 — closes codex round-2 NEW-HIGH-2 (SOAK_TS heredoc bug), NEW-HIGH-3 (jq reduce accumulator bug), and LOW-CODEX-5 PARTIALLY-CLOSED (distinct operator-approval checkpoint).**

Re-staged 24h soak watchdog + Phase 201 verification update. Supersedes Plan 201-12 (failed-canary path).

This plan executes ONLY if Plan 201-15 returned PASS. The soak validates that the control-model amendment (Plans 201-13 rev 3 + 201-14 rev 4) is stable over 24h continuous operation, with both the primary cycle-fidelity gate (floor-hit counter delta = 0) and the legacy secondary watchdog (UL hysteresis suppression rate < 5/60s mean) green.

**Three round-3 changes from rev 2:**

1. **NEW-HIGH-2 closure — SOAK_TS not exported to remote shell.** Rev 2 used `ssh cake-shaper bash <<'REMOTE_EOF' ... ${SOAK_TS} ... REMOTE_EOF` with `set -u` on the remote. The single-quoted heredoc prevents local interpolation; remote shell hits `${SOAK_TS}` and aborts with "unbound variable" before any capture starts.

   **Rev 3 fix:** Upload the capture script via `scp` and invoke with a positional argument. The script is plain bash, takes `$1` as SOAK_TS, no heredoc-vs-set-u interaction. Specifically:
   - Step 1: write `soak-capture.sh` locally (the script reads `$1` for SOAK_TS).
   - Step 2: `scp soak-capture.sh cake-shaper:/tmp/soak-capture.sh && ssh cake-shaper "chmod +x /tmp/soak-capture.sh"`.
   - Step 3: launch via verbatim tmux command:
     ```
     ssh cake-shaper "tmux new-session -d -s wanctl-soak \"bash /tmp/soak-capture.sh ${SOAK_TS} 2>&1 | tee /tmp/soak-capture.log\""
     ```
     The local `${SOAK_TS}` is expanded by the local shell into the literal value (e.g. `20260505T010203Z`), becoming a literal string in the ssh command. The remote tmux session sees `bash /tmp/soak-capture.sh 20260505T010203Z 2>&1 | tee /tmp/soak-capture.log` with no unbound variable.

   The capture script is also persisted into the soak directory (`soak/<TS>/soak-capture.sh`) for evidence — operator can re-read the exact script that ran.

2. **NEW-HIGH-3 closure — jq reduce iterates accumulator.** Rev 2's pipeline used `reduce $rows[] as $w (0; . + ([.[] | select(...)] | length))`. Inside `reduce`, `.` is the accumulator (a number after iteration #1), so `[.[] | select(...)]` iterates over fields of the accumulator number — wrong shape, returns nothing useful.

   **Rev 3 fix:** Bind sorted rows as `$rows` BEFORE entering `reduce`, then iterate `$rows[]` for the inner select:

   ```jq
   jq -s '
     sort_by(.t_monotonic) as $rows
     | ($rows[0].t_monotonic) as $t_start
     | ($rows[-1].t_monotonic) as $t_end
     | (($t_end - $t_start) / 60.0 | floor) as $window_count
     | reduce range(0; $window_count) as $w (
         {windows: []};
         .windows += [
           ([$rows[]
             | select(.t_monotonic >= ($t_start + ($w * 60)))
             | select(.t_monotonic <  ($t_start + (($w + 1) * 60)))
             | .suppressions_per_min // 0
            ] as $vals
            | if ($vals | length) > 0 then ($vals | add / length) else null end)
         ]
       )
     | .windows |= map(select(. != null))
     | {
         samples_total: ($rows | length),
         t_start: $t_start,
         t_end: $t_end,
         window_count: (.windows | length),
         suppressions_per_min_mean: (
           if (.windows | length) > 0 then (.windows | add / length) else null end
         ),
         suppressions_per_min_p95: (
           if (.windows | length) > 0
           then ((.windows | sort) | .[(((.windows | length) * 95 / 100) | floor)])
           else null end
         ),
         suppressions_per_min_max: ((.windows // []) | max),
         expected_samples_at_1hz: (($t_end - $t_start) | floor),
         sample_coverage_ratio: (($rows | length) / (($t_end - $t_start) + 1))
       }
   ' "$SOAK_DIR/soak-capture.ndjson" > "$SOAK_DIR/suppression-stats.json"
   ```

   The key change: `[$rows[] | select(...)]` (NOT `[.[] | select(...)]`). `$rows` is bound once, outside `reduce`, and used inside the reduction body for window selection. The accumulator `.` only carries the `windows` list being built up.

3. **LOW-CODEX-5 PARTIALLY-CLOSED → CLOSED — distinct operator-approval checkpoint.** Rev 2 wrote D-19 into 201-CONTEXT.md AS PART OF Task 2's verdict-recording action — i.e., the gate-tightening was recorded as "operator-approved" by the planner without an explicit operator interaction. Codex correctly flagged this: the operator must explicitly approve D-19 BEFORE the soak begins, not have the planner write "operator-approved" into an artifact post hoc.

   **Rev 3 fix:** Add a distinct BLOCKING `checkpoint:human-verify` task (Task 1, autonomous: false) that:
   - Presents the D-19 gate-tightening rationale to the operator (zero floor hits over 24h vs the original `<5/60s` suppression-rate watchdog).
   - Captures the operator's confirmation (resume signal "approved") OR rejection ("rejected: <reason>").
   - Writes `201-16-OPERATOR-APPROVAL-D19.md` containing:
     - UTC timestamp of approval
     - Operator decision (approved / rejected)
     - Free-text justification field (operator-supplied)
     - The full D-19 statement being approved
   - Task 2 (the actual soak) gates on this artifact's existence — first action is `test -f 201-16-OPERATOR-APPROVAL-D19.md && grep -q "decision: approved" 201-16-OPERATOR-APPROVAL-D19.md` else exit 2 with a "soak start blocked: D-19 not operator-approved" message.

   This ordering means the gate-tightening decision is captured as a discrete operator artifact BEFORE the soak begins, not assumed.

**autonomous: false** because: (1) D-19 operator-approval checkpoint (Task 1); (2) 24h soak operator-initiated and operator-monitored (Task 2 first half); (3) closure decisions update REQUIREMENTS.md / STATE.md and require operator approval per CLAUDE.md change policy.
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
<!-- Soak protocol mirrors Plan 201-12 verbatim except for the three rev-3 changes:
     1. Distinct operator-approval checkpoint for D-19 (codex LOW-CODEX-5)
     2. Capture script uploaded + positional-arg invocation; verbatim tmux command (codex NEW-HIGH-2)
     3. jq pipeline binds $rows for window selection inside reduce (codex NEW-HIGH-3) -->

T+0 baseline source (Plan 201-12 step 1.5 pattern preserved):
1. Primary: `jq -r '.floor_hit_cycles_total_loaded_window_end' <201-15-canary-verdict.json>`
2. Fallback: live `curl -s http://10.10.110.223:9101/health | jq '.wans[0].upload.floor_hit_cycles_total'` at soak start.

T+24h reading: live /health at soak end. Counter is monotonic-since-daemon-restart; restart between T+0 and T+24h → verdict=fail with reason `soak_primary_gate_uncollectible_negative_delta_<N>`.

**Capture script invocation (codex NEW-HIGH-2):**

The capture script lives in three places:
- Local working tree (committed under `soak/<TS>/soak-capture.sh` for evidence)
- `/tmp/soak-capture.sh` on cake-shaper (the one that actually runs)
- The verbatim tmux command runs that remote copy with the positional SOAK_TS arg.

Verbatim tmux invocation (rev-3 fix for NEW-HIGH-2 prose 'wrap in tmux'):
```
ssh cake-shaper "tmux new-session -d -s wanctl-soak \"bash /tmp/soak-capture.sh ${SOAK_TS} 2>&1 | tee /tmp/soak-capture.log\""
```
The local shell expands `${SOAK_TS}` into the literal value before sending to cake-shaper. The remote tmux session sees a literal string for the soak timestamp.

**Capture script content (codex NEW-HIGH-2 — reads $1, no heredoc interpolation):**

```bash
#!/usr/bin/env bash
set -euo pipefail
SOAK_TS="${1:?SOAK_TS positional arg required}"
SOAK_DURATION_SEC=86400  # 24h
HEALTH_URL="http://127.0.0.1:9101/health"
CAPTURE_DIR="/var/tmp/wanctl-soak-${SOAK_TS}"
mkdir -p "$CAPTURE_DIR"

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ $(date +%s) -lt $SOAK_END ]; do
  T_MONO=$(awk '{print $1; exit}' /proc/uptime)
  T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')
  curl -s "$HEALTH_URL" \
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
        docsis_mode_active: .wans[0].upload.docsis_mode_active,
        red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
        red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
      }' >> "$CAPTURE_DIR/soak-capture.ndjson"
  sleep 1
done
```

At T+24h, copy `soak-capture.ndjson` back to operator workstation:
```
scp cake-shaper:/var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson $SOAK_DIR/soak-capture.ndjson
```

Anti-windup trigger count: read directly from `.wans[0].upload.anti_windup_triggers` at T+0 and T+24h; the delta IS the trigger count over the soak window. Cross-check against `journalctl -u wanctl@spectrum --since` for rate-limited INFO logs (Plan 201-14 rev 4 emits at most one log per anti_windup_cycles interval).

REQUIREMENTS.md update pattern: VALN-06 row currently `Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement)`. On PASS: append `→ Satisfied via Phase 201 (canary <201-15-TS> + 24h soak <SOAK_TS>; primary gate floor_hit_cycles_total_delta_soak_window == 0 per operator-approved D-19, see 201-16-OPERATOR-APPROVAL-D19.md)`. On FAIL: append `→ Phase 201 gap-closure soak FAIL`.
</interfaces>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: D-19 operator approval — present the stricter primary soak gate to operator and capture explicit approval BEFORE soak begins (codex LOW-CODEX-5)</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (D-14 — original `<5/60s` watchdog)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (canary PASS verdict; build identity 1.42.1)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (LOW-CODEX-5 — distinct operator-approval checkpoint required)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md</files>
  <what-built>
    Plan 201-15 rev 3 returned PASS. The canary verdict file shows `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`. v1.42.1 binary is deployed on cake-shaper. The control-model amendment (rev-4 bounded-absolute decay + cap-and-clamp anti-windup) is proven on production hardware for the 10-15 min canary window.

    The 24h soak that follows uses BOTH a primary cycle-fidelity gate AND a secondary watchdog. The PRIMARY gate is **STRICTER** than the original D-14 success criterion:

    - **Original D-14 (CONTEXT.md):** suppression rate `<5/60s` mean over 24h. This is a coarse-grained watchdog.
    - **D-19 (proposed for Phase 201 closure):** floor_hit_cycles_total counter delta over the 24h soak window MUST be exactly 0. This aligns the soak's primary gate with the canary's primary gate (both use the cycle-fidelity floor-hit counter).

    Codex LOW-CODEX-5 (round 2): tightening D-14 to D-19 changes the success bar. The operator must explicitly approve this BEFORE the soak begins, not have it written into a verdict file post-hoc.
  </what-built>
  <how-to-verify>
    1. **Review the D-19 statement** to be approved (verbatim text that will be written into the artifact):

       > **D-19 (Phase 201 closure gate tightening):** Phase 201 closure adds a STRICTER PRIMARY soak gate beyond the original D-14 secondary watchdog. With the rev-4 control-model amendment in place (bounded-absolute decay + cap-and-clamp anti-windup, Plans 201-13 rev 3 / 201-14 rev 4), zero floor hits over a 24h DOCSIS soak (`floor_hit_cycles_total_delta_soak_window == 0`) is achievable as a cycle-fidelity proof of fix. The original D-14 `<5/60s` suppression-rate threshold STAYS as the SECONDARY gate (legacy compatibility, more permissive). Tightening the primary gate aligns the soak's primary metric with the canary's primary metric, so PASS at canary-time and PASS at soak-time use the same cycle-fidelity surface. Operator-approved 2026-05-XX as the closure shape for Phase 201 gap-closure path (b). Codex 201-REVIEWS LOW-CODEX-5: this tightening is captured here as a distinct operator-approval artifact, NOT silently written into a verdict file.

    2. **Verify prerequisite** (canary PASS):
       ```
       jq -e '.verdict == "pass"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       ```

    3. **Operator decision** — type one of:
       - `approved: <free-text justification>`  (proceed to Task 2 soak with D-19 active)
       - `rejected: <reason>`  (Task 2 will not run; closure path stays at canary-PASS-only and soak deferred)

    4. **Write artifact** — based on operator response, write `201-16-OPERATOR-APPROVAL-D19.md`:
       ```markdown
       # Phase 201 — D-19 Operator Approval (Stricter Primary Soak Gate)

       timestamp: <UTC ISO from `date -u -Iseconds`>
       decision: <approved|rejected>
       operator_justification: |
         <free-text from operator>

       ---

       ## D-19 Statement (Approved/Rejected)

       <verbatim D-19 paragraph from step 1>

       ---

       ## References

       - Plan 201-15 rev 3 canary PASS: <path to canary verdict.json>
       - 201-CONTEXT.md original D-14 watchdog
       - 201-REVIEWS.md round 2 LOW-CODEX-5 (distinct approval checkpoint required)
       - Captures operator approval BEFORE soak begins; gates Task 2.
       ```
  </how-to-verify>
  <resume-signal>Type one of: "approved: &lt;your free-text justification&gt;" or "rejected: &lt;reason&gt;". Approval is required before Task 2 can run.</resume-signal>
  <acceptance_criteria>
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md` exists
    - File contains a `decision: approved` OR `decision: rejected` line
    - File contains a `timestamp:` line with UTC ISO format (`date -u -Iseconds` output)
    - File contains a non-empty `operator_justification:` block (operator-supplied free-text)
    - File contains the verbatim D-19 statement
    - On `decision: rejected`: Task 2 is skipped (the soak will not run); operator must decide separately whether to defer Phase 201 closure or accept canary-PASS-only as the closure shape (closure decision out of scope of this plan)
  </acceptance_criteria>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Operator-run 24h soak ON cake-shaper via uploaded script + positional SOAK_TS arg + verbatim tmux invocation; capture T+0 baseline; capture suppression-rate distribution at 1Hz with monotonic timestamps</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 1 — original operator-soak playbook)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (T+0 baseline source)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md (Task 1 output — must show decision: approved)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (NEW-HIGH-2 — uploaded script + positional arg + verbatim tmux)
  </read_first>
  <what-built>
    Task 1 captured the D-19 operator approval. Plans 201-13 rev 3 + 201-14 rev 4 + 201-15 rev 3 are all complete; v1.42.1 binary is deployed and running on cake-shaper.
  </what-built>
  <how-to-verify>
    1. **GATE: Verify Task 1 D-19 approval exists and is `approved`** (codex LOW-CODEX-5):
       ```
       test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md \
         && grep -q "^decision: approved" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md \
         || { echo "soak start BLOCKED: D-19 not operator-approved (Task 1 must complete with decision=approved)"; exit 2; }
       ```
       If this fails, abort. Task 2 cannot run without explicit D-19 approval.

    2. **Verify other prerequisites** (canary PASS, version, controller knobs):
       ```
       jq -e '.verdict == "pass"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
       curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1" and .wans[0].upload.docsis_mode_active == true and .wans[0].upload.anti_windup_cycles == 60 and .wans[0].upload.red_decay_step_pct == 0.02 and .wans[0].upload.red_decay_delta_max_pct == 0.10'
       ```
       All four must succeed before starting the soak.

    3. **Capture T+0 baseline** (REVIEWS round-5 collectibility — REQUIRED before the 24h wait):
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

    4. **Write capture script locally** (codex NEW-HIGH-2 — script reads `$1`, no heredoc interpolation):

       Create `$SOAK_DIR/soak-capture.sh` with the verbatim content shown in the <interfaces> "Capture script content" block. The script uses `SOAK_TS="${1:?SOAK_TS positional arg required}"` so a missing arg fails with an explicit message. Make it executable locally:
       ```
       chmod +x $SOAK_DIR/soak-capture.sh
       ```

    5. **Upload capture script to cake-shaper** (codex NEW-HIGH-2):
       ```
       scp $SOAK_DIR/soak-capture.sh cake-shaper:/tmp/soak-capture.sh
       ssh cake-shaper "chmod +x /tmp/soak-capture.sh"
       ```

    6. **Launch soak in tmux on cake-shaper with verbatim invocation** (codex NEW-HIGH-2 — replace rev-2 prose 'wrap in tmux'):
       ```
       ssh cake-shaper "tmux new-session -d -s wanctl-soak \"bash /tmp/soak-capture.sh ${SOAK_TS} 2>&1 | tee /tmp/soak-capture.log\""
       ```
       Note: the local shell expands `${SOAK_TS}` into the literal timestamp (e.g. `20260505T010203Z`) BEFORE sending the ssh command. The remote tmux session sees:
       ```
       bash /tmp/soak-capture.sh 20260505T010203Z 2>&1 | tee /tmp/soak-capture.log
       ```
       No `${SOAK_TS}` expansion happens on the remote side; the script gets it via `$1`.

       Verify the tmux session started:
       ```
       ssh cake-shaper "tmux list-sessions | grep wanctl-soak"
       ssh cake-shaper "ls -lh /var/tmp/wanctl-soak-${SOAK_TS}/"
       sleep 5
       ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson"
       ```
       Line count should be >= 1 within 5 seconds (proves capture loop is writing).

    7. **Choose capture host documentation**:
       ```
       echo "capture_host: cake-shaper (on-host tmux, codex NEW-HIGH-2 uploaded-script + positional-arg pattern)" > $SOAK_DIR/capture-host.txt
       ```

    8. **Detect daemon restart mid-soak** (operator-monitored, periodically):
       ```
       ssh cake-shaper "sudo systemctl is-active wanctl@spectrum"   # must say 'active' throughout
       ```
       If at any point it shows inactive/failed, record the restart timestamp in `$SOAK_DIR/restart-events.log`. The gate verdict in Task 3 will then be fail-OPEN.

    9. **At T+24h**, capture end values and copy capture file back:
       ```
       T24_LIVE=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.floor_hit_cycles_total')
       T24_AW_TRIGGERS=$(curl -s http://10.10.110.223:9101/health | jq -r '.wans[0].upload.anti_windup_triggers')
       echo "{\"t24_live\": $T24_LIVE, \"t24_anti_windup_triggers\": $T24_AW_TRIGGERS, \"t24_captured_at_utc\": \"$(date -u -Iseconds)\"}" \
         > $SOAK_DIR/t24-baseline.json
       scp cake-shaper:/var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson $SOAK_DIR/soak-capture.ndjson
       ```

    10. **Hand off to Task 3** with the soak directory path.
  </how-to-verify>
  <resume-signal>Type "soak complete: &lt;SOAK_DIR&gt;" with the directory path, OR "soak aborted: &lt;reason&gt;" if the soak couldn't run to completion.</resume-signal>
  <acceptance_criteria>
    - **D-19 GATE PASSED:** `201-16-OPERATOR-APPROVAL-D19.md` exists with `decision: approved`
    - **Capture script artifact present:** `$SOAK_DIR/soak-capture.sh` exists locally, contains `SOAK_TS="$1"` (or `${1:?...}`)
    - $SOAK_DIR/t0-baseline.json exists with t0_anti_windup_triggers field
    - $SOAK_DIR/t24-baseline.json exists with t24_anti_windup_triggers field
    - $SOAK_DIR/capture-host.txt exists
    - $SOAK_DIR/soak-capture.ndjson exists, non-empty, every row has both `t_wall` and `t_monotonic` fields. Validate: `head -1 $SOAK_DIR/soak-capture.ndjson | jq -e '.t_wall and (.t_monotonic | type == "number")'`.
    - Sample count >= 86000 (1% loss budget on 24h × 1Hz capture)
    - $SOAK_DIR/restart-events.log either does not exist or is empty
    - Operator typed the resume signal with directory path
  </acceptance_criteria>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Compute soak verdict via $rows-iterating jq pipeline (codex NEW-HIGH-3 fix); write soak-summary.json + 201-16-SOAK-VERDICT.md; update VERIFICATION/REQUIREMENTS/STATE/CONTEXT (D-19 already approved in Task 1)</name>
  <read_first>
    - $SOAK_DIR/t0-baseline.json, $SOAK_DIR/t24-baseline.json, $SOAK_DIR/soak-capture.ndjson, $SOAK_DIR/restart-events.log (if exists), $SOAK_DIR/capture-host.txt
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md (Task 1 artifact — referenced from VERDICT/CONTEXT updates)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Task 2 — original closeout playbook format)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (current gaps_found state)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (Decisions section — D-19 will be appended REFERENCING the operator-approval artifact)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (NEW-HIGH-3 — $rows binding for jq reduce)
    - .planning/REQUIREMENTS.md (VALN-06 row)
    - .planning/STATE.md
  </read_first>
  <files>
    .planning/phases/201-docsis-aware-ul-congestion-control/soak/<SOAK_TS>/soak-summary.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/soak/<SOAK_TS>/suppression-stats.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/soak/<SOAK_TS>/diagnostic-distribution.json,
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
       - If $PRIMARY_DELTA > 0: verdict=fail, reason=`soak_primary_gate_floor_hit_delta_${PRIMARY_DELTA}` (D-19 zero-tolerance, operator-approved in Task 1)

    2. **Compute secondary gate via TIMESTAMP-WINDOWED 60s mean — codex NEW-HIGH-3 fix using `$rows` binding:**

       Run the rewritten jq pipeline (verbatim from <objective> NEW-HIGH-3 fix):
       ```bash
       jq -s '
         sort_by(.t_monotonic) as $rows
         | ($rows[0].t_monotonic) as $t_start
         | ($rows[-1].t_monotonic) as $t_end
         | (($t_end - $t_start) / 60.0 | floor) as $window_count
         | reduce range(0; $window_count) as $w (
             {windows: []};
             .windows += [
               ([$rows[]
                 | select(.t_monotonic >= ($t_start + ($w * 60)))
                 | select(.t_monotonic <  ($t_start + (($w + 1) * 60)))
                 | .suppressions_per_min // 0
                ] as $vals
                | if ($vals | length) > 0 then ($vals | add / length) else null end)
             ]
           )
         | .windows |= map(select(. != null))
         | {
             samples_total: ($rows | length),
             t_start: $t_start,
             t_end: $t_end,
             window_count: (.windows | length),
             suppressions_per_min_mean: (
               if (.windows | length) > 0 then (.windows | add / length) else null end
             ),
             suppressions_per_min_p95: (
               if (.windows | length) > 0
               then ((.windows | sort) | .[(((.windows | length) * 95 / 100) | floor)])
               else null end
             ),
             suppressions_per_min_max: ((.windows // []) | max),
             expected_samples_at_1hz: (($t_end - $t_start) | floor),
             sample_coverage_ratio: (($rows | length) / (($t_end - $t_start) + 1))
           }
       ' "$SOAK_DIR/soak-capture.ndjson" > "$SOAK_DIR/suppression-stats.json"

       SUPP_MEAN=$(jq -r '.suppressions_per_min_mean' $SOAK_DIR/suppression-stats.json)
       COVERAGE=$(jq -r '.sample_coverage_ratio' $SOAK_DIR/suppression-stats.json)
       ```

       Note the critical change vs rev 2: `[$rows[] | select(...)]` (NOT `[.[] | select(...)]`). `$rows` is bound once outside `reduce`; the inner select iterates the original sorted rows, not the accumulator. This is the codex NEW-HIGH-3 fix.

       - If $SUPP_MEAN < 5.0: secondary gate PASS
       - Else: verdict=fail, reason=`soak_secondary_gate_suppressions_per_min_${SUPP_MEAN}`
       - If $COVERAGE < 0.95: append warning to verdict (capture loss high; gate values may be approximate)
       - Disagreement (one PASS one FAIL): verdict=fail, reason=`soak_gates_disagreement_primary_${PRIMARY_GATE}_secondary_${SECONDARY_GATE}`

    3. **Compute diagnostic distributions**:
       ```bash
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
       (No `$rows` binding needed here because there's no `reduce`-with-inner-select; this jq is a single top-level pipeline that legitimately uses `.[]` against the slurped array.)

    4. **Anti-windup trigger count**:
       ```
       T0_AW=$(jq -r '.t0_anti_windup_triggers' $SOAK_DIR/t0-baseline.json)
       T24_AW=$(jq -r '.t24_anti_windup_triggers' $SOAK_DIR/t24-baseline.json)
       ANTI_WINDUP_DELTA=$((T24_AW - T0_AW))
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
         "capture_method": "uploaded script + positional SOAK_TS arg + verbatim tmux (codex NEW-HIGH-2)",
         "sample_coverage_ratio": <COVERAGE>,
         "primary_gate": {
           "name": "floor_hit_cycles_total_delta_soak_window",
           "threshold": "== 0 (operator-approved D-19, see 201-16-OPERATOR-APPROVAL-D19.md)",
           "t0": <T0>, "t24": <T24>, "delta": <PRIMARY_DELTA>,
           "verdict": "<pass|fail>",
           "reason": "<reason or null>"
         },
         "secondary_gate": {
           "name": "ul_hysteresis_suppression_rate_per_60s_mean",
           "computation": "timestamp-windowed 60s sliding mean (codex NEW-HIGH-3 fix: $rows binding inside reduce)",
           "value": <SUPP_MEAN>, "threshold": 5.0,
           "verdict": "<pass|fail>"
         },
         "diagnostic_distribution": <contents of diagnostic-distribution.json>,
         "anti_windup_triggers_delta": <ANTI_WINDUP_DELTA>,
         "anti_windup_log_count": <ANTI_WINDUP_LOGS>,
         "verdict": "<pass|fail>",
         "reason": "<combined reason>",
         "operator_approval_d19": ".planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md"
       }
       ```

    6. **Write 201-16-SOAK-VERDICT.md** mirroring 201-11-CANARY-VERDICT.md format. Required sections:
       - Soak Run Metadata (incl. capture host, capture method per codex NEW-HIGH-2, sample coverage)
       - Primary Gate (incl. EXPLICIT REFERENCE to `201-16-OPERATOR-APPROVAL-D19.md` as the source of D-19 approval — NOT a planner-written claim)
       - Secondary Gate (note: timestamp-windowed via `$rows` binding per codex NEW-HIGH-3)
       - Diagnostic Distribution
       - Anti-Windup Triggers (counter delta + log count)
       - Decision (PASS/FAIL/aborted)
       - Closure Action

    7. **Append D-19 reference to 201-CONTEXT.md** — this is now an artifact reference, NOT a planner-written approval claim:
       Append to the `## Decisions` section, in the appropriate sub-section (after D-18, before any Claude's Discretion subsection):
       ```markdown
       ### Soak Closure Gate (gap-closure path b, 2026-05-XX)

       - **D-19 (operator-approved gate tightening):** Phase 201 closure adds a STRICTER PRIMARY soak gate beyond the original D-14 secondary watchdog: `floor_hit_cycles_total_delta_soak_window == 0`. Original D-14 `<5/60s` suppression-rate threshold STAYS as SECONDARY gate. Tightening aligns the soak's primary metric with the canary's primary metric. **Operator approval captured pre-soak in `201-16-OPERATOR-APPROVAL-D19.md`** (codex 201-REVIEWS round-2 LOW-CODEX-5: distinct operator-approval checkpoint required, not a planner-written claim in a verdict file).
       ```

    8. **On PASS**: update artifacts:
       - **201-VERIFICATION.md**: change `status: gaps_found` → `status: verified` in frontmatter; flip truth-1 (floor_hit_cycles_total) to VERIFIED with evidence pointer; flip truth-2 (24h soak) to VERIFIED; flip truth-3 (A5 fallback) to SUPERSEDED; convert `## Gaps Summary` to `## Closure Summary`.
       - **REQUIREMENTS.md**: VALN-06 row → `Satisfied via Phase 201 (re-canary <201-15-TS> + 24h soak <SOAK_TS>; D-19 primary gate met, see 201-16-OPERATOR-APPROVAL-D19.md)`.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 closure (PASS via gap-closure path b)`.
       - **201-VALIDATION.md**: set `nyquist_compliant: true`, `wave_0_complete: true`.
       - **201-CONTEXT.md**: append D-19 (per step 7) AND under `## Deferred Ideas` `### Not in Scope for Phase 201` add an A5-superseded note.

    9. **On FAIL**: update artifacts:
       - **201-VERIFICATION.md**: stays `gaps_found`; append new gap entries.
       - **STATE.md**: append `## 2026-05-XX — Phase 201 soak FAIL (gap-closure path)`.
       - **REQUIREMENTS.md**: VALN-06 stays Deferred; append `→ Phase 201 gap-closure soak FAIL (<SOAK_TS>); next action <A5|v1.43+>`.
       - 201-CONTEXT.md still gets D-19 reference appended (the gate-tightening decision was taken; soak failed against it — that's an honest record).
       - Do NOT mark 201-VALIDATION.md complete.

    10. **Commit**: `feat(201-16): close Phase 201 — VALN-06 satisfied via gap-closure path (b); D-19 operator-approved pre-soak in 201-16-OPERATOR-APPROVAL-D19.md` on PASS, or `docs(201-16): record soak FAIL; route to <A5|v1.43+>` on FAIL.
  </action>
  <verify>
    <automated>jq -e '.verdict | IN("pass", "fail")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
    <automated>grep -q "VALN-06" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -q "supersedes" .planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md</automated>
    <automated>grep -q "D-19" .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md</automated>
    <automated>grep -q "201-16-OPERATOR-APPROVAL-D19.md" .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md</automated>
    <automated>grep -E "Phase 201 closure|Phase 201 soak FAIL" .planning/STATE.md | head -1</automated>
    <automated>jq -e '.secondary_gate.computation | contains("$rows")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
    <automated>jq -e '.capture_method | contains("uploaded script")' .planning/phases/201-docsis-aware-ul-congestion-control/soak/*/soak-summary.json | head -1</automated>
  </verify>
  <acceptance_criteria>
    - soak-summary.json exists with verdict ∈ {"pass", "fail"}, sample_coverage_ratio recorded
    - **codex NEW-HIGH-2 closure proof**: soak-summary.json `capture_method` field references "uploaded script" and "positional SOAK_TS arg"
    - **codex NEW-HIGH-3 closure proof**: soak-summary.json `secondary_gate.computation` references `$rows` binding
    - 201-16-SOAK-VERDICT.md exists with all required sections AND explicit reference to `201-16-OPERATOR-APPROVAL-D19.md` as source of D-19 approval (not planner-written)
    - 201-CONTEXT.md contains D-19 with explicit reference to `201-16-OPERATOR-APPROVAL-D19.md` (codex LOW-CODEX-5)
    - On PASS: 201-VERIFICATION.md `status: verified`; REQUIREMENTS.md VALN-06 row updated with D-19 reference + 201-16-OPERATOR-APPROVAL-D19.md citation; STATE.md records closure; 201-VALIDATION.md `nyquist_compliant: true`; A5 superseded note in 201-CONTEXT.md
    - On FAIL: 201-VERIFICATION.md retains `gaps_found` with new gaps; STATE.md records failure; D-19 reference still appended to 201-CONTEXT.md
    - Commit recorded
  </acceptance_criteria>
  <done>
    Phase 201 closure posture is final. PASS = VALN-06 satisfied with operator-approved D-19 primary gate (approval captured PRE-soak in 201-16-OPERATOR-APPROVAL-D19.md per codex LOW-CODEX-5; jq computation uses `$rows` binding per codex NEW-HIGH-3; capture script uploaded with positional arg per codex NEW-HIGH-2). FAIL = next gap-closure cycle scoped.
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 3 verdict:

- **PASS**: 201-VERIFICATION.md `status: verified`; REQUIREMENTS.md VALN-06 says "Satisfied" with citation to 201-16-OPERATOR-APPROVAL-D19.md; STATE.md records phase closure; A5 superseded; D-19 recorded as operator-approved with PRE-soak artifact reference. Phase 201 is closed.
- **FAIL**: 201-VERIFICATION.md retains `gaps_found`; STATE.md records failure + next-action choice; D-19 reference still recorded in CONTEXT (decision-taking is independent of outcome).
</verification>

<success_criteria>
- D-19 operator approval captured PRE-soak in `201-16-OPERATOR-APPROVAL-D19.md` (codex LOW-CODEX-5)
- 24h soak runs to completion against the v1.42.1 binary that PASSED Plan 201-15 rev 3 re-canary
- Capture script uploaded to cake-shaper as `/tmp/soak-capture.sh`, invoked with positional SOAK_TS arg via verbatim tmux command (codex NEW-HIGH-2 — replaces single-quoted heredoc bug)
- Every captured row has monotonic timestamp; secondary gate uses timestamp-windowed 60s mean computed via `$rows`-bound jq pipeline (codex NEW-HIGH-3 — replaces broken `[.[] | select(...)]` inside reduce)
- soak-summary.json captures both gates with cycle-fidelity primary metric and references the D-19 operator-approval artifact
- D-19 (gate tightening) recorded in 201-CONTEXT.md AS A REFERENCE to 201-16-OPERATOR-APPROVAL-D19.md (codex LOW-CODEX-5 — not a planner-written claim)
- Closure verdict recorded across all four planning artifacts (VERIFICATION, REQUIREMENTS, STATE, VALIDATION)
- A5 fallback explicitly recorded as superseded (PASS) or as next-action option (FAIL)
- Sample coverage ratio recorded; daemon-restart fail-OPEN-detection honored
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SUMMARY.md` per the standard template. Include: revision number (3); D-19 operator-approval artifact path + decision; soak timestamp; capture host (cake-shaper, on-host tmux via uploaded script + positional arg); sample coverage ratio; primary gate verdict + delta; secondary gate verdict + value (with note that computation uses `$rows`-bound jq per codex NEW-HIGH-3); diagnostic distribution highlights; anti-windup triggers delta + log count; closure verdict; downstream artifacts updated; codex review findings closed (LOW-CODEX-5 operator approval, NEW-HIGH-2 uploaded script + positional arg, NEW-HIGH-3 $rows binding).
</output>
</content>
</invoke>
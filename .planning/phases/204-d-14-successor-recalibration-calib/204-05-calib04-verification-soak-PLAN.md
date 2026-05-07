---
id: 204-05
phase: 204
plan: 05
type: execute
wave: 5
depends_on:
  - 204-04
files_modified:
  - .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-capture.ndjson
  - .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-summary.json
  - .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md
autonomous: false
production_canary: true
created: 2026-05-06
requirements:
  - CALIB-04
notes:
  - "FAIL-handling per 204-RESEARCH.md §Risk 6 lines 743-749 — three explicit recovery branches encoded in Task 3."
  - "All four researcher-default open questions (Q3/Q4/Q5/Q6) already adopted in upstream plans; no new decisions in this plan."
must_haves:
  truths:
    - "CALIB-04 24h verification soak NDJSON captured at .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-capture.ndjson with line count >= 86,000."
    - "soak-summary.json computed via .venv/bin/python scripts/soak_summary_aggregate.py contains both top-level keys: secondary_gate_legacy AND secondary_gate_completed_window (CALIB-03 dual-emission active)."
    - "Pass criterion enforced (per 204-RESEARCH.md §Q8 lines 411-417): primary_gate.verdict == 'pass' AND primary_gate.delta == 0 AND secondary_gate_completed_window.verdict == 'pass'."
    - "204-05-CALIB-04-SOAK-VERDICT.md exists with verdict: pass (or verdict: fail with explicit FAIL branch path per 204-RESEARCH.md §Risk 6)."
    - "On PASS: verdict file references soak-summary.json by path AND cites the four numeric gate fields verbatim (primary_gate.delta, secondary_gate_completed_window.value, .threshold, .verdict)."
    - "On FAIL: verdict file records which branch was taken (re-approve threshold / investigate / re-run for transient) and operator-decision rationale."
    - "git diff b72b463..HEAD -- src/wanctl/ produces 0 lines (SAFE-07 invariant)."
  artifacts:
    - path: .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-capture.ndjson
      provides: "24h verification soak raw capture from production cake-shaper under v1.43.0 binary with operator-approved threshold."
    - path: .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-summary.json
      provides: "Aggregator output containing both gate blocks; the verdict source of truth."
      contains: "secondary_gate_completed_window"
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md
      provides: "Operator-readable CALIB-04 verdict — pass closes CALIB-04; fail branches to FAIL-handling decision."
      contains: "verdict:"
  key_links:
    - from: "scripts/soak-capture.sh on cake-shaper"
      to: "soak/<CALIB_04_TS>/soak-capture.ndjson"
      via: "tmux + scp-back per Plan 201-16 protocol"
      pattern: "soak-capture.sh"
    - from: "soak/<CALIB_04_TS>/soak-summary.json::secondary_gate_completed_window.verdict"
      to: "204-05-CALIB-04-SOAK-VERDICT.md verdict field"
      via: "operator reads dual-gate state, records pass/fail"
      pattern: "secondary_gate_completed_window"
---

<objective>
Operator runs the 24h verification soak on cake-shaper. The aggregator (extended in Plan 204-04) renders the dual-gate verdict in `soak-summary.json`. CALIB-04 PASSES iff both `primary_gate.verdict == "pass"` (D-19 stays 0 floor hits) AND `secondary_gate_completed_window.verdict == "pass"` (D-14-successor at the operator-approved threshold). Verdict committed.

Purpose: This is the milestone-defining proof that the recalibrated threshold is correct under the actual post-Plan-201-14 production control surface. PASS closes the metric watchdog cleanly without any controller change. FAIL branches into one of three documented recovery paths.

Output: 24h capture + soak-summary.json + verdict file. Zero `src/wanctl/` source diff (SAFE-07).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-04-SUMMARY.md
@scripts/soak-capture.sh
@scripts/soak_summary_aggregate.py
@scripts/calib_02_threshold.json
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md

<interfaces>
<!-- CALIB-04 dual-gate criterion verbatim from 204-RESEARCH.md §Q8 lines 411-417 + 204-PATTERNS.md lines 583-603 -->

```python
calib_04_pass = (
    soak_summary["primary_gate"]["verdict"] == "pass"
    and soak_summary["primary_gate"]["delta"] == 0
    and soak_summary["secondary_gate_completed_window"]["verdict"] == "pass"
    and soak_summary["secondary_gate_completed_window"]["value"] <= soak_summary["secondary_gate_completed_window"]["threshold"]
)
```

```bash
SOAK_DIR=.planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}
jq -e '
  .primary_gate.verdict == "pass"
  and .primary_gate.delta == 0
  and .secondary_gate_completed_window.verdict == "pass"
' $SOAK_DIR/soak-summary.json
```

<!-- The legacy secondary_gate_legacy block is informational only; NOT part of pass criterion. -->

<!-- FAIL-handling branches per 204-RESEARCH.md §Risk 6 lines 743-749 -->
- Branch A (just-over): secondary_gate_completed_window.value within ~10% of threshold → operator can re-approve CALIB-02 at higher number, re-run CALIB-04. No new soak needed beyond next CALIB-04 attempt.
- Branch B (materially-higher): secondary_gate_completed_window.value > 2× threshold OR primary_gate.delta != 0 → stop. Investigate. v1.43 milestone closure deferred to v1.44.
- Branch C (transient): primary_gate.reason matches `soak_primary_gate_uncollectible_negative_delta_*` (daemon restart mid-soak) → re-run CALIB-04 (transient infra issue, not a real regression).
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Operator launches CALIB-04 24h verification soak</name>
  <read_first>
    - 204-PATTERNS.md "Soak harness invocation" lines 609-640 (verbatim launch sequence)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md (24h soak protocol)
    - 204-VALIDATION.md "Manual-Only Verifications" row "24h verification soak dual gate (CALIB-04)"
    - scripts/calib_02_threshold.json (operator-approved constants are now live in the aggregator since Plan 204-04)
  </read_first>
  <files>(remote /var/tmp/wanctl-soak-${CALIB_04_TS}/soak-capture.ndjson on cake-shaper; .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/ on local)</files>
  <what-built>
    Plan 204-04 landed `aggregate_watchdog()` in `scripts/soak_summary_aggregate.py` and `scripts/calib_02_threshold.json` carries the operator-approved constants. Production cake-shaper is still on v1.43.0 (Plan 204-01); Phase 204 has NOT modified the production binary. Ready to launch the verification 24h soak under the recalibrated threshold.
  </what-built>
  <how-to-verify>
    1. Confirm cake-shaper /health.version == 1.43.0: `ssh cake-shaper 'curl -s http://127.0.0.1:9101/health | jq -r .version'`.
    2. Confirm the operator-approved constants are loaded: `cat scripts/calib_02_threshold.json` — the operator should re-read and reconfirm these are the values they signed in Plan 204-03.
    3. Operator picks `CALIB_04_TS = $(date -u +%Y%m%dT%H%M%SZ)`.
    4. Launch the soak per 204-PATTERNS.md lines 619-637:
       ```bash
       SOAK_TS=$(date -u +%Y%m%dT%H%M%SZ)
       mkdir -p .planning/phases/204-d-14-successor-recalibration-calib/soak/${SOAK_TS}
       scp scripts/soak-capture.sh cake-shaper:/tmp/soak-capture.sh
       ssh cake-shaper "chmod +x /tmp/soak-capture.sh"
       ssh cake-shaper "tmux new-session -d -s wanctl-soak \"HEALTH_URL=http://127.0.0.1:9101/health bash /tmp/soak-capture.sh ${SOAK_TS} 2>&amp;1 | tee /tmp/soak-capture.log\""
       ssh cake-shaper "tmux list-sessions | grep wanctl-soak"
       sleep 5
       ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson"
       ```
    5. Schedule T+24h finish: `ssh cake-shaper 'systemd-run --user --on-active=24h30m -- tmux kill-session -t wanctl-soak'`.
    6. Operator decides: approved (24h soak begins; Task 2 waits) or rejected (record reason; abort plan).
  </how-to-verify>
  <resume-signal>Type "approved: CALIB-04 soak started, ts=&lt;CALIB_04_TS&gt;" or "rejected: &lt;reason&gt;".</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved" with literal `CALIB_04_TS` value
    - Local soak directory exists
    - Remote tmux session `wanctl-soak` running on cake-shaper
    - Pre-soak baseline captured: `/health` floor-hit total recorded for D-19 delta computation
  </acceptance_criteria>
  <done>Verification soak running; 24h wall clock has begun.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Pull CALIB-04 capture, run aggregator, evaluate dual gate</name>
  <read_first>
    - 204-PATTERNS.md "Soak harness invocation" lines 609-640 (scp-back pattern)
    - 204-PATTERNS.md "204-05-CALIB-04-SOAK-VERDICT.md (soak verdict, Plan 204-05)" section lines 580-606
    - 204-RESEARCH.md §Q8 lines 411-417 (pass criterion code)
    - 204-RESEARCH.md §Risk 6 lines 743-749 (FAIL-handling branches)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-capture.ndjson, .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-summary.json</files>
  <what-built>
    The 24h CALIB-04 soak has completed on cake-shaper. Capture is at `/var/tmp/wanctl-soak-${CALIB_04_TS}/soak-capture.ndjson` on the remote.
  </what-built>
  <how-to-verify>
    1. Confirm soak completion:
       ```bash
       ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${CALIB_04_TS}/soak-capture.ndjson"   # MUST be >= 86,000
       ```
    2. Pull capture:
       ```bash
       scp cake-shaper:/var/tmp/wanctl-soak-${CALIB_04_TS}/soak-capture.ndjson \
           .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-capture.ndjson
       ```
    3. Run aggregator (will load scripts/calib_02_threshold.json automatically via load_calib_02_constants()):
       ```bash
       .venv/bin/python scripts/soak_summary_aggregate.py \
         .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-capture.ndjson \
         -o .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-summary.json
       ```
    4. Evaluate dual gate (verbatim from 204-PATTERNS.md lines 596-602):
       ```bash
       SOAK_DIR=.planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}
       jq -e '
         .primary_gate.verdict == "pass"
         and .primary_gate.delta == 0
         and .secondary_gate_completed_window.verdict == "pass"
       ' $SOAK_DIR/soak-summary.json
       echo "exit=$?  (0 = PASS, 1 = FAIL)"
       ```
       NOTE: this jq command requires Plan 204-05 evidence-augmentation to also produce a `primary_gate` block in soak-summary.json. The Plan 204-04 aggregator extension only added `secondary_gate_*` keys; the `primary_gate` (D-19) block must be computed here from the floor-hit counter delta. Use the same pattern as v1.42 Plan 201-16:
       ```bash
       PRE_FH=<value recorded in Task 1 pre-soak baseline>
       POST_FH=$(ssh cake-shaper "curl -s http://127.0.0.1:9101/health | jq -r '.wans[0].upload.hysteresis.floor_hit_cycles_total // 0'")
       DELTA=$((POST_FH - PRE_FH))
       jq --argjson delta $DELTA '. + {primary_gate: {name: "floor_hit_cycles_total_delta_soak_window", threshold: 0, t0: '$PRE_FH', t24: '$POST_FH', delta: $delta, verdict: (if $delta == 0 then "pass" else "fail" end), reason: null}}' $SOAK_DIR/soak-summary.json > $SOAK_DIR/soak-summary.json.tmp && mv $SOAK_DIR/soak-summary.json.tmp $SOAK_DIR/soak-summary.json
       ```
    5. Display results to operator:
       ```bash
       jq '.primary_gate, .secondary_gate_legacy, .secondary_gate_completed_window' $SOAK_DIR/soak-summary.json
       ```
    6. Operator reads:
       - primary_gate.verdict (must be "pass" and delta == 0)
       - secondary_gate_completed_window.verdict (must be "pass")
       - secondary_gate_legacy.value (informational; the legacy mean for cross-validation)
       - secondary_gate_completed_window.value vs .threshold (must be ≤)
    7. Operator decides:
       - approved-pass: both gates PASS → proceed to Task 3 PASS branch
       - approved-fail-A: just-over (within ~10% of threshold) → Task 3 FAIL branch A (re-approve threshold)
       - approved-fail-B: materially-higher (>2× threshold) OR primary fails → Task 3 FAIL branch B (investigate, defer milestone closure)
       - approved-fail-C: transient (primary_gate.reason matches uncollectible_negative_delta) → Task 3 FAIL branch C (re-run CALIB-04)
       - rejected: reason recorded; abort plan
  </how-to-verify>
  <resume-signal>Type one of:
    - "approved-pass: primary_delta=&lt;N&gt;, secondary_value=&lt;V&gt;, secondary_threshold=&lt;T&gt;"
    - "approved-fail-A: just-over, secondary_value=&lt;V&gt;, secondary_threshold=&lt;T&gt;"
    - "approved-fail-B: materially-higher OR primary-fail, &lt;details&gt;"
    - "approved-fail-C: transient, primary_gate.reason=&lt;...&gt;"
    - "rejected: &lt;reason&gt;"
  </resume-signal>
  <acceptance_criteria>
    - `wc -l .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-capture.ndjson` returns >= 86000
    - `jq -e '.secondary_gate_completed_window != null and .secondary_gate_legacy != null and .primary_gate != null' .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}/soak-summary.json` exits 0
    - Operator typed one of the five resume-signal options
    - The chosen branch is recorded in operator notes for Task 3
  </acceptance_criteria>
  <done>CALIB-04 soak captured, aggregated, dual gate evaluated, branch chosen.</done>
</task>

<task type="auto">
  <name>Task 3: Write 204-05-CALIB-04-SOAK-VERDICT.md</name>
  <read_first>
    - 204-PATTERNS.md "204-05-CALIB-04-SOAK-VERDICT.md" section lines 580-606
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md (structural analog)
    - 204-RESEARCH.md §Risk 6 lines 743-749 (FAIL-handling branches text)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md</files>
  <action>
    Substitute Task 2's resume-signal values into the appropriate branch template.

    PASS template (use when Task 2 resume-signal was `approved-pass`):

    ```markdown
    # Phase 204 — Plan 204-05 CALIB-04 Verification Soak Verdict

    timestamp: <UTC ISO from `date -u -Iseconds`>
    soak_ts: <CALIB_04_TS>
    verdict: pass
    primary_gate_delta: <N>
    secondary_gate_value: <V>
    secondary_gate_threshold: <T>

    ---

    ## CALIB-04 Outcome (PASS)

    The 24h verification soak under v1.43.0 binary on cake-shaper with the operator-approved D-14 successor threshold passed the dual gate cleanly:
    - `primary_gate.verdict == "pass"` (D-19 stays at 0 floor hits over the 24h window)
    - `secondary_gate_completed_window.verdict == "pass"` (D-14 successor `<V>` ≤ threshold `<T>`)
    - `secondary_gate_legacy.value == <legacy_value>` (informational, drops in v1.44)

    CALIB-04 is satisfied. Plan 204-06 may proceed to RETRO + closeout.

    ## Evidence

    - Capture: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-capture.ndjson` (line count: <N>)
    - Summary: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/soak-summary.json`
    - Operator approval (CALIB-02): `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`
    - Constants: `scripts/calib_02_threshold.json`

    ## References

    - Plan 201-16 SOAK-VERDICT precedent: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md`
    - 204-RESEARCH.md §Q8 (pass criterion)
    - REQUIREMENTS.md CALIB-04
    ```

    FAIL templates (use the appropriate branch from Task 2 resume signal):

    Branch A (just-over):
    ```markdown
    # Phase 204 — Plan 204-05 CALIB-04 Verification Soak Verdict

    timestamp: <UTC ISO>
    soak_ts: <CALIB_04_TS>
    verdict: fail
    fail_branch: A
    fail_branch_label: "just-over (within ~10% of threshold)"
    secondary_gate_value: <V>
    secondary_gate_threshold: <T>
    next_action: "operator re-approves CALIB-02 at higher threshold; re-run CALIB-04 (Plan 204-05 re-execution)"
    [...evidence + references...]
    ```

    Branch B (materially-higher):
    ```markdown
    fail_branch: B
    fail_branch_label: "materially-higher OR primary fail (>2× threshold OR primary_gate.delta != 0)"
    next_action: "STOP. Investigate root cause. v1.43 milestone closure deferred to v1.44 with new RETRO entry."
    ```

    Branch C (transient):
    ```markdown
    fail_branch: C
    fail_branch_label: "transient (daemon restart mid-soak)"
    primary_gate_reason: "<from soak-summary.json>"
    next_action: "re-run CALIB-04 (Plan 204-05 re-execution); transient infra issue, not a real regression."
    ```

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>test -f .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md &amp;&amp; grep -qE "^verdict: (pass|fail)$" .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md &amp;&amp; bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - 204-05-CALIB-04-SOAK-VERDICT.md exists with `verdict: pass` OR `verdict: fail`
    - On PASS: file references soak-summary.json by path AND cites primary_gate_delta, secondary_gate_value, secondary_gate_threshold verbatim from Task 2 resume signal
    - On FAIL: file records `fail_branch: A|B|C` and `next_action` per the appropriate branch
    - `bash scripts/check-safe07-source-diff.sh` exits 0
    - Hot-path slice green
  </acceptance_criteria>
  <done>Verdict committed. On PASS: Plan 204-06 unblocked. On FAIL: explicit branch + operator next-action recorded.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 24h soak on cake-shaper | Same trust boundary as Plan 204-02; production-grade deploy environment. |
| Soak capture → aggregator → verdict | Pipeline correctness verified in Plan 204-04 (oracle regression); this plan consumes that trust. |
| Operator dual-gate decision → verdict file | The verdict IS the closure artifact; capture-in-distinct-file pattern (Codex 201-REVIEWS LOW-CODEX-5). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-05-01 | Tampering | soak-summary.json gate fields | mitigate | aggregate_watchdog() oracle-tested in Plan 204-04; primary_gate computation cited from v1.42 Plan 201-16 protocol; both are reviewable. |
| T-204-05-02 | Repudiation | CALIB-04 verdict | mitigate | Verdict captured in distinct timestamped file with verbatim numerics from soak-summary.json. |
| T-204-05-03 | Denial of Service | 24h soak window | accept | Same risk profile as Plan 204-02. |
| T-204-05-04 | Information Disclosure | soak NDJSON | accept | Operational metrics; no PII; existing committed precedent in v1.42-phases. |
</threat_model>

<verification>
- 24h CALIB-04 soak capture present (line count >= 86,000)
- soak-summary.json contains all three gates (primary_gate, secondary_gate_legacy, secondary_gate_completed_window)
- 204-05-CALIB-04-SOAK-VERDICT.md committed with verdict and branch
- SAFE-07 source-diff clean
- Hot-path slice green
</verification>

<success_criteria>
On PASS: CALIB-04 closed; D-14 successor watchdog verified; metric-watchdog regression closed without controller change. Plan 204-06 unblocked.
On FAIL: explicit branch (A/B/C) recorded; operator next-action documented; milestone closure path defined.
Zero `src/wanctl/` source diff regardless of outcome.
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-05-SUMMARY.md` recording:
- CALIB_04_TS literal value
- NDJSON line count
- All three gate blocks cited verbatim from soak-summary.json
- Verdict + branch (if FAIL)
- Next action — Plan 204-06 (closeout) on PASS, or branch-specific next action on FAIL
</output>

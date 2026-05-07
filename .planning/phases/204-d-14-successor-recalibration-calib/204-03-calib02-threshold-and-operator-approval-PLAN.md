---
id: 204-03
phase: 204
plan: 03
type: execute
wave: 3
depends_on:
  - 204-02
files_modified:
  - .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
  - scripts/calib_02_threshold.json
autonomous: false
production_canary: false
created: 2026-05-06
requirements:
  - CALIB-02
notes:
  - "Open Q4 (external JSON file vs in-aggregator constants): adopting researcher recommendation — `scripts/calib_02_threshold.json` external file. decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §Q4 lines 213-220 + §Code Examples lines 763-777; 204-PATTERNS.md lines 215-249)."
  - "OPEN QUESTION 1 (exact CALIB-02 threshold value): EXPLICITLY DEFERRED to Task 1 operator decision in this plan. The threshold cannot be locked at planning time — it depends on CALIB-01's distribution which is now in hand from Plan 204-02. Researcher's default if operator has no preference: `p99 × 1.5, rounded up to nearest 25` (204-RESEARCH.md §Q1 lines 117-123)."
  - "OPEN QUESTION 2 (gate against `dwell_hold` slice vs total): EXPLICITLY DEFERRED to Task 1 operator decision in this plan. Researcher recommendation: gate against `dwell_hold` slice (preserves D-14 spirit; surfaces total + backlog as informational); decision must be made with CALIB-01 by_cause distribution in hand (204-RESEARCH.md §Risk 2 lines 709-722)."
must_haves:
  truths:
    - "204-CALIB-02-OPERATOR-APPROVAL.md exists with `decision: approved` (or `decision: rejected` with abort branch)."
    - "204-CALIB-02-OPERATOR-APPROVAL.md front-matter has FIVE machine-readable fields: timestamp, decision, statistic, threshold, headroom_factor — per 204-PATTERNS.md lines 422-466 grep contract."
    - "204-CALIB-02-OPERATOR-APPROVAL.md operator_justification references CALIB-01 distribution by file path AND cites at least one numeric value from soak-summary.json (mean / p99 / window_count from either top-level or by_cause)."
    - "204-CALIB-02-OPERATOR-APPROVAL.md explicitly records the open-Q2 slice-vs-total decision (which column the threshold gates against)."
    - "scripts/calib_02_threshold.json parses as valid JSON and contains keys: statistic, threshold, headroom_factor, rounding_policy, approval_artifact, calib_01_distribution_reference, gate_column."
    - "scripts/calib_02_threshold.json::statistic, threshold, headroom_factor MUST equal the front-matter values in 204-CALIB-02-OPERATOR-APPROVAL.md (single source of truth)."
    - "scripts/calib_02_threshold.json::approval_artifact path equals .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md."
    - "git diff b72b463..HEAD -- src/wanctl/ produces 0 lines (SAFE-07 invariant — this plan touches NO src/wanctl/ files)."
  artifacts:
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
      provides: "Operator-signed pre-Deploy-2 approval artifact recording statistic + threshold + headroom + slice-vs-total decision + justification."
      contains: "decision: approved"
    - path: scripts/calib_02_threshold.json
      provides: "Machine-readable mirror of the operator-approval triple (statistic, threshold, headroom_factor) plus the open-Q2 gate_column choice. Consumed by aggregate_watchdog() in Plan 204-04."
      contains: "\"approval_artifact\""
  key_links:
    - from: ".planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json"
      to: "204-CALIB-02-OPERATOR-APPROVAL.md operator_justification"
      via: "operator reads distribution → derives threshold → records justification with file reference"
      pattern: "soak-summary.json"
    - from: "204-CALIB-02-OPERATOR-APPROVAL.md front-matter"
      to: "scripts/calib_02_threshold.json keys"
      via: "single source of truth — JSON file MUST mirror the artifact's machine-readable triple"
      pattern: "statistic.*threshold.*headroom_factor"
    - from: "scripts/calib_02_threshold.json"
      to: "Plan 204-04 aggregate_watchdog() default constants"
      via: "load_calib_02_constants() reads this file at aggregator init"
      pattern: "calib_02_threshold.json"
---

<objective>
Operator-judgment session. Read CALIB-01's distribution from Plan 204-02, lock the D-14 successor threshold, decide the open-Q2 slice-vs-total question, write the byte-for-byte mirror of the Plan 201-16 D-19 operator-approval artifact, and emit `scripts/calib_02_threshold.json` as the machine-readable mirror. No code beyond the JSON file; no production deploy.

Purpose: Per the Codex 201-REVIEWS LOW-CODEX-5 lesson (cited in 204-PATTERNS.md analog 201-16-OPERATOR-APPROVAL-D19.md), the operator MUST explicitly approve the gate threshold BEFORE Plan 204-04 encodes it into the soak harness — never silently written into a verdict file post hoc. This plan is the approval-capture step.

Output: Two committed files — the operator-readable approval artifact and the machine-readable JSON file — with a single source of truth (the artifact) and a derived consumer-facing format (the JSON). Zero `src/wanctl/` source diff (SAFE-07).
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
@.planning/phases/204-d-14-successor-recalibration-calib/204-02-SUMMARY.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md

<interfaces>
<!-- Verbatim precedent for the operator-approval artifact (21 lines, full file) — Plan 204-03 Task 1 mirrors this byte-for-byte with three additional front-matter fields per 204-PATTERNS.md lines 422-455. -->

From .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md:
```markdown
# Phase 201 — D-19 Operator Approval (Stricter Primary Soak Gate)

timestamp: 2026-05-05T13:15:37+00:00
decision: approved
operator_justification: |
  canary PASS

---

## D-19 Statement (Approved)

**D-19 (Phase 201 closure gate tightening):** [...verbatim Phase 201 approval text...]

---

## References

- Plan 201-15 rev 3 canary PASS: [...]
- Captures operator approval BEFORE soak begins; gates Task 2.
```

The Plan 204-03 mirror adds three machine-readable front-matter fields (`statistic`, `threshold`, `headroom_factor`) and one slice-decision field (`gate_column`) per 204-PATTERNS.md lines 425-433.

JSON schema for scripts/calib_02_threshold.json (204-PATTERNS.md lines 238-247):
```json
{
  "statistic": "p99",
  "threshold": 75,
  "headroom_factor": 1.5,
  "rounding_policy": "ceil_to_nearest_25",
  "approval_artifact": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md",
  "calib_01_distribution_reference": ".planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json",
  "gate_column": "by_cause.dwell_hold"
}
```
</interfaces>
</context>

<tasks>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 1: Operator session — pick statistic, threshold, headroom, slice</name>
  <read_first>
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json (the operator's data — Plan 204-02 output)
    - 204-RESEARCH.md §Q1 lines 95-129 (statistic candidates and tradeoffs table)
    - 204-RESEARCH.md §Q2 lines 132-143 (headroom multiplier tradeoffs table)
    - 204-RESEARCH.md §Risk 2 lines 709-722 (open-Q2 slice-vs-total decision; researcher recommends `dwell_hold` slice)
    - 204-PATTERNS.md lines 422-466 (front-matter machine-readable contract)
  </read_first>
  <files>(operator interaction; no file writes from Claude in this task — Task 2 writes the artifacts based on Task 1's recorded decisions)</files>
  <decision>
    Lock the D-14 successor gate parameters with CALIB-01 distribution data in hand. Four sub-decisions:
    1. **Statistic**: which percentile or aggregate to gate against
    2. **Headroom factor**: safety multiplier
    3. **Threshold**: the resulting integer (statistic × headroom, with rounding policy)
    4. **Gate column** (open-Q2): whether the gate compares against the top-level `suppressions_completed_window_count_distribution` total, OR a slice (`by_cause.dwell_hold`, `by_cause.backlog_recovery`, or `by_cause.other`)
  </decision>
  <context>
    The Plan 204-02 soak-summary.json now has the CALIB-01 distribution for production cake-shaper under v1.43.0. Read it:
    ```bash
    jq '.suppressions_completed_window_count_distribution' \
       .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json
    ```
    The choice depends on what the distribution actually shows. If `by_cause.backlog_recovery.mean >> by_cause.dwell_hold.mean`, the slice-vs-total decision is load-bearing — the v1.42 reference D-14 gated on the dwell-hold path (queue_controller.py:348), so gating on the total may admit a regression that the metric was never designed to catch (research §Risk 2).
  </context>
  <options>
    <option id="default-researcher-recommendation">
      <name>Researcher default: p99 × 1.5 rounded up to nearest 25, gated against by_cause.dwell_hold</name>
      <pros>Tail-aware (catches right-tail growth — the regression shape D-14 is meant to detect); 1.5× headroom absorbs benign drift; rounding to 25 avoids false precision; dwell_hold slice preserves the metric-semantic intent of the original D-14 (queue_controller.py:348 YELLOW-edge dwell-hold path).</pros>
      <cons>Operator must trust that the post-fix v1.43 production behavior is well-represented by the single 24h CALIB-01 sample; if production drifts seasonally, the gate may flap in v1.44 soaks.</cons>
    </option>
    <option id="conservative-against-total">
      <name>Conservative: p99 × 2.0 rounded up to nearest 25, gated against top-level total</name>
      <pros>Total-axis catches both dwell-hold AND backlog-recovery regressions; 2.0× absorbs more environmental drift across Spectrum link conditions; first soak-grounded threshold deserves wider safety margin.</pros>
      <cons>Loses metric-semantic alignment with the original D-14 framing; allows the per-cause story to drift unobserved.</cons>
    </option>
    <option id="tight-dwell-only">
      <name>Tight: p99 × 1.2 rounded up to nearest 5, gated against by_cause.dwell_hold</name>
      <pros>Very fast regression detection; matches the original D-14's role as a watchdog rather than a soft alarm.</pros>
      <cons>Higher false-FAIL rate on slightly-noisier soaks; risk of CALIB-04 PASS/FAIL flipflop forcing a re-approval cycle.</cons>
    </option>
    <option id="custom">
      <name>Operator-custom values</name>
      <pros>Operator may have a specific number in mind based on production knowledge not captured in the distribution alone.</pros>
      <cons>Departs from researcher recommendation — operator must justify in writing.</cons>
    </option>
  </options>
  <resume-signal>Type a single line: `approved: statistic=&lt;p99|p95|max|mean+ksigma&gt;, threshold=&lt;integer&gt;, headroom_factor=&lt;float&gt;, gate_column=&lt;suppressions_completed_window_count_distribution|by_cause.dwell_hold|by_cause.backlog_recovery|by_cause.other&gt;, rounding_policy=&lt;ceil_to_nearest_25|ceil_to_nearest_5|none&gt;, justification=&lt;free text referencing CALIB-01 distribution&gt;` — OR `rejected: &lt;reason&gt;`.</resume-signal>
  <acceptance_criteria>
    - Operator types `approved:` with all six fields supplied (statistic, threshold, headroom_factor, gate_column, rounding_policy, justification)
    - The four numeric/string values become Task 2's substitution inputs
    - If `rejected:` — record reason; abort plan; escalate to roadmap (e.g. CALIB-01 distribution looked anomalous and operator wants to re-run CALIB-01)
  </acceptance_criteria>
  <done>Operator decision captured in resume signal; Task 2 has all inputs needed to write both artifacts.</done>
</task>

<task type="auto">
  <name>Task 2: Write 204-CALIB-02-OPERATOR-APPROVAL.md and scripts/calib_02_threshold.json</name>
  <read_first>
    - 204-PATTERNS.md "Phase 204 mirror template" lines 422-455 (artifact template)
    - 204-PATTERNS.md "Front-matter machine-readable contract" lines 459-466 (grep-verifiable acceptance criteria)
    - 204-PATTERNS.md lines 238-247 (JSON schema for scripts/calib_02_threshold.json)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md (precedent — byte-for-byte structural mirror)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md, scripts/calib_02_threshold.json</files>
  <action>
    Substitute Task 1's six values into the template below. Use the exact `CALIB_01_TS` value from Plan 204-02 (read it from `.planning/phases/204-d-14-successor-recalibration-calib/204-02-SUMMARY.md`). Use `date -u -Iseconds` for the timestamp.

    Step 1: Write `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md` (mirror of 201-16-OPERATOR-APPROVAL-D19.md byte-for-byte structure with three additional front-matter fields per 204-PATTERNS.md lines 425-433):

    ```markdown
    # Phase 204 — CALIB-02 Operator Approval (D-14 Successor Threshold)

    timestamp: <UTC ISO from `date -u -Iseconds`>
    decision: approved
    statistic: <p99 | p95 | max | mean+ksigma>
    threshold: <integer>
    headroom_factor: <float>
    gate_column: <suppressions_completed_window_count_distribution | by_cause.dwell_hold | by_cause.backlog_recovery | by_cause.other>
    rounding_policy: <ceil_to_nearest_25 | ceil_to_nearest_5 | none>
    operator_justification: |
      <verbatim free text from Task 1 resume signal, including reference to CALIB-01 distribution numerics and the slice-vs-total rationale>

    ---

    ## CALIB-02 Statement (Approved)

    **CALIB-02 (D-14 successor threshold, soak-grounded):** Phase 204 closure replaces the inherited Phase 201 D-14 `<5/60s` live-counter-snapshot mean threshold with a soak-calibrated successor based on the post-Plan-201-14 production control surface. The threshold is `<statistic>` of the per-completed-window suppression-count distribution observed in the CALIB-01 24h baseline soak (gated against `<gate_column>`), multiplied by a `<headroom_factor>` safety margin and rounded per `<rounding_policy>`, giving a final gate value of `<threshold>`. The legacy `<5/60s` framing is acknowledged as metric-semantically ambiguous (Phase 201 RETRO Lesson #1) and is emitted alongside the new statistic for one transition cycle (CALIB-03), then dropped in a v1.44 follow-up. This approval references the CALIB-01 distribution by file path; the statistic + headroom + threshold + gate-column slice are operator decisions captured here as a distinct pre-deploy artifact, NOT silently written into a verdict file. Operator-approved <YYYY-MM-DD>.

    ---

    ## CALIB-01 Distribution Reference

    - Soak run: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/`
    - soak-summary.json fields cited:
      - `suppressions_completed_window_count_distribution.mean = <verbatim from soak-summary.json>`
      - `..._distribution.p50 = <verbatim>`
      - `..._distribution.p95 = <verbatim>`
      - `..._distribution.p99 = <verbatim>`  ← if statistic = p99
      - `..._distribution.max = <verbatim>`
      - `..._distribution.window_count = <verbatim>`
      - `by_cause.dwell_hold.{mean, p99, max, window_count}` — verbatim
      - `by_cause.backlog_recovery.{mean, p99, max, window_count}` — verbatim
      - `by_cause.other.{mean, p99, max, window_count}` — verbatim

    ## Open Question 2 — Slice vs Total decision (recorded)

    The CALIB-01 distribution shows by_cause.backlog_recovery.mean = <X> vs by_cause.dwell_hold.mean = <Y>. Operator decision: gate against `<gate_column>` because <one-sentence rationale>.

    ## References

    - Phase 201 RETRO Lesson #1 (metric-semantics framing): `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md`
    - Phase 201 RETRO Lesson #2 (threshold-basis hygiene): same.
    - 201-16-OPERATOR-APPROVAL-D19.md (precedent format)
    - CALIB-01 baseline soak summary: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json`
    - Captures operator approval BEFORE Deploy 2 (Plan 204-04) + CALIB-04 verification soak (Plan 204-05) begins; gates the verification plan.
    ```

    Step 2: Write `scripts/calib_02_threshold.json` mirroring 204-PATTERNS.md lines 238-247 with the additional `gate_column` key:

    ```json
    {
      "statistic": "<from Task 1>",
      "threshold": <integer from Task 1>,
      "headroom_factor": <float from Task 1>,
      "rounding_policy": "<from Task 1>",
      "approval_artifact": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md",
      "calib_01_distribution_reference": ".planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json",
      "gate_column": "<from Task 1>"
    }
    ```

    Both files must contain THE SAME values for statistic, threshold, headroom_factor, gate_column. The artifact is the source of truth; the JSON is the derived machine-readable form.

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>test -f .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; grep -q "^decision: approved$" .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; grep -qE "^statistic: (p99|p95|max|mean\+ksigma)$" .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; grep -qE "^threshold: [0-9]+$" .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; grep -qE "^headroom_factor: [0-9]+\.?[0-9]*$" .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; grep -q "^gate_column:" .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md &amp;&amp; jq -e '.statistic and .threshold and .headroom_factor and .approval_artifact and .gate_column' scripts/calib_02_threshold.json &amp;&amp; bash scripts/check-safe07-source-diff.sh</automated>
  </verify>
  <acceptance_criteria>
    - `204-CALIB-02-OPERATOR-APPROVAL.md` exists with all five required front-matter fields (timestamp, decision, statistic, threshold, headroom_factor) AND the slice-decision field gate_column
    - All five grep checks from 204-PATTERNS.md lines 462-465 pass (decision, statistic, threshold, headroom_factor — plus our gate_column extension)
    - `scripts/calib_02_threshold.json` parses as JSON and contains all seven keys (statistic, threshold, headroom_factor, rounding_policy, approval_artifact, calib_01_distribution_reference, gate_column)
    - JSON values for statistic, threshold, headroom_factor, gate_column EQUAL the artifact's front-matter values (single source of truth verified by manual inspection or simple cross-check command)
    - `bash scripts/check-safe07-source-diff.sh` exits 0
    - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
  </acceptance_criteria>
  <done>Operator-signed approval artifact and machine-readable JSON committed; Plan 204-04 has the constants it needs to encode into aggregate_watchdog().</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator decision → committed artifact | The approval IS the trust anchor; Codex 201-REVIEWS LOW-CODEX-5 lesson — capture in a discrete file, not silently in a verdict. |
| 204-CALIB-02-OPERATOR-APPROVAL.md → scripts/calib_02_threshold.json | Single source of truth (artifact); derived consumer-facing format (JSON); divergence is a real risk. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-03-01 | Repudiation | Operator approval capture | mitigate | Approval recorded in a distinct, timestamped, committed file (not silently written into a downstream verdict). Mirror of Plan 201-16 D-19 LOW-CODEX-5 mitigation. |
| T-204-03-02 | Tampering | scripts/calib_02_threshold.json drift from artifact | mitigate | Both files written in the same task; manual cross-check + future Plan 204-04 acceptance criterion (artifact-vs-JSON consistency) catches drift. |
| T-204-03-03 | Information Disclosure | Operator justification text | accept | Public-safe content; no secrets, no PII; CALIB-01 distribution numerics are routine operational metrics. |
</threat_model>

<verification>
- 204-CALIB-02-OPERATOR-APPROVAL.md grep checks all pass
- scripts/calib_02_threshold.json valid JSON with required keys
- Both files agree on statistic/threshold/headroom_factor/gate_column
- SAFE-07 source-diff clean
- Hot-path slice green
</verification>

<success_criteria>
Operator has signed off on the D-14 successor threshold with explicit rationale referencing CALIB-01 distribution. The slice-vs-total open question is decided and recorded. Plan 204-04 can read scripts/calib_02_threshold.json to wire the constants into aggregate_watchdog(). Zero `src/wanctl/` source diff.
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-03-SUMMARY.md` recording:
- The four locked values (statistic, threshold, headroom_factor, gate_column)
- The CALIB_01_TS reference
- Cross-check: artifact and JSON agree
- Hand-off pointer to Plan 204-04 (CALIB-03 watchdog harness update + Deploy 2)
</output>

---
id: 204-06
phase: 204
plan: 06
type: execute
wave: 6
depends_on:
  - 204-05
files_modified:
  - .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md
  - .planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md
  - .planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/STATE.md
  - CHANGELOG.md
  - .planning/todos/pending/2026-XX-XX-v1.44-drop-secondary-gate-legacy-and-promote-calib02-to-yaml.md
autonomous: false
production_canary: false
created: 2026-05-06
requirements:
  - CALIB-05
  - SAFE-07
notes:
  - "Open Q6 (one transition cycle = one milestone): adopted in Plan 204-04. This plan operationalizes it by creating the v1.44 follow-up TODO that drops secondary_gate_legacy. decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §Q5 lines 224-237)."
  - "All four researcher-default open questions now landed across the plan set (Q3 1.43.0, Q4 external JSON, Q5 degenerate-explained, Q6 one-milestone-then-drop)."
must_haves:
  truths:
    - "204-RETRO.md exists with section structure mirroring 201-RETRO.md (What Was Built / Tested / Worked / Inefficient / Patterns Established / Key Lessons / Cross-Reference / Lessons for v1.44 / Open Questions)."
    - "204-RETRO.md Key Lessons section contains the literal phrase 'threshold-basis hygiene' (CALIB-05 acceptance criterion per 204-PATTERNS.md line 503)."
    - "204-RETRO.md Lessons for v1.44 section explicitly names: (a) drop secondary_gate_legacy, (b) consider promoting CALIB-02 threshold to YAML if CALIB-04 PASS proved the harness-constant approach."
    - "scripts/check-safe07-source-diff.sh exits 0 against ref b72b463 (SAFE-07 mechanical diff invariant)."
    - "tests/test_phase_195_replay.py -k safe05_threshold_name_counts passes (SAFE-05 three-dict pin block byte-identical at v1.43 close)."
    - "Hot-path slice passes (regression invariant)."
    - "Phase-scoped slice passes: tests/test_phase_204_distribution.py + tests/test_phase_204_watchdog.py + tests/test_phase_204_replay.py + Phase 203 + Phase 202 + Phase 195 replay tests all green."
    - "Full suite passes (.venv/bin/pytest tests/ -q)."
    - "REQUIREMENTS.md CALIB-01..05 + SAFE-07 row updated to satisfied (the existing `[ ]` flips to `[x]`)."
    - "ROADMAP.md Phase 204 row marked Complete; v1.43 milestone status flipped to ✅ shipped."
    - "STATE.md updated with Phase 204 completion + final progress numbers."
    - "CHANGELOG.md v1.43-dev heading flipped to `## v1.43.0 — <YYYY-MM-DD>` per 204-PATTERNS.md line 651."
    - "204-VERIFICATION.md exists, structurally mirrors 203-VERIFICATION.md, declares phase satisfied."
    - "204-VALIDATION.md updated with `nyquist_compliant: true` (matching Phase 202 + 203 carve-outs for operator-judgment manual-only items)."
    - "v1.44 follow-up TODO file created in .planning/todos/pending/ pointing at: drop secondary_gate_legacy from aggregate_watchdog() AND consider promoting CALIB-02 threshold to YAML."
  artifacts:
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md
      provides: "Phase 204 retrospective; CALIB-05 lesson-of-record."
      contains: "threshold-basis hygiene"
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md
      provides: "Phase 204 verification — all six requirements satisfied, SAFE-07 invariant clean."
      contains: "satisfied"
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
      provides: "Phase 204 validation contract; nyquist_compliant: true at close."
      contains: "nyquist_compliant: true"
    - path: .planning/REQUIREMENTS.md
      provides: "CALIB-01..05 + SAFE-07 flipped to satisfied."
    - path: .planning/ROADMAP.md
      provides: "Phase 204 + v1.43 milestone marked complete."
    - path: CHANGELOG.md
      provides: "v1.43.0 release heading + dated."
      contains: "v1.43.0"
    - path: .planning/todos/pending/2026-XX-XX-v1.44-drop-secondary-gate-legacy-and-promote-calib02-to-yaml.md
      provides: "v1.44 follow-up captured; legacy drop and YAML promotion deferred per researcher recommendation."
      contains: "secondary_gate_legacy"
  key_links:
    - from: "204-RETRO.md Key Lesson #1"
      to: "Phase 201 RETRO Lesson #2"
      via: "verbatim mirror per 204-PATTERNS.md lines 496-498"
      pattern: "threshold-basis hygiene"
    - from: "scripts/check-safe07-source-diff.sh"
      to: "v1.43 close commit (this plan close)"
      via: "exit 0 confirms zero src/wanctl/ diff between Phase 201 close (b72b463) and v1.43 close"
      pattern: "check-safe07-source-diff.sh"
    - from: "tests/test_phase_195_replay.py SAFE-05 pin block"
      to: "byte-identical state at v1.43 close"
      via: "no phase204_expected_counts dict added (verified — Phase 204 introduces zero new src/wanctl/ symbols)"
      pattern: "phase202_expected_counts"
---

<objective>
Close Phase 204 and milestone v1.43. Write 204-RETRO.md capturing CALIB-05's threshold-basis hygiene lesson. Run the four-command SAFE-07 verification checklist. Update REQUIREMENTS.md, ROADMAP.md, STATE.md, CHANGELOG.md. Write 204-VERIFICATION.md and update 204-VALIDATION.md to `nyquist_compliant: true`. Create the v1.44 follow-up TODO entry capturing the deferred legacy-drop and YAML-promotion work.

Purpose: This is the milestone closeout. CALIB-05 is satisfied by the RETRO lesson. SAFE-07 is verified mechanically. The v1.43 milestone ships clean: metric watchdog repaired, target-edge churn instrumented, gate recalibrated against post-Plan-201-14 production behavior — all without any controller-path change.

Output: Eight committed artifact files (or updates), all CALIB-* + SAFE-07 requirements satisfied, milestone v1.43 marked complete in ROADMAP. Zero `src/wanctl/` source diff between Phase 201 close (`b72b463`) and v1.43 close.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-05-SUMMARY.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VERIFICATION.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VALIDATION.md
@scripts/check-safe07-source-diff.sh
@tests/test_phase_195_replay.py
@CHANGELOG.md

<interfaces>
<!-- 204-RETRO.md section structure (verbatim from 204-PATTERNS.md lines 484-505 + 201-RETRO.md mirror) -->

1. ## What Was Built
2. ## What Was Tested in Production (per Hypothesis / Result / Evidence)
3. ## What Worked
4. ## What Was Inefficient / Harder Than Expected
5. ## Patterns Established (carry into future phases)
6. ## Key Lessons (CALIB-05 lives here as Lesson #1)
7. ## Cross-Reference (REQUIREMENTS, CONTEXT/CALIB artifacts)
8. ## Lessons for v1.44 (legacy-drop + YAML-promotion follow-ups)
9. ## Open Questions / Nothing-Claimed-But-Not-Shipped

<!-- CALIB-05 lesson text — verbatim mirror of Phase 201 RETRO Lesson #2 (204-PATTERNS.md line 498) -->

> Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially. D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default.

<!-- SAFE-07 closeout four-command checklist (204-RESEARCH.md §Q10 lines 484-497) -->

```bash
# 1. SAFE-07 source diff (must exit 0)
bash scripts/check-safe07-source-diff.sh

# 2. SAFE-05 pin block (must pass; dicts byte-identical)
.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"

# 3. Hot-path slice (regression)
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q

# 4. Phase-scoped slice (Phase 204 + Phase 203 + Phase 202 + Phase 195 replay tests)
.venv/bin/pytest tests/test_phase_204_replay.py tests/test_phase_204_watchdog.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run SAFE-07 closeout checklist + write 204-VERIFICATION.md and update 204-VALIDATION.md</name>
  <read_first>
    - 204-RESEARCH.md §Q10 lines 459-499 (SAFE-07 four-command checklist)
    - 204-PATTERNS.md "Phase 204 introduces zero new src/wanctl/ symbols" lines 32-37
    - .planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VERIFICATION.md (structural analog)
    - .planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VALIDATION.md (analog for nyquist_compliant: true update)
    - .planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md (current draft state)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md, .planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md</files>
  <action>
    Step 1: Run all four commands from the SAFE-07 closeout checklist (verbatim from interfaces block above). Capture stdout for the verification document. ALL FOUR must exit 0; any failure is a blocker.

    Step 2: Run the full suite as well: `.venv/bin/pytest tests/ -q`. Record pass count.

    Step 3: Write `.planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md` mirroring 203-VERIFICATION.md structure:

    ```markdown
    # Phase 204 — D-14 Successor Recalibration (CALIB) Verification

    timestamp: <UTC ISO>
    status: satisfied
    requirements:
      CALIB-01: satisfied (Plan 204-02 — 24h CALIB-01 baseline soak captured at <CALIB_01_TS>)
      CALIB-02: satisfied (Plan 204-03 — 204-CALIB-02-OPERATOR-APPROVAL.md + scripts/calib_02_threshold.json)
      CALIB-03: satisfied (Plan 204-04 — aggregate_watchdog() with dual-emission; v1.42 oracle regression PASS)
      CALIB-04: satisfied (Plan 204-05 — verification soak at <CALIB_04_TS> dual gate PASS)
      CALIB-05: satisfied (Plan 204-06 — RETRO Key Lesson #1 "threshold-basis hygiene")
      SAFE-07: satisfied (zero src/wanctl/ diff vs b72b463; SAFE-05 three-dict pin block byte-identical)

    ---

    ## SAFE-07 Closeout Checklist

    | # | Command | Exit Code | Notes |
    |---|---------|-----------|-------|
    | 1 | `bash scripts/check-safe07-source-diff.sh` | 0 | "SAFE-07 OK: no src/wanctl/ diff vs b72b463" |
    | 2 | `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` | 0 | 1 passed; three-dict pin block byte-identical (no `phase204_expected_counts` dict added) |
    | 3 | Hot-path slice | 0 | <NNN> tests passed |
    | 4 | Phase-scoped slice | 0 | <NNN> tests passed |
    | full | `.venv/bin/pytest tests/ -q` | 0 | <NNNN> tests passed |

    ## Must-Haves Audit

    From the phase goal "A clean 24h Spectrum baseline soak under post-Plan-201-14 production yields a soak-calibrated D-14 successor threshold with explicit operator rationale, and a verification 24h soak passes the dual gate cleanly — closing the metric watchdog without any control-path change."

    | Truth | Status | Evidence |
    |-------|--------|----------|
    | 24h CALIB-01 baseline soak completed under post-Plan-201-14 production | ✓ | `.planning/phases/204-.../soak/<CALIB_01_TS>/` |
    | Operator-approved threshold artifact exists with rationale tying to CALIB-01 distribution | ✓ | `204-CALIB-02-OPERATOR-APPROVAL.md` + `scripts/calib_02_threshold.json` |
    | Soak harness watchdog uses new completed-window statistic + emits legacy alongside | ✓ | `aggregate_watchdog()` in `scripts/soak_summary_aggregate.py` |
    | 24h CALIB-04 verification soak passes dual gate | ✓ | `204-05-CALIB-04-SOAK-VERDICT.md` verdict: pass |
    | SAFE-05 control-path pins byte-identical at v1.43 close + zero src/wanctl/ diff | ✓ | Checklist row 1 + 2 above |
    | RETRO captures threshold-basis hygiene lesson | ✓ | `204-RETRO.md` Key Lesson #1 |

    ## Cross-Reference

    - Plans: 204-01 (Deploy 1), 204-02 (CALIB-01), 204-03 (CALIB-02 approval), 204-04 (CALIB-03 + Deploy 2), 204-05 (CALIB-04), 204-06 (RETRO + closeout — this plan)
    - REQUIREMENTS.md CALIB-01..05 + SAFE-07
    - ROADMAP.md Phase 204
    ```

    Step 4: Update `.planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md` — flip `nyquist_compliant: false` → `nyquist_compliant: true` in the front-matter; populate the per-task verification map; check the Validation Sign-Off boxes.

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts" &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q &amp;&amp; .venv/bin/pytest tests/test_phase_204_replay.py tests/test_phase_204_watchdog.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q &amp;&amp; .venv/bin/pytest tests/ -q &amp;&amp; test -f .planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md &amp;&amp; grep -q "^status: satisfied$" .planning/phases/204-d-14-successor-recalibration-calib/204-VERIFICATION.md &amp;&amp; grep -q "nyquist_compliant: true" .planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md</automated>
  </verify>
  <acceptance_criteria>
    - All four SAFE-07 checklist commands exit 0
    - Full suite exits 0
    - 204-VERIFICATION.md exists with `status: satisfied` and the must-haves audit table all `✓`
    - 204-VALIDATION.md `nyquist_compliant: true`
    - `git diff b72b463..HEAD -- src/wanctl/` produces 0 lines
  </acceptance_criteria>
  <done>SAFE-07 mechanically verified clean. Phase 204 verification artifact committed.</done>
</task>

<task type="auto">
  <name>Task 2: Write 204-RETRO.md (CALIB-05 lesson) + create v1.44 follow-up TODO</name>
  <read_first>
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md (full file — section structure to mirror; Lesson #2 verbatim text to clone)
    - 204-PATTERNS.md lines 470-505 (RETRO structural mirror + verbatim CALIB-05 lesson)
    - 204-RESEARCH.md §Q5 line 237 (one milestone = v1.43 emits both, v1.44 drops legacy)
    - .planning/todos/pending/ (existing TODO file naming convention — `YYYY-MM-DD-<short-slug>.md`)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md, .planning/todos/pending/2026-XX-XX-v1.44-drop-secondary-gate-legacy-and-promote-calib02-to-yaml.md</files>
  <action>
    Step 1: Write `.planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md` with the nine-section structure from 204-PATTERNS.md lines 484-505. The CALIB-05 lesson (Lesson #1) MUST contain the literal phrase "threshold-basis hygiene" (acceptance criterion per 204-PATTERNS.md line 503).

    Section template (clone from 201-RETRO.md style):

    ```markdown
    # Phase 204 Retrospective: D-14 Successor Recalibration (CALIB)

    **Phase outcome:** CALIB-01..05 + SAFE-07 all satisfied. CALIB-04 verification soak at <CALIB_04_TS> passed the dual gate cleanly: D-19 primary stayed at 0 floor hits AND D-14 successor at the operator-approved threshold passed. Phase 201 RETRO Lesson #1 (metric semantics) is now closed. v1.43 milestone shipped with zero controller-path change.
    **Plans completed:** 6 of 6 (204-01 Deploy 1, 204-02 CALIB-01 baseline soak, 204-03 CALIB-02 operator approval, 204-04 CALIB-03 watchdog harness + Deploy 2, 204-05 CALIB-04 verification soak, 204-06 RETRO + closeout — this plan).
    **Time-on-phase:** approximately <N> calendar days (Deploy 1 → CALIB-04 PASS), spanning two 24h soaks.

    ## What Was Built

    - `aggregate_completed_window_distribution()` in `scripts/soak_summary_aggregate.py` (Plan 204-02) — distribution math for the post-fix completed-window suppression-count column.
    - `aggregate_watchdog()` + `load_calib_02_constants()` in `scripts/soak_summary_aggregate.py` (Plan 204-04) — dual-emission watchdog; legacy live-counter mean preserved alongside the new statistic for one milestone cycle.
    - `scripts/calib_02_threshold.json` — operator-approval-derived constants file (Plan 204-03).
    - `204-CALIB-02-OPERATOR-APPROVAL.md` — operator-signed threshold approval (Plan 204-03), with explicit slice-vs-total decision recording (open Q2).
    - Three test files: `tests/test_phase_204_distribution.py` (Plan 204-02), `tests/test_phase_204_watchdog.py` (Plan 204-04), `tests/test_phase_204_replay.py` (Plan 204-04).
    - Documentation in `docs/SOAK_HARNESS.md` "Watchdog computation transition (CALIB-03)" + CHANGELOG.md.

    ## What Was Tested in Production

    | Hypothesis | Result | Evidence |
    |------------|--------|----------|
    | The v1.43 binary running in production produces the same control surface as Phase 201 close (no SAFE-07 violation) | confirmed | `bash scripts/check-safe07-source-diff.sh` exit 0 throughout |
    | A soak-calibrated D-14 successor threshold (operator-approved on CALIB-01 evidence) PASSES on a verification soak | <pass/fail per Plan 204-05> | `204-05-CALIB-04-SOAK-VERDICT.md` |
    | The legacy live-counter mean ports byte-equivalently from inline jq to Python | confirmed | `tests/test_phase_204_watchdog.py::TestV142WatchdogRegression` against oracle 6.466842364880155 |

    ## What Worked

    - Two-snapshot rollback ritual on Deploy 1 (Plan 204-01) was a trivial no-op for YAML reconciliation (v1.43 ships zero new YAML keys), but the snapshot capture itself was retained for evidence symmetry — operator confidence cost was zero.
    - Per-cause-tag breakdown in CALIB-01 distribution (`by_cause.{dwell_hold, backlog_recovery, other}`) made the open-Q2 slice-vs-total decision data-backed rather than judgment-only.
    - v1.42 oracle regression test gave a clean signal that the inline-jq → Python port preserved semantics — the 6.466842364880155 ± 1e-6 assertion is unambiguous.

    ## What Was Inefficient / Harder Than Expected

    - <fill in based on actual execution; templates if nothing surfaces: harness fixture refresh in two places (Phase 203 + Phase 204) was easy to miss; primary_gate computation needs to be assembled from operator-recorded baseline + post-soak /health rather than emitted by the aggregator>

    ## Patterns Established

    - **Operator-approval-derived JSON pattern** (`scripts/calib_02_threshold.json`) — first instance under `scripts/` of a config file consumed by another script, with the human-readable artifact as source of truth. Reusable for future operator-approved-constant work.
    - **Dual-emission for one transition cycle = one milestone** (CALIB-03) — pattern for evolving harness math without breaking historical interpretability. Apply same approach in v1.44 when dropping the legacy block.
    - **Plan 201-15 two-snapshot ritual reuse for additive-only deploys** — the ritual structure is preserved even when YAML reconciliation is a no-op; this normalizes the operator workflow across Phase 200/201/202/203/204+ deploys.

    ## Key Lessons

    1. **Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.** D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default. **(CALIB-05.)**
    2. <add other lessons surfaced during execution>

    ## Cross-Reference

    - REQUIREMENTS.md CALIB-01..05 + SAFE-07
    - 204-CALIB-02-OPERATOR-APPROVAL.md (the soak-grounded threshold)
    - 204-05-CALIB-04-SOAK-VERDICT.md (the dual-gate proof)
    - Phase 201 RETRO Lesson #1 (metric semantics — now closed by Phase 202 + 204)
    - Phase 201 RETRO Lesson #2 (threshold-basis hygiene — repeated here as Lesson #1 for emphasis)

    ## Lessons for v1.44

    - **Drop `secondary_gate_legacy` from `aggregate_watchdog()`.** Per CALIB-03 transition-cycle definition (one milestone), v1.43 emitted both legacy and new; v1.44 should drop the legacy block in a one-commit follow-up.
    - **Consider promoting CALIB-02 threshold to YAML.** Per REQUIREMENTS.md Out-of-Scope §4, the soak-harness Python constant was the chosen v1.43 form "until proven through CALIB-04." If CALIB-04 PASSed cleanly, the threshold has been proven; v1.44 may evaluate operator-facing YAML knob.
    - **SEED-005** conservative UL tuning sweep prereqs are now complete (METRIC-01 + OBSV-05 + CALIB-01 all live in production with clean baseline soak under CALIB-02's recalibrated threshold). v1.44 may re-evaluate.

    ## Open Questions / Nothing-Claimed-But-Not-Shipped

    - <track any items the executor surfaces during execution>
    ```

    Step 2: Create `.planning/todos/pending/2026-XX-XX-v1.44-drop-secondary-gate-legacy-and-promote-calib02-to-yaml.md` (use today's date in `YYYY-MM-DD` format):

    ```markdown
    # v1.44 Follow-up: Drop secondary_gate_legacy and consider CALIB-02 YAML promotion

    Created: <YYYY-MM-DD>
    Source: Phase 204 RETRO Lessons for v1.44 (CALIB-03 transition-cycle definition; CALIB-02 promotion-after-proof)
    Status: pending

    ## Items

    1. **Drop `secondary_gate_legacy` block from `aggregate_watchdog()`** in `scripts/soak_summary_aggregate.py`. Per CALIB-03 transition cycle = one milestone (v1.43 emitted both; v1.44 drops legacy). One-commit follow-up. Update `tests/test_phase_204_watchdog.py::TestV142WatchdogRegression` accordingly (or retire the legacy regression test).

    2. **Consider promoting CALIB-02 threshold to a YAML config knob.** Per REQUIREMENTS.md Out-of-Scope §4, the soak-harness Python constant in `scripts/calib_02_threshold.json` was the v1.43 form "until proven through CALIB-04." If Phase 204 CALIB-04 PASSed (`204-05-CALIB-04-SOAK-VERDICT.md` verdict: pass), the threshold has been proven and v1.44 may evaluate exposing it as an operator-facing YAML knob (e.g., `continuous_monitoring.upload.calib_02_threshold`).

    3. **SEED-005** conservative UL tuning sweep prereqs are now complete (METRIC-01 + OBSV-05 + CALIB-01 + CALIB-02 + CALIB-04 all live with clean baseline soak). v1.44 may pull SEED-005 from deferred status into active scope.

    ## References

    - .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md
    - .planning/REQUIREMENTS.md (CALIB-* + SAFE-07; SEED-005 deferred)
    - .planning/ROADMAP.md
    ```

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>test -f .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md &amp;&amp; grep -q "threshold-basis hygiene" .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md &amp;&amp; grep -q "## Lessons for v1.44" .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md &amp;&amp; ls .planning/todos/pending/*v1.44-drop-secondary-gate-legacy*.md &amp;&amp; grep -q "secondary_gate_legacy" .planning/todos/pending/*v1.44-drop-secondary-gate-legacy*.md &amp;&amp; bash scripts/check-safe07-source-diff.sh</automated>
  </verify>
  <acceptance_criteria>
    - 204-RETRO.md exists with all nine sections
    - `grep -q "threshold-basis hygiene" .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md` exits 0 (CALIB-05 acceptance)
    - `grep -q "## Lessons for v1.44" .planning/phases/204-d-14-successor-recalibration-calib/204-RETRO.md` exits 0
    - v1.44 follow-up TODO file exists in `.planning/todos/pending/` with both items 1 (legacy drop) and 2 (YAML promotion) named
    - `bash scripts/check-safe07-source-diff.sh` exits 0
  </acceptance_criteria>
  <done>CALIB-05 satisfied via RETRO. v1.44 follow-up captured.</done>
</task>

<task type="auto">
  <name>Task 3: Update REQUIREMENTS.md, ROADMAP.md, STATE.md, CHANGELOG.md (milestone close)</name>
  <read_first>
    - .planning/REQUIREMENTS.md (CALIB-01..05 + SAFE-07 rows currently `[ ]`)
    - .planning/ROADMAP.md (Phase 204 row + v1.43 milestone row)
    - .planning/STATE.md (current Position section + Decisions + Performance Metrics)
    - CHANGELOG.md current `## v1.43-dev` heading at line 8
    - 204-PATTERNS.md lines 644-661 (CHANGELOG flip pattern)
  </read_first>
  <files>.planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/STATE.md, CHANGELOG.md</files>
  <action>
    Step 1: REQUIREMENTS.md — flip the six Phase 204 rows from `[ ]` to `[x]` and append the plan reference:
    - `[x] **CALIB-01** — ... (Plan 204-02)`
    - `[x] **CALIB-02** — ... (Plan 204-03)`
    - `[x] **CALIB-03** — ... (Plan 204-04)`
    - `[x] **CALIB-04** — ... (Plan 204-05)`
    - `[x] **CALIB-05** — ... (Plan 204-06)`
    - SAFE-07 row: keep `[x]` (already satisfied across phases) but update last-verified date in the trailing "Last updated" line.

    Update the Traceability table at the bottom — fill in the Plan column for CALIB-01..05 with the corresponding 204-NN references.

    Update the trailing `_Last updated:_` line with today's date and a closure note.

    Step 2: ROADMAP.md — Phase 204 row in the "Progress" table flips from `Not started` → `Complete` with today's date; the `### Phase 204:` "Plans" line flips to `**Plans**: 6/6 complete (...)`. Milestone v1.43 row at the top of the file flips from `🚧` → `✅`. Update the "Current Milestone" header to mark v1.43 as shipped.

    Step 3: STATE.md — update front-matter:
    - `progress.completed_phases: 3` (was 2 — Phase 204 now complete)
    - `progress.completed_plans: 13` (was 7 — Phase 204 added 6 plans)
    - `progress.percent: 100`
    - `last_updated`, `last_activity`, `stopped_at` updated
    Update Position section: "Last shipped milestone: v1.43 UL Suppression Metrics & Gate Calibration (shipped <YYYY-MM-DD>)". Add Decisions entries for Phase 204-01 through 204-06 close. Add Performance Metrics rows summarizing each Phase 204 plan completion.

    Step 4: CHANGELOG.md — flip `## v1.43-dev` heading to `## v1.43.0 — <YYYY-MM-DD>` per 204-PATTERNS.md line 651. Ensure all Phase 202 / 203 / 204 entries are present under it.

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>grep -E "^- \[x\] \*\*CALIB-0[1-5]\*\*" .planning/REQUIREMENTS.md | wc -l | grep -q '^5$' &amp;&amp; grep -q "Phase 204" .planning/ROADMAP.md &amp;&amp; grep -qE "v1\.43\.0 — [0-9]{4}-[0-9]{2}-[0-9]{2}" CHANGELOG.md &amp;&amp; bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - All five `**CALIB-0X**` rows in REQUIREMENTS.md flipped to `[x]` and reference their plan
    - REQUIREMENTS.md Traceability table populated for CALIB-01..05
    - ROADMAP.md Phase 204 row marked Complete; v1.43 milestone marked ✅
    - STATE.md progress fields updated to reflect 3/3 phases, 13/13 plans, 100%
    - CHANGELOG.md heading reads `## v1.43.0 — <YYYY-MM-DD>`
    - SAFE-07 source-diff still clean
    - Hot-path slice still green
  </acceptance_criteria>
  <done>Milestone v1.43 documented as shipped across REQUIREMENTS, ROADMAP, STATE, CHANGELOG.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Closeout artifacts → milestone-shipped state | The closeout files are the historical record; tampering = silently mis-stating what shipped. |
| SAFE-07 mechanical checks → ship/no-ship gate | All four checklist commands must exit 0; any failure blocks the close. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-06-01 | Tampering | scripts/check-safe07-source-diff.sh `b72b463` ref | mitigate | Per 204-RESEARCH.md §Risk 5 lines 736-740, ref is stable on main; if ever rebased, the script catches the missing ref via exit code 2. |
| T-204-06-02 | Repudiation | Closeout decisions | mitigate | All recorded in committed RETRO + VERIFICATION + STATE files; no silent state changes. |
| T-204-06-03 | Information Disclosure | RETRO + VERIFICATION + TODO content | accept | Public-safe content; no secrets; standard milestone-archive practice. |
</threat_model>

<verification>
- 204-VERIFICATION.md status: satisfied (Task 1)
- 204-VALIDATION.md nyquist_compliant: true (Task 1)
- 204-RETRO.md contains "threshold-basis hygiene" (Task 2)
- v1.44 follow-up TODO file exists (Task 2)
- REQUIREMENTS.md CALIB-01..05 + SAFE-07 all `[x]` (Task 3)
- ROADMAP.md Phase 204 + v1.43 marked complete (Task 3)
- STATE.md progress 100% (Task 3)
- CHANGELOG.md heading flipped to v1.43.0 (Task 3)
- All four SAFE-07 closeout commands exit 0
- Full suite green
- Zero src/wanctl/ source diff between Phase 201 close (b72b463) and v1.43 close
</verification>

<success_criteria>
Phase 204 closed. Milestone v1.43 shipped. CALIB-01..05 + SAFE-07 satisfied. RETRO captures threshold-basis hygiene as the durable lesson. v1.44 follow-up TODO captures the legacy-drop and YAML-promotion deferrals. SAFE-07 mechanically verified clean — zero `src/wanctl/` source diff between Phase 201 close (`b72b463`) and v1.43 close. SAFE-05 three-dict pin block byte-identical (no `phase204_expected_counts` dict added).
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-06-SUMMARY.md` recording:
- Closeout date
- Final SAFE-07 + SAFE-05 + hot-path + phase-scoped + full-suite test counts (all PASS)
- All six requirements satisfied
- v1.44 follow-up TODO file path
- Hand-off pointer: milestone v1.43 ready for `/gsd-complete-milestone`
</output>

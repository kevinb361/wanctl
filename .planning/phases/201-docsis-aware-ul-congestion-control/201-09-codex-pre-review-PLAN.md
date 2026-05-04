---
phase: 201-docsis-aware-ul-congestion-control
plan: 09
type: execute
wave: 1
depends_on: [01, 02]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md
autonomous: false
requirements: [VALN-06]
tags: [phase-201, wave-1, cross-ai-review, d-18, codex, checkpoint]

must_haves:
  truths:
    - "Codex has reviewed the SPEC + Wave 0 stubs + Plans 03-08 BEFORE Wave 1 implementation lands"
    - "Codex's review is captured in 201-09-CODEX-PRE-REVIEW.md with explicit signal-or-design challenges"
    - "Operator has explicitly accepted, deferred, or rejected each Codex comment with rationale"
    - "If Codex flags signal-or-design issue with HIGH severity, Wave 1+ is paused until reconciliation lands as a plan amendment"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md
      provides: "Codex review verdict + operator dispositions"
      contains: "Codex Review"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md"
      to: "Plans 201-03 through 201-08"
      via: "review covers each plan; dispositions reference plan IDs"
      pattern: "201-0[3-8]"
---

<objective>
Wave 1 cross-AI review checkpoint (D-18). Required, NOT optional, per Phase 200 RETRO "high-leverage on production-control work" and CONTEXT D-18.

Codex reads SPEC (CONTEXT.md, RESEARCH.md, PATTERNS.md), Wave 0 stubs (Plans 201-01, 201-02), and Plans 201-03 through 201-08 BEFORE any production code lands. Goal: catch signal-or-design errors at the cheapest possible moment — before tests or implementation.

Phase 200's pre-review caught the value-derived presence-flag regression (D-03) and the architectural-direction question that produced the operator's escalation to Phase 201. The same leverage point applies here.

Output: 201-09-CODEX-PRE-REVIEW.md with each Codex comment + operator disposition; if any HIGH-severity signal-or-design challenge survives without remediation, Wave 1+ is BLOCKED.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VALIDATION.md
@.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Run Codex pre-review against Phase 201 SPEC + Plans 03-08</name>
  <what-built>
    Wave 0 stubs (Plans 201-01, 201-02) are landed. Plans 201-03 through 201-08 are written but NOT YET executed. The window for cross-AI review is open: Codex can challenge the design choices (D-09 setpoint=12, augment-vs-replace, RESEARCH §5 R5+R3 keep, integral threshold default 30 ms·s, CAKE corroborator categorical-only, predeploy-gate Option B fail-closed) WITHOUT requiring code-revert.
  </what-built>
  <how-to-verify>
    Operator MUST execute these steps and capture results in `.planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md`:

    1. From the project root, invoke Codex CLI with explicit context handoff:

       ```
       codex review-phase 201 \
           --spec .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md \
           --research .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md \
           --patterns .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md \
           --plans .planning/phases/201-docsis-aware-ul-congestion-control/201-03-config-schema-and-validators-PLAN.md,.planning/phases/201-docsis-aware-ul-congestion-control/201-04-controller-core-PLAN.md,.planning/phases/201-docsis-aware-ul-congestion-control/201-05-wan-controller-and-health-PLAN.md,.planning/phases/201-docsis-aware-ul-congestion-control/201-06-spectrum-yaml-and-version-PLAN.md,.planning/phases/201-docsis-aware-ul-congestion-control/201-07-predeploy-gate-PLAN.md,.planning/phases/201-docsis-aware-ul-congestion-control/201-08-canary-script-extension-PLAN.md
       ```

       (If `codex review-phase` is not a real subcommand on this machine, fall back to invoking codex interactively and feeding it the file paths — operator's call. The deliverable is a written review, not a specific CLI invocation.)

    2. Ask Codex to specifically challenge:
       - **D-09 setpoint=12 Mbit:** does Codex see evidence in the three Spectrum sweep notes (`spectrum-inline-native-18-upload-test-2026-04-29.md`, `spectrum-upload-ceiling-sweep-2026-04-29.md`, `spectrum-target-bloat-sweep-2026-04-15.md`) that argues for a different value?
       - **Augment-vs-replace:** does Codex agree that AUGMENT preserves ARCH-03 better than REPLACE? Is there a scenario where the integral path interferes with the RED fast-trip?
       - **R5+R3 keep:** RESEARCH §5 says retain factor_down_yellow=1.0 and consecutive_yellow_decay_clamp=40. Does Codex see a YELLOW-decay edge case where R5 + setpoint clamp interact badly?
       - **Integral threshold 30 ms·s:** is this the right default, or is the linear "average sample at target_delta" framing flawed?
       - **CAKE corroborator categorical-only:** Phase 197 RETRO 2026-04-23 forbade µs/ms ratios; does Codex agree categorical AND-gate is the only durable shape?
       - **Predeploy-gate Option B (fail-closed, NOT auto-strip):** is operator-manual reconciliation the right shape, or does Codex want auto-strip with audit trail?
       - **Per-key explicit-presence flags presence-based (D-03 mirror):** Phase 200 Codex pre-review caught the value-derived bug. Does the Phase 201 plan correctly mirror presence-based via `"key" in ul`?
       - **/health additive runtime-state semantics:** are the five new fields runtime-state (read from `self.upload.*`) and not YAML echoes (Phase 200 Plan 05 bug 2 family)?
       - **Plan 201-04 budget claim ("under ~80 lines net new"):** does Codex see scope creep risk? Should anything be pulled out?

    3. Capture the Codex review verdict in `.planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md` with this structure:

       ```
       # Phase 201 — Codex Pre-Review (D-18)

       **Reviewed:** YYYY-MM-DD
       **Reviewer:** Codex (model + version)
       **Scope:** SPEC + Wave 0 stubs + Plans 201-03 through 201-08
       **Verdict:** PASS | PASS WITH COMMENTS | BLOCK

       ## Comments

       | # | Severity (HIGH/MED/LOW) | Plan / Section | Issue | Operator disposition (ACCEPT / DEFER / REJECT) | Rationale |
       |---|--------------------------|----------------|-------|------------------------------------------------|-----------|
       | 1 | ... | ... | ... | ... | ... |

       ## Plan Amendments Required (if any)

       List any plan files that need updating before Wave 1 starts. Each entry cites the plan ID + section + the operator-accepted change.

       ## Operator Sign-Off

       - [ ] All HIGH-severity comments have ACCEPT or REJECT-with-rationale dispositions
       - [ ] No HIGH-severity comment has unaddressed DEFER (DEFER allowed only for LOW/MED)
       - [ ] Plan amendments (if any) are listed and dated
       - [ ] Operator confirms Wave 1 may proceed
       ```

    4. If verdict is BLOCK or any HIGH-severity comment is unresolved, STOP. Re-plan affected sections via `/gsd-plan-phase --reviews` mode or operator-direct edits before proceeding to Wave 1.
  </how-to-verify>
  <resume-signal>
    After committing 201-09-CODEX-PRE-REVIEW.md with completed Operator Sign-Off, type "approved" to proceed to Wave 1 (Plan 201-03 execution).

    If BLOCK, type "blocked" + brief reason; the orchestrator will route to plan amendments.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Claude (planner) -> Codex (reviewer) | Cross-AI review surface. Codex sees the same files Claude has authored; review verdict is the new artifact. |
| Codex review -> operator decision | Operator is the authority; Codex comments are advisory until accepted. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-41 | Repudiation | Codex review skipped or ignored ("we know better this time") | mitigate | D-18 makes review REQUIRED, not optional. This plan is gating; orchestrator will not proceed to Wave 2+ until this checkpoint completes. |
| T-201-42 | Tampering | Review verdict captured incompletely (HIGH comments dropped) | mitigate | Sign-off checklist requires explicit handling of every HIGH comment; DEFER not allowed for HIGH. |
| T-201-43 | Spoofing | Codex output fabricated or summarized away | accept | Operator is in the loop; the operator runs Codex directly. No mitigation needed at this level. |
</threat_model>

<verification>
- 201-09-CODEX-PRE-REVIEW.md exists with completed sign-off block.
- All HIGH comments have ACCEPT or REJECT dispositions (no unresolved DEFER).
- Plan amendments (if any) are linked from the review doc.
</verification>

<success_criteria>
- D-18 pre-review checkpoint completed.
- Operator has the audit trail of what Codex challenged and how each comment was handled.
- Wave 1 only proceeds after operator types "approved".
- Phase 200 RETRO "high-leverage" pattern preserved.
</success_criteria>

<output>
The artifact IS the SUMMARY for this plan: `.planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md` is the audit trail. After it commits, the orchestrator can proceed to Wave 2.

(No separate `201-09-SUMMARY.md` is required — the review doc IS the summary.)
</output>

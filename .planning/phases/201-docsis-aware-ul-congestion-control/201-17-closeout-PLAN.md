---
phase: 201-docsis-aware-ul-congestion-control
plan: 17
type: execute
wave: 1
depends_on: [201-16]
gap_closure: true
files_modified:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/STATE.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md
  - .planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md
  - .planning/seeds/SEED-003-v143-d14-watchdog-recalibration.md
  - .planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md
  - .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md
autonomous: false
requirements: [VALN-06]
tags: [closeout, gap_closure, retrospective, v1.43-baton]

must_haves:
  truths:
    - "Phase 201 is recorded as `gaps_found` in REQUIREMENTS.md, ROADMAP.md, STATE.md, and 201-VERIFICATION.md, with explicit deferral language that names v1.43 (or `v1.43+`) as the successor for the D-14 suppression watchdog."
    - "201-RETRO.md exists and follows the structural shape of 200-RETRO.md, including a Final Closure section dated 2026-05-06, a Route B summary, and a Lessons-for-v1.43 subsection enumerating four ordered backlog items."
    - "Four v1.43 backlog seed files exist under .planning/seeds/, numbered SEED-002..SEED-005 in priority order, each containing the priority rationale (items 1–3 are prerequisites to item 4)."
    - "STATE.md `stopped_at` no longer contains the phrase `awaiting operator`; the operator decision (Route B) and Plan 17 closeout are reflected."
    - "No production code, configs, tests, or scripts are modified by this plan (src/wanctl/, configs/, tests/, scripts/ untouched)."
  artifacts:
    - path: ".planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md"
      provides: "Phase 201 retrospective with Route B closure and v1.43 baton-pass"
      contains: ["Route B", "metric_semantics_and_recalibration", "Lessons for v1.43", "Final Closure (2026-05-06)"]
    - path: ".planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md"
      provides: "v1.43 backlog item 1 (metric semantics fix; prerequisite for items 2–4)"
    - path: ".planning/seeds/SEED-003-v143-d14-watchdog-recalibration.md"
      provides: "v1.43 backlog item 2 (D-14 successor recalibration; depends on item 1)"
    - path: ".planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md"
      provides: "v1.43 backlog item 3 (per-sample load_rtt - baseline_rtt distribution capture)"
    - path: ".planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md"
      provides: "v1.43 backlog item 4 (gated dwell_cycles / target_bloat_ms tune; depends on items 1–3)"
  key_links:
    - from: ".planning/REQUIREMENTS.md VALN-06 row"
      to: ".planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md"
      via: "explicit `gaps_found` + `v1.43` deferral text matching the existing `Deferred -> Phase 201` formatting style"
      pattern: "VALN-06.*gaps_found.*v1\\.43"
    - from: ".planning/ROADMAP.md Phase 201 entry"
      to: "201-RETRO.md and v1.43 baton"
      via: "closure-line mirroring Phase 200's `closed (gaps_found)` pattern"
      pattern: "Phase 201.*gaps_found.*D-14 deferred"
    - from: ".planning/STATE.md `stopped_at`"
      to: "operator Route B decision"
      via: "stopped_at update reflecting Plan 17 closeout complete (no `awaiting operator`)"
      pattern: "stopped_at: Phase 201.*closed.*gaps_found"
---

<objective>
Close Phase 201 documentation state per operator Route B decision (2026-05-06): mark `gaps_found`, hand the residual D-14 watchdog gap to v1.43+, and seed the four-item v1.43 backlog in priority order. NO production code, configs, tests, or scripts change.

Purpose: D-19 primary VALN-06 floor-hit gate PASSED on canary 20260505T122513Z and 24h soak 20260505T132736Z (v1.42.1 in production). D-14 secondary suppression watchdog FAILED at 6.47/min vs <5.0, classified by Codex re-aggregation as `metric_semantics_and_recalibration` on the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at queue_controller.py:348), unrelated to the bounded RED decay path Plan 201-14 fixed (queue_controller.py:361-376). The phase-goal control behavior shipped; the residual gap is metric-side, not control-side. Operator Route B is the recorded closure shape.

Output:
- 201-RETRO.md (new) mirroring Phase 200 RETRO structure
- Updated VALN-06 row in REQUIREMENTS.md
- Updated Phase 201 entry in ROADMAP.md (mirroring Phase 200 `closed (gaps_found)` pattern)
- Updated Deferred Ideas section in 201-CONTEXT.md
- Updated re_verification block in 201-VERIFICATION.md
- Updated STATE.md `stopped_at` and metadata
- Four v1.43 backlog seed files in `.planning/seeds/` (SEED-002..SEED-005) in priority order
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SUMMARY.md
@.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md

<closure_route_summary>
**Route B (operator decision, 2026-05-06):** close Phase 201 as `gaps_found`.

- **D-19 primary VALN-06 floor-hit gate: PASS.** Canary `20260505T122513Z` and 24h soak `20260505T132736Z` both report `floor_hit_cycles_total_delta=0`. Production binary v1.42.1 surviving 24h saturation. Rollback path validated by Plan 201-15 two-snapshot strategy.
- **D-14 secondary suppression watchdog: FAIL** at `6.466842364880155/min` vs `<5.0`, classified `metric_semantics_and_recalibration`, NOT control regression.
- D-14 FAIL lives on the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), not the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`). Codex re-aggregation of 84,117-sample soak NDJSON: `red_streak>0` in 0.023% of samples; YELLOW tails in 1.52%; suppression correlates 0.72 with YELLOW samples and 0.01 with `max_delay_delta_us`.
- **Metric-semantics surprise:** `suppressions_per_min` field at `queue_controller.py:649,668` is a 60s reset *counter*, not a true rate. The published 6.47 mean is the mean of live-counter snapshots. Completed-window peak mean is ~13.9/min (p95=41, max=124). D-14's `<5/60s` threshold was inherited from Phase 200's qualitative "31/60s degraded → near-zero" framing — never soak-calibrated against the post-Plan-201-14 control surface.
</closure_route_summary>

<v143_backlog_priority_order>
The four v1.43 items are LOAD-BEARING in this order. Items 1–3 are prerequisites to item 4. Each seed file MUST state its priority rationale.

1. **SEED-002 — UL suppression-counter metric-semantics fix.** Add completed-window UL suppression counts + cause tags (dwell-hold vs backlog-recovery vs other) to `/health`. Additive only — preserve the existing `suppressions_per_min` field. Required prerequisite for items 2–4.
2. **SEED-003 — D-14 successor recalibration.** Replace D-14's `<5/60s` with a soak-derived threshold from a clean 24h baseline of the post-201-14 binary, using completed-window counts (item 1) instead of live-counter-snapshot means. Depends on item 1.
3. **SEED-004 — target-edge churn instrumentation.** Add per-sample `load_rtt - baseline_rtt` distribution capture to soak schema. Current soak has integral and zone trace but not per-sample delta. Required before any `target_bloat_ms` tune.
4. **SEED-005 — Conservative tuning sweep (gated).** Only after items 1–3 land. Candidates: `dwell_cycles: 5 → 4` and/or modest `upload_target_bloat_ms` bump above 15ms. Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back).
</v143_backlog_priority_order>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update REQUIREMENTS.md VALN-06 traceability row for Phase 201 partial closure</name>
  <files>.planning/REQUIREMENTS.md</files>
  <read_first>
    - `.planning/REQUIREMENTS.md` (current VALN-06 row at lines 105-107 of v1.41 Traceability table; mirrors `Deferred -> Phase 201 (inherited blocking requirement)` formatting)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` lines 195-203 (Requirements Coverage table for the authoritative status wording)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md` (canonical numbers)
  </read_first>
  <action>
Edit the v1.41 Traceability table VALN-06 row (currently `| VALN-06 | Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement) (...). → Phase 201 gap-closure soak FAIL ... Next action: operator decision between A5-style controlled reattempt and v1.43+ control-model/suppression-watchdog follow-up. |`).

Append (do NOT replace) closure language that mirrors the existing arrow-prefixed continuation style:

`→ Phase 201 closed gaps_found 2026-05-06 (operator Route B). D-19 primary floor-hit gate PASSED (canary 20260505T122513Z and 24h soak 20260505T132736Z both at floor_hit_cycles_total_delta=0; v1.42.1 in production). D-14 secondary suppression watchdog FAILED at 6.466842364880155/60s mean (vs <5.0), classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (queue_controller.py:348), not a control regression on the bounded RED decay path Plan 201-14 fixed (queue_controller.py:361-376). D-14 successor work deferred to v1.43 as four ordered backlog items (see .planning/seeds/SEED-002..SEED-005 and 201-RETRO.md). VALN-06 phase-goal control behavior achieved; this row remains tracked under v1.41 for the partial closure trail.`

Preserve the existing `Status` cell content (the `Deferred -> Phase 201 (inherited blocking requirement)` lead-in and all prior `→` continuation lines). The new sentence is additive. Do not edit the Phase column.

Do NOT change ARB-05, SAFE-06, or DOCS-03 rows. Do NOT touch v1.39 traceability.
  </action>
  <acceptance_criteria>
    - `grep -E 'VALN-06.*gaps_found.*v1\.43' .planning/REQUIREMENTS.md` returns the updated VALN-06 row
    - `grep -c 'VALN-06' .planning/REQUIREMENTS.md` count is unchanged from before the edit (only the existing row was extended; no new row added)
    - `grep -F 'metric_semantics_and_recalibration' .planning/REQUIREMENTS.md` returns the new wording
    - `grep -F '20260505T132736Z' .planning/REQUIREMENTS.md` returns the soak-evidence reference
    - The existing `Deferred -> Phase 201 (inherited blocking requirement)` text is still present (additive edit, not replacement)
    - ARB-05, SAFE-06, DOCS-03 rows are byte-identical to before
  </acceptance_criteria>
  <verify>
    <automated>grep -E 'VALN-06.*gaps_found.*v1\.43' .planning/REQUIREMENTS.md && grep -F 'metric_semantics_and_recalibration' .planning/REQUIREMENTS.md && grep -F 'Deferred -> Phase 201 (inherited blocking requirement)' .planning/REQUIREMENTS.md && [ "$(grep -c 'VALN-06' .planning/REQUIREMENTS.md)" = "2" ]</automated>
  </verify>
  <done>VALN-06 row carries the partial-closure status with explicit v1.43 deferral, preserving the existing inherited-blocking trail.</done>
</task>

<task type="auto">
  <name>Task 2: Update ROADMAP.md Phase 201 entry to mirror Phase 200 gaps_found closure pattern</name>
  <files>.planning/ROADMAP.md</files>
  <read_first>
    - `.planning/ROADMAP.md` lines 122-124 (Phase 200 closure-line in Phase Summary table) and lines 130-163 (Phase 200 body — note the explicit `Closed (gaps_found)` summary cell and the `**(Deferred to Phase 201 — see `200-RETRO.md`...)**` annotations on Success Criteria 3 and 4)
    - `.planning/ROADMAP.md` lines 183-185 (Phase 201 row in v1.42 Phase Summary table — currently `In Progress`)
    - `.planning/ROADMAP.md` lines 220-247 (Phase 201 body, Success Criteria, and Plans list — Plan 16 is `[x]`; Phase summary line at 227 says "15/16 plans executed; Plan 201-16 executed and recorded soak FAIL")
    - `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` `## Final Closure (2026-05-04)` section (closure pattern reference — Route B mirrors Route A in shape)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` (authoritative status wording)
  </read_first>
  <action>
Three coordinated edits to ROADMAP.md, ALL within the v1.42 / Phase 201 region:

**Edit A — Phase Summary table row (line 185).** Replace the cell `| 201 | DOCSIS-Aware UL Congestion Control | 14/16 | In Progress|  |` with:

`| 201 | DOCSIS-Aware UL Congestion Control | 16/16 | Closed (gaps_found) — D-19 primary VALN-06 PASS shipped on v1.42.1; D-14 suppression watchdog deferred to v1.43+ as metric_semantics_and_recalibration | 2026-05-06 |`

**Edit B — Success Criteria annotations (lines 220-225).** On Success Criteria #2 and #3, append closure annotations mirroring the Phase 200 pattern (where SC#3 and SC#4 carry `**(Deferred to Phase 201 — see `200-RETRO.md`. ...)**` parenthetical updates).

For SC#2 (the canary criterion at line 222), append after the existing `verdict.json` reference:
`**(SATISFIED 2026-05-05 — recanary `20260505T122513Z` PASSED with `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`. Phase-goal D-19 primary VALN-06 closure evidence on v1.42.1.)**`

For SC#3 (the soak criterion at line 223 — already carries the Plan 201-16 result), the existing text already records the gate disagreement. Append:
`**(Closed Route B 2026-05-06 — operator decision: D-19 primary PASS satisfies the dominant phase-goal proof; D-14 secondary deferred to v1.43+ as `metric_semantics_and_recalibration`. See `201-RETRO.md`.)**`

**Edit C — Plans-summary line and Plan 17 entry.**

Update the Plans-summary line currently at line 227:
`**Plans:** 15/16 plans executed; Plan 201-16 executed and recorded soak FAIL`

Replace with:
`**Plans:** 16/16 plans complete — Phase 201 closed as `gaps_found` 2026-05-06 via operator Route B. D-19 primary VALN-06 floor-hit gate PASSED on canary `20260505T122513Z` and 24h soak `20260505T132736Z` (production binary v1.42.1 with rollback evidence at `canary/20260505T122513Z/` and `soak/20260505T132736Z/`). D-14 secondary suppression watchdog FAILED at `6.466842364880155/60s` mean (vs `<5.0`); FAIL is on the YELLOW-edge dwell-hold path (`queue_controller.py:348`), unrelated to the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`), and the original threshold was never soak-calibrated against the post-fix control surface. D-14 work deferred to v1.43 as four ordered backlog items (`SEED-002`..`SEED-005`). See `201-RETRO.md` and `201-VERIFICATION.md` `closure_route` block.`

Then in the Plans checklist (line 230 onward), strike the stale Plan 12 line if it is currently `[ ]` (inspect: `- [ ] 201-12-soak-and-closeout-PLAN.md — Superseded by revised Plan 201-16...`). Leave the line in place but mark it `[~]` (or whatever marker is already used for superseded plans elsewhere — if no convention exists, add `(superseded)` parenthetical and leave checkbox `[ ]`; do NOT mark it `[x]`).

Append a new line at the end of the Plans checklist (after the Plan 16 entry at line 245):
`- [x] 201-17-closeout-PLAN.md — Phase 201 closeout per operator Route B 2026-05-06: documentation-state correction (REQUIREMENTS/ROADMAP/STATE/CONTEXT/VERIFICATION), 201-RETRO.md authored, four v1.43 backlog seeds opened in priority order; NO production binary or YAML change`

Do NOT touch v1.41, v1.40, v1.39, or any other milestone region.
  </action>
  <acceptance_criteria>
    - `grep -E 'Phase 201.*Closed \(gaps_found\)' .planning/ROADMAP.md` returns the Phase Summary row
    - `grep -F 'D-14 deferred' .planning/ROADMAP.md` matches (via `D-14 ... deferred to v1.43+` or equivalent in any of the three edits)
    - `grep -F 'canary/20260505T122513Z/' .planning/ROADMAP.md` returns the rollback-evidence reference
    - `grep -F 'soak/20260505T132736Z/' .planning/ROADMAP.md` returns the rollback-evidence reference
    - `grep -F 'v1.42.1' .planning/ROADMAP.md` returns the production binary reference
    - `grep -E '201-17-closeout-PLAN.md' .planning/ROADMAP.md` returns the new plan-checklist line
    - `grep -c 'Phase 201' .planning/ROADMAP.md` is at least the prior count (no Phase 201 rows removed)
    - Phase 200 region (lines 114-170) unchanged; v1.39 / v1.40 / archived regions unchanged
  </acceptance_criteria>
  <verify>
    <automated>grep -E 'Phase 201.*Closed \(gaps_found\)' .planning/ROADMAP.md && grep -F 'D-14' .planning/ROADMAP.md | grep -E 'deferred|defer' && grep -F '20260505T122513Z' .planning/ROADMAP.md && grep -F '20260505T132736Z' .planning/ROADMAP.md && grep -F '201-17-closeout-PLAN.md' .planning/ROADMAP.md</automated>
  </verify>
  <done>ROADMAP.md Phase 201 row, success criteria, plans-summary, and plan checklist all reflect Route B closure with v1.42.1 production binary and v1.43 baton-pass; mirrors Phase 200 closure formatting.</done>
</task>

<task type="auto">
  <name>Task 3: Update 201-CONTEXT.md Deferred Ideas section with v1.43 backlog items in priority order</name>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md</files>
  <read_first>
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` lines 188-205 (existing `<deferred>` section with `### Not in Scope for Phase 201` and `### Future Milestone Scope` subsections)
    - `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md` (authoritative four-item v1.43 list)
  </read_first>
  <action>
Add a new third subsection inside the existing `<deferred>` block, between `### Future Milestone Scope` (at line 202) and the closing `</deferred>` tag (line 206). Title it:

`### Deferred to v1.43+ via Route B Closure (2026-05-06)`

Body MUST state the priority order is load-bearing — items 1–3 are prerequisites to item 4 — and enumerate the four items with their priority rationale:

```
The Plan 201-16 24h soak D-14 watchdog FAIL at 6.466842364880155/60s mean (vs <5.0) was classified by Codex re-aggregation as `metric_semantics_and_recalibration` on the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), unrelated to the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`). The underlying counter `suppressions_per_min` (queue_controller.py:649,668) is a 60s reset counter rather than a true rate; the published 6.47 mean is the mean of live-counter snapshots, and the `<5/60s` threshold was inherited from Phase 200's qualitative "31/60s degraded → near-zero" framing without ever being soak-calibrated against the post-Plan-201-14 control surface.

Operator Route B (2026-05-06) defers D-14 successor work to v1.43+ as **four ordered backlog items**. The order is load-bearing: items 1–3 are prerequisites to item 4. Tracked at `.planning/seeds/SEED-002..SEED-005`.

1. **SEED-002 — UL suppression-counter metric-semantics fix.** Add completed-window UL suppression counts + cause tags (dwell-hold vs backlog-recovery vs other) to `/health`. Additive only — preserve the existing `suppressions_per_min` field. Required prerequisite for items 2–4.
2. **SEED-003 — D-14 successor recalibration.** Replace D-14's `<5/60s` with a soak-derived threshold from a clean 24h baseline of the post-201-14 binary, using completed-window counts (item 1) instead of live-counter-snapshot means. Depends on item 1.
3. **SEED-004 — target-edge churn instrumentation.** Add per-sample `load_rtt - baseline_rtt` distribution capture to soak schema. Current soak has integral and zone trace but not per-sample delta. Required before any `target_bloat_ms` tune.
4. **SEED-005 — Conservative tuning sweep (gated).** Only after items 1–3 land. Candidates: `dwell_cycles: 5 → 4` and/or modest `upload_target_bloat_ms` bump above 15ms. Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back).
```

Do NOT modify the existing `### Not in Scope for Phase 201` or `### Future Milestone Scope` subsections (the `<decisions>`, `<canonical_refs>`, `<code_context>`, and `<specifics>` blocks remain untouched). The edit is purely additive at the bottom of `<deferred>`.
  </action>
  <acceptance_criteria>
    - `grep -F 'Deferred to v1.43+ via Route B Closure' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` matches
    - `grep -F 'SEED-002' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` matches
    - `grep -F 'SEED-005' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` matches
    - `grep -F 'load-bearing' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` matches (priority-rationale signal)
    - `grep -F 'Modem SNMP / DOCSIS HCS counter signal' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` still matches (Not-in-Scope subsection preserved)
    - The closing `</deferred>` tag count is exactly 1 (no nesting bug)
  </acceptance_criteria>
  <verify>
    <automated>grep -F 'Deferred to v1.43+ via Route B Closure' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md && grep -cE 'SEED-00[2-5]' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md | grep -qE '^[4-9]|^[0-9]{2,}$' && [ "$(grep -c '</deferred>' .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md)" = "1" ]</automated>
  </verify>
  <done>201-CONTEXT.md `<deferred>` block carries the four-item v1.43 baton with explicit priority-order rationale; pre-existing Deferred Ideas content untouched.</done>
</task>

<task type="auto">
  <name>Task 4: Author 201-RETRO.md mirroring 200-RETRO.md structure with Route B closure and Lessons-for-v1.43</name>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md</files>
  <read_first>
    - `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` (FULL FILE — this is the structural template; mirror its section ordering: header → What Was Built → What Was Tested in Production → What Worked → What Was Inefficient → Patterns Established → Key Lessons → Cross-Reference → Gap-Closure Cycle → Final Closure)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` (authoritative numbers and outcomes)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md`, `201-14-SUMMARY.md`, `201-15-SUMMARY.md`, `201-16-SUMMARY.md` (Plan-by-plan outcomes)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md`
    - `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md` (operator decision rationale)
  </read_first>
  <action>
Create `.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` with the following structural skeleton. Use Phase 200 RETRO as the formatting template (heading levels, table style, bullet density). The numerical values, file paths, decision IDs, and lesson phrasings below are load-bearing — use them verbatim where given.

**Required sections, in order:**

```
# Phase 201 Retrospective: DOCSIS-Aware UL Congestion Control

**Phase outcome:** D-19 primary VALN-06 floor-hit gate PASSED on production v1.42.1; D-14 secondary suppression watchdog FAILED, classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (independent of the bounded RED decay fix). Closed `gaps_found` via operator Route B 2026-05-06; D-14 successor work deferred to v1.43+.
**Plans completed:** 16 of 16 (Plan 12 superseded by Plan 16 mid-flight after Plan 15 re-canary PASS).
**Time-on-phase:** ~3 days planning + ~14 days executing (2026-05-04 → 2026-05-06).

## What Was Built

- DOCSIS-aware UL congestion control mode (YAML opt-in via `continuous_monitoring.upload.docsis_mode: true`).
- Conservative YAML setpoint (Spectrum `setpoint_mbps=12`, 60% of provisioned upstream rate ~20 Mbit; Phase 200's 18 Mbit ceiling preserved as guard rail).
- RTT-integral classifier + CAKE-backlog direction-aligned secondary corroborator (Plan 201-04).
- Bounded-absolute RED decay clamp (Plan 201-14) replacing the multiplicative cascade-to-floor identified in 201-VERIFICATION.md as the original control-model defect.
- Integral anti-windup with synchronous headroom recompute (Plan 201-14, queue_controller.py:290-320).
- Red-decay safety validators failing closed on unsafe step/clamp/floor ordering (autorate_config.py:530-555 daemon, check_config_validators.py:576-654 offline mirror).
- Eight additive `/health` diagnostic fields (Plan 201-13): `max_delay_delta_us`, `red_streak`, `zone_trace` (200-element bounded deque), `headroom_exhausted_streak`, `anti_windup_cycles`, `anti_windup_triggers`, `red_decay_step_pct`, `red_decay_delta_max_pct`.
- Spectrum-only predeploy gate (`scripts/phase201-predeploy-gate.sh`) that blocks rejected v1.41 keys (`target_bloat_ms`, `warn_bloat_ms`) before deploy and either reconciles or fails closed.
- Phase 201 canary script extension to `scripts/phase200-saturation-canary.sh` with env-vs-YAML cross-check, /health DOCSIS-mode probe, and counter-delta primary verdict.
- Two Codex cross-AI review checkpoints (Plan 201-09 pre-review BLOCK with HIGH amendments; Plan 201-10 stop-time review GO WITH FOLLOW-UPS).
- Production binary `1.42.1` deployed to Spectrum via `/opt/wanctl` rsync; rollback path validated by Plan 201-15 two-snapshot strategy.

## What Was Tested in Production

- **Hypothesis:** A DOCSIS-aware UL congestion control mode running a YAML setpoint well below the upload ceiling, with RTT-integral as the headroom probe and CAKE backlog as a direction-aligned secondary corroborator, will hold Spectrum DOCSIS upload off the floor under saturated load (closing the inherited Phase 200 VALN-06 blocking requirement).
- **Result (D-19 primary VALN-06 gate):** ACCEPTED. Recanary `20260505T122513Z` PASSED with `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`, `floor_hit_cycles_total_delta_loaded_window=0` over a 1022s loaded window. 24h soak `20260505T132736Z` against v1.42.1 confirmed `floor_hit_cycles_total_delta_soak_window=0` over 84,117 captured samples (~86,400s, sample coverage ratio 0.974). The bounded-absolute RED decay clamp held above floor through 24h saturation with anti-windup trigger delta=0 (no anti-windup activations were needed).
- **Result (D-14 secondary suppression watchdog):** FAILED at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` (vs the inherited `<5.0` threshold). Codex re-aggregation of `soak-capture.ndjson` localized the FAIL to the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), unrelated to the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`). `red_streak>0` in 0.023% of samples; YELLOW tails in 1.52%; suppression correlates 0.72 with YELLOW samples and 0.01 with `max_delay_delta_us`. Classified as `metric_semantics_and_recalibration`, NOT control regression.
- **Evidence files:**
  - `canary/20260505T122513Z/verdict.json` (recanary PASS)
  - `canary/20260505T122513Z/loaded_capture.ndjson` (1022s loaded window)
  - `soak/20260505T132736Z/soak-summary.json` (D-19 PASS / D-14 FAIL)
  - `soak/20260505T132736Z/soak-capture.ndjson` (84,117 rows)
  - `201-15-CANARY-VERDICT.md`, `201-16-OPERATOR-APPROVAL-D19.md`, `201-16-SOAK-VERDICT.md`

## What Worked

- **Cross-AI review caught real issues before production contact.** Plan 201-09 Codex pre-review returned BLOCK with 5 HIGH findings (floor-hit counter placement, DOCSIS YELLOW/R5+R3 semantics, replay threshold fidelity, Spectrum-only predeploy gate wiring, fail-closed Phase 201 canary env enforcement). All five HIGH amendments landed before Wave 1+ continued. Plan 201-10 Codex stop-time review caught one MED follow-up (PHASE201_LOCAL_YAML_OVERRIDE confirmation) before live canary. The Phase 200 RETRO lesson "Cross-AI review before implementation is high-leverage on production-control work" held.
- **Two-snapshot rollback strategy on the recanary path (Plan 201-15) validated the rollback target without ever needing to roll back.** Snapshot A (rollback-clean, count=0) before reconcile and Snapshot B (post-gate, count=5) as deploy evidence cleanly separated "the rollback artifact is correct" from "the deploy artifact carries the new keys" — neither claim leaked into the other. This is a stronger pattern than Phase 200's single-snapshot approach.
- **Diagnostic seam from Plan 201-13 was load-bearing for the post-soak FAIL post-mortem.** Without `zone_trace`, `max_delay_delta_us` snapshot retention, and the anti-windup counter exposure, the D-14 FAIL would have looked like an ambiguous regression of the Plan 201-14 RED bounded decay. Codex re-aggregation of the 84,117-sample NDJSON used these fields to prove the FAIL was on the YELLOW-edge dwell-hold path, not the RED bounded decay path. **This separation is what made Route B (defer D-14, ship D-19) defensible instead of needing another remediation cycle.**
- **D-19 primary gate tightening (operator-approved pre-soak in `201-16-OPERATOR-APPROVAL-D19.md`) aligned the soak's primary metric with the canary's primary metric.** This let the closure decision focus on a single, narrow remaining gap (D-14 secondary) rather than triaging a noisy multi-failure soak.
- **Bounded-absolute RED decay validators failed closed.** The configuration `setpoint_mbps * (1 - red_decay_delta_max_pct) <= floor_mbps` is rejected by both the daemon (autorate_config.py:546-555) and the offline check-config (check_config_validators.py:625-654) — production cannot start with a configuration that would cascade to floor. Plan 201-14 added 12 validator tests including 1/3 floating-point at-equality rejection.
- **Phase 200 hardened canary tooling carried forward cleanly.** Reusing `scripts/phase200-saturation-canary.sh` with a Phase 201 preflight extension preserved the bug-fix history (logger silent-drop, /health field assumption, env-var false-PASS regression) at zero rewrite cost.

## What Was Inefficient / What Was Harder Than Expected

- **D-14 threshold was inherited without soak calibration.** The `<5/60s` was lifted from Phase 200's qualitative "31/60s degraded → near-zero" framing and stayed in the Phase 201 SPEC under the assumption that the new control mode would produce far less suppression than the rejected Phase 200 hypothesis. Once the soak ran on the post-201-14 control surface, the assumption did not hold for dwell-hold suppression specifically — but the threshold had no recalibration plan, and Codex re-aggregation was needed to establish that the FAIL was on a different code path. **A pre-canary "what is the post-fix steady-state value of this metric" prediction would have caught this earlier.**
- **`suppressions_per_min` field name implied a rate but was a 60s reset counter.** The published 6.47 mean is the mean of live-counter snapshots (instantaneous values of the counter at sample times), not a true 60s rate. Completed-window peak mean against the same data is ~13.9/min (p95=41, max=124). The headline number was honest under its definition but misleading under the threshold's definition. **This is the dominant durable lesson for v1.43.**
- **Plan 201-12 was written before Plan 201-11's canary outcome was known and became stale immediately.** Plan 201-11 canary FAILED with 1453 floor-hit cycles, prompting Plans 201-13 (diagnostic extension) and 201-14 (control-model amendment), then Plan 201-15 (re-canary) and Plan 201-16 (revised soak). Plan 201-12 sat as a stale soak path until Plan 201-15 re-canary PASS confirmed it was permanently superseded. Future phases involving control-path changes should write the canary plan, gate the soak plan behind the canary verdict, and only materialize the soak plan after the canary lands.

## Patterns Established (carry into future phases)

- **Diagnostic-first then control-model change is the right ordering for control-path phases.** Plan 201-13 added the `/health` diagnostic surface before Plan 201-14 changed the control model; this meant Plan 201-14's tests could lock invariants in terms of observable diagnostic fields, and Plan 201-16's post-soak post-mortem had the data it needed to do code-path attribution without re-running the soak.
- **Two-snapshot rollback strategy on production deploys.** Snapshot A captured before reconcile (rollback-clean), Snapshot B captured after deploy (post-gate evidence). Each snapshot answers exactly one question. Carry this forward to all v1.43+ production deploy plans.
- **Operator-approved gate tightening is a first-class pre-soak artifact.** D-19 tightening was captured in a distinct file (`201-16-OPERATOR-APPROVAL-D19.md`) before the soak started, separate from the verdict file. Codex round-2 LOW-CODEX-5 caught that this had to be a distinct artifact and not a planner-written claim retro-fitted into the verdict. Carry this forward.
- **A failure on a different code path than the one a phase fixed is a deferral candidate, not necessarily a regression.** When post-fix data shows the residual failure is on an architecturally-independent path, document the separation rigorously (cycle counts, correlation analysis, line-number references on both paths) and defer rather than dilute the original fix's verification.

## Key Lessons

1. **Metric semantics are part of the contract, not a footnote.** `suppressions_per_min` is a 60s reset counter at `queue_controller.py:649,668`. Reading it like a rate (mean of N snapshots → "rate per minute") gave a number that was honest under one definition (mean live-counter value) and misleading under another (true 60s window rate). Future watchdogs need named-window counters with cause tags so the field name encodes the semantics. **This is the dominant durable lesson for v1.43+ — items 1 and 2 of the v1.43 backlog are direct consequences.**
2. **Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.** D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. After Plan 201-14 changed the control surface (bounded RED decay + anti-windup), the threshold's basis no longer survived. D-19 was an explicit operator-approved tightening with documented rationale (recorded in `201-16-OPERATOR-APPROVAL-D19.md`); D-14 had no equivalent and shipped on inertia. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default whenever a phase changes the control surface.
3. **Diagnostic seams pay dividends at post-mortem time.** Plan 201-13's zone_trace, max_delay_delta_us snapshot retention, and anti-windup counter exposure were what allowed the post-FAIL post-mortem to separate dwell-hold suppression from RED bounded decay from backlog recovery. Without those fields, the FAIL would have looked like an ambiguous regression. Continue investing in diagnostic seams before control-path changes — the cost is small and the post-mortem leverage is large.

## Cross-Reference

- `201-VERIFICATION.md`: authoritative truth table, closure_route block at top, re_verification field showing 6→8/9 promotions across Plans 201-13/14/15.
- `201-CONTEXT.md` `<deferred>` `### Deferred to v1.43+ via Route B Closure (2026-05-06)`: four ordered v1.43 backlog items.
- `201-15-CANARY-VERDICT.md`, `201-16-OPERATOR-APPROVAL-D19.md`, `201-16-SOAK-VERDICT.md`: operator-readable artifacts.
- `200-RETRO.md` `## Final Closure (2026-05-04)`: Phase 200's Route-A-equivalent closure pattern; structural template for this RETRO.
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md`: operator memory recording the Route B decision and codex second-opinion (`/tmp/codex-201-prompt.md`, `/tmp/codex-201-response.log`, 2026-05-06).
- `.planning/seeds/SEED-002` through `SEED-005`: v1.43 backlog items in priority order.

## Lessons for v1.43

The v1.43 backlog is **four ordered items** captured in `.planning/seeds/SEED-002..SEED-005`. The order is load-bearing — items 1–3 are prerequisites to item 4. Each seed file states its priority rationale.

1. **SEED-002 — UL suppression-counter metric-semantics fix.** Add completed-window UL suppression counts + cause tags (dwell-hold vs backlog-recovery vs other) to `/health`. Additive only — preserve `suppressions_per_min`. **Required prerequisite for items 2–4.** Direct consequence of Lesson #1.
2. **SEED-003 — D-14 successor recalibration.** Replace `<5/60s` with a soak-derived threshold from a clean 24h baseline of the post-201-14 binary, using completed-window counts (item 1) instead of live-counter-snapshot means. **Depends on item 1.** Direct consequence of Lesson #2.
3. **SEED-004 — target-edge churn instrumentation.** Add per-sample `load_rtt - baseline_rtt` distribution capture to soak schema. Current soak has integral and zone trace but not per-sample delta. **Required before any `target_bloat_ms` tune.** Direct consequence of Lesson #3.
4. **SEED-005 — Conservative tuning sweep (gated).** Only after items 1–3 land. Candidates: `dwell_cycles: 5 → 4` and/or modest `upload_target_bloat_ms` bump above 15ms. Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back).

## Open Questions / Nothing-Claimed-But-Not-Shipped

- **D-14 successor threshold value is unknown.** A clean 24h baseline soak of post-201-14 production (no further code change) is needed to derive a soak-calibrated number; this is SEED-003's job and cannot be answered from the existing 20260505T132736Z capture alone (that capture used the live-counter-snapshot framing).
- **Whether dwell-hold suppression is the dominant cause vs a multi-cause aggregate is not yet decomposed.** Codex correlation analysis (suppression vs YELLOW samples = 0.72; vs `max_delay_delta_us` = 0.01) is suggestive but not a clean cause-tag separation. SEED-002's cause-tag work will provide that decomposition.
- **No claim is made that bounded-absolute RED decay is sufficient under all DOCSIS deployments.** The Spectrum production evidence is one deployment over 24h. Other DOCSIS deployments (different upstream provisioning, different CMTS queue depths) may need different `red_decay_step_pct` / `red_decay_delta_max_pct` values; the schema validators fail closed on unsafe combinations but do not prescribe values.
- **VALN-05b ATT cake-primary canary remains cross-milestone deferred.** Tracked at `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`; gated on v1.39 Phase 191 closure. Unrelated to Phase 201's VALN-06 path (different WAN, different control mode) but lives in the same operational neighborhood for v1.43+ scoping.

## Final Closure (2026-05-06)

**Operator decision:** VALN-06's D-19 primary floor-hit gate is **PASSED on production v1.42.1**; the D-14 secondary suppression watchdog is **deferred to v1.43+** as `metric_semantics_and_recalibration`, NOT as a control regression. Phase 201 closes `gaps_found` via operator Route B 2026-05-06 (codex second-opinion at `/tmp/codex-201-prompt.md` and `/tmp/codex-201-response.log` recommended Route B; operator selected).

### Decision rationale

Three findings drove Route B selection:

1. **The phase-goal control behavior shipped.** Recanary `20260505T122513Z` and 24h soak `20260505T132736Z` both report `floor_hit_cycles_total_delta=0` against the original VALN-06 contract. Production binary v1.42.1 survived 24h of saturated DOCSIS upload with anti-windup trigger delta=0 (bounded RED decay alone was sufficient).
2. **The D-14 FAIL is on a different code path than the phase-goal fix.** Codex re-aggregation localized the FAIL to `_apply_dwell_logic` at `queue_controller.py:348` (YELLOW-edge dwell-hold), not `_compute_rate_3state` at `queue_controller.py:361-376` (bounded RED decay, the Plan 201-14 fix). `red_streak>0` in 0.023% of soak samples; YELLOW tails in 1.52%; suppression correlates 0.72 with YELLOW samples and 0.01 with `max_delay_delta_us`. The two paths are architecturally independent.
3. **The D-14 threshold itself is unsound under the post-fix control surface.** `suppressions_per_min` is a 60s reset counter; the 6.47 mean is the mean of live-counter snapshots, not a true 60s rate. The `<5/60s` threshold was inherited from Phase 200 qualitative framing without soak calibration. A clean replacement number does not yet exist; deriving one is SEED-003's job.

### What was not attempted

- **No A5-style controlled reattempt.** The alternative closure path (rerun canary + soak with revised operational parameters) was rejected because the FAIL is metric-semantic and the threshold itself needs replacement before any retry is meaningful.
- **No production binary or YAML change.** Spectrum remains on v1.42.1 post-recanary deploy. The bounded RED decay + anti-windup config is in production and surviving 24h saturation. Rollback path validated by Plan 201-15 two-snapshot strategy.
- **No D-14 threshold relaxation.** Lowering the threshold to fit the observed value would be metric-facing without addressing the root cause (counter-vs-rate semantics + dwell-hold churn distribution). v1.43 work fixes the underlying semantics first.

### VALN-06 routing under Route B

- **Phase-goal closure (D-19 primary):** Achieved on v1.42.1 production; verified by canary + 24h soak.
- **D-14 successor:** Deferred to v1.43+ as four ordered backlog items (SEED-002..SEED-005). Order is load-bearing.
- **Inheritance trail (preserved):** `200-VERIFICATION.md` `closure: deferred-to-phase-201` → `REQUIREMENTS.md` v1.41 traceability VALN-06 row → `201-CONTEXT.md` Inherited Requirements + Deferred to v1.43+ via Route B Closure → `201-RETRO.md` (this file) → SEED-002..SEED-005.

### Lessons reinforced for v1.43

- **Metric semantics are contract.** Field names that imply rate when the field is a counter create false-PASS / false-FAIL ambiguity at threshold time. Future watchdogs need named-window counters with cause tags. SEED-002 is the direct response.
- **Threshold-basis hygiene.** Inherited thresholds need explicit re-justification when the control surface changes materially. The D-19 pattern (operator-approved threshold revision with rationale captured in a distinct pre-soak file) should be the default. SEED-003 is the direct response.
- **Diagnostic seams before control-model changes.** Plan 201-13 → Plan 201-14 → Plan 201-16 worked because the diagnostic surface was in production before the control change. Continue this ordering. SEED-004 is the direct response (per-sample delta is the diagnostic surface needed before SEED-005's tuning sweep).
- **Defer-on-different-code-path is a first-class closure shape.** When post-fix data shows the residual FAIL is on an architecturally-independent path, rigorous separation (line numbers + correlation analysis + completed-window stats) makes deferral defensible. Phase 201 spent post-mortem time on this and Route B is the result; future phases should expect this as a possible closure shape rather than treating any soak FAIL as monolithic.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Retro written: 2026-05-06*
*Status: closed gaps_found via operator Route B; D-19 primary VALN-06 PASS on v1.42.1; D-14 deferred to v1.43+ as SEED-002..SEED-005*
```

Use the exact section ordering and headline phrasings above. Numerical values, file paths, line numbers, and decision IDs are load-bearing — preserve them verbatim. Bullet density and table style should mirror Phase 200 RETRO.
  </action>
  <acceptance_criteria>
    - File `.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` exists
    - `grep -F 'Route B' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - `grep -F 'metric_semantics_and_recalibration' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - `grep -F 'Lessons for v1.43' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - `grep -F 'Final Closure (2026-05-06)' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - `grep -cE 'SEED-00[2-5]' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` is at least 4 (each item referenced at least once)
    - `grep -F 'queue_controller.py:348' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches (dwell-hold path line reference)
    - `grep -F 'queue_controller.py:361' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches (bounded RED decay path line reference)
    - `grep -F 'v1.42.1' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - `grep -F '20260505T132736Z' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` matches
    - File has at least 8 H2 headings (`grep -c '^## ' ... >= 8`) covering Built / Tested / Worked / Inefficient / Patterns / Lessons / Cross-Reference / Lessons-for-v1.43 / Open-Questions / Final-Closure
  </acceptance_criteria>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md && grep -F 'Route B' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md && grep -F 'metric_semantics_and_recalibration' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md && grep -F 'Lessons for v1.43' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md && grep -F 'Final Closure (2026-05-06)' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md && [ "$(grep -cE 'SEED-00[2-5]' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md)" -ge 4 ] && [ "$(grep -c '^## ' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md)" -ge 8 ]</automated>
  </verify>
  <done>201-RETRO.md exists with Phase 200 RETRO structural shape, Route B closure, three durable lessons, four-item v1.43 baton, and Final Closure section.</done>
</task>

<task type="auto">
  <name>Task 5: Add closeout_recorded annotation to 201-VERIFICATION.md re_verification block</name>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md</files>
  <read_first>
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` lines 1-48 (frontmatter; the `re_verification:` block is at lines 8-21)
  </read_first>
  <action>
Add a single annotation field to the existing `re_verification:` frontmatter block. Locate the block:

```yaml
re_verification:
  previous_status: gaps_found
  previous_score: "6/9 frontmatter / 4/9 inline (disagreed; both stale)"
  gaps_closed:
    - ...
  gaps_remaining:
    - ...
  regressions: []
```

After the `regressions: []` line, add (still inside the `re_verification:` block, same indentation level):

```yaml
  closeout_recorded: 2026-05-06
  closeout_artifact: ".planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md"
  closeout_note: "Plan 201-17 closeout completed per operator Route B 2026-05-06; D-19 primary VALN-06 PASS shipped on v1.42.1, D-14 secondary deferred to v1.43+ as SEED-002..SEED-005. See 201-RETRO.md."
```

Do NOT modify:
- The `closure_route` block (lines 7)
- The truth table or Goal Achievement section (refreshed 2026-05-06T14:35:00Z)
- The `gaps:` list, `deferred:` list, or `human_verification:` list
- Anything in the body of the document below the frontmatter

The edit is a single 3-line addition inside the existing `re_verification:` block.
  </action>
  <acceptance_criteria>
    - `grep -F 'closeout_recorded: 2026-05-06' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` matches
    - `grep -F '201-RETRO.md' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` matches in the closeout_artifact line
    - `grep -F 'closure_route:' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` still matches (unchanged closure_route block preserved)
    - The truth table line for Truth 7 still says `FAILED` (no body change)
    - YAML frontmatter still parses (closing `---` still present, `re_verification:` block well-formed)
  </acceptance_criteria>
  <verify>
    <automated>grep -F 'closeout_recorded: 2026-05-06' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md && grep -F 'closure_route:' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md && grep -F 'closeout_artifact:' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md && python3 -c "import yaml; yaml.safe_load(open('.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md').read().split('---')[1])"</automated>
  </verify>
  <done>201-VERIFICATION.md re_verification block carries the Plan 17 closeout annotation; closure_route and truth table unchanged.</done>
</task>

<task type="auto">
  <name>Task 6: Update STATE.md to reflect Phase 201 closeout complete</name>
  <files>.planning/STATE.md</files>
  <read_first>
    - `.planning/STATE.md` lines 1-15 (frontmatter); line 6 is `stopped_at: Phase 201 Plan 16 soak FAIL — awaiting operator next-action decision`
    - `.planning/STATE.md` lines 130-131 (Session Continuity `Stopped at:`)
    - `.planning/STATE.md` lines 254-256 (most recent Decisions entry — already records the Plan 201-16 outcome)
    - `.planning/STATE.md` lines 326-330 (Current Position block)
  </read_first>
  <action>
Five coordinated edits to STATE.md:

**Edit A — frontmatter `stopped_at` (line 6).** Replace:
`stopped_at: Phase 201 Plan 16 soak FAIL — awaiting operator next-action decision`
with:
`stopped_at: Phase 201 closed gaps_found via operator Route B 2026-05-06; D-19 primary VALN-06 PASS shipped on v1.42.1, D-14 deferred to v1.43+ as SEED-002..SEED-005`

**Edit B — frontmatter `last_updated` and `last_activity`.** Update both to `2026-05-06` (or current ISO timestamp for `last_updated`; date-only for `last_activity`). The executor should set `last_updated` to the actual time of the edit (e.g., `"2026-05-06T<HH:MM:SS>.000Z"`), preserving the existing string format.

**Edit C — frontmatter `progress.completed_plans`.** Increment from `14` to `16` (Plans 201-15, 201-16, 201-17 all complete; Plan 201-12 superseded but counted in total). Recompute `percent` = `completed_plans / total_plans * 100` rounded — with `completed_plans=16` and `total_plans=16` this is `100`. (If executor judges that Plan 12 superseded should not be counted, leave `total_plans=16` and bump `completed_plans` to `15`; document the choice in the commit message. Default: `16/16 = 100%`.)

**Edit D — Session Continuity (line 131).** Replace:
`Stopped at: Completed 201-15-recanary-PLAN.md`
with:
`Stopped at: Completed 201-17-closeout-PLAN.md (Phase 201 closed gaps_found via operator Route B 2026-05-06)`

**Edit E — Current Position block (lines 327-330).** Replace the four lines:
```
Phase: 201 (docsis-aware-ul-congestion-control) — EXECUTING
Plan: 16 of 16
Status: Soak FAIL — awaiting operator next-action decision
Last activity: 2026-05-06
```
with:
```
Phase: 201 (docsis-aware-ul-congestion-control) — CLOSED gaps_found
Plan: 17 of 17 (closeout complete)
Status: D-19 primary VALN-06 PASS shipped on v1.42.1; D-14 deferred to v1.43+ as SEED-002..SEED-005; milestone v1.42 ready for `/gsd-complete-milestone`
Last activity: 2026-05-06
```

**Edit F — Add Decisions entry.** Append at the end of the `## Decisions` section (after the line at 256 currently ending "...next action requires operator decision between A5-style reattempt and v1.43+ follow-up."):

`- [Phase 201 closure 2026-05-06]: Operator Route B selected. Phase 201 closes gaps_found; D-19 primary VALN-06 floor-hit gate PASSED on canary 20260505T122513Z and 24h soak 20260505T132736Z (v1.42.1 in production). D-14 secondary suppression watchdog FAIL classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (queue_controller.py:348), unrelated to bounded RED decay (queue_controller.py:361-376). D-14 deferred to v1.43+ as four ordered backlog items: SEED-002 (suppression-counter metric semantics fix), SEED-003 (D-14 successor recalibration), SEED-004 (target-edge churn instrumentation), SEED-005 (conservative tuning sweep, gated). Order is load-bearing — items 1-3 are prerequisites to item 4. No production binary or YAML change in Plan 201-17. Milestone v1.42 ready for /gsd-complete-milestone.`

Do NOT touch other sections (Position, Deferred Items, Parallel Milestone, Accumulated Context, Performance Metrics, Blockers above this entry).

**Update Blockers section (lines 318-323):** The first blocker line currently reads `Phase 201 Plan 201-16 soak failed after the re-canary pass: ...`. Replace this entire blocker bullet with:

`- ~~Phase 201 Plan 201-16 soak failed after the re-canary pass~~ — RESOLVED 2026-05-06 via operator Route B: D-19 primary PASS shipped, D-14 deferred to v1.43+ (SEED-002..SEED-005). See 201-RETRO.md and Decisions entry [Phase 201 closure 2026-05-06]. The remaining VALN-06 partial-closure trail is now in v1.41 traceability under REQUIREMENTS.md.`

Do NOT modify the v1.41 VALN-06 inheritance blocker (line 320), the Phase 191 closure blocker (line 321), the Phase 196 ATT canary blocker (line 322), or the pending follow-up note (line 323) — those are unrelated.
  </action>
  <acceptance_criteria>
    - `grep 'stopped_at:' .planning/STATE.md` does NOT contain `awaiting operator`
    - `grep 'stopped_at:' .planning/STATE.md` contains `gaps_found` and `Route B`
    - `grep -E 'Phase: 201.*CLOSED gaps_found' .planning/STATE.md` matches
    - `grep -F '[Phase 201 closure 2026-05-06]' .planning/STATE.md` matches
    - `grep -cE 'SEED-00[2-5]' .planning/STATE.md` >= 4
    - `grep -F 'last_activity: 2026-05-06' .planning/STATE.md` matches
    - YAML frontmatter still parses
    - Phase 191 closure blocker line still present (not accidentally edited)
  </acceptance_criteria>
  <verify>
    <automated>! grep 'stopped_at:' .planning/STATE.md | grep -q 'awaiting operator' && grep 'stopped_at:' .planning/STATE.md | grep -q 'Route B' && grep -E 'Phase: 201.*CLOSED gaps_found' .planning/STATE.md && grep -F '[Phase 201 closure 2026-05-06]' .planning/STATE.md && [ "$(grep -cE 'SEED-00[2-5]' .planning/STATE.md)" -ge 4 ] && python3 -c "import yaml; yaml.safe_load(open('.planning/STATE.md').read().split('---')[1])"</automated>
  </verify>
  <done>STATE.md frontmatter, Session Continuity, Current Position, Decisions, and Blockers sections all reflect Phase 201 closeout complete via Route B; v1.42 ready for milestone close.</done>
</task>

<task type="auto">
  <name>Task 7: Create four v1.43 backlog seed files in priority order under .planning/seeds/</name>
  <files>.planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md, .planning/seeds/SEED-003-v143-d14-watchdog-recalibration.md, .planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md, .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md</files>
  <read_first>
    - `.planning/seeds/SEED-001-spectrum-topology-correct-cake-mode.md` (existing seed format — frontmatter shape, heading style, "Why This Matters" / "When to Surface" / "Scope Estimate" sections)
    - `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md` (authoritative four-item priority list)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md` `gaps[*].missing` block (the four items in execution-ready phrasing)
    - `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md` (canonical numerical evidence)
  </read_first>
  <action>
Create four seed files mirroring SEED-001's structure (frontmatter with `id`, `status`, `planted`, `planted_during`, `trigger_when`, `scope`; body with `## Why This Matters`, `## When to Surface`, `## Scope Estimate`).

Common frontmatter pattern for all four:
```
---
id: SEED-00X
status: dormant
planted: 2026-05-06
planted_during: Phase 201 closeout (Plan 201-17) per operator Route B
trigger_when: <item-specific — see below>
scope: <item-specific — see below>
priority: <ordinal 1/2/3/4>
prerequisites: [<list of SEED IDs that must land first, or [] for SEED-002>]
priority_rationale: <one-line explanation of order>
---
```

**SEED-002 — UL suppression-counter metric-semantics fix**

- `priority: 1`
- `prerequisites: []`
- `priority_rationale: "Required prerequisite for SEED-003 (recalibration needs completed-window counts), SEED-004 (per-sample delta), and SEED-005 (tuning sweep gates)."`
- `trigger_when: v1.43 milestone planning, OR any time work touches src/wanctl/queue_controller.py:649,668 (suppressions_per_min counter), OR any /health.wans[].upload field addition`
- `scope: Small`

Body content:

```
# SEED-002: UL suppression-counter metric-semantics fix

## Why This Matters

Phase 201 Plan 16 soak FAILED the D-14 secondary watchdog at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` against `<5.0`. Codex re-aggregation of the 84,117-sample NDJSON revealed the FAIL is metric-semantic, not control-side:

- The field `suppressions_per_min` at `src/wanctl/queue_controller.py:649,668` is a **60s reset counter** — it tracks the live count of suppressions in the last 60s window and resets at the boundary. Sampling it produces an instantaneous count, not a rate.
- The published 6.47 mean is the mean of **live-counter snapshots** at sample times, weighted toward partial windows.
- Re-aggregating the same data over **completed 60s windows** gives peak mean ~13.9/min (p95=41, max=124) — a different number against a different definition.
- D-14's `<5/60s` threshold was inherited from Phase 200's qualitative "31/60s degraded → near-zero" framing and was never soak-calibrated against the post-Plan-201-14 control surface. The threshold's basis does not survive the post-fix surface, but a clean replacement number cannot be derived from the existing capture (it would inherit the same semantic ambiguity).

The fix is a `/health` schema addition, not a controller change. Add **completed-window counts** alongside the existing `suppressions_per_min` (additive only — preserve the current field for backward compatibility) plus **cause tags** that decompose suppressions by cause: dwell-hold (`_apply_dwell_logic` at `queue_controller.py:348`), backlog-recovery, and other. This unblocks SEED-003 (recalibration against soak-calibrated completed-window counts), SEED-004 (per-sample delta capture), and SEED-005 (tuning sweep with gates that reference well-defined metrics).

This is the dominant durable lesson from Phase 201 — see `.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` Lesson #1.

## When to Surface

**Trigger:** v1.43 milestone planning, OR any time work touches `src/wanctl/queue_controller.py` lines 649/668 (`suppressions_per_min` counter), OR any `/health.wans[].upload` field addition.

This seed is the **first item** in the v1.43 backlog and is a **prerequisite for SEED-003, SEED-004, SEED-005**. It should be presented during `/gsd-new-milestone` for v1.43 as the lead phase.

## Scope Estimate

**Small** — single-phase, additive `/health` schema work.

1. **Completed-window counter:** add a 60s rolling-window counter that emits values only at window boundaries (not on every sample). Surface as `suppressions_completed_window_count` in `/health.wans[].upload`.
2. **Cause tags:** when incrementing the suppression counter, classify by cause (dwell-hold vs backlog-recovery vs other) and surface counts per cause as additive `/health` fields.
3. **Preserve `suppressions_per_min`** untouched for backward compatibility (Phase 201 verdict files reference it; do not break the existing soak harness's jq paths).
4. Tests: golden-fixture replay confirming completed-window counts match codex re-aggregation values from `soak/20260505T132736Z/soak-capture.ndjson`.
5. SAFE-05 v1.43 baseline counts re-established for new keys.
6. Migration note in CHANGELOG / docs/CONFIGURATION.md (additive `/health` fields require restart for daemon to start emitting; consumers tolerate absence).

No production canary required — this is `/health` schema and counter accounting, not control-path. Standard hot-path regression slice + a fresh observational soak (no controller change) confirm the new fields populate correctly.
```

**SEED-003 — D-14 successor recalibration**

- `priority: 2`
- `prerequisites: [SEED-002]`
- `priority_rationale: "Cannot derive a soak-calibrated threshold without completed-window counts (SEED-002); recalibration depends on the new metric being live in production for a clean baseline soak."`
- `trigger_when: v1.43 milestone planning AFTER SEED-002 lands AND a clean 24h baseline soak of post-201-14 production has run`
- `scope: Small`

Body content:

```
# SEED-003: D-14 successor recalibration

## Why This Matters

Phase 201's D-14 secondary watchdog at `<5/60s` UL hysteresis suppression rate FAILED on the Plan 201-16 24h soak (mean = 6.47, see SEED-002 for why this number is metric-semantically ambiguous). The threshold's basis was Phase 200's qualitative "drop from degraded 31/60s to near-zero" framing — never soak-calibrated against the post-Plan-201-14 control surface.

Once SEED-002 ships completed-window counts + cause tags, run a clean 24h baseline soak of the post-201-14 binary (no further code change) on Spectrum and derive a soak-calibrated D-14 successor threshold from completed-window counts. The number cannot be derived from the existing 20260505T132736Z capture because that capture used the live-counter-snapshot framing.

The D-19 primary floor-hit gate PASSED on the same soak (`floor_hit_cycles_total_delta_soak_window=0`); the phase-goal control behavior is shipping in production v1.42.1. SEED-003 is closure of the metric watchdog only, not a control-path change.

This addresses Lesson #2 of `201-RETRO.md` (threshold-basis hygiene). Use the D-19 pattern: operator-approved threshold revision with rationale captured in a distinct pre-soak file.

## When to Surface

**Trigger:** v1.43 milestone planning, AFTER SEED-002 has shipped completed-window counts to production, AND after a clean 24h baseline soak of post-201-14 production has captured at least one full week of completed-window count distributions.

This seed is the **second item** in the v1.43 backlog. **Prerequisite: SEED-002.**

## Scope Estimate

**Small** — operator-approved threshold revision with documented rationale; no controller change.

1. **Baseline soak:** 24h clean soak of post-Plan-201-14 production with SEED-002's completed-window counts live. Capture distribution of completed-window counts (mean, p50, p95, p99, max) and cause-tag breakdown.
2. **Threshold derivation:** propose D-14-successor threshold based on the distribution (e.g., p99 + margin), with explicit rationale documented in a `D-XX-OPERATOR-APPROVAL-D14-SUCCESSOR.md`-style file mirroring `201-16-OPERATOR-APPROVAL-D19.md`.
3. **Soak harness update:** replace the live-counter-snapshot mean computation in the soak verdict harness with completed-window counts.
4. **Verification:** rerun the 24h soak under the new threshold and verify VALN-06 D-14 successor closes cleanly.
5. **Documentation:** RETRO update for v1.43 referencing the threshold-basis hygiene lesson from Phase 201.

No production binary change. No new YAML keys. Operator-approval pattern is the change.
```

**SEED-004 — target-edge churn instrumentation**

- `priority: 3`
- `prerequisites: [SEED-002]`
- `priority_rationale: "Per-sample load_rtt - baseline_rtt distribution is the diagnostic surface needed before SEED-005's target_bloat_ms tune; SEED-002's metric semantics work establishes the precedent for additive /health and soak-schema fields without breaking existing harness."`
- `trigger_when: v1.43 milestone planning AFTER SEED-002 OR concurrently with SEED-002 if scoped together`
- `scope: Small`

Body content:

```
# SEED-004: target-edge churn instrumentation

## Why This Matters

The Plan 201-16 24h soak captured RTT integral, zone trace, and CAKE max-delay-delta but **NOT** the per-sample `load_rtt - baseline_rtt` delta. This is the dominant signal that drives target-edge YELLOW classification and dwell-hold suppression — without it, the question "is dwell churn driven by load_rtt sitting near `target_delta` or by spikes above `warn_delta`?" cannot be answered from the existing capture.

Codex correlation analysis on the 20260505T132736Z capture localized D-14 FAIL to the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`) with suppression-vs-YELLOW correlation 0.72. That separation is enough to defer D-14 work via Route B but not enough to safely tune `dwell_cycles` or `target_bloat_ms` (SEED-005). A per-sample distribution capture is required first.

This is a soak-schema additive change, not a control-path change. The existing `effective_ul_load_rtt` and `baseline_rtt_ms` are already serialized; SEED-004 adds the **per-sample delta** as a first-class soak field plus a histogram aggregation in soak-summary.json so future plans can read the target-edge distribution directly.

This addresses Lesson #3 of `201-RETRO.md` (diagnostic seams before control-path changes).

## When to Surface

**Trigger:** v1.43 milestone planning. May be scoped concurrently with SEED-002 if both are presented as paired observability work, but SEED-002's metric-semantics work has higher priority for unblocking SEED-003.

This seed is the **third item** in the v1.43 backlog. **Prerequisite: SEED-002 (for additive /health + soak-schema precedent).**

## Scope Estimate

**Small** — additive soak schema field + harness aggregation.

1. **Soak NDJSON schema addition:** emit per-sample `load_rtt_delta_us` (= `effective_ul_load_rtt - baseline_rtt_ms` in microseconds) on every sample.
2. **soak-summary.json aggregation:** histogram (binned) + p50/p95/p99/max of `load_rtt_delta_us` over the soak window, broken down by zone (GREEN/YELLOW/RED) and by cause-tag from SEED-002.
3. **Tests:** golden-fixture replay confirming the new field is populated and aggregated correctly against a known fixture.
4. **Documentation:** soak harness README update; CHANGELOG note.

No production binary change required if the soak-capture script reads existing exposed `/health` fields and computes the delta locally; if `/health` does not currently expose `effective_ul_load_rtt` and `baseline_rtt_ms` together at sample time, a small additive `/health` change unblocks the soak schema (still no controller change).
```

**SEED-005 — Conservative UL tuning sweep (gated)**

- `priority: 4`
- `prerequisites: [SEED-002, SEED-003, SEED-004]`
- `priority_rationale: "Cannot tune target_bloat_ms without per-sample delta distribution (SEED-004), cannot judge tune success without soak-calibrated D-14 successor threshold (SEED-003), cannot define rollback gates without well-defined completed-window suppression counts (SEED-002). All three are hard prerequisites — order is load-bearing."`
- `trigger_when: v1.43+ milestone planning ONLY after SEED-002, SEED-003, SEED-004 have shipped to production`
- `scope: Medium`

Body content:

```
# SEED-005: Conservative UL tuning sweep (gated)

## Why This Matters

Phase 201's Route B closure deferred D-14 work to v1.43 with a load-bearing order: **SEED-005 cannot ship until SEED-002, SEED-003, and SEED-004 land**. Tuning candidates considered during Phase 201 closure discussions:

- `dwell_cycles: 5 → 4` (lower YELLOW-edge dwell hold; reduces dwell-hold suppression at risk of more frequent rate adjustments under shaped chop)
- Modest `upload_target_bloat_ms` bump above the current 15ms (raises the YELLOW threshold; reduces target-edge churn at risk of higher steady-state buffer occupancy)

Both are conservative one-knob changes against the post-Plan-201-14 control surface. Neither is safe to attempt without:

1. **SEED-002's completed-window suppression counts** to define the rollback gate ("completed-window suppression worsens by X% → roll back").
2. **SEED-003's soak-calibrated D-14 successor threshold** to define the success gate (post-tune soak must pass D-14 successor).
3. **SEED-004's per-sample `load_rtt - baseline_rtt` distribution** to predict the tune's effect on target-edge churn before deploying (the same diagnostic surface that drove the SEED-005 candidate selection in the first place).

Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back). Phase 201's two-snapshot rollback strategy and operator-approved gate-tightening pattern (D-19 pre-soak approval) carry forward.

## When to Surface

**Trigger:** v1.43+ milestone planning, ONLY after SEED-002, SEED-003, and SEED-004 have shipped to production AND a clean baseline soak under SEED-003's recalibrated threshold has passed.

This seed is the **fourth and final** item in the v1.43 backlog. **Prerequisites: SEED-002, SEED-003, SEED-004 (all three required).**

## Scope Estimate

**Medium** — production canary + 24h soak + rollback gate; multiple tune candidates may need separate canary cycles.

1. **Tune candidate selection:** pick one knob (not both at once); evaluate against SEED-004's distribution data to predict effect.
2. **Standard canary + 24h soak under SEED-003's recalibrated D-14 successor threshold.**
3. **Rollback gate:** primary = `floor_hit_cycles_total_delta > 0`; secondary = SEED-002 completed-window suppression worsens by margin TBD; tertiary = SEED-004 distribution shifts adversely.
4. **Two-snapshot rollback strategy** (Snapshot A clean, Snapshot B post-deploy) per Phase 201 Plan 201-15 pattern.
5. **Operator-approved gate** captured in distinct pre-soak file per Phase 201 Plan 201-16 D-19 pattern.

If first-knob tune fails or rolls back, the second-knob tune may be attempted in a follow-on cycle. Two failed tune cycles → reconsider whether tuning is the right approach vs another control-model change.

This seed assumes Phase 201's bounded RED decay + anti-windup remain in production unchanged. If those need revision, that's a different control-path phase, not SEED-005.
```

Each file is self-contained — they cross-reference each other but each can be read alone for context.
  </action>
  <acceptance_criteria>
    - All four files exist:
      - `.planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md`
      - `.planning/seeds/SEED-003-v143-d14-watchdog-recalibration.md`
      - `.planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md`
      - `.planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md`
    - Each file has `priority:` field in frontmatter (1, 2, 3, 4 respectively)
    - Each file has `prerequisites:` field with the correct dependency list
    - Each file has `priority_rationale:` field stating why the order matters
    - Each file has `## Why This Matters`, `## When to Surface`, `## Scope Estimate` sections (mirroring SEED-001)
    - SEED-002 references `queue_controller.py:649,668`
    - SEED-003 references SEED-002 as prerequisite
    - SEED-004 references SEED-002 as prerequisite
    - SEED-005 references SEED-002, SEED-003, SEED-004 as prerequisites
    - All four frontmatters parse as valid YAML
  </acceptance_criteria>
  <verify>
    <automated>for f in SEED-002-v143-ul-suppression-metric-semantics.md SEED-003-v143-d14-watchdog-recalibration.md SEED-004-v143-target-edge-churn-instrumentation.md SEED-005-v143-conservative-ul-tuning-sweep.md; do test -f ".planning/seeds/$f" || { echo "MISSING $f"; exit 1; }; done && grep -q 'priority: 1' .planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md && grep -q 'priority: 4' .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md && grep -q 'SEED-002' .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md && grep -q 'queue_controller.py:649,668' .planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md && for f in SEED-002-v143-ul-suppression-metric-semantics.md SEED-003-v143-d14-watchdog-recalibration.md SEED-004-v143-target-edge-churn-instrumentation.md SEED-005-v143-conservative-ul-tuning-sweep.md; do python3 -c "import yaml,sys; yaml.safe_load(open('.planning/seeds/$f').read().split('---')[1])" || { echo "BAD YAML $f"; exit 1; }; done</automated>
  </verify>
  <done>Four v1.43 backlog seed files exist under .planning/seeds/ in priority order, each with priority/prerequisites/priority_rationale frontmatter and SEED-001-style body sections; mutual cross-references intact.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 8: Operator review of closeout artifacts before commit</name>
  <what-built>
    Plan 201-17 closeout: REQUIREMENTS.md VALN-06 row updated, ROADMAP.md Phase 201 entry mirrored to Phase 200 gaps_found pattern, 201-CONTEXT.md Deferred Ideas extended, 201-RETRO.md authored, 201-VERIFICATION.md re_verification block annotated, STATE.md (frontmatter + Session Continuity + Current Position + Decisions + Blockers) updated, four v1.43 backlog seed files created under .planning/seeds/.
    NO production code, configs, tests, or scripts were modified by this plan.
  </what-built>
  <how-to-verify>
1. **Spot-check REQUIREMENTS.md** — `grep -A2 '^| VALN-06' .planning/REQUIREMENTS.md` shows the existing inheritance trail PLUS the new closure language with `gaps_found`, `v1.43`, `metric_semantics_and_recalibration`, and the `20260505T132736Z` evidence reference.
2. **Spot-check ROADMAP.md** — `grep -B1 -A3 'Phase 201.*Closed (gaps_found)' .planning/ROADMAP.md` shows the Phase Summary row matches Phase 200's closure pattern. `grep '201-17-closeout-PLAN.md' .planning/ROADMAP.md` shows the new plan-checklist line.
3. **Read 201-RETRO.md** — confirm structural shape mirrors `200-RETRO.md`: section ordering, table style, bullet density. Confirm Final Closure (2026-05-06) section reads cleanly. Confirm the three durable lessons (metric semantics, threshold hygiene, diagnostic seams) and the four-item Lessons-for-v1.43 list are coherent.
4. **Spot-check STATE.md** — `grep stopped_at .planning/STATE.md` no longer says `awaiting operator`. `grep -A4 'Current Position' .planning/STATE.md` shows `CLOSED gaps_found` and the milestone-ready note.
5. **Read each SEED-002..SEED-005 file** — confirm priority field, prerequisites field, priority_rationale field, and Why/When/Scope sections are present. Confirm SEED-002 calls out the `queue_controller.py:649,668` counter-vs-rate semantics. Confirm SEED-005 lists all three prerequisites.
6. **Confirm no code/config drift:** `git diff --stat` should show ONLY:
   - `.planning/REQUIREMENTS.md`
   - `.planning/ROADMAP.md`
   - `.planning/STATE.md`
   - `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md`
   - `.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md`
   - `.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` (new)
   - `.planning/phases/201-docsis-aware-ul-congestion-control/201-17-closeout-PLAN.md` (new — this plan)
   - `.planning/seeds/SEED-002-*.md` (new)
   - `.planning/seeds/SEED-003-*.md` (new)
   - `.planning/seeds/SEED-004-*.md` (new)
   - `.planning/seeds/SEED-005-*.md` (new)
   No files under `src/wanctl/`, `configs/`, `tests/`, `scripts/`, or `deploy/` should appear. If any do, the plan was misexecuted — flag it.
  </how-to-verify>
  <resume-signal>Type "approved" to allow project-finalizer + commit, or describe issues to fix.</resume-signal>
</task>

</tasks>

<verification>
After all tasks complete, run:

```bash
# Documentation-state coherence checks
grep -E 'VALN-06.*gaps_found.*v1\.43' .planning/REQUIREMENTS.md
grep -E 'Phase 201.*Closed \(gaps_found\)' .planning/ROADMAP.md
grep -F '201-17-closeout-PLAN.md' .planning/ROADMAP.md
grep -F 'closeout_recorded: 2026-05-06' .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md
grep -F 'Final Closure (2026-05-06)' .planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md
! grep 'stopped_at:' .planning/STATE.md | grep -q 'awaiting operator'

# Backlog seeds in priority order
for n in 2 3 4 5; do test -f .planning/seeds/SEED-00${n}-v143-*.md || echo "MISSING SEED-00${n}"; done
grep -q 'priority: 1' .planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md
grep -q 'priority: 4' .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md
grep -q 'prerequisites: \[SEED-002, SEED-003, SEED-004\]' .planning/seeds/SEED-005-v143-conservative-ul-tuning-sweep.md

# YAML frontmatter integrity
for f in .planning/STATE.md .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md .planning/seeds/SEED-002-v143-*.md .planning/seeds/SEED-003-v143-*.md .planning/seeds/SEED-004-v143-*.md .planning/seeds/SEED-005-v143-*.md; do
  python3 -c "import yaml; yaml.safe_load(open('$f').read().split('---')[1])" || echo "BAD YAML: $f"
done

# Negative check: no production code/config touched
git diff --name-only HEAD | grep -E '^(src/|configs/|tests/|scripts/|deploy/|docker/|pyproject\.toml|Makefile)' && echo "FAIL: production files touched" || echo "PASS: no production files touched"
```

All checks must pass. The negative check (`git diff --name-only`) is load-bearing — if any production file appears, the plan was misexecuted.
</verification>

<success_criteria>
- Phase 201 closure state is coherent across REQUIREMENTS.md, ROADMAP.md, STATE.md, 201-CONTEXT.md, and 201-VERIFICATION.md (all five reference Route B, gaps_found, v1.43 deferral, and the canonical evidence files).
- 201-RETRO.md exists and follows Phase 200 RETRO structure with Route B Final Closure section, three durable lessons, and four-item Lessons-for-v1.43 list.
- Four SEED-002..SEED-005 files exist in `.planning/seeds/` with priority/prerequisites/priority_rationale frontmatter and SEED-001-style body.
- STATE.md `stopped_at` no longer contains `awaiting operator`; v1.42 milestone is recorded as ready for `/gsd-complete-milestone`.
- No production code, configs, tests, or scripts changed (`git diff --name-only HEAD` confirms `.planning/` only).
- Operator approves at Task 8 checkpoint before project-finalizer + commit.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-17-SUMMARY.md` capturing:
- Closure shape (Route B, gaps_found, v1.43 baton)
- Files modified (all under `.planning/`)
- Confirmation of zero code/config drift
- Pointer to 201-RETRO.md as the durable closeout artifact
- Pointer to SEED-002..SEED-005 as the v1.43 seed set
</output>

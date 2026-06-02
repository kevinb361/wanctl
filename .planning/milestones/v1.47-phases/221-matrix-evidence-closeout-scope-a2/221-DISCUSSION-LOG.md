# Phase 221: Matrix Evidence + Closeout (Scope A2) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 221-matrix-evidence-closeout-scope-a2
**Areas discussed:** Operator orchestration & early termination, CLOSEOUT.md report schema, Aborted/failed cell recovery + base_sha drift, Todo closure & close-with-prejudice protocol
**Mode:** auto-decide (operator said "you decide all of the things" after gray-area selection)

---

## Operator orchestration & early termination

| Option | Description | Selected |
|--------|-------------|----------|
| Always run all 54 (no early stop) | Run every cell × replicate even if kill/defect tripped. Maximum corroboration, defensible against cherry-picked stop. ~3 days operator load. | ✓ |
| Stop only on kill verdict | Asymmetric stop: kill short-circuits, defect stays full-matrix. | |
| Stop on kill OR defect with corroboration | Fastest path to closeout; risks data-driven stop semantics. | |
| Run all 18 cells, replicate-count short-cut | Always run all cells but stop at 2/3 replicates if both agree. | |

**User's choice:** auto-decide → "Always run all 54"
**Notes:** Pitfall 2 (data-driven threshold leakage) and v1.47's read-only/defensibility posture forbid any operator-discretion stop path. Per-axis rollup requires the complete grid. Captured as D-01 / D-02 / D-03 in CONTEXT.md.

---

## CLOSEOUT.md report schema

No multi-option AskUserQuestion was presented for this area (auto-decide invoked before further question turns). Decisions captured:

**Selections (auto-decided):**
- Two separate tables — canonical control rows live in their own section before supplemental rows (AGGREGATE-02 visual enforcement).
- Per-cell row columns: cell_id, target_kind, target_name, path, window, replicate_count, run_timestamps_utc, p50/p95/p99, primary_driver, ranked_drivers_top3 (`name(weight)`), mtr_pre_ref, mtr_post_flag, base_sha, cell_verdict.
- Separate "Per-Axis Rollup" section with three sub-tables (per-target, per-path, per-window), aggregation rule cited inline.
- Matrix-level verdict section appears last with explicit decision-tree trace; cites Phase 220 YAML `base_sha`.
- Six-driver classifier output: top-3 ranked with weights, primary_driver column = rank-1.
- mtr snapshot cited by relative path; no inline mtr dumps in the report body.

Captured as D-04 through D-07 in CONTEXT.md.

---

## Aborted/failed cell recovery + base_sha drift

No multi-option AskUserQuestion was presented (auto-decide invoked). Decisions captured:

**Selections (auto-decided):**
- Re-run failed replicate up to 3 attempts per replicate index; cell marked `INCOMPLETE` if 3 attempts fail.
- Matrix INVALID and Phase 221 reopens if `>2 supplemental cells INCOMPLETE` OR `any canonical control cell INCOMPLETE in any window`.
- Matrix VALID with footnote if `≤2 supplemental cells INCOMPLETE` — closeout cites which and why.
- BGP-change per replicate: `mtr-post-<N>.txt` written; replicate row sets `mtr_post_flag: true`; cell verdict computed normally but excluded from defect-corroboration if both flagged AND `cell_defect` (path attribution ambiguous).
- base_sha frozen for matrix duration by default; non-controller-path edits unaffected (D-14 differential).
- base_sha re-pin protocol (exceptional path): operator pauses matrix, updates YAML on new branch, closeout records SHA boundary, each cell row carries its `base_sha` value, pre-cutover cells with non-empty forbidden-path diff vs new SHA are recomputed.

Captured as D-08 through D-12 in CONTEXT.md.

---

## Todo closure & close-with-prejudice protocol

No multi-option AskUserQuestion was presented (auto-decide invoked). Decisions captured:

**Selections (auto-decided):**
- Always move `pending/` → `closed/` on ANY verdict (including carry verdict — close-with-prejudice is operationally a close).
- Frontmatter on move: `closed_by_phase: 221`, `verdict: {one_of_three}`, `close_with_prejudice: true|false` (true only when verdict = carried_narrower_*).
- Closure stanza appended as `## Phase 221 Closeout` section to the todo body — existing investigation log preserved. Stanza contains: verdict summary, CLOSEOUT.md citation, matrix base_sha + Phase 220 YAML SHA, and on carry verdict the CRITERIA-02 close-with-prejudice rule **verbatim from REQUIREMENTS.md** (no paraphrase — REQ-traceability is exact).
- CLOSEOUT.md cites the todo-move commit SHA for reverse traceability.
- "Narrower" on carry verdict means the close-with-prejudice rule itself — no further scope narrowing (no "carried, but only daytime"). Avoids re-creating the "carried-narrower forever" anti-pattern.

Captured as D-13 through D-17 in CONTEXT.md.

---

## Claude's Discretion

- Exact ledger schema for `221-EVIDENCE-LEDGER.md` — clean extension of closeout table; documented inline.
- Closeout report markdown style — match Phase 217 / Phase 214 cadence.
- Per-axis rollup table formatting (compact vs expanded).
- Decision-tree trace formatting — bulleted "branch matched / branch failed" markers.
- Whether to emit `221-CLOSEOUT.json` companion (D-17 envelope) — recommended IF aggregator already produces structured cube output.
- Aggregator invocation timing — recommended ONCE at end-of-matrix; intermediate runs allowed in evidence dir for audit but NOT in closeout report.

## Deferred Ideas

(See CONTEXT.md `<deferred>` for full list.)

- v1.48+ tuning work sourced from matrix verdict
- Aggregator heat-map / sparkline visualization
- Multi-protocol matrix (UDP_FLOOD, tcp_1up, RRUL)
- Auto-rotating supplemental target pool
- DSCP marking probe
- Cube projection to additional axes
- mtr path-change auto-replan
- ML/prediction for next-best-target

## Folded Todos

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` (score 0.9, tuning) — primary CLOSEOUT-03 target.

## Reviewed Todos (not folded)

- `2026-04-17-ingestion-rate-tool` — closed by Phase 219
- `2026-04-17-investigate-steering-degraded-on-clean-restart` — out of scope, STEER-DRIFT-01 family
- `2026-04-17-operator-summary-digest-permission-handling` — tooling-hygiene, unrelated
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` — Phase 218 watch-list
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196` — gated on Phase 191
- `2026-04-28-add-silicom-bypass-nic-operational-tooling`, `2026-04-28-add-silicom-bypass-test-harness` — SEED-006 dormant

# Phase 221: Matrix Evidence + Closeout (Scope A2) — Context

**Gathered:** 2026-06-01
**Status:** Ready for planning
**Source:** /gsd:discuss-phase (4 gray areas resolved; 1 folded todo; auto-decide mode per operator)

<domain>
## Phase Boundary

Execute the 18-cell × 3-replicate target/path/window matrix landed by Phase 220, then write `221-CLOSEOUT.md` applying the LOCKED CRITERIA-01 thresholds and verdict roll-up algorithm verbatim. Close-or-carry the folded `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` todo with the CRITERIA-02 close-with-prejudice rule attached on a carry verdict.

**In scope:**
- Operator-driven execution of all 54 evidence runs (18 cells × 3 replicates) via `scripts/phase220-target-path-matrix.sh`, spread across multiple calendar days.
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` — running per-cell status ledger updated by Claude across operator sessions.
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` — final report: per-cell verdict table (canonical + supplemental), per-axis rollup, matrix-level verdict, decision-tree trace, threshold-citation backreference to Phase 220 YAML SHA.
- Phase 221 aggregator invocation (`scripts/phase220-matrix-aggregator.py`) producing the cube snapshot consumed by the closeout report.
- Folded-todo file move `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` → `.planning/todos/closed/...` with closure stanza + verdict + close-with-prejudice rule (verbatim from REQUIREMENTS.md CRITERIA-02) on carry verdict.
- Phase 221 SAFE-11 mutation-boundary pytest at milestone-close boundary.

**Out of scope (deferred):**
- Edits to thresholds, verdict algorithm, replicate count, cell list, classifier, harness — all locked by Phase 220 commit (Pitfall 2: data-driven threshold leakage).
- Controller/algorithm/CAKE/steering changes — v1.47 read-only milestone.
- Tuning recommendations sourced from matrix verdict — v1.48+ work, NEVER inside `221-CLOSEOUT.md`.
- Multi-protocol matrix (UDP_FLOOD, tcp_1up, RRUL) — anti-feature per REQUIREMENTS.md.
- Auto-rotating supplemental targets / ML / DSCP marking — anti-features per REQUIREMENTS.md.

</domain>

<decisions>
## Implementation Decisions

### Operator Orchestration & Pacing

- **D-01: Always run all 54 — no early termination.** Even if kill OR defect criteria already trip mid-matrix, every (target, path, window, replicate) run completes. Rationale: Pitfall 2 (data-driven leakage) forbids any operator-discretion stop path that could selectively over-sample favorable evidence. Per-axis rollup REQUIRES complete grid. Defensibility of the close-with-prejudice rule depends on the matrix being run-to-completion.
- **D-02: Calendar spread is operator-driven within window-hour gates.** Off-peak (01–05), daytime (10–16), prime-time (19–22) gates from Phase 220 YAML are enforced by the wrapper; operator chooses which qualifying calendar day each window-slot fires on. Multiple cells inside the same window-slot on the same day are permitted (Phase 220 60s inter-cell spacing already covers this).
- **D-03: Multi-session resume via running evidence ledger.** Operator triggers cell runs out-of-session via `./scripts/phase220-target-path-matrix.sh --cell <cell_id> --replicate <N>`. Each Claude session reads `evidence/`, updates `221-EVIDENCE-LEDGER.md` (per-cell status: `pending|partial|complete|incomplete`, replicate timestamps, mtr-pre/post hash, base_sha), commits, exits. No matrix-level verdict computed until ledger shows 54/54 complete (or matrix-fail conditions in D-08).

### CLOSEOUT.md Report Schema

- **D-04: Two separate per-cell tables.** Canonical control (Phase 214 `dallas`) rows are presented in a dedicated "Table 1: Canonical Control" section BEFORE supplemental cells. Supplemental targets (`vultr_dallas`, `vultr_chicago`) live in "Table 2: Supplemental Cells". Enforces the AGGREGATE-02 / canonical-separation invariant visually and prevents accidental cross-pooling.
- **D-05: Per-cell row columns** (both tables, identical schema):
  - `cell_id` (e.g., `dallas__spectrum__daytime`)
  - `target_kind` (`canonical` | `supplemental`)
  - `target_name`, `path` (Spectrum | ATT), `window` (off-peak | daytime | prime-time)
  - `replicate_count` (e.g., `3/3` or `2/3 (incomplete)`)
  - `run_timestamps_utc` (comma-separated ISO 8601, one per replicate)
  - `p50_ms`, `p95_ms`, `p99_ms` — replicate-median per Phase 220 D-05
  - `primary_driver` — rank-1 classifier output
  - `ranked_drivers_top3` — top-3 driver names with weights, format `name(weight)`
  - `mtr_pre_ref` — relative path to `mtr-pre-<replicate>.txt` in evidence dir
  - `mtr_post_flag` — boolean, true iff BGP-change post-flight mtr captured (Pitfall 4)
  - `base_sha` — short SHA used for this cell's D-14 source-floor anchor
  - `cell_verdict` — `cell_defect` | `cell_kill_clear` | `cell_carry` per Phase 220 D-04 roll-up step 1
- **D-06: Per-axis rollup section** appears after the two tables — three sub-tables (per-target, per-path, per-window), each showing axis value + axis-level rollup verdict per Phase 220 D-04 step 2. Aggregation rule cited inline: `any cell_defect wins → any cell_carry wins → else cell_kill_clear`.
- **D-07: Matrix-level verdict section** appears last with explicit decision-tree trace per Phase 220 D-04 step 3. Each branch decision shows the evidence that triggered (or failed to trigger) it. The final verdict is one of `{defect_located, hypothesis_killed, carried_narrower_with_close_with_prejudice_rule}` — NO other value permitted. Cites Phase 220 YAML SHA (`base_sha` field from `scripts/phase220-matrix.yaml`) verifying thresholds applied unchanged.

### Failed-Cell Recovery & base_sha Drift

- **D-08: Failed replicate re-run policy.** If a replicate fails (D-14 drift, source-bind verify fail, flent error, journal pull error, BGP-mid-replicate), the wrapper invocation is RE-RUN for that replicate against the same cell. Up to 3 total attempts per replicate index. After 3 failed attempts on the same replicate, the cell is marked `INCOMPLETE` in the ledger with failure-reason citation. No partial-replicate evidence enters the closeout table.
- **D-09: Matrix-fail criteria.**
  - Matrix is INVALID and Phase 221 reopens for re-plan if: `>2 supplemental cells INCOMPLETE` OR `any canonical control cell INCOMPLETE in any window`. Canonical is foundational — without it, MWU and 1.5× control-comparison are undefined.
  - Matrix is VALID with footnote if: `≤2 supplemental cells INCOMPLETE`. Closeout report cites which cells were skipped and why; per-axis rollup excludes those cells; matrix-level verdict notes degraded supplemental coverage.
- **D-10: BGP-change handling per replicate.** If `mtr-pre` for a replicate differs from the previous cell's `mtr-post` for the same target, the wrapper writes `mtr-post-<replicate>.txt` after the replicate (Pitfall 4 mitigation, already in Phase 220 wrapper). The replicate's row in the closeout table sets `mtr_post_flag: true`. Cell verdict is computed normally — BGP change does NOT auto-invalidate the replicate; it carries a flag for closeout-report audit. If `mtr_post_flag: true` AND `cell_defect`, the matrix-level decision-tree explicitly excludes that cell from defect-corroboration arguments (path attribution ambiguous).
- **D-11: base_sha frozen for matrix duration (default).** The `base_sha` field in `scripts/phase220-matrix.yaml` is the source-floor anchor for ALL 54 runs by default. Non-controller-path edits (scripts/, docs/, tests/) during the matrix are unaffected — D-14 checks differential against base_sha for forbidden paths only.
- **D-12: base_sha re-pin protocol (exceptional path).** If a controller-path hotfix MUST merge mid-matrix (e.g., production incident requiring `wan_controller.py` change), the operator pauses the matrix, updates `phase220-matrix.yaml` `base_sha` field on a new branch, and the closeout report records the SHA boundary explicitly. Each cell row carries its `base_sha` value; cells run under different SHAs are footnoted. Pre-cutover cells whose forbidden-path diff against the NEW base_sha is non-empty are recomputed against the new SHA. In practice, since the controller-path is forbidden anyway, this should be a no-op for any legitimate non-controller hotfix.

### Todo Closure Protocol (CLOSEOUT-03)

- **D-13: Always move pending → closed on any verdict.** The folded todo file moves `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` → `.planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` for every verdict in `{defect_located, hypothesis_killed, carried_narrower_with_close_with_prejudice_rule}`. Rationale: "carried-narrower" with close-with-prejudice is operationally a close (the rule forbids reopen without independent new evidence); leaving it in `pending/` would invite future-Claude re-litigation.
- **D-14: Todo frontmatter on move.** Append three YAML frontmatter fields:
  ```yaml
  closed_by_phase: 221
  verdict: defect_located | hypothesis_killed | carried_narrower_with_close_with_prejudice_rule
  close_with_prejudice: true | false   # true ONLY when verdict = carried_narrower_*
  ```
- **D-15: Closure stanza appended to todo body.** A new `## Phase 221 Closeout` section is appended (NOT replacing existing content — historical investigation log preserved). Stanza contains:
  - Verdict + summary line.
  - Citation: `See .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` (relative repo path).
  - Matrix base_sha + Phase 220 YAML SHA.
  - On `carried_narrower_with_close_with_prejudice_rule`: the CRITERIA-02 rule **verbatim from REQUIREMENTS.md** (no paraphrase — REQ-traceability is exact).
- **D-16: CLOSEOUT.md cites the todo-move commit.** The `221-CLOSEOUT.md` "Todo Disposition" section records the git commit SHA that moved the todo file. Reverse traceability: from closeout report → commit → todo file diff → exact closure stanza.
- **D-17: "Narrower" definition on carry verdict.** On `carried_narrower_with_close_with_prejudice_rule`, "narrower" means **the close-with-prejudice rule itself** — no further scope narrowing (no "carried, but only daytime", no "carried, but only Spectrum"). The rule IS the narrowing. This avoids re-creating the exact "carried-narrower forever" anti-pattern that CRITERIA-02 was designed to close (STATE.md cross-cutting invariants).

### Claude's Discretion

- Exact ledger schema (`221-EVIDENCE-LEDGER.md` table columns) — pick a clean extension of the closeout table schema; document inline.
- Closeout report markdown style — match v1.46 / v1.47 report cadence (Phase 217 baseline / Phase 214 matrix summary as style anchors).
- Per-axis rollup table formatting (compact vs expanded) — pick what reads cleanly for an external auditor.
- Decision-tree trace formatting — bulleted with explicit "branch matched / branch failed" markers; readable as a checklist.
- Whether to emit a `221-CLOSEOUT.json` machine-readable companion (Phase 219 D-17 schema_version envelope convention) — recommended IF aggregator already produces structured cube output; skip otherwise to avoid duplication.
- Aggregator invocation timing within Phase 221 — recommended: run aggregator ONCE at end-of-matrix when ledger reaches 54/54 (or matrix-fail trigger); intermediate aggregator runs MAY appear in evidence dir for audit but MUST NOT appear in closeout report (data-driven-stop avoidance per D-01).

### Folded Todos

- **`2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl`** (score 0.9, tuning) — primary CLOSEOUT-03 target. Already folded into the Phase 220/221 evidence design (the matrix exists to confirm-or-kill this todo). Phase 221 executes the close-or-carry per D-13 through D-17.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 221 source-of-truth (REQ + roadmap)
- `.planning/REQUIREMENTS.md` — CLOSEOUT-01, CLOSEOUT-02, CLOSEOUT-03, SAFE-11; CRITERIA-01 (locked thresholds applied unchanged); CRITERIA-02 (close-with-prejudice rule, cited verbatim on carry verdict per D-15)
- `.planning/ROADMAP.md` §Phase 221 — Success Criteria #1–5
- `.planning/STATE.md` §Cross-Cutting Invariants — v1.47 read-only posture, stdlib-only mandate, pre-registered kill/defect rule, canonical control mandate, mutation-boundary expanded allowlist

### Phase 220 lock (thresholds + algorithm + harness — ALL applied unchanged)
- `.planning/phases/220-matrix-runner-scope-a1/220-CONTEXT.md` — CRITERIA-01 kill/defect/carry verdict text; verdict roll-up algorithm (three-step, per-cell → per-axis → matrix-level); canonical separation rule; replicate count (N=3) + flent duration (30s) + inter-cell spacing (60s); MWU + bootstrap CI sample basis
- `.planning/phases/220-matrix-runner-scope-a1/220-VERIFICATION.md` — Phase 220 close evidence; harness rehearsal cell match against Phase 214 anchor
- `scripts/phase220-matrix.yaml` — 18-cell list, window-hour gates, locked CRITERIA-01 thresholds, `base_sha` source-floor anchor (cited per-cell in closeout table per D-05)
- `scripts/phase220-target-path-matrix.sh` — per-cell wrapper invoked by operator; composes Phase 213/214 chain unchanged
- `scripts/phase220-matrix-aggregator.py` — cube rollup (per-target × per-path × per-window) with MWU + bootstrap CI; produces aggregator JSON consumed by closeout report
- `docs/PHASE220-MATRIX-RUNNER.md` — operator-facing wrapper invocation guide

### v1.47 research (pitfall mitigation)
- `.planning/research/PITFALLS.md` — Pitfall 2 (data-driven threshold leakage → no early termination, no threshold edit after first run; basis for D-01), Pitfall 4 (BGP path change → mtr-post handling per D-10), Pitfall 8 (mutation boundary → SAFE-11 at Phase 221 close), Pitfall 12 (`/health` is never quality)
- `.planning/research/SUMMARY.md` — confirm-or-kill posture; rationale for matrix-driven closure

### Phase 214 anchor (canonical control identity + classifier definition)
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/` — canonical `dallas` reflector identity, six-driver classifier definition (`reflector_loss | loss | jitter | queue_delay | host_kernel | signal_none`), sidecar manifest schema, Phase 214 daytime anchor for canonical control reproduction check
- `scripts/phase214-classify.py` — six-driver classifier (unchanged; output appears in closeout per D-05)

### Phase 213 harness (composed unchanged via Phase 220 wrapper)
- `scripts/phase213-baseline-capture.sh` — source-bind + egress IP verification, flent invocation, health polling, alert pulls, steering snapshots

### Folded todo
- `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — primary target; moves to `closed/` on any Phase 221 verdict per D-13

### Phase 219 envelope convention (if JSON companion emitted)
- `.planning/phases/219-ingestion-rate-observability-scope-d/` — D-17 `schema_version: 1` JSON envelope convention; reuse iff `221-CLOSEOUT.json` companion is produced

### Phase 217 anchor (cycle-budget posture; not changed)
- `.planning/milestones/v1.46-phases/217-production-cycle-budget-baseline/` — controller cycle budget unchanged; Phase 221 makes no controller deploys

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase220-target-path-matrix.sh` — invoked by operator per replicate; writes evidence under `.planning/phases/220-matrix-runner-scope-a1/evidence/{cell}__{wan}__{window}__r{N}/`. Phase 221 reads from this path; does NOT modify the wrapper.
- `scripts/phase220-matrix-aggregator.py` — cube aggregator producing per-axis rollup; called once at end-of-matrix per D-07 (Claude's Discretion on timing). Output JSON feeds CLOSEOUT report tables.
- `scripts/phase220-matrix.yaml` — `base_sha` field cited per-cell in the closeout table (D-05). Phase 221 does NOT edit this YAML.
- Phase 214 / 219 / 220 mutation-boundary pytest clones — pattern reused for `tests/test_phase221_mutation_boundary.py` at milestone-close boundary.
- `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/` — rehearsal cell layout reference. Per-replicate directories carry `signal-sheet.json`, `phase220-cell.json`, `mtr-pre-<N>.txt`, `REHEARSAL-VERDICT.md`.

### Established Patterns
- **Wrapper Composition Pattern** (Phase 220 MATRIX-02): NOT extended by Phase 221 — all 54 runs use the existing wrapper unchanged.
- **Sidecar manifest convention** (Phase 214): per-cell `signal-sheet.json` carries verdict + ranked drivers + p50/p95/p99 — exact source for closeout table rows (D-05).
- **Stdlib-only statistics** (Phase 214 D-10): MWU + bootstrap CI in aggregator already implemented in Phase 220 — Phase 221 does NOT add stats code.
- **D-17 JSON envelope** (Phase 219): `{"schema_version": 1, ...}` for the optional `221-CLOSEOUT.json` companion.
- **Mutation-boundary pytest** (Phase 214/219/220): clone pattern; Phase 221 allowlist is `.planning/phases/221-.../`, `.planning/todos/closed/`, and the `221-CLOSEOUT.md`/`221-EVIDENCE-LEDGER.md` files. Controller-path forbidden list unchanged.

### Integration Points
- Closeout report consumes per-cell `signal-sheet.json` (Phase 214 schema) + aggregator output JSON (Phase 220 schema) — both consumed read-only.
- Todo move (D-13) is a `git mv` from `.planning/todos/pending/` to `.planning/todos/closed/` plus body append (D-15). Commit message cites the verdict.
- `221-CLOSEOUT.md` cites the todo-move commit SHA (D-16) — natural ordering: aggregator → CLOSEOUT.md → todo move + closure stanza commit → CLOSEOUT.md amended with the commit SHA, OR closeout report and todo move in the same commit.
- SAFE-11 pytest at Phase 221 close validates: no `src/wanctl/` controller-path diff vs Phase 220 base_sha; `scripts/`/`docs/`/`tests/` diffs within allowlist; `docs/` carries no threshold-tuning language and no future-tuning predictions.

</code_context>

<specifics>
## Specific Ideas

- The 2026-04-15 `02:45 CDT` historical p99 = 3059ms run from the folded todo is the worst-case the matrix is confirming-or-killing. Closeout's narrative should reference whether any Phase 221 cell reproduced p99 > 1000ms (the folded todo's "fail candidate" gate from line 159), independently of the formal CRITERIA-01 thresholds. This is reportage, not a verdict — the formal verdict still flows through CRITERIA-01 alone.
- Closeout report should call out the asymmetry that Phase 214 daytime and prime-time anchors already showed p99 in {606ms, 560ms} on canonical `dallas` — those numbers ARE inside the defect band (>500ms) but classified `ambiguous` by Phase 214 driver attribution. Phase 221 with corroboration rule decides whether the matrix promotes them to `defect_located` or rules them out via control-vs-supplemental relative gating.
- `random.Random(220)` bootstrap seed convention from Phase 220 D-10 carries forward in aggregator runs — no reseed for Phase 221 to avoid spurious bootstrap drift relative to Phase 220's pinned tests.

</specifics>

<deferred>
## Deferred Ideas

- v1.48+ tuning work sourced from matrix verdict — explicitly forbidden in v1.47 closeout text; belongs to a future tuning milestone with its own scoping.
- Aggregator heat-map / sparkline visualization — out of scope; markdown report only.
- Multi-protocol matrix (UDP_FLOOD, tcp_1up, RRUL) — anti-feature per REQUIREMENTS.md.
- Auto-rotating supplemental target pool — anti-feature per REQUIREMENTS.md.
- DSCP marking probe — anti-feature per REQUIREMENTS.md.
- Cube projection to additional axes (weekday, weather, RouterOS uptime) — out of scope for confirm-or-kill.
- `mtr` path-change auto-replan — D-10 fails closed and flags; auto-replan adds operational opacity.
- ML/prediction for next-best-target — anti-feature per REQUIREMENTS.md.

### Reviewed Todos (not folded)
- `2026-04-17-ingestion-rate-tool` (score 0.9, tooling) — CLOSED by Phase 219; auto-surfaced by matcher.
- `2026-04-17-investigate-steering-degraded-on-clean-restart` (score 0.9, steering) — out of scope for v1.47 read-only milestone; STEER-DRIFT-01 family, pending operator approval for v1.48+ scoping.
- `2026-04-17-operator-summary-digest-permission-handling` (score 0.9, tooling) — tooling-hygiene, unrelated to matrix/closeout.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` (score 0.6, alerting) — Phase 218 watch-list, parallel to v1.47.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196` (score 0.6, validation) — gated on Phase 191 closure; unrelated.
- `2026-04-28-add-silicom-bypass-nic-operational-tooling`, `2026-04-28-add-silicom-bypass-test-harness` (both 0.6, SEED-006 dormant) — out of scope for v1.47.

</deferred>

---

*Phase: 221-matrix-evidence-closeout-scope-a2*
*Context gathered: 2026-06-01 via /gsd:discuss-phase (auto-decide on all gray areas)*
*CRITERIA-01 thresholds + verdict roll-up + replicate count + cell list LOCKED at Phase 220 — Phase 221 applies them unchanged*

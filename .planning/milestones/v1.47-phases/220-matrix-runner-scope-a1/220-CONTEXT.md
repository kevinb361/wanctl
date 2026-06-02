# Phase 220: Matrix Runner (Scope A1) — Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Source:** /gsd:discuss-phase (4 gray areas resolved + 1 folded todo)

<domain>
## Phase Boundary

Land the target/path/window matrix runner with **pre-registered decision criteria** and a verified harness so Phase 221 evidence collection runs against immutable rules. Composes existing Phase 213 `phase213-baseline-capture.sh` and Phase 214 analyzer chain (extractor + aligner + six-driver classifier) UNCHANGED. Forks Phase 214 matrix-summary into a (target × path × window) cube aggregator with Mann-Whitney U + bootstrap 95% percentile CI.

**In scope:**
- `scripts/phase220-matrix.yaml` — canonical cell list + pre-registered CRITERIA-01 thresholds + `base_sha` field anchoring multi-day runs
- `scripts/phase220-target-path-matrix.sh` — per-cell wrapper carrying the Phase 214 Wrapper Composition Pattern verbatim
- `scripts/phase220-matrix-aggregator.py` — stdlib-only fork of `phase214-matrix-summary.py` extended to (target × path × window) cube rollup with MWU + bootstrap CI
- Wave 0 unit tests: pinned `.flent.gz` fixtures (reuse Phase 214) + new synthetic per-cell fixtures (matrix-aggregator surface) + golden MWU p-values + bootstrap CI bounds with seeded `random.Random(220)`, B=2000
- One wet daytime control cell rehearsal (Spectrum + canonical `dallas`) reproducing the Phase 214 anchor verdict before any supplemental cell runs
- Mutation-boundary pytest extending SAFE-11 to the Phase 220 allowlist
- `tests/fixtures/phase220/` (observed-evidence shape only)

**Out of scope (deferred):**
- Live supplemental cell execution — operator-driven, belongs to Phase 221
- Closeout decision report — Phase 221 (CLOSEOUT-01..03)
- Controller threshold/algorithm/CAKE/steering changes — v1.47 read-only milestone
- DSCP marking probe, auto-rotating target pool, ML/prediction — anti-features (REQUIREMENTS.md)
- New third-party Python deps (SciPy/NumPy/pandas) — stdlib-only mandate from Phase 214 D-10
- Edits to existing Phase 213/214 scripts (MATRIX-02 "zero edits")

</domain>

<decisions>
## Implementation Decisions

### Pre-Registered CRITERIA-01 Thresholds — LOCKED at Phase 220 plan time; NEVER edited after first live cell run

**Kill criteria (verdict `hypothesis_killed`):**
> Canonical control cell p99 ≤ 200ms on ≥ 2/3 windows AND zero supplemental cell exceeds 1.5× control p99 across all windows.

**Defect criteria (verdict `defect_located`):**
> ≥ 1 supplemental cell p99 > 500ms reproduced across ≥ 2 windows with corroborating driver in `{reflector_loss, loss, queue_delay}`.

**Carry-forward criteria (verdict `carried_narrower_with_close_with_prejudice_rule`):**
> Neither kill nor defect criteria met. Triggers CRITERIA-02 close-with-prejudice rule.

**Why this exact wording:**
- Matches the REQUIREMENTS.md CRITERIA-01 example verbatim — no judgment leakage from Phase 214's already-seen 606/560ms anchor.
- Both thresholds quantitative + time-bound + comparable across the three time-of-day windows per CRITERIA-01.
- Defect-corroborating-driver allowlist excludes `jitter`, `host_kernel`, and `signal_none` because those drivers cannot attribute defect to controller/path: `jitter` is reflector clock noise, `host_kernel` is local capture noise, `signal_none` is by definition uncorroborated.
- `reflector_loss` stays in the defect-driver allowlist because cross-axis corroboration (see verdict roll-up algorithm below) still discriminates reflector-side-only loss from path-side loss.

### Per-Window p99 Measurement

- **Per-cell, per-window p99** = **median of replicate-level p99s** across N replicates in that (cell, window). Used for kill/defect threshold comparison.
- **MWU + bootstrap CI sample basis** = pooled per-second flent latency samples across replicates within a cell. Approx n=90 per cell pair (3 replicates × 30s flent → 90 per-second samples per cell).
- Replicate-level p99 median is robust to single-replicate outliers — a single bad replicate cannot fire `defect_located`; persistent tail across replicates can.

### Replicate Count + Matrix Budget (operator load anchor for Phase 221)

- **N = 3 replicates** per (cell, window).
- **Flent duration = 30s** per replicate — matches Phase 214 anchor exactly (PHASE214_FLENT_DURATION default).
- **Inter-cell spacing = 60s** minimum between cell starts within a window slot.
- **Matrix size:** 3 targets × 2 paths × 3 windows = 18 cells.
- **Total runs:** 18 cells × 3 replicates = 54 evidence runs.
- **Per-window slot load:** 3 targets × 2 paths × 3 replicates = 18 runs ≈ 27 minutes of active runtime (fits the off-peak 01–05 / daytime 10–16 / prime-time 19–22 hour gates with room for hour-of-day buffer and inter-cell spacing).

### Matrix Verdict Roll-Up Algorithm — pre-registered per CLOSEOUT-01 orthogonal-corroboration rule

Three-step roll-up:

1. **Per-cell verdict**: classify each (target, path, window) cell against thresholds:
   - `cell_defect` if median replicate p99 > 500ms AND classifier primary driver ∈ {reflector_loss, loss, queue_delay}
   - `cell_kill_clear` if median replicate p99 ≤ 200ms (for canonical control cells) OR median ≤ 1.5× same-window control p99 (for supplemental cells)
   - `cell_carry` otherwise

2. **Per-axis rollup** (three independent views, NEVER pooled with each other):
   - Per-target: aggregate that target's cells across paths × windows
   - Per-path: aggregate that path's cells across targets × windows
   - Per-window: aggregate that window's cells across targets × paths
   - Aggregation rule per axis: any `cell_defect` wins → any `cell_carry` wins → else `cell_kill_clear`

3. **Matrix-level verdict** decision tree (in order; first match wins):
   - **`defect_located`** ONLY IF: ≥ 1 supplemental `cell_defect` reproduced across ≥ 2 windows (defect criteria above) AND **corroborated across an orthogonal axis**. Orthogonal corroboration = at least one of: (a) **path-orthogonal** — same target on the other path also `cell_defect`; OR (b) **target-orthogonal** — same path on a different supplemental target also `cell_defect`; OR (c) **driver-orthogonal** — ≥ 2 of the defect cells share the same primary driver. Single-cell `defect_located` is FORBIDDEN per CLOSEOUT-01.
   - **`hypothesis_killed`** IF: kill criteria above met (control p99 ≤ 200ms on ≥ 2/3 windows AND no supplemental cell exceeds 1.5× control p99 in any window).
   - **`carried_narrower_with_close_with_prejudice_rule`** otherwise. Triggers CRITERIA-02.

**Canonical separation:** The canonical control cell (Phase 214 `dallas`) is reported on its own row in the cube. It is **never** aggregated with supplemental cells, NEVER input to MWU comparison as a supplemental, and the per-target rollup distinguishes `canonical_dallas` from `vultr_dallas`/`vultr_chicago`. AGGREGATE-02 enforced.

### CRITERIA-02 Close-with-Prejudice Rule (verbatim from REQUIREMENTS.md)

If the matrix verdict is `carried_narrower_with_close_with_prejudice_rule`, the folded `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` todo is closed-with-prejudice. No v1.48+ follow-up may reopen the thread WITHOUT independent new evidence — e.g., a real production p99 incident captured in the metrics DB. "Carried-narrower forever" is explicitly disallowed.

Phase 221's `221-CLOSEOUT.md` attaches this rule verbatim if the carry verdict fires.

### Wave 0 Fixture Strategy — hybrid

**Reuse Phase 214 `.flent.gz` fixtures** for the unchanged extractor + aligner + classifier chain. The chain is stable upstream surface; Phase 214's verification work covers it. No new `.flent.gz` capture for Phase 220 unit tests.

**Craft NEW synthetic per-cell aggregator fixtures** in `tests/fixtures/phase220/`:
- Tiny JSON `cell-evidence` documents (one per synthetic cell) with pinned `p50_ms`/`p95_ms`/`p99_ms`/`primary_driver`/`per_second_samples[]` fields — the minimum surface the aggregator consumes.
- Cover at least: (a) all-clean canonical + all-clean supplemental → `hypothesis_killed`; (b) canonical clean + one supplemental cell over threshold in 1 window → `cell_defect` but matrix carries (single-window not "reproduced"); (c) canonical clean + same supplemental cell over threshold in 2 windows + no orthogonal corroboration → matrix carries; (d) canonical clean + supplemental defect reproduced + path-orthogonal corroboration → `defect_located`; (e) canonical clean + supplemental defect reproduced + driver-orthogonal corroboration → `defect_located`.
- Pin MWU p-values and bootstrap 95% percentile CI bounds for two canonical pairwise comparisons using seeded `random.Random(220)`, B=2000. Two pins ≥ acceptance signal without over-pinning.

**Why hybrid:** don't re-test what isn't changing. The aggregator is the novel surface; pinning real `.flent.gz`-derived MWU outputs adds determinism noise without testing aggregator-specific logic.

### Mutation-Boundary Scope (SAFE-11) — Phase 220 allowlist

**Allowlisted for additive edits this phase:**
- `scripts/phase220-matrix.yaml` (new file)
- `scripts/phase220-target-path-matrix.sh` (new file)
- `scripts/phase220-matrix-aggregator.py` (new file)
- `tests/test_phase220_matrix_aggregator.py` (new file)
- `tests/test_phase220_matrix_wrapper.py` (new file — dry-run gate behavior)
- `tests/test_phase220_mutation_boundary.py` (new file — SAFE-11 boundary clone of Phase 214/219 pattern)
- `tests/fixtures/phase220/` (new — synthetic aggregator fixtures + observed evidence shape only; no `expected_behavior_*.json`)
- `docs/` — describe new CLI tool only; NO threshold-tuning language; NO future-tuning prediction

**Forbidden (mutation-boundary enforced):**
- `src/wanctl/wan_controller.py`, `queue_controller.py`, `cake_signal.py`
- All RouterOS/CAKE backends, `alert_engine.py`, fusion code
- Existing Phase 213 / Phase 214 scripts (MATRIX-02 "zero edits to existing Phase 213/214 scripts")
- Anything in the daemon hot path

### `base_sha` Anchor Mechanism (Claude discretion, recorded for traceability)

- `base_sha` field in `phase220-matrix.yaml` is set at Phase 220 plan-commit time to `git rev-parse HEAD` of the Phase 220 plan commit.
- Per-cell wrapper triple-checks `src/wanctl/` cleanliness via D-14 guard against this `base_sha` at every cell start.
- Multi-day Phase 221 runs that drift off `base_sha` fail closed; recovery requires explicit operator decision (not in Phase 220 scope to design recovery).

### `mtr`/traceroute Snapshot Mechanics (Claude discretion)

- Per-cell pre-flight `mtr --no-dns --report -c 10 <target>` snapshot stored in the cell's evidence sidecar manifest as `mtr_snapshot.txt`.
- Per-cell post-flight `mtr` repeat ONLY if pre-flight differs from the previous cell's post-flight for the same target (BGP path change detection — Pitfall 4 mitigation).
- Snapshot path referenced from the per-cell `signal-sheet.json` so the closeout report can cite it (CLOSEOUT-02 row requirement).

### Folded Todos

- **`2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl`** (score 0.9, tuning) — primary target. The folded todo motivates the entire CRITERIA-01 pre-registration and the matrix definition. Phase 221's `221-CLOSEOUT.md` updates this todo with the verdict and either marks it closed or attaches the close-with-prejudice rule per CLOSEOUT-03. Phase 220 does NOT close the todo (that's Phase 221's work).
- **`2026-04-17-ingestion-rate-tool`** (score 0.9, tooling) — already CLOSED by Phase 219. Listed only to acknowledge the matcher's auto-surface.

### Claude's Discretion

- Exact YAML schema layout of `phase220-matrix.yaml` (canonical/supplemental discriminator field name, per-cell knobs, per-window window-hour overrides) — pick the cleanest extension of Phase 214's per-window YAML pattern; document inline.
- Per-cell sidecar manifest schema — extend Phase 214 sidecar manifest with cube discriminator fields (`target_kind: canonical|supplemental`, `target_name`, `path_name`, `window_name`, `replicate_index`).
- Mann-Whitney U two-sided normal approximation tie-handling — use the stdlib `statistics`-friendly Wilcoxon mid-rank tie correction; document the chosen variant inline.
- Bootstrap percentile CI corner cases (all-equal samples, single-sample inputs) — return explicit `degenerate: true` field on the CI dict rather than crashing.
- Aggregator output JSON schema version field — start at `schema_version: 1` (matches Phase 219 D-17 convention; future cube extensions can fork).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 220 source-of-truth
- `.planning/REQUIREMENTS.md` — CRITERIA-01, CRITERIA-02, MATRIX-01..04, AGGREGATE-01..03, SAFE-11 (and the locked CRITERIA-01 example used verbatim in this CONTEXT)
- `.planning/ROADMAP.md` §Phase 220 — Success Criteria #1–5
- `.planning/STATE.md` §Cross-Cutting Invariants — v1.47 read-only posture, stdlib-only mandate, pre-registered kill/defect rule, canonical control mandate, per-replicate IP-pinning, cycle-budget guard

### v1.47 research (pitfall mitigation + scope rationale)
- `.planning/research/PITFALLS.md` — Pitfall 2 (data-driven threshold leakage → forbids editing thresholds after first live cell), Pitfall 4 (BGP path change mid-run → mtr per-cell), Pitfall 8 (mutation boundary), Pitfall 11 (D-first sequencing — Phase 219 first), Pitfall 12 (`/health` is never quality)
- `.planning/research/SUMMARY.md` — Scope A rationale and confirm-or-kill posture
- `.planning/research/ARCHITECTURE.md` — read-only milestone architecture posture
- `.planning/research/STACK.md` — stdlib-only mandate (`statistics`, `random`, `math`, `json` only; no SciPy/NumPy/pandas)

### Phase 214 anchor (canonical control + analyzer chain reuse)
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/` (if archived under v1.46) or `.planning/phases/214-measurement-collapse-investigation/` — canonical `dallas` reflector identity, six-driver classifier definition, Wrapper Composition Pattern, sidecar manifest schema
- `scripts/phase214-flent-matrix.sh` — Wrapper Composition Pattern reference (window gate → D-14 source mutation refusal → delegate to `phase213-baseline-capture.sh` → bounded journal capture → sidecar manifest). Phase 220 wrapper MUST mirror this structure verbatim (MATRIX-02 zero-edits requirement)
- `scripts/phase214-extract.py`, `scripts/phase214-align.py`, `scripts/phase214-classify.py` — analyzer chain reused UNCHANGED (MATRIX-04)
- `scripts/phase214-matrix-summary.py` — base for the Phase 220 cube aggregator fork (AGGREGATE-01)

### Phase 213 harness (composed unchanged)
- `scripts/phase213-baseline-capture.sh` — source-bind + egress IP verification, flent invocation, health polling, alert pulls, steering snapshots (MATRIX-03 source-bind/egress harness enforcement)

### Phase 219 precedent (D-17 envelope convention + atomic write + test scaffold)
- `.planning/phases/219-ingestion-rate-observability-scope-d/219-CONTEXT.md` D-17 — JSON `schema_version` envelope convention reused by the aggregator output
- `src/wanctl/state_utils.py` `atomic_write_json` — IF the aggregator emits its own JSON snapshot, reuse this helper (same boundary relaxation rationale as Phase 219 D-21)

### Phase 217 anchor (cycle-budget posture; Phase 220 is build-only, no production deploy)
- `.planning/milestones/v1.46-phases/217-production-cycle-budget-baseline/` — `cycle_total.avg_ms ≤ 3.0`, `p99_ms ≤ 7.5` (Phase 220 does NOT change controller; included for v1.47 cross-cutting invariant awareness only)

### Folded todo
- `.planning/todos/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — primary target hypothesis

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase214-flent-matrix.sh` — Wrapper Composition Pattern (window gate + D-14 + delegate + sidecar). Forking pattern, not file.
- `scripts/phase214-matrix-summary.py` `matrix_verdict()` — single-axis verdict rollup logic that Phase 220 extends to per-target/per-path/per-window cube rollup.
- `scripts/phase213-baseline-capture.sh` — base capture invocation; composed by every Phase 220 cell.
- `src/wanctl/state_utils.py` `atomic_write_json` — if aggregator emits JSON snapshots.
- Phase 214 `tests/test_phase214_mutation_boundary.py` (and Phase 219 sibling) — clone pattern for Phase 220 SAFE-11 boundary test.

### Established Patterns
- **Wrapper Composition Pattern** (MATRIX-02): gate entry → triple-check `src/wanctl/` cleanliness via D-14 → window-hour gate → delegate to `phase213-baseline-capture.sh` → pull journal via SSH → write phase-owned sidecar manifest. Zero edits to existing Phase 213/214 scripts.
- **Sidecar manifest convention** (Phase 214): per-cell evidence directory with `signal-sheet.json` carrying the classifier verdict + ranked drivers + p50/p95/p99.
- **Stdlib-only statistics** (Phase 214 D-10): MWU + bootstrap CI implemented in `statistics`/`random`/`math` — no third-party deps. Seeded via `random.Random(seed)` for golden tests.
- **D-17 JSON envelope** (Phase 219): `{"schema_version": 1, ...}` for any new JSON output surface.
- **Mutation-boundary pytest** (Phase 214, 219): clone pattern; per-phase allowlist hard-coded; controller-path forbidden list hard-coded; fails closed on dirty/staged/untracked surfaces.

### Integration Points
- Aggregator consumes per-cell `signal-sheet.json` outputs (Phase 214 schema) — extend, don't replace.
- Wrapper delegates traffic generation to `phase213-baseline-capture.sh` — pass-through, no in-script tcpdump/flent invocation.
- Journal capture via SSH alias `cake-shaper` (matches `PHASE214_CAKE_SHAPER` env default).
- `base_sha` from `git rev-parse HEAD` at plan-commit time; cell wrapper enforces via D-14 guard.

</code_context>

<specifics>
## Specific Ideas

- CRITERIA-01 kill + defect language is taken verbatim from REQUIREMENTS.md §CRITERIA so REQ-traceability is exact and Phase 221 closeout can cite by-reference.
- Wave 0 synthetic fixtures cover five rollup paths explicitly (all-clean kill, single-window non-reproduced carry, two-window non-corroborated carry, path-orthogonal-corroborated defect, driver-orthogonal-corroborated defect) — minimum surface to verify the orthogonal-corroboration rule.
- Pinning two MWU + bootstrap CI pairs is the minimum to detect (a) p-value computation drift and (b) bootstrap reseeding drift; more pins are over-fitting golden tests.
- `random.Random(220)` chosen as the bootstrap seed for thematic consistency with the phase number — operationally arbitrary but documented.

</specifics>

<deferred>
## Deferred Ideas

- Aggregator visualization (heat-map / sparkline output) — not in scope; closeout report is markdown-only.
- Auto-rotating supplemental target pool — anti-feature per REQUIREMENTS.md (undermines reproducibility).
- DSCP marking probe — anti-feature per REQUIREMENTS.md (scope-drift risk from confirm-or-kill narrow scope).
- Cube projection to additional axes (time-of-day-hour, weekday, weather, RouterOS uptime) — interesting later, out of scope for confirm-or-kill matrix.
- `mtr` path-change auto-replan (skip cell if BGP changed) — adds operational opacity; for now fail closed and let operator re-trigger.
- Multi-protocol matrix (UDP_FLOOD, tcp_1up, RRUL) — out of scope; tcp_12down only per the folded todo's scope.
- ML/prediction for next-best-target — anti-feature per REQUIREMENTS.md.

### Reviewed Todos (not folded)
- `2026-04-17-operator-summary-digest-permission-handling` (score 0.9, tooling) — unrelated to Phase 220 matrix work; belongs to a tooling-hygiene phase. NOT folded.
- `2026-04-17-investigate-steering-degraded-on-clean-restart` (score 0.6, steering) — out of scope for v1.47 read-only milestone; pending operator approval (STEER-DRIFT-01 family).
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` (score 0.6, alerting) — Phase 218 watch-list item; parallel to v1.47.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196` (score 0.6, validation) — gated on Phase 191 closure; unrelated to matrix scope.
- `2026-04-28-add-silicom-bypass-nic-operational-tooling`, `2026-04-28-add-silicom-bypass-test-harness` (both 0.6, SEED-006 dormant) — out of scope for v1.47.

</deferred>

---

*Phase: 220-matrix-runner-scope-a1*
*Context gathered: 2026-05-30 via /gsd:discuss-phase*
*CRITERIA-01 thresholds LOCKED — never edit after first live cell run (REQ pre-registration rule)*
